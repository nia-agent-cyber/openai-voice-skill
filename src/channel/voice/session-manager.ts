/**
 * Voice Session Manager
 * 
 * Manages OpenClaw sessions for voice calls, including:
 * - Session lifecycle management
 * - Session linking across channels
 * - Session persistence and recovery
 * - Caller identity tracking
 */

import { OpenClawSession } from '@openclaw/types';
import { VoiceConfig, VoiceSession, CallState, CallerHistory, SessionLinkingOptions } from './types';
import { v4 as uuidv4 } from 'uuid';
import { EventEmitter } from 'events';

export class VoiceSessionManager extends EventEmitter {
  private sessions: Map<string, VoiceSession> = new Map();
  private sessionsByCallId: Map<string, string> = new Map(); // callId -> sessionId
  private sessionsByPhone: Map<string, string[]> = new Map(); // phoneNumber -> sessionIds[]
  private callerHistory: Map<string, CallerHistory> = new Map();
  private config: VoiceConfig;
  
  constructor(config: VoiceConfig) {
    super();
    this.config = config;
  }

  async initialize(): Promise<void> {
    // Load caller history from persistent storage
    await this.loadCallerHistory();
    
    // Set up cleanup interval for ended sessions
    setInterval(() => this.cleanupEndedSessions(), 5 * 60 * 1000); // Every 5 minutes
  }

  /**
   * Create a new voice session for incoming call
   */
  async createSession(
    callId: string,
    phoneNumber: string,
    metadata?: Record<string, any>
  ): Promise<VoiceSession> {
    const sessionId = uuidv4();
    const now = new Date();
    
    // Get caller history
    const history = await this.getCallerHistory(phoneNumber);
    
    const session: VoiceSession = {
      id: sessionId,
      channel: 'voice',
      createdAt: now,
      lastActivity: now,
      metadata: metadata || {},
      
      voiceData: {
        callId,
        phoneNumber,
        direction: 'inbound',
        callState: 'ringing',
        startTime: now,
        transcript: []
      },
      
      context: {
        callerHistory: history,
        contextTokensUsed: 0,
        lastContextUpdate: now
      },
      
      linkedSessions: []
    };
    
    // Store session mappings
    this.sessions.set(sessionId, session);
    this.sessionsByCallId.set(callId, sessionId);
    this.addPhoneMapping(phoneNumber, sessionId);
    
    this.emit('sessionCreated', session);
    
    return session;
  }

  /**
   * Create a new session for outbound call
   */
  async createOutboundSession(
    phoneNumber: string,
    callerIdHint?: string,
    contextHint?: string
  ): Promise<VoiceSession> {
    const sessionId = uuidv4();
    const callId = `outbound_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const now = new Date();
    
    // Get caller history
    const history = await this.getCallerHistory(phoneNumber);
    
    const session: VoiceSession = {
      id: sessionId,
      channel: 'voice',
      createdAt: now,
      lastActivity: now,
      metadata: { callerIdHint, contextHint },
      
      voiceData: {
        callId,
        phoneNumber,
        direction: 'outbound',
        callState: 'ringing',
        startTime: now,
        transcript: [],
        callerIdHint
      },
      
      context: {
        callerHistory: history,
        callSpecificInstructions: contextHint,
        contextTokensUsed: 0,
        lastContextUpdate: now
      },
      
      linkedSessions: []
    };
    
    // Store session mappings
    this.sessions.set(sessionId, session);
    this.sessionsByCallId.set(callId, sessionId);
    this.addPhoneMapping(phoneNumber, sessionId);
    
    this.emit('sessionCreated', session);
    
    return session;
  }

  /**
   * Get session by ID
   */
  async getSession(sessionId: string): Promise<VoiceSession | null> {
    return this.sessions.get(sessionId) || null;
  }

  /**
   * Get session by call ID
   */
  async getSessionByCallId(callId: string): Promise<VoiceSession | null> {
    const sessionId = this.sessionsByCallId.get(callId);
    if (!sessionId) return null;
    return this.getSession(sessionId);
  }

  /**
   * Get all active sessions
   */
  async getActiveSessions(): Promise<VoiceSession[]> {
    return Array.from(this.sessions.values()).filter(
      session => session.voiceData.callState === 'active' || session.voiceData.callState === 'ringing'
    );
  }

  /**
   * Get sessions by phone number
   */
  async getSessionsByPhone(phoneNumber: string): Promise<VoiceSession[]> {
    const sessionIds = this.sessionsByPhone.get(phoneNumber) || [];
    const sessions = await Promise.all(
      sessionIds.map(id => this.getSession(id))
    );
    return sessions.filter(s => s !== null) as VoiceSession[];
  }

  /**
   * Update session call state
   */
  async updateCallState(sessionId: string, state: CallState): Promise<void> {
    const session = await this.getSession(sessionId);
    if (!session) return;

    const oldState = session.voiceData.callState;
    session.voiceData.callState = state;
    session.lastActivity = new Date();

    // Handle state transitions
    if (oldState !== 'active' && state === 'active') {
      session.voiceData.startTime = new Date();
      this.emit('callAnswered', session);
    }
    
    if (state === 'ended') {
      session.voiceData.endTime = new Date();
      session.voiceData.duration = session.voiceData.endTime.getTime() - session.voiceData.startTime.getTime();
      this.emit('callEnded', session);
    }
    
    if (state === 'failed') {
      this.emit('callFailed', session);
    }

    this.emit('callStateChanged', session, oldState, state);
  }

  /**
   * Link voice session to existing OpenClaw session
   */
  async linkSession(
    voiceSessionId: string,
    openClawSessionId: string,
    options: SessionLinkingOptions = {
      inheritContext: true,
      syncMemory: true,
      notifyLinkedChannels: false
    }
  ): Promise<void> {
    const session = await this.getSession(voiceSessionId);
    if (!session) {
      throw new Error(`Voice session ${voiceSessionId} not found`);
    }

    // Add to linked sessions
    if (!session.linkedSessions.includes(openClawSessionId)) {
      session.linkedSessions.push(openClawSessionId);
    }

    this.emit('sessionLinked', session, openClawSessionId, options);
  }

  /**
   * End a session
   */
  async endSession(sessionId: string): Promise<void> {
    const session = await this.getSession(sessionId);
    if (!session) return;

    // Update caller history
    await this.updateCallerHistory(session);
    
    // Clean up mappings
    this.sessionsByCallId.delete(session.voiceData.callId);
    this.removePhoneMapping(session.voiceData.phoneNumber, sessionId);
    this.sessions.delete(sessionId);
    
    this.emit('sessionEnded', session);
  }

  /**
   * Get caller history
   */
  private async getCallerHistory(phoneNumber: string): Promise<CallerHistory> {
    let history = this.callerHistory.get(phoneNumber);
    
    if (!history) {
      history = {
        phoneNumber,
        previousCalls: [],
        knownIdentity: undefined
      };
      this.callerHistory.set(phoneNumber, history);
    }
    
    return history;
  }

  /**
   * Update caller history after call
   */
  private async updateCallerHistory(session: VoiceSession): Promise<void> {
    const history = await this.getCallerHistory(session.voiceData.phoneNumber);
    
    if (session.voiceData.endTime && session.voiceData.duration) {
      history.previousCalls.push({
        date: session.voiceData.startTime,
        duration: session.voiceData.duration,
        summary: this.generateCallSummary(session)
      });
      
      // Keep only last 10 calls
      if (history.previousCalls.length > 10) {
        history.previousCalls = history.previousCalls.slice(-10);
      }
    }
    
    // Update linked sessions
    if (session.linkedSessions.length > 0) {
      if (!history.knownIdentity) {
        history.knownIdentity = { linkedSessions: [] };
      }
      
      session.linkedSessions.forEach(linkedId => {
        if (!history.knownIdentity!.linkedSessions.includes(linkedId)) {
          history.knownIdentity!.linkedSessions.push(linkedId);
        }
      });
    }
    
    // Persist to storage
    await this.saveCallerHistory();
  }

  /**
   * Generate call summary
   */
  private generateCallSummary(session: VoiceSession): string {
    const transcript = session.voiceData.transcript;
    if (!transcript || transcript.length === 0) {
      return 'Call completed (no transcript available)';
    }
    
    // Simple summary logic - in production this could use LLM summarization
    const userMessages = transcript.filter(t => t.speaker === 'user').length;
    const agentMessages = transcript.filter(t => t.speaker === 'agent').length;
    
    return `Call with ${userMessages} user messages, ${agentMessages} agent responses`;
  }

  /**
   * Phone number mapping helpers
   */
  private addPhoneMapping(phoneNumber: string, sessionId: string): void {
    const sessions = this.sessionsByPhone.get(phoneNumber) || [];
    if (!sessions.includes(sessionId)) {
      sessions.push(sessionId);
      this.sessionsByPhone.set(phoneNumber, sessions);
    }
  }

  private removePhoneMapping(phoneNumber: string, sessionId: string): void {
    const sessions = this.sessionsByPhone.get(phoneNumber) || [];
    const filtered = sessions.filter(id => id !== sessionId);
    
    if (filtered.length === 0) {
      this.sessionsByPhone.delete(phoneNumber);
    } else {
      this.sessionsByPhone.set(phoneNumber, filtered);
    }
  }

  /**
   * Cleanup ended sessions periodically
   */
  private cleanupEndedSessions(): void {
    const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000); // 24 hours ago
    
    for (const [sessionId, session] of this.sessions.entries()) {
      if (
        (session.voiceData.callState === 'ended' || session.voiceData.callState === 'failed') &&
        session.lastActivity < cutoff
      ) {
        this.endSession(sessionId);
      }
    }
  }

  /**
   * Load caller history from persistent storage
   */
  private async loadCallerHistory(): Promise<void> {
    // TODO: Load from file system or database
    // For now, start with empty history
  }

  /**
   * Save caller history to persistent storage
   */
  private async saveCallerHistory(): Promise<void> {
    // TODO: Save to file system or database
    // For now, keep in memory only
  }

  /**
   * Shutdown and cleanup
   */
  async shutdown(): Promise<void> {
    // Save caller history
    await this.saveCallerHistory();
    
    // End all active sessions
    const activeSessions = await this.getActiveSessions();
    await Promise.all(
      activeSessions.map(session => this.endSession(session.id))
    );
    
    // Clear all data
    this.sessions.clear();
    this.sessionsByCallId.clear();
    this.sessionsByPhone.clear();
    this.callerHistory.clear();
    
    this.removeAllListeners();
  }
}