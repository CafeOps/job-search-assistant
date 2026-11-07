# 09. What your tool can do, and the fallbacks

Two families, both on a paid plan:
- **ChatGPT:** Codex (app or terminal), or the ChatGPT desktop app.
- **Claude:** Claude Code (the Code tab in the desktop app, or a terminal), or the Claude desktop app.

The workflow is the same in both. Decide from abilities, not the app's name.

## Abilities and fallbacks

`tools/setup_check.py` probes most of these and writes `<data>/SETUP.md`. Ask the user whether Gmail is
connected in their app. Browser control needs the readiness test below.

| Ability | Unlocks | Without it |
|---|---|---|
| Local files and terminal | profile files, harvest, scripts | the user runs your commands and pastes the output |
| Runs on the user's own computer (a cloud sandbox can't reach their folders or scheduler) | harvest, scheduling, password store | the user runs that command on their computer |
| Network | the job scan | the user runs the scan on their computer |
| Scheduler | the daily run | the user runs the scan when they want it |
| Mail connector (Gmail connected in ChatGPT or Claude settings) | daily email, no password stored | SMTP app password, or digest-only |
| Password store plus a window or terminal | SMTP fallback | digest-only |
| Browser control | filling in applications | application packet the user fills in |

## The daily email: pick one

1. **Mail connector** (simplest). The user connects Gmail in the app's settings once. The scheduled run asks
   the app's command line to send the digest file:
   - Claude: `scanner/run.ps1 -Mail claude` or `MAIL=claude bash scanner/run.sh` (runs `claude -p`). Check the
     Gmail tool's name with `/mcp` in Claude Code and set `email.claude_tool` if it differs.
   - ChatGPT: `scanner/run.ps1 -Mail codex` or `MAIL=codex bash scanner/run.sh` (runs `codex exec` with the
     ChatGPT Gmail connector).

   Both use the default model unless `email.ai_model` is set. Picks count as sent only when the command exits
   cleanly and prints exactly `SENT`.
2. **SMTP fallback** (no connector). `tools/email_setup.py --install-deps` (ask first), then
   `--configure --provider gmail --from <sender> --to <recipient>`. The user makes an app password (Gmail: turn
   on 2-Step Verification, then https://myaccount.google.com/apppasswords. Work, school and security-key-only
   accounts often can't), runs `--password` themselves and pastes it into the box that opens. The password
   never goes through the chat. Then an approved `--test`.
3. **Digest-only.** No email. The scan writes the digest file and the picks stay queued until the user has read
   it (`docs/06-daily-scan.md`).

## Filling in applications in the browser

- **Claude:** Claude in Chrome (the user's own Chrome), or the desktop app's built-in browser.
- **ChatGPT:** ChatGPT agent mode (its own browser), or computer use where the plan offers it.

In both, the user signs in to job sites and approves each submit. The AI never types a password. Some sites
block automated browsers. Run the readiness test in `docs/07-apply-on-behalf.md` first. If it fails, use the
application packet: every answer ready to paste, in the form's order.

## Optional extras

- **Drafts and outreach notes:** always fine. The user sends each one, or approves its exact text before you
  send it through a connector (`docs/08-outreach.md`).
- **Phone:** Claude Remote Control or the mobile apps. ChatGPT: the mobile app.

## Acceptance checklist (run in both families before sharing a new version)

- [ ] **Startup:** a fresh session reads AGENTS.md (Codex directly, Claude through CLAUDE.md, ChatGPT desktop
      from the attached file) and starts at stage 0.
- [ ] **Recovery:** stop mid-intake, start a new session, say "continue". It resumes from PROGRESS.md without
      re-asking.
- [ ] **Resume:** from the example profile, `tools/build_resume.py` shows no FAIL, the AI looks at every page
      image, and the bullets map to STORIES and NUMBERS and pass the banned list.
- [ ] **Screening:** a pasted posting gets the verdict format from `docs/05-jd-screen.md`.
- [ ] **Daily email:** the connector sends the digest and acknowledges the batch. SMTP and digest-only also work.
- [ ] **Applying:** the readiness test passes, or an application packet is produced.
- [ ] **No secrets in chat:** no password is ever asked for in the conversation.
