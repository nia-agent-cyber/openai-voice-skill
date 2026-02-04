/**
 * Voice Channel Inbound Handler
 *
 * Handles incoming phone calls and routes them to OpenClaw sessions.
 *
 * Phase 2 implementation - placeholder for now.
 *
 * Flow:
 * 1. Twilio webhook receives incoming call
 * 2. Check allowlist (from channels.voice.allowFrom)
 * 3. Connect to OpenAI Realtime for speech-to-text
 * 4. Inject transcribed text as user message in OpenClaw session
 * 5. Agent response → TTS → speak back
 */
/**
 * Incoming call event from Twilio
 */
export interface InboundCallEvent {
    callSid: string;
    from: string;
    to: string;
    direction: "inbound";
}
/**
 * Handle incoming call webhook
 *
 * @param event - Incoming call details from Twilio
 * @returns TwiML response for Twilio
 */
export declare function handleInboundCall(_event: InboundCallEvent): Promise<string>;
/**
 * Handle speech transcription from OpenAI Realtime
 *
 * @param sessionId - OpenClaw session ID
 * @param transcript - Transcribed text from speech
 */
export declare function handleSpeechTranscript(_sessionId: string, _transcript: string): Promise<void>;
/**
 * Handle agent response - convert to speech
 *
 * @param sessionId - OpenClaw session ID
 * @param text - Agent response text
 */
export declare function handleAgentResponse(_sessionId: string, _text: string): Promise<void>;
//# sourceMappingURL=inbound.d.ts.map