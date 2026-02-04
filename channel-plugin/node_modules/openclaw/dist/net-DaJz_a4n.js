import { t as pickPrimaryTailnetIPv4 } from "./tailnet-BijMqkqa.js";
import net from "node:net";

//#region src/gateway/net.ts
function isLoopbackAddress(ip) {
	if (!ip) return false;
	if (ip === "127.0.0.1") return true;
	if (ip.startsWith("127.")) return true;
	if (ip === "::1") return true;
	if (ip.startsWith("::ffff:127.")) return true;
	return false;
}
function normalizeIPv4MappedAddress(ip) {
	if (ip.startsWith("::ffff:")) return ip.slice(7);
	return ip;
}
function normalizeIp(ip) {
	const trimmed = ip?.trim();
	if (!trimmed) return;
	return normalizeIPv4MappedAddress(trimmed.toLowerCase());
}
function stripOptionalPort(ip) {
	if (ip.startsWith("[")) {
		const end = ip.indexOf("]");
		if (end !== -1) return ip.slice(1, end);
	}
	if (net.isIP(ip)) return ip;
	const lastColon = ip.lastIndexOf(":");
	if (lastColon > -1 && ip.includes(".") && ip.indexOf(":") === lastColon) {
		const candidate = ip.slice(0, lastColon);
		if (net.isIP(candidate) === 4) return candidate;
	}
	return ip;
}
function parseForwardedForClientIp(forwardedFor) {
	const raw = forwardedFor?.split(",")[0]?.trim();
	if (!raw) return;
	return normalizeIp(stripOptionalPort(raw));
}
function parseRealIp(realIp) {
	const raw = realIp?.trim();
	if (!raw) return;
	return normalizeIp(stripOptionalPort(raw));
}
function isTrustedProxyAddress(ip, trustedProxies) {
	const normalized = normalizeIp(ip);
	if (!normalized || !trustedProxies || trustedProxies.length === 0) return false;
	return trustedProxies.some((proxy) => normalizeIp(proxy) === normalized);
}
function resolveGatewayClientIp(params) {
	const remote = normalizeIp(params.remoteAddr);
	if (!remote) return;
	if (!isTrustedProxyAddress(remote, params.trustedProxies)) return remote;
	return parseForwardedForClientIp(params.forwardedFor) ?? parseRealIp(params.realIp) ?? remote;
}
/**
* Resolves gateway bind host with fallback strategy.
*
* Modes:
* - loopback: 127.0.0.1 (rarely fails, but handled gracefully)
* - lan: always 0.0.0.0 (no fallback)
* - tailnet: Tailnet IPv4 if available, else loopback
* - auto: Loopback if available, else 0.0.0.0
* - custom: User-specified IP, fallback to 0.0.0.0 if unavailable
*
* @returns The bind address to use (never null)
*/
async function resolveGatewayBindHost(bind, customHost) {
	const mode = bind ?? "loopback";
	if (mode === "loopback") {
		if (await canBindToHost("127.0.0.1")) return "127.0.0.1";
		return "0.0.0.0";
	}
	if (mode === "tailnet") {
		const tailnetIP = pickPrimaryTailnetIPv4();
		if (tailnetIP && await canBindToHost(tailnetIP)) return tailnetIP;
		if (await canBindToHost("127.0.0.1")) return "127.0.0.1";
		return "0.0.0.0";
	}
	if (mode === "lan") return "0.0.0.0";
	if (mode === "custom") {
		const host = customHost?.trim();
		if (!host) return "0.0.0.0";
		if (isValidIPv4(host) && await canBindToHost(host)) return host;
		return "0.0.0.0";
	}
	if (mode === "auto") {
		if (await canBindToHost("127.0.0.1")) return "127.0.0.1";
		return "0.0.0.0";
	}
	return "0.0.0.0";
}
/**
* Test if we can bind to a specific host address.
* Creates a temporary server, attempts to bind, then closes it.
*
* @param host - The host address to test
* @returns True if we can successfully bind to this address
*/
async function canBindToHost(host) {
	return new Promise((resolve) => {
		const testServer = net.createServer();
		testServer.once("error", () => {
			resolve(false);
		});
		testServer.once("listening", () => {
			testServer.close();
			resolve(true);
		});
		testServer.listen(0, host);
	});
}
async function resolveGatewayListenHosts(bindHost, opts) {
	if (bindHost !== "127.0.0.1") return [bindHost];
	if (await (opts?.canBindToHost ?? canBindToHost)("::1")) return [bindHost, "::1"];
	return [bindHost];
}
/**
* Validate if a string is a valid IPv4 address.
*
* @param host - The string to validate
* @returns True if valid IPv4 format
*/
function isValidIPv4(host) {
	const parts = host.split(".");
	if (parts.length !== 4) return false;
	return parts.every((part) => {
		const n = parseInt(part, 10);
		return !Number.isNaN(n) && n >= 0 && n <= 255 && part === String(n);
	});
}
function isLoopbackHost(host) {
	return isLoopbackAddress(host);
}

//#endregion
export { resolveGatewayBindHost as a, parseForwardedForClientIp as i, isLoopbackHost as n, resolveGatewayClientIp as o, isTrustedProxyAddress as r, resolveGatewayListenHosts as s, isLoopbackAddress as t };