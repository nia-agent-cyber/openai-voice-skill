import { r as resolveCliName } from "./command-format-3xiXujG0.js";
import * as path$1 from "node:path";
import * as os$1 from "node:os";
import * as fs$1 from "node:fs/promises";
import { randomUUID } from "node:crypto";

//#region src/infra/node-shell.ts
function buildNodeShellCommand(command, platform) {
	if (String(platform ?? "").trim().toLowerCase().startsWith("win")) return [
		"cmd.exe",
		"/d",
		"/s",
		"/c",
		command
	];
	return [
		"/bin/sh",
		"-lc",
		command
	];
}

//#endregion
//#region src/cli/nodes-camera.ts
function asRecord$2(value) {
	return typeof value === "object" && value !== null ? value : {};
}
function asString$2(value) {
	return typeof value === "string" ? value : void 0;
}
function asNumber(value) {
	return typeof value === "number" && Number.isFinite(value) ? value : void 0;
}
function asBoolean(value) {
	return typeof value === "boolean" ? value : void 0;
}
function parseCameraSnapPayload(value) {
	const obj = asRecord$2(value);
	const format = asString$2(obj.format);
	const base64 = asString$2(obj.base64);
	const width = asNumber(obj.width);
	const height = asNumber(obj.height);
	if (!format || !base64 || width === void 0 || height === void 0) throw new Error("invalid camera.snap payload");
	return {
		format,
		base64,
		width,
		height
	};
}
function parseCameraClipPayload(value) {
	const obj = asRecord$2(value);
	const format = asString$2(obj.format);
	const base64 = asString$2(obj.base64);
	const durationMs = asNumber(obj.durationMs);
	const hasAudio = asBoolean(obj.hasAudio);
	if (!format || !base64 || durationMs === void 0 || hasAudio === void 0) throw new Error("invalid camera.clip payload");
	return {
		format,
		base64,
		durationMs,
		hasAudio
	};
}
function cameraTempPath(opts) {
	const tmpDir = opts.tmpDir ?? os$1.tmpdir();
	const id = opts.id ?? randomUUID();
	const facingPart = opts.facing ? `-${opts.facing}` : "";
	const ext = opts.ext.startsWith(".") ? opts.ext : `.${opts.ext}`;
	const cliName = resolveCliName();
	return path$1.join(tmpDir, `${cliName}-camera-${opts.kind}${facingPart}-${id}${ext}`);
}
async function writeBase64ToFile(filePath, base64) {
	const buf = Buffer.from(base64, "base64");
	await fs$1.writeFile(filePath, buf);
	return {
		path: filePath,
		bytes: buf.length
	};
}

//#endregion
//#region src/cli/nodes-canvas.ts
function asRecord$1(value) {
	return typeof value === "object" && value !== null ? value : {};
}
function asString$1(value) {
	return typeof value === "string" ? value : void 0;
}
function parseCanvasSnapshotPayload(value) {
	const obj = asRecord$1(value);
	const format = asString$1(obj.format);
	const base64 = asString$1(obj.base64);
	if (!format || !base64) throw new Error("invalid canvas.snapshot payload");
	return {
		format,
		base64
	};
}
function canvasSnapshotTempPath(opts) {
	const tmpDir = opts.tmpDir ?? os$1.tmpdir();
	const id = opts.id ?? randomUUID();
	const ext = opts.ext.startsWith(".") ? opts.ext : `.${opts.ext}`;
	const cliName = resolveCliName();
	return path$1.join(tmpDir, `${cliName}-canvas-snapshot-${id}${ext}`);
}

//#endregion
//#region src/cli/nodes-run.ts
function parseEnvPairs(pairs) {
	if (!Array.isArray(pairs) || pairs.length === 0) return;
	const env = {};
	for (const pair of pairs) {
		if (typeof pair !== "string") continue;
		const idx = pair.indexOf("=");
		if (idx <= 0) continue;
		const key = pair.slice(0, idx).trim();
		if (!key) continue;
		env[key] = pair.slice(idx + 1);
	}
	return Object.keys(env).length > 0 ? env : void 0;
}

//#endregion
//#region src/cli/nodes-screen.ts
function asRecord(value) {
	return typeof value === "object" && value !== null ? value : {};
}
function asString(value) {
	return typeof value === "string" ? value : void 0;
}
function parseScreenRecordPayload(value) {
	const obj = asRecord(value);
	const format = asString(obj.format);
	const base64 = asString(obj.base64);
	if (!format || !base64) throw new Error("invalid screen.record payload");
	return {
		format,
		base64,
		durationMs: typeof obj.durationMs === "number" ? obj.durationMs : void 0,
		fps: typeof obj.fps === "number" ? obj.fps : void 0,
		screenIndex: typeof obj.screenIndex === "number" ? obj.screenIndex : void 0,
		hasAudio: typeof obj.hasAudio === "boolean" ? obj.hasAudio : void 0
	};
}
function screenRecordTempPath(opts) {
	const tmpDir = opts.tmpDir ?? os$1.tmpdir();
	const id = opts.id ?? randomUUID();
	const ext = opts.ext.startsWith(".") ? opts.ext : `.${opts.ext}`;
	return path$1.join(tmpDir, `openclaw-screen-record-${id}${ext}`);
}
async function writeScreenRecordToFile(filePath, base64) {
	return writeBase64ToFile(filePath, base64);
}

//#endregion
export { canvasSnapshotTempPath as a, parseCameraClipPayload as c, buildNodeShellCommand as d, parseEnvPairs as i, parseCameraSnapPayload as l, screenRecordTempPath as n, parseCanvasSnapshotPayload as o, writeScreenRecordToFile as r, cameraTempPath as s, parseScreenRecordPayload as t, writeBase64ToFile as u };