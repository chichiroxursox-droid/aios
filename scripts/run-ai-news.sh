#!/bin/bash
# Daily ai-news runner. launchd fires it at 7am, an hour before daily-pulse, which
# inlines the digest's Top Stories. The ai-news skill itself is a global skill
# (~/.claude/skills/ai-news) and is not part of this extract.
# launchd runs the copy at ~/.local/bin/aios/ (TCC blocks scripts under ~/Desktop).
set -euo pipefail

# launchd's default soft fd limit is 256, which crashes `claude --print` mid-run.
ulimit -n 10240

PROJECT="$HOME/aios"
CLAUDE_BIN="$HOME/.local/bin/claude"
TODAY="$(date +%Y-%m-%d)"
LOG_DIR="$HOME/.local/share/aios-logs"
LOG_FILE="$LOG_DIR/ai-news-$TODAY.log"

mkdir -p "$LOG_DIR"
cd "$PROJECT"

PROMPT="Run the ai-news skill end-to-end for today ($TODAY). Scrape AI news and write the wiki MD file. No Google Doc: the 8am daily-pulse email picks up the Top Stories section. Confirm the wiki file landed."

{
  echo "===== ai-news run start: $(date -Iseconds) ====="
  # `< /dev/null`: with no stdin under launchd, `claude --print` dies with EINTR.
  "$CLAUDE_BIN" --print --permission-mode bypassPermissions "$PROMPT" < /dev/null
  echo "===== ai-news run end: $(date -Iseconds) ====="
} >> "$LOG_FILE" 2>&1
