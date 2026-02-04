/**
 * Voice Channel Status Adapter
 *
 * Handles health monitoring and status reporting for the voice channel.
 */
import type { ChannelAccountSnapshot } from "../types.js";
import type { ResolvedVoiceAccount } from "./config.js";
type OpenClawConfig = Record<string, unknown>;
/**
 * Runtime state for a voice account
 */
interface VoiceRuntimeState {
    accountId: string;
    running: boolean;
    lastStartAt: number | null;
    lastStopAt: number | null;
    lastError: string | null;
    lastInboundAt?: number | null;
    lastOutboundAt?: number | null;
}
/**
 * Status issue detected for a channel
 */
interface ChannelStatusIssue {
    channel: "voice";
    accountId: string;
    kind: "intent" | "permissions" | "config" | "auth" | "runtime";
    message: string;
    fix?: string;
}
/**
 * Voice Status Adapter
 *
 * Implements ChannelStatusAdapter pattern from OpenClaw.
 */
export declare const voiceStatusAdapter: {
    /**
     * Default runtime state for new accounts
     */
    defaultRuntime: ChannelAccountSnapshot;
    /**
     * Collect status issues for voice accounts
     *
     * Checks for common problems:
     * - Missing Twilio credentials
     * - Invalid phone number format
     * - Runtime errors
     */
    collectStatusIssues: (accounts: ChannelAccountSnapshot[]) => ChannelStatusIssue[];
    /**
     * Build summary for channel status display
     */
    buildChannelSummary: (params: {
        account: ResolvedVoiceAccount;
        cfg: OpenClawConfig;
        defaultAccountId: string;
        snapshot: ChannelAccountSnapshot;
    }) => Record<string, unknown>;
    /**
     * Probe account connectivity
     *
     * For voice, we check:
     * 1. Twilio API is reachable
     * 2. Phone number is valid
     * 3. Webhook endpoint is responsive
     */
    probeAccount: (params: {
        account: ResolvedVoiceAccount;
        timeoutMs: number;
        cfg: OpenClawConfig;
    }) => Promise<{
        twilioReachable: boolean;
        webhookReachable: boolean;
        error?: string;
    }>;
    /**
     * Build account snapshot from account + runtime state
     */
    buildAccountSnapshot: (params: {
        account: ResolvedVoiceAccount;
        cfg: OpenClawConfig;
        runtime?: VoiceRuntimeState;
        probe?: unknown;
    }) => ChannelAccountSnapshot;
};
export type VoiceStatusAdapter = typeof voiceStatusAdapter;
export {};
//# sourceMappingURL=status.d.ts.map