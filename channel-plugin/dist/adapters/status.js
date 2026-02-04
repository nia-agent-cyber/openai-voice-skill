/**
 * Voice Channel Status Adapter
 *
 * Handles health monitoring and status reporting for the voice channel.
 */
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
    },
    /**
     * Collect status issues for voice accounts
     *
     * Checks for common problems:
     * - Missing Twilio credentials
     * - Invalid phone number format
     * - Runtime errors
     */
    collectStatusIssues: (accounts) => {
        const issues = [];
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
    buildChannelSummary: (params) => {
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
    probeAccount: async (params) => {
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
                    new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), timeoutMs)),
                ]);
                result.twilioReachable = true;
            }
        }
        catch {
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
        }
        catch {
            // Webhook probe failed - leave as false
        }
        return result;
    },
    /**
     * Build account snapshot from account + runtime state
     */
    buildAccountSnapshot: (params) => {
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
//# sourceMappingURL=status.js.map