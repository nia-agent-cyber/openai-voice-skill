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
 * Handle incoming call webhook
 *
 * @param event - Incoming call details from Twilio
 * @returns TwiML response for Twilio
 */
export async function handleInboundCall(_event) {
    // Phase 2 implementation:
    //
    // 1. Validate caller against allowFrom
    // const config = loadVoiceConfig();
    // if (!isAllowed(event.from, config.allowFrom)) {
    //   return rejectTwiml("Not authorized");
    // }
    //
    // 2. Create/resume OpenClaw session for this caller
    // const session = await getOrCreateSession({
    //   channel: "voice",
    //   senderId: event.from,
    // });
    //
    // 3. Return TwiML to connect to media stream
    // return connectToRealtimeTwiml(session.id);
    // For now, return a placeholder response
    return `
    <Response>
      <Say>Voice channel inbound calls coming soon. Goodbye!</Say>
      <Hangup/>
    </Response>
  `.trim();
}
/**
 * Handle speech transcription from OpenAI Realtime
 *
 * @param sessionId - OpenClaw session ID
 * @param transcript - Transcribed text from speech
 */
export async function handleSpeechTranscript(_sessionId, _transcript) {
    // Phase 2 implementation:
    //
    // Inject transcript as user message into OpenClaw session
    // const session = await getSession(sessionId);
    // await session.injectMessage({
    //   role: "user",
    //   content: transcript,
    //   channel: "voice",
    // });
    // Placeholder for now
}
/**
 * Handle agent response - convert to speech
 *
 * @param sessionId - OpenClaw session ID
 * @param text - Agent response text
 */
export async function handleAgentResponse(_sessionId, _text) {
    // Phase 2 implementation:
    //
    // Send text to OpenAI Realtime for TTS
    // The Realtime API handles the actual speaking
    // Placeholder for now
}
//# sourceMappingURL=inbound.js.map