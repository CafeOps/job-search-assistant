# Job Search Assistant

Turn your paid ChatGPT or Claude plan into your own job-search helper.

## Use the right tool

| Your plan | Use this | Not this |
|---|---|---|
| Paid ChatGPT (Plus, Pro, Business) | **Codex** (the Codex app, or Codex in a terminal) | the normal ChatGPT chat window |
| Paid Claude (Pro, Max, Team) | **Claude Code** (the **Code** tab in the Claude desktop app, or Claude Code in a terminal) | the normal Claude chat window |

Why: the kit needs an AI that can work with files and run programs on your computer, and chat windows can't.
Free plans and other AI tools aren't supported.

## Start

1. Open Codex (get it from the ChatGPT website) or Claude Code (the **Code** tab in the Claude desktop app, or
   install it from the Claude website). Sign in with your ChatGPT or Claude account.
2. Start a new session and paste this:

> Download https://github.com/CafeOps/job-search-assistant and set it up for me. Read its AGENTS.md first.
> Do the computer setup yourself. Ask me only for personal answers, sign-ins and approvals.

When the AI asks permission to run something, read it, then allow it.

Last resort, if you truly can't use Codex or Claude Code: download the ZIP (green **Code** button, **Download
ZIP**), extract it, attach `AGENTS.md` to a normal chat and say "Follow this." It can interview you, write your
resume text and screen job postings, but you run every step on your computer yourself.

## What it does

You answer questions about your work and goals (rough answers are fine). The AI does the rest, with your approval:

- finds your old resumes and cover letters (you approve which ones)
- interviews you, then writes down your goals, pay floor, deal breakers and best work stories
- rebuilds your resume (Word and PDF) in your own words, with only true claims
- emails you new matching jobs every morning, once you approve it
- tells you APPLY or SKIP on any job posting you paste
- fills in applications in your browser (you sign in and approve every submit)

You don't need to code. The AI does the technical parts and asks before installing anything.

## What you need

- A Windows 10/11 PC or a Mac, and a paid ChatGPT or Claude plan. No API key.
- About an hour for setup, in one or two sittings. Stop any time and say "continue" later.
- For the daily email: the Gmail connector in your ChatGPT or Claude account, or an email account that can make
  an "app password" (Gmail, Outlook, Yahoo, iCloud and most others can). You type it into a password box
  on your screen, never into the chat.

## Privacy

- Your files stay in a job-hunt folder you choose (default `Documents\Job Hunt`, Mac `~/Job Hunt`), outside the
  assistant's folder. Updating or re-downloading the assistant can't touch them, and they never reach GitHub.
- The AI's provider processes whatever the AI reads, like any chat. The daily email goes through your email
  provider (and, with the connector, your AI app).
- OneDrive, iCloud and Dropbox keep copies of anything in their folders.
- To share the assistant, send the link above. Never send your job-hunt folder.

## Good to know

- The daily scan runs on your computer, so only while it's on and you're signed in. If it was off at the set
  time, it runs when you're back.
- Something broke? Say "Run the status check and fix what's wrong." To pause the email: "Pause the daily scan."
  To remove it all: "Uninstall the daily scan and delete my saved email password."
- The scan reads LinkedIn's public job pages, which isn't an official API: it can stop working and reads slowly,
  once a day. Company career sites on your watchlist are more reliable.
- Job matches are a first pass. Read the full posting.
- It won't write things that aren't true.

## For the technical folks

`AGENTS.md` is the AI's entry point (Codex reads it directly, Claude Code reads `CLAUDE.md`, which imports it). `docs/` holds the step guides,
`scanner/` the daily scan (stdlib Python 3.9+), `tools/` the scripts, `templates/` the profile skeleton and
`examples/` a complete fake profile. The data folder comes from `JOBHUNT_DATA_DIR`, then the per-user config
that `tools/setup_check.py --data-dir` writes, then a legacy `profile/` folder in the kit.
