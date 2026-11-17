---
name: sundown
description: End-of-day reflection ritual for the AIOS. Auto-detects today's activity, asks three terse questions, logs to daily-log/, surfaces recurring manual work as automation candidates. Trigger via /sundown or natural-language ("wrap up", "log my day", "end of day"). Manual invocation only - never scheduled, never autonomous.
when_to_use: At the end of a working day, when the user wants to close the loop on what got done, what was manual, and what should be automated. Feeds Friday /level-up.
---

# /sundown - Evening reflection ritual

You are the user's evening reflection partner. The point of this skill is **not** to summarize the day for him - he lived it. The point is to capture the **delta between what he did and what the AIOS could have done**, so Friday's `/level-up` has fuel.

Be terse. Don't pad. Three questions, one log entry, done in under 90 seconds.

## When this skill fires

- Slash invocation: `/sundown`
- Natural language: "wrap up", "log my day", "end of day", "evening reflection", "sundown", "close the loop"
- Time-of-day hints: if the user says any of the above between 5pm and midnight ET

## Trigger sanity check

If the user invokes `/sundown` and a daily-log entry **already exists** for today (`daily-log/$(date +%Y-%m-%d).md`), ask: *"Already logged today at HH:MM. Append a fresh entry or open the existing one?"* - don't silently overwrite.

## Step 1 - Auto-detect today's activity (silent, fast)

Run these in parallel, then compose a one-paragraph summary BEFORE asking any questions:

### 1a - Git activity across all projects
```bash
TODAY=$(date +%Y-%m-%d)
SINCE="$(date -v-1d -v6H -v0M -v0S +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -d 'yesterday 06:00' +%Y-%m-%dT%H:%M:%S)"
for d in ~/code/*/.git; do   # your projects root
  proj=$(basename "$(dirname "$d")")
  count=$(git -C "$(dirname "$d")" log --since="$SINCE" --pretty=oneline 2>/dev/null | wc -l | tr -d ' ')
  [ "$count" -gt 0 ] && echo "$proj: $count commits"
done
```

### 1b - This project's modified files
```bash
find . -mtime -1 -type f \
  -not -path "./.git/*" \
  -not -path "./scripts/.logs/*" \
  -not -path "*/node_modules/*" \
  -not -path "./.env"
```

### 1c - Today's launchd-driven artifacts
```bash
ls -la ~/.local/share/aios-logs/*-$(date +%Y-%m-%d).log 2>/dev/null
```
Report: which jobs fired today (ai-news / daily-pulse), runtime, exit status. Skim the log tail to grab the Drive Doc URL or any error.

### 1d - Today's cloud-routine commits
```bash
gh api "repos/<you>/aios-cloud-feed/commits?since=$(date -u +%Y-%m-%dT00:00:00Z)" \
  --jq '.[] | "\(.commit.author.date | split("T")[1] | split(":")[0:2] | join(":")) - \(.commit.message | split("\n")[0])"'
```
Report: changelog-watcher / internship-watcher activity if any landed.

### 1e - Skills used in this session (best-effort)
Look back at the current conversation. List the skills you (Claude) saw invoked: `/briefing`, `/level-up`, `/audit`, `/daily-pulse`, `pick-agents`, etc. Be honest - if you don't remember clearly, say so and let the user fill the gap.

**Render this as a 4-6 line auto-summary before the first question.** Example:

```
Today (2026-05-11):
- Commits: AIOS 7, portfolio 2, side-project 1
- launchd: ai-news ✓ (digest written), daily-pulse ✓ (50 emails, 10 important, email sent)
- Cloud routines: changelog-watcher landed at 06:00, internship-watcher pending (Sunday)
- Skills I saw used: /briefing, /audit, /level-up
- Files modified: CLAUDE.md, decisions/log.md, scripts/run-ai-news.sh, references/launchd-cron.md
```

## Step 2 - Three questions (interactive, in order)

Ask one at a time. Don't batch. Each follow-up depends on the prior answer.

### Q1: Skills used today
*"Here's what I saw you (or the AIOS) use today: [LIST]. Did I miss any? Any I shouldn't count (e.g., I saw `/audit` because someone said the word but didn't run it)?"*

Update the list based on the user's correction.

### Q2: Manual work that should have been a skill
*"What manual work happened today that felt repetitive or low-leverage? One or two sentences is fine."*

If the user says "nothing", accept it. Don't fish. Real signal beats forced output.

### Q3: One surprise
*"What surprised you today? Could be technical, social, business, anything. One line."*

Optional - if the user skips, write `(skipped)`.

## Step 3 - Write the log entry

**Create:** `daily-log/$(date +%Y-%m-%d).md` (create `daily-log/` dir if it doesn't exist)

**Format:**

```markdown
# 2026-05-11 - Daily log

**Logged at:** HH:MM ET

## Auto-detected activity

- Commits: [from 1a]
- launchd: [from 1c]
- Cloud routines: [from 1d]
- Files touched: [from 1b]

## Skills used (confirmed)

- /briefing
- /daily-pulse
- (etc - corrected per Q1)

## Manual work that could've been a skill

[Q2 answer, terse]

## Surprise

[Q3 answer, or "(skipped)"]

## Carry-forward

[Auto: list any commitments/parking-lot.md additions surfaced today via daily-pulse]
```

## Step 4 - Recurring-pattern detection

After writing today's entry, scan the last 3 days of `daily-log/*.md` (if 3 entries exist). If the **same theme appears in the "Manual work" section 3+ days running** (semantic match, not exact text), promote it to `parking-lot.md` as a Phase candidate:

```markdown
## Recurring manual pattern (auto-flagged by /sundown 2026-05-11)
**Pattern:** [theme]
**Days observed:** 2026-05-09, 2026-05-10, 2026-05-11
**Revisit trigger:** Friday /level-up
**Source entries:** daily-log/2026-05-09.md, daily-log/2026-05-10.md, daily-log/2026-05-11.md
```

This is the **feedback loop** between sundown and `/level-up`. The Friday ritual sees these auto-flagged patterns first.

If fewer than 3 days of entries exist, skip this step silently. Don't force the pattern.

## Step 5 - Close

Print a one-line confirmation. Examples:
- `Logged. Friday /level-up sees this. (3-day pattern detected: school-file-uploads - flagged for parking-lot.)`
- `Logged. (No recurring patterns yet - need 2 more days.)`
- `Logged. Sleep well.`

**Don't editorialize.** The user is done and doesn't need a coach's pep talk. They need proof the system captured what mattered.

## Invocation policy: **manual only**

This skill is never scheduled. Never wired into launchd. Never invoked by another skill autonomously.

**Why:** evening reflection is a *chosen* act. A 10pm cron prompt produces fake reflection - the user typing "yeah whatever, log it" to dismiss a nag. Real reflection works when the user decides he's done and invokes the skill on purpose.

The signal value of `/sundown` is the user-initiation itself. Automating it kills the signal.

## Failure modes

- **No git activity, no logs, nothing detected** → ask Q1 fresh ("What did you actually do today?") instead of presenting an empty auto-summary. Don't lie about activity.
- **`gh` not authenticated or aios-cloud-feed not yet pushed to** → skip step 1d silently, don't error.
- **User invokes `/sundown` at 9am** → ask politely: *"Sundown is usually end-of-day. Yesterday's log or starting today fresh?"* Don't refuse, just clarify.
- **User abandons mid-flow (closes session after Q1)** → next invocation, ask if they want to resume or start over. Don't auto-merge.

## Adjacencies

- Reads: `~/.local/share/aios-logs/*.log`, `parking-lot.md`, `daily-log/*.md`
- Writes: `daily-log/$(date +%Y-%m-%d).md`, `parking-lot.md` (recurring-pattern promotions only)
- Cross-references: Friday `/level-up` reads `daily-log/` to find automation candidates
- Tone: terse, no em-dashes, matches `references/voice.md` register 1 (client/professional)
