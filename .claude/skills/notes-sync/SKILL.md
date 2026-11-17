---
name: notes-sync
description: Use to cross-reference the user's class notes against the class recording for that session, fill in what was missed, and flag other important things mentioned. Triggers on `/notes-sync <course code> [date]`, "sync my notes with the transcript", "check my notes against the recording", "did I miss anything in [course] notes".
argument-hint: "[course code] [date]"
---

# Notes Sync - fill class-note gaps from the class recording

## What this skill does

You take notes in a running Google Doc per course (one doc, a new dated section each class day) and also record the class with a local recorder that writes one folder per session: `$RECORDER_DIR/transcripts/YYYY-MM-DD_*/` holding `transcript.md` and `meta.json`. (The author uses his own recorder app; any tool with that output shape works.) This skill reads the transcript for a given class, compares it against what you actually wrote in your notes for that date, and **integrates what's missing directly into your existing notes** - extending an existing bullet's sentence with the missing clause, or inserting a new sibling bullet right after the most relevant existing one, matching that bullet's own formatting exactly. Logistics-type content that doesn't belong inline (deadlines, announcements, asides) still gets appended as its own small labeled block at the end.

**The point:** close the gap between "what got said in class" and "what actually made it into notes," in a way that reads like you filled it in yourself, without re-listening to the recording.

**How the integration is safe:** every insertion is anchored to a specific existing paragraph identified by this skill's own read of the doc (never a guessed or model-invented location), and targets `location.index = <paragraph's own endIndex> - 1` - strictly *inside* that paragraph's own range, before its trailing newline. Splitting a paragraph there always inherits that paragraph's own list/bullet formatting (verified empirically - see Step 8). No existing character is ever deleted or overwritten; only new characters get inserted. When several insertions land in the same `batchUpdate` call, they're ordered by **descending index** so an earlier (higher-index) insertion never shifts the position of a later (lower-index) one still to be applied.

## When NOT to run this

- If you didn't record that class (no matching transcript folder) - say so, don't fabricate notes from nothing.
- If a piece of content can't be confidently anchored to a specific existing paragraph AND doesn't fit the logistics/flagged bucket either - don't force it in. Hold it out and show it in chat instead of guessing at a location.
- This is not a transcription-cleanup tool - it doesn't touch `transcript.md` or the audio files, only reads them.

## Execution

### Step 1: Resolve arguments

Parse `<course code>` (required, e.g. `CS 101` - match case-insensitively against `code` or `name` in the schedule) and `[date]` (optional, defaults to today; accepts `today`, `yesterday`, or `YYYY-MM-DD`, always resolved in America/New_York).

### Step 2: Resolve the course's scheduled time window

Read your schedule file (`schedule.json`: one entry per course with `code`, `name`, `days`, `start`, `end`) for the matching course. Confirm the target date's weekday is in that course's `days` array - if not, say there's no scheduled class for that course on that date and stop. Otherwise capture `start`/`end` (e.g. `"09:50"`–`"11:30"`).

### Step 3: Find the matching transcript folder

List `$RECORDER_DIR/transcripts/` for folders matching `YYYY-MM-DD_*` for the target date. Each has a `meta.json` with `started_at`/`ended_at` as Unix epoch seconds - convert to America/New_York and compare against the course's scheduled window (±15 min buffer, since class doesn't start/end exactly on the recording).

- Exactly one folder overlaps → use it.
- Zero overlap → stop: *"No transcript found overlapping {course} on {date}."*
- More than one overlaps (recording wasn't stopped between back-to-back classes, or multiple separate recordings that day) → don't guess. List the candidates (title, start–end time) and ask which one, or confirm using all of them.

### Step 4: Extract just this class's segment

Read `transcript.md` from the selected folder. Lines look like:

```
**[17:27:57] You:** ...
```

Parse the `[HH:MM:SS]` timestamp on each line (local time, per the `_YYYY-MM-DD HH:MM_` line at the top of the file) and keep only lines falling inside the course's scheduled window ± the same buffer used in Step 3. **This is the fix for back-to-back recordings** - if the transcript spans two classes because the recorder wasn't stopped/restarted, this slices out only the target class's portion, discarding the rest. If zero lines fall in the window after slicing, stop and report that rather than guessing from the whole transcript.

### Step 5: Find or create the notes Doc

Read `references/drive-folders.md` for the current term's notes folder ID (`<DRIVE_FOLDER_ID>`) - never hardcode it.

```bash
gws drive files list --params '{
  "q": "'"'"'<folderId>'"'"' in parents and mimeType = '"'"'application/vnd.google-apps.document'"'"' and (name contains '"'"'<course code>'"'"' or name contains '"'"'<course name>'"'"')",
  "fields": "files(id,name,modifiedTime,webViewLink)"
}'
```

- One match → use it.
- Multiple matches → ask which one (this shouldn't normally happen for a "one doc per course" setup, but don't silently pick).
- Zero matches → no notes doc exists for this course yet. Create one with `gws docs documents create --json '{"title":"<course code> - <course name> Notes"}'`, then move it into that folder with `gws drive files update --params '{"fileId":"<id>","addParents":"<folderId>"}'` (fileId + addParents are query params on the Drive `files.update` endpoint, not standalone flags), and treat the whole thing as "no notes taken" per Step 6 - the entire day's section will be generated from the transcript.

### Step 6: Read the doc's paragraph structure

`gws docs documents get --params '{"documentId": "<id>"}'` and walk `body.content` (or `tabs[0].documentTab.body.content` if `tabs` is present - same structure, single-tab docs mirror both). For every element with a `paragraph` key, extract:

- `startIndex` / `endIndex` (exact character offsets - this is what makes anchored insertion safe)
- plain text (concatenate `paragraph.elements[].textRun.content`)
- `paragraphStyle.namedStyleType` (heading/subtitle vs normal text)
- `paragraph.bullet` (present = it's a list item; carries `listId` + optional `nestingLevel`)

Also capture the top-level `revisionId` from the same `documents.get` response - Step 8 uses it as a write guard.

Assign each paragraph a short stable ID in reading order (`P1`, `P2`, ...) - these IDs, not the text itself, are what anchor every edit, so there's no risk of the model mismatching similar-looking lines.

If any paragraph's text matches a date-header pattern (`August 26, 2026`, `Aug 26`, `2026-08-26`, `8/26`, etc.), scope everything below (Steps 7-8) to the paragraph range between the target date's own header and the next date header (or end of doc) - don't let content anchor into a different day's section. **The author's notes docs had no date headers yet** (checked 2026-08-26 - each doc held one undated block), so until dated sections exist, treat the whole doc as the current/only section. This scoping logic is forward-compatible for whenever dated sections do exist.

### Step 7: Generate the integration plan

Run `claude -p` using the **subscription-auth env-strip pattern** (drop API-key variables so the CLI uses the logged-in subscription instead of billing an API key):

```python
env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
# claude -p "<prompt>"
```

Feed it the scoped paragraphs from Step 6 as `{id, text}` pairs (in order) plus the sliced transcript segment from Step 4. Ask for a structured plan (JSON) with two buckets:

1. **Inline integrations** - content clearly covered in the transcript but missing from the notes, each tied to the existing paragraph it belongs with. For each: `{"anchor_id": "P7", "mode": "extend" | "new_bullet_after", "text": "..."}`.
   - `extend`: a short clause to append onto the end of that paragraph's existing sentence (no leading capital, reads as a continuation - e.g. `" - due Sept 24 at 11:59pm"`).
   - `new_bullet_after`: a full new bullet's worth of text, inserted as a sibling immediately after that paragraph.
   - The model must only reference `anchor_id`s it was actually given. If nothing in the existing notes is topically close enough to anchor a piece of content, don't force an anchor - drop it into the logistics bucket instead (bucket 2) or, if it's genuinely neither, list it separately as "couldn't place."
   - **Only bullet or normal-text paragraphs are valid anchors** - when building the `{id, text}` list for the prompt, mark heading/subtitle paragraphs as context-only (or omit their IDs entirely). An insertion inherits its anchor's formatting, so a `new_bullet_after` anchored to a SUBTITLE topic header would render as another subtitle, not a bullet. To add the first bullet under a heading, anchor to the heading's *last existing bullet* instead - or if the heading has no content yet, treat that item as "couldn't place."
   - **Validate the returned plan before applying it:** parse the JSON, drop any entry whose `anchor_id` wasn't in the prompt, whose anchor is a heading, or whose `mode` isn't one of the two allowed values. Dropped entries go to "couldn't place," never get a guessed location.
2. **Logistics / flagged** - deadlines, announcements, assignment mentions, asides. These don't need an anchor; they're appended as their own block (Step 9).

Never invent content not present in the transcript segment.

### Step 8: Apply the inline integrations

Map each `anchor_id` from Step 7 back to its real `startIndex`/`endIndex` from Step 6 (deterministic lookup - no fuzzy text matching needed since Step 6 assigned the IDs). For each op, compute the insertion index:

- Both `extend` and `new_bullet_after` target `location.index = <anchor paragraph's endIndex> - 1` - strictly inside the anchor's own range, before its trailing `\n`.
- `extend` text is inserted as-is (no leading `\n`).
- `new_bullet_after` text is inserted as `"\n" + text` (the leading `\n` creates the new paragraph boundary; the anchor's own trailing `\n` becomes the new paragraph's terminator - this is what makes it inherit the anchor's bullet formatting).
- If both an `extend` and one or more `new_bullet_after` share the same `anchor_id`, combine them into a **single** insertText for that anchor (extend clause first, then each new bullet as its own `"\n" + text`) so there's only one op per real index.

Sort the resulting per-anchor ops by **descending index** and issue them as one `documents.batchUpdate` call, guarded by the `revisionId` captured in Step 6 so the write fails cleanly if the doc changed between read and write (e.g. you have it open and are typing):

```json
{
  "requests": [
    {"insertText": {"location": {"index": <higher index>}, "text": "..."}},
    {"insertText": {"location": {"index": <lower index>}, "text": "..."}}
  ],
  "writeControl": {"requiredRevisionId": "<revisionId from Step 6>"}
}
```

If the call fails with a revision mismatch, re-run Steps 6-8 from a fresh read - never retry with the stale indices.

**Build the `--json` body programmatically** (Python `json.dumps` + argv-list subprocess, no shell) - never by interpolating the model's text into a shell string. Inserted text contains quotes, apostrophes, and newlines; hand-quoted bash here is a corruption bug waiting to happen.

This exact approach (extend + new-bullet-after, descending-index batching, index math) was empirically validated against a disposable scratch Google Doc on 2026-08-26 before being written into this skill - confirmed both operations correctly inherit the anchor paragraph's bullet/list formatting and don't corrupt surrounding content.

### Step 9: Append the logistics/flagged block

Compose the bucket-2 content from Step 7:

```
### Also mentioned in class
{flagged content, or skip this step entirely if the bucket is empty}
```

Append via `gws docs +write --document <id> --text "<content>"`. Like the rest of this project's Docs tooling (see `daily-pulse` skill), `+write` inserts plain text - `###` will appear as literal characters, not native heading style. Known limitation, not a bug.

### Step 10: Verify integrity

Re-fetch the doc (`documents get`) and re-extract its plain paragraph text. Confirm:

- Every original paragraph's text (from Step 6, minus what Step 8 deliberately extended) still appears intact and in the same relative order - nothing got deleted or scrambled.
- The new content actually landed where intended (spot-check a couple of anchors).

If anything looks off, stop and say plainly what happened rather than reporting success - don't paper over a bad write.

### Step 11: Report back

```
Notes synced - {course code}, {date}
{N} bullets extended, {M} new bullets inserted inline, {K} logistics items appended
Doc: {webViewLink}
```

If some content couldn't be confidently placed (Step 7's "couldn't place" list), show it in chat instead of guessing.

## Critical implementation rules

1. **Anchor every insertion to a real paragraph ID from Step 6.** Never let the model invent or approximate an index - IDs are assigned deterministically by this skill, not by the model.
2. **Insertions only, never deletions or overwrites.** No existing character is ever removed or replaced. If a piece of content doesn't clearly belong anywhere, leave it out rather than force-editing something existing.
3. **Descending-index batching within a single `batchUpdate` call.** Never issue ascending-order multi-insert batches - earlier insertions shift the indices of everything after them.
4. **Never hardcode the Drive folder ID.** Always read `references/drive-folders.md`.
5. **Never invent content.** Everything added must trace back to an actual line in the transcript segment.
6. **Time-slice, don't trust the whole file.** Step 4's window-based slicing is mandatory, not optional - back-to-back recordings happen.
7. **Read-only on the transcript and audio.** Never modify `transcript.md`, `meta.json`, or the `.wav` files.
8. **Always verify after writing (Step 10).** A batchUpdate index bug is silent until you check.

## Error handling

| Failure | Response |
|---|---|
| No transcript folder for that date | "No transcript found for {course} on {date}." Stop. |
| Transcript folder found but no lines overlap the class window | "Found a recording that day, but none of it overlaps {course}'s scheduled time ({start}–{end})." Stop. |
| Multiple transcript folders overlap | List candidates (title, start–end), ask which to use. |
| No notes Doc found for the course | Create one fresh (Step 5), generate the full day's section from transcript (nothing to anchor to yet, so this is closer to plain append for that first pass). |
| Multiple notes Docs match the course name | Ask which one - don't guess. |
| Step 7 can't confidently anchor a piece of content | Don't force it. Show it in chat as "couldn't place" instead. |
| Step 8 batchUpdate rejected for revision mismatch | Doc changed between read and write. Re-run Steps 6-8 from a fresh read; never retry stale indices. |
| Step 10 verification finds something off | Stop, report exactly what looks wrong, don't claim success. |
| `gws auth status` shows invalid token | Tell the user to run `gws auth login --services drive,docs`. Don't auto-run (browser interactive). |

## Verification

1. Manually invoke `/notes-sync CS 101` (or any course with a real recent transcript + notes doc).
2. Confirm it correctly identifies the right transcript folder and slices to just that class's time window.
3. Confirm inline integrations land next to the right existing bullets, formatted as either an extended sentence or a new sibling bullet with matching indentation/bullet style - not a flat block.
4. Confirm Step 10's integrity check actually catches a deliberately-broken case (e.g. test with an intentionally wrong index once, off the real docs, to confirm the check fires).
5. Confirm nothing added is unsupported by the actual transcript text.

## Future expansions (out of scope for v1)

- **Date-section scoping in practice** - the scoping logic in Step 6 is written and ready, but untested against a real dated doc since none exist yet. Revisit once dated sections exist.
- **Format preservation for the logistics block** - Step 9 still uses plain-text `###` via `+write`. Could upgrade to a `batchUpdate` + `createParagraphBullets`/heading-style insert instead, same technique as Step 8.
- **Auto-tag recorder sessions by course** - if the recorder ever captures a course code at record time, Step 3's schedule-time matching becomes a confirmation instead of the only signal.
