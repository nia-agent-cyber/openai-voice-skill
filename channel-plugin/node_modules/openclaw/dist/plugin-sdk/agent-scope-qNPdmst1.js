import { t as runCommandWithTimeout, w as resolveUserPath } from "./exec-CjyVHUuE.js";
import { s as resolveStateDir } from "./paths-BFxmmTT5.js";
import os from "node:os";
import path from "node:path";
import fs from "node:fs";
import fs$1 from "node:fs/promises";
import { fileURLToPath } from "node:url";

//#region src/sessions/session-key-utils.ts
function parseAgentSessionKey(sessionKey) {
	const raw = (sessionKey ?? "").trim();
	if (!raw) return null;
	const parts = raw.split(":").filter(Boolean);
	if (parts.length < 3) return null;
	if (parts[0] !== "agent") return null;
	const agentId = parts[1]?.trim();
	const rest = parts.slice(2).join(":");
	if (!agentId || !rest) return null;
	return {
		agentId,
		rest
	};
}
function isSubagentSessionKey(sessionKey) {
	const raw = (sessionKey ?? "").trim();
	if (!raw) return false;
	if (raw.toLowerCase().startsWith("subagent:")) return true;
	const parsed = parseAgentSessionKey(raw);
	return Boolean((parsed?.rest ?? "").toLowerCase().startsWith("subagent:"));
}
function isAcpSessionKey(sessionKey) {
	const raw = (sessionKey ?? "").trim();
	if (!raw) return false;
	if (raw.toLowerCase().startsWith("acp:")) return true;
	const parsed = parseAgentSessionKey(raw);
	return Boolean((parsed?.rest ?? "").toLowerCase().startsWith("acp:"));
}
const THREAD_SESSION_MARKERS = [":thread:", ":topic:"];
function resolveThreadParentSessionKey(sessionKey) {
	const raw = (sessionKey ?? "").trim();
	if (!raw) return null;
	const normalized = raw.toLowerCase();
	let idx = -1;
	for (const marker of THREAD_SESSION_MARKERS) {
		const candidate = normalized.lastIndexOf(marker);
		if (candidate > idx) idx = candidate;
	}
	if (idx <= 0) return null;
	const parent = raw.slice(0, idx).trim();
	return parent ? parent : null;
}

//#endregion
//#region src/routing/session-key.ts
const DEFAULT_AGENT_ID = "main";
const DEFAULT_MAIN_KEY = "main";
const DEFAULT_ACCOUNT_ID = "default";
const VALID_ID_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/i;
const INVALID_CHARS_RE = /[^a-z0-9_-]+/g;
const LEADING_DASH_RE = /^-+/;
const TRAILING_DASH_RE = /-+$/;
function normalizeToken(value) {
	return (value ?? "").trim().toLowerCase();
}
function normalizeMainKey(value) {
	const trimmed = (value ?? "").trim();
	return trimmed ? trimmed.toLowerCase() : DEFAULT_MAIN_KEY;
}
function resolveAgentIdFromSessionKey(sessionKey) {
	return normalizeAgentId(parseAgentSessionKey(sessionKey)?.agentId ?? DEFAULT_AGENT_ID);
}
function normalizeAgentId(value) {
	const trimmed = (value ?? "").trim();
	if (!trimmed) return DEFAULT_AGENT_ID;
	if (VALID_ID_RE.test(trimmed)) return trimmed.toLowerCase();
	return trimmed.toLowerCase().replace(INVALID_CHARS_RE, "-").replace(LEADING_DASH_RE, "").replace(TRAILING_DASH_RE, "").slice(0, 64) || DEFAULT_AGENT_ID;
}
function sanitizeAgentId(value) {
	const trimmed = (value ?? "").trim();
	if (!trimmed) return DEFAULT_AGENT_ID;
	if (VALID_ID_RE.test(trimmed)) return trimmed.toLowerCase();
	return trimmed.toLowerCase().replace(INVALID_CHARS_RE, "-").replace(LEADING_DASH_RE, "").replace(TRAILING_DASH_RE, "").slice(0, 64) || DEFAULT_AGENT_ID;
}
function normalizeAccountId(value) {
	const trimmed = (value ?? "").trim();
	if (!trimmed) return DEFAULT_ACCOUNT_ID;
	if (VALID_ID_RE.test(trimmed)) return trimmed.toLowerCase();
	return trimmed.toLowerCase().replace(INVALID_CHARS_RE, "-").replace(LEADING_DASH_RE, "").replace(TRAILING_DASH_RE, "").slice(0, 64) || DEFAULT_ACCOUNT_ID;
}
function buildAgentMainSessionKey(params) {
	return `agent:${normalizeAgentId(params.agentId)}:${normalizeMainKey(params.mainKey)}`;
}
function buildAgentPeerSessionKey(params) {
	const peerKind = params.peerKind ?? "dm";
	if (peerKind === "dm") {
		const dmScope = params.dmScope ?? "main";
		let peerId = (params.peerId ?? "").trim();
		const linkedPeerId = dmScope === "main" ? null : resolveLinkedPeerId({
			identityLinks: params.identityLinks,
			channel: params.channel,
			peerId
		});
		if (linkedPeerId) peerId = linkedPeerId;
		peerId = peerId.toLowerCase();
		if (dmScope === "per-account-channel-peer" && peerId) {
			const channel = (params.channel ?? "").trim().toLowerCase() || "unknown";
			const accountId = normalizeAccountId(params.accountId);
			return `agent:${normalizeAgentId(params.agentId)}:${channel}:${accountId}:dm:${peerId}`;
		}
		if (dmScope === "per-channel-peer" && peerId) {
			const channel = (params.channel ?? "").trim().toLowerCase() || "unknown";
			return `agent:${normalizeAgentId(params.agentId)}:${channel}:dm:${peerId}`;
		}
		if (dmScope === "per-peer" && peerId) return `agent:${normalizeAgentId(params.agentId)}:dm:${peerId}`;
		return buildAgentMainSessionKey({
			agentId: params.agentId,
			mainKey: params.mainKey
		});
	}
	const channel = (params.channel ?? "").trim().toLowerCase() || "unknown";
	const peerId = ((params.peerId ?? "").trim() || "unknown").toLowerCase();
	return `agent:${normalizeAgentId(params.agentId)}:${channel}:${peerKind}:${peerId}`;
}
function resolveLinkedPeerId(params) {
	const identityLinks = params.identityLinks;
	if (!identityLinks) return null;
	const peerId = params.peerId.trim();
	if (!peerId) return null;
	const candidates = /* @__PURE__ */ new Set();
	const rawCandidate = normalizeToken(peerId);
	if (rawCandidate) candidates.add(rawCandidate);
	const channel = normalizeToken(params.channel);
	if (channel) {
		const scopedCandidate = normalizeToken(`${channel}:${peerId}`);
		if (scopedCandidate) candidates.add(scopedCandidate);
	}
	if (candidates.size === 0) return null;
	for (const [canonical, ids] of Object.entries(identityLinks)) {
		const canonicalName = canonical.trim();
		if (!canonicalName) continue;
		if (!Array.isArray(ids)) continue;
		for (const id of ids) {
			const normalized = normalizeToken(id);
			if (normalized && candidates.has(normalized)) return canonicalName;
		}
	}
	return null;
}
function buildGroupHistoryKey(params) {
	const channel = normalizeToken(params.channel) || "unknown";
	const accountId = normalizeAccountId(params.accountId);
	const peerId = params.peerId.trim().toLowerCase() || "unknown";
	return `${channel}:${accountId}:${params.peerKind}:${peerId}`;
}
function resolveThreadSessionKeys(params) {
	const threadId = (params.threadId ?? "").trim();
	if (!threadId) return {
		sessionKey: params.baseSessionKey,
		parentSessionKey: void 0
	};
	const normalizedThreadId = threadId.toLowerCase();
	return {
		sessionKey: params.useSuffix ?? true ? `${params.baseSessionKey}:thread:${normalizedThreadId}` : params.baseSessionKey,
		parentSessionKey: params.parentSessionKey
	};
}

//#endregion
//#region src/infra/openclaw-root.ts
const CORE_PACKAGE_NAMES = new Set(["openclaw"]);
async function readPackageName(dir) {
	try {
		const raw = await fs$1.readFile(path.join(dir, "package.json"), "utf-8");
		const parsed = JSON.parse(raw);
		return typeof parsed.name === "string" ? parsed.name : null;
	} catch {
		return null;
	}
}
function readPackageNameSync(dir) {
	try {
		const raw = fs.readFileSync(path.join(dir, "package.json"), "utf-8");
		const parsed = JSON.parse(raw);
		return typeof parsed.name === "string" ? parsed.name : null;
	} catch {
		return null;
	}
}
async function findPackageRoot(startDir, maxDepth = 12) {
	let current = path.resolve(startDir);
	for (let i = 0; i < maxDepth; i += 1) {
		const name = await readPackageName(current);
		if (name && CORE_PACKAGE_NAMES.has(name)) return current;
		const parent = path.dirname(current);
		if (parent === current) break;
		current = parent;
	}
	return null;
}
function findPackageRootSync(startDir, maxDepth = 12) {
	let current = path.resolve(startDir);
	for (let i = 0; i < maxDepth; i += 1) {
		const name = readPackageNameSync(current);
		if (name && CORE_PACKAGE_NAMES.has(name)) return current;
		const parent = path.dirname(current);
		if (parent === current) break;
		current = parent;
	}
	return null;
}
function candidateDirsFromArgv1(argv1) {
	const normalized = path.resolve(argv1);
	const candidates = [path.dirname(normalized)];
	const parts = normalized.split(path.sep);
	const binIndex = parts.lastIndexOf(".bin");
	if (binIndex > 0 && parts[binIndex - 1] === "node_modules") {
		const binName = path.basename(normalized);
		const nodeModulesDir = parts.slice(0, binIndex).join(path.sep);
		candidates.push(path.join(nodeModulesDir, binName));
	}
	return candidates;
}
async function resolveOpenClawPackageRoot(opts) {
	const candidates = [];
	if (opts.moduleUrl) candidates.push(path.dirname(fileURLToPath(opts.moduleUrl)));
	if (opts.argv1) candidates.push(...candidateDirsFromArgv1(opts.argv1));
	if (opts.cwd) candidates.push(opts.cwd);
	for (const candidate of candidates) {
		const found = await findPackageRoot(candidate);
		if (found) return found;
	}
	return null;
}
function resolveOpenClawPackageRootSync(opts) {
	const candidates = [];
	if (opts.moduleUrl) candidates.push(path.dirname(fileURLToPath(opts.moduleUrl)));
	if (opts.argv1) candidates.push(...candidateDirsFromArgv1(opts.argv1));
	if (opts.cwd) candidates.push(opts.cwd);
	for (const candidate of candidates) {
		const found = findPackageRootSync(candidate);
		if (found) return found;
	}
	return null;
}

//#endregion
//#region src/agents/workspace-templates.ts
const FALLBACK_TEMPLATE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../docs/reference/templates");
let cachedTemplateDir;
let resolvingTemplateDir;
async function pathExists(candidate) {
	try {
		await fs$1.access(candidate);
		return true;
	} catch {
		return false;
	}
}
async function resolveWorkspaceTemplateDir(opts) {
	if (cachedTemplateDir) return cachedTemplateDir;
	if (resolvingTemplateDir) return resolvingTemplateDir;
	resolvingTemplateDir = (async () => {
		const moduleUrl = opts?.moduleUrl ?? import.meta.url;
		const argv1 = opts?.argv1 ?? process.argv[1];
		const cwd = opts?.cwd ?? process.cwd();
		const packageRoot = await resolveOpenClawPackageRoot({
			moduleUrl,
			argv1,
			cwd
		});
		const candidates = [
			packageRoot ? path.join(packageRoot, "docs", "reference", "templates") : null,
			cwd ? path.resolve(cwd, "docs", "reference", "templates") : null,
			FALLBACK_TEMPLATE_DIR
		].filter(Boolean);
		for (const candidate of candidates) if (await pathExists(candidate)) {
			cachedTemplateDir = candidate;
			return candidate;
		}
		cachedTemplateDir = candidates[0] ?? FALLBACK_TEMPLATE_DIR;
		return cachedTemplateDir;
	})();
	try {
		return await resolvingTemplateDir;
	} finally {
		resolvingTemplateDir = void 0;
	}
}

//#endregion
//#region src/agents/workspace.ts
function resolveDefaultAgentWorkspaceDir(env = process.env, homedir = os.homedir) {
	const profile = env.OPENCLAW_PROFILE?.trim();
	if (profile && profile.toLowerCase() !== "default") return path.join(homedir(), ".openclaw", `workspace-${profile}`);
	return path.join(homedir(), ".openclaw", "workspace");
}
const DEFAULT_AGENT_WORKSPACE_DIR = resolveDefaultAgentWorkspaceDir();
const DEFAULT_AGENTS_FILENAME = "AGENTS.md";
const DEFAULT_SOUL_FILENAME = "SOUL.md";
const DEFAULT_TOOLS_FILENAME = "TOOLS.md";
const DEFAULT_IDENTITY_FILENAME = "IDENTITY.md";
const DEFAULT_USER_FILENAME = "USER.md";
const DEFAULT_HEARTBEAT_FILENAME = "HEARTBEAT.md";
const DEFAULT_BOOTSTRAP_FILENAME = "BOOTSTRAP.md";
const DEFAULT_MEMORY_FILENAME = "MEMORY.md";
const DEFAULT_MEMORY_ALT_FILENAME = "memory.md";
function stripFrontMatter(content) {
	if (!content.startsWith("---")) return content;
	const endIndex = content.indexOf("\n---", 3);
	if (endIndex === -1) return content;
	const start = endIndex + 4;
	let trimmed = content.slice(start);
	trimmed = trimmed.replace(/^\s+/, "");
	return trimmed;
}
async function loadTemplate(name) {
	const templateDir = await resolveWorkspaceTemplateDir();
	const templatePath = path.join(templateDir, name);
	try {
		return stripFrontMatter(await fs$1.readFile(templatePath, "utf-8"));
	} catch {
		throw new Error(`Missing workspace template: ${name} (${templatePath}). Ensure docs/reference/templates are packaged.`);
	}
}
async function writeFileIfMissing(filePath, content) {
	try {
		await fs$1.writeFile(filePath, content, {
			encoding: "utf-8",
			flag: "wx"
		});
	} catch (err) {
		if (err.code !== "EEXIST") throw err;
	}
}
async function hasGitRepo(dir) {
	try {
		await fs$1.stat(path.join(dir, ".git"));
		return true;
	} catch {
		return false;
	}
}
async function isGitAvailable() {
	try {
		return (await runCommandWithTimeout(["git", "--version"], { timeoutMs: 2e3 })).code === 0;
	} catch {
		return false;
	}
}
async function ensureGitRepo(dir, isBrandNewWorkspace) {
	if (!isBrandNewWorkspace) return;
	if (await hasGitRepo(dir)) return;
	if (!await isGitAvailable()) return;
	try {
		await runCommandWithTimeout(["git", "init"], {
			cwd: dir,
			timeoutMs: 1e4
		});
	} catch {}
}
async function ensureAgentWorkspace(params) {
	const dir = resolveUserPath(params?.dir?.trim() ? params.dir.trim() : DEFAULT_AGENT_WORKSPACE_DIR);
	await fs$1.mkdir(dir, { recursive: true });
	if (!params?.ensureBootstrapFiles) return { dir };
	const agentsPath = path.join(dir, DEFAULT_AGENTS_FILENAME);
	const soulPath = path.join(dir, DEFAULT_SOUL_FILENAME);
	const toolsPath = path.join(dir, DEFAULT_TOOLS_FILENAME);
	const identityPath = path.join(dir, DEFAULT_IDENTITY_FILENAME);
	const userPath = path.join(dir, DEFAULT_USER_FILENAME);
	const heartbeatPath = path.join(dir, DEFAULT_HEARTBEAT_FILENAME);
	const bootstrapPath = path.join(dir, DEFAULT_BOOTSTRAP_FILENAME);
	const isBrandNewWorkspace = await (async () => {
		const paths = [
			agentsPath,
			soulPath,
			toolsPath,
			identityPath,
			userPath,
			heartbeatPath
		];
		return (await Promise.all(paths.map(async (p) => {
			try {
				await fs$1.access(p);
				return true;
			} catch {
				return false;
			}
		}))).every((v) => !v);
	})();
	const agentsTemplate = await loadTemplate(DEFAULT_AGENTS_FILENAME);
	const soulTemplate = await loadTemplate(DEFAULT_SOUL_FILENAME);
	const toolsTemplate = await loadTemplate(DEFAULT_TOOLS_FILENAME);
	const identityTemplate = await loadTemplate(DEFAULT_IDENTITY_FILENAME);
	const userTemplate = await loadTemplate(DEFAULT_USER_FILENAME);
	const heartbeatTemplate = await loadTemplate(DEFAULT_HEARTBEAT_FILENAME);
	const bootstrapTemplate = await loadTemplate(DEFAULT_BOOTSTRAP_FILENAME);
	await writeFileIfMissing(agentsPath, agentsTemplate);
	await writeFileIfMissing(soulPath, soulTemplate);
	await writeFileIfMissing(toolsPath, toolsTemplate);
	await writeFileIfMissing(identityPath, identityTemplate);
	await writeFileIfMissing(userPath, userTemplate);
	await writeFileIfMissing(heartbeatPath, heartbeatTemplate);
	if (isBrandNewWorkspace) await writeFileIfMissing(bootstrapPath, bootstrapTemplate);
	await ensureGitRepo(dir, isBrandNewWorkspace);
	return {
		dir,
		agentsPath,
		soulPath,
		toolsPath,
		identityPath,
		userPath,
		heartbeatPath,
		bootstrapPath
	};
}
async function resolveMemoryBootstrapEntries(resolvedDir) {
	const candidates = [DEFAULT_MEMORY_FILENAME, DEFAULT_MEMORY_ALT_FILENAME];
	const entries = [];
	for (const name of candidates) {
		const filePath = path.join(resolvedDir, name);
		try {
			await fs$1.access(filePath);
			entries.push({
				name,
				filePath
			});
		} catch {}
	}
	if (entries.length <= 1) return entries;
	const seen = /* @__PURE__ */ new Set();
	const deduped = [];
	for (const entry of entries) {
		let key = entry.filePath;
		try {
			key = await fs$1.realpath(entry.filePath);
		} catch {}
		if (seen.has(key)) continue;
		seen.add(key);
		deduped.push(entry);
	}
	return deduped;
}
async function loadWorkspaceBootstrapFiles(dir) {
	const resolvedDir = resolveUserPath(dir);
	const entries = [
		{
			name: DEFAULT_AGENTS_FILENAME,
			filePath: path.join(resolvedDir, DEFAULT_AGENTS_FILENAME)
		},
		{
			name: DEFAULT_SOUL_FILENAME,
			filePath: path.join(resolvedDir, DEFAULT_SOUL_FILENAME)
		},
		{
			name: DEFAULT_TOOLS_FILENAME,
			filePath: path.join(resolvedDir, DEFAULT_TOOLS_FILENAME)
		},
		{
			name: DEFAULT_IDENTITY_FILENAME,
			filePath: path.join(resolvedDir, DEFAULT_IDENTITY_FILENAME)
		},
		{
			name: DEFAULT_USER_FILENAME,
			filePath: path.join(resolvedDir, DEFAULT_USER_FILENAME)
		},
		{
			name: DEFAULT_HEARTBEAT_FILENAME,
			filePath: path.join(resolvedDir, DEFAULT_HEARTBEAT_FILENAME)
		},
		{
			name: DEFAULT_BOOTSTRAP_FILENAME,
			filePath: path.join(resolvedDir, DEFAULT_BOOTSTRAP_FILENAME)
		}
	];
	entries.push(...await resolveMemoryBootstrapEntries(resolvedDir));
	const result = [];
	for (const entry of entries) try {
		const content = await fs$1.readFile(entry.filePath, "utf-8");
		result.push({
			name: entry.name,
			path: entry.filePath,
			content,
			missing: false
		});
	} catch {
		result.push({
			name: entry.name,
			path: entry.filePath,
			missing: true
		});
	}
	return result;
}
const SUBAGENT_BOOTSTRAP_ALLOWLIST = new Set([DEFAULT_AGENTS_FILENAME, DEFAULT_TOOLS_FILENAME]);
function filterBootstrapFilesForSession(files, sessionKey) {
	if (!sessionKey || !isSubagentSessionKey(sessionKey)) return files;
	return files.filter((file) => SUBAGENT_BOOTSTRAP_ALLOWLIST.has(file.name));
}

//#endregion
//#region src/agents/agent-scope.ts
let defaultAgentWarned = false;
function listAgents(cfg) {
	const list = cfg.agents?.list;
	if (!Array.isArray(list)) return [];
	return list.filter((entry) => Boolean(entry && typeof entry === "object"));
}
function listAgentIds(cfg) {
	const agents = listAgents(cfg);
	if (agents.length === 0) return [DEFAULT_AGENT_ID];
	const seen = /* @__PURE__ */ new Set();
	const ids = [];
	for (const entry of agents) {
		const id = normalizeAgentId(entry?.id);
		if (seen.has(id)) continue;
		seen.add(id);
		ids.push(id);
	}
	return ids.length > 0 ? ids : [DEFAULT_AGENT_ID];
}
function resolveDefaultAgentId(cfg) {
	const agents = listAgents(cfg);
	if (agents.length === 0) return DEFAULT_AGENT_ID;
	const defaults = agents.filter((agent) => agent?.default);
	if (defaults.length > 1 && !defaultAgentWarned) {
		defaultAgentWarned = true;
		console.warn("Multiple agents marked default=true; using the first entry as default.");
	}
	const chosen = (defaults[0] ?? agents[0])?.id?.trim();
	return normalizeAgentId(chosen || DEFAULT_AGENT_ID);
}
function resolveSessionAgentIds(params) {
	const defaultAgentId = resolveDefaultAgentId(params.config ?? {});
	const sessionKey = params.sessionKey?.trim();
	const normalizedSessionKey = sessionKey ? sessionKey.toLowerCase() : void 0;
	const parsed = normalizedSessionKey ? parseAgentSessionKey(normalizedSessionKey) : null;
	return {
		defaultAgentId,
		sessionAgentId: parsed?.agentId ? normalizeAgentId(parsed.agentId) : defaultAgentId
	};
}
function resolveSessionAgentId(params) {
	return resolveSessionAgentIds(params).sessionAgentId;
}
function resolveAgentEntry(cfg, agentId) {
	const id = normalizeAgentId(agentId);
	return listAgents(cfg).find((entry) => normalizeAgentId(entry.id) === id);
}
function resolveAgentConfig(cfg, agentId) {
	const entry = resolveAgentEntry(cfg, normalizeAgentId(agentId));
	if (!entry) return;
	return {
		name: typeof entry.name === "string" ? entry.name : void 0,
		workspace: typeof entry.workspace === "string" ? entry.workspace : void 0,
		agentDir: typeof entry.agentDir === "string" ? entry.agentDir : void 0,
		model: typeof entry.model === "string" || entry.model && typeof entry.model === "object" ? entry.model : void 0,
		skills: Array.isArray(entry.skills) ? entry.skills : void 0,
		memorySearch: entry.memorySearch,
		humanDelay: entry.humanDelay,
		heartbeat: entry.heartbeat,
		identity: entry.identity,
		groupChat: entry.groupChat,
		subagents: typeof entry.subagents === "object" && entry.subagents ? entry.subagents : void 0,
		sandbox: entry.sandbox,
		tools: entry.tools
	};
}
function resolveAgentSkillsFilter(cfg, agentId) {
	const raw = resolveAgentConfig(cfg, agentId)?.skills;
	if (!raw) return;
	const normalized = raw.map((entry) => String(entry).trim()).filter(Boolean);
	return normalized.length > 0 ? normalized : [];
}
function resolveAgentModelPrimary(cfg, agentId) {
	const raw = resolveAgentConfig(cfg, agentId)?.model;
	if (!raw) return;
	if (typeof raw === "string") return raw.trim() || void 0;
	return raw.primary?.trim() || void 0;
}
function resolveAgentModelFallbacksOverride(cfg, agentId) {
	const raw = resolveAgentConfig(cfg, agentId)?.model;
	if (!raw || typeof raw === "string") return;
	if (!Object.hasOwn(raw, "fallbacks")) return;
	return Array.isArray(raw.fallbacks) ? raw.fallbacks : void 0;
}
function resolveAgentWorkspaceDir(cfg, agentId) {
	const id = normalizeAgentId(agentId);
	const configured = resolveAgentConfig(cfg, id)?.workspace?.trim();
	if (configured) return resolveUserPath(configured);
	if (id === resolveDefaultAgentId(cfg)) {
		const fallback = cfg.agents?.defaults?.workspace?.trim();
		if (fallback) return resolveUserPath(fallback);
		return DEFAULT_AGENT_WORKSPACE_DIR;
	}
	return path.join(os.homedir(), ".openclaw", `workspace-${id}`);
}
function resolveAgentDir(cfg, agentId) {
	const id = normalizeAgentId(agentId);
	const configured = resolveAgentConfig(cfg, id)?.agentDir?.trim();
	if (configured) return resolveUserPath(configured);
	const root = resolveStateDir(process.env, os.homedir);
	return path.join(root, "agents", id, "agent");
}

//#endregion
export { normalizeAccountId as A, resolveOpenClawPackageRootSync as C, buildAgentMainSessionKey as D, DEFAULT_MAIN_KEY as E, sanitizeAgentId as F, isAcpSessionKey as I, isSubagentSessionKey as L, normalizeMainKey as M, resolveAgentIdFromSessionKey as N, buildAgentPeerSessionKey as O, resolveThreadSessionKeys as P, parseAgentSessionKey as R, resolveOpenClawPackageRoot as S, DEFAULT_AGENT_ID as T, DEFAULT_TOOLS_FILENAME as _, resolveAgentModelPrimary as a, filterBootstrapFilesForSession as b, resolveDefaultAgentId as c, DEFAULT_AGENTS_FILENAME as d, DEFAULT_AGENT_WORKSPACE_DIR as f, DEFAULT_SOUL_FILENAME as g, DEFAULT_IDENTITY_FILENAME as h, resolveAgentModelFallbacksOverride as i, normalizeAgentId as j, buildGroupHistoryKey as k, resolveSessionAgentId as l, DEFAULT_HEARTBEAT_FILENAME as m, resolveAgentConfig as n, resolveAgentSkillsFilter as o, DEFAULT_BOOTSTRAP_FILENAME as p, resolveAgentDir as r, resolveAgentWorkspaceDir as s, listAgentIds as t, resolveSessionAgentIds as u, DEFAULT_USER_FILENAME as v, DEFAULT_ACCOUNT_ID as w, loadWorkspaceBootstrapFiles as x, ensureAgentWorkspace as y, resolveThreadParentSessionKey as z };