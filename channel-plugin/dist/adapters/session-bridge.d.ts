/**
 * Voice Channel Session Bridge
 *
 * Bridges voice calls with OpenClaw sessions for continuity.
 *
 * Architecture:
 * - webhook-server.py handles real-time voice via OpenAI Realtime API
 * - This bridge syncs call transcripts to OpenClaw sessions
 * - Enables cross-channel context (voice ↔ Telegram/etc.)
 *
 * Design Constraints:
 * - Cannot modify webhook-server.py (DO NOT TOUCH)
 * - Bridge receives events via HTTP endpoints
 * - Transcripts fetched via webhook-server.py's /history API
 */
export interface BridgeConfig {
    /** Port for the bridge HTTP server */
    port: number;
    /** URL of webhook-server.py (e.g., http://localhost:8080) */
    webhookServerUrl: string;
    /** OpenClaw config for agent access */
    openclawConfig?: Record<string, unknown>;
    /** Logger interface */
    logger?: Logger;
}
export interface Logger {
    info: (msg: string) => void;
    warn: (msg: string) => void;
    error: (msg: string) => void;
    debug: (msg: string) => void;
}
export interface CallEvent {
    callId: string;
    eventType: "call_started" | "call_ended" | "transcript_update";
    phoneNumber: string;
    direction: "inbound" | "outbound";
    timestamp: string;
    data?: Record<string, unknown>;
}
export interface TranscriptEntry {
    timestamp: string;
    speaker: "user" | "assistant";
    content: string;
    eventType?: string;
}
export interface SessionSyncResult {
    success: boolean;
    sessionKey?: string;
    messagesInjected?: number;
    error?: string;
}
/**
 * Session Bridge for Voice ↔ OpenClaw integration
 *
 * This bridge:
 * 1. Receives call events from webhook-server.py (or polling)
 * 2. Fetches transcripts from the webhook server's /history API
 * 3. Injects transcripts into OpenClaw sessions
 */
export declare class VoiceSessionBridge {
    private config;
    private server;
    private log;
    private coreAgentDeps;
    constructor(config: BridgeConfig);
    /**
     * Start the bridge HTTP server
     */
    start(): Promise<void>;
    /**
     * Stop the bridge server
     */
    stop(): Promise<void>;
    /**
     * Handle incoming HTTP requests
     */
    private handleRequest;
    /**
     * Handle a call event from webhook-server.py
     */
    handleCallEvent(event: CallEvent): Promise<{
        status: string;
        sessionKey?: string;
    }>;
    /**
     * Sync a call's transcript to its OpenClaw session
     */
    syncTranscriptToSession(callId: string): Promise<SessionSyncResult>;
    /**
     * Fetch transcript from webhook-server.py's /history API
     */
    private fetchTranscriptFromWebhook;
    /**
     * Inject transcript entries into an OpenClaw session
     *
     * This creates a session record with the voice conversation,
     * enabling cross-channel context continuity.
     */
    private injectTranscriptToSession;
    /**
     * Format transcript for session injection
     */
    private formatTranscriptForSession;
    /**
     * Resolve session key for a phone number
     */
    private resolveSessionKey;
    /**
     * Read request body
     */
    private readBody;
}
/**
 * Factory function to create a voice session bridge
 */
export declare function createSessionBridge(config: BridgeConfig): VoiceSessionBridge;
//# sourceMappingURL=session-bridge.d.ts.map