import { l as createSubsystemLogger } from "./exec-CjyVHUuE.js";
import { R as parseAgentSessionKey, s as resolveAgentWorkspaceDir } from "./agent-scope-qNPdmst1.js";
import { s as resolveStateDir } from "./paths-BFxmmTT5.js";
import { i as resolveSessionTranscriptsDirForAgent } from "./paths-Bkjq_KcG.js";
import { t as redactSensitiveText } from "./redact-wH73ib3-.js";
import { o as hashText, t as requireNodeSqlite } from "./sqlite-CqVsQPIl.js";
import os from "node:os";
import path from "node:path";
import fs from "node:fs/promises";
import { spawn } from "node:child_process";

//#region src/memory/session-files.ts
const log$1 = createSubsystemLogger("memory");
async function listSessionFilesForAgent(agentId) {
	const dir = resolveSessionTranscriptsDirForAgent(agentId);
	try {
		return (await fs.readdir(dir, { withFileTypes: true })).filter((entry) => entry.isFile()).map((entry) => entry.name).filter((name) => name.endsWith(".jsonl")).map((name) => path.join(dir, name));
	} catch {
		return [];
	}
}
function sessionPathForFile(absPath) {
	return path.join("sessions", path.basename(absPath)).replace(/\\/g, "/");
}
function normalizeSessionText(value) {
	return value.replace(/\s*\n+\s*/g, " ").replace(/\s+/g, " ").trim();
}
function extractSessionText(content) {
	if (typeof content === "string") {
		const normalized = normalizeSessionText(content);
		return normalized ? normalized : null;
	}
	if (!Array.isArray(content)) return null;
	const parts = [];
	for (const block of content) {
		if (!block || typeof block !== "object") continue;
		const record = block;
		if (record.type !== "text" || typeof record.text !== "string") continue;
		const normalized = normalizeSessionText(record.text);
		if (normalized) parts.push(normalized);
	}
	if (parts.length === 0) return null;
	return parts.join(" ");
}
async function buildSessionEntry(absPath) {
	try {
		const stat = await fs.stat(absPath);
		const lines = (await fs.readFile(absPath, "utf-8")).split("\n");
		const collected = [];
		for (const line of lines) {
			if (!line.trim()) continue;
			let record;
			try {
				record = JSON.parse(line);
			} catch {
				continue;
			}
			if (!record || typeof record !== "object" || record.type !== "message") continue;
			const message = record.message;
			if (!message || typeof message.role !== "string") continue;
			if (message.role !== "user" && message.role !== "assistant") continue;
			const text = extractSessionText(message.content);
			if (!text) continue;
			const safe = redactSensitiveText(text, { mode: "tools" });
			const label = message.role === "user" ? "User" : "Assistant";
			collected.push(`${label}: ${safe}`);
		}
		const content = collected.join("\n");
		return {
			path: sessionPathForFile(absPath),
			absPath,
			mtimeMs: stat.mtimeMs,
			size: stat.size,
			hash: hashText(content),
			content
		};
	} catch (err) {
		log$1.debug(`Failed reading session file ${absPath}: ${String(err)}`);
		return null;
	}
}

//#endregion
//#region src/memory/qmd-manager.ts
const log = createSubsystemLogger("memory");
const SNIPPET_HEADER_RE = /@@\s*-([0-9]+),([0-9]+)/;
var QmdMemoryManager = class QmdMemoryManager {
	static async create(params) {
		const resolved = params.resolved.qmd;
		if (!resolved) return null;
		const manager = new QmdMemoryManager({
			cfg: params.cfg,
			agentId: params.agentId,
			resolved
		});
		await manager.initialize();
		return manager;
	}
	constructor(params) {
		this.collectionRoots = /* @__PURE__ */ new Map();
		this.sources = /* @__PURE__ */ new Set();
		this.docPathCache = /* @__PURE__ */ new Map();
		this.updateTimer = null;
		this.pendingUpdate = null;
		this.closed = false;
		this.db = null;
		this.lastUpdateAt = null;
		this.lastEmbedAt = null;
		this.cfg = params.cfg;
		this.agentId = params.agentId;
		this.qmd = params.resolved;
		this.workspaceDir = resolveAgentWorkspaceDir(params.cfg, params.agentId);
		this.stateDir = resolveStateDir(process.env, os.homedir);
		this.agentStateDir = path.join(this.stateDir, "agents", this.agentId);
		this.qmdDir = path.join(this.agentStateDir, "qmd");
		this.xdgConfigHome = path.join(this.qmdDir, "xdg-config");
		this.xdgCacheHome = path.join(this.qmdDir, "xdg-cache");
		this.indexPath = path.join(this.xdgCacheHome, "qmd", "index.sqlite");
		this.env = {
			...process.env,
			XDG_CONFIG_HOME: this.xdgConfigHome,
			XDG_CACHE_HOME: this.xdgCacheHome,
			NO_COLOR: "1"
		};
		this.sessionExporter = this.qmd.sessions.enabled ? {
			dir: this.qmd.sessions.exportDir ?? path.join(this.qmdDir, "sessions"),
			retentionMs: this.qmd.sessions.retentionDays ? this.qmd.sessions.retentionDays * 24 * 60 * 60 * 1e3 : void 0,
			collectionName: this.pickSessionCollectionName()
		} : null;
		if (this.sessionExporter) this.qmd.collections = [...this.qmd.collections, {
			name: this.sessionExporter.collectionName,
			path: this.sessionExporter.dir,
			pattern: "**/*.md",
			kind: "sessions"
		}];
	}
	async initialize() {
		await fs.mkdir(this.xdgConfigHome, { recursive: true });
		await fs.mkdir(this.xdgCacheHome, { recursive: true });
		await fs.mkdir(path.dirname(this.indexPath), { recursive: true });
		this.bootstrapCollections();
		await this.ensureCollections();
		if (this.qmd.update.onBoot) await this.runUpdate("boot", true);
		if (this.qmd.update.intervalMs > 0) this.updateTimer = setInterval(() => {
			this.runUpdate("interval").catch((err) => {
				log.warn(`qmd update failed (${String(err)})`);
			});
		}, this.qmd.update.intervalMs);
	}
	bootstrapCollections() {
		this.collectionRoots.clear();
		this.sources.clear();
		for (const collection of this.qmd.collections) {
			const kind = collection.kind === "sessions" ? "sessions" : "memory";
			this.collectionRoots.set(collection.name, {
				path: collection.path,
				kind
			});
			this.sources.add(kind);
		}
	}
	async ensureCollections() {
		const existing = /* @__PURE__ */ new Set();
		try {
			const result = await this.runQmd([
				"collection",
				"list",
				"--json"
			]);
			const parsed = JSON.parse(result.stdout);
			if (Array.isArray(parsed)) {
				for (const entry of parsed) if (typeof entry === "string") existing.add(entry);
				else if (entry && typeof entry === "object") {
					const name = entry.name;
					if (typeof name === "string") existing.add(name);
				}
			}
		} catch {}
		for (const collection of this.qmd.collections) {
			if (existing.has(collection.name)) continue;
			try {
				await this.runQmd([
					"collection",
					"add",
					collection.path,
					"--name",
					collection.name,
					"--mask",
					collection.pattern
				]);
			} catch (err) {
				const message = err instanceof Error ? err.message : String(err);
				if (message.toLowerCase().includes("already exists")) continue;
				if (message.toLowerCase().includes("exists")) continue;
				log.warn(`qmd collection add failed for ${collection.name}: ${message}`);
			}
		}
	}
	async search(query, opts) {
		if (!this.isScopeAllowed(opts?.sessionKey)) return [];
		const trimmed = query.trim();
		if (!trimmed) return [];
		await this.pendingUpdate?.catch(() => void 0);
		const limit = Math.min(this.qmd.limits.maxResults, opts?.maxResults ?? this.qmd.limits.maxResults);
		const args = [
			"query",
			trimmed,
			"--json",
			"-n",
			String(limit)
		];
		let stdout;
		try {
			stdout = (await this.runQmd(args, { timeoutMs: this.qmd.limits.timeoutMs })).stdout;
		} catch (err) {
			log.warn(`qmd query failed: ${String(err)}`);
			throw err instanceof Error ? err : new Error(String(err));
		}
		let parsed = [];
		try {
			parsed = JSON.parse(stdout);
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			log.warn(`qmd query returned invalid JSON: ${message}`);
			throw new Error(`qmd query returned invalid JSON: ${message}`, { cause: err });
		}
		const results = [];
		for (const entry of parsed) {
			const doc = await this.resolveDocLocation(entry.docid);
			if (!doc) continue;
			const snippet = entry.snippet?.slice(0, this.qmd.limits.maxSnippetChars) ?? "";
			const lines = this.extractSnippetLines(snippet);
			const score = typeof entry.score === "number" ? entry.score : 0;
			if (score < (opts?.minScore ?? 0)) continue;
			results.push({
				path: doc.rel,
				startLine: lines.startLine,
				endLine: lines.endLine,
				score,
				snippet,
				source: doc.source
			});
		}
		return this.clampResultsByInjectedChars(results.slice(0, limit));
	}
	async sync(params) {
		if (params?.progress) params.progress({
			completed: 0,
			total: 1,
			label: "Updating QMD index…"
		});
		await this.runUpdate(params?.reason ?? "manual", params?.force);
		if (params?.progress) params.progress({
			completed: 1,
			total: 1,
			label: "QMD index updated"
		});
	}
	async readFile(params) {
		const relPath = params.relPath?.trim();
		if (!relPath) throw new Error("path required");
		const absPath = this.resolveReadPath(relPath);
		if (!absPath.endsWith(".md")) throw new Error("path required");
		const stat = await fs.lstat(absPath);
		if (stat.isSymbolicLink() || !stat.isFile()) throw new Error("path required");
		const content = await fs.readFile(absPath, "utf-8");
		if (!params.from && !params.lines) return {
			text: content,
			path: relPath
		};
		const lines = content.split("\n");
		const start = Math.max(1, params.from ?? 1);
		const count = Math.max(1, params.lines ?? lines.length);
		return {
			text: lines.slice(start - 1, start - 1 + count).join("\n"),
			path: relPath
		};
	}
	status() {
		const counts = this.readCounts();
		return {
			backend: "qmd",
			provider: "qmd",
			model: "qmd",
			requestedProvider: "qmd",
			files: counts.totalDocuments,
			chunks: counts.totalDocuments,
			dirty: false,
			workspaceDir: this.workspaceDir,
			dbPath: this.indexPath,
			sources: Array.from(this.sources),
			sourceCounts: counts.sourceCounts,
			vector: {
				enabled: true,
				available: true
			},
			batch: {
				enabled: false,
				failures: 0,
				limit: 0,
				wait: false,
				concurrency: 0,
				pollIntervalMs: 0,
				timeoutMs: 0
			},
			custom: { qmd: {
				collections: this.qmd.collections.length,
				lastUpdateAt: this.lastUpdateAt
			} }
		};
	}
	async probeEmbeddingAvailability() {
		return { ok: true };
	}
	async probeVectorAvailability() {
		return true;
	}
	async close() {
		if (this.closed) return;
		this.closed = true;
		if (this.updateTimer) {
			clearInterval(this.updateTimer);
			this.updateTimer = null;
		}
		await this.pendingUpdate?.catch(() => void 0);
		if (this.db) {
			this.db.close();
			this.db = null;
		}
	}
	async runUpdate(reason, force) {
		if (this.pendingUpdate && !force) return this.pendingUpdate;
		if (this.shouldSkipUpdate(force)) return;
		const run = async () => {
			if (this.sessionExporter) await this.exportSessions();
			await this.runQmd(["update"], { timeoutMs: 12e4 });
			const embedIntervalMs = this.qmd.update.embedIntervalMs;
			if (Boolean(force) || this.lastEmbedAt === null || embedIntervalMs > 0 && Date.now() - this.lastEmbedAt > embedIntervalMs) try {
				await this.runQmd(["embed"], { timeoutMs: 12e4 });
				this.lastEmbedAt = Date.now();
			} catch (err) {
				log.warn(`qmd embed failed (${reason}): ${String(err)}`);
			}
			this.lastUpdateAt = Date.now();
			this.docPathCache.clear();
		};
		this.pendingUpdate = run().finally(() => {
			this.pendingUpdate = null;
		});
		await this.pendingUpdate;
	}
	async runQmd(args, opts) {
		return await new Promise((resolve, reject) => {
			const child = spawn(this.qmd.command, args, {
				env: this.env,
				cwd: this.workspaceDir
			});
			let stdout = "";
			let stderr = "";
			const timer = opts?.timeoutMs ? setTimeout(() => {
				child.kill("SIGKILL");
				reject(/* @__PURE__ */ new Error(`qmd ${args.join(" ")} timed out after ${opts.timeoutMs}ms`));
			}, opts.timeoutMs) : null;
			child.stdout.on("data", (data) => {
				stdout += data.toString();
			});
			child.stderr.on("data", (data) => {
				stderr += data.toString();
			});
			child.on("error", (err) => {
				if (timer) clearTimeout(timer);
				reject(err);
			});
			child.on("close", (code) => {
				if (timer) clearTimeout(timer);
				if (code === 0) resolve({
					stdout,
					stderr
				});
				else reject(/* @__PURE__ */ new Error(`qmd ${args.join(" ")} failed (code ${code}): ${stderr || stdout}`));
			});
		});
	}
	ensureDb() {
		if (this.db) return this.db;
		const { DatabaseSync } = requireNodeSqlite();
		this.db = new DatabaseSync(this.indexPath, { readOnly: true });
		return this.db;
	}
	async exportSessions() {
		if (!this.sessionExporter) return;
		const exportDir = this.sessionExporter.dir;
		await fs.mkdir(exportDir, { recursive: true });
		const files = await listSessionFilesForAgent(this.agentId);
		const keep = /* @__PURE__ */ new Set();
		const cutoff = this.sessionExporter.retentionMs ? Date.now() - this.sessionExporter.retentionMs : null;
		for (const sessionFile of files) {
			const entry = await buildSessionEntry(sessionFile);
			if (!entry) continue;
			if (cutoff && entry.mtimeMs < cutoff) continue;
			const target = path.join(exportDir, `${path.basename(sessionFile, ".jsonl")}.md`);
			await fs.writeFile(target, this.renderSessionMarkdown(entry), "utf-8");
			keep.add(target);
		}
		const exported = await fs.readdir(exportDir).catch(() => []);
		for (const name of exported) {
			if (!name.endsWith(".md")) continue;
			const full = path.join(exportDir, name);
			if (!keep.has(full)) await fs.rm(full, { force: true });
		}
	}
	renderSessionMarkdown(entry) {
		return `${`# Session ${path.basename(entry.absPath, path.extname(entry.absPath))}`}\n\n${entry.content?.trim().length ? entry.content.trim() : "(empty)"}\n`;
	}
	pickSessionCollectionName() {
		const existing = new Set(this.qmd.collections.map((collection) => collection.name));
		if (!existing.has("sessions")) return "sessions";
		let counter = 2;
		let candidate = `sessions-${counter}`;
		while (existing.has(candidate)) {
			counter += 1;
			candidate = `sessions-${counter}`;
		}
		return candidate;
	}
	async resolveDocLocation(docid) {
		if (!docid) return null;
		const normalized = docid.startsWith("#") ? docid.slice(1) : docid;
		if (!normalized) return null;
		const cached = this.docPathCache.get(normalized);
		if (cached) return cached;
		const row = this.ensureDb().prepare("SELECT collection, path FROM documents WHERE hash LIKE ? AND active = 1 LIMIT 1").get(`${normalized}%`);
		if (!row) return null;
		const location = this.toDocLocation(row.collection, row.path);
		if (!location) return null;
		this.docPathCache.set(normalized, location);
		return location;
	}
	extractSnippetLines(snippet) {
		const match = SNIPPET_HEADER_RE.exec(snippet);
		if (match) {
			const start = Number(match[1]);
			const count = Number(match[2]);
			if (Number.isFinite(start) && Number.isFinite(count)) return {
				startLine: start,
				endLine: start + count - 1
			};
		}
		return {
			startLine: 1,
			endLine: snippet.split("\n").length
		};
	}
	readCounts() {
		try {
			const rows = this.ensureDb().prepare("SELECT collection, COUNT(*) as c FROM documents WHERE active = 1 GROUP BY collection").all();
			const bySource = /* @__PURE__ */ new Map();
			for (const source of this.sources) bySource.set(source, {
				files: 0,
				chunks: 0
			});
			let total = 0;
			for (const row of rows) {
				const source = this.collectionRoots.get(row.collection)?.kind ?? "memory";
				const entry = bySource.get(source) ?? {
					files: 0,
					chunks: 0
				};
				entry.files += row.c ?? 0;
				entry.chunks += row.c ?? 0;
				bySource.set(source, entry);
				total += row.c ?? 0;
			}
			return {
				totalDocuments: total,
				sourceCounts: Array.from(bySource.entries()).map(([source, value]) => ({
					source,
					files: value.files,
					chunks: value.chunks
				}))
			};
		} catch (err) {
			log.warn(`failed to read qmd index stats: ${String(err)}`);
			return {
				totalDocuments: 0,
				sourceCounts: Array.from(this.sources).map((source) => ({
					source,
					files: 0,
					chunks: 0
				}))
			};
		}
	}
	isScopeAllowed(sessionKey) {
		const scope = this.qmd.scope;
		if (!scope) return true;
		const channel = this.deriveChannelFromKey(sessionKey);
		const chatType = this.deriveChatTypeFromKey(sessionKey);
		const normalizedKey = sessionKey ?? "";
		for (const rule of scope.rules ?? []) {
			if (!rule) continue;
			const match = rule.match ?? {};
			if (match.channel && match.channel !== channel) continue;
			if (match.chatType && match.chatType !== chatType) continue;
			if (match.keyPrefix && !normalizedKey.startsWith(match.keyPrefix)) continue;
			return rule.action === "allow";
		}
		return (scope.default ?? "allow") === "allow";
	}
	deriveChannelFromKey(key) {
		if (!key) return;
		const normalized = this.normalizeSessionKey(key);
		if (!normalized) return;
		const parts = normalized.split(":").filter(Boolean);
		if (parts.length >= 2 && (parts[1] === "group" || parts[1] === "channel" || parts[1] === "dm")) return parts[0]?.toLowerCase();
	}
	deriveChatTypeFromKey(key) {
		if (!key) return;
		const normalized = this.normalizeSessionKey(key);
		if (!normalized) return;
		if (normalized.includes(":group:")) return "group";
		if (normalized.includes(":channel:")) return "channel";
		return "direct";
	}
	normalizeSessionKey(key) {
		const trimmed = key.trim();
		if (!trimmed) return;
		const normalized = (parseAgentSessionKey(trimmed)?.rest ?? trimmed).toLowerCase();
		if (normalized.startsWith("subagent:")) return;
		return normalized;
	}
	toDocLocation(collection, collectionRelativePath) {
		const root = this.collectionRoots.get(collection);
		if (!root) return null;
		const normalizedRelative = collectionRelativePath.replace(/\\/g, "/");
		const absPath = path.normalize(path.resolve(root.path, collectionRelativePath));
		const relativeToWorkspace = path.relative(this.workspaceDir, absPath);
		return {
			rel: this.buildSearchPath(collection, normalizedRelative, relativeToWorkspace, absPath),
			abs: absPath,
			source: root.kind
		};
	}
	buildSearchPath(collection, collectionRelativePath, relativeToWorkspace, absPath) {
		if (this.isInsideWorkspace(relativeToWorkspace)) {
			const normalized = relativeToWorkspace.replace(/\\/g, "/");
			if (!normalized) return path.basename(absPath);
			return normalized;
		}
		return `qmd/${collection}/${collectionRelativePath.replace(/^\/+/, "")}`;
	}
	isInsideWorkspace(relativePath) {
		if (!relativePath) return true;
		if (relativePath.startsWith("..")) return false;
		if (relativePath.startsWith(`..${path.sep}`)) return false;
		return !path.isAbsolute(relativePath);
	}
	resolveReadPath(relPath) {
		if (relPath.startsWith("qmd/")) {
			const [, collection, ...rest] = relPath.split("/");
			if (!collection || rest.length === 0) throw new Error("invalid qmd path");
			const root = this.collectionRoots.get(collection);
			if (!root) throw new Error(`unknown qmd collection: ${collection}`);
			const joined = rest.join("/");
			const resolved = path.resolve(root.path, joined);
			if (!this.isWithinRoot(root.path, resolved)) throw new Error("qmd path escapes collection");
			return resolved;
		}
		const absPath = path.resolve(this.workspaceDir, relPath);
		if (!this.isWithinWorkspace(absPath)) throw new Error("path escapes workspace");
		return absPath;
	}
	isWithinWorkspace(absPath) {
		const normalizedWorkspace = this.workspaceDir.endsWith(path.sep) ? this.workspaceDir : `${this.workspaceDir}${path.sep}`;
		if (absPath === this.workspaceDir) return true;
		return (absPath.endsWith(path.sep) ? absPath : `${absPath}${path.sep}`).startsWith(normalizedWorkspace);
	}
	isWithinRoot(root, candidate) {
		const normalizedRoot = root.endsWith(path.sep) ? root : `${root}${path.sep}`;
		if (candidate === root) return true;
		return (candidate.endsWith(path.sep) ? candidate : `${candidate}${path.sep}`).startsWith(normalizedRoot);
	}
	clampResultsByInjectedChars(results) {
		const budget = this.qmd.limits.maxInjectedChars;
		if (!budget || budget <= 0) return results;
		let remaining = budget;
		const clamped = [];
		for (const entry of results) {
			if (remaining <= 0) break;
			const snippet = entry.snippet ?? "";
			if (snippet.length <= remaining) {
				clamped.push(entry);
				remaining -= snippet.length;
			} else {
				const trimmed = snippet.slice(0, Math.max(0, remaining));
				clamped.push({
					...entry,
					snippet: trimmed
				});
				break;
			}
		}
		return clamped;
	}
	shouldSkipUpdate(force) {
		if (force) return false;
		const debounceMs = this.qmd.update.debounceMs;
		if (debounceMs <= 0) return false;
		if (!this.lastUpdateAt) return false;
		return Date.now() - this.lastUpdateAt < debounceMs;
	}
};

//#endregion
export { QmdMemoryManager };