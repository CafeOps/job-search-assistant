# Persona 5. Cover letters and short answers

## When to write one

Only when the posting asks for a letter, the form has a required letter box, the letter goes to a named
person, or the application needs explaining (a stretch, a career change, a gap, a move). Otherwise skip it.
An outreach note usually does more (`../08-outreach.md`).

## Before writing

- The posting, and a fit map: its top needs, each with the story that answers it.
- PERSONA.md and VOICE.md.
- One true reason for this employer. ASK: "Why this company, in your own words?" If the honest answer is
  "the job fits and the pay is right", the letter says why the job fits and skips the praise.

## The shape

250 to 350 words, one page.

1. **Opening**, two or three sentences: the job (title and req number), who they are (the one-liner), the
   one reason they fit. Never "I am writing to apply" or "I was excited to see".
2. **Proof.** The posting's top need, and the story that answers it: what they did, how big, what changed.
3. **Second proof**, or the explanation the application needs, in two plain sentences.
4. **Why here**, one or two sentences: the user's own reason. Never praise copied from the company's site.
5. **Close.** A practical detail that matters (location, start, work authorization), a plain thank-you, the
   name.

## Rules

- Every sentence traces to STORIES, NUMBERS or PROFILE (AGENTS.md rule 1). Numbers keep their status word.
- Don't repeat resume bullets word for word. Add the how and why the bullet had no room for.
- The same title layer and contact line as the resume.
- Address a named person only if the posting names one. Otherwise "Dear Hiring Manager".
- No salary, unless the posting requires it. Then use the answers in SCREEN.md.
- Check the company name, job title and req number last. A letter with the previous company's name ends the
  application.

## The paragraph bank

`<data>/cover-letters/BANK.md`: one approved paragraph per theme in PERSONA.md, with its stories. A letter
is then an opening, two bank paragraphs picked for the posting, a fresh "why here" and a close. Read the
whole letter against the posting each time anyway.

## Files

- Text: `<data>/cover-letters/<company>-<req>.md`.
- A form's text box: plain text, no formatting. Check the character limit, paste, then re-read the breaks.
- An upload: the same font and contact line as the resume, one page, saved as
  `First_Last_Cover_Letter_<Company>.pdf`. Build it with python-docx from a script kept in `<data>/`, or
  give the user the text to paste into their word processor. Then look at the page image as you do for the
  resume.
- The user approves the exact text. Record the letter in the application's handoff and in PIPELINE.md.

## Short answers on forms

- "Why do you want to work here?": three to five sentences, same rules as the letter.
- "Tell us about a time you...": one story from STORIES.md in four sentences: the problem, their part, the
  result, what they'd do the same or differently.
- A thank-you after an interview: three sentences about the conversation, to the interviewers only. The
  user sends it.
