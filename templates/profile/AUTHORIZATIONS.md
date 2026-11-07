# Authorizations

Standing permissions the user gave. Anything not listed needs a fresh yes for that one item.

## Daily job email
- Approved on: YYYY-MM-DD
- Sends: the daily digest file only (job titles, companies, links, pay). No other files.
- From / to:
- Schedule:
- Method: smtp (password in the system password store), claude or codex (Gmail connector), or none (digest only)
- To stop it: say "pause the daily scan", or run the uninstall in docs/06-daily-scan.md

## Applications
One line per application. Preparing a handoff is NOT permission to submit.
| Date | Company / req | Prepare | Submit | Show summary before submit? |
|---|---|---|---|---|
