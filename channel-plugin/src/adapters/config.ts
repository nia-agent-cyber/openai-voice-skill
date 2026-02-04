/**
 * Voice Channel Config Adapter
 *
 * Handles reading/writing voice configuration from OpenClaw config.
 * Configuration lives at `channels.voice` in openclaw.yaml.
 *
 * Example config:
 * ```yaml
 * channels:
 *   voice:
 *     enabled: true
 *     twilioAccountSid: AC...
 *     twilioAuthToken: ...
 *     twilioPhoneNumber: +14402915517
 *     openaiApiKey: sk-...
 *     webhookUrl: https://api.niavoice.org
 *     allowFrom:
 *       - "+1234567890"
 * ```
 */

// Using 'any' for OpenClawConfig to avoid tight coupling with internal types
// In production, this would import from openclaw
type OpenClawConfig = Record<string, unknown>;

const DEFAULT_ACCOUNT_ID = "default";

/**
 * Voice account configuration
 */
export interface VoiceAccountConfig {
  enabled?: boolean;
  twilioAccountSid?: string;
  twilioAuthToken?: string;
  twilioPhoneNumber?: string;
  openaiApiKey?: string;
  webhookUrl?: string;
  allowFrom?: string[];
  dmPolicy?: "open" | "allowlist" | "pairing";
}

/**
 * Full voice channel configuration
 */
export interface VoiceConfig extends VoiceAccountConfig {
  accounts?: Record<string, VoiceAccountConfig>;
}

/**
 * Resolved account with computed properties
 */
export interface ResolvedVoiceAccount {
  accountId: string;
  name?: string;
  enabled: boolean;
  configured: boolean;
  config: VoiceAccountConfig;
  twilioPhoneNumber?: string;
}

/**
 * Get the voice config section from OpenClaw config
 */
function getVoiceSection(cfg: OpenClawConfig): VoiceConfig | undefined {
  const channels = cfg.channels as Record<string, unknown> | undefined;
  return channels?.voice as VoiceConfig | undefined;
}

/**
 * Voice Config Adapter
 *
 * Implements ChannelConfigAdapter pattern from OpenClaw.
 */
export const voiceConfigAdapter = {
  /**
   * List all configured account IDs
   */
  listAccountIds: (cfg: OpenClawConfig): string[] => {
    const voice = getVoiceSection(cfg);
    if (!voice) return [];

    const ids = new Set<string>();

    // Check for base-level config (default account)
    if (voice.twilioPhoneNumber || voice.twilioAccountSid) {
      ids.add(DEFAULT_ACCOUNT_ID);
    }

    // Check for named accounts
    if (voice.accounts) {
      for (const id of Object.keys(voice.accounts)) {
        ids.add(id);
      }
    }

    return Array.from(ids);
  },

  /**
   * Resolve a specific account configuration
   */
  resolveAccount: (
    cfg: OpenClawConfig,
    accountId?: string | null
  ): ResolvedVoiceAccount => {
    const voice = getVoiceSection(cfg);
    const id = accountId ?? DEFAULT_ACCOUNT_ID;

    // Try named account first
    const namedConfig = voice?.accounts?.[id];

    // Merge with base config for default account
    const config: VoiceAccountConfig =
      id === DEFAULT_ACCOUNT_ID
        ? {
            enabled: voice?.enabled,
            twilioAccountSid: voice?.twilioAccountSid,
            twilioAuthToken: voice?.twilioAuthToken,
            twilioPhoneNumber: voice?.twilioPhoneNumber,
            openaiApiKey: voice?.openaiApiKey,
            webhookUrl: voice?.webhookUrl,
            allowFrom: voice?.allowFrom,
            dmPolicy: voice?.dmPolicy,
            ...namedConfig,
          }
        : namedConfig ?? {};

    const enabled = config.enabled !== false;
    const configured = Boolean(
      config.twilioAccountSid &&
        config.twilioAuthToken &&
        config.twilioPhoneNumber
    );

    return {
      accountId: id,
      enabled,
      configured,
      config,
      twilioPhoneNumber: config.twilioPhoneNumber,
    };
  },

  /**
   * Get the default account ID
   */
  defaultAccountId: (_cfg: OpenClawConfig): string => {
    return DEFAULT_ACCOUNT_ID;
  },

  /**
   * Check if an account is configured
   */
  isConfigured: (account: ResolvedVoiceAccount): boolean => {
    return account.configured;
  },

  /**
   * Describe an account for status display
   */
  describeAccount: (account: ResolvedVoiceAccount) => ({
    accountId: account.accountId,
    name: account.name,
    enabled: account.enabled,
    configured: account.configured,
    twilioPhoneNumber: account.twilioPhoneNumber,
  }),

  /**
   * Get allowFrom list for an account
   */
  resolveAllowFrom: (params: {
    cfg: OpenClawConfig;
    accountId?: string | null;
  }): string[] | undefined => {
    const account = voiceConfigAdapter.resolveAccount(
      params.cfg,
      params.accountId
    );
    return account.config.allowFrom;
  },

  /**
   * Format allowFrom entries (normalize phone numbers)
   */
  formatAllowFrom: (params: {
    allowFrom: Array<string | number>;
  }): string[] => {
    return params.allowFrom
      .map((entry) => String(entry).trim())
      .filter(Boolean)
      .map((entry) => {
        if (entry === "*") return "*";
        // Normalize to E.164 format
        const cleaned = entry.replace(/[^\d+]/g, "");
        return cleaned.startsWith("+") ? cleaned : `+${cleaned}`;
      })
      .filter(Boolean);
  },
};

export type VoiceConfigAdapter = typeof voiceConfigAdapter;
