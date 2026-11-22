# Persona: questions for the AI assistant at work

Many employers give staff an AI assistant that can search the user's own work email, chats, meetings and
files (Microsoft 365 Copilot, Gemini in Google Workspace and others). It can rebuild a timeline of projects
that no memory holds. It is step 16 of the sweep (`1-evidence-sweep.md`).

## Rules first

- The user runs these at work, in the work assistant. You never touch it and never sign in to it.
- They ask about their OWN work only. They check their employer's rules on AI tools and on taking notes
  home. If unsure, they ask, or they skip this step.
- What comes home is the user's own notes about their own work: project names in plain words, their part,
  dates, counts. Never customer names, internal documents, financial results, security details, or another
  person's information. They read every answer and strip those before it leaves.
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
4. **Praise.** "Find messages where someone thanked me, praised my work, or told others about something I
   did. Give the date, who said it (their role, not their name), and their exact words."
5. **Numbers.** "For the projects in the timeline, find any numbers tied to my work: how many users,
   devices, sites, tickets, records or dollars, time saved, deadlines met, before and after. Quote the
   source for each and say whether it was measured or estimated."
6. **Growth.** "How did my responsibilities change from <month year> to today? What did I take on, what did
   I stop doing, and when? What am I trusted with now that I wasn't at the start?"
7. **Tools and skills.** "List every tool, system, language and method I used in that period, with the
   first and latest date you can find for each and what I used it for."
8. **Reviews and goals.** "Summarize my performance reviews, goals and feedback in that period: what I was
   asked to achieve, what was said about how I did, and what I was asked to improve."
9. **What it missed.** "What recurring work do I do every week or month that doesn't show up as a project?"

## What to do with the answers

1. The user cleans them (the rules above) and brings their notes home, typed or pasted into a file.
2. Save the file in `<data>/source/evidence/` and add it to `<data>/EVIDENCE.md` as "work assistant summary,
   unconfirmed".
3. Put each project on the spine with its dates. Each one is a story to take down the ladder in
   `2-deep-interview.md`. Each number is a question: "Is this right? How do you know?"
4. Nothing from these notes reaches a resume until the user has confirmed it in the interview.
