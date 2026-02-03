/**
 * Types and interfaces for the Voice Channel Plugin
 */

import { OpenClawSession, OpenClawMessage } from '@openclaw/types';

export interface VoiceConfig {
  // OpenAI Configuration
  openai: {
    apiKey: string;
    projectId: string;
    model: string;
    voice: VoiceModel;
  };
  
  // Twilio Configuration (for outbound calls)
  twilio?: {
    accountSid: string;
    authToken: string;
    phoneNumber: string;
  };
  
  // Webhook Configuration
  webhook: {
    secret?: string;
    port: number;
    baseUrl: string;
  };
  
  // OpenClaw Integration
  openclaw: {
    workspaceDir: string;
    memoryEnabled: boolean;
    contextMaxTokens: number;
    crossChannelEnabled: boolean;
  };
  
  // Call Settings
  call: {
    defaultInstructions: string;
    recordCalls: boolean;
    maxCallDurationMinutes: number;
    autoEndOnSilence: boolean;
  };
}

export type VoiceModel = 'alloy' | 'echo' | 'fable' | 'onyx' | 'nova' | 'shimmer';

export interface VoiceSession extends OpenClawSession {
  // Voice-specific session data
  voiceData: {
    callId: string;
    phoneNumber: string;
    direction: 'inbound' | 'outbound';
    callState: CallState;
    startTime: Date;
    endTime?: Date;
    duration?: number;
    recordingUrl?: string;
    transcript?: TranscriptEntry[];
    callerIdHint?: string;
  };
  
  // OpenClaw integration
  context: VoiceSessionContext;
  linkedSessions: string[]; // Other OpenClaw session IDs
}

export type CallState = 'ringing' | 'active' | 'ended' | 'failed';

export interface VoiceSessionContext {
  // Injected OpenClaw context
  agentIdentity?: string;
  userProfile?: string;
  recentMemory?: string;
  crossChannelContext?: string;
  activeTasks?: string;
  callerHistory?: CallerHistory;
  
  // Dynamic context
  callSpecificInstructions?: string;
  contextTokensUsed: number;
  lastContextUpdate: Date;
}

export interface TranscriptEntry {
  timestamp: Date;
  speaker: 'user' | 'agent';
  text: string;
  audioUrl?: string;
  confidence?: number;
}

export interface CallerHistory {
  phoneNumber: string;
  previousCalls: {
    date: Date;
    duration: number;
    summary?: string;
  }[];
  knownIdentity?: {
    name?: string;
    linkedSessions: string[];
    preferences?: Record<string, any>;
  };
}

export interface VoiceMessage extends OpenClawMessage {
  // Voice-specific message properties
  audioData?: Buffer;
  audioUrl?: string;
  transcription?: string;
  voiceMetadata?: {
    duration: number;
    voice: VoiceModel;
    audioFormat: string;
  };
}

export interface CallHandoffContext {
  sessionId: string;
  targetChannel: string;
  conversationSummary: string;
  transcript: TranscriptEntry[];
  contextSnapshot: VoiceSessionContext;
  handoffReason: string;
  timestamp: Date;
}

export interface VoiceCallEvent {
  type: CallEventType;
  sessionId: string;
  timestamp: Date;
  data?: Record<string, any>;
}

export type CallEventType = 
  | 'call_initiated'
  | 'call_ringing'
  | 'call_answered'
  | 'call_ended'
  | 'audio_received'
  | 'audio_sent'
  | 'transcript_updated'
  | 'context_injected'
  | 'session_linked'
  | 'handoff_initiated'
  | 'error_occurred';

export interface ContextInjectionResult {
  success: boolean;
  tokensUsed: number;
  contextSources: string[];
  error?: string;
}

export interface SessionLinkingOptions {
  inheritContext: boolean;
  syncMemory: boolean;
  notifyLinkedChannels: boolean;
}

export interface VoiceChannelMetrics {
  activeCalls: number;
  totalCallsToday: number;
  averageCallDuration: number;
  contextInjectionLatency: number;
  memoryPersistenceLatency: number;
  errorRate: number;
}

// Webhook payload types from OpenAI
export interface OpenAIWebhookPayload {
  type: string;
  event: OpenAICallEvent;
}

export interface OpenAICallEvent {
  id: string;
  type: 'realtime.call.incoming' | 'realtime.call.ended';
  data: {
    call_id: string;
    phone_number?: string;
    status?: string;
    duration?: number;
    [key: string]: any;
  };
}

// Twilio webhook payload types
export interface TwilioWebhookPayload {
  CallSid: string;
  From: string;
  To: string;
  CallStatus: string;
  Direction: string;
  [key: string]: any;
}