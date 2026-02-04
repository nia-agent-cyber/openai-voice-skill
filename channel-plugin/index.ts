/**
 * Voice Channel Plugin Entry Point
 *
 * This file provides the plugin in the object form that OpenClaw expects.
 * OpenClaw uses jiti to load TypeScript directly.
 */

// Import the compiled plugin components
import { voicePlugin } from "./dist/index.js";
import type { PluginApi } from "./dist/types.js";

/**
 * Plugin object in the standard OpenClaw format
 */
const voiceChannelPlugin = {
  id: "voice-channel",
  name: "Voice Channel",
  configSchema: undefined, // Channel config lives under channels.voice, not plugins.entries

  register(api: PluginApi): void {
    api.registerChannel({ plugin: voicePlugin });
    console.log("[voice-channel] Voice channel registered");
  },
};

export default voiceChannelPlugin;
