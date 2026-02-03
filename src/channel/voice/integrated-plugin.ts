/**
 * Integrated Voice Channel Plugin for OpenClaw
 * 
 * Updated version that integrates with the existing Python webhook server
 * while providing full OpenClaw channel plugin capabilities.
 * 
 * This plugin:
 * - Manages OpenClaw sessions and context
 * - Integrates with proven Python voice infrastructure
 * - Provides seamless voice <-> OpenClaw message bridging
 * - Supports memory persistence and cross-channel linking
 */

import { ChannelPlugin, OpenClawSession, OpenClawMessage, ChannelCapability } from '@openclaw/types';
import { VoiceSessionManager } from './session-manager';
import { VoiceContextManager } from './context-manager';
import { IntegratedVoiceCallHandler } from './integrated-call-handler';
import { VoiceConfig, VoiceSession, VoiceMessage } from './types';

export class IntegratedVoiceChannelPlugin implements ChannelPlugin {
  public readonly name = 'voice' as const;
  public readonly capabilities: ChannelCapability[] = [
    'inbound',
    'outbound', 
    'realtime',
    'audio'
  ];

  private sessionManager: VoiceSessionManager;
  private contextManager: VoiceContextManager;
  private callHandler: IntegratedVoiceCallHandler;
  private config: VoiceConfig;
  private isInitialized: boolean = false;

  constructor(config: VoiceConfig) {
    this.config = config;
    this.sessionManager = new VoiceSessionManager(config);
    this.contextManager = new VoiceContextManager(config);
    this.callHandler = new IntegratedVoiceCallHandler(config, this.sessionManager, this.contextManager);
  }

  /**
   * Initialize the voice channel plugin
   */
  async initialize(): Promise<void> {
    if (this.isInitialized) {
      return;
    }

    try {
      // Initialize components in order
      await this.sessionManager.initialize();
      await this.contextManager.initialize();
      await this.callHandler.initialize();
      
      // Set up event forwarding
      this.setupEventForwarding();
      
      this.isInitialized = true;
      console.log('🎙️ Integrated Voice Channel Plugin initialized');
      
    } catch (error) {
      console.error('Failed to initialize Voice Channel Plugin:', error);
      throw new Error(`Voice Channel Plugin initialization failed: ${error.message}`);
    }
  }

  /**
   * Create an OpenClaw session for a voice call
   */
  async createSession(callId: string, phoneNumber: string, metadata?: Record<string, any>): Promise<OpenClawSession> {
    this.ensureInitialized();
    
    const session = await this.sessionManager.createSession(callId, phoneNumber, metadata);
    
    // Inject relevant context from OpenClaw
    await this.contextManager.injectContext(session);
    
    return session;
  }

  /**
   * Handle outgoing message from OpenClaw to voice
   */
  async sendMessage(sessionId: string, message: OpenClawMessage): Promise<void> {
    this.ensureInitialized();
    
    const session = await this.sessionManager.getSession(sessionId);
    if (!session || !(session as VoiceSession).voiceData) {
      throw new Error(`Voice session ${sessionId} not found`);
    }

    // Convert OpenClaw message to voice response
    await this.callHandler.sendVoiceMessage(session as VoiceSession, message);
  }

  /**
   * Handle incoming audio from voice call
   * 
   * Note: Audio processing is handled by the Python webhook server.
   * This method is provided for completeness and future enhancements.
   */
  async receiveAudio(sessionId: string, audioData: Buffer, metadata?: Record<string, any>): Promise<void> {
    this.ensureInitialized();
    
    const session = await this.sessionManager.getSession(sessionId);
    if (!session || !(session as VoiceSession).voiceData) {
      throw new Error(`Voice session ${sessionId} not found`);
    }

    // Audio processing is handled by Python server via webhook events
    await this.callHandler.handleIncomingAudio(session as VoiceSession, audioData, metadata);
  }

  /**
   * Handle incoming voice call
   * 
   * This will be triggered by webhook events from the Python server
   */
  async handleIncomingCall(callId: string, phoneNumber: string, metadata?: Record<string, any>): Promise<string> {
    this.ensureInitialized();
    
    // Create session for the call
    const session = await this.createSession(callId, phoneNumber, metadata) as VoiceSession;
    
    // Accept the call with OpenClaw context
    // The Python server handles the actual OpenAI API call acceptance
    await this.callHandler.acceptCall(session);
    
    return session.id;
  }

  /**
   * Initiate outgoing voice call
   */
  async initiateOutgoingCall(
    phoneNumber: string, 
    callerIdHint?: string, 
    contextHint?: string
  ): Promise<string> {
    this.ensureInitialized();
    
    // Generate a unique call ID for tracking
    const callId = `outbound_${Date.now()}_${Math.random().toString(36).substring(7)}`;
    
    const session = await this.sessionManager.createOutboundSession(phoneNumber, callerIdHint, contextHint) as VoiceSession;
    
    // Set the call ID
    session.voiceData.callId = callId;
    
    // Inject context for outbound call
    await this.contextManager.injectContext(session);
    
    // Initiate the call via the integrated handler (which uses Python bridge)
    await this.callHandler.initiateCall(session);
    
    return session.id;
  }

  /**
   * End a voice call and cleanup session
   */
  async endCall(sessionId: string): Promise<void> {
    this.ensureInitialized();
    
    const session = await this.sessionManager.getSession(sessionId);
    if (!session || !(session as VoiceSession).voiceData) {
      return; // Already ended or not a voice session
    }

    const voiceSession = session as VoiceSession;
    
    // End the call via integrated handler
    await this.callHandler.endCall(voiceSession);
    
    // Persist session memory to OpenClaw context
    await this.contextManager.persistSession(voiceSession);
    
    // Cleanup session
    await this.sessionManager.endSession(sessionId);
  }

  /**
   * Get active voice sessions
   */
  async getActiveSessions(): Promise<OpenClawSession[]> {
    this.ensureInitialized();
    return this.sessionManager.getActiveSessions();
  }

  /**
   * Get session by ID
   */
  async getSession(sessionId: string): Promise<OpenClawSession | null> {
    this.ensureInitialized();
    return this.sessionManager.getSession(sessionId);
  }

  /**
   * Link voice session to existing OpenClaw session
   */
  async linkToSession(voiceSessionId: string, openClawSessionId: string): Promise<void> {
    this.ensureInitialized();
    
    await this.sessionManager.linkSession(voiceSessionId, openClawSessionId);
    
    // Re-inject context with linked session data
    const session = await this.sessionManager.getSession(voiceSessionId);
    if (session) {
      await this.contextManager.injectContext(session as VoiceSession);
    }
  }

  /**
   * Transfer conversation from voice to another channel
   */
  async handoffToChannel(sessionId: string, targetChannel: string): Promise<void> {
    this.ensureInitialized();
    
    const session = await this.sessionManager.getSession(sessionId);
    if (!session || !(session as VoiceSession).voiceData) {
      throw new Error(`Voice session ${sessionId} not found`);
    }

    const voiceSession = session as VoiceSession;

    // Prepare handoff context
    const handoffContext = await this.contextManager.prepareHandoffContext(voiceSession, targetChannel);
    
    // Persist current conversation
    await this.contextManager.persistSession(voiceSession);
    
    // TODO: Integrate with OpenClaw's channel routing system
    // This would notify the target channel about the handoff
    console.log(`Handoff prepared for session ${sessionId} to channel ${targetChannel}`, handoffContext);
    
    // End voice session
    await this.endCall(sessionId);
  }

  /**
   * Get channel-specific status and metrics
   */
  async getChannelStatus(): Promise<any> {
    this.ensureInitialized();
    
    const activeSessions = await this.getActiveSessions();
    const bridgeStatus = this.callHandler.getBridgeStatus();
    
    return {
      plugin: {
        name: this.name,
        initialized: this.isInitialized,
        capabilities: this.capabilities
      },
      sessions: {
        active: activeSessions.length,
        total: activeSessions.length // TODO: Add historical count
      },
      bridge: bridgeStatus,
      python_server: {
        healthy: bridgeStatus.healthy,
        integration: 'active'
      },
      config: {
        memory_enabled: this.config.openclaw.memoryEnabled,
        recording_enabled: this.config.call.recordCalls,
        cross_channel_enabled: this.config.openclaw.crossChannelEnabled
      }
    };
  }

  /**
   * Handle webhook events (called by external webhook handlers)
   */
  async handleWebhookEvent(eventType: string, eventData: any): Promise<void> {
    this.ensureInitialized();
    
    switch (eventType) {
      case 'incoming_call':
        await this.handleIncomingCall(
          eventData.call_id,
          eventData.phone_number,
          eventData.metadata
        );
        break;
        
      case 'call_ended':
        if (eventData.session_id) {
          await this.endCall(eventData.session_id);
        }
        break;
        
      default:
        console.log(`Unhandled webhook event: ${eventType}`, eventData);
    }
  }

  /**
   * Setup event forwarding from components
   */
  private setupEventForwarding(): void {
    // Forward call handler events
    this.callHandler.on('messageReceived', (session: VoiceSession, message: VoiceMessage) => {
      // This would typically be forwarded to OpenClaw's message routing system
      console.log(`Voice message received from ${session.voiceData.phoneNumber}:`, message.content);
    });
    
    this.callHandler.on('callAnswered', (session: VoiceSession) => {
      console.log(`Call answered: ${session.voiceData.callId} from ${session.voiceData.phoneNumber}`);
    });
    
    this.callHandler.on('callEnded', (session: VoiceSession) => {
      console.log(`Call ended: ${session.voiceData.callId}`);
    });
    
    this.callHandler.on('transcriptUpdated', (session: VoiceSession, entry: any) => {
      console.log(`Transcript updated for ${session.voiceData.callId}: ${entry.text}`);
    });
    
    this.callHandler.on('bridgeHealthChanged', (status: any) => {
      console.log(`Python bridge health changed:`, status);
    });
  }

  /**
   * Ensure plugin is initialized before operations
   */
  private ensureInitialized(): void {
    if (!this.isInitialized) {
      throw new Error('Voice Channel Plugin not initialized. Call initialize() first.');
    }
  }

  /**
   * Cleanup and shutdown
   */
  async shutdown(): Promise<void> {
    if (!this.isInitialized) {
      return;
    }

    console.log('🎙️ Shutting down Voice Channel Plugin...');
    
    // End all active calls
    const activeSessions = await this.getActiveSessions();
    await Promise.all(
      activeSessions.map(session => 
        this.endCall(session.id).catch(error => 
          console.error(`Error ending call ${session.id}:`, error)
        )
      )
    );
    
    // Shutdown components
    await this.callHandler.shutdown();
    await this.sessionManager.shutdown();
    await this.contextManager.shutdown();
    
    this.isInitialized = false;
    console.log('🎙️ Voice Channel Plugin shut down');
  }
}

export { VoiceConfig, VoiceSession, VoiceMessage, IntegratedVoiceCallHandler };
export * from './types';