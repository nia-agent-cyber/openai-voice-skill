/**
 * Voice Channel Outbound Adapter
 *
 * Handles sending messages via voice (text → TTS → phone call).
 *
 * This adapter is a BRIDGE to the existing webhook-server.py.
 * It does NOT implement Twilio logic directly — it delegates to the
 * working webhook server via HTTP POST.
 */
import { voiceConfigAdapter } from "./config.js";
const DEFAULT_WEBHOOK_URL = "https://api.niavoice.org";
/**
 * Voice Outbound Adapter
 *
 * Implements ChannelOutboundAdapter pattern from OpenClaw.
 * Delivery is "direct" - we initiate calls immediately via the webhook server.
 */
export const voiceOutboundAdapter = {
    /**
     * Delivery mode: direct means we send immediately
     * (as opposed to "gateway" which queues for a background service)
     */
    deliveryMode: "direct",
    /**
     * No text chunking for voice - the full message is spoken
     */
    chunker: null,
    /**
     * Send text message via voice call
     *
     * Flow:
     * 1. Validate phone number
     * 2. POST to webhook server's /call endpoint
     * 3. Webhook server handles Twilio + OpenAI Realtime
     *
     * @param ctx - Outbound context with config, target, and message
     * @returns Delivery result with call ID on success
     */
    sendText: async (ctx) => {
        const { cfg, to, text, accountId } = ctx;
        // Resolve account config
        const account = voiceConfigAdapter.resolveAccount(cfg, accountId);
        // Validate phone number format
        const normalizedTo = normalizePhoneNumber(to);
        if (!normalizedTo) {
            return {
                channel: "voice",
                success: false,
                error: `Invalid phone number: ${to}`,
            };
        }
        // Get webhook URL from config, with sensible default
        const webhookBaseUrl = account.config.webhookUrl ?? DEFAULT_WEBHOOK_URL;
        try {
            // POST to existing webhook server — it handles all Twilio logic
            const response = await fetch(`${webhookBaseUrl}/call`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    to: normalizedTo,
                    message: text,
                }),
            });
            if (!response.ok) {
                const errorText = await response.text();
                return {
                    channel: "voice",
                    success: false,
                    error: `Webhook server error (${response.status}): ${errorText}`,
                };
            }
            const result = (await response.json());
            if (result.status === "error" || result.error) {
                return {
                    channel: "voice",
                    success: false,
                    error: result.error ?? result.message ?? "Unknown error from webhook server",
                };
            }
            return {
                channel: "voice",
                success: true,
                callSid: result.call_id,
            };
        }
        catch (error) {
            const message = error instanceof Error ? error.message : "Unknown error initiating call";
            return {
                channel: "voice",
                success: false,
                error: `Failed to reach webhook server: ${message}`,
            };
        }
    },
    /**
     * No media support for voice channel (yet)
     * Could later support playing audio files
     */
    sendMedia: undefined,
    /**
     * No poll support for voice
     */
    sendPoll: undefined,
};
/**
 * Normalize phone number to E.164 format
 */
function normalizePhoneNumber(input) {
    const cleaned = input.replace(/[^\d+]/g, "");
    if (!cleaned)
        return null;
    // Already E.164
    if (cleaned.startsWith("+") && cleaned.length >= 10) {
        return cleaned;
    }
    // Assume US number if no country code
    if (cleaned.length === 10) {
        return `+1${cleaned}`;
    }
    // Has country code but missing +
    if (cleaned.length >= 11) {
        return `+${cleaned}`;
    }
    return null;
}
//# sourceMappingURL=outbound.js.map