---
name: briefing
description: Use when the user opens this AIOS project and wants the current state - Q-priorities with deadline countdowns, last few decisions, parking-lot items due, latest /audit score. Triggers on `/briefing`, "AIOS status", "where am I", "what's going on with the AIOS", or any session-start morning equivalent. Project-scoped - does NOT scan global tasks/todo.md files (that's /get-ready's job).
---

# AIOS Briefing - project-scoped status surface

## What this skill does

Reads four already-current source files inside this project and synthesizes a terse briefing. Designed to fire alongside the global `/get-ready` (project-wide todo scan) - this one is AIOS-specific.

**Critically: this skill does NOT scan `tasks/todo.md`.** Per the onboarding intake, earlier `todo.md` experiments failed because tasks completed faster than they were logged. The AIOS uses its own source-of-truth files instead.

## Inputs (all read-only)

| File | What's read |
|---|---|
| `context/priorities.md` | Q-priorities with target dates |
| `decisions/log.md` | Last 3 decisions (reverse chronological) |
| `parking-lot.md` | Items with `Revisit at:` triggers that have arrived |
| `audits/*.md` | Most recent audit by filename date - extract score |
| (optional) `references/drive-folders.md` | Drive folder map for context |

## Execution

### Step 1: Compute deadline countdowns

For each Q-priority that has a date in `context/priorities.md`, compute days remaining from today. Highlight any priority with ≤ 7 days remaining as **URGENT**.

### Step 2: Pull last 3 decisions

Tail the `decisions/log.md` file. Get the three most recent `## YYYY-MM-DD - Short title` blocks. One-line summary each (the title, not the body).

### Step 3: Check parking-lot for due items

Read `parking-lot.md`. Find any entry with `Revisit at:` ≤ today. Surface them as *"Parking-lot due to revisit:"* lines. Skip items with future trigger dates.

### Step 4: Find latest /audit score

Glob `audits/audit-*.md`, pick the most recent by filename. Extract the `Score: NN/100` line (and the Stage label if present). Also extract the top gap from "Top 3 Gaps" section.

### Step 5: Output the briefing

Use this exact template - terse, no fluff, no em dashes:

```
# AIOS briefing - <today's date>

## Q-priorities ⏱
1. <priority 1> - <N> days remaining <URGENT if ≤ 7>
2. <priority 2> - <N> days remaining
3. <priority 3> - <N> days remaining

## Latest /audit: <score>/100 (<Stage>)
Top gap to close: <gap from audit>

## Recent decisions (last 3)
- <YYYY-MM-DD>: <title>
- <YYYY-MM-DD>: <title>
- <YYYY-MM-DD>: <title>

## Parking-lot - due to revisit
<list if any; "Nothing due" if empty>

## Default Shift
Before any task today: "To what extent could AI be leveraged here?"
```

## Critical implementation rules

1. **Read-only.** Never write to any of the input files. If a file is missing, note it inline (*"context/priorities.md missing - Q-priorities unknown"*) but don't fail.
2. **Terse.** This is a briefing, not a report. Each priority is one line. No paragraph blocks.
3. **No em dashes** (the owner's stated dislike, same rule as everywhere else).
4. **No restating.** Don't say *"Here's your briefing:"* or *"Based on your files:"* - just output the template.
5. **Date format:** Always `YYYY-MM-DD`. Never relative ("yesterday") because briefings get rendered on dates the user can't predict.

## When NOT to run this

- When user asks for project-wide task scan → that's `/get-ready` (global, scans every project's `tasks/todo.md`).
- When user wants a deep audit → that's `/audit` (Four Cs scoring, much heavier).
- When user wants to know what skill to build next → that's `/level-up` (Friday ritual).

This skill is intentionally lightweight - fires daily via SessionStart hook, must be fast and read-only.

## Verification

1. Run `/briefing` cold (no prior context).
2. Output should match the template above.
3. Each priority countdown should be correct against today's date.
4. The score from the newest `audits/audit-*.md` should appear.
5. Last 3 decisions should match `decisions/log.md` tail.
6. Output ends with the Default Shift question - no commentary after.

## Future expansions (out of scope for v1)

- Pull latest `Daily Pulse - YYYY-MM-DD` Doc URL from Drive (after Phase 11 lands)
- Pull latest `AI News - YYYY-MM-DD` Doc URL from Drive (after Phase 10 lands)
- Compare current /audit score to previous to show trajectory (+/- since last week)
- Surface specific in-flight `/level-up` artifacts from `decisions/log.md`
