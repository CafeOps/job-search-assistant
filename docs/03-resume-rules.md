# 03. Resume rules and the resume pass

Default rules. In the intake, copy them to `<data>/RESUME-RULES.md` and fill in the blanks. After that the
user's file wins.

## How rules are made

Rules come from mistakes. When the user catches one (a chopped line, an extra bullet, an invented cert, a
word that sounds fake), add a dated line under "Correction history" in RESUME-RULES.md: what went wrong and
why. A rule with its reason survives. A bare rule gets argued away.

Flag a concern once. If the user keeps the thing, log it in `<data>/DECISIONS.md` and never raise it again.

## Rule 0. Source of truth

Every claim maps to PROFILE, STORIES or NUMBERS, or a document the user gave you. No source, no claim. AI
tools invent certifications, inflate numbers and push "Senior" titles the years don't back.
The bar is "true and defensible in an interview", not an audit. The user is the final fact check.

## Rule 1. Line width

Each bullet fills one line. Find the user's band on the built page: the longest bullet that still fits on
one line sets the top, about 15 characters less is the bottom. Record it in RESUME-RULES.md as
`Line width band (Rule 1): A to B`. Character count is a proxy. The page image is the proof.

## Rule 2. Structure

- A fixed bullet count per role (`Bullets per role (Rule 2): current N, previous M`), often 5 or 6 and 3 or 4.
- Each bullet covers a different lane of the job. No two say the same thing.
- Every bullet makes sense to a stranger: no internal project names, ticket numbers or team jargon.
- Never add or drop a bullet without telling the user.

## Rule 3. Title layers

Application forms and references get the HR-record title. The resume may use a functional title that
describes the same job, never a higher level, and only with the user's OK. LinkedIn is self-described.
Record which title goes where in RESUME-RULES.md.

## Rule 4. Voice

- Plain and factual: a capable person describing their own job, not a sales page.
- Capability, not an event log: what they do, with at most one proof point.
- Metric bullets: result, number, how. Scope bullets stay scope-led. Never invent a metric to fill the shape.
- Current role: present tense for ongoing work, past tense for a finished result. Older roles: past tense.
- The user's ear decides. A phrase they call AI-sounding goes, and into VOICE.md.

## Rule 5. One banned list

ONE list in `<data>/VOICE.md`, pasted into every drafting brief, including briefs to another model. Seed:
leveraged, spearheaded, streamlined, seamless, synergy, orchestrated, passionate, dynamic, results-driven,
go-getter, "in order to", "it is worth noting", "responsible for", "helped to", utilized, cutting-edge,
best-in-class, "proven track record". No em or en dashes. No semicolons in bullets.
Ask: "Any words that sound wrong where you live or in your industry?" A word the user really uses can be
un-banned under "Allowed" in VOICE.md, so it's never flagged again.

## Rule 6. Locked numbers

Every figure on the page has a row in `<data>/NUMBERS.md`: figure, source, status (measured, estimated,
identified). The wording keeps the status ("estimated", "identified", never "saved" for identified money).
Never add separate figures into one total. A figure the user picked is locked. Repeating an unconfirmed
claim in a new draft doesn't confirm it.

## Rule 7. Certifications

Held certifications only, exact names. One letter apart is a different exam. In-progress certs stay off
unless the user asks for an "in progress" line.

## Rule 8. Other AI models

Another model may critique or reword. It never supplies a fact. Check what it returns against Rules 0 and 5.

## ATS readability

Most applications are read by software first (Workday, Greenhouse, Lever, iCIMS, Taleo, SuccessFactors).
If it can't read the file, no person sees it.

1. One column. No tables, text boxes, sidebars, graphics, icons, photos, skill bars or charts.
2. Contact details in the page body, line 2. Parsers often skip headers and footers.
3. Standard section names: Summary, Skills, Experience, Projects, Education, Certifications.
4. A plain font (Calibri, Arial, Cambria, Georgia) at 10 to 12 pt. Real bullets.
5. Every job: title, employer, city, dates, with ONE date format ("Mar 2023 to Present").
6. The posting's exact words for skills the user really has ("Power BI", not "PowerBI"). Never add one they lack.
7. Send the .docx when a form takes either, unless the posting asks for PDF. Both must be real text.
8. One page under about 10 years of experience. Two at most after that.
9. After an upload, read the autofilled fields and fix what the parser got wrong (docs/07).

`tools/build_resume.py` builds to rules 1 to 5 and checks 7 and 8 itself.

## Files and names

Files are `First_Last_Resume.docx` and `.pdf`. A variant adds one word: `First_Last_Resume_Endpoint`.
Recruiters see the file name, so never "resume_final_v3".

```
<data>/resume/resume.md                source text (the AI edits this, then builds)
<data>/resume/live/                    ONLY the current .docx and .pdf
<data>/resume/history/NN_YYYY-MM-DD/   every replaced version, with a line in history/README.md
<data>/resume/preview/page-N.png       the page images from the last build
<data>/source/harvest/                 old resumes found on the computer (docs/02)
```

The builder keeps this layout and never deletes. Start with one resume. Add a variant only for a clearly
different lane, and note which rules bind it. If the user keeps a hand-made Word file as the master, edit a
copy of it with python-docx (swap the first run's text, blank the rest, clone a middle bullet) and run
`tools/check_render.ps1` or `tools/check_render.sh` for the page check.

## The resume pass

Write `<data>/resume/resume.md` in the format of `examples/jordan-rivera/resume.md`, then:

1. **Facts.** List every claim the version needs. Confirm them with the user in ONE numbered message.
2. **Draft once**, all sections, against Rules 0 to 7. Cut any line you yourself think is risky. Read it as
   the user would say it: if it sounds like an AI resume, rewrite it.
3. **Build:** `<python> tools/build_resume.py <data>/resume/resume.md`. It tries five layouts, keeps the
   fullest one that fits the page limit, archives the old version, renders the page images and prints the
   QUALITY GATE. Fix every FAIL in resume.md and build again. "Page fill" fails below 85%: add true content
   from STORIES (another bullet, a Projects line), never filler.
4. **Look at it.** Open every `preview/page-N.png` with your image viewer (Claude Code: read the PNG file.
   Codex: view the image). Go through the visual checklist below. Fix and rebuild until every item passes.
   Never skip this step. A script can't see a page.
5. **One critic.** A reviewer with a fresh context (Claude Code: a new subagent. Codex: a new session)
   gets the PDF, the page image and, for a targeted version, the job posting. It returns findings only,
   without knowing who wrote it. One critic per version, never a panel. Its verdict never overrides the user.
6. **Show the user** the page image. Apply their corrections without re-arguing, then build again (the gate
   reruns).
7. **Record** in PROGRESS.md: `resume: approved YYYY-MM-DD (gate: automatic PASS, visual PASS, user approved): <paths>`.

No Word and no LibreOffice? Give the user the finished text to paste into Word, Google Docs or Pages, ask
for the exported PDF, then render or screenshot it and do step 4 on that.

### Visual checklist (step 4)

1. Page count as agreed. No stray blank page.
2. The page looks full and balanced: content reaches the bottom fifth, no large empty block.
3. Every bullet on one line. No orphan word on a line of its own.
4. Name, contact line and headline centered. Dates and locations in one straight right-hand column.
5. Every item of a kind looks the same: same font, size, weight, spacing and indent.
6. Nothing cut off, overlapping, or shown as boxes or odd characters.
7. No heading stranded at the bottom of a page.
8. The top third says who they are and what they do, at a glance.

## Staleness check

At the start of a resume session, read the "Last resume update" date in RESUME-RULES.md. If a new cert,
title or finished result with a number landed since, or 8 weeks passed, mention it once. If declined, drop it.
