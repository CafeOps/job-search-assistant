# Persona build: resume, cover letter and professional profile

The deep track. The standard stages (harvest, intake, rules, resume) give the user a sound resume. This track
gives them a strong one. It collects every piece of proof the user will share, questions them job by job
until the facts run out, and only then writes. One fact base then feeds the resume, the cover letters, the
LinkedIn text and the interview answers, so they all say the same thing.

Run it when the user asks for the best resume they can have, asks for cover letter, LinkedIn or "how do I
present myself" help, or when a resume pass finds the facts thin. It is optional and never blocks a stage.

## Offer it once

Right before the first resume pass (stage 5), or when a quick-start user first asks for resume work, say:
"I can build your resume from what we have now. Or I can run the deep build first: I collect every document
you're willing to share, then ask detailed questions over three to five short sittings. It takes longer and
gives a much stronger resume, plus cover letters and LinkedIn text that match it. Which do you want?"

A no is recorded as `persona: declined YYYY-MM-DD` in `<data>/PROGRESS.md` and not raised again. The user can
ask for it later.

## The order

Start by copying `templates/persona/*` into `<data>/`. Skip any file that already exists.

| Step | Guide | Writes | Status in PROGRESS.md (`persona:` line) |
|---|---|---|---|
| 1. Evidence sweep | `1-evidence-sweep.md` | `<data>/EVIDENCE.md`, copies under `<data>/source/` | `sweep done YYYY-MM-DD (N sources)` |
| 2. Deep interview | `2-deep-interview.md` | PROFILE, STORIES, NUMBERS, SKILLS, VOICE, COVERAGE | `interview: role N of M`, then `coverage met YYYY-MM-DD` or `coverage accepted with gaps YYYY-MM-DD` |
| 3. Positioning | `3-positioning.md` | `<data>/PERSONA.md` | `positioning confirmed YYYY-MM-DD` |
| 4. Resume | `4-resume.md`, then the pass and gate in `../03-resume-rules.md` | `<data>/resume/` | the stage 5 `resume: approved ...` line |
| 5. Cover letters | `5-cover-letters.md` | `<data>/cover-letters/` | none. Each letter is approved on its own |
| 6. Public profile | `6-public-profile.md` | PERSONA.md "Profile text" | `profile text approved YYYY-MM-DD` |

Steps 1 to 4 run in order. Steps 5 and 6 can run any time after step 3. Keep one `persona:` line and move it
forward, so any tool can pick up from the file alone.

How it fits the stages: the sweep completes stage 2 (record the `harvest:` line too). The deep interview
completes intake phases 2, 5 and 6. Phases 1, 3 and 4 still come from `../01-intake-interview.md`, and the
rules (stage 4) from `../03-resume-rules.md`. Never re-ask what `<data>/` already answers. Confirm it.

## The sittings

Plan three to five sittings of 30 to 60 minutes. You do the reading and writing between them. Say this plan
to the user at the start, so they know what they're signing up for.

1. **Permission and sweep.** The user approves what you look at and what you copy. Then you read everything
   and draft the profile files and your question list.
2. **Current job.** The full role drill. This is the longest sitting.
3. **Earlier jobs, school and everything outside work.**
4. **Positioning and the resume facts.** Then you build, and the user sees the page.
5. **Cover letter base and profile text.**

Stop a sitting after about 45 minutes or when the answers get short. Tired people agree to things that aren't
quite true. Short on time: the current-job drill, the skills table and the positioning page pay for
themselves. Log the rest as gaps.

## What holds throughout

The rules in AGENTS.md all apply. These matter most here:

- **Only true claims.** A fact has a source: a document, or "user, YYYY-MM-DD". Mark each fact confirmed,
  from a document, or unconfirmed. An unconfirmed fact never reaches a resume, a letter, a form or a profile.
- **Never feed the answer.** Ask open questions and offer ranges or lists. "Was it about 30%?" plants a
  number. "Did anyone measure it? What was it before and after?" finds one.
- **The computer and the accounts are the user's.** List first. Copy only what they approve. Never move,
  rename or delete an original. They sign in and they export. You never type a password.
- **The employer's material stays out.** No internal documents, exports, screenshots, customer data or code.
  From work the user brings facts, never files.
- **Private details stay where the user puts them.** Pay, health, immigration and discipline history are
  written down only if the user says to, and only where they say.
- **The user's ear decides the wording** (VOICE.md). Their own phrases, written down as they said them, beat
  anything you compose.

## Keeping it alive

- A new win, cert, tool or job change goes into STORIES, SKILLS and PROFILE the day the user mentions it.
- Suggest the work log in `../04-story-bank.md`. Next year's resume is written from it.
- At each resume session run the staleness check in `../03-resume-rules.md`, refresh the years in SKILLS.md,
  and rerun the consistency check in `6-public-profile.md` after any title, date or cert change.
