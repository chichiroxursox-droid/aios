# aios

A personal AI operating system built on Claude Code: project skills, a session-start hook, local `launchd` jobs that run Claude headlessly, and cloud routines, wired so the useful parts of a day show up without being asked for. Built with Claude Code.

This is a sanitized extract of a private system I use every day. The private data layer (my context files, decisions, email-derived commitments, course material) is not here.

## Why it exists

Every morning started with the same tab tour: Gmail, the LMS, group chats, a campus events site, GitHub. Commitments made over email had no tracker, so they lived in my head. The AIOS turns that into one email at 8am, a tracked list of commitments with revisit dates, and a weekly habit of automating one more thing.

## Architecture

The layout follows the Four Cs from Nate Herk's AIS-OS template: Context (what it knows), Connections (what it reaches), Capabilities (skills), Cadence (what runs without being asked). Cadence is the layer this repo is mostly about.

```
 CADENCE (when)                     CAPABILITY (what)                 OUTPUT (where I look)

 SessionStart hook ───────────────▶ /get-ready + /briefing ─────────▶ first reply in the session
   fires when Claude Code opens       read-only, cheap

 launchd on the Mac (needs local OAuth + .env)
   07:00 run-ai-news.sh ──────────▶ claude --print → ai-news ───────▶ wiki digest
   08:00 run-daily-pulse.sh ──────▶ claude --print → /daily-pulse ──▶ one email to me
                                        ▲ inlines                     + commitments → parking-lot.md
   every 60s unlock-sync.sh ──────▶ count open Reminders ──────────▶ /etc/hosts block on/off
                                        │
 cloud routines (no local creds, run while the laptop sleeps)
   06:00 changelog-watcher ───────▶ git push → aios-cloud-feed repo ┘
   Sun   internship-watcher ──────▶ git push → aios-cloud-feed repo ┘

 manual on purpose
   evening /sundown ──────────────▶ daily-log/ ── same theme 3 days ─▶ parking-lot.md
   Friday  /level-up ─────────────▶ one new automation ─────────────▶ decisions/log.md
   weekly  /audit, /os-audit ─────▶ score + integrity report ───────▶ audits/
```

Design decisions worth calling out:

- **The hook injects an instruction, not output.** `.claude/settings.json` tells the agent which skills to run, and includes an escape hatch: if the first message is unrelated, skip the briefing. A ritual that taxes every session gets routed around.
- **Local scheduler for anything touching private accounts, cloud for the rest.** Cloud routines can't see local skills, the Google Workspace OAuth store or `.env`, so they only fetch public sources and commit markdown to a repo. The 8am job reads that repo and inlines it.
- **Runners delegate to the skill file.** The daily-pulse runner used to restate the steps in its prompt, so steps added to the skill later were silently skipped. Now the prompt says "execute every step in SKILL.md".
- **Reflection is never scheduled.** `/sundown` states it: a 10pm prompt produces fake reflection. Its absence is data too.
- **Two audits with different jobs.** `/audit` scores whether the system is good. `/os-audit` checks whether it is true: every path the routing files name still exists, nothing on disk is unrouted, and every launchd job's last exit code is 0. Its first run found both daily jobs had been failing for days.
- **Memory is tiered.** A thin `CLAUDE.md` router, references loaded on demand, an append-only decisions log, and a parking lot where each entry carries a `Revisit at:` date so `/briefing` surfaces it on that day instead of searching for it.

## Skills

| Skill | What it does |
|---|---|
| [`briefing`](.claude/skills/briefing/SKILL.md) | Session-start status: priority countdowns, last 3 decisions, parking-lot items due today, latest audit score. Read-only. |
| [`daily-pulse`](.claude/skills/daily-pulse/SKILL.md) | 8am email: last-24h Gmail triage (metadata first, bodies only for important mail), Outlook-forward detection by header, LMS due/missing, events not on the calendar, cloud-routine feeds, commitment capture. |
| [`sundown`](.claude/skills/sundown/SKILL.md) | Evening log in three questions; promotes a manual-work theme seen 3 days running to the parking lot. |
| [`level-up`](.claude/skills/level-up/SKILL.md) | Friday interview (Mindset, Method, Machine) that scopes and ships one automation, defaulting to the least autonomy that works. From the AIS-OS template. |
| [`audit`](.claude/skills/audit/SKILL.md) | Four-Cs score out of 100 with the top 3 gaps ranked by points lost times impact. From the AIS-OS template. |
| [`os-audit`](.claude/skills/os-audit/SKILL.md) | Integrity scan ([`check.py`](.claude/skills/os-audit/check.py)): dead refs, unrouted files, stale logs, failing launchd jobs. Reports, never fixes. |
| [`notes-sync`](.claude/skills/notes-sync/SKILL.md) | Fills gaps in a class-notes Google Doc from the class recording. Inserts are anchored to paragraph IDs, batched by descending index, and guarded by `requiredRevisionId`. |
| [`study-prep`](.claude/skills/study-prep/SKILL.md) | Practice quiz and study guide from real course material, published as one page. [`build.py`](.claude/skills/study-prep/build.py) rejects questions without a source, duplicate stems, and answer keys where one letter holds over 40%. |
| [`etf-board`](.claude/skills/etf-board/SKILL.md) | Weekly review for a simulated ETF contest: compliance check first, four advisor personas, a mandatory dissent section, one verdict. |

## Running Claude Code under launchd

`scripts/run-*.sh` call `claude --print` headlessly; `launchd/*.plist` schedule them. Each fix below cost real debugging time and is commented where it lives.

| Symptom | Cause | Fix |
|---|---|---|
| Job exits 1 with `EINTR`, no other output | `claude --print` with no stdin under launchd | `< /dev/null` on every `claude --print` line |
| Claude crashes partway through a run | launchd's default soft fd limit is 256 | `ulimit -n 10240` at the top of the runner |
| Every `gws` call fails with `invalid peer certificate: UnknownIssuer` while `curl` works | the Rust TLS stack sees an empty keychain trust store under launchd | `export SSL_CERT_FILE=/etc/ssl/cert.pem` |
| Job fires, exit 126, nothing happens | macOS privacy (TCC) blocks launchd from executing scripts under `~/Desktop` | launchd runs copies in `~/.local/bin/aios/`; re-copy after editing |
| `claude: command not found` | launchd jobs get a minimal environment | absolute `CLAUDE_BIN`, plus `PATH` and `HOME` in the plist |
| Editing the plist changes nothing | the loaded copy is cached | `launchctl unload` then `launchctl load` (there is no reload) |
| Log has only a start line and hours of elapsed time | the Mac slept mid-run | check `pmset -g log` before calling it a hang |
| `API Error: 400 ... version X or newer is required` | the pinned CLI binary fell behind the model | update the CLI, and monitor for the artifact, not just the job |

Common commands:

```bash
launchctl list | grep com.you.aios          # PID, last exit code, label
launchctl start com.you.aios.daily-pulse    # force a run now (smoke test)
tail -f ~/.local/share/aios-logs/daily-pulse-$(date +%F).log
```

Jobs don't fire while the Mac is fully asleep; they run on the next wake.

## Repo scanner

[`tools/repo-scanner/`](tools/repo-scanner/) vets trending GitHub repos before the daily AI-news digest lists them. That lane turned out to carry a star-farmed malware campaign aimed at Claude Code users, and the campaign changed its loader three times (plaintext C2, then XOR-encrypted int arrays, then plaintext process hollowing). `scan.py` matches shapes and behavior together (exec-on-decode, one-line XOR loops, IPv4 URL literals, Windows injection APIs, install hooks) and never runs repo code. `diffscan.py` re-scans only files changed since the last scanned commit. `test_scan.py` checks every detector against a positive control. Indicators are kept separately in [`IOCS.md`](tools/repo-scanner/IOCS.md).

## Reminders gate

`scripts/unlock-sync.sh` runs every 60 seconds and blocks YouTube in `/etc/hosts` while a Reminders list named `Unlock` has open tasks; `unlock-daily.sh` adds a fixed morning routine at 8:55. The hosts edit goes through a root-owned helper (`aios-youtube-block`) with a fixed `PATH`, called via a sudoers rule limited to the exact arguments `on` and `off`. If Reminders can't be read, the hosts file is left as it is (fails neither open nor closed). The daily-pulse email only suggests tasks for the list; it never adds them.

## Run it locally

Needs macOS, Claude Code, Python 3. The Google-facing skills need the `gws` Google Workspace CLI authenticated; the cloud-feed steps need `gh`.

```bash
git clone <this repo> ~/aios && cd ~/aios

# pieces that run with no accounts
python3 -I tools/repo-scanner/test_scan.py
python3 .claude/skills/study-prep/build.py .claude/skills/study-prep/example   # writes example/example.html
python3 .claude/skills/os-audit/check.py .

# cadence layer
mkdir -p ~/.local/bin/aios ~/.local/share/aios-logs
cp scripts/run-daily-pulse.sh scripts/run-ai-news.sh ~/.local/bin/aios/
sed "s/YOU/$USER/g" launchd/com.you.aios.daily-pulse.plist > ~/Library/LaunchAgents/com.you.aios.daily-pulse.plist
launchctl load ~/Library/LaunchAgents/com.you.aios.daily-pulse.plist
```

Then fill in `CLAUDE.md` (a template with the structure and rules, no personal content), create `context/`, `decisions/log.md` and `parking-lot.md`, and replace the `<you>` / `<your-email>` / `<DRIVE_FOLDER_ID>` placeholders in the skills.

## Status and limits

- This is an extract of a private, daily-used system. The private data layer is omitted, so the skills reference files you have to create yourself.
- Not included: the fetchers that read the school inbox, LMS, group chats, campus events and social posts (they ride my own logged-in sessions), the global `ai-news` and `get-ready` skills, and the cloud routine prompts.
- Headless runs use `--permission-mode bypassPermissions` and read email and chat text. That text is not labeled as untrusted in the prompts; the safeguards are procedural (Gmail is read-only, events are never auto-added to the calendar, the email goes only to me). Labeling retrieved content is the known gap.
- macOS only for the scheduler and the Reminders gate.
- The strategic audit scored 53/100 on day one and 88/100 the next day.

## Credits

Built on Nate Herk's AIS-OS template (MIT). The `audit` and `level-up` skills and the `CLAUDE.md` structure come from it. The Three Ms of AI is a trademark of Nate Herk. Licensed MIT, see [LICENSE](LICENSE).
