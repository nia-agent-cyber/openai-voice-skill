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

  // Optional adapters (not used for voice v1)
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
