/**
 * Voice Context Manager
 * 
 * Handles OpenClaw context integration for voice calls:
 * - Memory file access (MEMORY.md, daily files)
 * - Cross-channel context injection
 * - Context persistence after calls
 * - Dynamic context updates during calls
 */

import { VoiceConfig, VoiceSession, ContextInjectionResult, CallHandoffContext, VoiceSessionContext } from './types';
import { EventEmitter } from 'events';
import * as fs from 'fs/promises';
import * as path from 'path';

export class VoiceContextManager extends EventEmitter {
  private config: VoiceConfig;
  private memoryCache: Map<string, { content: string; lastModified: number }> = new Map();
  
  constructor(config: VoiceConfig) {
    super();
    this.config = config;
  }

  async initialize(): Promise<void> {
    // Validate workspace directory
    try {
      await fs.access(this.config.openclaw.workspaceDir);
    } catch (error) {
      throw new Error(`OpenClaw workspace directory not accessible: ${this.config.openclaw.workspaceDir}`);
    }
    
    // Set up file system watchers for memory files
    if (this.config.openclaw.memoryEnabled) {
      this.setupMemoryFileWatchers();
    }
  }

  /**
   * Inject relevant OpenClaw context into a voice session
   */
  async injectContext(session: VoiceSession): Promise<ContextInjectionResult> {
    const startTime = Date.now();
    let tokensUsed = 0;
    const contextSources: string[] = [];

    try {
      const context: VoiceSessionContext = {
        contextTokensUsed: 0,
        lastContextUpdate: new Date()
      };

      // Load core agent identity
      if (await this.fileExists('SOUL.md')) {
        context.agentIdentity = await this.loadAndCondenseFile('SOUL.md');
        contextSources.push('SOUL.md');
        tokensUsed += this.estimateTokens(context.agentIdentity);
      }

      // Load user profile
      if (await this.fileExists('USER.md')) {
        context.userProfile = await this.loadAndCondenseFile('USER.md');
        contextSources.push('USER.md');
        tokensUsed += this.estimateTokens(context.userProfile);
      }

      // Load recent memory (last 2-3 days)
      if (this.config.openclaw.memoryEnabled) {
        context.recentMemory = await this.loadRecentMemory(2);
        if (context.recentMemory) {
          contextSources.push('recent_memory');
          tokensUsed += this.estimateTokens(context.recentMemory);
        }
      }

      // Load cross-channel context if session is linked
      if (this.config.openclaw.crossChannelEnabled && session.linkedSessions.length > 0) {
        context.crossChannelContext = await this.loadCrossChannelContext(session.linkedSessions);
        if (context.crossChannelContext) {
          contextSources.push('cross_channel');
          tokensUsed += this.estimateTokens(context.crossChannelContext);
        }
      }

      // Load active tasks/projects
      context.activeTasks = await this.loadActiveTasks();
      if (context.activeTasks) {
        contextSources.push('active_tasks');
        tokensUsed += this.estimateTokens(context.activeTasks);
      }

      // Apply token limit
      if (tokensUsed > this.config.openclaw.contextMaxTokens) {
        context = await this.condenseContext(context, this.config.openclaw.contextMaxTokens);
        tokensUsed = this.config.openclaw.contextMaxTokens;
      }

      // Update session context
      session.context = { ...session.context, ...context };
      session.context.contextTokensUsed = tokensUsed;
      session.context.lastContextUpdate = new Date();

      this.emit('contextInjected', session, {
        tokensUsed,
        contextSources,
        latencyMs: Date.now() - startTime
      });

      return {
        success: true,
        tokensUsed,
        contextSources
      };

    } catch (error) {
      this.emit('contextInjectionError', session, error);
      
      return {
        success: false,
        tokensUsed: 0,
        contextSources: [],
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  /**
   * Prepare context for handoff to another channel
   */
  async prepareHandoffContext(session: VoiceSession, targetChannel: string): Promise<CallHandoffContext> {
    return {
      sessionId: session.id,
      targetChannel,
      conversationSummary: await this.generateConversationSummary(session),
      transcript: session.voiceData.transcript || [],
      contextSnapshot: session.context,
      handoffReason: `Voice call handoff to ${targetChannel}`,
      timestamp: new Date()
    };
  }

  /**
   * Persist session memory to OpenClaw context files
   */
  async persistSession(session: VoiceSession): Promise<void> {
    if (!this.config.openclaw.memoryEnabled) return;

    const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
    const memoryDir = path.join(this.config.openclaw.workspaceDir, 'memory');
    const dailyMemoryFile = path.join(memoryDir, `${today}.md`);

    // Ensure memory directory exists
    await fs.mkdir(memoryDir, { recursive: true });

    // Generate session summary
    const sessionSummary = await this.generateSessionSummary(session);
    
    // Append to daily memory file
    const timestamp = new Date().toISOString();
    const entry = `\n\n## Voice Call - ${timestamp}\n\n${sessionSummary}\n`;
    
    try {
      await fs.appendFile(dailyMemoryFile, entry, 'utf-8');
      this.emit('sessionPersisted', session, dailyMemoryFile);
    } catch (error) {
      this.emit('sessionPersistenceError', session, error);
    }

    // Update caller history in memory
    await this.updateCallerMemory(session);
  }

  /**
   * Load recent memory from daily files
   */
  private async loadRecentMemory(daysBack: number): Promise<string | undefined> {
    const memories: string[] = [];
    const now = new Date();

    for (let i = 0; i < daysBack; i++) {
      const date = new Date(now);
      date.setDate(date.getDate() - i);
      const dateStr = date.toISOString().split('T')[0];
      
      const memoryFile = path.join(this.config.openclaw.workspaceDir, 'memory', `${dateStr}.md`);
      
      try {
        const content = await this.loadAndCondenseFile(memoryFile);
        if (content) {
          memories.push(`## ${dateStr}\n${content}`);
        }
      } catch {
        // File doesn't exist, skip
      }
    }

    return memories.length > 0 ? memories.join('\n\n') : undefined;
  }

  /**
   * Load cross-channel context from linked sessions
   */
  private async loadCrossChannelContext(linkedSessionIds: string[]): Promise<string | undefined> {
    // This would integrate with OpenClaw's session management
    // For now, return a placeholder
    if (linkedSessionIds.length === 0) return undefined;
    
    return `Linked to ${linkedSessionIds.length} other session(s): ${linkedSessionIds.join(', ')}`;
  }

  /**
   * Load active tasks and projects
   */
  private async loadActiveTasks(): Promise<string | undefined> {
    // Look for common task files
    const taskFiles = ['HEARTBEAT.md', 'TODO.md', 'TASKS.md', 'PROJECTS.md'];
    
    for (const filename of taskFiles) {
      try {
        const content = await this.loadAndCondenseFile(filename);
        if (content) {
          return content;
        }
      } catch {
        // File doesn't exist, try next
      }
    }
    
    return undefined;
  }

  /**
   * Load and condense a file to fit context limits
   */
  private async loadAndCondenseFile(filename: string, maxTokens: number = 500): Promise<string | undefined> {
    const filePath = path.resolve(this.config.openclaw.workspaceDir, filename);
    
    // Check cache first
    const cached = this.memoryCache.get(filePath);
    if (cached) {
      try {
        const stat = await fs.stat(filePath);
        if (stat.mtime.getTime() <= cached.lastModified) {
          return cached.content;
        }
      } catch {
        // File no longer exists, remove from cache
        this.memoryCache.delete(filePath);
        return undefined;
      }
    }

    try {
      let content = await fs.readFile(filePath, 'utf-8');
      
      // Condense if too long
      if (this.estimateTokens(content) > maxTokens) {
        content = this.condenseText(content, maxTokens);
      }
      
      // Cache the result
      const stat = await fs.stat(filePath);
      this.memoryCache.set(filePath, {
        content,
        lastModified: stat.mtime.getTime()
      });
      
      return content;
    } catch {
      return undefined;
    }
  }

  /**
   * Check if file exists
   */
  private async fileExists(filename: string): Promise<boolean> {
    try {
      const filePath = path.resolve(this.config.openclaw.workspaceDir, filename);
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Condense context to fit within token limits
   */
  private async condenseContext(context: VoiceSessionContext, maxTokens: number): Promise<VoiceSessionContext> {
    const fields = ['agentIdentity', 'userProfile', 'recentMemory', 'crossChannelContext', 'activeTasks'];
    const tokenAllowance = Math.floor(maxTokens / fields.length);
    
    const condensed = { ...context };
    
    for (const field of fields) {
      const value = (condensed as any)[field];
      if (typeof value === 'string' && this.estimateTokens(value) > tokenAllowance) {
        (condensed as any)[field] = this.condenseText(value, tokenAllowance);
      }
    }
    
    return condensed;
  }

  /**
   * Condense text to approximate token limit
   */
  private condenseText(text: string, maxTokens: number): string {
    // Simple approximation: ~4 characters per token
    const maxChars = maxTokens * 4;
    
    if (text.length <= maxChars) return text;
    
    // Try to find a good break point
    const truncated = text.substring(0, maxChars);
    const lastNewline = truncated.lastIndexOf('\n');
    const lastPeriod = truncated.lastIndexOf('. ');
    
    const breakPoint = lastNewline > maxChars * 0.8 ? lastNewline :
                      lastPeriod > maxChars * 0.8 ? lastPeriod + 2 :
                      maxChars;
    
    return truncated.substring(0, breakPoint) + '\n\n[Content condensed...]';
  }

  /**
   * Estimate token count (rough approximation)
   */
  private estimateTokens(text: string): number {
    // Rough approximation: average of 4 characters per token
    return Math.ceil(text.length / 4);
  }

  /**
   * Generate conversation summary
   */
  private async generateConversationSummary(session: VoiceSession): Promise<string> {
    const transcript = session.voiceData.transcript;
    if (!transcript || transcript.length === 0) {
      return 'Voice call with no recorded conversation.';
    }

    // Simple summary - in production this could use LLM summarization
    const userMessages = transcript.filter(t => t.speaker === 'user');
    const duration = session.voiceData.duration || 0;
    
    return `Voice call lasting ${Math.round(duration / 1000 / 60)} minutes with ${userMessages.length} user interactions. Call ${session.voiceData.direction} from/to ${session.voiceData.phoneNumber}.`;
  }

  /**
   * Generate session summary for memory persistence
   */
  private async generateSessionSummary(session: VoiceSession): Promise<string> {
    const conversationSummary = await this.generateConversationSummary(session);
    const contextInfo = `Context sources: ${session.context.contextTokensUsed || 0} tokens from various sources.`;
    
    let linkedInfo = '';
    if (session.linkedSessions.length > 0) {
      linkedInfo = `\nLinked sessions: ${session.linkedSessions.join(', ')}`;
    }
    
    return `**Phone:** ${session.voiceData.phoneNumber}\n**Direction:** ${session.voiceData.direction}\n**Summary:** ${conversationSummary}\n**Context:** ${contextInfo}${linkedInfo}`;
  }

  /**
   * Update caller-specific memory
   */
  private async updateCallerMemory(session: VoiceSession): Promise<void> {
    // This could maintain caller-specific memory files
    // For now, just emit an event
    this.emit('callerMemoryUpdated', session);
  }

  /**
   * Set up file system watchers for memory files
   */
  private setupMemoryFileWatchers(): void {
    // This would set up file watchers to invalidate cache when memory files change
    // Implementation would depend on the specific file watching library used
    this.emit('memoryWatchersSetup');
  }

  /**
   * Shutdown and cleanup
   */
  async shutdown(): Promise<void> {
    this.memoryCache.clear();
    this.removeAllListeners();
  }
}