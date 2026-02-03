/**
 * Voice Channel Plugin for OpenClaw
 * 
 * Integrates voice calls as a first-class OpenClaw channel with:
 * - Session management and persistence
 * - Memory integration and context awareness
 * - Cross-channel session linking
 * - Full OpenClaw workflow integration
 */

import { ChannelPlugin, OpenClawSession, OpenClawMessage, ChannelCapability } from '@openclaw/types';
import { VoiceSessionManager } from './session-manager';
import { VoiceContextManager } from './context-manager';
import { VoiceCallHandler } from './call-handler';
import { VoiceConfig } from './types';

export class VoiceChannelPlugin implements ChannelPlugin {
  public readonly name = 'voice' as const;
  public readonly capabilities: ChannelCapability[] = [
    'inbound',
    'outbound', 
    'realtime',
    'audio'
  ];

  private sessionManager: VoiceSessionManager;
  private contextManager: VoiceContextManager;
  private callHandler: VoiceCallHandler;
  private config: VoiceConfig;

  constructor(config: VoiceConfig) {
    this.config = config;
    this.sessionManager = new VoiceSessionManager(config);
    this.contextManager = new VoiceContextManager(config);
    this.callHandler = new VoiceCallHandler(config, this.sessionManager, this.contextManager);
  }

  /**
   * Initialize the voice channel plugin
   */
  async initialize(): Promise<void> {
    await this.sessionManager.initialize();
    await this.contextManager.initialize();
    await this.callHandler.initialize();
  }

  /**
   * Create an OpenClaw session for a voice call
   */
  async createSession(callId: string, phoneNumber: string, metadata?: Record<string, any>): Promise<OpenClawSession> {
    const session = await this.sessionManager.createSession(callId, phoneNumber, metadata);
    
    // Inject relevant context from OpenClaw
    await this.contextManager.injectContext(session);
    
    return session;
  }

  /**
   * Handle outgoing message from OpenClaw to voice
   */
  async sendMessage(sessionId: string, message: OpenClawMessage): Promise<void> {
    const session = await this.sessionManager.getSession(sessionId);
    if (!session) {
      throw new Error(`Voice session ${sessionId} not found`);
    }

    // Convert OpenClaw message to voice response
    await this.callHandler.sendVoiceMessage(session, message);
  }

  /**
   * Handle incoming audio from voice call
   */
  async receiveAudio(sessionId: string, audioData: Buffer, metadata?: Record<string, any>): Promise<void> {
    const session = await this.sessionManager.getSession(sessionId);
    if (!session) {
      throw new Error(`Voice session ${sessionId} not found`);
    }

    // Process audio and convert to OpenClaw message
    await this.callHandler.handleIncomingAudio(session, audioData, metadata);
  }

  /**
   * Handle incoming voice call
   */
  async handleIncomingCall(callId: string, phoneNumber: string, metadata?: Record<string, any>): Promise<string> {
    // Create session for the call
    const session = await this.createSession(callId, phoneNumber, metadata);
    
    // Accept the call with OpenClaw context
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
    const session = await this.sessionManager.createOutboundSession(phoneNumber, callerIdHint, contextHint);
    
    // Inject context for outbound call
    await this.contextManager.injectContext(session);
    
    // Initiate the call
    await this.callHandler.initiateCall(session);
    
    return session.id;
  }

  /**
   * End a voice call and cleanup session
   */
  async endCall(sessionId: string): Promise<void> {
    const session = await this.sessionManager.getSession(sessionId);
    if (!session) {
      return; // Already ended
    }

    // End the call
    await this.callHandler.endCall(session);
    
    // Persist session memory to OpenClaw context
    await this.contextManager.persistSession(session);
    
    // Cleanup session
    await this.sessionManager.endSession(sessionId);
  }

  /**
   * Get active voice sessions
   */
  async getActiveSessions(): Promise<OpenClawSession[]> {
    return this.sessionManager.getActiveSessions();
  }

  /**
   * Get session by ID
   */
  async getSession(sessionId: string): Promise<OpenClawSession | null> {
    return this.sessionManager.getSession(sessionId);
  }

  /**
   * Link voice session to existing OpenClaw session
   */
  async linkToSession(voiceSessionId: string, openClawSessionId: string): Promise<void> {
    await this.sessionManager.linkSession(voiceSessionId, openClawSessionId);
    
    // Re-inject context with linked session data
    const session = await this.sessionManager.getSession(voiceSessionId);
    if (session) {
      await this.contextManager.injectContext(session);
    }
  }

  /**
   * Transfer conversation from voice to another channel
   */
  async handoffToChannel(sessionId: string, targetChannel: string): Promise<void> {
    const session = await this.sessionManager.getSession(sessionId);
    if (!session) {
      throw new Error(`Voice session ${sessionId} not found`);
    }

    // Prepare handoff context
    const handoffContext = await this.contextManager.prepareHandoffContext(session, targetChannel);
    
    // Persist current conversation
    await this.contextManager.persistSession(session);
    
    // Notify target channel about handoff
    // (This would integrate with OpenClaw's channel routing)
    
    // End voice session
    await this.endCall(sessionId);
  }

  /**
   * Cleanup and shutdown
   */
  async shutdown(): Promise<void> {
    await this.callHandler.shutdown();
    await this.sessionManager.shutdown();
    await this.contextManager.shutdown();
  }
}

export { VoiceConfig, VoiceSessionManager, VoiceContextManager, VoiceCallHandler };
export * from './types';