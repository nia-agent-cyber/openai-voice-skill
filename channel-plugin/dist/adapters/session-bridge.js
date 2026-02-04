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