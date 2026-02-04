import os from "node:os";
import path from "node:path";
import fs from "node:fs";

//#region src/config/paths.ts
/**
* Nix mode detection: When OPENCLAW_NIX_MODE=1, the gateway is running under Nix.
* In this mode:
* - No auto-install flows should be attempted
* - Missing dependencies should produce actionable Nix-specific error messages
* - Config is managed externally (read-only from Nix perspective)
*/
function resolveIsNixMode(env = process.env) {
	return env.OPENCLAW_NIX_MODE === "1";
}
const isNixMode = resolveIsNixMode();
const LEGACY_STATE_DIRNAMES = [
	".clawdbot",
	".moltbot",
	".moldbot"
];
const NEW_STATE_DIRNAME = ".openclaw";
const CONFIG_FILENAME = "openclaw.json";
const LEGACY_CONFIG_FILENAMES = [
	"clawdbot.json",
	"moltbot.json",
	"moldbot.json"
];
function legacyStateDirs(homedir = os.homedir) {
	return LEGACY_STATE_DIRNAMES.map((dir) => path.join(homedir(), dir));
}
function newStateDir(homedir = os.homedir) {
	return path.join(homedir(), NEW_STATE_DIRNAME);
}
/**
* State directory for mutable data (sessions, logs, caches).
* Can be overridden via OPENCLAW_STATE_DIR.
* Default: ~/.openclaw
*/
function resolveStateDir(env = process.env, homedir = os.homedir) {
	const override = env.OPENCLAW_STATE_DIR?.trim() || env.CLAWDBOT_STATE_DIR?.trim();
	if (override) return resolveUserPath(override);
	const newDir = newStateDir(homedir);
	const legacyDirs = legacyStateDirs(homedir);
	if (fs.existsSync(newDir)) return newDir;
	const existingLegacy = legacyDirs.find((dir) => {
		try {
			return fs.existsSync(dir);
		} catch {
			return false;
		}
	});
	if (existingLegacy) return existingLegacy;
	return newDir;
}
function resolveUserPath(input) {
	const trimmed = input.trim();
	if (!trimmed) return trimmed;
	if (trimmed.startsWith("~")) {
		const expanded = trimmed.replace(/^~(?=$|[\\/])/, os.homedir());
		return path.resolve(expanded);
	}
	return path.resolve(trimmed);
}
const STATE_DIR = resolveStateDir();
/**
* Config file path (JSON5).
* Can be overridden via OPENCLAW_CONFIG_PATH.
* Default: ~/.openclaw/openclaw.json (or $OPENCLAW_STATE_DIR/openclaw.json)
*/
function resolveCanonicalConfigPath(env = process.env, stateDir = resolveStateDir(env, os.homedir)) {
	const override = env.OPENCLAW_CONFIG_PATH?.trim() || env.CLAWDBOT_CONFIG_PATH?.trim();
	if (override) return resolveUserPath(override);
	return path.join(stateDir, CONFIG_FILENAME);
}
/**
* Resolve the active config path by preferring existing config candidates
* before falling back to the canonical path.
*/
function resolveConfigPathCandidate(env = process.env, homedir = os.homedir) {
	const existing = resolveDefaultConfigCandidates(env, homedir).find((candidate) => {
		try {
			return fs.existsSync(candidate);
		} catch {
			return false;
		}
	});
	if (existing) return existing;
	return resolveCanonicalConfigPath(env, resolveStateDir(env, homedir));
}
/**
* Active config path (prefers existing config files).
*/
function resolveConfigPath(env = process.env, stateDir = resolveStateDir(env, os.homedir), homedir = os.homedir) {
	const override = env.OPENCLAW_CONFIG_PATH?.trim();
	if (override) return resolveUserPath(override);
	const stateOverride = env.OPENCLAW_STATE_DIR?.trim();
	const existing = [path.join(stateDir, CONFIG_FILENAME), ...LEGACY_CONFIG_FILENAMES.map((name) => path.join(stateDir, name))].find((candidate) => {
		try {
			return fs.existsSync(candidate);
		} catch {
			return false;
		}
	});
	if (existing) return existing;
	if (stateOverride) return path.join(stateDir, CONFIG_FILENAME);
	const defaultStateDir = resolveStateDir(env, homedir);
	if (path.resolve(stateDir) === path.resolve(defaultStateDir)) return resolveConfigPathCandidate(env, homedir);
	return path.join(stateDir, CONFIG_FILENAME);
}
const CONFIG_PATH = resolveConfigPathCandidate();
/**
* Resolve default config path candidates across default locations.
* Order: explicit config path → state-dir-derived paths → new default.
*/
function resolveDefaultConfigCandidates(env = process.env, homedir = os.homedir) {
	const explicit = env.OPENCLAW_CONFIG_PATH?.trim() || env.CLAWDBOT_CONFIG_PATH?.trim();
	if (explicit) return [resolveUserPath(explicit)];
	const candidates = [];
	const openclawStateDir = env.OPENCLAW_STATE_DIR?.trim() || env.CLAWDBOT_STATE_DIR?.trim();
	if (openclawStateDir) {
		const resolved = resolveUserPath(openclawStateDir);
		candidates.push(path.join(resolved, CONFIG_FILENAME));
		candidates.push(...LEGACY_CONFIG_FILENAMES.map((name) => path.join(resolved, name)));
	}
	const defaultDirs = [newStateDir(homedir), ...legacyStateDirs(homedir)];
	for (const dir of defaultDirs) {
		candidates.push(path.join(dir, CONFIG_FILENAME));
		candidates.push(...LEGACY_CONFIG_FILENAMES.map((name) => path.join(dir, name)));
	}
	return candidates;
}
const DEFAULT_GATEWAY_PORT = 18789;
const OAUTH_FILENAME = "oauth.json";
/**
* OAuth credentials storage directory.
*
* Precedence:
* - `OPENCLAW_OAUTH_DIR` (explicit override)
* - `$*_STATE_DIR/credentials` (canonical server/default)
*/
function resolveOAuthDir(env = process.env, stateDir = resolveStateDir(env, os.homedir)) {
	const override = env.OPENCLAW_OAUTH_DIR?.trim();
	if (override) return resolveUserPath(override);
	return path.join(stateDir, "credentials");
}
function resolveOAuthPath(env = process.env, stateDir = resolveStateDir(env, os.homedir)) {
	return path.join(resolveOAuthDir(env, stateDir), OAUTH_FILENAME);
}
function resolveGatewayPort(cfg, env = process.env) {
	const envRaw = env.OPENCLAW_GATEWAY_PORT?.trim() || env.CLAWDBOT_GATEWAY_PORT?.trim();
	if (envRaw) {
		const parsed = Number.parseInt(envRaw, 10);
		if (Number.isFinite(parsed) && parsed > 0) return parsed;
	}
	const configPort = cfg?.gateway?.port;
	if (typeof configPort === "number" && Number.isFinite(configPort)) {
		if (configPort > 0) return configPort;
	}
	return DEFAULT_GATEWAY_PORT;
}

//#endregion
export { resolveOAuthDir as a, resolveGatewayPort as i, resolveConfigPath as n, resolveOAuthPath as o, resolveDefaultConfigCandidates as r, resolveStateDir as s, STATE_DIR as t };