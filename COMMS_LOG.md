# Voice Skill Comms Log

## 2026-03-05 — Launch Distribution Push

### ✅ Show HN — POSTED
- **Title:** Show HN: Voice skill for AI agents – sub-200ms latency via native SIP
- **URL:** https://news.ycombinator.com/item?id=47261143
- **Platform:** Hacker News (nia-agent account)
- **Time:** 2026-03-05 15:01 GMT+2
- **Content:** Full description with tech stack, use case (missed-call callback), 97 tests, MIT licensed

### ✅ Cal.com GitHub Discussion — POSTED
- **Title:** Integration idea: AI voice agent for missed-call auto-callback → Cal.com booking
- **URL:** https://github.com/calcom/cal.com/discussions/28291
- **Platform:** GitHub Discussions (calcom/cal.com repo, "Other" category)
- **Time:** 2026-03-05 16:34 GMT+2
- **Content:** Open-source integration proposal. Framed as missed-call callback using Cal.com webhooks + API v2 for slot checking and booking. Includes flow diagram, community questions, and link to our repo.

### ❌ Reddit — BLOCKED (MANUAL ACTION REQUIRED)
- **Reason:** No Reddit account credentials available in browser or password store
- **Planned subreddits:** r/selfhosted, r/opensource, r/artificial
- **Action needed:** 
  1. Create Reddit account via GitHub OAuth at https://www.reddit.com/login
  2. Generate API credentials at https://www.reddit.com/dev/apps
  3. Save to pass: `pass insert reddit/client_id`, `pass insert reddit/client_secret`
  4. Comms agent will auto-post once credentials available
- **Draft ready:** `REDDIT_POST_DRAFT.md`

### ❌ Dev.to — BLOCKED (MANUAL ACTION REQUIRED)
- **Reason:** No Dev.to account credentials available
- **Action needed:**
  1. Create Dev.to account via GitHub OAuth at https://dev.to/enter
  2. Generate API key at Settings → Extensions
  3. Save to pass: `pass insert devto/api-key`
  4. Comms agent will auto-post once credentials available
- **Draft ready:** `DEVTO_POST_DRAFT.md`

### ❌ PinchSocial — BLOCKED
- **Reason:** No PinchSocial credentials in password store (~/.config/pinchsocial/credentials.json missing). Browser session not logged in.
- **Action needed:** Re-authenticate PinchSocial or provide API key

---

## ⚠️ Browser Control Status (2026-03-06 14:23 GMT+2)

Browser control is currently unreliable (OpenClaw browser control service unreachable). Account creation for Reddit and Dev.to requires browser-based OAuth flow. **Manual action required from Remi** to create accounts and save API credentials to pass store. Once credentials are available, Comms agent can complete posting via API.

---

## 2026-03-06 14:33 GMT+2 — Comms Retry Attempt

**Action:** Voice Comms subagent spawned to retry Reddit/Dev.to posting after gateway restart.

**Credential Check:**
```bash
pass ls | grep -E "(reddit|devto)"
# Result: No entries found
```

**Outcome:** ❌ **BLOCKED** — Reddit and Dev.to credentials still missing from pass store.

**Status:** Posts cannot be published until Remi manually:
1. Creates Reddit account → saves `reddit/client_id` and `reddit/client_secret` to pass
2. Creates Dev.to account → saves `devto/api-key` to pass

**Next Step:** This remains a P0 manual action item for Remi. Comms will auto-post once credentials are available.

---

## 2026-03-07 04:15 GMT+2 — Email Outreach Executed

**Action:** Voice Comms subagent spawned to execute email outreach (only unblocked channel per STATUS.md).

### ✅ Cal.com Partnership Email — SENT
- **To:** team@cal.com
- **Subject:** Voice AI + Cal.com App Store Partnership
- **From:** nia@agentmail.to
- **Message ID:** `0100019cc611af74-c2603f03-a72d-4977-a982-f4edc92eddc8-000000@email.amazonses.com`
- **Thread ID:** `792ed0e9-fe9c-4195-955c-de21e33f7fb5`
- **Content:** Partnership proposal for OAuth App Store integration. Pitched missed-call auto-callback use case with 11x ROI. Referenced GitHub Discussion #28291.
- **Status:** ✅ Delivered

### ✅ Shpigford Retry Email — SENT
- **To:** josh@baremetrics.com (alternative to bounced josh@shpigford.com)
- **Subject:** Voice reliability fixes - following up on your feedback
- **From:** nia@agentmail.to
- **Message ID:** `0100019cc611b230-bfa33963-0d07-4ae8-bf97-cbc1913f2c57-000000@email.amazonses.com`
- **Thread ID:** `def3a9f9-cbf3-49ab-b11a-be9891cca494`
- **Content:** Follow-up on his reliability concerns. Highlighted 6 reliability PRs shipped (#36-#42), 97 tests passing. Invited for test call/walkthrough.
- **Status:** ✅ Delivered

**Rationale:** Email is the ONLY distribution channel available today without new credentials (per STATUS.md channel audit). All social channels blocked (Twitter expired, Reddit/Dev.to/Molthub/PinchSocial missing creds).

**Next Steps:**
- Monitor for responses (7-day follow-up if no reply)
- Cal.com: If no response, try @peer_rich on Twitter or GitHub Discussion follow-up
- Shpigford: If no response, consider Twitter DM (@Shpigford) as fallback

---

## Previous Posts

### 2026-02-19 — Twitter
- 2 tweets posted about voice skill (via bird CLI)
- Content: Voice skill capability announcements

### 2026-02-20 — ctxly Directory
- Listed voice skill in agent directory
