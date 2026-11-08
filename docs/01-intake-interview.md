# 01. Intake interview

Goal: learn enough to write the profile, resume rules, screening rules and scanner config without guessing. AGENTS.md stages 0 to 2 come first, so harvested files are already read and PROFILE.md and NUMBERS.md drafted. These phases fill gaps and settle conflicts. Confirm what an old document answers instead of asking again.

## How to ask

- One phase per round, at most 6 to 8 numbered questions. Offer a default so they can say "yes".
- Accept rough answers. Follow up only when an answer changes a filter.
- Read any files they give you first. Ask only what those don't answer.
- End each phase with a short written summary the user confirms, quoting their words (their phrasing seeds the resume voice). Save the answers in `<data>/` and update `<data>/PROGRESS.md` (phase reached, open questions) before moving on.
- Short on time: phases 1, 3 and 4 are enough to draft the scanner config. Mark the rest open in PROGRESS.md and finish them before the resume pass.

## Phase 1. Who they are

1. Full legal name, and the name they go by.
2. City, province or state, country. (Street address only if a form needs it.)
3. Email for applications, and email for the daily digest (can match).
4. Phone, LinkedIn URL, GitHub or portfolio URL.
5. Work authorization: which countries can they work in without sponsorship?
6. Status: employed, between jobs, student, contract ending? Is the search public or quiet? Does their employer, or anyone at the employer's vendors, know?

Write: `<data>/PROFILE.md` (identity). Note their AI tool and OS in `<data>/PROGRESS.md` (it decides what phase 6 can set up).

## Phase 2. Work history (facts, not wording)

For each job, newest first:
1. Employer, city, start and end month and year (or "present").
2. The HR-record title (what a reference check confirms), and any functional title they use instead (Rule 3 in `docs/03-resume-rules.md`).
3. Team size, what the company does, how big it is.
4. What they own day to day: tools, systems, products, customers.
5. Two or three results with a number, if any. Mark each "measured", "estimated" or "identified but not realized".

Education: school, program, status (completed, in progress, paused), dates. Certifications: exact name, issuer, date earned, expiry. Only ones they hold. Never mark anything completed that isn't.

Write: `<data>/PROFILE.md` (history) and `<data>/NUMBERS.md` (each figure with source and status).

## Phase 3. Direction

1. Which job titles do they want? Which do they refuse (too junior, wrong lane, "support", "sales")?
2. Which industries or company types? Any to avoid? Bigger or smaller than now?
3. Seniority, as an exact number: "How many years have you done this kind of work, counting only the real lane?" Then stretch up, stay level or step back? Then "Do you want Senior titles in your digest?" (Default no under about 5 years.) This sets `title_exclude_seniority` in the scanner config.
4. Where: cities and commute radius, remote, hybrid, on-site, relocation.
5. Where do they want to be in 3 to 5 years? (It ranks matches. It doesn't filter.)
6. Employers never to send them to: current and former employers, the current employer's vendors, companies with a bad history.

Write: `<data>/TARGETS.md` and `exclude_companies` in `<data>/scanner-config.json`.

## Phase 4. Money and deal breakers

1. Salaried permanent: the floor (walk away below), the target, and the "would move for" number.
2. Contract: hourly floor, whether they take contracts at all, minimum length, contract-to-perm only?
3. Non-negotiable benefits, pension or bonus?
4. Hard no's: travel percentage, on-call, shifts, overtime, security clearance, relocation, a tech stack, a company size, unpaid take-home tests over N hours.
5. Form answers: notice period, how to word start dates (for example "two weeks after an offer is accepted"), and salary answers (expected, a range, the minimum they'd accept). Record them in SCREEN.md "Form answers".
6. Anything a form needs a careful answer for: non-compete, past employment or relatives at a target company, a degree in progress, a work gap.
7. Has any agency or recruiter submitted their resume anywhere in the last 6 months? Which employers? Those go into `flag_companies` (an agency may already hold right-to-represent there).
8. Any applications or interviews already in progress? Which employers? Those go into `exclude_companies` and `<data>/PIPELINE.md`.

Write: `<data>/SCREEN.md` (from `templates/profile/SCREEN.md`), `<data>/scanner-config.json` (fields in `docs/06-daily-scan.md`) and `<data>/DECISIONS.md` lines.

## Phase 5. Stories

First ask: "Where can the proof live? A work log, tickets, emails, a journal?" Every claim needs a source (Rule 0 in `docs/03-resume-rules.md`). No work log? Suggest starting one now (template in `docs/04-story-bank.md`).

Then collect 5 to 8 stories with `docs/04-story-bank.md`, one or two per round. School projects, volunteer work and part-time jobs count. Never pad with invented stories. Record the gaps in PROGRESS.md. Prompts that work:
- "What problem could nobody else fix? What did you do?"
- "What did you build or change that people still use?"
- "When did something break badly? What was your part?"
- "What do coworkers come to you for?"
- "What saved someone time or money? Roughly how much?"

Write each story into `<data>/STORIES.md` in that doc's format.

## Phase 6. Voice and tool setup

1. Ask for something they wrote that sounds like them (an email, a post). Note their habits.
2. Ask which words they hate seeing on resumes. Seed `<data>/VOICE.md` from the default banned list in `docs/03-resume-rules.md` and add theirs.
3. Read `docs/09-tool-setup.md` and set up only what they pick: the daily job digest by email, you filling in applications in their browser, you drafting emails and outreach notes, phone access to this chat.

## Done when

- `<data>/PROFILE.md`, `TARGETS.md`, `SCREEN.md`, `STORIES.md`, `VOICE.md`, `NUMBERS.md` and `scanner-config.json` are filled from the user's own answers, and they confirmed each summary.
- You compared each with its match in `examples/john-smith/`. Where theirs is thinner, ask one more round or record the gap. "Done" means as complete as the facts allow, not as long as the example.
- `<data>/PROGRESS.md` says `intake: confirmed YYYY-MM-DD`.
- Next: the resume pass in `docs/03-resume-rules.md`.
