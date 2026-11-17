#!/bin/bash
# AIOS Unlock: every 60s (launchd com.you.aios.unlock), block YouTube while the
# Reminders list "Unlock" has unchecked tasks. Lives outside ~/Desktop because
# launchd cannot exec scripts there (TCC, exit 126). Hosts edits go through the
# root-owned helper via sudo -n. Setup + override: README, "Unlock gate".

open=$(osascript -e 'tell application "Reminders" to count (reminders of list "Unlock" whose completed is false)' 2>&1)

# ponytail: on any Reminders error leave hosts as-is (fail neither open nor closed)
case "$open" in
  ''|*[!0-9]*)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Reminders read failed, hosts unchanged: $open" >&2
    exit 1 ;;
esac

[ "$open" -gt 0 ] && state=on || state=off
sudo -n /usr/local/sbin/aios-youtube-block "$state"
