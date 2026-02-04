/**
 * Voice Channel Plugin for OpenClaw
 *
 * Enables voice calls as a native OpenClaw channel, providing:
 * - Session continuity with other channels (Telegram, etc.)
 * - Unified conversation history
 * - Standard security features (allowlists, DM policies)
 *
 * @module voice-channel
 */

import type { ChannelPlugin, PluginApi } from "./types.js";
import { voiceMeta } from "./meta.js";
import { voiceConfigAdapter } from "./adapters/config.js";
import { voiceOutboundAdapter } from "./adapters/outbound.js";
import { voiceStatusAdapter } from "./adapters/status.js";
import { voiceGatewayAdapter } from "./adapters/gateway.js";

/**
 * Voice channel plugin definition
 *
 * Follows the OpenClaw channel adapter pattern (see signal.js for reference).
 */
export const voicePlugin: ChannelPlugin = {
  id: "voice",

  meta: voiceMeta,

  capabilities: {
    chatTypes: ["direct"],
    media: false,
    polls: false,
    reactions: false,
    edit: false,
    unsend: false,
    reply: false,
    effects: false,
    threads: false,
    groupManagement: false,
    nativeCommands: false,
    blockStreaming: false,
  },

  config: voiceConfigAdapter,

  outbound: voiceOutboundAdapter,

  status: voiceStatusAdapter,

  gateway: voiceGatewayAdapter,

  // Voice-specific: no streaming (real-time audio, not text chunks)
  streaming: undefined,

  // Voice-specific: no pairing (uses phone number allowlist)
  pairing: undefined,

  // Voice-specific: no group support
  group: undefined,

  // Voice-specific: no directory integration yet (Phase 3)
  directory: undefined,

  // Voice-specific: no threading
  threading: undefined,

  // Voice-specific: no mentions
  mentions: undefined,

  // Voice-specific: no message actions beyond basic send
  messageActions: undefined,
};

/**
 * Plugin registration function
 *
 * OpenClaw calls this function with the plugin API when loading the plugin.
 * We register the voice channel so it appears in `openclaw status` and can
 * be configured under `channels.voice`.
 */
export default function register(api: PluginApi): void {
  api.registerChannel({ plugin: voicePlugin });
}

// Re-export types for consumers
export type { VoiceConfig, VoiceAccountConfig } from "./adapters/config.js";
