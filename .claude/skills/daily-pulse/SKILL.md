---
name: daily-pulse
description: Use to generate the user's daily morning read, a single email to their own Gmail combining (1) last-24h Gmail summary with commitment-tracking, plus school-inbox mail from people that the school won't forward, (2) LMS upcoming assignments + missing submissions, (3) upcoming events from group chats, the campus events platform, and club social posts that are not already on the calendar, (4) today's Anthropic + Claude Code changelog inlined from the aios-cloud-feed cloud routine, (5) the weekly AI internships digest also inlined from a cloud routine, and (6) the top stories from that morning's ai-news digest. Triggers on `/daily-pulse`, "give me today's pulse", "summarize my inbox", "what came in today", or as a scheduled launchd job at 8am daily.
---

# Daily Pulse - single morning read (Gmail + LMS + events + cloud routines)

## What this skill does

Pulls last-24h Gmail (filtered to important messages), classifies importance using LLM judgment, summarizes each significant thread, queries the LMS for upcoming/missing assignments, gathers events the user wouldn't otherwise see, **pulls today's cloud-routine outputs from `aios-cloud-feed` and today's ai-news top stories**, and emails everything to the user as one HTML email.

**The point:** one email per morning that contains everything. Open on phone, scan, done. It replaces opening (a) Gmail, (b) the LMS, (c) the GitHub repo for cloud-routine outputs. (Earlier versions wrote a Google Doc; email won because it is already where the user looks.)

**Token economy:**
- Use metadata-only fetches for the initial listing (headers only, ~50 tokens/msg)
- Only fetch full body for classified-important messages (typically 5-10 out of 30-50 daily)
- Never dump raw JSON of all messages into context. Filter and summarize on the API side, reason on the summarized side

**Fetchers not included in this public extract:** the school-inbox, group-chat, campus-events and social fetchers. They ride the user's own logged-in browser sessions or personal tokens, so they stay private. Each one is a small script that writes a `latest.json` of candidates and exits with a documented code (0 ok, 2 session expired, 3 data shape changed / flagged). The judgment rules below are the part worth reusing.

## When NOT to run this

- For arbitrary email searches → use `gws gmail users messages list --params '{"q":"<search>"}'` directly with no skill overhead
- For drafting replies → a different skill chain (a voice skill + `gws gmail users drafts create`)
- For Gmail labeling / archiving → a separate email-organizer pipeline

This skill is read-only and summary-focused. It does not modify Gmail state.

## Execution

### Step 1: Resolve today's date and time window

Today's date in `YYYY-MM-DD` format. Time window: messages received in the last 24 hours from `now()`. Gmail's `after:<epoch-seconds>` gives an exact 24h window; `after:YYYY/MM/DD` rounds to a day.

Build the Gmail query string: `after:<epoch>` plus `(in:inbox OR label:<school-label> OR from:<your-school-email>) -in:spam -in:trash -subject:"Daily Pulse"`. The OR clauses catch school-forwarded mail that an existing Gmail filter auto-labels and removes from the inbox. Without them, everything forwarded from the school account is silently missed. Person-to-person staff mail may not forward at all (see Step 7.4).

### Step 2: List messages (metadata only)

```bash
gws gmail users messages list --params '{
  "userId": "me",
  "q": "after:<epoch> (in:inbox OR label:<school-label> OR from:<your-school-email>) -in:spam -in:trash -subject:\"Daily Pulse\"",
  "maxResults": 50,
  "fields": "messages(id,threadId)"
}' < /dev/null
```

If 0 messages: output *"Nothing in the last 24 hours."* and exit. Don't send an empty email. (`-subject:"Daily Pulse"` keeps yesterday's pulse email out of today's window.)

### Step 3: Fetch headers for each message

For each message ID, fetch metadata (not full body; that comes later for important ones only):

```bash
gws gmail users messages get --params '{"userId":"me","id":"<msgId>","format":"metadata"}' < /dev/null
```

Hard-won rules for `gws`:
- **Don't pass `metadataHeaders`.** With it, the CLI returned zero headers. Omit it and pick `From`/`To`/`Subject`/`Date` out of `payload.headers` with `jq`.
- **Loop sequentially.** Parallel `gws` calls returned empty results.
- **`< /dev/null` on every call inside a loop.** `gws` reads stdin, so `while read ...; do gws ...; done < file` hangs silently.
- **Strip the keyring banner** before `jq`: `gws` prints a "Using keyring backend" line; pipe through `sed -n '/^{/,$p'`.
- If `gws` is slow under load (~14s/call), the claude.ai Gmail connector reads the same inbox and is fine for the wide scan.

### Step 4: Classify importance

For each message, judge importance with these heuristics. **Inline judgment, no extra LLM call needed for most:**

**Important (always include in summary):**
- From recruiters, hiring managers, internship coordinators ("opportunity", "internship", "position", "interview" in the subject)
- From professors or academic contacts (`.edu` domains)
- **School mail forwarded from the user's Microsoft 365 school account: always important.** Forwarding is an Outlook inbox rule. Detection and extraction is a two-step process, verified against real headers:

  **Step A - Detect forwarded mail (priority order, stop at first match):**
  1. **Primary signal (reliable):** header `X-MS-Exchange-Inbox-Rules-Loop` contains `<your-school-email>`. This header is unique to Microsoft inbox-rule forwarding and present on every forwarded message.
  2. **Secondary signal:** header `auto-submitted: auto-generated` AND `Return-Path` is `<your-school-email>`. Catches edge cases where a relay strips the loop header.
  3. **Tertiary signal:** subject starts with `FW:` AND From is `<your-school-email>` AND the body contains a literal `From: ` near the top.

  **Note: Outlook rewrites the visible `From:` on forwarded mail to the user's own school address. The TRUE original sender lives in the body, not the header.**

  **Step B - Extract the true original sender from the body.** Parse the first ~30 lines of the plaintext body for the header block below a row of underscores:

  ```
  From: {NAME} <{email@domain}>
  Sent: {date}
  To: {recipient}
  Subject: {original_subject}
  ```

  Use `{NAME}`, `{email@domain}` and `{original_subject}` in the summary instead of the rewritten From header.

  **Step C - Clean the subject:** strip leading `FW: ` and `[External] ` (or `[EXTERNAL] `). `FW: [External] Registration deadline` becomes `Registration deadline`.

  **Step D - Sub-categorize by the original sender's address:**
  - school address containing `registrar`, `bursar`, `studentaccounts` → `[Registrar]`
  - `financialaid`, `studentfinancialservices` → `[Financial Aid]`
  - `housing`, `reslife` → `[Housing]`
  - `orientation`, `welcomecenter` → `[Orientation]`
  - `advisor`, `advising` → `[Advising]`
  - any other school address → `[Academic]`
  - external sender that came through the school inbox → `[External via School]`
  - uncertain → `[School General]`
- From current clients or anyone on the user's private "always important" sender list (kept in a local, gitignored file)
- Subjects with deadlines / time pressure ("due", "deadline", "tomorrow", "by Friday", "ASAP", "EOD")
- Subjects with payments / contracts ("invoice", "payment", "agreement", "contract")
- Personal correspondence from known senders

**Skip (don't include):**
- Newsletters (Substack, Medium digests, etc.)
- Promotional (marketing@, deals@, no-reply@)
- Notification emails (GitHub notifications, app updates, unless about something actively in progress)
- Calendar invites that auto-accept
- Receipts / order confirmations

When uncertain, *include*. Better to over-summarize than miss a recruiter.

### Step 5: Fetch full body for important messages

```bash
gws gmail users messages get --params '{"userId":"me","id":"<msgId>","format":"full"}' < /dev/null
```

Extract the plain-text body (multipart messages return `parts[]`; pick `text/plain`; if only `text/html` exists, strip HTML inline).

### Step 6: Summarize each important message

One paragraph per message, 2-4 sentences max:
- What it's about (1 sentence)
- What action it requires, if any (1 sentence)
- Any deadline / time-sensitive detail (1 sentence if applicable)

**Don't paraphrase the entire email.** The goal is *"can the user triage this in 5 seconds?"*, not *"can they avoid opening the email?"*.

### Step 7: Detect implicit commitments

Parse each important summary for commitment language: *"I'll get back to you"*, *"by next week"*, *"send the resume soon"*, *"follow up"*, *"will let you know"*. If found, capture it as a commitment to track.

After Step 9 (email sent), **append commitments to `parking-lot.md`** in this format:

```
## Commitment: <one-line description> - captured <YYYY-MM-DD>
**From:** <email subject + sender>
**Due:** <date inferred from email, or "no date stated">
**Revisit at:** <date for /briefing to surface - default: 3 days from capture>
```

This is the commitment tracker: emails become trackable arcs without the user typing them, and `/briefing` surfaces each one on its revisit date.

### Step 7.4: School inbox (mail that doesn't forward)

Some schools run a transport rule that blocks auto-forwards of person-to-person staff mail (advisors, professors), so those never reach Gmail. Bulk mail still forwards and is handled above. This step reads the school inbox directly through the user's own Outlook web session (private fetcher, `--json` mode, last 24h, people only, bulk dropped).

Output: `messages[]` with `from_name`, `subject`, `received`, `preview` (300 chars), `unread`.
- **Skip** any message whose subject already appeared as a `FW:` in today's Gmail set. It forwarded fine and is already in Important.
- For the rest, write **one line each**: sender, subject, and what the user needs to do (with deadline if the preview gives one). Use the preview only. **Never fetch or paste full bodies.** Full text stays in the school mailbox (school email policy).
- `from_name` "Microsoft Outlook" is a bounce notice; its subject is a thread that failed to forward. List it under the thread's subject as "(bounced, check Outlook)".
- These are school people and offices, so they are important by default. Commitment language in a preview feeds Step 7 like any other email.

Failures (one line in the section, never fail the skill):
- **On exit 2 or 3, re-run the fetcher once by itself** (after the other browser fetchers finish) before reporting. A headless browser cold start at 8am times out and looks like an expired login; the solo retry worked every time it was tried.
- Exit 2 after the retry = session expired: "School inbox login expired: run the fetcher with `--login`".
- Exit 3 after the retry = quote the fetcher's stderr line. Only call it "data shape changed" if stderr says so.

### Step 7.5: LMS upcoming + missing

If the LMS allows personal API tokens (Canvas does unless the school disables them), load the token + host from `.env` (gitignored):

```bash
set -a; source ./.env; set +a   # CANVAS_TOKEN, CANVAS_HOST
```

**A. Upcoming assignments next 7 days:**

```bash
curl -s -H "Authorization: Bearer $CANVAS_TOKEN" \
  "$CANVAS_HOST/api/v1/users/self/upcoming_events?type=assignment&per_page=20"
```

Extract `title`, `start_at`, `context_name` (course), `html_url`. Keep events with `start_at` ≤ today + 7 days. Convert UTC → local time for display.

**B. Missing submissions:**

```bash
curl -s -H "Authorization: Bearer $CANVAS_TOKEN" \
  "$CANVAS_HOST/api/v1/users/self/missing_submissions?per_page=20"
```

Extract `name`, `due_at`, `course_id`, `html_url`. Map `course_id` to a course name (`/users/self/courses`). Skip items > 90 days old (stale practice tasks the LMS leaves open).

**Schools that block student tokens:** use a session-cookie fetcher instead (private). If it reports `NOT_AUTHENTICATED`, use the last dated snapshot of its output and label the section with that date rather than skipping it.

If auth fails (401/403): note inline, skip the section, continue. Don't fail the whole skill.

### Step 7.6: Pull cloud-routine outputs from `aios-cloud-feed`

Two cloud routines (`changelog-watcher` daily 6am, `internship-watcher` Sunday 9am) write markdown to a `<you>/aios-cloud-feed` GitHub repo. They need no local credentials, so they run in the cloud whether or not the laptop is awake. The user can't read cloud-routine output without opening a session, so **inline today's entries into the email**.

**A. Changelog (daily):**

```bash
TODAY=$(date +%Y-%m-%d)
CHANGELOG_CONTENT=$(gh api "repos/<you>/aios-cloud-feed/contents/changelog/$TODAY.md" \
  --jq '.content' 2>/dev/null | base64 -d 2>/dev/null)

if [ -z "$CHANGELOG_CONTENT" ]; then
  YESTERDAY=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d)
  CHANGELOG_CONTENT=$(gh api "repos/<you>/aios-cloud-feed/contents/changelog/$YESTERDAY.md" \
    --jq '.content' 2>/dev/null | base64 -d 2>/dev/null)
  CHANGELOG_DATE="$YESTERDAY (most recent; today's hasn't landed yet)"
else
  CHANGELOG_DATE="$TODAY"
fi
```

If both fail: one line ("changelog-watcher hasn't posted yet") and continue.

**B. Internships (every run, most recent file):** the weekly listing is useful all week, so always show the newest file, dated with the Sunday it was generated.

```bash
LATEST_INTERNSHIP=$(gh api "repos/<you>/aios-cloud-feed/contents/internships" \
  --jq '[.[] | select(.name | endswith(".md"))] | sort_by(.name) | reverse | .[0].name' 2>/dev/null | tr -d '"')

if [ -n "$LATEST_INTERNSHIP" ] && [ "$LATEST_INTERNSHIP" != "null" ]; then
  INTERNSHIPS_CONTENT=$(gh api "repos/<you>/aios-cloud-feed/contents/internships/$LATEST_INTERNSHIP" \
    --jq '.content' 2>/dev/null | base64 -d 2>/dev/null)
  INTERNSHIPS_DATE="${LATEST_INTERNSHIP%.md}"
fi
```

No .md files yet: skip the section silently (a daily "hasn't posted" line for weeks is noise). `gh` auth failure: one line ("run `gh auth status`"), skip the cloud sections, continue.

**Cloud routines commit to their session branch by default.** Their prompt has to say `git push origin HEAD:main` explicitly, or nothing lands where this step reads.

### Step 7.7: Events from group chats

Club and class group chats carry meeting times, room changes, and socials that never reach the LMS or email. The private fetcher is the deterministic half: it fetches only messages it has not seen (state file), keeps messages scoring >= 2 on time/date/keyword/location, collapses cross-posted duplicates, and writes `candidates[]`.

**Your half is judgment.** For each candidate:

1. **Resolve the actual date** against that candidate's `sent_at`, not against now. A message sent Monday saying "tomorrow" means Tuesday.
2. **Drop anything already past.** Most candidates announce events that already happened.
3. **Drop non-events.** Thank-you notes and recaps score high but announce nothing ("BIG TURNOUT FOR THE 5:30 STUDY, thanks for coming"). So do requests for photos of a past event.
4. **Cross-reference the calendar.** The user wants what they would not otherwise know:

   ```bash
   gws calendar events list --params '{"calendarId":"primary","timeMin":"<ISO>","timeMax":"<ISO>","singleEvents":true}'
   ```

   (`gws calendar` has no `--from`/`--to` flags; pass `timeMin`/`timeMax` in `--params`.) If a matching event exists, skip it. Recurring commitments are usually already there.
5. **Do NOT create calendar events automatically.** Group chat is noisy and a wrong auto-add is worse than a missed one. Surface them and let the user confirm.

Missing token or 401/403: one line, skip the section.

### Step 7.8: Campus events platform + club social posts

Two more event sources, same split. Neither has a public API, so both ride the user's own browser session.

**Campus events platform:** structured events with exact `start`, `location`, `host`, `new_since_last_run` and an `add_to_calendar` link. It lists dozens of events per two weeks, so **pick, don't dump**:
- **Always include** events hosted by the user's own clubs (a list kept in a local file). These don't count toward the cap.
- Then at most 8 more, chosen for fit with the user's priorities. Lead with `new_since_last_run`.
- Put each row's `add_to_calendar` link in the Add column. End with one line pointing at the full listing.

**Club social posts:** `candidates[]` are posts and stories from a local list of club accounts.
- `needs_image_read: true` means the caption has no date. Read the image and judge the flyer. Most are photos or recaps: drop them.
- Resolve relative dates against `posted_at`. Stories last 24h, so "tonight" on a story means the day it was posted.

Then apply Step 7.7 rules 2-5 to both: drop past events, drop non-events, skip anything already on the calendar, never auto-add.

Failures (one line each, never fail the skill):
- Events platform exit 2: re-run once by itself before reporting (same 8am cold-start false alarm as Step 7.4).
- Exit 2 after that = session expired: name the `--login` command and skip that source.
- Social platform exit 3, or a non-null `checkpoint` in its JSON = the platform flagged the session. Put this **at the top of the email**: "The social platform flagged the automation. Clear it in the app and don't re-run until then." **Never retry.**

### Step 7.9: AI News top stories

The `ai-news` launchd job runs at 7am and writes `ai-news-{YYYY-MM-DD}.md` to the user's wiki. Take only its `## Top Stories` section (6-8 curated stories). Skip the rest: the full digest stays in the wiki.

If today's file doesn't exist, one line: "No AI News digest today. Log: `~/.local/share/aios-logs/ai-news-{YYYY-MM-DD}.log`".

### Step 8: Compose the summary markdown

Template (no em dashes, terse, voice rules per `references/voice.md`):

```markdown
# Daily Pulse - {YYYY-MM-DD}

**Window:** last 24 hours
**Inbox:** {N} messages total, {M} flagged important

## Important

### {Cleaned subject} - from {Original sender from body, or header sender if not forwarded}
{For forwarded school mail: lead with the sub-category tag (e.g. `[Registrar]`). Then one paragraph: what it's about, action required, deadline. End with "(via school inbox)".}

(Repeat for each important message)

## School inbox (didn't forward)

- **{from_name}**: {subject}. {What to do + deadline, from the preview only}

(Step 7.4. If none: "Nothing from people." If the fetcher failed: its one-line note.)

## Skipped

{N} newsletter/promo/notification emails skipped. Sample senders: {3-5 example sender domains}.

## LMS - upcoming assignments (next 7 days)

| Due | Assignment | Course |
|---|---|---|
| {YYYY-MM-DD HH:MM} | {title} | {course} |

(If none: "No assignments due in next 7 days.")

## LMS - missing submissions

| Originally due | Assignment | Course |
|---|---|---|
| {YYYY-MM-DD} | {name} | {course} |

(If clean: "Caught up - no real missing submissions.")

## Suggested for your Unlock list

(**Suggestions only. Never add to, edit, or check off anything in the Reminders "Unlock" list from this skill.** The user adds what they want. See `scripts/unlock-sync.sh`.)

- {Assignment} ({course}), due {Day HH:MM}
- {Commitment one-liner}, due {date}

(Unsubmitted assignments due in the next 24 hours, real missing submissions from the past 7 days, and Step 7 commitments due today or tomorrow. Soonest first. Omit the section if nothing qualifies.)

## Upcoming events not on your calendar

| When | What | Where | Source | Add |
|---|---|---|---|---|
| {resolved date + time} | {event} | {room/building} | {chat / host / @handle} | {add_to_calendar link, else blank} |

(Only forward-looking events absent from the calendar, soonest first. Merge the same event seen in several sources into one row. If none: "Nothing new.")

## Commitments captured

{New commitment lines added to parking-lot.md, or "None - no commitment language detected."}

## Anthropic + Claude Code changelog ({CHANGELOG_DATE})

{$CHANGELOG_CONTENT, already markdown}

## AI Internships - week of {INTERNSHIPS_DATE}

{$INTERNSHIPS_CONTENT, already markdown. Omit the section if no file exists yet.}

## AI News

(Step 7.9 top stories, inlined as-is.)

---
*Generated by /daily-pulse on {YYYY-MM-DD HH:MM}*
```

### Step 9: Email it to the user

Render the Step 8 markdown to simple HTML yourself: `h1`-`h3`, `p`, `ul`/`li`, `b`, `a href` (every URL clickable), tables as `<table border="1" cellpadding="4" style="border-collapse:collapse">`. No CSS beyond that, no images. Write it with the Write tool to `.tmp/dp/{YYYY-MM-DD}/pulse.html`, then send from the project root:

```bash
gws gmail +send --to <your-email> \
  --subject "Daily Pulse: {Day Mon D}" \
  --body "$(cat .tmp/dp/{YYYY-MM-DD}/pulse.html)" --html < /dev/null | sed -n '/^{/,$p' | jq -r .id
```

A message id back = sent. `gws` is authed as the same account, so this is a self-send and lands in the inbox. The subject starts with "Daily Pulse" so Step 2's `-subject:"Daily Pulse"` filter skips it tomorrow.

### Step 10: Return summary to conversation

```
Daily Pulse: {YYYY-MM-DD}
{N} inbox / {M} important
{Top 2-3 important headlines, one-line each}

Emailed: message {id}
Commitments captured: {count → parking-lot.md}
```

## Critical implementation rules

1. **Read-only on Gmail.** Never label, archive, delete, or modify any message.
2. **Token budget.** Headers-only for the wide scan; full body only for the important subset. Never dump 50 message bodies into context.
3. **No em dashes** in any output.
4. **Voice register for the summaries.** Direct, terse, no breathless adjectives. *"From the recruiter re: AI internship opening Mon."* not *"An exciting opportunity has arrived from..."*
5. **Privacy.** This skill processes private email. Never log full email bodies to the wiki, decision logs or commits. The email itself is fine (self-sent). Don't quote message bodies in chat beyond the summary.
6. **Commitment-tracking is mandatory.** Step 7 is the reason this skill exists at the cadence level.

## Error handling

| Failure | Response |
|---|---|
| `gws` token invalid | Tell the user to run `gws auth login`. Don't auto-run (browser interactive). Don't preflight with `gws auth status`: it can hang; the real calls fail fast on their own. |
| Every `gws` call fails with `invalid peer certificate: UnknownIssuer` under launchd | The runner must export `SSL_CERT_FILE=/etc/ssl/cert.pem` (see `scripts/run-daily-pulse.sh`). |
| Gmail returns 0 messages in window | Output "Nothing in the last 24 hours." Exit gracefully. Don't send an empty email. |
| Email send (Step 9) fails | Retry once with the plain markdown as body (drop `--html`). If that fails too, print the summary in chat and note "Email failed, HTML at .tmp/dp/{date}/pulse.html". |

## Verification

1. Manually invoke `/daily-pulse` from the AIOS project.
2. Expected: lists ~30-50 messages, classifies ~5-10 important, writes one-paragraph summaries, sends one "Daily Pulse" email, appends 0-3 commitments to `parking-lot.md`.
3. Open the email on a phone: headers, tables and links render.
4. Check `parking-lot.md`: new commitment entries have a correct `Revisit at:` date.
5. Re-run on a quiet day: graceful "Nothing in the last 24 hours" output.

## Future expansions

- **Reply-draft chaining:** identify "ready for a reply" messages, draft with the voice skill, save as Gmail draft
- **Importance learning:** track which classified-important messages actually get opened and adjust heuristics
