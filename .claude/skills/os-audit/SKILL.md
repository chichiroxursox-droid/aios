---
name: os-audit
description: Use for a mechanical integrity audit of the AIOS - checks whether the routing table still matches reality (dead refs, unrouted files, stale feeds, failing crons). Triggers on `/os-audit`, "audit my OS", "is my routing still true", "check for drift/dead links", "OS integrity check". Complements /audit (which scores strategy via the Four-Cs); this one checks facts on disk. Read-only - reports, never fixes.
---

## What this skill does

Nate Herk's "have AI audit itself" hack. `/audit` scores *strategy* (Four-Cs); this scores *truth* - does every path the routing files claim still exist, has disk grown past the routing table, are the data feeds fresh, are the crons alive. Catches the poisoning / bloat / confusion / clash failures a strategic audit sails past.

**Read-only. Never fix, rename, or delete during the audit.** Produce a report + a fix list that awaits approval, exactly like `/audit`.

## When NOT to run

- Strategic "is my AIOS working / what should I improve" → that's `/audit` (Four-Cs).
- Actually applying fixes → run this first for the report, then apply with approval.

## Execution

### 1. Run the scanner

```bash
python3 .claude/skills/os-audit/check.py
```

It prints three sections: **ROUTING INTEGRITY** (dead refs in CLAUDE.md / connections.md / MEMORY.md), **INDEX TRUTH** (top-level files on disk that no router mentions), **FRESHNESS** (mtimes of decisions/parking-lot, daily-log presence, launchd cron exit codes, log error scan, git untracked/modified counts).

### 2. Interpret - separate real findings from noise

The scanner is deliberately conservative but still over-flags. Before reporting, sanity-check each:

- **Dead ref that's really a template/placeholder** (`<id>`, `{tool}`, `YYYY`) → the scanner should skip these; if one slips through, ignore it.
- **Bare-filename ref** (e.g. `about-me.md`) → the real markdown link target may be valid even if the backtick label doesn't resolve. Check the actual `](...)` target before calling it dead.
- **`todo.md`** → AIOS deliberately doesn't use the tasks/todo.md convention. Expected, not a finding.
- **Unrouted committed files** (README, LICENSE, intentional docs) → only flag unrouted files that are genuinely orphaned clutter.
- **Cron EXIT n (FAIL)** → real. Read the newest `~/.local/share/aios-logs/<job>-<today>.log`; look for `EINTR` (needs `< /dev/null` on the `claude --print` line, see the README section on launchd), auth expiry, or file locks.

### 3. Score + write the report

Score each dimension 🟢/🟡/🔴. Write to `audits/os-integrity-YYYY-MM-DD.md` (create `audits/` if absent - it's gitignored, local-only). Include: scoreboard table, findings grouped by dimension, and a **fix list (await approval)** mapping each fix to the failure mode it kills (poisoning / bloat / confusion / clash) and rough effort.

### 4. Offer, don't act

End with "Here are N fixes. Apply which?" - never auto-fix. Applying is a separate, approved step.

## Notes

- The parser rules in `check.py` (strip `bash `/`node ` command prefixes, skip glob/placeholder tokens, resolve sibling `../` paths) are what separate real findings from false positives. If you find a new false-positive class, tighten `check.py` rather than eyeballing it each run.
- Cron + log checks are AIOS-specific (launchd labels starting with `LABEL_PREFIX` in `check.py`, logs in `~/.local/share/aios-logs`); harmless no-ops on other projects.
- Good `/level-up` durability candidate: a weekly cron that runs this and only pings if anything is 🔴.
