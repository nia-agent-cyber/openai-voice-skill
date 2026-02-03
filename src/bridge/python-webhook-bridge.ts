/**
 * Python Webhook Bridge
 * 
 * Bridges the TypeScript voice channel plugin with the existing Python webhook server.
 * This allows OpenClaw session management while leveraging the proven Python infrastructure.
 */

import { VoiceConfig, VoiceSession, CallEventType, VoiceCallEvent } from '../channel/voice/types';
import { EventEmitter } from 'events';
import axios, { AxiosInstance } from 'axios';

export interface PythonWebhookConfig {
  baseUrl: string;
  port: number;
  healthCheckInterval: number;
  timeout: number;
  retryAttempts: number;
}

export interface CallInitiationRequest {
  to: string;
  caller_id?: string;
  message?: string;
  openclaw_session_id: string;
  context?: {
    agent_identity?: string;
    user_profile?: string;
    recent_memory?: string;
    caller_history?: any;
    active_tasks?: string;
    call_instructions?: string;
  };
}

export interface CallControlRequest {
  action: 'cancel' | 'transfer' | 'mute' | 'unmute';
  target?: string; // For transfers
  reason?: string;
}

export class PythonWebhookBridge extends EventEmitter {
  private config: PythonWebhookConfig;
  private httpClient: AxiosInstance;
  private healthCheckTimer?: NodeJS.Timeout;
  private isHealthy: boolean = false;
  private sessionCallMap: Map<string, string> = new Map(); // sessionId -> pythonCallId
  private callSessionMap: Map<string, string> = new Map(); // pythonCallId -> sessionId

  constructor(config: PythonWebhookConfig) {
    super();
    this.config = config;
    
    this.httpClient = axios.create({
      baseURL: config.baseUrl,
      timeout: config.timeout,
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'OpenClaw-Voice-Channel-Plugin/1.0',
      },
    });
    
    this.setupResponseInterceptor();
  }

  async initialize(): Promise<void> {
    // Start health monitoring
    await this.startHealthCheck();
    
    // Verify Python server is responsive
    await this.verifyPythonServer();
    
    this.emit('initialized');
  }

  /**
   * Initiate outbound call via Python server
   */
  async initiateCall(sessionId: string, request: CallInitiationRequest): Promise<string> {
    try {
      const response = await this.httpClient.post('/call', {
        ...request,
        // Add OpenClaw-specific metadata
        metadata: {
          openclaw_session_id: sessionId,
          channel_plugin: 'voice',
          integration_version: '1.0.0',
          ...request.context
        }
      });

      const pythonCallId = response.data.call_id;
      
      // Track call mapping
      this.sessionCallMap.set(sessionId, pythonCallId);
      this.callSessionMap.set(pythonCallId, sessionId);
      
      // Emit event for session manager
      this.emit('callInitiated', {
        type: 'call_initiated',
        sessionId: sessionId,
        timestamp: new Date(),
        data: {
          pythonCallId,
          phoneNumber: request.to,
          direction: 'outbound'
        }
      } as VoiceCallEvent);

      return pythonCallId;
      
    } catch (error) {
      this.emit('callError', {
        type: 'error_occurred',
        sessionId: sessionId,
        timestamp: new Date(),
        data: {
          error: 'Failed to initiate call via Python server',
          details: error.response?.data || error.message
        }
      } as VoiceCallEvent);
      
      throw new Error(`Call initiation failed: ${error.response?.data?.message || error.message}`);
    }
  }

  /**
   * Control active call
   */
  async controlCall(sessionId: string, request: CallControlRequest): Promise<void> {
    const pythonCallId = this.sessionCallMap.get(sessionId);
    if (!pythonCallId) {
      throw new Error(`No Python call ID found for session ${sessionId}`);
    }

    try {
      switch (request.action) {
        case 'cancel':
          await this.httpClient.delete(`/call/${pythonCallId}`);
          break;
          
        case 'transfer':
          // Implementation would depend on Python server supporting transfer
          throw new Error('Transfer not yet implemented in Python server');
          
        default:
          throw new Error(`Unsupported call action: ${request.action}`);
      }
      
      this.emit('callControlled', {
        type: 'call_ended',
        sessionId: sessionId,
        timestamp: new Date(),
        data: {
          action: request.action,
          pythonCallId
        }
      } as VoiceCallEvent);
      
    } catch (error) {
      this.emit('callError', {
        type: 'error_occurred',
        sessionId: sessionId,
        timestamp: new Date(),
        data: {
          error: `Call control failed: ${request.action}`,
          details: error.response?.data || error.message
        }
      } as VoiceCallEvent);
      
      throw error;
    }
  }

  /**
   * Get active calls from Python server
   */
  async getActiveCalls(): Promise<any[]> {
    try {
      const response = await this.httpClient.get('/calls');
      return response.data.calls || [];
    } catch (error) {
      return [];
    }
  }

  /**
   * Get call history from Python server
   */
  async getCallHistory(limit: number = 50, offset: number = 0): Promise<any[]> {
    try {
      const response = await this.httpClient.get('/history', {
        params: { limit, offset }
      });
      return response.data;
    } catch (error) {
      return [];
    }
  }

  /**
   * Get call transcript from Python server
   */
  async getCallTranscript(pythonCallId: string): Promise<any> {
    try {
      const response = await this.httpClient.get(`/history/${pythonCallId}/transcript`);
      return response.data;
    } catch (error) {
      return null;
    }
  }

  /**
   * Register webhook endpoint for Python server to call back
   */
  registerWebhookEndpoint(endpoint: string): void {
    // This would be called by the voice channel plugin to tell us where
    // the Python server should send webhook events
    this.emit('webhookEndpointRegistered', endpoint);
  }

  /**
   * Handle webhook event from Python server
   */
  async handleWebhookEvent(pythonCallId: string, eventType: string, eventData: any): Promise<void> {
    const sessionId = this.callSessionMap.get(pythonCallId);
    
    if (!sessionId) {
      // This might be a direct Python server call not managed by OpenClaw
      return;
    }

    // Convert Python webhook events to OpenClaw voice events
    let voiceEventType: CallEventType;
    let voiceEventData: any = { pythonCallId, ...eventData };

    switch (eventType) {
      case 'call_ringing':
        voiceEventType = 'call_ringing';
        break;
      case 'call_answered':
        voiceEventType = 'call_answered';
        break;
      case 'call_ended':
        voiceEventType = 'call_ended';
        // Cleanup mappings
        this.sessionCallMap.delete(sessionId);
        this.callSessionMap.delete(pythonCallId);
        break;
      case 'transcript_updated':
        voiceEventType = 'transcript_updated';
        break;
      case 'audio_received':
        voiceEventType = 'audio_received';
        break;
      default:
        return; // Ignore unknown events
    }

    const voiceEvent: VoiceCallEvent = {
      type: voiceEventType,
      sessionId: sessionId,
      timestamp: new Date(),
      data: voiceEventData
    };

    this.emit('voiceEvent', voiceEvent);
  }

  /**
   * Check if Python server is healthy
   */
  async checkHealth(): Promise<boolean> {
    try {
      const response = await this.httpClient.get('/health', { timeout: 5000 });
      this.isHealthy = response.status === 200;
      return this.isHealthy;
    } catch (error) {
      this.isHealthy = false;
      return false;
    }
  }

  /**
   * Get Python server status
   */
  getStatus(): {
    healthy: boolean;
    activeCalls: number;
    sessionMappings: number;
  } {
    return {
      healthy: this.isHealthy,
      activeCalls: this.callSessionMap.size,
      sessionMappings: this.sessionCallMap.size
    };
  }

  private async startHealthCheck(): Promise<void> {
    // Initial health check
    await this.checkHealth();
    
    // Set up periodic health checks
    this.healthCheckTimer = setInterval(async () => {
      const wasHealthy = this.isHealthy;
      const isHealthy = await this.checkHealth();
      
      if (wasHealthy !== isHealthy) {
        this.emit('healthChanged', { healthy: isHealthy });
      }
    }, this.config.healthCheckInterval);
  }

  private async verifyPythonServer(): Promise<void> {
    try {
      const response = await this.httpClient.get('/health');
      
      if (response.status !== 200) {
        throw new Error(`Python server returned status ${response.status}`);
      }
      
      // Check if server has required endpoints
      const rootResponse = await this.httpClient.get('/');
      const endpoints = rootResponse.data.endpoints || {};
      
      const requiredEndpoints = ['webhook', 'calls', 'health', 'initiate_call'];
      const missingEndpoints = requiredEndpoints.filter(ep => !endpoints[ep]);
      
      if (missingEndpoints.length > 0) {
        throw new Error(`Python server missing required endpoints: ${missingEndpoints.join(', ')}`);
      }
      
    } catch (error) {
      throw new Error(`Python server verification failed: ${error.message}`);
    }
  }

  private setupResponseInterceptor(): void {
    // Add retry logic for failed requests
    this.httpClient.interceptors.response.use(
      response => response,
      async error => {
        const { config, response } = error;
        
        // Don't retry health checks
        if (config.url?.includes('/health')) {
          return Promise.reject(error);
        }
        
        // Retry on network errors or 5xx responses
        if (
          (!response || response.status >= 500) &&
          config.retryCount < this.config.retryAttempts
        ) {
          config.retryCount = (config.retryCount || 0) + 1;
          
          // Exponential backoff
          const delay = Math.pow(2, config.retryCount) * 1000;
          await new Promise(resolve => setTimeout(resolve, delay));
          
          return this.httpClient(config);
        }
        
        return Promise.reject(error);
      }
    );
  }

  async shutdown(): Promise<void> {
    // Clear health check timer
    if (this.healthCheckTimer) {
      clearInterval(this.healthCheckTimer);
      this.healthCheckTimer = undefined;
    }
    
    // Cancel any active calls
    const activeSessions = Array.from(this.sessionCallMap.keys());
    await Promise.all(
      activeSessions.map(sessionId =>
        this.controlCall(sessionId, { action: 'cancel', reason: 'system_shutdown' })
          .catch(() => {}) // Ignore errors during shutdown
      )
    );
    
    // Clear mappings
    this.sessionCallMap.clear();
    this.callSessionMap.clear();
    
    this.removeAllListeners();
  }
}