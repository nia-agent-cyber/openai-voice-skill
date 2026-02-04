import { c as readTailscaleWhoisIdentity } from "./tailscale-Cvk3mQDZ.js";
import { i as parseForwardedForClientIp, o as resolveGatewayClientIp, r as isTrustedProxyAddress } from "./net-DeiCIMU6.js";
import { timingSafeEqual } from "node:crypto";

//#region src/gateway/auth.ts
function safeEqual(a, b) {
	if (a.length !== b.length) return false;
	return timingSafeEqual(Buffer.from(a), Buffer.from(b));
}
function normalizeLogin(login) {
	return login.trim().toLowerCase();
}
function isLoopbackAddress(ip) {
	if (!ip) return false;
	if (ip === "127.0.0.1") return true;
	if (ip.startsWith("127.")) return true;
	if (ip === "::1") return true;
	if (ip.startsWith("::ffff:127.")) return true;
	return false;
}
function getHostName(hostHeader) {
	const host = (hostHeader ?? "").trim().toLowerCase();
	if (!host) return "";
	if (host.startsWith("[")) {
		const end = host.indexOf("]");
		if (end !== -1) return host.slice(1, end);
	}
	const [name] = host.split(":");
	return name ?? "";
}
function headerValue(value) {
	return Array.isArray(value) ? value[0] : value;
}
function resolveTailscaleClientIp(req) {
	if (!req) return;
	const forwardedFor = headerValue(req.headers?.["x-forwarded-for"]);
	return forwardedFor ? parseForwardedForClientIp(forwardedFor) : void 0;
}
function resolveRequestClientIp(req, trustedProxies) {
	if (!req) return;
	return resolveGatewayClientIp({
		remoteAddr: req.socket?.remoteAddress ?? "",
		forwardedFor: headerValue(req.headers?.["x-forwarded-for"]),
		realIp: headerValue(req.headers?.["x-real-ip"]),
		trustedProxies
	});
}
function isLocalDirectRequest(req, trustedProxies) {
	if (!req) return false;
	if (!isLoopbackAddress(resolveRequestClientIp(req, trustedProxies) ?? "")) return false;
	const host = getHostName(req.headers?.host);
	const hostIsLocal = host === "localhost" || host === "127.0.0.1" || host === "::1";
	const hostIsTailscaleServe = host.endsWith(".ts.net");
	const hasForwarded = Boolean(req.headers?.["x-forwarded-for"] || req.headers?.["x-real-ip"] || req.headers?.["x-forwarded-host"]);
	const remoteIsTrustedProxy = isTrustedProxyAddress(req.socket?.remoteAddress, trustedProxies);
	return (hostIsLocal || hostIsTailscaleServe) && (!hasForwarded || remoteIsTrustedProxy);
}
function getTailscaleUser(req) {
	if (!req) return null;
	const login = req.headers["tailscale-user-login"];
	if (typeof login !== "string" || !login.trim()) return null;
	const nameRaw = req.headers["tailscale-user-name"];
	const profilePic = req.headers["tailscale-user-profile-pic"];
	const name = typeof nameRaw === "string" && nameRaw.trim() ? nameRaw.trim() : login.trim();
	return {
		login: login.trim(),
		name,
		profilePic: typeof profilePic === "string" && profilePic.trim() ? profilePic.trim() : void 0
	};
}
function hasTailscaleProxyHeaders(req) {
	if (!req) return false;
	return Boolean(req.headers["x-forwarded-for"] && req.headers["x-forwarded-proto"] && req.headers["x-forwarded-host"]);
}
function isTailscaleProxyRequest(req) {
	if (!req) return false;
	return isLoopbackAddress(req.socket?.remoteAddress) && hasTailscaleProxyHeaders(req);
}
async function resolveVerifiedTailscaleUser(params) {
	const { req, tailscaleWhois } = params;
	const tailscaleUser = getTailscaleUser(req);
	if (!tailscaleUser) return {
		ok: false,
		reason: "tailscale_user_missing"
	};
	if (!isTailscaleProxyRequest(req)) return {
		ok: false,
		reason: "tailscale_proxy_missing"
	};
	const clientIp = resolveTailscaleClientIp(req);
	if (!clientIp) return {
		ok: false,
		reason: "tailscale_whois_failed"
	};
	const whois = await tailscaleWhois(clientIp);
	if (!whois?.login) return {
		ok: false,
		reason: "tailscale_whois_failed"
	};
	if (normalizeLogin(whois.login) !== normalizeLogin(tailscaleUser.login)) return {
		ok: false,
		reason: "tailscale_user_mismatch"
	};
	return {
		ok: true,
		user: {
			login: whois.login,
			name: whois.name ?? tailscaleUser.name,
			profilePic: tailscaleUser.profilePic
		}
	};
}
function resolveGatewayAuth(params) {
	const authConfig = params.authConfig ?? {};
	const env = params.env ?? process.env;
	const token = authConfig.token ?? env.OPENCLAW_GATEWAY_TOKEN ?? env.CLAWDBOT_GATEWAY_TOKEN ?? void 0;
	const password = authConfig.password ?? env.OPENCLAW_GATEWAY_PASSWORD ?? env.CLAWDBOT_GATEWAY_PASSWORD ?? void 0;
	const mode = authConfig.mode ?? (password ? "password" : "token");
	return {
		mode,
		token,
		password,
		allowTailscale: authConfig.allowTailscale ?? (params.tailscaleMode === "serve" && mode !== "password")
	};
}
function assertGatewayAuthConfigured(auth) {
	if (auth.mode === "token" && !auth.token) {
		if (auth.allowTailscale) return;
		throw new Error("gateway auth mode is token, but no token was configured (set gateway.auth.token or OPENCLAW_GATEWAY_TOKEN)");
	}
	if (auth.mode === "password" && !auth.password) throw new Error("gateway auth mode is password, but no password was configured");
}
async function authorizeGatewayConnect(params) {
	const { auth, connectAuth, req, trustedProxies } = params;
	const tailscaleWhois = params.tailscaleWhois ?? readTailscaleWhoisIdentity;
	const localDirect = isLocalDirectRequest(req, trustedProxies);
	if (auth.allowTailscale && !localDirect) {
		const tailscaleCheck = await resolveVerifiedTailscaleUser({
			req,
			tailscaleWhois
		});
		if (tailscaleCheck.ok) return {
			ok: true,
			method: "tailscale",
			user: tailscaleCheck.user.login
		};
	}
	if (auth.mode === "token") {
		if (!auth.token) return {
			ok: false,
			reason: "token_missing_config"
		};
		if (!connectAuth?.token) return {
			ok: false,
			reason: "token_missing"
		};
		if (!safeEqual(connectAuth.token, auth.token)) return {
			ok: false,
			reason: "token_mismatch"
		};
		return {
			ok: true,
			method: "token"
		};
	}
	if (auth.mode === "password") {
		const password = connectAuth?.password;
		if (!auth.password) return {
			ok: false,
			reason: "password_missing_config"
		};
		if (!password) return {
			ok: false,
			reason: "password_missing"
		};
		if (!safeEqual(password, auth.password)) return {
			ok: false,
			reason: "password_mismatch"
		};
		return {
			ok: true,
			method: "password"
		};
	}
	return {
		ok: false,
		reason: "unauthorized"
	};
}

//#endregion
export { resolveGatewayAuth as i, authorizeGatewayConnect as n, isLocalDirectRequest as r, assertGatewayAuthConfigured as t };