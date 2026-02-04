/**
 * Type definitions for Voice Channel Plugin
 *
 * These mirror OpenClaw's channel plugin types but are defined locally
 * to avoid tight coupling with internal OpenClaw types.
 */
import type { VoiceConfigAdapter } from "./adapters/config.js";
import type { VoiceOutboundAdapter } from "./adapters/outbound.js";
import type { VoiceStatusAdapter } from "./adapters/status.js";
import type { VoiceGatewayAdapter } from "./adapters/gateway.js";
/**
 * Channel capabilities - what the voice channel supports
 */
export interface ChannelCapabilities {
    chatTypes: Array<"direct" | "group" | "thread">;
    media?: boolean;
    polls?: boolean;
    reactions?: boolean;
    edit?: boolean;
    unsend?: boolean;
    reply?: boolean;
    effects?: boolean;
    threads?: boolean;
    groupManagement?: boolean;
    nativeCommands?: boolean;
    blockStreaming?: boolean;
}
/**
 * Channel metadata for registration and UI
 */
export interface ChannelMeta {
    id: string;
    label: string;
    selectionLabel: string;
    docsPath: string;
    docsLabel?: string;
    blurb: string;
    order?: number;
    aliases?: string[];
    systemImage?: string;
}
/**
 * Voice channel plugin definition
 */
export interface ChannelPlugin {
    id: "voice";
    meta: ChannelMeta;
    capabilities: ChannelCapabilities;
    config: VoiceConfigAdapter;
    outbound: VoiceOutboundAdapter;
    status: VoiceStatusAdapter;
    gateway: VoiceGatewayAdapter;
    streaming?: unknown;
    pairing?: unknown;
    group?: unknown;
    directory?: unknown;
    threading?: unknown;
    mentions?: unknown;
    messageActions?: unknown;
}
/**
 * Account snapshot for status reporting
 */
export interface ChannelAccountSnapshot {
    accountId: string;
    name?: string;
    enabled?: boolean;
    configured?: boolean;
    running?: boolean;
    lastError?: string | null;
    lastStartAt?: number | null;
    lastStopAt?: number | null;
    lastInboundAt?: number | null;
    lastOutboundAt?: number | null;
}
/**
 * OpenClaw Plugin API (subset we need)
 *
 * This is the API object passed to the plugin's default export function.
 * We only define the methods we use to avoid tight coupling.
 */
export interface PluginApi {
    /**
     * Register a channel plugin with OpenClaw
     */
    registerChannel(opts: {
        plugin: ChannelPlugin;
    }): void;
    /**
     * Current OpenClaw configuration (read-only)
     */
    config: Record<string, unknown>;
    /**
     * Runtime helpers (TTS, etc.)
     */
    runtime?: {
        tts?: {
            textToSpeechTelephony(opts: {
                text: string;
                cfg: Record<string, unknown>;
            }): Promise<{
                buffer: Buffer;
                sampleRate: number;
            }>;
        };
    };
}
//# sourceMappingURL=types.d.ts.map