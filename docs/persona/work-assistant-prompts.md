# Persona: questions for the AI assistant at work

Many employers give staff an AI assistant that can search the user's own work email, chats, meetings and
files (Microsoft 365 Copilot, Gemini in Google Workspace and others). It can rebuild a timeline of projects
that no memory holds. It is the last item of the sweep map (`1-evidence-sweep.md`).

## Rules first

- The user runs these at work, in the work assistant. You never touch it and never sign in to it.
- **Skip this step** if they work under strict rules (health care, finance, defence, law, government), if
  their employer watches for data leaving, or if they are not sure it is allowed.
- **Tell them this first:** "Your employer can see what you ask its assistant. A run of questions about
  your whole career can look like a job search. On a quiet search, ask only two or three (the timeline, the
  growth one, the recurring-work one), spread over a few days, the way you would before a yearly review."
- They ask about their OWN work only.
- The assistant's raw answers stay at work: never forwarded, synced or pasted out whole. What comes home
  is the user's own short notes about their own work, in their own words: project names in plain words,
  their part, the months, rough size. Never customer or patient names, coworkers' words, money figures,
  ticket numbers, security details, file names or another person's information.
- The assistant can be wrong. It mixes up who did what and guesses at dates. Every item is a prompt for the
  interview, marked unconfirmed, until the user says "yes, that was me, and that is right".

## The prompts

The user pastes one at a time, changes the dates, and asks again by year if the answer stops short. Give
them the list as text they can open at work.

1. **The job.** "From my emails, chats, meetings and files over the last 12 months, describe my job: my main
   responsibilities, the systems and tools I work in, the people and teams I work with most, and what I am
   asked for most often. Use only what you can find, and say where each point comes from."
2. **The timeline.** "Build a timeline of the projects and major pieces of work I was part of from
   <month year> to today, by quarter. For each: a plain name, what it was for, my role, when it started and
   ended, and how it turned out. Cite the emails, meetings or files each entry comes from."
3. **Above and beyond.** "List the things I did that went beyond my normal duties in that period: problems
   I solved that weren't mine, things I built or automated, processes I improved, times I covered for
   someone, work I led without being asked. Give the date and the evidence for each."
4. **Recognition.** "Find times my work was thanked or praised. For each, give the month, what it was
   about and what I had done. No names and no quotes."
5. **Size.** "For the projects in the timeline, what was the rough size of my part: how many people,
   sites, devices or requests, how long it took, deadlines met? Leave out money, customer and security
   figures, and say whether each was measured or estimated."
6. **Growth.** "How did my responsibilities change from <month year> to today? What did I take on, what did
   I stop doing, and when? What am I trusted with now that I wasn't at the start?"
7. **Tools and skills.** "List every tool, system, language and method I used in that period, with the
   first and latest date you can find for each and what I used it for."
8. **Reviews and goals.** "Summarize my performance reviews, goals and feedback in that period: what I was
   asked to achieve, what was said about how I did, and what I was asked to improve."
9. **What it missed.** "What recurring work do I do every week or month that doesn't show up as a project?"

## What to do with the answers

1. At home, the user types their own notes into a file, or reads them to you.
2. Save the file in `<data>/source/evidence/` and add it to `<data>/EVIDENCE.md` as "work assistant summary,
   unconfirmed".
3. Put each project on the spine with its dates. Each one is a story to take down the ladder in
   `2-deep-interview.md`. Each number is a question: "Is this right? How do you know?"
4. Nothing from these notes reaches a resume until the user has confirmed it in the interview.
