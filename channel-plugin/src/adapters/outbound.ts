/**
 * Voice Channel Outbound Adapter
 *
 * Handles sending messages via voice (text → TTS → phone call).
 * This is the core of outbound voice functionality.
 */

import { voiceConfigAdapter } from "./config.js";

// Using 'any' for OpenClawConfig to avoid tight coupling
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
  to: string; // Phone number to call
  text: string; // Message to speak
  accountId?: string | null;
}

/**
 * Voice Outbound Adapter
 *
 * Implements ChannelOutboundAdapter pattern from OpenClaw.
 * Delivery is "direct" - we initiate calls immediately, not via gateway.
 */
export const voiceOutboundAdapter = {
  /**
   * Delivery mode: direct means we send immediately
   * (as opposed to "gateway" which queues for a background service)
   */
  deliveryMode: "direct" as const,

  /**
   * No text chunking for voice - the full message is spoken
   */
  chunker: null,

  /**
   * Send text message via voice call
   *
   * Flow:
   * 1. Validate config and phone number
   * 2. Initiate Twilio call to target number
   * 3. Twilio webhook triggers OpenAI Realtime
   * 4. OpenAI speaks the message (TTS)
   *
   * @param ctx - Outbound context with config, target, and message
   * @returns Delivery result with call SID on success
   */
  sendText: async (ctx: OutboundContext): Promise<OutboundDeliveryResult> => {
    const { cfg, to, text, accountId } = ctx;

    // Resolve account config
    const account = voiceConfigAdapter.resolveAccount(cfg, accountId);

    if (!account.configured) {
      return {
        channel: "voice",
        success: false,
        error: "Voice channel not configured. Set channels.voice in config.",
      };
    }

    // Validate phone number format
    const normalizedTo = normalizePhoneNumber(to);
    if (!normalizedTo) {
      return {
        channel: "voice",
        success: false,
        error: `Invalid phone number: ${to}`,
      };
    }

    // Get credentials from config
    const {
      twilioAccountSid,
      twilioAuthToken,
      twilioPhoneNumber,
      webhookUrl,
    } = account.config;

    if (!twilioAccountSid || !twilioAuthToken || !twilioPhoneNumber) {
      return {
        channel: "voice",
        success: false,
        error: "Missing Twilio credentials in voice config",
      };
    }

    try {
      // Dynamic import to avoid bundling Twilio when not needed
      const twilio = await import("twilio");
      const client = twilio.default(twilioAccountSid, twilioAuthToken);

      // Build webhook URL with context
      const twimlUrl = buildTwimlUrl(webhookUrl, text);

      // Initiate the call
      const call = await client.calls.create({
        to: normalizedTo,
        from: twilioPhoneNumber,
        url: twimlUrl,
        // TODO: Add status callback for call completion tracking
      });

      return {
        channel: "voice",
        success: true,
        callSid: call.sid,
      };
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unknown error initiating call";
      return {
        channel: "voice",
        success: false,
        error: message,
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
function normalizePhoneNumber(input: string): string | null {
  const cleaned = input.replace(/[^\d+]/g, "");

  if (!cleaned) return null;

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

/**
 * Build TwiML webhook URL with message context
 *
 * The webhook will receive this and pass to OpenAI Realtime
 * which handles the actual TTS and conversation.
 */
function buildTwimlUrl(baseUrl: string | undefined, message: string): string {
  const base = baseUrl ?? "https://api.niavoice.org";
  const url = new URL("/voice/twiml", base);

  // Encode message for the voice prompt
  url.searchParams.set("message", message);

  return url.toString();
}

export type VoiceOutboundAdapter = typeof voiceOutboundAdapter;
