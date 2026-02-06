/**
 * Tests for Inbound Call Handler (T4)
 */

import { describe, it, expect } from "vitest";
import {
  authorizeInboundCall,
  buildInboundSessionContext,
  generateRejectTwiml,
  generateAcceptTwiml,
  _internal,
} from "./inbound.js";
import type { VoiceAccountConfig } from "./config.js";
import type { InboundCallEvent } from "./inbound.js";

const { normalizePhoneNumber, maskPhoneNumber, checkAllowlist } = _internal;

describe("Phone Normalization", () => {
  it("normalizes E.164 format", () => {
    expect(normalizePhoneNumber("+14402915517")).toBe("+14402915517");
  });

  it("adds + prefix when missing", () => {
    expect(normalizePhoneNumber("14402915517")).toBe("+14402915517");
  });

  it("removes formatting characters", () => {
    expect(normalizePhoneNumber("+1 (440) 291-5517")).toBe("+14402915517");
    expect(normalizePhoneNumber("1-440-291-5517")).toBe("+14402915517");
  });

  it("handles empty string", () => {
    expect(normalizePhoneNumber("")).toBe("");
  });
});

describe("Phone Masking", () => {
  it("masks middle digits", () => {
    expect(maskPhoneNumber("+14402915517")).toBe("+144****5517");
  });

  it("returns **** for short numbers", () => {
    expect(maskPhoneNumber("123")).toBe("****");
    expect(maskPhoneNumber("")).toBe("****");
  });
});

describe("Allowlist Checking", () => {
  it("matches exact numbers", () => {
    const allowlist = ["+14402915517", "+15551234567"];
    expect(checkAllowlist("+14402915517", allowlist)).toBe("+14402915517");
    expect(checkAllowlist("+15551234567", allowlist)).toBe("+15551234567");
    expect(checkAllowlist("+19999999999", allowlist)).toBeNull();
  });

  it("matches wildcard", () => {
    const allowlist = ["*"];
    expect(checkAllowlist("+14402915517", allowlist)).toBe("*");
    expect(checkAllowlist("+19999999999", allowlist)).toBe("*");
  });

  it("matches prefix patterns", () => {
    const allowlist = ["+1440*"];
    expect(checkAllowlist("+14402915517", allowlist)).toBe("+1440*");
    expect(checkAllowlist("+14401234567", allowlist)).toBe("+1440*");
    expect(checkAllowlist("+15551234567", allowlist)).toBeNull();
  });

  it("returns null for empty allowlist", () => {
    expect(checkAllowlist("+14402915517", [])).toBeNull();
  });
});

describe("Authorization", () => {
  it("open policy accepts all", () => {
    const config: VoiceAccountConfig = {
      dmPolicy: "open",
    };
    const result = authorizeInboundCall("+14402915517", config);

    expect(result.authorized).toBe(true);
    expect(result.reason).toBe("allowed");
    expect(result.policy).toBe("open");
  });

  it("allowlist policy matches allowed number", () => {
    const config: VoiceAccountConfig = {
      dmPolicy: "allowlist",
      allowFrom: ["+14402915517"],
    };
    const result = authorizeInboundCall("+14402915517", config);

    expect(result.authorized).toBe(true);
    expect(result.reason).toBe("allowlist_match");
    expect(result.matchedEntry).toBe("+14402915517");
  });

  it("allowlist policy rejects non-matching number", () => {
    const config: VoiceAccountConfig = {
      dmPolicy: "allowlist",
      allowFrom: ["+15551234567"],
    };
    const result = authorizeInboundCall("+14402915517", config);

    expect(result.authorized).toBe(false);
    expect(result.reason).toBe("denied");
  });

  it("empty allowlist rejects all (secure default)", () => {
    const config: VoiceAccountConfig = {
      dmPolicy: "allowlist",
      allowFrom: [],
    };
    const result = authorizeInboundCall("+14402915517", config);

    expect(result.authorized).toBe(false);
    expect(result.reason).toBe("not_configured");
  });

  it("disabled config rejects", () => {
    const config: VoiceAccountConfig = {
      enabled: false,
    };
    const result = authorizeInboundCall("+14402915517", config);

    expect(result.authorized).toBe(false);
    expect(result.reason).toBe("not_configured");
  });
});

describe("Session Context Building", () => {
  const baseEvent: InboundCallEvent = {
    callSid: "CA123",
    from: "+14402915517",
    to: "+18005551234",
    direction: "inbound",
  };

  it("builds session key from phone number", () => {
    const context = buildInboundSessionContext(baseEvent);
    expect(context.sessionKey).toBe("voice:14402915517");
  });

  it("identifies new callers", () => {
    const context = buildInboundSessionContext(baseEvent);
    expect(context.isKnownCaller).toBe(false);
    expect(context.contextInstructions).toContain("NEW CALLER");
  });

  it("includes location info when available", () => {
    const event: InboundCallEvent = {
      ...baseEvent,
      fromCity: "Cleveland",
      fromState: "OH",
      fromCountry: "US",
    };
    const context = buildInboundSessionContext(event);
    expect(context.contextInstructions).toContain("Cleveland, OH, US");
  });

  it("includes caller name when available", () => {
    const event: InboundCallEvent = {
      ...baseEvent,
      callerName: "John Doe",
    };
    const context = buildInboundSessionContext(event);
    expect(context.contextInstructions).toContain("John Doe");
  });
});

describe("TwiML Generation", () => {
  it("generates valid reject TwiML with voicemail", () => {
    const twiml = generateRejectTwiml("Not authorized", true);
    expect(twiml).toContain("<Response>");
    expect(twiml).toContain("<Say");
    expect(twiml).toContain("<Record");
    expect(twiml).toContain("</Response>");
  });

  it("generates valid reject TwiML without voicemail", () => {
    const twiml = generateRejectTwiml("Not authorized", false);
    expect(twiml).toContain("<Response>");
    expect(twiml).toContain("<Hangup/>");
    expect(twiml).not.toContain("<Record");
  });

  it("generates valid accept TwiML with SIP URI", () => {
    const sipUri = "sip:proj_123@sip.api.openai.com;transport=tls";
    const twiml = generateAcceptTwiml(sipUri);
    expect(twiml).toContain("<Response>");
    expect(twiml).toContain("<Dial>");
    expect(twiml).toContain("<Sip>");
    expect(twiml).toContain(sipUri);
  });
});
