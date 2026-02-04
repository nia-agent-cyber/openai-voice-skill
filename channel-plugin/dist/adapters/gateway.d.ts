/**
 * Voice Channel Gateway Adapter
 *
 * Handles starting/stopping the voice service and session bridge.
 *
 * Architecture:
 * - webhook-server.py runs independently (DO NOT MODIFY)
 * - Session bridge syncs voice transcripts to OpenClaw sessions
 * - Outbound calls work via outbound adapter (direct Twilio API)
 */
import type { ChannelAccountSnapshot } from "../types.js";
import type { ResolvedVoiceAccount } from "./config.js";
import { type VoiceSessionBridge } from "./session-bridge.js";
type OpenClawConfig = Record<string, unknown>;
/**
 * Runtime environment from OpenClaw
 */
interface RuntimeEnv {
}
/**
 * Log sink for gateway operations
 */
interface LogSink {
    info: (msg: string) => void;
    warn: (msg: string) => void;
    error: (msg: string) => void;
    debug?: (msg: string) => void;
}
/**
 * Gateway context provided by OpenClaw
 */
interface GatewayContext {
    cfg: OpenClawConfig;
    accountId: string;
    account: ResolvedVoiceAccount;
    runtime: RuntimeEnv;
    abortSignal: AbortSignal;
    log?: LogSink;
    getStatus: () => ChannelAccountSnapshot;
    setStatus: (next: Partial<ChannelAccountSnapshot>) => void;
}
/**
 * Voice Gateway Adapter
 *
 * Implements ChannelGatewayAdapter pattern from OpenClaw.
 *
 * Components:
 * - Session Bridge: Syncs voice transcripts to OpenClaw sessions
 * - Health monitoring: Verifies webhook-server.py connectivity
 */
export declare const voiceGatewayAdapter: {
    /**
     * Start the voice gateway for an account
     *
     * This:
     * 1. Starts the session bridge (if not already running)
     * 2. Verifies webhook-server.py is reachable
     * 3. Updates gateway status
     */
    startAccount: (ctx: GatewayContext) => Promise<void>;
    /**
     * Stop the voice gateway for an account
     */
    stopAccount: (ctx: GatewayContext) => Promise<void>;
    /**
     * No QR login for voice (uses API credentials)
     */
    loginWithQrStart: undefined;
    loginWithQrWait: undefined;
    /**
     * Logout not applicable for voice (stateless API auth)
     */
    logoutAccount: undefined;
};
/**
 * Get the current session bridge instance (for testing/debugging)
 */
export declare function getSessionBridge(): VoiceSessionBridge | null;
export type VoiceGatewayAdapter = typeof voiceGatewayAdapter;
export {};
//# sourceMappingURL=gateway.d.ts.map