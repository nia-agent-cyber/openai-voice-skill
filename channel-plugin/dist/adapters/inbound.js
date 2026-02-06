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
// In-memory stores (in production, use persistent storage)
const callerHistory = new Map();
const missedCalls = [];
// Default logger
const defaultLogger = {
    info: (msg) => console.log(`[inbound] ${msg}`),
    warn: (msg) => console.warn(`[inbound] ${msg}`),
    error: (msg) => console.error(`[inbound] ${msg}`),
    debug: (msg) => console.debug(`[inbound] ${msg}`),
};
/**
 * Normalize a phone number to E.164 format for comparison
 */
function normalizePhoneNumber(phone) {
    if (!phone)
        return "";
    // Remove all non-digit characters except leading +
    const cleaned = phone.replace(/[^\d+]/g, "");
    if (!cleaned || cleaned === "+")
        return "";
    // Ensure it starts with +
    return cleaned.startsWith("+") ? cleaned : `+${cleaned}`;
}
/**
 * Mask phone number for logging (PII protection)
 */
function maskPhoneNumber(phone) {
    if (!phone || phone.length < 7)
        return "****";
    return `${phone.slice(0, 4)}****${phone.slice(-4)}`;
}
/**
 * Check if a caller is authorized based on configuration
 *
 * @param callerPhone - The caller's phone number
 * @param config - Voice account configuration
 * @returns Authorization result
 */
export function authorizeInboundCall(callerPhone, config) {
    const normalized = normalizePhoneNumber(callerPhone);
    const policy = config.dmPolicy ?? "allowlist";
    // Check if inbound is enabled
    if (config.enabled === false) {
        return {
            authorized: false,
            reason: "not_configured",
            message: "Voice channel is disabled",
            policy: "disabled",
        };
    }
    // Open policy - accept all calls
    if (policy === "open") {
        return {
            authorized: true,
            reason: "allowed",
            message: "Open policy - all calls accepted",
            policy: "open",
        };
    }
    // Pairing policy - only accept paired numbers
    if (policy === "pairing") {
        // TODO: Check against paired device database
        // For now, fall back to allowlist behavior
        const allowFrom = config.allowFrom ?? [];
        const matched = checkAllowlist(normalized, allowFrom);
        return matched
            ? {
                authorized: true,
                reason: "allowlist_match",
                message: "Caller matches paired device",
                matchedEntry: matched,
                policy: "pairing",
            }
            : {
                authorized: false,
                reason: "denied",
                message: "Caller not paired",
                policy: "pairing",
            };
    }
    // Allowlist policy (default)
    const allowFrom = config.allowFrom ?? [];
    // If allowlist is empty, deny all (secure default)
    if (allowFrom.length === 0) {
        return {
            authorized: false,
            reason: "not_configured",
            message: "No allowlist configured - inbound calls disabled for security",
            policy: "allowlist",
        };
    }
    // Check for wildcard (allow all)
    if (allowFrom.includes("*")) {
        return {
            authorized: true,
            reason: "allowed",
            message: "Wildcard allowlist - all calls accepted",
            matchedEntry: "*",
            policy: "allowlist",
        };
    }
    // Check against allowlist
    const matched = checkAllowlist(normalized, allowFrom);
    if (matched) {
        return {
            authorized: true,
            reason: "allowlist_match",
            message: `Caller matches allowlist entry: ${matched}`,
            matchedEntry: matched,
            policy: "allowlist",
        };
    }
    return {
        authorized: false,
        reason: "denied",
        message: "Caller not in allowlist",
        policy: "allowlist",
    };
}
/**
 * Check if a phone number matches any entry in the allowlist
 *
 * Supports:
 * - Exact match: "+14402915517"
 * - Wildcard: "*"
 * - Prefix match: "+1440*" (matches all +1440 numbers)
 */
function checkAllowlist(phone, allowFrom) {
    const normalized = normalizePhoneNumber(phone);
    for (const entry of allowFrom) {
        const normalizedEntry = normalizePhoneNumber(entry.replace(/\*$/, ""));
        // Wildcard - allow all
        if (entry === "*") {
            return "*";
        }
        // Prefix match (entry ends with *)
        if (entry.endsWith("*")) {
            if (normalized.startsWith(normalizedEntry)) {
                return entry;
            }
        }
        // Exact match
        if (normalized === normalizedEntry) {
            return entry;
        }
    }
    return null;
}
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
export function buildInboundSessionContext(event, logger = defaultLogger) {
    const normalized = normalizePhoneNumber(event.from);
    const sessionKey = `voice:${normalized.replace(/\+/g, "")}`;
    // Look up caller history
    const history = callerHistory.get(normalized);
    const isKnownCaller = !!history;
    // Build context instructions
    const contextParts = [
        "--- INBOUND CALL CONTEXT ---",
        `Call Direction: Inbound (caller reached you)`,
    ];
    // Add caller location if available
    if (event.fromCity || event.fromState || event.fromCountry) {
        const locationParts = [event.fromCity, event.fromState, event.fromCountry]
            .filter(Boolean)
            .join(", ");
        contextParts.push(`Caller Location: ${locationParts}`);
    }
    // Add caller name if available
    if (event.callerName) {
        contextParts.push(`Caller ID Name: ${event.callerName}`);
    }
    // Add history for known callers
    if (isKnownCaller && history) {
        contextParts.push("");
        contextParts.push("--- CALLER HISTORY ---");
        if (history.name) {
            contextParts.push(`Known as: ${history.name}`);
        }
        contextParts.push(`Previous calls: ${history.callCount}`);
        contextParts.push(`Last call: ${history.lastCallAt}`);
        if (history.notes) {
            contextParts.push(`Notes: ${history.notes}`);
        }
        contextParts.push("");
        contextParts.push("Since this is a returning caller, you may reference previous conversations if relevant.");
    }
    else {
        contextParts.push("");
        contextParts.push("--- NEW CALLER ---");
        contextParts.push("This is the first call from this number. Be welcoming and ask how you can help.");
    }
    contextParts.push("--- END CONTEXT ---");
    logger.debug(`Built session context for ${maskPhoneNumber(event.from)}`);
    return {
        sessionKey,
        isKnownCaller,
        callerName: history?.name ?? event.callerName,
        previousCallCount: history?.callCount ?? 0,
        lastCallAt: history?.lastCallAt,
        callerNotes: history?.notes,
        contextInstructions: contextParts.join("\n"),
    };
}
/**
 * Record a call start (updates caller history)
 */
export function recordCallStart(callerPhone, callerName) {
    const normalized = normalizePhoneNumber(callerPhone);
    const existing = callerHistory.get(normalized);
    callerHistory.set(normalized, {
        name: callerName ?? existing?.name,
        callCount: (existing?.callCount ?? 0) + 1,
        lastCallAt: new Date().toISOString(),
        notes: existing?.notes,
    });
}
/**
 * Update caller notes
 */
export function updateCallerNotes(callerPhone, notes) {
    const normalized = normalizePhoneNumber(callerPhone);
    const existing = callerHistory.get(normalized);
    if (existing) {
        existing.notes = notes;
        callerHistory.set(normalized, existing);
    }
}
/**
 * Record a missed call
 */
export function recordMissedCall(from, reason, voicemailTranscript) {
    missedCalls.push({
        timestamp: new Date().toISOString(),
        from,
        reason,
        hasVoicemail: !!voicemailTranscript,
        voicemailTranscript,
        callbackScheduled: false,
    });
    // Keep only last 100 missed calls in memory
    if (missedCalls.length > 100) {
        missedCalls.shift();
    }
}
/**
 * Get pending missed calls that need callback
 */
export function getPendingMissedCalls() {
    return missedCalls.filter((call) => !call.callbackScheduled && call.hasVoicemail);
}
/**
 * Mark a missed call as scheduled for callback
 */
export function markCallbackScheduled(timestamp) {
    const call = missedCalls.find((c) => c.timestamp === timestamp);
    if (call) {
        call.callbackScheduled = true;
        return true;
    }
    return false;
}
/**
 * Generate TwiML response for rejecting unauthorized calls
 *
 * @param reason - Human-readable rejection reason
 * @param recordVoicemail - Whether to offer voicemail
 * @returns TwiML XML string
 */
export function generateRejectTwiml(reason, recordVoicemail = true) {
    if (recordVoicemail) {
        return `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna">
    I'm sorry, I'm not able to take your call right now. 
    Please leave a message after the tone and I'll get back to you.
  </Say>
  <Record 
    maxLength="120" 
    action="/voicemail-complete" 
    transcribe="true"
    playBeep="true"
  />
  <Say voice="Polly.Joanna">
    I didn't receive a recording. Goodbye.
  </Say>
  <Hangup/>
</Response>`.trim();
    }
    return `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna">
    I'm sorry, this number is not able to receive calls at this time. Goodbye.
  </Say>
  <Hangup/>
</Response>`.trim();
}
/**
 * Generate TwiML response for accepting and forwarding to OpenAI Realtime
 *
 * @param sipUri - OpenAI SIP URI to connect to
 * @returns TwiML XML string
 */
export function generateAcceptTwiml(sipUri) {
    return `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial>
    <Sip>${sipUri}</Sip>
  </Dial>
</Response>`.trim();
}
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
export async function handleInboundCall(event, config, logger = defaultLogger) {
    logger.info(`Incoming call: ${maskPhoneNumber(event.from)} → ${maskPhoneNumber(event.to)}`);
    // Authorize the call
    const authResult = authorizeInboundCall(event.from, config);
    if (!authResult.authorized) {
        logger.warn(`Call rejected: ${maskPhoneNumber(event.from)} - ${authResult.reason}`);
        // Record missed call
        recordMissedCall(event.from, "unauthorized");
        // Return reject TwiML with voicemail option
        return {
            authorized: false,
            twiml: generateRejectTwiml(authResult.message, true),
            authResult,
        };
    }
    // Build session context for authorized call
    const sessionContext = buildInboundSessionContext(event, logger);
    // Record call start
    recordCallStart(event.from, event.callerName);
    logger.info(`Call authorized: ${maskPhoneNumber(event.from)} → session ${sessionContext.sessionKey}`);
    // Generate accept TwiML
    // Note: The actual SIP URI will be constructed by webhook-server.py
    // We return a placeholder that indicates acceptance
    const openaiProjectId = process.env.OPENAI_PROJECT_ID;
    const sipUri = openaiProjectId
        ? `sip:${openaiProjectId}@sip.api.openai.com;transport=tls`
        : "sip:placeholder@sip.api.openai.com;transport=tls";
    return {
        authorized: true,
        twiml: generateAcceptTwiml(sipUri),
        sessionContext,
        authResult,
    };
}
/**
 * Get caller history for display
 */
export function getCallerHistory(callerPhone) {
    const normalized = normalizePhoneNumber(callerPhone);
    return callerHistory.get(normalized);
}
/**
 * Get all known callers (for admin/debugging)
 */
export function getAllKnownCallers() {
    return Array.from(callerHistory.entries()).map(([phone, data]) => ({
        phone: maskPhoneNumber(phone),
        name: data.name,
        callCount: data.callCount,
        lastCallAt: data.lastCallAt,
    }));
}
/**
 * Get recent missed calls (for admin/debugging)
 */
export function getRecentMissedCalls(limit = 10) {
    return missedCalls
        .slice(-limit)
        .reverse()
        .map((call) => ({
        ...call,
        from: maskPhoneNumber(call.from),
    }));
}
/**
 * Export for testing/admin
 */
export const _internal = {
    normalizePhoneNumber,
    maskPhoneNumber,
    checkAllowlist,
    callerHistory,
    missedCalls,
};
//# sourceMappingURL=inbound.js.map