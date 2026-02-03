/**
 * Voice Call Handler
 * 
 * Handles the actual voice call interactions:
 * - OpenAI Realtime API integration
 * - Audio streaming and processing
 * - Message bridging between voice and OpenClaw
 * - Call lifecycle management
 */

import { VoiceConfig, VoiceSession, VoiceMessage, TranscriptEntry, OpenAIWebhookPayload, TwilioWebhookPayload } from './types';
import { VoiceSessionManager } from './session-manager';
import { VoiceContextManager } from './context-manager';
import { OpenClawMessage } from '@openclaw/types';
import { EventEmitter } from 'events';
import * as http from 'http';
import * as https from 'https';

export class VoiceCallHandler extends EventEmitter {
  private config: VoiceConfig;
  private sessionManager: VoiceSessionManager;
  private contextManager: VoiceContextManager;
  private activeStreams: Map<string, any> = new Map(); // sessionId -> stream connection
  private webhookServer?: http.Server | https.Server;
  
  constructor(
    config: VoiceConfig,
    sessionManager: VoiceSessionManager,
    contextManager: VoiceContextManager
  ) {
    super();
    this.config = config;
    this.sessionManager = sessionManager;
    this.contextManager = contextManager;
  }

  async initialize(): Promise<void> {
    // Start webhook server to receive OpenAI and Twilio events
    await this.startWebhookServer();
    
    // Set up event listeners
    this.setupEventListeners();
    
    this.emit('initialized');
  }

  /**
   * Accept an incoming call with OpenClaw context
   */
  async acceptCall(session: VoiceSession): Promise<void> {
    try {
      // Prepare call instructions with injected context
      const instructions = await this.prepareCallInstructions(session);
      
      // Accept the call via OpenAI Realtime API
      const acceptResponse = await this.sendOpenAIRequest('/realtime/calls/accept', {
        call_id: session.voiceData.callId,
        instructions: instructions,
        voice: this.config.openai.voice,
        model: this.config.openai.model
      });
      
      if (acceptResponse.status === 'accepted') {
        await this.sessionManager.updateCallState(session.id, 'active');
        this.emit('callAccepted', session);
      } else {
        await this.sessionManager.updateCallState(session.id, 'failed');
        this.emit('callFailed', session, 'Failed to accept call');
      }
      
    } catch (error) {
      await this.sessionManager.updateCallState(session.id, 'failed');
      this.emit('callFailed', session, error);
      throw error;
    }
  }

  /**
   * Initiate an outbound call
   */
  async initiateCall(session: VoiceSession): Promise<void> {
    try {
      // Prepare call instructions with context
      const instructions = await this.prepareCallInstructions(session);
      
      // Initiate call via Twilio (if configured) or directly via OpenAI
      let callResponse;
      
      if (this.config.twilio) {
        callResponse = await this.initiateTwilioCall(session, instructions);
      } else {
        callResponse = await this.initiateOpenAICall(session, instructions);
      }
      
      if (callResponse.success) {
        await this.sessionManager.updateCallState(session.id, 'ringing');
        this.emit('callInitiated', session);
      } else {
        await this.sessionManager.updateCallState(session.id, 'failed');
        this.emit('callFailed', session, callResponse.error);
      }
      
    } catch (error) {
      await this.sessionManager.updateCallState(session.id, 'failed');
      this.emit('callFailed', session, error);
      throw error;
    }
  }

  /**
   * Send a voice message (OpenClaw message -> voice output)
   */
  async sendVoiceMessage(session: VoiceSession, message: OpenClawMessage): Promise<void> {
    try {
      // Convert OpenClaw message to voice instruction
      const voiceInstruction = this.convertMessageToVoiceInstruction(message);
      
      // Send instruction to OpenAI Realtime API
      await this.sendRealtimeInstruction(session.voiceData.callId, voiceInstruction);
      
      // Add to transcript
      const transcriptEntry: TranscriptEntry = {
        timestamp: new Date(),
        speaker: 'agent',
        text: message.content,
      };
      
      session.voiceData.transcript = session.voiceData.transcript || [];
      session.voiceData.transcript.push(transcriptEntry);
      
      this.emit('voiceMessageSent', session, message);
      
    } catch (error) {
      this.emit('voiceMessageError', session, message, error);
      throw error;
    }
  }

  /**
   * Handle incoming audio and convert to OpenClaw message
   */
  async handleIncomingAudio(
    session: VoiceSession,
    audioData: Buffer,
    metadata?: Record<string, any>
  ): Promise<void> {
    try {
      // Process audio through OpenAI Realtime API (this is handled automatically in the stream)
      // The transcription will come via webhook events
      
      this.emit('audioReceived', session, audioData, metadata);
      
    } catch (error) {
      this.emit('audioProcessingError', session, error);
    }
  }

  /**
   * End a call
   */
  async endCall(session: VoiceSession): Promise<void> {
    try {
      // End the call via OpenAI API or Twilio
      if (this.config.twilio) {
        await this.endTwilioCall(session.voiceData.callId);
      } else {
        await this.endOpenAICall(session.voiceData.callId);
      }
      
      // Cleanup active stream
      this.activeStreams.delete(session.id);
      
      await this.sessionManager.updateCallState(session.id, 'ended');
      this.emit('callEnded', session);
      
    } catch (error) {
      this.emit('callEndError', session, error);
    }
  }

  /**
   * Prepare call instructions with OpenClaw context
   */
  private async prepareCallInstructions(session: VoiceSession): Promise<string> {
    let instructions = this.config.call.defaultInstructions;
    
    // Add context from session
    if (session.context.agentIdentity) {
      instructions += `\n\nAgent Identity:\n${session.context.agentIdentity}`;
    }
    
    if (session.context.userProfile) {
      instructions += `\n\nUser Profile:\n${session.context.userProfile}`;
    }
    
    if (session.context.recentMemory) {
      instructions += `\n\nRecent Context:\n${session.context.recentMemory}`;
    }
    
    if (session.context.callerHistory?.knownIdentity) {
      instructions += `\n\nCaller: ${session.context.callerHistory.knownIdentity.name || 'Known caller'}`;
      if (session.context.callerHistory.previousCalls.length > 0) {
        instructions += ` (${session.context.callerHistory.previousCalls.length} previous calls)`;
      }
    }
    
    if (session.context.activeTasks) {
      instructions += `\n\nActive Tasks:\n${session.context.activeTasks}`;
    }
    
    // Add call-specific instructions
    if (session.context.callSpecificInstructions) {
      instructions += `\n\nCall Context:\n${session.context.callSpecificInstructions}`;
    }
    
    return instructions;
  }

  /**
   * Convert OpenClaw message to voice instruction
   */
  private convertMessageToVoiceInstruction(message: OpenClawMessage): string {
    // For now, just use the content directly
    // In the future, this could handle different message types, attachments, etc.
    return message.content;
  }

  /**
   * Start webhook server for receiving events
   */
  private async startWebhookServer(): Promise<void> {
    const express = require('express');
    const app = express();
    
    app.use(express.json({ limit: '10mb' }));
    app.use(express.raw({ type: 'audio/*', limit: '50mb' }));
    
    // OpenAI webhook endpoint
    app.post('/webhook', async (req: any, res: any) => {
      await this.handleOpenAIWebhook(req, res);
    });
    
    // Twilio webhook endpoint
    app.post('/twilio-webhook', async (req: any, res: any) => {
      await this.handleTwilioWebhook(req, res);
    });
    
    // Health check
    app.get('/health', (req: any, res: any) => {
      res.json({ status: 'healthy', timestamp: new Date().toISOString() });
    });
    
    return new Promise((resolve) => {
      this.webhookServer = app.listen(this.config.webhook.port, () => {
        resolve();
      });
    });
  }

  /**
   * Handle OpenAI webhook events
   */
  private async handleOpenAIWebhook(req: any, res: any): Promise<void> {
    try {
      const payload: OpenAIWebhookPayload = req.body;
      
      // Verify webhook signature if secret is configured
      if (this.config.webhook.secret) {
        const signature = req.headers['openai-signature'];
        if (!this.verifyWebhookSignature(JSON.stringify(payload), signature, this.config.webhook.secret)) {
          res.status(401).json({ error: 'Invalid signature' });
          return;
        }
      }
      
      const session = await this.sessionManager.getSessionByCallId(payload.event.data.call_id);
      
      switch (payload.event.type) {
        case 'realtime.call.incoming':
          await this.handleIncomingCallEvent(payload.event);
          break;
          
        case 'realtime.call.ended':
          if (session) {
            await this.sessionManager.updateCallState(session.id, 'ended');
          }
          break;
          
        default:
          // Handle other event types (audio, transcript, etc.)
          if (session) {
            await this.handleRealtimeEvent(session, payload.event);
          }
      }
      
      res.json({ received: true });
      
    } catch (error) {
      res.status(500).json({ error: 'Webhook processing failed' });
    }
  }

  /**
   * Handle Twilio webhook events
   */
  private async handleTwilioWebhook(req: any, res: any): Promise<void> {
    // Implementation for Twilio webhook handling
    res.json({ received: true });
  }

  /**
   * Handle incoming call event
   */
  private async handleIncomingCallEvent(event: any): Promise<void> {
    const callId = event.data.call_id;
    const phoneNumber = event.data.phone_number || 'unknown';
    
    // Create session for the call
    const session = await this.sessionManager.createSession(callId, phoneNumber, event.data);
    
    // Inject context
    await this.contextManager.injectContext(session);
    
    // Accept the call
    await this.acceptCall(session);
  }

  /**
   * Handle realtime events (audio, transcript, etc.)
   */
  private async handleRealtimeEvent(session: VoiceSession, event: any): Promise<void> {
    switch (event.type) {
      case 'audio.received':
        // Handle received audio
        break;
        
      case 'transcript.updated':
        // Update session transcript
        if (event.data.transcript) {
          const entry: TranscriptEntry = {
            timestamp: new Date(),
            speaker: event.data.speaker || 'user',
            text: event.data.transcript,
            confidence: event.data.confidence
          };
          
          session.voiceData.transcript = session.voiceData.transcript || [];
          session.voiceData.transcript.push(entry);
          
          // Emit as OpenClaw message
          const message: OpenClawMessage = {
            id: `voice_${Date.now()}`,
            sessionId: session.id,
            content: event.data.transcript,
            timestamp: new Date(),
            channel: 'voice',
            author: {
              id: session.voiceData.phoneNumber,
              name: session.voiceData.phoneNumber
            }
          };
          
          this.emit('messageReceived', session, message);
        }
        break;
    }
  }

  /**
   * Send instruction to OpenAI Realtime API
   */
  private async sendRealtimeInstruction(callId: string, instruction: string): Promise<void> {
    await this.sendOpenAIRequest(`/realtime/calls/${callId}/instruction`, {
      instruction: instruction
    });
  }

  /**
   * Send request to OpenAI API
   */
  private async sendOpenAIRequest(endpoint: string, data: any): Promise<any> {
    // Implementation would use the actual OpenAI API client
    // For now, return a mock response
    return { status: 'accepted' };
  }

  /**
   * Initiate call via Twilio
   */
  private async initiateTwilioCall(session: VoiceSession, instructions: string): Promise<{ success: boolean; error?: string }> {
    // Implementation would use Twilio client to initiate call
    return { success: true };
  }

  /**
   * Initiate call via OpenAI
   */
  private async initiateOpenAICall(session: VoiceSession, instructions: string): Promise<{ success: boolean; error?: string }> {
    // Implementation would use OpenAI Realtime API to initiate call
    return { success: true };
  }

  /**
   * End call via Twilio
   */
  private async endTwilioCall(callId: string): Promise<void> {
    // Implementation would use Twilio client to end call
  }

  /**
   * End call via OpenAI
   */
  private async endOpenAICall(callId: string): Promise<void> {
    // Implementation would use OpenAI API to end call
  }

  /**
   * Verify webhook signature
   */
  private verifyWebhookSignature(payload: string, signature: string, secret: string): boolean {
    // Implementation would verify HMAC signature
    return true; // Placeholder
  }

  /**
   * Set up event listeners
   */
  private setupEventListeners(): void {
    // Listen for session events and forward relevant ones
    this.sessionManager.on('callAnswered', (session) => {
      this.emit('callAnswered', session);
    });
    
    this.sessionManager.on('callEnded', (session) => {
      this.emit('callEnded', session);
    });
  }

  /**
   * Shutdown and cleanup
   */
  async shutdown(): Promise<void> {
    // Close webhook server
    if (this.webhookServer) {
      await new Promise<void>((resolve) => {
        this.webhookServer!.close(() => resolve());
      });
    }
    
    // End all active calls
    const activeSessions = await this.sessionManager.getActiveSessions();
    await Promise.all(
      activeSessions.map(session => this.endCall(session))
    );
    
    // Clear active streams
    this.activeStreams.clear();
    
    this.removeAllListeners();
  }
}