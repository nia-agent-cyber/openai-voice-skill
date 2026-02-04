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
const DEFAULT_ACCOUNT_ID = "default";
/**
 * Get the voice config section from OpenClaw config
 */
function getVoiceSection(cfg) {
    const channels = cfg.channels;
    return channels?.voice;
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
    listAccountIds: (cfg) => {
        const voice = getVoiceSection(cfg);
        if (!voice)
            return [];
        const ids = new Set();
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
    resolveAccount: (cfg, accountId) => {
        const voice = getVoiceSection(cfg);
        const id = accountId ?? DEFAULT_ACCOUNT_ID;
        // Try named account first
        const namedConfig = voice?.accounts?.[id];
        // Merge with base config for default account
        const config = id === DEFAULT_ACCOUNT_ID
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
        const configured = Boolean(config.twilioAccountSid &&
            config.twilioAuthToken &&
            config.twilioPhoneNumber);
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
    defaultAccountId: (_cfg) => {
        return DEFAULT_ACCOUNT_ID;
    },
    /**
     * Check if an account is configured
     */
    isConfigured: (account) => {
        return account.configured;
    },
    /**
     * Describe an account for status display
     */
    describeAccount: (account) => ({
        accountId: account.accountId,
        name: account.name,
        enabled: account.enabled,
        configured: account.configured,
        twilioPhoneNumber: account.twilioPhoneNumber,
    }),
    /**
     * Get allowFrom list for an account
     */
    resolveAllowFrom: (params) => {
        const account = voiceConfigAdapter.resolveAccount(params.cfg, params.accountId);
        return account.config.allowFrom;
    },
    /**
     * Format allowFrom entries (normalize phone numbers)
     */
    formatAllowFrom: (params) => {
        return params.allowFrom
            .map((entry) => String(entry).trim())
            .filter(Boolean)
            .map((entry) => {
            if (entry === "*")
                return "*";
            // Normalize to E.164 format
            const cleaned = entry.replace(/[^\d+]/g, "");
            return cleaned.startsWith("+") ? cleaned : `+${cleaned}`;
        })
            .filter(Boolean);
    },
};
//# sourceMappingURL=config.js.map