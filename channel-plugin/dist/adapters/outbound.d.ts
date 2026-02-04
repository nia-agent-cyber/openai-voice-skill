/**
 * Voice Channel Outbound Adapter
 *
 * Handles sending messages via voice (text → TTS → phone call).
 *
 * This adapter is a BRIDGE to the existing webhook-server.py.
 * It does NOT implement Twilio logic directly — it delegates to the
 * working webhook server via HTTP POST.
 */
type OpenClawConfig = Record<string, unknown>;
/**
 * Result of an outbound delivery attempt
 */
interface OutboundDeliveryResult {
    channel: "voice";
    success: boolean;
    callSid?: string;
    error?: string;
}
/**
 * Context for outbound operations
 */
interface OutboundContext {
    cfg: OpenClawConfig;
    to: string;
    text: string;
    accountId?: string | null;
}
/**
 * Voice Outbound Adapter
 *
 * Implements ChannelOutboundAdapter pattern from OpenClaw.
 * Delivery is "direct" - we initiate calls immediately via the webhook server.
 */
export declare const voiceOutboundAdapter: {
    /**
     * Delivery mode: direct means we send immediately
     * (as opposed to "gateway" which queues for a background service)
     */
    deliveryMode: "direct";
    /**
     * No text chunking for voice - the full message is spoken
     */
    chunker: null;
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
    sendText: (ctx: OutboundContext) => Promise<OutboundDeliveryResult>;
    /**
     * No media support for voice channel (yet)
     * Could later support playing audio files
     */
    sendMedia: undefined;
    /**
     * No poll support for voice
     */
    sendPoll: undefined;
};
export type VoiceOutboundAdapter = typeof voiceOutboundAdapter;
export {};
//# sourceMappingURL=outbound.d.ts.map