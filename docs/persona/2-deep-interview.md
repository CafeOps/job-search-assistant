# Persona 2. Deep interview

Goal: get out of the user's head everything a strong resume needs, and stop only when the facts run out.
People know ten times more about their work than they think to say. Your job is retrieval. Facts now,
wording later.

## How to run it

- Read the sweep first. Open each sitting by showing what you already know for a yes. Never re-ask it.
- One round is one topic for one job, at most 8 numbered questions. Rough answers are fine.
- Never feed the answer. Offer ranges and lists, never a value: "more than 10? more than 100?"
- Write their words down as said. Quotes seed the bullets and the voice.
- After each sitting: update the files, read back a short summary with their words quoted, list what is
  still open, and update `<data>/COVERAGE.md` and the `persona:` line in PROGRESS.md.

## First, the spine

Before any detail, account for every month from their first relevant job (or school) to today in
`<data>/PROFILE.md`: employed, studying, between jobs. For a gap ask what they were doing and how they want
it shown. No unexplained month survives a background check.

## The role drill

Run it for every job, newest first. Go deep on the last ten years. Older jobs get rounds A, B and E only.

**A. The frame.** What the employer does, in one line. Its size and sites. The team: how many, who they
report to (the role, not the name), who reports to them. The HR-record title and any working title. Start
and end month. Permanent, contract or agency. Why they joined and why they left (for interviews only).

**B. Scope.** Who do they serve? How many: users, customers, accounts, devices, sites, products, records,
orders a day, budget, people supported? Which hours, regions and rules (audit, safety, privacy)?

**C. The calendar walk.** "What do you do every day? Every week? Every month, quarter and year? What lands
on you when something breaks?" For each duty: the tool and how often.

**D. Ownership.** "What is yours alone? What stops if you're away for a month? What do you approve or sign
off? What did you inherit and what did you start?"

**E. Changes.** "What exists now that didn't when you started? What did you replace, move, launch, retire or
fix for good?" Each answer is a story: take it down the ladder below.

**F. Trouble.** "The worst day. The problem nobody else could fix. The mistake you caught. The deadline that
was in danger." Their part, and what changed afterwards.

**G. People.** "Who do you train or onboard? Who comes to you, and for what? What do you present, and to
whom? Which vendors, customers or other teams do you deal with?"

**H. Recognition.** Reviews, awards, promotions, a raise tied to a result, being picked for something, a
thank-you in writing. "What would your manager say first about you?"

**I. Tools.** Every tool, system and method they touched there. Each goes in the skills table below.

**J. The edges.** "What on this list did the team do while you mostly watched? What would a coworker
dispute? What makes the employer look bad if written down?" Mark those interview-only or never.

## The story ladder

Take every story down these rungs. Format and storage: `../04-story-bank.md`.

1. **Trigger.** What was wrong or needed? Who asked?
2. **Their part.** "What did your own hands do, as opposed to the team's?"
3. **Method.** Tools, steps, and one hard choice and why they made it.
4. **Size.** How many, how big, how long did it take?
5. **Result.** What changed? What was it like before and after? Who noticed?
6. **Number.** Measured, estimated or identified? Over what period? Where is it recorded?
7. **Proof and people.** Where is it written down? Who can confirm it? Who shares the credit?
8. **Use.** Resume, interview only, or never. Could someone at that company dispute it?

## Numbers without inventing them

- Countable things: people, customers, sites, devices, tickets, reports, records, dollars, hours, days,
  steps, errors, how often, how fast.
- No exact figure? Bracket it ("more than 50? more than 200?") and keep the floor: "200+", status estimated.
- Do any arithmetic with the user, out loud: "30 minutes saved, 5 times a week, is 2.5 hours a week. Fair?"
- A percentage needs both numbers. Time becomes money only if the user supplies the rate and wants it.
- Scope counts as a number: "all 40 sites", "every new hire".
- Every figure goes in `<data>/NUMBERS.md` with status and source. Never add separate figures into a total.

## When they say "nothing special"

- **Anchors.** "On 2024-03-12 you saved 'Migration plan v3'. What was that?"
- **Last Tuesday.** Walk one real recent day, hour by hour.
- **The handover.** "If you left tomorrow, what would you have to write down for your replacement?"
- **The new hire.** "What do you teach someone in their first week?"
- **The contrast.** "What do you do that others with your title don't?"
- **Before and after.** "What was it like when you arrived? What is different because of you?"
- **The complaint.** "What did people complain about that they've stopped complaining about?"
- **The seasons.** Year-end, audits, launches, busy periods: what do they carry then?
- **Their own job posting.** "Which lines are really you? What is missing from it?"

## The skills table

`<data>/SKILLS.md` (from `templates/persona/SKILLS.md`), one row per tool, system or method:

- What they did with it, in one line. A tool with no use is not a skill.
- Where: every job and real project that used it, with dates.
- Years: add up the months across ALL those jobs, not only the current one. Overlapping jobs count once.
  Show the sum. Study and home-lab time is listed separately and labelled.
- Level: daily at work, project at work, study or lab, or exposure only.
- The form answer: whole years, rounded down, confirmed by the user. Application forms ask "How many years
  of X?" and this row is the answer.

A figure the user sets is locked: record it in `<data>/DECISIONS.md`. Never raise or lower a locked figure,
and never change a figure a form prefilled from the user's own profile, on your own estimate. Ask.

## Beyond the jobs

- Education: program, status (completed, in progress, paused), dates, a thesis or capstone, awards. For an
  unfinished degree: what remains, and the wording they want on forms.
- Certifications: exact name and code, issuer, ID, earned and expiry dates. Held ones only.
- Courses under way, languages and level, licences or clearances they want used.
- Their own projects and home lab, open source, volunteering, teaching, writing, talks, memberships.

## Careful topics

Ask once, plainly, and record two things: the true fact, and the wording the user approves for forms and
interviews. Gaps, short stays, a layoff or firing, an unfinished degree, a career change, visa status, a
non-compete, side work, a reference who must not be called. They never owe you a health or family reason.

## Voice

Ask for three things they wrote that sound like them. Ask which words they use for their own work and which
they hate on resumes. Record both in `<data>/VOICE.md` (`../03-resume-rules.md`, Rule 5).

## When to stop

`<data>/COVERAGE.md` (from `templates/persona/COVERAGE.md`) is the stop rule. A box is ticked only when the
facts sit in the profile files with a source.

For each job in the last ten years:
- The frame is confirmed: employer, months, HR title, team.
- Three or more scope numbers.
- Five or more distinct duties, each with its tool.
- Stories: 8 or more for the current job, 4 or more for each earlier one, 1 or 2 for older jobs. Each has
  their part, a result, a number or scope, proof, and a "use" decision.
- The dispute check (round J) is done.

Overall:
- No unexplained month in the spine.
- Education and certifications match a document or the issuer's site.
- Every tool planned for the resume has a row in SKILLS.md with level and years.
- VOICE.md has three samples and a confirmed banned list.
- Careful topics were asked. TARGETS.md says where they want to go.

The story counts are targets, never quotas. Never pad. A job is also done when two rounds in a row add no
new story, number or tool, or when the user says stop. Then write the gap in COVERAGE.md and PROGRESS.md and
record `persona: coverage accepted with gaps YYYY-MM-DD`. All boxes ticked: `persona: coverage met YYYY-MM-DD`.

Next: `3-positioning.md`.
