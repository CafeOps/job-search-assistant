# 06. Daily job scan

`scanner/jobscan.py` finds new postings, filters them by the user's rules and writes a plain-text digest.
The run script emails it, then marks those jobs sent. A failed email keeps them queued for the next run.

Sources: LinkedIn's public guest search (no login) and an employer watchlist on public ATS feeds
(Greenhouse, Lever, Ashby, Workday). Indeed blocks scripts, so it isn't used. The scan runs on the user's
computer because cloud AI sandboxes usually allowlist sites: job sites are blocked and posting dates can't
be confirmed. LinkedIn often blocks cloud addresses too.

## 1. Build the config

Copy `scanner/config.example.json` to `<data>/scanner-config.json` and fill it from the intake (compare
with `examples/jordan-rivera/scanner-config.json`):
- `keywords`: 5 to 20 search terms. More terms, longer run.
- `linkedin.searches`: their city with a radius, plus a country-wide remote search if wanted.
- `title_exclude_seniority`, `title_exclude_words`: from their seniority answer and "refuse" list.
- `lane_title_words`, `stack_terms`, `core_terms`: words a posting in their lane uses.
- `location_words`: towns in commuting range. `remote_country`: where they can legally work.
- `currency`, `pay_floor`, `pay_ceiling`, `pay_prefer_pattern`: their money answers. A range that reaches
  the floor only at the top stays in, labelled "Pay range crosses your floor".
- `contracts`: allowed, minimum months, hourly floor, contract-to-perm only.
- `exclude_companies` (current employer, applications in progress), `flag_companies` (an agency already
  submitted them), `agency_words`.
- `watchlist`: employers they'd love to work at (below).
- `max_detail_fetches` (default 60): full postings opened per run. The rest are listed, not rejected.

## 2. Test it (changes nothing)

1. Quick check, a minute or two: `<python> scanner/jobscan.py --dry --quick`.
2. Full test: `<python> scanner/jobscan.py --dry`. It takes 10 to 20 minutes because it reads slowly on
   purpose. Run it in the background, tell the user, and watch the progress lines. Silence for a few
   minutes is not a hang.

Read the digest with the user (`<data>/scan/out/<date>.txt`) and tune. The `.json` beside it lists every
rejected posting and why, the fastest way to spot a filter that is too tight. Act on any "SCAN PROBLEMS"
or "COULD NOT CHECK" section before trusting "no matches". Screen each pick (`docs/05-jd-screen.md`). Set
`scan: tested` in PROGRESS.md when the user is happy with the results.

## 3. Email

Pick a mode in "The daily email" (`docs/09-tool-setup.md`) and set `email.mode` in the config (`claude`,
`codex`, `smtp` or `none`), or pass it to the run script.

`none` is digest-only: no email. The run writes the digest and prints `DIGEST <path>`. The picks stay
queued and return in the next digest until the user has read it and you run
`<python> scanner/jobscan.py --mark-read-latest` (newest batch) or `--mark-sent <batch>` (a specific one).

Send one approved test, have the user confirm it arrived, and record the standing permission in
`<data>/AUTHORIZATIONS.md`.

## 4. Schedule it, then prove it

**Windows:** `powershell -ExecutionPolicy Bypass -File scanner\install-task.ps1 -Time 07:00` registers
"Job Search Assistant - daily scan". It runs only while the PC is on and the user is signed in, and
catches up if the PC was off or asleep at the set time.

**Mac:** `bash scanner/install-launchagent.sh 07:00` installs a launchd job. It catches up when the Mac
wakes.

Registering does not run the task. The first run is at the set time. To prove the schedule now, add
`-RunNow` to the Windows install command, or run `bash scanner/install-launchagent.sh --run-now` on a Mac.
Either starts one real run and SENDS A REAL EMAIL, so ask first.

Setup is done only when an email from the scheduled run arrives and the user confirms it. Then set
`email: verified <date>` in PROGRESS.md.

## Everyday commands (the user can just ask)

| User says | You run |
|---|---|
| "Is my job email working?" | `<python> scanner/jobscan.py --status` (last scan, last delivery, queued, next run, problems) |
| "Run it now" | Windows: `powershell -ExecutionPolicy Bypass -File scanner\run.ps1` / Mac: `bash scanner/run.sh` |
| "Pause the daily scan" | Windows: `powershell -ExecutionPolicy Bypass -File scanner\install-task.ps1 -Uninstall` / Mac: `bash scanner/install-launchagent.sh --uninstall` (reinstall to resume) |
| "Change what it looks for" | edit `<data>/scanner-config.json`, then `--dry` to check |
| "Stop and remove everything" | uninstall the schedule, then `<python> tools/email_setup.py --remove` |

## The employer watchlist (most reliable source)

LinkedIn's guest pages are not an official API and can change. Employer ATS feeds are public JSON: stable,
real dates, not blocked.

| ATS | Careers URL looks like | Config |
|---|---|---|
| Greenhouse | `boards.greenhouse.io/<slug>` or `job-boards.greenhouse.io/<slug>` | `{"ats": "greenhouse", "slug": "<slug>"}` |
| Lever | `jobs.lever.co/<slug>` | `{"ats": "lever", "slug": "<slug>"}` |
| Ashby | `jobs.ashbyhq.com/<slug>` | `{"ats": "ashby", "slug": "<slug>"}` |
| Workday | `<company>.wd5.myworkdayjobs.com/en-US/<site>/...` | `{"ats": "workday", "host": "<host>", "slug": "<tenant>/<site>"}` (tenant is usually the first word of the host) |
