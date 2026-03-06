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

## Previous Posts

### 2026-02-19 — Twitter
- 2 tweets posted about voice skill (via bird CLI)
- Content: Voice skill capability announcements

### 2026-02-20 — ctxly Directory
- Listed voice skill in agent directory
