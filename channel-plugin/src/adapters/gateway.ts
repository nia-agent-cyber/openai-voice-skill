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
import { createSessionBridge, type VoiceSessionBridge } from "./session-bridge.js";

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

// Session bridge instance (shared across accounts)
let sessionBridge: VoiceSessionBridge | null = null;
let bridgeStartPromise: Promise<void> | null = null;

// Default bridge port (separate from webhook-server.py's 8080)
const DEFAULT_BRIDGE_PORT = 8082;

/**
 * Voice Gateway Adapter
 *
 * Implements ChannelGatewayAdapter pattern from OpenClaw.
 *
 * Components:
 * - Session Bridge: Syncs voice transcripts to OpenClaw sessions
 * - Health monitoring: Verifies webhook-server.py connectivity
 */
export const voiceGatewayAdapter = {
  /**
   * Start the voice gateway for an account
   *
   * This:
   * 1. Starts the session bridge (if not already running)
   * 2. Verifies webhook-server.py is reachable
   * 3. Updates gateway status
   */
  startAccount: async (ctx: GatewayContext): Promise<void> => {
    const { account, cfg, log, setStatus } = ctx;
    const webhookUrl = account.config.webhookUrl ?? "http://localhost:8080";
    const bridgePort = DEFAULT_BRIDGE_PORT;

    log?.info(`[voice:${account.accountId}] Starting voice gateway`);

    try {
      // Start session bridge if not already running
      if (!sessionBridge && !bridgeStartPromise) {
        bridgeStartPromise = startSessionBridge({
          port: bridgePort,
          webhookServerUrl: webhookUrl,
          openclawConfig: cfg,
          logger: log ? {
            info: log.info,
            warn: log.warn,
            error: log.error,
            debug: log.debug ?? log.info,
          } : undefined,
        });
      }

      if (bridgeStartPromise) {
        await bridgeStartPromise;
      }

      // Verify webhook-server.py is reachable
      const webhookHealthy = await checkWebhookHealth(webhookUrl);
      if (!webhookHealthy) {
        log?.warn(
          `[voice:${account.accountId}] webhook-server.py not reachable at ${webhookUrl}`
        );
        log?.warn(
          `[voice:${account.accountId}] Voice calls will work but session sync may fail`
        );
      } else {
        log?.info(
          `[voice:${account.accountId}] webhook-server.py connected at ${webhookUrl}`
        );
      }

      // Update status
      setStatus({
        accountId: account.accountId,
        running: true,
        lastStartAt: Date.now(),
        lastError: null,
      });

      log?.info(`[voice:${account.accountId}] Voice gateway started`);
      log?.info(`[voice:${account.accountId}] Session bridge on port ${bridgePort}`);
      log?.info(
        `[voice:${account.accountId}] Configure webhook-server.py to POST to http://localhost:${bridgePort}/call-event`
      );
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      log?.error(`[voice:${account.accountId}] Failed to start: ${errorMsg}`);
      setStatus({
        accountId: account.accountId,
        running: false,
        lastError: errorMsg,
      });
      throw err;
    }
  },

  /**
   * Stop the voice gateway for an account
   */
  stopAccount: async (ctx: GatewayContext): Promise<void> => {
    const { account, log, setStatus } = ctx;

    log?.info(`[voice:${account.accountId}] Stopping voice gateway`);

    // Stop session bridge if running
    if (sessionBridge) {
      try {
        await sessionBridge.stop();
        sessionBridge = null;
        bridgeStartPromise = null;
        log?.info(`[voice:${account.accountId}] Session bridge stopped`);
      } catch (err) {
        log?.warn(
          `[voice:${account.accountId}] Error stopping bridge: ${
            err instanceof Error ? err.message : String(err)
          }`
        );
      }
    }

    setStatus({
      accountId: account.accountId,
      running: false,
      lastStopAt: Date.now(),
    });

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

/**
 * Start the session bridge
 */
async function startSessionBridge(config: {
  port: number;
  webhookServerUrl: string;
  openclawConfig?: Record<string, unknown>;
  logger?: {
    info: (msg: string) => void;
    warn: (msg: string) => void;
    error: (msg: string) => void;
    debug: (msg: string) => void;
  };
}): Promise<void> {
  sessionBridge = createSessionBridge(config);
  await sessionBridge.start();
}

/**
 * Check if webhook-server.py is healthy
 */
async function checkWebhookHealth(webhookUrl: string): Promise<boolean> {
  try {
    const response = await fetch(`${webhookUrl}/health`, {
      method: "GET",
      signal: AbortSignal.timeout(5000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Get the current session bridge instance (for testing/debugging)
 */
export function getSessionBridge(): VoiceSessionBridge | null {
  return sessionBridge;
}

export type VoiceGatewayAdapter = typeof voiceGatewayAdapter;
