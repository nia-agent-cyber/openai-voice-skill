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
/**
 * Voice channel plugin definition
 *
 * Follows the OpenClaw channel adapter pattern (see signal.js for reference).
 */
export declare const voicePlugin: ChannelPlugin;
/**
 * Plugin registration function
 *
 * OpenClaw calls this function with the plugin API when loading the plugin.
 * We register the voice channel so it appears in `openclaw status` and can
 * be configured under `channels.voice`.
 */
export default function register(api: PluginApi): void;
export type { VoiceConfig, VoiceAccountConfig } from "./adapters/config.js";
//# sourceMappingURL=index.d.ts.map