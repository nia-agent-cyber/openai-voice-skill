import { t as installProcessWarningFilter } from "./entry.js";
import { createRequire } from "node:module";
import path from "node:path";
import fs from "node:fs";
import fs$1 from "node:fs/promises";
import crypto from "node:crypto";

//#region src/memory/internal.ts
function ensureDir(dir) {
	try {
		fs.mkdirSync(dir, { recursive: true });
	} catch {}
	return dir;
}
function normalizeRelPath(value) {
	return value.trim().replace(/^[./]+/, "").replace(/\\/g, "/");
}
function normalizeExtraMemoryPaths(workspaceDir, extraPaths) {
	if (!extraPaths?.length) return [];
	const resolved = extraPaths.map((value) => value.trim()).filter(Boolean).map((value) => path.isAbsolute(value) ? path.resolve(value) : path.resolve(workspaceDir, value));
	return Array.from(new Set(resolved));
}
function isMemoryPath(relPath) {
	const normalized = normalizeRelPath(relPath);
	if (!normalized) return false;
	if (normalized === "MEMORY.md" || normalized === "memory.md") return true;
	return normalized.startsWith("memory/");
}
async function walkDir(dir, files) {
	const entries = await fs$1.readdir(dir, { withFileTypes: true });
	for (const entry of entries) {
		const full = path.join(dir, entry.name);
		if (entry.isSymbolicLink()) continue;
		if (entry.isDirectory()) {
			await walkDir(full, files);
			continue;
		}
		if (!entry.isFile()) continue;
		if (!entry.name.endsWith(".md")) continue;
		files.push(full);
	}
}
async function listMemoryFiles(workspaceDir, extraPaths) {
	const result = [];
	const memoryFile = path.join(workspaceDir, "MEMORY.md");
	const altMemoryFile = path.join(workspaceDir, "memory.md");
	const memoryDir = path.join(workspaceDir, "memory");
	const addMarkdownFile = async (absPath) => {
		try {
			const stat = await fs$1.lstat(absPath);
			if (stat.isSymbolicLink() || !stat.isFile()) return;
			if (!absPath.endsWith(".md")) return;
			result.push(absPath);
		} catch {}
	};
	await addMarkdownFile(memoryFile);
	await addMarkdownFile(altMemoryFile);
	try {
		const dirStat = await fs$1.lstat(memoryDir);
		if (!dirStat.isSymbolicLink() && dirStat.isDirectory()) await walkDir(memoryDir, result);
	} catch {}
	const normalizedExtraPaths = normalizeExtraMemoryPaths(workspaceDir, extraPaths);
	if (normalizedExtraPaths.length > 0) for (const inputPath of normalizedExtraPaths) try {
		const stat = await fs$1.lstat(inputPath);
		if (stat.isSymbolicLink()) continue;
		if (stat.isDirectory()) {
			await walkDir(inputPath, result);
			continue;
		}
		if (stat.isFile() && inputPath.endsWith(".md")) result.push(inputPath);
	} catch {}
	if (result.length <= 1) return result;
	const seen = /* @__PURE__ */ new Set();
	const deduped = [];
	for (const entry of result) {
		let key = entry;
		try {
			key = await fs$1.realpath(entry);
		} catch {}
		if (seen.has(key)) continue;
		seen.add(key);
		deduped.push(entry);
	}
	return deduped;
}
function hashText(value) {
	return crypto.createHash("sha256").update(value).digest("hex");
}
async function buildFileEntry(absPath, workspaceDir) {
	const stat = await fs$1.stat(absPath);
	const hash = hashText(await fs$1.readFile(absPath, "utf-8"));
	return {
		path: path.relative(workspaceDir, absPath).replace(/\\/g, "/"),
		absPath,
		mtimeMs: stat.mtimeMs,
		size: stat.size,
		hash
	};
}
function chunkMarkdown(content, chunking) {
	const lines = content.split("\n");
	if (lines.length === 0) return [];
	const maxChars = Math.max(32, chunking.tokens * 4);
	const overlapChars = Math.max(0, chunking.overlap * 4);
	const chunks = [];
	let current = [];
	let currentChars = 0;
	const flush = () => {
		if (current.length === 0) return;
		const firstEntry = current[0];
		const lastEntry = current[current.length - 1];
		if (!firstEntry || !lastEntry) return;
		const text = current.map((entry) => entry.line).join("\n");
		const startLine = firstEntry.lineNo;
		const endLine = lastEntry.lineNo;
		chunks.push({
			startLine,
			endLine,
			text,
			hash: hashText(text)
		});
	};
	const carryOverlap = () => {
		if (overlapChars <= 0 || current.length === 0) {
			current = [];
			currentChars = 0;
			return;
		}
		let acc = 0;
		const kept = [];
		for (let i = current.length - 1; i >= 0; i -= 1) {
			const entry = current[i];
			if (!entry) continue;
			acc += entry.line.length + 1;
			kept.unshift(entry);
			if (acc >= overlapChars) break;
		}
		current = kept;
		currentChars = kept.reduce((sum, entry) => sum + entry.line.length + 1, 0);
	};
	for (let i = 0; i < lines.length; i += 1) {
		const line = lines[i] ?? "";
		const lineNo = i + 1;
		const segments = [];
		if (line.length === 0) segments.push("");
		else for (let start = 0; start < line.length; start += maxChars) segments.push(line.slice(start, start + maxChars));
		for (const segment of segments) {
			const lineSize = segment.length + 1;
			if (currentChars + lineSize > maxChars && current.length > 0) {
				flush();
				carryOverlap();
			}
			current.push({
				line: segment,
				lineNo
			});
			currentChars += lineSize;
		}
	}
	flush();
	return chunks;
}
function parseEmbedding(raw) {
	try {
		const parsed = JSON.parse(raw);
		return Array.isArray(parsed) ? parsed : [];
	} catch {
		return [];
	}
}
function cosineSimilarity(a, b) {
	if (a.length === 0 || b.length === 0) return 0;
	const len = Math.min(a.length, b.length);
	let dot = 0;
	let normA = 0;
	let normB = 0;
	for (let i = 0; i < len; i += 1) {
		const av = a[i] ?? 0;
		const bv = b[i] ?? 0;
		dot += av * bv;
		normA += av * av;
		normB += bv * bv;
	}
	if (normA === 0 || normB === 0) return 0;
	return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

//#endregion
//#region src/memory/sqlite.ts
const require = createRequire(import.meta.url);
function requireNodeSqlite() {
	installProcessWarningFilter();
	return require("node:sqlite");
}

//#endregion
export { ensureDir as a, listMemoryFiles as c, cosineSimilarity as i, normalizeExtraMemoryPaths as l, buildFileEntry as n, hashText as o, chunkMarkdown as r, isMemoryPath as s, requireNodeSqlite as t, parseEmbedding as u };