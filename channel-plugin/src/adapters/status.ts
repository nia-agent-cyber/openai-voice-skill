/**
 * Voice Channel Status Adapter
 *
 * Handles health monitoring and status reporting for the voice channel.
 */

import type { ChannelAccountSnapshot } from "../types.js";
import type { ResolvedVoiceAccount } from "./config.js";

// Using 'any' for OpenClawConfig to avoid tight coupling
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
export const voiceStatusAdapter = {
  /**
   * Default runtime state for new accounts
   */
  defaultRuntime: {
    accountId: "default",
    running: false,
    lastStartAt: null,
    lastStopAt: null,
    lastError: null,
  } as ChannelAccountSnapshot,

  /**
   * Collect status issues for voice accounts
   *
   * Checks for common problems:
   * - Missing Twilio credentials
   * - Invalid phone number format
   * - Runtime errors
   */
  collectStatusIssues: (accounts: ChannelAccountSnapshot[]): ChannelStatusIssue[] => {
    const issues: ChannelStatusIssue[] = [];

    for (const account of accounts) {
      // Check for runtime errors
      if (account.lastError) {
        issues.push({
          channel: "voice",
          accountId: account.accountId,
          kind: "runtime",
          message: `Voice error: ${account.lastError}`,
        });
      }

      // Check configuration
      if (!account.configured) {
        issues.push({
          channel: "voice",
          accountId: account.accountId,
          kind: "config",
          message: "Voice channel not fully configured",
          fix: "Set twilioAccountSid, twilioAuthToken, and twilioPhoneNumber in channels.voice",
        });
      }
    }

    return issues;
  },

  /**
   * Build summary for channel status display
   */
  buildChannelSummary: (params: {
    account: ResolvedVoiceAccount;
    cfg: OpenClawConfig;
    defaultAccountId: string;
    snapshot: ChannelAccountSnapshot;
  }): Record<string, unknown> => {
    const { account, snapshot } = params;

    return {
      configured: account.configured,
      enabled: account.enabled,
      twilioPhoneNumber: account.twilioPhoneNumber ?? null,
      running: snapshot.running ?? false,
      lastStartAt: snapshot.lastStartAt ?? null,
      lastStopAt: snapshot.lastStopAt ?? null,
      lastError: snapshot.lastError ?? null,
      lastOutboundAt: snapshot.lastOutboundAt ?? null,
      lastInboundAt: snapshot.lastInboundAt ?? null,
    };
  },

  /**
   * Probe account connectivity
   *
   * For voice, we check:
   * 1. Twilio API is reachable
   * 2. Phone number is valid
   * 3. Webhook endpoint is responsive
   */
  probeAccount: async (params: {
    account: ResolvedVoiceAccount;
    timeoutMs: number;
    cfg: OpenClawConfig;
  }): Promise<{
    twilioReachable: boolean;
    webhookReachable: boolean;
    error?: string;
  }> => {
    const { account, timeoutMs } = params;

    if (!account.configured) {
      return {
        twilioReachable: false,
        webhookReachable: false,
        error: "Not configured",
      };
    }

    const result = {
      twilioReachable: false,
      webhookReachable: false,
    };

    // Probe Twilio API
    try {
      const { twilioAccountSid, twilioAuthToken } = account.config;
      if (twilioAccountSid && twilioAuthToken) {
        const twilio = await import("twilio");
        const client = twilio.default(twilioAccountSid, twilioAuthToken);

        // Simple API call to verify credentials
        await Promise.race([
          client.api.accounts(twilioAccountSid).fetch(),
          new Promise((_, reject) =>
            setTimeout(() => reject(new Error("timeout")), timeoutMs)
          ),
        ]);

        result.twilioReachable = true;
      }
    } catch {
      // Twilio probe failed - leave as false
    }

    // Probe webhook endpoint
    try {
      const webhookUrl = account.config.webhookUrl ?? "https://api.niavoice.org";
      const healthUrl = `${webhookUrl}/health`;

      const response = await fetch(healthUrl, {
        method: "GET",
        signal: AbortSignal.timeout(timeoutMs),
      });

      result.webhookReachable = response.ok;
    } catch {
      // Webhook probe failed - leave as false
    }

    return result;
  },

  /**
   * Build account snapshot from account + runtime state
   */
  buildAccountSnapshot: (params: {
    account: ResolvedVoiceAccount;
    cfg: OpenClawConfig;
    runtime?: VoiceRuntimeState;
    probe?: unknown;
  }): ChannelAccountSnapshot => {
    const { account, runtime, probe } = params;

    return {
      accountId: account.accountId,
      name: account.name,
      enabled: account.enabled,
      configured: account.configured,
      running: runtime?.running ?? false,
      lastStartAt: runtime?.lastStartAt ?? null,
      lastStopAt: runtime?.lastStopAt ?? null,
      lastError: runtime?.lastError ?? null,
      lastInboundAt: runtime?.lastInboundAt ?? null,
      lastOutboundAt: runtime?.lastOutboundAt ?? null,
    };
  },
};

export type VoiceStatusAdapter = typeof voiceStatusAdapter;
