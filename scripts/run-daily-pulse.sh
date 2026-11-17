#!/bin/bash
# Daily-pulse runner. launchd fires it at 8am (launchd/com.you.aios.daily-pulse.plist).
# launchd runs the COPY at ~/.local/bin/aios/, not this file: macOS privacy (TCC)
# blocks launchd from executing scripts under ~/Desktop (exit 126). Re-copy after editing.
set -euo pipefail

# launchd's default soft fd limit is 256, which crashes `claude --print` mid-run.
ulimit -n 10240

# Under launchd, gws (Rust) sees an empty keychain trust store and every call fails
# with "invalid peer certificate: UnknownIssuer". Point it at the system bundle.
export SSL_CERT_FILE=/etc/ssl/cert.pem

PROJECT="$HOME/aios"                 # project root: skills are discovered from its .claude/
CLAUDE_BIN="$HOME/.local/bin/claude" # absolute path: launchd's PATH is minimal
TODAY="$(date +%Y-%m-%d)"
LOG_DIR="$HOME/.local/share/aios-logs"
LOG_FILE="$LOG_DIR/daily-pulse-$TODAY.log"

mkdir -p "$LOG_DIR"
cd "$PROJECT"

# The skill file is the source of truth for WHAT to do. This prompt used to
# re-specify the steps, which silently skipped any step added later. Delegate
# instead, so new steps run without editing this runner.
PROMPT="Run the daily-pulse skill for today ($TODAY). Open .claude/skills/daily-pulse/SKILL.md and execute EVERY step in it in order, including steps added after this runner was written. Do not skip a step unless that step's own instructions tell you to skip it. If a data source fails, note it inline and continue with the rest."

{
  echo "===== daily-pulse run start: $(date -Iseconds) ====="
  # `< /dev/null`: with no stdin under launchd, `claude --print` dies with EINTR.
  "$CLAUDE_BIN" --print --permission-mode bypassPermissions "$PROMPT" < /dev/null
  echo "===== daily-pulse run end: $(date -Iseconds) ====="
} >> "$LOG_FILE" 2>&1
