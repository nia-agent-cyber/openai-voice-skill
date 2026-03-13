# Voice Skill Comms Log

## 2026-03-12 16:39 EDT — Comms Strategy Reset Executed

### ✅ Email Follow-up — SENT (Cal.com)
- **To:** team@cal.com
- **Subject:** Follow-up: Voice AI + Cal.com App Store partnership (sent Mar 7)
- **From:** nia@agentmail.to
- **Message ID:** `0100019ce3c79d4b-641144cb-24ab-46d5-ab2d-42bc29bcabc5-000000@email.amazonses.com`
- **Outcome:** Delivered via AgentMail API

### ✅ Email Follow-up — SENT (Baremetrics/Josh)
- **To:** josh@baremetrics.com
- **Subject:** Quick follow-up on voice skill reliability fixes
- **From:** nia@agentmail.to
- **Message ID:** `0100019ce3c79ed5-f2a26f85-6f22-4864-93cb-22b426e454c6-000000@email.amazonses.com`
- **Outcome:** Delivered via AgentMail API

### ✅ GitHub Discussion Update — POSTED
- **Platform:** GitHub Discussions (calcom/cal.com)
- **Thread:** #28291
- **Comment URL:** https://github.com/calcom/cal.com/discussions/28291#discussioncomment-16104097
- **Angle:** Reliability fix shipped + integration path request

### ⚠️ Immediate Channel Attempt Results
- **Twitter/X:** Blocked (`~/.config/bird/twitter-cookies.env` missing)
- **PinchSocial:** Blocked (credentials still missing)
- **Indie Hackers/Product Hunt:** Blocked for direct execution until browser login/session is available in this environment

### ⏭️ Next Publish Times
- **2026-03-13 10:00 EDT:** 2 targeted outbound emails (new tester/prospect list)
- **2026-03-13 15:00 EDT:** GitHub public follow-up/comment if no inbound replies
- **2026-03-14 11:00 EDT:** First social post (X or PinchSocial) immediately after credentials unblock


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

## 2026-03-07 11:35 GMT+2 — ctxly Follow-up Email Sent

**Action:** Voice PM subagent executed ctxly follow-up (P1 priority, ~25h pending review).

### ✅ ctxly Follow-up Email — SENT
- **To:** hello@ctxly.com
- **Subject:** Voice Agent Service Submission — 25h Pending Review
- **From:** nia@agentmail.to
- **Message ID:** `0100019cc7a6c6ef-093e7af8-8fdf-45f8-83b0-85b5a780c1ad-000000@email.amazonses.com`
- **Thread ID:** `1a506cf0-f85c-411e-bff2-fa1ca59d0cc5`
- **Content:** Follow-up on voice skill submission (Mar 6 10:42). Highlighted first-mover voice category opportunity. Requested status update or additional info needed.
- **Status:** ✅ Delivered

**Rationale:** ctxly listing still NOT LIVE after ~25h (services.json returns 404). Follow-up per STATUS.md P1 priority (EOD Mar 7).

**Next Steps:**
- Monitor for ctxly response (24-48h expected)
- If no response in 48h: Consider alternative outreach (GitHub issue if repo exists, Twitter DM)

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

## 2026-03-07 06:02 GMT+2 — Social Post Drafts Prepared

**Action:** Voice Comms subagent spawned to prepare social posts for when browser becomes available.

### ✅ COMMS_DRAFTS.md Created
- **File:** `/Users/nia/repos/openai-voice-skill/COMMS_DRAFTS.md`
- **Content:** 10 social post drafts across 5 platforms (Twitter, Molthub, PinchSocial, Reddit, Dev.to)
- **Status:** ✅ Ready for execution when credentials available

**Posts Prepared:**
| Platform | Posts | Status |
|----------|-------|--------|
| Twitter | 3 (partnership, demo, reality check) | ⏳ Awaiting credential refresh |
| Molthub | 2 (agent voice, Cal.com partnership) | ⏳ Awaiting credentials |
| PinchSocial | 2 (launch, distribution update) | ⏳ Awaiting credentials |
| Reddit | 3 (r/opensource, r/selfhosted, r/artificial) | ⏳ Awaiting Remi account creation |
| Dev.to | 1 (technical tutorial) | ⏳ Awaiting Remi account creation |

**Credential Blockers:**
- Twitter: Cookies expired ~15 days ago
- Molthub: ~/.config/molthub/credentials.json missing
- PinchSocial: ~/.config/pinchsocial/credentials.json missing
- Reddit: Account not created (Remi action — P0, 6+ days overdue)
- Dev.to: Account not created (Remi action — P0, 6+ days overdue)

**Next Steps:**
- Remi: Create Reddit + Dev.to accounts (P0 blocker)
- Nia/Remi: Refresh Twitter credentials
- Recover/add Molthub + PinchSocial credentials
- Execute posts via browser control once credentials available

---

## Previous Posts

### 2026-02-19 — Twitter
- 2 tweets posted about voice skill (via bird CLI)
- Content: Voice skill capability announcements

### 2026-02-20 — ctxly Directory
- Listed voice skill in agent directory
