#!/bin/bash
# AIOS Unlock: daily 8:55am (launchd com.you.aios.unlock-daily), add the morning
# routine to the Reminders list "Unlock", which gates YouTube + phone apps until
# all are checked off. A task still open from a missed day is not added twice.
# Runs the ~/.local/bin/aios copy (re-copy after editing). Optional arg = list name
# (for testing). Setup: README, "Unlock gate".

osascript - "${1:-Unlock}" <<'EOF'
on run argv
  set tasks to {"1. Reading (20 min)", "2. Language practice (20 min)", "3. Apply to an internship", "4. Deep work on a project (60 min)"}
  set nine to current date
  set time of nine to 9 * hours
  tell application "Reminders"
    set l to list (item 1 of argv)
    repeat with t in tasks
      set n to contents of t
      if (count (reminders of l whose name is n and completed is false)) = 0 then
        set r to make new reminder at end of l with properties {name:n, allday due date:nine}
        -- ponytail: one 9am nudge on task 1 only, not five at once
        if n starts with "1." then set remind me date of r to nine
      end if
    end repeat
  end tell
end run
EOF
