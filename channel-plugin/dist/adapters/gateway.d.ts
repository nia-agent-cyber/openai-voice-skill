/**
 * Voice Channel Gateway Adapter
 *
 * Handles starting/stopping the voice service for inbound calls.
 * For Phase 1, this is mostly a placeholder - outbound works without gateway.
 * Phase 2 will implement inbound call handling here.
 */
import type { ChannelAccountSnapshot } from "../types.js";
import type { ResolvedVoiceAccount } from "./config.js";
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
 * For voice:
 * - Outbound calls don't need a running gateway (direct Twilio API)
 * - Inbound calls require webhook server + OpenAI Realtime (Phase 2)
 */
export declare const voiceGatewayAdapter: {
    /**
     * Start the voice gateway for an account
     *
     * Phase 1: Just update status, outbound works without gateway
     * Phase 2: Start webhook server for inbound calls
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
export type VoiceGatewayAdapter = typeof voiceGatewayAdapter;
export {};
//# sourceMappingURL=gateway.d.ts.map