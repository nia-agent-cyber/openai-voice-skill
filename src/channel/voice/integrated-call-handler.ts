/**
 * Integrated Voice Call Handler
 * 
 * Updated call handler that integrates the TypeScript channel plugin
 * with the existing Python webhook server infrastructure.
 * 
 * This handler bridges OpenClaw session management with the Python
 * voice server's proven call handling capabilities.
 */

import { VoiceConfig, VoiceSession, VoiceMessage, TranscriptEntry, VoiceCallEvent } from './types';
import { VoiceSessionManager } from './session-manager';
import { VoiceContextManager } from './context-manager';
import { PythonWebhookBridge, CallInitiationRequest } from '../bridge/python-webhook-bridge';
import { OpenClawMessage } from '@openclaw/types';
import { EventEmitter } from 'events';
import * as express from 'express';
import * as http from 'http';

export class IntegratedVoiceCallHandler extends EventEmitter {
  private config: VoiceConfig;
  private sessionManager: VoiceSessionManager;
  private contextManager: VoiceContextManager;
  private pythonBridge: PythonWebhookBridge;
  private webhookServer?: http.Server;
  private expressApp: express.Application;
  
  constructor(
    config: VoiceConfig,
    sessionManager: VoiceSessionManager,
    contextManager: VoiceContextManager
  ) {
    super();
    this.config = config;
    this.sessionManager = sessionManager;
    this.contextManager = contextManager;
    
    // Initialize Python webhook bridge
    this.pythonBridge = new PythonWebhookBridge({
      baseUrl: `http://localhost:8080`, // Python server default
      port: 8080,
      healthCheckInterval: 30000, // 30 seconds
      timeout: 30000, // 30 seconds
      retryAttempts: 3
    });
    
    this.expressApp = express();
    this.setupMiddleware();
    this.setupWebhookRoutes();
  }

  async initialize(): Promise<void> {
    // Initialize Python bridge
    await this.pythonBridge.initialize();
    
    // Start our webhook server to receive events from Python server
    await this.startWebhookServer();
    
    // Set up event listeners
    this.setupEventListeners();
    
    this.emit('initialized');
  }

  /**
   * Accept an incoming call with OpenClaw context
   * 
   * For incoming calls, the Python server handles the acceptance automatically
   * based on its configuration. This method updates the session with OpenClaw context.
   */
  async acceptCall(session: VoiceSession): Promise<void> {
    try {
      // The Python server handles the actual call acceptance via OpenAI API
      // We focus on OpenClaw session management and context injection
      
      // Prepare context for the Python server
      const contextData = await this.prepareContextForPython(session);
      
      // Update session state
      await this.sessionManager.updateCallState(session.id, 'active');
      
      // The Python server will send webhook events as the call progresses
      this.emit('callAccepted', session);
      
    } catch (error) {
      await this.sessionManager.updateCallState(session.id, 'failed');
      this.emit('callFailed', session, error);
      throw error;
    }
  }

  /**
   * Initiate an outbound call via the Python webhook server
   */
  async initiateCall(session: VoiceSession): Promise<void> {
    try {
      // Prepare context data for the call
      const contextData = await this.prepareContextForPython(session);
      
      // Build call initiation request
      const callRequest: CallInitiationRequest = {
        to: session.voiceData.phoneNumber,
        caller_id: this.config.twilio?.phoneNumber,
        openclaw_session_id: session.id,
        context: contextData
      };
      
      // Add initial message if specified
      if (session.context.callSpecificInstructions) {
        callRequest.message = session.context.callSpecificInstructions;
      }
      
      // Initiate call via Python bridge
      const pythonCallId = await this.pythonBridge.initiateCall(session.id, callRequest);
      
      // Update session with Python call ID
      session.voiceData.callId = pythonCallId;
      await this.sessionManager.updateSession(session);
      
      this.emit('callInitiated', session);
      
    } catch (error) {
      await this.sessionManager.updateCallState(session.id, 'failed');
      this.emit('callFailed', session, error);
      throw error;
    }
  }

  /**
   * Send a voice message (OpenClaw message -> voice output)
   * 
   * The Python server handles real-time audio streaming via OpenAI Realtime API.
   * For now, we'll add this to the transcript and emit events.
   * Future enhancement: Send instructions to Python server for immediate delivery.
   */
  async sendVoiceMessage(session: VoiceSession, message: OpenClawMessage): Promise<void> {
    try {
      // Add to transcript
      const transcriptEntry: TranscriptEntry = {
        timestamp: new Date(),
        speaker: 'agent',
        text: message.content,
      };
      
      session.voiceData.transcript = session.voiceData.transcript || [];
      session.voiceData.transcript.push(transcriptEntry);
      
      // Update session
      await this.sessionManager.updateSession(session);
      
      this.emit('voiceMessageSent', session, message);
      
      // TODO: Future enhancement - send real-time instruction to Python server
      // await this.sendRealtimeInstruction(session.voiceData.callId, message.content);
      
    } catch (error) {
      this.emit('voiceMessageError', session, message, error);
      throw error;
    }
  }

  /**
   * Handle incoming audio - managed by Python server
   * 
   * The Python server processes audio via OpenAI Realtime API and sends
   * webhook events with transcripts. This method is mainly for completeness.
   */
  async handleIncomingAudio(
    session: VoiceSession,
    audioData: Buffer,
    metadata?: Record<string, any>
  ): Promise<void> {
    // Audio processing is handled by Python server
    // Webhook events will update the session with transcripts
    this.emit('audioReceived', session, audioData, metadata);
  }

  /**
   * End a call via Python bridge
   */
  async endCall(session: VoiceSession): Promise<void> {
    try {
      // End call via Python bridge
      await this.pythonBridge.controlCall(session.id, {
        action: 'cancel',
        reason: 'session_ended'
      });
      
      await this.sessionManager.updateCallState(session.id, 'ended');
      this.emit('callEnded', session);
      
    } catch (error) {
      this.emit('callEndError', session, error);
      // Even if Python call end fails, update our session state
      await this.sessionManager.updateCallState(session.id, 'ended');
    }
  }

  /**
   * Prepare OpenClaw context for Python server
   */
  private async prepareContextForPython(session: VoiceSession): Promise<any> {
    const context: any = {};
    
    // Add OpenClaw context data
    if (session.context.agentIdentity) {
      context.agent_identity = session.context.agentIdentity;
    }
    
    if (session.context.userProfile) {
      context.user_profile = session.context.userProfile;
    }
    
    if (session.context.recentMemory) {
      context.recent_memory = session.context.recentMemory;
    }
    
    if (session.context.activeTasks) {
      context.active_tasks = session.context.activeTasks;
    }
    
    if (session.context.callSpecificInstructions) {
      context.call_instructions = session.context.callSpecificInstructions;
    }
    
    // Add caller history if available
    if (session.context.callerHistory) {
      context.caller_history = {
        phone_number: session.context.callerHistory.phoneNumber,
        previous_calls_count: session.context.callerHistory.previousCalls.length,
        known_identity: session.context.callerHistory.knownIdentity
      };
    }
    
    return context;
  }

  /**
   * Set up Express middleware
   */
  private setupMiddleware(): void {
    this.expressApp.use(express.json({ limit: '10mb' }));
    this.expressApp.use(express.urlencoded({ extended: true }));
    
    // CORS for Python server
    this.expressApp.use((req, res, next) => {
      res.header('Access-Control-Allow-Origin', '*');
      res.header('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS');
      res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
      next();
    });
  }

  /**
   * Set up webhook routes for Python server to call
   */
  private setupWebhookRoutes(): void {
    // Main webhook endpoint for Python server events
    this.expressApp.post('/python-webhook', async (req, res) => {
      try {
        await this.handlePythonWebhookEvent(req.body);
        res.json({ received: true });
      } catch (error) {
        console.error('Python webhook error:', error);
        res.status(500).json({ error: 'Webhook processing failed' });
      }
    });
    
    // Health check endpoint
    this.expressApp.get('/health', (req, res) => {
      const bridgeStatus = this.pythonBridge.getStatus();
      res.json({
        status: 'healthy',
        bridge: bridgeStatus,
        timestamp: new Date().toISOString()
      });
    });
    
    // Status endpoint for debugging
    this.expressApp.get('/status', async (req, res) => {
      const activeSessions = await this.sessionManager.getActiveSessions();
      const activeCallsFromPython = await this.pythonBridge.getActiveCalls();
      
      res.json({
        voice_channel_plugin: {
          active_sessions: activeSessions.length,
          sessions: activeSessions.map(s => ({
            id: s.id,
            callId: s.voiceData.callId,
            phoneNumber: s.voiceData.phoneNumber,
            state: s.voiceData.callState
          }))
        },
        python_server: {
          healthy: this.pythonBridge.getStatus().healthy,
          active_calls: activeCallsFromPython.length,
          calls: activeCallsFromPython
        }
      });
    });
  }

  /**
   * Handle webhook events from Python server
   */
  private async handlePythonWebhookEvent(eventData: any): Promise<void> {
    const { call_id, event_type, data, timestamp } = eventData;
    
    if (!call_id || !event_type) {
      console.warn('Invalid Python webhook event:', eventData);
      return;
    }
    
    // Let the bridge handle the event mapping
    await this.pythonBridge.handleWebhookEvent(call_id, event_type, data);
  }

  /**
   * Start webhook server
   */
  private async startWebhookServer(): Promise<void> {
    const port = this.config.webhook.port + 1; // Use different port from Python server
    
    return new Promise((resolve) => {
      this.webhookServer = this.expressApp.listen(port, () => {
        console.log(`OpenClaw Voice Channel webhook server listening on port ${port}`);
        
        // Register our webhook endpoint with the bridge
        this.pythonBridge.registerWebhookEndpoint(`http://localhost:${port}/python-webhook`);
        
        resolve();
      });
    });
  }

  /**
   * Set up event listeners
   */
  private setupEventListeners(): void {
    // Listen for bridge events
    this.pythonBridge.on('voiceEvent', async (event: VoiceCallEvent) => {
      await this.handleVoiceEvent(event);
    });
    
    this.pythonBridge.on('healthChanged', (status) => {
      this.emit('bridgeHealthChanged', status);
    });
    
    this.pythonBridge.on('callInitiated', (event: VoiceCallEvent) => {
      this.emit('callInitiated', event);
    });
    
    // Forward session manager events
    this.sessionManager.on('callAnswered', (session) => {
      this.emit('callAnswered', session);
    });
    
    this.sessionManager.on('callEnded', (session) => {
      this.emit('callEnded', session);
    });
  }

  /**
   * Handle voice events from the Python bridge
   */
  private async handleVoiceEvent(event: VoiceCallEvent): Promise<void> {
    const session = await this.sessionManager.getSession(event.sessionId);
    if (!session) {
      console.warn(`Voice event for unknown session: ${event.sessionId}`);
      return;
    }
    
    switch (event.type) {
      case 'call_ringing':
        await this.sessionManager.updateCallState(session.id, 'ringing');
        this.emit('callRinging', session);
        break;
        
      case 'call_answered':
        await this.sessionManager.updateCallState(session.id, 'active');
        this.emit('callAnswered', session);
        break;
        
      case 'call_ended':
        await this.sessionManager.updateCallState(session.id, 'ended');
        this.emit('callEnded', session);
        break;
        
      case 'transcript_updated':
        await this.handleTranscriptUpdate(session, event.data);
        break;
        
      case 'audio_received':
        this.emit('audioReceived', session, event.data);
        break;
        
      default:
        console.log(`Unhandled voice event: ${event.type}`);
    }
  }

  /**
   * Handle transcript updates from Python server
   */
  private async handleTranscriptUpdate(session: VoiceSession, data: any): Promise<void> {
    if (!data.transcript) return;
    
    const entry: TranscriptEntry = {
      timestamp: new Date(data.timestamp || Date.now()),
      speaker: data.speaker || 'user',
      text: data.transcript,
      confidence: data.confidence
    };
    
    // Add to session transcript
    session.voiceData.transcript = session.voiceData.transcript || [];
    session.voiceData.transcript.push(entry);
    
    // Update session
    await this.sessionManager.updateSession(session);
    
    // Convert to OpenClaw message if it's user speech
    if (entry.speaker === 'user') {
      const message: VoiceMessage = {
        id: `voice_${Date.now()}`,
        sessionId: session.id,
        content: entry.text,
        timestamp: entry.timestamp,
        channel: 'voice',
        author: {
          id: session.voiceData.phoneNumber,
          name: session.context.callerHistory?.knownIdentity?.name || session.voiceData.phoneNumber
        },
        transcription: entry.text,
        voiceMetadata: {
          duration: 0, // Not available from transcript
          voice: this.config.openai.voice,
          audioFormat: 'unknown'
        }
      };
      
      this.emit('messageReceived', session, message);
    }
    
    this.emit('transcriptUpdated', session, entry);
  }

  /**
   * Get bridge status for monitoring
   */
  getBridgeStatus(): any {
    return this.pythonBridge.getStatus();
  }

  /**
   * Shutdown handler
   */
  async shutdown(): Promise<void> {
    // Shutdown Python bridge
    await this.pythonBridge.shutdown();
    
    // Close webhook server
    if (this.webhookServer) {
      await new Promise<void>((resolve) => {
        this.webhookServer!.close(() => resolve());
      });
    }
    
    this.removeAllListeners();
  }
}