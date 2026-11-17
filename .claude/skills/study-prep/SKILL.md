---
name: study-prep
description: Use when the user wants a practice quiz, study guide, drill, or exam/quiz prep for a course. Triggers on `/study-prep <course> <exam or scope> [quiz|guide|both]`, "make me a practice quiz for...", "study guide for my ... quiz", "help me prepare for my ... exam". Pulls LMS slides/pages/announcements/video transcripts plus the user's own Google Doc notes and publishes one interactive artifact.
argument-hint: <course> <exam or scope> [quiz|guide|both]
---

# Study Prep: practice quiz and/or study guide from real course material

Builds from what the course actually gave the user (LMS slides, PDFs, pages, announcements, video transcripts) plus their own Google Doc notes, then publishes one artifact with a **Study guide** tab and/or a **Practice quiz** tab (instant grading, why + source on every question, misses filter, progress saved in the browser).

Everything below was learned the hard way across four courses' worth of preps in one semester. Don't skip the scope step.

**Tools in this folder:** `build.py` (validates the bank, fills `template.html`, prints the answer spread), `graphs.py` (supply/demand SVG helper), `example/` (the authoring format and the self-test: `python3 .claude/skills/study-prep/build.py .claude/skills/study-prep/example`).

**Not included in this public extract:** the LMS materials fetcher. It rides the user's own browser session (the school blocks student API tokens), so it stays private. Any fetcher that drops course text into `.tmp/lms/materials/<courseId>/text/` with an `index.json` of module names works with the steps below.

## 0. Parse the request

- **Course**: match against the cached LMS course list (course names/codes).
- **Exam or scope**: "Exam 2", "Quiz 4", "chapters 1 and 3", "weeks 5-7".
- **Mode**: `quiz`, `guide`, or `both`. If unstated, build both.
- **Size / sets**: only if stated ("36 questions", "three quizzes").
- **Prep folder**: `references/<course-dir>/prep/<slug>/` (local, gitignored). Use the existing course dir, else `<dept><num>` lowercase. Slug is the exam in kebab case (`exam-2`, `quiz-4-vaccines`). If the folder already has a `prep.py`, this is an update: keep its questions unless asked, and reuse the `# artifact:` URL on its first line.

## 1. Course-wide LMS pull (scope sources only)

Run the materials fetcher with a module filter that matches nothing (`'^$'`). That skips module content and still saves syllabus, front page, and announcements (plus their attachments) to `text/`, and `index.json` lists every module name.

**Session expired** → start the fetcher's `--login` mode in the background. A real browser window opens and the user logs in themselves. Tell them to. Never type into, fill, or snapshot the login page (snapshot tools return autofilled credentials in plaintext). If the user is away, fall back to local copies under `references/<course-dir>/` and the dated LMS snapshot, and say so in the report.

## 2. Lock the scope before writing anything

Read `text/announcements.txt` (newest first) and `text/syllabus.txt`. Scope and logistics (date, time, room, format, question count, time limit) come from **announcements, the syllabus, or the last slides of the newest deck** (one course put quiz scope there). Never from assignment due dates or video-response cadence: LMS due dates can be placeholders (one said 11:59pm when the check was in class at 12:30), and inferred scope was wrong once already.

State the scope in one line with its source ("Scope: §2.5 and §2.6, per the Sept 15 announcement"). If nothing states it, or sources conflict, ask the user one short question with your best guess. Don't build on inferred scope.

## 3. Gather everything in scope

**a. LMS modules.** Pick a regex from the module names in `index.json` (they vary: "Week 05", "Module 4:", "Unit 3") and re-run the fetcher with it. It should save page, assignment, quiz, and discussion bodies, download every linked file (including ones linked only from bodies or announcements, which works around hidden Files tabs), and extract their text (pdftotext for PDFs, markitdown for pptx/docx, speaker notes included). Cache files by size so re-runs are cheap. 403s on links into other courses can be ignored.

**b. Local copies.** Check `references/<course-dir>/` (slides/, earlier guides). **Verify each deck's content matches its filename** by reading its first slides: one `Week_03_...pptx` actually held a different week's deck.

**c. A deck announcements mention that still isn't downloaded:** if the Files tab is hidden but `/api/v1/files/<id>` works, probe neighbouring file IDs (about ±40 around a known ID, filtered by `folder_id`). Only then.

**d. Video transcripts** (only videos in scope). YouTube IDs:

```python
from youtube_transcript_api import YouTubeTranscriptApi
text = " ".join(s.text for s in YouTubeTranscriptApi().fetch("<id>"))
```

Everything else (BBC, TED, Vimeo, Kaltura, LMS media), or any video link you spot in the text files:

```bash
yt-dlp --skip-download --write-subs --write-auto-subs --sub-langs "en.*" -o "<prep>/sources/%(title)s.%(ext)s" "<url>"
```

Vimeo page URLs (`vimeo.com/<id>/<hash>`) demand a login. Use the player URL instead: `https://player.vimeo.com/video/<id>?h=<hash>` with `--referer "https://<your-lms-host>/"`.

No subtitles? Transcribe locally for free with an on-device ASR model (the author uses parakeet-mlx). Run it in the background (~1 min per video) and keep working:

```bash
yt-dlp -q -f "bestaudio/worst" -x --audio-format wav --postprocessor-args "ffmpeg:-ac 1 -ar 16000" --referer "https://<your-lms-host>/" -o "<prep>/sources/video <name>.%(ext)s" "<player url>" < /dev/null
# then, for each wav:
OPENBLAS_NUM_THREADS=1 python -c "import parakeet_mlx,sys; r=parakeet_mlx.from_pretrained('mlx-community/parakeet-tdt-0.6b-v2').transcribe(sys.argv[1], chunk_duration=120, overlap_duration=15); print('\n'.join(f'[{int(s.start//60):02d}:{int(s.start%60):02d}] {s.text.strip()}' for s in r.sentences))" "<wav>" > "<txt>"
```

Delete the wavs afterwards. Only if both paths fail does the video go in `MISSING`.

**e. The user's Google Doc notes.** Doc names don't match course names reliably, and Drive `name contains` is prefix-matching (a truncated term silently returns zero files), so search several terms at once:

```bash
python3 - <<'EOF'
import json, subprocess
terms = ["CS", "Intro", "101"]  # course code, number, subject words
q = "mimeType='application/vnd.google-apps.document' and trashed=false and (" + " or ".join(f"name contains '{t}'" for t in terms) + ")"
params = {"q": q, "fields": "files(id,name,modifiedTime)", "orderBy": "modifiedTime desc"}
out = subprocess.run(["gws", "drive", "files", "list", "--params", json.dumps(params)],
                     capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
for f in json.loads(out[out.index("{"):])["files"]: print(f["modifiedTime"][:10], f["id"], f["name"])
EOF
```

Pick the running class-notes doc (usually the most recently edited). Skip earlier Claude-made outputs like "... Study Guide" and "... Practice Quiz", but glance at a previous study guide to avoid repeating it. Still nothing? Try `fullText contains '<distinctive lecture term>'`. Export with `gws drive files export --params '{"fileId":"<id>","mimeType":"text/plain"}' -o "<prep>/sources/notes.txt"` (a `--fileId` flag does not exist). Notes show what the instructor stressed in class, so weight those topics up.

**f. Class recordings (if any).** Slice each recording's transcript to the course's time window exactly as `/notes-sync` Steps 2-4 do. Use them for emphasis ("this will be on the exam") and for anything said but not on slides.

**Don't:** scrape publisher homework platforms (question text often never crosses the network, and drag-and-drop UIs kill DOM scraping; the publisher's slide decks + speaker notes are the better source). Don't automate graded-homework platforms at all: that is the academic-integrity line. If the user wants those problems in, ask for screenshots.

## 4. Read, then plan coverage

Read every in-scope text in full: slides with speaker notes, notes doc, transcripts, announcements. The distractor rule in Step 6 needs the sources' exact wording, so summaries aren't enough.

**Handwritten scans** (posted solution PDFs) extract as garbage text. Read those pages as images with the Read tool (`pages: "1-5"`). They show the instructor's exact method and notation, which is what the quiz grades. The homework list says which problems were assigned; the real quiz is usually "problems similar to the ones assigned".

For big scopes (roughly 10+ decks), fan out one `general-purpose` subagent per unit, in parallel, with: *"Read <files>. Return every testable fact as a bullet in the source's exact wording with a cite (deck + slide number, or doc + date). Include lists, definitions, named examples, and figures. Do not paraphrase."*

Weight topics: announced scope first. Then anything the instructor flagged (announcements, the user's notes, recordings). Then anything new in a revised deck (diff versions when both exist).

## 5. Study guide (`guide` or `both`) → `<prep>/guide.md`

- `##` per topic in the order of the announced scope (these become the contents sidebar), `###` for subtopics.
- Definitions in the source's exact wording when answers are graded against it.
- Tables for confusable lists. Real figures from the deck, not rounded or invented.
- One `>` callout per trap (the thing students mix up).
- End with `## Know cold`: 8-12 bullets.
- Math: `\( \)` inline, `$$ $$` display. Bare `$` is safe for prices.
- No em dashes. Only what the sources say. If the scope names a topic with no source material, say so in the guide and add it to `MISSING`.

## 6. Practice quiz (`quiz` or `both`) → `<prep>/prep.py`

Copy the shape of `example/prep.py`: `META`, `SOURCES`, `MISSING`, then `QUESTIONS` (one quiz) or `SETS = {"Drill 1": [...], "Drill 2": [...]}` (several quizzes; build rejects repeated stems across sets). Helpers: `MC(topic, stem, options, why, src)`, `TF(topic, stem, answer, why, src)`, `SA(topic, stem, answer, src, why="")`. A guide-only prep still needs `prep.py` with `META` and `SOURCES`. **Graphs:** `prep.py` also gets `graphs` (`graphs.py` here). `graphs.Panel` draws supply/demand graphs from data coordinates and `graphs.fig()` returns inline SVG; append `"\n\n" + graphs.fig(...)` to an answer or `why`. When the real exam has graphing questions, use it for the worked answers and add "Graph it" draw-and-shade problems.

**Size:** scale to the material, about 2-3 questions per major topic (a slide section, textbook subsection, or named list), more for announced-emphasis topics. A stated count wins.

**Mix:** mirror the real format when announcements give it (MC only? T/F? short answer?). Computational courses: `SA` worked problems are the core, with MC only for concept checks.

**Mirror the real exam when you have graded copies.** Keep a per-course `references/<course-dir>/exam-format.md` built from the user's graded quizzes/exams (point values, number of problems, lettered parts, the instructor's instruction wording and grading notes). Read it first, mirror it, and put the grading notes into the `why`.

**Quality rules. The build enforces the mechanical ones; the rest are on you:**
- Every question traces to a source. `src` is specific: `"Wk5 CRM slides #14"`, `"Notes 9/16"`, `"Vaccines video 04:10"`, `"Announcement 9/21"`. Never invent content.
- **Distractors are real phrases from elsewhere in the same scope** (a sibling list, a neighbouring concept), never invented filler. Correct and wrong options must read alike, or cadence gives the answer away.
- **Check every distractor is actually wrong.** Math options can be secretly equivalent: for "which f and a" questions, \(f(x)=x^4-81, a=3\) produces the same limit as \(f(x)=x^4, a=3\). Solve each wrong option once.
- **A posted review-problem list means the practice sets ARE those problems**, word for word, one card each, the posted solution as the answer. No new-number variants unless asked. The brand-new-numbers rule below is for weekly quizzes.
- Brand-new numbers for worked problems (don't reuse the instructor's solved examples; the user has seen them). Model each on an assigned problem and cite it as `"modeled on 2.7 Solutions #19"`.
- Spread the starred option across A-D as you write. Build fails if one letter holds over 40% of a set.
- `why` teaches the distinction: why the answer is right, and what the tempting wrong option actually belongs to.
- Math answers: copy the instructor's write-up layout from their solutions (rule named, pieces written before computing, units). Carry `\lim` on every line until substitution, `=` between lines never `→`, name each law, and never skip the formula line before the numbers: that skipped line is where points get lost. Guides get a "How it's graded" and a "How to write it" section.
- Test understanding over trivia. No "which slide number" questions.

**META:** `course` ("CS 101"), `title` (short: "Exam 2", becomes the page title "CS 101 Exam 2"), `exam` (logistics line from Step 2: "Wed Oct 21 · in class · 36 questions · 50 min"), `scope`. **SOURCES:** one line per real source used. **MISSING:** every gap (video with no transcript, deck the user would need to screenshot, topic with no material).

## 7. Build

```bash
python3 .claude/skills/study-prep/build.py references/<course-dir>/prep/<slug>
```

Fix every `ERROR` and rebuild. Check the spread and topic lines match your plan. Output: `<prep>/<slug>.html`. Progress is saved per question, keyed by its content, so a rebuild keeps saved answers for every question you didn't change (editing a `why` or an SA answer keeps them too).

## 8. Publish

The template already follows the artifact page contract. Don't redesign the page, and skip the screenshot loop: the template is tested and `build.py` is the check.

- **First publish:** Artifact tool, `file_path` = the html, `icon: "quiz"`, `description` = one sentence ("Study guide and 30-question practice quiz for CS 101 Exam 2, built from the Week 5-7 slides and class notes."). Then write `# artifact: <url>` as the first line of `prep.py`.
- **Update in the same session:** rebuild, re-publish the same `file_path` (same URL).
- **Update in a later session:** read the `# artifact:` URL with `action: "read"` first, then publish with that `url`.

## 9. Report back

```
<course> <exam>: <artifact link>
Scope: <scope> (per <source + date>)
Guide: <N> sections · Quiz: <N> questions (MC a · TF b · SA c) · answers A.. B.. C.. D..
Built from: <sources>
Missing: <gaps, or "nothing">
```

If the scope question from Step 2 is still open, or `MISSING` includes something the user can supply (a screenshot, a doc), end with that one ask.

## Guardrails

- Scope from announcements/syllabus/deck, never inferred (Step 2).
- Nothing without a `src`. A gap is reported, never filled from general knowledge.
- Never touch a login page or password field. `--login` is the user's to complete.
- No scraping or automation of graded-homework or publisher platforms.
- Don't overwrite a prep the user is mid-way through with a different question set unless asked; add a new set instead.
- Don't use the artifact `db` capability for progress (its frozen snapshots broke every answer after the first in one quiz). The template's localStorage is enough.
