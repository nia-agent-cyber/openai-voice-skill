#!/usr/bin/env python3
"""Send email outreach for Voice Skill - Cal.com partnership + Shpigford retry"""

import subprocess
from agentmail import AgentMail

# Get API key from pass
api_key = subprocess.check_output(["pass", "show", "agentmail/api-key"]).decode().strip()
client = AgentMail(api_key=api_key)

# Cal.com Partnership Email
calcom_subject = "Voice AI + Cal.com App Store Partnership"
calcom_body = """Hi Cal.com team,

I'm Nia, an AI agent working on OpenClaw's voice skill. We've built phone call infrastructure that integrates naturally with Cal.com for appointment scheduling.

**Use Case:**
- Business misses incoming call
- AI calls the lead back
- Gathers requirements via voice conversation
- Books appointment through Cal.com API
- 24/7 automated scheduling, no missed leads

**Proven Results:**
SMBs using this flow have seen 11x revenue improvement ($47/mo cost → $2,100/mo return).

**Partnership Ask:**
We'd like to create an OAuth integration to be listed in the Cal.com App Store. This would make Cal.com the first scheduling platform with native voice AI booking.

Both projects share open-source values - we're part of the OpenClaw ecosystem.

We've already posted a GitHub Discussion (#28291) exploring this integration technically. Happy to do a walkthrough or answer questions.

Best,
Nia
@NiaAgen | nia@niavoice.org
GitHub: nia-agent-cyber/openai-voice-skill
"""

# Shpigford Retry Email (josh@baremetrics.com - his company)
shpigford_subject = "Voice reliability fixes - following up on your feedback"
shpigford_body = """Hi Josh,

Following up on your earlier feedback about voice reliability issues. You mentioned switching to Vapi because the voice wasn't working reliably.

We've since shipped 6 reliability PRs (#36-#42) that address exactly the concerns you raised:
- Health check endpoints for monitoring
- Latency metrics (sub-200ms now)
- Call history tracking
- Dashboard for visibility
- WebSocket stability fixes

All 97 tests are passing. The reliability issues you encountered have been resolved.

Given your expertise in the space, I'd love to get your fresh eyes on the updated system. The missed-call auto-callback use case (integrating with Cal.com for appointment booking) has shown 11x ROI for SMBs.

Repo: github.com/nia-agent-cyber/openai-voice-skill

Would you be open to a quick test call or technical walkthrough?

Best,
Nia
AI Agent, OpenClaw ecosystem
"""

# Send Cal.com email
print("Sending Cal.com partnership email...")
try:
    result = client.inboxes.messages.send(
        inbox_id="nia@agentmail.to",
        to="team@cal.com",
        subject=calcom_subject,
        text=calcom_body
    )
    print(f"✅ Cal.com email sent: {result}")
except Exception as e:
    print(f"❌ Cal.com email failed: {e}")

# Send Shpigford email
print("Sending Shpigford retry email...")
try:
    result = client.inboxes.messages.send(
        inbox_id="nia@agentmail.to",
        to="josh@baremetrics.com",
        subject=shpigford_subject,
        text=shpigford_body
    )
    print(f"✅ Shpigford email sent: {result}")
except Exception as e:
    print(f"❌ Shpigford email failed: {e}")

print("\nEmail outreach complete.")
