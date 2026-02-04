/**
 * Voice Channel Gateway Adapter
 *
 * Handles starting/stopping the voice service for inbound calls.
 * For Phase 1, this is mostly a placeholder - outbound works without gateway.
 * Phase 2 will implement inbound call handling here.
 */

import type { ChannelAccountSnapshot } from "../types.js";
import type { ResolvedVoiceAccount } from "./config.js";

// Using 'any' for OpenClawConfig to avoid tight coupling
type OpenClawConfig = Record<string, unknown>;

/**
 * Runtime environment from OpenClaw
 */
interface RuntimeEnv {
  // Placeholder for OpenClaw runtime
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
export const voiceGatewayAdapter = {
  /**
   * Start the voice gateway for an account
   *
   * Phase 1: Just update status, outbound works without gateway
   * Phase 2: Start webhook server for inbound calls
   */
  startAccount: async (ctx: GatewayContext): Promise<void> => {
    const { account, log, setStatus } = ctx;

    log?.info(`[voice:${account.accountId}] Starting voice gateway`);

    // Update status
    setStatus({
      accountId: account.accountId,
      running: true,
      lastStartAt: Date.now(),
      lastError: null,
    });

    // Phase 1: No actual server needed for outbound-only
    // Phase 2: Start webhook server here
    //
    // Future implementation:
    // const { startVoiceServer } = await import("../server/index.js");
    // await startVoiceServer({
    //   port: 8080,
    //   account,
    //   abortSignal: ctx.abortSignal,
    //   onInboundCall: (callSid, from) => {
    //     // Route to OpenClaw session
    //   },
    // });

    log?.info(`[voice:${account.accountId}] Voice gateway started (outbound-only mode)`);
  },

  /**
   * Stop the voice gateway for an account
   */
  stopAccount: async (ctx: GatewayContext): Promise<void> => {
    const { account, log, setStatus } = ctx;

    log?.info(`[voice:${account.accountId}] Stopping voice gateway`);

    setStatus({
      accountId: account.accountId,
      running: false,
      lastStopAt: Date.now(),
    });

    // Phase 2: Stop webhook server here

    log?.info(`[voice:${account.accountId}] Voice gateway stopped`);
  },

  /**
   * No QR login for voice (uses API credentials)
   */
  loginWithQrStart: undefined,
  loginWithQrWait: undefined,

  /**
   * Logout not applicable for voice (stateless API auth)
   */
  logoutAccount: undefined,
};

export type VoiceGatewayAdapter = typeof voiceGatewayAdapter;
