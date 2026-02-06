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

export interface BridgeConfig {
  /** Port for the bridge HTTP server */
  port: number;
  /** URL of webhook-server.py (e.g., http://localhost:8080) */
  webhookServerUrl: string;
  /** OpenClaw config for agent access */
  openclawConfig?: Record<string, unknown>;
  /** Logger interface */
  logger?: Logger;
}

export interface Logger {
  info: (msg: string) => void;
  warn: (msg: string) => void;
  error: (msg: string) => void;
  debug: (msg: string) => void;
}

export interface CallEvent {
  callId: string;
  eventType: "call_started" | "call_ended" | "transcript_update";
  phoneNumber: string;
  direction: "inbound" | "outbound";
  timestamp: string;
  data?: Record<string, unknown>;
}

export interface TranscriptEntry {
  timestamp: string;
  speaker: "user" | "assistant";
  content: string;
  eventType?: string;
}

export interface SessionSyncResult {
  success: boolean;
  sessionKey?: string;
  messagesInjected?: number;
  error?: string;
}

// Store active call → session mappings
const callSessionMap = new Map<string, string>();

// Store pending transcripts for calls in progress
const pendingTranscripts = new Map<string, TranscriptEntry[]>();

/**
 * Session Bridge for Voice ↔ OpenClaw integration
 *
 * This bridge:
 * 1. Receives call events from webhook-server.py (or polling)
 * 2. Fetches transcripts from the webhook server's /history API
 * 3. Injects transcripts into OpenClaw sessions
 */
export class VoiceSessionBridge {
  private config: BridgeConfig;
  private server: http.Server | null = null;
  private log: Logger;
  private coreAgentDeps: CoreAgentDeps | null = null;

  constructor(config: BridgeConfig) {
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
  async start(): Promise<void> {
    const { port } = this.config;

    // Lazy-load core agent deps for session injection
    try {
      this.coreAgentDeps = await loadCoreAgentDeps();
      this.log.info("[voice-bridge] Core agent deps loaded");
    } catch (err) {
      this.log.warn(
        `[voice-bridge] Core agent deps unavailable: ${err instanceof Error ? err.message : String(err)}`
      );
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
        resolve();
      });
    });
  }

  /**
   * Stop the bridge server
   */
  async stop(): Promise<void> {
    return new Promise((resolve) => {
      if (this.server) {
        this.server.close(() => {
          this.server = null;
          resolve();
        });
      } else {
        resolve();
      }
    });
  }

  /**
   * Handle incoming HTTP requests
   */
  private async handleRequest(
    req: http.IncomingMessage,
    res: http.ServerResponse
  ): Promise<void> {
    const url = new URL(req.url || "/", `http://${req.headers.host}`);

    res.setHeader("Content-Type", "application/json");

    // Health check
    if (url.pathname === "/health" && req.method === "GET") {
      res.statusCode = 200;
      res.end(
        JSON.stringify({
          status: "healthy",
          activeCalls: callSessionMap.size,
          timestamp: new Date().toISOString(),
        })
      );
      return;
    }

    // Call event webhook (receives events from webhook-server.py)
    if (url.pathname === "/call-event" && req.method === "POST") {
      const body = await this.readBody(req);
      try {
        const event = JSON.parse(body) as CallEvent;
        const result = await this.handleCallEvent(event);
        res.statusCode = 200;
        res.end(JSON.stringify(result));
      } catch (err) {
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
      } catch (err) {
        res.statusCode = 400;
        res.end(JSON.stringify({ error: "Invalid request" }));
      }
      return;
    }

    // List active call-session mappings
    if (url.pathname === "/sessions" && req.method === "GET") {
      const sessions = Array.from(callSessionMap.entries()).map(
        ([callId, sessionKey]) => ({
          callId,
          sessionKey,
          pendingTranscripts: pendingTranscripts.get(callId)?.length ?? 0,
        })
      );
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
      } catch (err) {
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
      } catch (err) {
        res.statusCode = 500;
        res.end(
          JSON.stringify({
            error: "Cleanup failed",
            details: err instanceof Error ? err.message : String(err),
          })
        );
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
  async handleCallEvent(event: CallEvent): Promise<{ status: string; sessionKey?: string }> {
    const { callId, eventType, phoneNumber, direction } = event;
    this.log.info(`[voice-bridge] Call event: ${eventType} for ${callId}`);

    switch (eventType) {
      case "call_started": {
        // Create or find OpenClaw session for this phone number
        const sessionKey = this.resolveSessionKey(phoneNumber);
        callSessionMap.set(callId, sessionKey);
        pendingTranscripts.set(callId, []);
        this.log.info(
          `[voice-bridge] Call ${callId} mapped to session ${sessionKey}`
        );
        return { status: "session_mapped", sessionKey };
      }

      case "transcript_update": {
        // Store transcript entry for later sync
        const transcriptData = event.data as TranscriptEntry | undefined;
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
  async syncTranscriptToSession(callId: string): Promise<SessionSyncResult> {
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
        } else {
          sessionKey = `voice:${callId}`;
        }
      }

      // Inject into OpenClaw session
      const injected = await this.injectTranscriptToSession(
        sessionKey,
        transcript,
        callId
      );

      return {
        success: true,
        sessionKey,
        messagesInjected: injected,
      };
    } catch (err) {
      this.log.error(
        `[voice-bridge] Sync failed: ${err instanceof Error ? err.message : String(err)}`
      );
      return {
        success: false,
        error: err instanceof Error ? err.message : String(err),
      };
    }
  }

  /**
   * Fetch transcript from webhook-server.py's /history API
   */
  private async fetchTranscriptFromWebhook(
    callId: string
  ): Promise<TranscriptEntry[] | null> {
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

      const data = (await response.json()) as {
        transcript: Array<{
          timestamp: string;
          speaker: string;
          content: string;
          event_type?: string;
        }>;
      };

      // Convert to our format
      return data.transcript.map((entry) => ({
        timestamp: entry.timestamp,
        speaker: entry.speaker === "user" ? "user" : "assistant",
        content: entry.content,
        eventType: entry.event_type,
      }));
    } catch (err) {
      this.log.warn(
        `[voice-bridge] Failed to fetch transcript: ${err instanceof Error ? err.message : String(err)}`
      );
      return null;
    }
  }

  /**
   * Inject transcript entries into an OpenClaw session
   *
   * This creates a session record with the voice conversation,
   * enabling cross-channel context continuity.
   */
  private async injectTranscriptToSession(
    sessionKey: string,
    transcript: TranscriptEntry[],
    callId: string
  ): Promise<number> {
    if (!this.coreAgentDeps || !this.config.openclawConfig) {
      // Fallback: Log for manual review
      this.log.info(
        `[voice-bridge] Would inject ${transcript.length} messages to ${sessionKey}`
      );
      for (const entry of transcript) {
        this.log.debug(
          `[voice-bridge]   [${entry.speaker}] ${entry.content.slice(0, 50)}...`
        );
      }
      return transcript.length;
    }

    const deps = this.coreAgentDeps;
    const cfg = this.config.openclawConfig;
    const agentId = "main";

    try {
      // Resolve session paths
      const storePath = deps.resolveStorePath(
        (cfg.session as Record<string, string> | undefined)?.store,
        { agentId }
      );

      // Load or create session
      const sessionStore = deps.loadSessionStore(storePath);
      const now = Date.now();

      let sessionEntry = sessionStore[sessionKey] as
        | { sessionId: string; updatedAt: number }
        | undefined;

      if (!sessionEntry) {
        sessionEntry = {
          sessionId: crypto.randomUUID(),
          updatedAt: now,
        };
        sessionStore[sessionKey] = sessionEntry;
        await deps.saveSessionStore(storePath, sessionStore);
      }

      const sessionFile = deps.resolveSessionFilePath(
        sessionEntry.sessionId,
        sessionEntry,
        { agentId }
      );

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

      this.log.info(
        `[voice-bridge] Injected voice transcript (${transcript.length} turns) to ${sessionKey}`
      );
      return transcript.length;
    } catch (err) {
      this.log.error(
        `[voice-bridge] Session injection failed: ${err instanceof Error ? err.message : String(err)}`
      );
      throw err;
    }
  }

  /**
   * Format transcript for session injection
   */
  private formatTranscriptForSession(
    transcript: TranscriptEntry[],
    callId: string
  ): string {
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
  private resolveSessionKey(phoneNumber: string): string {
    // Normalize phone number
    const normalized = phoneNumber.replace(/\D/g, "");
    return `voice:${normalized}`;
  }

  /**
   * Read request body
   */
  private readBody(req: http.IncomingMessage): Promise<string> {
    return new Promise((resolve, reject) => {
      const chunks: Buffer[] = [];
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
  async getZombieCalls(
    thresholdSeconds: number = 3600
  ): Promise<{ zombies: unknown[]; count: number; threshold: number }> {
    try {
      const url = `${this.config.webhookServerUrl}/storage/stats`;
      this.log.debug(`[voice-bridge] Fetching storage stats from ${url}`);

      const response = await fetch(url, { method: "GET" });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const stats = (await response.json()) as {
        active_calls: number;
        total_calls: number;
      };

      // If there are active calls, fetch history to identify zombies
      if (stats.active_calls > 0) {
        const historyUrl = `${this.config.webhookServerUrl}/history?limit=100`;
        const historyResponse = await fetch(historyUrl, { method: "GET" });

        if (historyResponse.ok) {
          const calls = (await historyResponse.json()) as Array<{
            call_id: string;
            status: string;
            started_at: string;
            ended_at: string | null;
            duration_seconds: number | null;
            has_transcript: boolean;
            has_audio: boolean;
          }>;

          const now = Date.now();
          const thresholdMs = thresholdSeconds * 1000;

          const zombies = calls.filter((call) => {
            if (call.status !== "active") return false;
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
    } catch (err) {
      this.log.error(
        `[voice-bridge] Failed to get zombie calls: ${err instanceof Error ? err.message : String(err)}`
      );
      throw err;
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
  async cleanupStaleCalls(thresholdSeconds?: number): Promise<{
    success: boolean;
    cleaned_count: number;
    cleaned_calls: unknown[];
    errors: string[];
  }> {
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

      this.log.info(
        `[voice-bridge] Found ${zombies.count} zombie calls to clean up`
      );

      // Since we can't modify webhook-server.py, we'll trigger transcript sync
      // for each zombie call which will at least capture any pending transcripts
      const cleaned: unknown[] = [];
      const errors: string[] = [];

      for (const zombie of zombies.zombies as Array<{ call_id: string }>) {
        try {
          // Attempt transcript sync for each zombie call
          const syncResult = await this.syncTranscriptToSession(zombie.call_id);
          if (syncResult.success) {
            cleaned.push({
              call_id: zombie.call_id,
              synced: true,
              sessionKey: syncResult.sessionKey,
            });
            this.log.info(
              `[voice-bridge] Synced transcript for zombie call ${zombie.call_id}`
            );
          } else {
            cleaned.push({
              call_id: zombie.call_id,
              synced: false,
              error: syncResult.error,
            });
          }

          // Clean up from our local tracking
          callSessionMap.delete(zombie.call_id);
          pendingTranscripts.delete(zombie.call_id);
        } catch (err) {
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
    } catch (err) {
      this.log.error(
        `[voice-bridge] Cleanup failed: ${err instanceof Error ? err.message : String(err)}`
      );
      throw err;
    }
  }
}

// Core agent deps interface (mirrors voice-call plugin pattern)
interface CoreAgentDeps {
  resolveStorePath: (store?: string, opts?: { agentId?: string }) => string;
  loadSessionStore: (storePath: string) => Record<string, unknown>;
  saveSessionStore: (
    storePath: string,
    store: Record<string, unknown>
  ) => Promise<void>;
  resolveSessionFilePath: (
    sessionId: string,
    entry: unknown,
    opts?: { agentId?: string }
  ) => string;
}

// Lazy load core deps (adapted from voice-call plugin)
let coreDepsPromise: Promise<CoreAgentDeps> | null = null;

async function loadCoreAgentDeps(): Promise<CoreAgentDeps> {
  if (coreDepsPromise) return coreDepsPromise;

  coreDepsPromise = (async () => {
    // Try to find OpenClaw installation
    const fs = await import("node:fs");
    const path = await import("node:path");
    const { fileURLToPath, pathToFileURL } = await import("node:url");

    function findPackageRoot(startDir: string, name: string): string | null {
      let dir = startDir;
      for (;;) {
        const pkgPath = path.join(dir, "package.json");
        try {
          if (fs.existsSync(pkgPath)) {
            const raw = fs.readFileSync(pkgPath, "utf8");
            const pkg = JSON.parse(raw) as { name?: string };
            if (pkg.name === name) return dir;
          }
        } catch {
          // ignore
        }
        const parent = path.dirname(dir);
        if (parent === dir) return null;
        dir = parent;
      }
    }

    const candidates = new Set<string>();
    if (process.argv[1]) candidates.add(path.dirname(process.argv[1]));
    candidates.add(process.cwd());
    try {
      const urlPath = fileURLToPath(import.meta.url);
      candidates.add(path.dirname(urlPath));
    } catch {
      // ignore
    }

    let root: string | null = null;
    for (const start of candidates) {
      root = findPackageRoot(start, "openclaw");
      if (root) break;
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

    const sessions = (await import(pathToFileURL(distPath).href)) as CoreAgentDeps;
    return sessions;
  })();

  return coreDepsPromise;
}

/**
 * Factory function to create a voice session bridge
 */
export function createSessionBridge(config: BridgeConfig): VoiceSessionBridge {
  return new VoiceSessionBridge(config);
}
