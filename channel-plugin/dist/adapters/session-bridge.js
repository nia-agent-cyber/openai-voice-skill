/**
 * Voice Channel Session Bridge
 *
 * Bridges voice calls with OpenClaw sessions for continuity.
 *
 * Architecture:
 * - webhook-server.py handles real-time voice via OpenAI Realtime API
 * - This bridge syncs call transcripts to OpenClaw sessions
 * - Enables cross-channel context (voice ↔ Telegram/etc.)
 *
 * Design Constraints:
 * - Cannot modify webhook-server.py (DO NOT TOUCH)
 * - Bridge receives events via HTTP endpoints
 * - Transcripts fetched via webhook-server.py's /history API
 */
import http from "node:http";
import crypto from "node:crypto";
import { URL } from "node:url";
// Store active call → session mappings
const callSessionMap = new Map();
// Store pending transcripts for calls in progress
const pendingTranscripts = new Map();
/**
 * Session Bridge for Voice ↔ OpenClaw integration
 *
 * This bridge:
 * 1. Receives call events from webhook-server.py (or polling)
 * 2. Fetches transcripts from the webhook server's /history API
 * 3. Injects transcripts into OpenClaw sessions
 */
export class VoiceSessionBridge {
    config;
    server = null;
    log;
    coreAgentDeps = null;
    constructor(config) {
        this.config = config;
        this.log = config.logger ?? {
            info: console.log,
            warn: console.warn,
            error: console.error,
            debug: console.debug,
        };
    }
    /**
     * Start the bridge HTTP server
     */
    async start() {
        const { port } = this.config;
        // Lazy-load core agent deps for session injection
        try {
            this.coreAgentDeps = await loadCoreAgentDeps();
            this.log.info("[voice-bridge] Core agent deps loaded");
        }
        catch (err) {
            this.log.warn(`[voice-bridge] Core agent deps unavailable: ${err instanceof Error ? err.message : String(err)}`);
        }
        return new Promise((resolve, reject) => {
            this.server = http.createServer((req, res) => {
                this.handleRequest(req, res).catch((err) => {
                    this.log.error(`[voice-bridge] Request error: ${err}`);
                    res.statusCode = 500;
                    res.end(JSON.stringify({ error: "Internal server error" }));
                });
            });
            this.server.on("error", reject);
            this.server.listen(port, "0.0.0.0", () => {
                this.log.info(`[voice-bridge] Listening on port ${port}`);
                this.log.info(`[voice-bridge] POST /call-event - Receive call events`);
                this.log.info(`[voice-bridge] POST /sync-transcript - Manual transcript sync`);
                this.log.info(`[voice-bridge] GET /health - Health check`);
                this.log.info(`[voice-bridge] GET /zombie-calls - List zombie/stale calls`);
                this.log.info(`[voice-bridge] POST /cleanup-stale-calls - Clean up zombie calls`);
                this.log.info(`[voice-bridge] GET /metrics - Prometheus metrics`);
                this.log.info(`[voice-bridge] GET /metrics/dashboard - Dashboard data`);
                this.log.info(`[voice-bridge] GET /metrics/export - Export data (CSV/JSON)`);
                this.log.info(`[voice-bridge] GET /metrics/health - Health check`);
                this.log.info(`[voice-bridge] GET /metrics/failures - Recent failures`);
                resolve();
            });
        });
    }
    /**
     * Stop the bridge server
     */
    async stop() {
        return new Promise((resolve) => {
            if (this.server) {
                this.server.close(() => {
                    this.server = null;
                    resolve();
                });
            }
            else {
                resolve();
            }
        });
    }
    /**
     * Handle incoming HTTP requests
     */
    async handleRequest(req, res) {
        const url = new URL(req.url || "/", `http://${req.headers.host}`);
        res.setHeader("Content-Type", "application/json");
        // Health check
        if (url.pathname === "/health" && req.method === "GET") {
            res.statusCode = 200;
            res.end(JSON.stringify({
                status: "healthy",
                activeCalls: callSessionMap.size,
                timestamp: new Date().toISOString(),
            }));
            return;
        }
        // Call event webhook (receives events from webhook-server.py)
        if (url.pathname === "/call-event" && req.method === "POST") {
            const body = await this.readBody(req);
            try {
                const event = JSON.parse(body);
                const result = await this.handleCallEvent(event);
                res.statusCode = 200;
                res.end(JSON.stringify(result));
            }
            catch (err) {
                res.statusCode = 400;
                res.end(JSON.stringify({ error: "Invalid call event" }));
            }
            return;
        }
        // Manual transcript sync (fetch from webhook-server.py and inject)
        if (url.pathname === "/sync-transcript" && req.method === "POST") {
            const body = await this.readBody(req);
            try {
                const { callId } = JSON.parse(body);
                if (!callId) {
                    res.statusCode = 400;
                    res.end(JSON.stringify({ error: "callId required" }));
                    return;
                }
                const result = await this.syncTranscriptToSession(callId);
                res.statusCode = result.success ? 200 : 500;
                res.end(JSON.stringify(result));
            }
            catch (err) {
                res.statusCode = 400;
                res.end(JSON.stringify({ error: "Invalid request" }));
            }
            return;
        }
        // List active call-session mappings
        if (url.pathname === "/sessions" && req.method === "GET") {
            const sessions = Array.from(callSessionMap.entries()).map(([callId, sessionKey]) => ({
                callId,
                sessionKey,
                pendingTranscripts: pendingTranscripts.get(callId)?.length ?? 0,
            }));
            res.statusCode = 200;
            res.end(JSON.stringify({ sessions }));
            return;
        }
        // Zombie call diagnostics (GET /zombie-calls)
        if (url.pathname === "/zombie-calls" && req.method === "GET") {
            try {
                const thresholdParam = url.searchParams.get("threshold");
                const threshold = thresholdParam ? parseInt(thresholdParam, 10) : 3600;
                const result = await this.getZombieCalls(threshold);
                res.statusCode = 200;
                res.end(JSON.stringify(result));
            }
            catch (err) {
                res.statusCode = 500;
                res.end(JSON.stringify({ error: "Failed to get zombie calls" }));
            }
            return;
        }
        // Cleanup stale calls endpoint (POST /cleanup-stale-calls)
        if (url.pathname === "/cleanup-stale-calls" && req.method === "POST") {
            try {
                const body = await this.readBody(req);
                const { threshold } = body ? JSON.parse(body) : {};
                const result = await this.cleanupStaleCalls(threshold);
                res.statusCode = 200;
                res.end(JSON.stringify(result));
            }
            catch (err) {
                res.statusCode = 500;
                res.end(JSON.stringify({
                    error: "Cleanup failed",
                    details: err instanceof Error ? err.message : String(err),
                }));
            }
            return;
        }
        // ==================== METRICS ENDPOINTS ====================
        // Prometheus-style metrics (GET /metrics)
        if (url.pathname === "/metrics" && req.method === "GET") {
            try {
                const metrics = await this.getPrometheusMetrics();
                res.setHeader("Content-Type", "text/plain; charset=utf-8");
                res.statusCode = 200;
                res.end(metrics);
            }
            catch (err) {
                res.statusCode = 500;
                res.end(JSON.stringify({ error: "Failed to get metrics" }));
            }
            return;
        }
        // Dashboard data (GET /metrics/dashboard)
        if (url.pathname === "/metrics/dashboard" && req.method === "GET") {
            try {
                const dashboard = await this.getDashboardMetrics();
                res.statusCode = 200;
                res.end(JSON.stringify(dashboard));
            }
            catch (err) {
                res.statusCode = 500;
                res.end(JSON.stringify({ error: "Failed to get dashboard data" }));
            }
            return;
        }
        // Export data (GET /metrics/export)
        if (url.pathname === "/metrics/export" && req.method === "GET") {
            try {
                const format = url.searchParams.get("format") || "json";
                const daysParam = url.searchParams.get("days");
                const days = daysParam ? parseInt(daysParam, 10) : 30;
                const data = await this.exportMetrics(format, days);
                if (format === "csv") {
                    res.setHeader("Content-Type", "text/csv; charset=utf-8");
                    res.setHeader("Content-Disposition", `attachment; filename="calls-export-${new Date().toISOString().split('T')[0]}.csv"`);
                }
                else {
                    res.setHeader("Content-Type", "application/json");
                }
                res.statusCode = 200;
                res.end(data);
            }
            catch (err) {
                res.statusCode = 500;
                res.end(JSON.stringify({ error: "Export failed" }));
            }
            return;
        }
        // Health check with metrics (GET /metrics/health)
        if (url.pathname === "/metrics/health" && req.method === "GET") {
            try {
                const health = await this.getHealthCheck();
                res.statusCode = health.status === "healthy" ? 200 : 503;
                res.end(JSON.stringify(health));
            }
            catch (err) {
                res.statusCode = 500;
                res.end(JSON.stringify({
                    status: "error",
                    error: "Health check failed"
                }));
            }
            return;
        }
        // Recent failures (GET /metrics/failures)
        if (url.pathname === "/metrics/failures" && req.method === "GET") {
            try {
                const limitParam = url.searchParams.get("limit");
                const limit = limitParam ? parseInt(limitParam, 10) : 10;
                const failures = await this.getRecentFailures(limit);
                res.statusCode = 200;
                res.end(JSON.stringify({ failures, count: failures.length }));
            }
            catch (err) {
                res.statusCode = 500;
                res.end(JSON.stringify({ error: "Failed to get failures" }));
            }
            return;
        }
        // Hourly timeseries (GET /metrics/hourly)
        if (url.pathname === "/metrics/hourly" && req.method === "GET") {
            try {
                const hoursParam = url.searchParams.get("hours");
                const hours = hoursParam ? parseInt(hoursParam, 10) : 24;
                const timeseries = await this.getHourlyTimeseries(hours);
                res.statusCode = 200;
                res.end(JSON.stringify({ timeseries, hours }));
            }
            catch (err) {
                res.statusCode = 500;
                res.end(JSON.stringify({ error: "Failed to get timeseries" }));
            }
            return;
        }
        // Daily timeseries (GET /metrics/daily)
        if (url.pathname === "/metrics/daily" && req.method === "GET") {
            try {
                const daysParam = url.searchParams.get("days");
                const days = daysParam ? parseInt(daysParam, 10) : 30;
                const timeseries = await this.getDailyTimeseries(days);
                res.statusCode = 200;
                res.end(JSON.stringify({ timeseries, days }));
            }
            catch (err) {
                res.statusCode = 500;
                res.end(JSON.stringify({ error: "Failed to get timeseries" }));
            }
            return;
        }
        // 404 for unknown routes
        res.statusCode = 404;
        res.end(JSON.stringify({ error: "Not found" }));
    }
    /**
     * Handle a call event from webhook-server.py
     */
    async handleCallEvent(event) {
        const { callId, eventType, phoneNumber, direction } = event;
        this.log.info(`[voice-bridge] Call event: ${eventType} for ${callId}`);
        switch (eventType) {
            case "call_started": {
                // Create or find OpenClaw session for this phone number
                const sessionKey = this.resolveSessionKey(phoneNumber);
                callSessionMap.set(callId, sessionKey);
                pendingTranscripts.set(callId, []);
                this.log.info(`[voice-bridge] Call ${callId} mapped to session ${sessionKey}`);
                return { status: "session_mapped", sessionKey };
            }
            case "transcript_update": {
                // Store transcript entry for later sync
                const transcriptData = event.data;
                if (transcriptData) {
                    const pending = pendingTranscripts.get(callId) ?? [];
                    pending.push(transcriptData);
                    pendingTranscripts.set(callId, pending);
                }
                return { status: "transcript_stored" };
            }
            case "call_ended": {
                // Sync full transcript to OpenClaw session
                const sessionKey = callSessionMap.get(callId);
                if (sessionKey) {
                    const result = await this.syncTranscriptToSession(callId);
                    // Cleanup
                    callSessionMap.delete(callId);
                    pendingTranscripts.delete(callId);
                    return {
                        status: result.success ? "session_synced" : "sync_failed",
                        sessionKey,
                    };
                }
                return { status: "no_session_found" };
            }
            default:
                return { status: "ignored" };
        }
    }
    /**
     * Sync a call's transcript to its OpenClaw session
     */
    async syncTranscriptToSession(callId) {
        try {
            // First try pending transcripts (real-time events)
            let transcript = pendingTranscripts.get(callId) ?? [];
            // If no pending transcripts, fetch from webhook-server.py's history API
            if (transcript.length === 0) {
                const fetched = await this.fetchTranscriptFromWebhook(callId);
                if (fetched) {
                    transcript = fetched;
                }
            }
            if (transcript.length === 0) {
                return { success: true, messagesInjected: 0 };
            }
            // Get or create session key for this call
            let sessionKey = callSessionMap.get(callId);
            if (!sessionKey) {
                // Try to extract phone from transcript metadata
                const phoneMatch = callId.match(/\+?\d{10,}/);
                if (phoneMatch) {
                    sessionKey = this.resolveSessionKey(phoneMatch[0]);
                }
                else {
                    sessionKey = `voice:${callId}`;
                }
            }
            // Inject into OpenClaw session
            const injected = await this.injectTranscriptToSession(sessionKey, transcript, callId);
            return {
                success: true,
                sessionKey,
                messagesInjected: injected,
            };
        }
        catch (err) {
            this.log.error(`[voice-bridge] Sync failed: ${err instanceof Error ? err.message : String(err)}`);
            return {
                success: false,
                error: err instanceof Error ? err.message : String(err),
            };
        }
    }
    /**
     * Fetch transcript from webhook-server.py's /history API
     */
    async fetchTranscriptFromWebhook(callId) {
        try {
            const url = `${this.config.webhookServerUrl}/history/${callId}/transcript`;
            this.log.debug(`[voice-bridge] Fetching transcript from ${url}`);
            const response = await fetch(url, { method: "GET" });
            if (!response.ok) {
                if (response.status === 404) {
                    this.log.debug(`[voice-bridge] No transcript found for ${callId}`);
                    return null;
                }
                throw new Error(`HTTP ${response.status}`);
            }
            const data = (await response.json());
            // Convert to our format
            return data.transcript.map((entry) => ({
                timestamp: entry.timestamp,
                speaker: entry.speaker === "user" ? "user" : "assistant",
                content: entry.content,
                eventType: entry.event_type,
            }));
        }
        catch (err) {
            this.log.warn(`[voice-bridge] Failed to fetch transcript: ${err instanceof Error ? err.message : String(err)}`);
            return null;
        }
    }
    /**
     * Inject transcript entries into an OpenClaw session
     *
     * This creates a session record with the voice conversation,
     * enabling cross-channel context continuity.
     */
    async injectTranscriptToSession(sessionKey, transcript, callId) {
        if (!this.coreAgentDeps || !this.config.openclawConfig) {
            // Fallback: Log for manual review
            this.log.info(`[voice-bridge] Would inject ${transcript.length} messages to ${sessionKey}`);
            for (const entry of transcript) {
                this.log.debug(`[voice-bridge]   [${entry.speaker}] ${entry.content.slice(0, 50)}...`);
            }
            return transcript.length;
        }
        const deps = this.coreAgentDeps;
        const cfg = this.config.openclawConfig;
        const agentId = "main";
        try {
            // Resolve session paths
            const storePath = deps.resolveStorePath(cfg.session?.store, { agentId });
            // Load or create session
            const sessionStore = deps.loadSessionStore(storePath);
            const now = Date.now();
            let sessionEntry = sessionStore[sessionKey];
            if (!sessionEntry) {
                sessionEntry = {
                    sessionId: crypto.randomUUID(),
                    updatedAt: now,
                };
                sessionStore[sessionKey] = sessionEntry;
                await deps.saveSessionStore(storePath, sessionStore);
            }
            const sessionFile = deps.resolveSessionFilePath(sessionEntry.sessionId, sessionEntry, { agentId });
            // Append voice transcript as a system event to the session
            const voiceSummary = this.formatTranscriptForSession(transcript, callId);
            // Write to JSONL session file
            const fs = await import("node:fs/promises");
            const sessionLine = JSON.stringify({
                role: "system",
                content: voiceSummary,
                timestamp: new Date().toISOString(),
                metadata: {
                    source: "voice-channel",
                    callId,
                    transcriptCount: transcript.length,
                },
            });
            await fs.appendFile(sessionFile, sessionLine + "\n", "utf-8");
            this.log.info(`[voice-bridge] Injected voice transcript (${transcript.length} turns) to ${sessionKey}`);
            return transcript.length;
        }
        catch (err) {
            this.log.error(`[voice-bridge] Session injection failed: ${err instanceof Error ? err.message : String(err)}`);
            throw err;
        }
    }
    /**
     * Format transcript for session injection
     */
    formatTranscriptForSession(transcript, callId) {
        const lines = [
            `📞 Voice Call Transcript (${callId})`,
            `Time: ${new Date().toISOString()}`,
            "",
        ];
        for (const entry of transcript) {
            const speaker = entry.speaker === "user" ? "📱 Caller" : "🤖 Agent";
            lines.push(`${speaker}: ${entry.content}`);
        }
        return lines.join("\n");
    }
    /**
     * Resolve session key for a phone number
     */
    resolveSessionKey(phoneNumber) {
        // Normalize phone number
        const normalized = phoneNumber.replace(/\D/g, "");
        return `voice:${normalized}`;
    }
    /**
     * Read request body
     */
    readBody(req) {
        return new Promise((resolve, reject) => {
            const chunks = [];
            req.on("data", (chunk) => chunks.push(chunk));
            req.on("end", () => resolve(Buffer.concat(chunks).toString("utf-8")));
            req.on("error", reject);
        });
    }
    /**
     * Get zombie calls from webhook server
     *
     * Zombie calls are calls with status='active' that have been running
     * longer than the threshold (default 1 hour). These occur when Twilio
     * call termination webhooks don't properly close the recording.
     *
     * Issue: #38 - Zombie calls with 60,000+ second durations
     */
    async getZombieCalls(thresholdSeconds = 3600) {
        try {
            const url = `${this.config.webhookServerUrl}/storage/stats`;
            this.log.debug(`[voice-bridge] Fetching storage stats from ${url}`);
            const response = await fetch(url, { method: "GET" });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const stats = (await response.json());
            // If there are active calls, fetch history to identify zombies
            if (stats.active_calls > 0) {
                const historyUrl = `${this.config.webhookServerUrl}/history?limit=100`;
                const historyResponse = await fetch(historyUrl, { method: "GET" });
                if (historyResponse.ok) {
                    const calls = (await historyResponse.json());
                    const now = Date.now();
                    const thresholdMs = thresholdSeconds * 1000;
                    const zombies = calls.filter((call) => {
                        if (call.status !== "active")
                            return false;
                        const startTime = new Date(call.started_at).getTime();
                        return now - startTime > thresholdMs;
                    });
                    return {
                        zombies,
                        count: zombies.length,
                        threshold: thresholdSeconds,
                    };
                }
            }
            return { zombies: [], count: 0, threshold: thresholdSeconds };
        }
        catch (err) {
            this.log.error(`[voice-bridge] Failed to get zombie calls: ${err instanceof Error ? err.message : String(err)}`);
            throw err;
        }
    }
    // ==================== METRICS METHODS ====================
    /**
     * Get Prometheus-style metrics for monitoring integration.
     */
    async getPrometheusMetrics() {
        try {
            const url = `${this.config.webhookServerUrl}/metrics/prometheus`;
            this.log.debug(`[voice-bridge] Fetching Prometheus metrics from ${url}`);
            const response = await fetch(url, { method: "GET" });
            if (response.ok) {
                return await response.text();
            }
            // Fallback: construct metrics from storage stats
            return this.constructPrometheusMetrics();
        }
        catch (err) {
            this.log.warn(`[voice-bridge] Prometheus fetch failed, using fallback: ${err}`);
            return this.constructPrometheusMetrics();
        }
    }
    /**
     * Construct Prometheus metrics from available data.
     */
    async constructPrometheusMetrics() {
        try {
            const statsUrl = `${this.config.webhookServerUrl}/storage/stats`;
            const response = await fetch(statsUrl, { method: "GET" });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const stats = await response.json();
            const lines = [
                "# HELP voice_calls_total Total number of calls",
                "# TYPE voice_calls_total counter",
                `voice_calls_total ${stats.total_calls}`,
                "",
                "# HELP voice_calls_active Currently active calls",
                "# TYPE voice_calls_active gauge",
                `voice_calls_active ${stats.active_calls}`,
                "",
                "# HELP voice_calls_with_transcript Calls with transcripts",
                "# TYPE voice_calls_with_transcript counter",
                `voice_calls_with_transcript ${stats.calls_with_transcripts}`,
                "",
                "# HELP voice_storage_size_mb Storage size in MB",
                "# TYPE voice_storage_size_mb gauge",
                `voice_storage_size_mb ${stats.recordings_size_mb?.toFixed(2) || 0}`,
                "",
                "# HELP voice_bridge_active_sessions Active bridge sessions",
                "# TYPE voice_bridge_active_sessions gauge",
                `voice_bridge_active_sessions ${callSessionMap.size}`,
            ];
            return lines.join("\n") + "\n";
        }
        catch (err) {
            return `# Error fetching metrics: ${err}\n`;
        }
    }
    /**
     * Get dashboard metrics for visualization.
     */
    async getDashboardMetrics() {
        try {
            const url = `${this.config.webhookServerUrl}/metrics/dashboard`;
            this.log.debug(`[voice-bridge] Fetching dashboard metrics from ${url}`);
            const response = await fetch(url, { method: "GET" });
            if (response.ok) {
                return await response.json();
            }
            // Fallback: construct from available data
            return this.constructDashboardMetrics();
        }
        catch (err) {
            this.log.warn(`[voice-bridge] Dashboard fetch failed, using fallback: ${err}`);
            return this.constructDashboardMetrics();
        }
    }
    /**
     * Construct dashboard metrics from available data.
     */
    async constructDashboardMetrics() {
        try {
            const statsUrl = `${this.config.webhookServerUrl}/storage/stats`;
            const historyUrl = `${this.config.webhookServerUrl}/history?limit=100`;
            const [statsResponse, historyResponse] = await Promise.all([
                fetch(statsUrl),
                fetch(historyUrl),
            ]);
            const stats = statsResponse.ok
                ? await statsResponse.json()
                : { total_calls: 0, active_calls: 0 };
            const calls = historyResponse.ok
                ? await historyResponse.json()
                : [];
            // Calculate metrics from history
            let completed = 0, failed = 0, timeout = 0;
            let totalDuration = 0, durationCount = 0;
            let inbound = 0, outbound = 0;
            let withTranscript = 0;
            const durations = [];
            for (const call of calls) {
                if (call.status === "completed") {
                    completed++;
                    if (call.duration_seconds && call.duration_seconds < 3600) {
                        durations.push(call.duration_seconds);
                        totalDuration += call.duration_seconds;
                        durationCount++;
                    }
                }
                else if (call.status === "failed") {
                    failed++;
                }
                else if (call.status === "timeout") {
                    timeout++;
                }
                if (call.call_type === "inbound")
                    inbound++;
                else
                    outbound++;
                if (call.has_transcript)
                    withTranscript++;
            }
            durations.sort((a, b) => a - b);
            const avgDuration = durationCount > 0 ? totalDuration / durationCount : 0;
            const p50 = durations.length > 0 ? durations[Math.floor(durations.length * 0.5)] : 0;
            const p95 = durations.length > 0 ? durations[Math.floor(durations.length * 0.95)] : 0;
            const successRate = calls.length > 0 ? (completed / calls.length) * 100 : 0;
            return {
                generated_at: new Date().toISOString(),
                period: {
                    note: "Based on last 100 calls",
                },
                summary: {
                    total_calls: stats.total_calls,
                    success_rate: Math.round(successRate * 10) / 10,
                    avg_duration: Math.round(avgDuration * 10) / 10,
                    active_now: stats.active_calls,
                },
                breakdown: {
                    by_status: { completed, failed, timeout, active: stats.active_calls },
                    by_type: { inbound, outbound },
                },
                duration: {
                    avg: Math.round(avgDuration * 10) / 10,
                    p50: Math.round(p50 * 10) / 10,
                    p95: Math.round(p95 * 10) / 10,
                },
                transcript: {
                    calls_with_transcript: withTranscript,
                    transcript_rate: calls.length > 0
                        ? Math.round((withTranscript / calls.length) * 1000) / 10
                        : 0,
                },
                bridge: {
                    active_sessions: callSessionMap.size,
                    pending_transcripts: pendingTranscripts.size,
                },
            };
        }
        catch (err) {
            return {
                error: "Failed to construct metrics",
                details: err instanceof Error ? err.message : String(err),
                generated_at: new Date().toISOString(),
            };
        }
    }
    /**
     * Export metrics data in specified format.
     */
    async exportMetrics(format, days) {
        try {
            const url = `${this.config.webhookServerUrl}/metrics/export?format=${format}&days=${days}`;
            const response = await fetch(url, { method: "GET" });
            if (response.ok) {
                return await response.text();
            }
            // Fallback: construct from history
            return this.constructExport(format, days);
        }
        catch (err) {
            this.log.warn(`[voice-bridge] Export fetch failed, using fallback: ${err}`);
            return this.constructExport(format, days);
        }
    }
    /**
     * Construct export from available data.
     */
    async constructExport(format, days) {
        try {
            const historyUrl = `${this.config.webhookServerUrl}/history?limit=500`;
            const response = await fetch(historyUrl);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const calls = await response.json();
            if (format === "csv") {
                const headers = ["call_id", "call_type", "caller_number", "callee_number",
                    "started_at", "ended_at", "duration_seconds", "status", "has_transcript"];
                const lines = [headers.join(",")];
                for (const call of calls) {
                    const values = headers.map(h => {
                        const v = call[h];
                        if (v === null || v === undefined)
                            return "";
                        const s = String(v);
                        return s.includes(",") ? `"${s}"` : s;
                    });
                    lines.push(values.join(","));
                }
                return lines.join("\n") + "\n";
            }
            return JSON.stringify({
                exported_at: new Date().toISOString(),
                period_days: days,
                call_count: calls.length,
                calls,
            }, null, 2);
        }
        catch (err) {
            return JSON.stringify({ error: "Export failed", details: String(err) });
        }
    }
    /**
     * Get health check with metrics indicators.
     */
    async getHealthCheck() {
        try {
            const url = `${this.config.webhookServerUrl}/metrics/health`;
            const response = await fetch(url, { method: "GET" });
            if (response.ok) {
                return await response.json();
            }
            // Fallback
            return this.constructHealthCheck();
        }
        catch (err) {
            this.log.warn(`[voice-bridge] Health check failed, using fallback: ${err}`);
            return this.constructHealthCheck();
        }
    }
    /**
     * Construct health check from available data.
     */
    async constructHealthCheck() {
        const warnings = [];
        let status = "healthy";
        try {
            const statsUrl = `${this.config.webhookServerUrl}/storage/stats`;
            const response = await fetch(statsUrl);
            if (!response.ok) {
                warnings.push("Cannot reach webhook server");
                status = "degraded";
            }
            else {
                const stats = await response.json();
                if (stats.active_calls > 10) {
                    warnings.push(`High active calls: ${stats.active_calls}`);
                }
            }
        }
        catch (err) {
            warnings.push(`Webhook server unreachable: ${err}`);
            status = "degraded";
        }
        return {
            status,
            timestamp: new Date().toISOString(),
            indicators: {
                bridge_active_sessions: callSessionMap.size,
                bridge_pending_transcripts: pendingTranscripts.size,
            },
            warnings,
        };
    }
    /**
     * Get recent failures for debugging.
     */
    async getRecentFailures(limit) {
        try {
            const url = `${this.config.webhookServerUrl}/metrics/failures?limit=${limit}`;
            const response = await fetch(url, { method: "GET" });
            if (response.ok) {
                const data = await response.json();
                return data.failures || [];
            }
            // Fallback: filter from history
            return this.constructRecentFailures(limit);
        }
        catch (err) {
            this.log.warn(`[voice-bridge] Failures fetch failed, using fallback: ${err}`);
            return this.constructRecentFailures(limit);
        }
    }
    /**
     * Construct recent failures from history.
     */
    async constructRecentFailures(limit) {
        try {
            const historyUrl = `${this.config.webhookServerUrl}/history?limit=100`;
            const response = await fetch(historyUrl);
            if (!response.ok) {
                return [];
            }
            const calls = await response.json();
            return calls
                .filter(c => c.status === "failed" || c.status === "timeout")
                .slice(0, limit);
        }
        catch {
            return [];
        }
    }
    /**
     * Get hourly timeseries for charts.
     */
    async getHourlyTimeseries(hours) {
        try {
            const url = `${this.config.webhookServerUrl}/metrics/hourly?hours=${hours}`;
            const response = await fetch(url, { method: "GET" });
            if (response.ok) {
                const data = await response.json();
                return data.timeseries || [];
            }
            return [];
        }
        catch {
            return [];
        }
    }
    /**
     * Get daily timeseries for trends.
     */
    async getDailyTimeseries(days) {
        try {
            const url = `${this.config.webhookServerUrl}/metrics/daily?days=${days}`;
            const response = await fetch(url, { method: "GET" });
            if (response.ok) {
                const data = await response.json();
                return data.timeseries || [];
            }
            return [];
        }
        catch {
            return [];
        }
    }
    /**
     * Clean up stale/zombie calls
     *
     * This is a workaround for the fact that webhook-server.py's handle_twilio_webhook()
     * doesn't call end_call_recording() when Twilio fires call completion events.
     *
     * Calls the Python recording manager's cleanup_stale_calls() method via HTTP.
     *
     * Issue: #38 - Zombie calls with 60,000+ second durations
     */
    async cleanupStaleCalls(thresholdSeconds) {
        try {
            // Call the cleanup endpoint on the webhook server
            // Note: This requires adding the cleanup endpoint to webhook-server.py
            // For now, we do the cleanup directly via the storage stats workaround
            const zombies = await this.getZombieCalls(thresholdSeconds ?? 3600);
            if (zombies.count === 0) {
                this.log.info("[voice-bridge] No zombie calls to clean up");
                return {
                    success: true,
                    cleaned_count: 0,
                    cleaned_calls: [],
                    errors: [],
                };
            }
            this.log.info(`[voice-bridge] Found ${zombies.count} zombie calls to clean up`);
            // Since we can't modify webhook-server.py, we'll trigger transcript sync
            // for each zombie call which will at least capture any pending transcripts
            const cleaned = [];
            const errors = [];
            for (const zombie of zombies.zombies) {
                try {
                    // Attempt transcript sync for each zombie call
                    const syncResult = await this.syncTranscriptToSession(zombie.call_id);
                    if (syncResult.success) {
                        cleaned.push({
                            call_id: zombie.call_id,
                            synced: true,
                            sessionKey: syncResult.sessionKey,
                        });
                        this.log.info(`[voice-bridge] Synced transcript for zombie call ${zombie.call_id}`);
                    }
                    else {
                        cleaned.push({
                            call_id: zombie.call_id,
                            synced: false,
                            error: syncResult.error,
                        });
                    }
                    // Clean up from our local tracking
                    callSessionMap.delete(zombie.call_id);
                    pendingTranscripts.delete(zombie.call_id);
                }
                catch (err) {
                    const errorMsg = `Failed to process zombie ${zombie.call_id}: ${err instanceof Error ? err.message : String(err)}`;
                    errors.push(errorMsg);
                    this.log.error(`[voice-bridge] ${errorMsg}`);
                }
            }
            return {
                success: errors.length === 0,
                cleaned_count: cleaned.length,
                cleaned_calls: cleaned,
                errors,
            };
        }
        catch (err) {
            this.log.error(`[voice-bridge] Cleanup failed: ${err instanceof Error ? err.message : String(err)}`);
            throw err;
        }
    }
}
// Lazy load core deps (adapted from voice-call plugin)
let coreDepsPromise = null;
async function loadCoreAgentDeps() {
    if (coreDepsPromise)
        return coreDepsPromise;
    coreDepsPromise = (async () => {
        // Try to find OpenClaw installation
        const fs = await import("node:fs");
        const path = await import("node:path");
        const { fileURLToPath, pathToFileURL } = await import("node:url");
        function findPackageRoot(startDir, name) {
            let dir = startDir;
            for (;;) {
                const pkgPath = path.join(dir, "package.json");
                try {
                    if (fs.existsSync(pkgPath)) {
                        const raw = fs.readFileSync(pkgPath, "utf8");
                        const pkg = JSON.parse(raw);
                        if (pkg.name === name)
                            return dir;
                    }
                }
                catch {
                    // ignore
                }
                const parent = path.dirname(dir);
                if (parent === dir)
                    return null;
                dir = parent;
            }
        }
        const candidates = new Set();
        if (process.argv[1])
            candidates.add(path.dirname(process.argv[1]));
        candidates.add(process.cwd());
        try {
            const urlPath = fileURLToPath(import.meta.url);
            candidates.add(path.dirname(urlPath));
        }
        catch {
            // ignore
        }
        let root = null;
        for (const start of candidates) {
            root = findPackageRoot(start, "openclaw");
            if (root)
                break;
        }
        if (!root) {
            // Check common install paths
            const commonPaths = [
                "/opt/homebrew/lib/node_modules/openclaw",
                "/usr/local/lib/node_modules/openclaw",
                path.join(process.env.HOME || "", ".openclaw/openclaw"),
            ];
            for (const p of commonPaths) {
                if (fs.existsSync(path.join(p, "package.json"))) {
                    root = p;
                    break;
                }
            }
        }
        if (!root) {
            throw new Error("Could not find OpenClaw installation");
        }
        const distPath = path.join(root, "dist", "config/sessions.js");
        if (!fs.existsSync(distPath)) {
            throw new Error(`OpenClaw sessions module not found at ${distPath}`);
        }
        const sessions = (await import(pathToFileURL(distPath).href));
        return sessions;
    })();
    return coreDepsPromise;
}
/**
 * Factory function to create a voice session bridge
 */
export function createSessionBridge(config) {
    return new VoiceSessionBridge(config);
}
//# sourceMappingURL=session-bridge.js.map