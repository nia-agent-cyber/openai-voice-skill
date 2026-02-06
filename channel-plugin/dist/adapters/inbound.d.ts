/**
 * Voice Channel Inbound Handler
 *
 * Handles incoming phone calls and routes them to OpenClaw sessions.
 *
 * T4 Implementation - Full inbound call support:
 * - Allowlist-based caller authorization
 * - OpenClaw session context injection for inbound calls
 * - Integration with session-bridge for transcript syncing
 * - Missed call tracking and voicemail-to-appointment flow
 *
 * Flow:
 * 1. Twilio webhook receives incoming call
 * 2. Check allowlist (from channels.voice.allowFrom config)
 * 3. Create or resume OpenClaw session for caller
 * 4. Inject caller context into session instructions
 * 5. Connect to OpenAI Realtime for speech-to-speech
 * 6. Transcripts sync to OpenClaw session via session-bridge
 *
 * Architecture Note:
 * - This module does NOT modify webhook-server.py
 * - It provides authorization and session context that can be:
 *   a) Called by webhook-server.py via HTTP (recommended)
 *   b) Deployed as a middleware layer in front of webhook-server.py
 *   c) Used by the channel-plugin for outbound session context
 */
import { type VoiceAccountConfig } from "./config.js";
/**
 * Incoming call event from Twilio
 */
export interface InboundCallEvent {
    /** Twilio's unique call identifier */
    callSid: string;
    /** Caller's phone number (E.164 format) */
    from: string;
    /** Called phone number (E.164 format) */
    to: string;
    /** Call direction - always "inbound" for this handler */
    direction: "inbound";
    /** Optional: City of the caller (from Twilio) */
    fromCity?: string;
    /** Optional: State/Province of the caller */
    fromState?: string;
    /** Optional: Country of the caller */
    fromCountry?: string;
    /** Optional: Zip code of the caller */
    fromZip?: string;
    /** Optional: Twilio account SID */
    accountSid?: string;
    /** Optional: API version used */
    apiVersion?: string;
    /** Optional: Caller ID name (CNAM) if available */
    callerName?: string;
}
/**
 * Authorization result for an inbound call
 */
export interface AuthorizationResult {
    /** Whether the call is authorized */
    authorized: boolean;
    /** Reason code for the authorization decision */
    reason: "allowed" | "allowlist_match" | "denied" | "not_configured";
    /** Human-readable message */
    message: string;
    /** If authorized, the matched allowlist entry (if any) */
    matchedEntry?: string;
    /** Policy that was applied */
    policy: "open" | "allowlist" | "pairing" | "disabled";
}
/**
 * Session context for an inbound call
 */
export interface InboundSessionContext {
    /** Unique session key for OpenClaw */
    sessionKey: string;
    /** Whether this is a known caller */
    isKnownCaller: boolean;
    /** Caller's display name (if known) */
    callerName?: string;
    /** Previous call count with this caller */
    previousCallCount?: number;
    /** Last call timestamp (ISO string) */
    lastCallAt?: string;
    /** Notes about this caller */
    callerNotes?: string;
    /** Custom context to inject into agent instructions */
    contextInstructions: string;
}
/**
 * Missed call record for voicemail-to-appointment flow
 */
export interface MissedCall {
    /** Timestamp of the missed call */
    timestamp: string;
    /** Caller's phone number */
    from: string;
    /** Reason for missing */
    reason: "unauthorized" | "busy" | "no_answer" | "after_hours";
    /** Whether voicemail was left */
    hasVoicemail: boolean;
    /** Voicemail transcription (if available) */
    voicemailTranscript?: string;
    /** Whether callback is scheduled */
    callbackScheduled: boolean;
}
/**
 * Logger interface for the inbound handler
 */
export interface InboundLogger {
    info: (msg: string) => void;
    warn: (msg: string) => void;
    error: (msg: string) => void;
    debug: (msg: string) => void;
}
/**
 * Normalize a phone number to E.164 format for comparison
 */
declare function normalizePhoneNumber(phone: string): string;
/**
 * Mask phone number for logging (PII protection)
 */
declare function maskPhoneNumber(phone: string): string;
/**
 * Check if a caller is authorized based on configuration
 *
 * @param callerPhone - The caller's phone number
 * @param config - Voice account configuration
 * @returns Authorization result
 */
export declare function authorizeInboundCall(callerPhone: string, config: VoiceAccountConfig): AuthorizationResult;
/**
 * Check if a phone number matches any entry in the allowlist
 *
 * Supports:
 * - Exact match: "+14402915517"
 * - Wildcard: "*"
 * - Prefix match: "+1440*" (matches all +1440 numbers)
 */
declare function checkAllowlist(phone: string, allowFrom: string[]): string | null;
/**
 * Build session context for an inbound call
 *
 * Creates a session key and context instructions for the caller,
 * including any known history from previous calls.
 *
 * @param event - The inbound call event
 * @param logger - Optional logger
 * @returns Session context for injection
 */
export declare function buildInboundSessionContext(event: InboundCallEvent, logger?: InboundLogger): InboundSessionContext;
/**
 * Record a call start (updates caller history)
 */
export declare function recordCallStart(callerPhone: string, callerName?: string): void;
/**
 * Update caller notes
 */
export declare function updateCallerNotes(callerPhone: string, notes: string): void;
/**
 * Record a missed call
 */
export declare function recordMissedCall(from: string, reason: MissedCall["reason"], voicemailTranscript?: string): void;
/**
 * Get pending missed calls that need callback
 */
export declare function getPendingMissedCalls(): MissedCall[];
/**
 * Mark a missed call as scheduled for callback
 */
export declare function markCallbackScheduled(timestamp: string): boolean;
/**
 * Generate TwiML response for rejecting unauthorized calls
 *
 * @param reason - Human-readable rejection reason
 * @param recordVoicemail - Whether to offer voicemail
 * @returns TwiML XML string
 */
export declare function generateRejectTwiml(reason: string, recordVoicemail?: boolean): string;
/**
 * Generate TwiML response for accepting and forwarding to OpenAI Realtime
 *
 * @param sipUri - OpenAI SIP URI to connect to
 * @returns TwiML XML string
 */
export declare function generateAcceptTwiml(sipUri: string): string;
/**
 * Handle incoming call webhook - main entry point
 *
 * This is called by the webhook handler to process incoming calls.
 * It handles authorization, session context, and generates the appropriate response.
 *
 * @param event - Incoming call event from Twilio
 * @param config - Voice account configuration
 * @param logger - Optional logger
 * @returns Response object with TwiML and metadata
 */
export declare function handleInboundCall(event: InboundCallEvent, config: VoiceAccountConfig, logger?: InboundLogger): Promise<{
    authorized: boolean;
    twiml: string;
    sessionContext?: InboundSessionContext;
    authResult: AuthorizationResult;
}>;
/**
 * Get caller history for display
 */
export declare function getCallerHistory(callerPhone: string): {
    name?: string;
    callCount: number;
    lastCallAt: string;
    notes?: string;
} | undefined;
/**
 * Get all known callers (for admin/debugging)
 */
export declare function getAllKnownCallers(): Array<{
    phone: string;
    name?: string;
    callCount: number;
    lastCallAt: string;
}>;
/**
 * Get recent missed calls (for admin/debugging)
 */
export declare function getRecentMissedCalls(limit?: number): MissedCall[];
/**
 * Export for testing/admin
 */
export declare const _internal: {
    normalizePhoneNumber: typeof normalizePhoneNumber;
    maskPhoneNumber: typeof maskPhoneNumber;
    checkAllowlist: typeof checkAllowlist;
    callerHistory: Map<string, {
        name?: string;
        callCount: number;
        lastCallAt: string;
        notes?: string;
    }>;
    missedCalls: MissedCall[];
};
export {};
//# sourceMappingURL=inbound.d.ts.map