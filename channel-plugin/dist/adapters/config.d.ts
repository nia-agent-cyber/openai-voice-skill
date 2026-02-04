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
type OpenClawConfig = Record<string, unknown>;
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
 * Voice Config Adapter
 *
 * Implements ChannelConfigAdapter pattern from OpenClaw.
 */
export declare const voiceConfigAdapter: {
    /**
     * List all configured account IDs
     */
    listAccountIds: (cfg: OpenClawConfig) => string[];
    /**
     * Resolve a specific account configuration
     */
    resolveAccount: (cfg: OpenClawConfig, accountId?: string | null) => ResolvedVoiceAccount;
    /**
     * Get the default account ID
     */
    defaultAccountId: (_cfg: OpenClawConfig) => string;
    /**
     * Check if an account is configured
     */
    isConfigured: (account: ResolvedVoiceAccount) => boolean;
    /**
     * Describe an account for status display
     */
    describeAccount: (account: ResolvedVoiceAccount) => {
        accountId: string;
        name: string | undefined;
        enabled: boolean;
        configured: boolean;
        twilioPhoneNumber: string | undefined;
    };
    /**
     * Get allowFrom list for an account
     */
    resolveAllowFrom: (params: {
        cfg: OpenClawConfig;
        accountId?: string | null;
    }) => string[] | undefined;
    /**
     * Format allowFrom entries (normalize phone numbers)
     */
    formatAllowFrom: (params: {
        allowFrom: Array<string | number>;
    }) => string[];
};
export type VoiceConfigAdapter = typeof voiceConfigAdapter;
export {};
//# sourceMappingURL=config.d.ts.map