"""Daily job scan. Config-driven, standard library only (Python 3.9+).

Sources:
  - LinkedIn public guest search (no login), for discovery. Real posting dates.
  - An employer watchlist on public ATS feeds: Greenhouse, Lever, Ashby, Workday.

Usage ("<python>" is the Python command from setup, for example `py -3` on Windows or `python3` on a Mac):
  <python> scanner/jobscan.py                      # scan, write the digest, queue the picks in the outbox
  <python> scanner/jobscan.py --dry                # scan, write the digest, don't touch state
  <python> scanner/jobscan.py --quick              # short test run: 1 keyword, 1 page per search, 15 detail fetches
  <python> scanner/jobscan.py --mark-sent <batch>  # after the email went out: acknowledge exactly that batch
  <python> scanner/jobscan.py --mark-read-latest   # digest-only mode: acknowledge the newest batch after the user has read it
  <python> scanner/jobscan.py --status             # last scan, last delivery, queued picks, next run, problems
  <python> scanner/jobscan.py --config other.json  # use another config (default: <data folder>/scanner-config.json)
  <python> scanner/jobscan.py --state-dir DIR      # keep state somewhere else (default: <data folder>/scan)
  <python> scanner/jobscan.py -h                   # this text

Progress prints to stderr (at most every 5 seconds). Config "max_detail_fetches" (default 60) caps how many
full postings are opened per run; the rest are listed under COULD NOT CHECK, not rejected.

The last line of a normal run is "BATCH <id> <digest path>". The run scripts pass both to the mail step.

State (all inside <data folder>/scan/; every write is temp-file then os.replace):
  out/YYYY-MM-DD.txt   the digest to email (contains "Batch: <id>")
  out/YYYY-MM-DD.json  every candidate with its reject reason
  outbox.json          picks not yet acknowledged, plus the batch ids handed to the mail step
  seen.json            picks already sent: ids forever, company|title keys for 60 days
  firstseen.json       first time a posting with no published date was seen
  status.json          last scan, last delivery, problems
  run.lock             exists only while a scan or acknowledgement is running
"""
import contextlib
import datetime as dt
import functools
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

with contextlib.suppress(Exception):  # job titles with odd characters on Windows
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import paths  # noqa: E402  (the shared data-folder resolver)
UTC = dt.timezone.utc
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
KEY_DAYS = 60            # company|title fallback keys expire after this many days
LOCK_STALE_HOURS = 3
HEALTH = []              # source problems, printed at the top of the digest
DETAIL_FAILS = {}        # (source, http code) -> count

CFG = {}
STATE = OUT = SEEN = OUTBOX = STATUS = FIRSTSEEN = LOCK = None


def arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else default
    return default


# ---------- config ----------

@functools.cache
def term_re(term):
    """Case-insensitive match of a term that must not touch other word characters.
    Works for terms with punctuation: c++, c#, .net. 'sql' does not match NoSQL; 'excel' not excellent."""
    return re.compile(r"(?<![\w])" + re.escape(term.strip()) + r"(?![\w])", re.I)


def words(lst):
    """One regex for a list of words or phrases (same boundary rule as term_re)."""
    lst = sorted({w.strip() for w in (lst or []) if w and w.strip()}, key=len, reverse=True)
    if not lst:
        return None
    return re.compile(r"(?<![\w])(?:" + "|".join(re.escape(w) for w in lst) + r")(?![\w])", re.I)


def set_state(path):
    global STATE, OUT, SEEN, OUTBOX, STATUS, FIRSTSEEN, LOCK
    STATE = Path(path)
    OUT, SEEN, OUTBOX = STATE / "out", STATE / "seen.json", STATE / "outbox.json"
    STATUS, FIRSTSEEN, LOCK = STATE / "status.json", STATE / "firstseen.json", STATE / "run.lock"


def init(cfg, state_dir=None):
    """Load a config dict into the module globals. Tests call this with their own dict."""
    global CFG, SENIOR, OFFLANE, TITLE_KEEP, LANE, PLACES, EXCLUDE_CO, INCLUDE_CO, FLAG_CO, AGENCY
    global STACK, CORE, PAY_PREFER, PAY_AVOID, MAX_AGE_H, CURRENCY
    CFG = cfg
    SENIOR = words(cfg.get("title_exclude_seniority"))
    OFFLANE = words(cfg.get("title_exclude_words"))
    TITLE_KEEP = words(cfg.get("title_exceptions"))
    LANE = words(cfg.get("lane_title_words"))
    PLACES = words(cfg.get("location_words"))
    EXCLUDE_CO = words(cfg.get("exclude_companies"))
    INCLUDE_CO = words(cfg.get("include_companies"))
    FLAG_CO = words(cfg.get("flag_companies"))
    AGENCY = words(cfg.get("agency_words"))
    STACK = [s.lower() for s in cfg.get("stack_terms", [])]
    CORE = [s.lower() for s in cfg.get("core_terms", [])]
    PAY_PREFER = re.compile(cfg.get("pay_prefer_pattern") or r"$^", re.I)
    PAY_AVOID = re.compile(cfg.get("pay_avoid_pattern") or r"$^", re.I)
    MAX_AGE_H = int(cfg.get("max_age_hours", 48))
    CURRENCY = (cfg.get("currency") or "USD").upper()
    HEALTH.clear()
    DETAIL_FAILS.clear()
    set_state(state_dir or STATE or paths.data_dir() / "scan")


set_state(paths.data_dir() / "scan")
init({})


def load_config(path):
    path = Path(path)
    if not path.exists():
        sys.exit(f"No config at {path}. Copy scanner/config.example.json to <data folder>/scanner-config.json "
                 "and fill it in (the intake interview does this for you).")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        sys.exit(f"The config file {path} is not valid JSON: {e}")


# ---------- small helpers ----------

SLOW_HOSTS = {}          # host -> sleep multiplier, doubled after the host's first HTTP 429 (this run only)
MAX_PAUSE = 20.0
_LAST_PROGRESS = [0.0]


def host_of(url):
    return urllib.parse.urlparse(url).netloc.lower()


def pause(url, seconds):
    """Sleep between requests to one host. After that host sent a 429, the pause is doubled (capped)."""
    time.sleep(min(MAX_PAUSE, float(seconds) * SLOW_HOSTS.get(host_of(url), 1)))


def progress(msg, force=False):
    """Print a progress line to stderr, at most once every 5 seconds."""
    now = time.monotonic()
    if force or now - _LAST_PROGRESS[0] >= 5:
        _LAST_PROGRESS[0] = now
        print(msg, file=sys.stderr, flush=True)


def get(url, data=None, tries=3):
    code = 0
    for i in range(tries):
        try:
            headers = {"User-Agent": UA, "Accept-Language": CFG.get("accept_language", "en-US,en;q=0.9")}
            body = None
            if data is not None:
                body = json.dumps(data).encode()
                headers["Content-Type"] = "application/json"
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            code = e.code
            if code != 429:
                return code, ""
            host = host_of(url)
            if host not in SLOW_HOSTS:
                SLOW_HOSTS[host] = 2
                HEALTH.append(f"{host} answered 'too many requests' (HTTP 429). The scan slowed down for "
                              "that site for the rest of this run.")
            time.sleep(min(MAX_PAUSE, 20 * (i + 1)))
        except Exception:
            code = 0
            time.sleep(5)
    return code, ""


def text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def grab(pattern, s):
    """First capture group of the first match in s, or an empty string."""
    m = re.search(pattern, s, re.S)
    return m.group(1) if m else ""


_ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5"}


def norm_title(t):
    """Lower-case, punctuation stripped. Level numerals stay, so 'Analyst I' and 'Analyst II' differ
    ('I' and '1' are treated as the same level)."""
    toks = re.sub(r"[^a-z0-9 ]", " ", (t or "").lower()).split()
    if toks and toks[-1] in _ROMAN:
        toks[-1] = _ROMAN[toks[-1]]
    return " ".join(toks)


def dedupe_key(j):
    return f"{j['company'].lower()}|{norm_title(j['title'])}"


def write_json(path, obj):
    """Atomic: write a temp file in the same folder, then os.replace."""
    write_text(path, json.dumps(obj, indent=1))


def write_text(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(body, encoding="utf-8")
    os.replace(tmp, path)


def load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else default
    except ValueError:
        return default


@contextlib.contextmanager
def run_lock():
    STATE.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        age_h = (time.time() - LOCK.stat().st_mtime) / 3600 if LOCK.exists() else 0
        if age_h < LOCK_STALE_HOURS:
            sys.exit(f"Another scan is running (lock file {LOCK}). Try again later.")
        LOCK.unlink(missing_ok=True)  # left behind by a crash
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, f"{os.getpid()} {dt.datetime.now(UTC).isoformat()}".encode())
        os.close(fd)
        yield
    finally:
        LOCK.unlink(missing_ok=True)


# ---------- dates ----------

def parse_when(s):
    """-> (aware UTC datetime or None, date_only). A date-only value counts as the END of that day, so a
    posting dated 'today' is never rejected as old. Years before 2000 (epoch zero) are treated as missing."""
    s = (s or "").strip()
    if not s:
        return None, False
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            d = dt.date.fromisoformat(s)
            x = dt.datetime(d.year, d.month, d.day, tzinfo=UTC) + dt.timedelta(days=1)
            return (x, True) if d.year >= 2000 else (None, False)
        x = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if x.tzinfo is None:
            x = x.replace(tzinfo=UTC)
        x = x.astimezone(UTC)
        return (x, False) if x.year >= 2000 else (None, False)
    except ValueError:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
        return parse_when(m.group(1)) if m and m.group(1) != s else (None, False)


def ms_to_iso(ms):
    try:
        ms = float(ms)
        return dt.datetime.fromtimestamp(ms / 1000, UTC).isoformat() if ms > 0 else ""
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def resolve_dates(j, now, firstseen):
    """Set posted (display), age_hours and date_unknown. With no published date the first-seen time is used
    and the digest says so. updated_at is never shown as the posting date."""
    when, _ = parse_when(j.get("published_at"))
    if when:
        j["date_unknown"] = False
        j["posted"] = (j["published_at"] or "")[:10]
    else:
        first = firstseen.setdefault(j["id"], now.isoformat())
        j["first_seen_at"] = first
        when, _ = parse_when(first)
        when = when or now
        j["date_unknown"] = True
        j["posted"] = f"date unknown, first seen {first[:10]}"
    j["age_hours"] = max(0.0, (now - when).total_seconds() / 3600)


def job(src, board, jid, title, company, location, published="", link="", desc="", updated="", **extra):
    full = f"{src}:{board}:{jid}" if board else f"{src}:{jid}"
    return {"source": src, "id": full, "title": text(title), "company": text(company),
            "location": text(location), "published_at": published or "", "updated_at": updated or "",
            "link": link, "desc": text(desc), "flags": [], **extra}


# ---------- source: LinkedIn guest search ----------

def linkedin():
    li = CFG.get("linkedin", {})
    if not li.get("enabled", True):
        return {}
    jobs, calls, errors = {}, 0, {}
    hours = max(MAX_AGE_H, 24)
    total_searches = len(CFG.get("keywords", [])) * len(li.get("searches", []))
    done_searches = 0
    for kw in CFG.get("keywords", []):
        for s in li.get("searches", []):
            done_searches += 1
            progress(f"LinkedIn search {done_searches} of {total_searches} ({len(jobs)} listings so far)...")
            for page in range(int(li.get("pages", 3))):
                q = {"keywords": kw, "location": s["location"], "f_TPR": f"r{hours * 3600}",
                     "start": str(page * 10)}
                if s.get("distance"):
                    q["distance"] = str(s["distance"])
                if s.get("remote"):
                    q["f_WT"] = "2"
                code, body = get("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
                                 + urllib.parse.urlencode(q))
                calls += 1
                pause("https://www.linkedin.com/", li.get("sleep_seconds", 1.5))
                if code != 200:
                    errors[code] = errors.get(code, 0) + 1
                    break
                cards = body.split("<li>")[1:]
                for c in cards:
                    m = re.search(r"jobPosting:(\d+)", c)
                    if not m or f"linkedin:{m.group(1)}" in jobs:
                        continue
                    j = job("linkedin", "", m.group(1), grab(r'base-search-card__title">(.*?)</h3>', c),
                            grab(r'base-search-card__subtitle">(.*?)</h4>', c),
                            grab(r'job-search-card__location">(.*?)</span>', c),
                            grab(r'datetime="([\d-]+)"', c),
                            f"https://www.linkedin.com/jobs/view/{m.group(1)}/",
                            remote_search=bool(s.get("remote")), found_by=f"{kw} | {s['location']}")
                    jobs[j["id"]] = j
                if len(cards) < 10:
                    break
    if errors:
        HEALTH.append(f"LinkedIn: {sum(errors.values())} of {calls} searches failed (HTTP {errors}). "
                      "403/999 usually means the IP is blocked. Run from a home connection.")
    if calls and not jobs:
        HEALTH.append("LinkedIn: 0 listings from every search. The scan probably didn't work today.")
    return jobs


def note_fail(source, code):
    DETAIL_FAILS[(source, code)] = DETAIL_FAILS.get((source, code), 0) + 1


def linkedin_detail(j):
    """-> 'ok', 'closed' or 'failed'. Never raises."""
    try:
        code, body = get(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{j['id'].split(':')[-1]}")
        pause("https://www.linkedin.com/", CFG.get("linkedin", {}).get("sleep_seconds", 1.5))
        if code in (404, 410):
            j["closed"] = True
            return "closed"
        if code != 200 or not body:
            note_fail("LinkedIn", code)
            return "failed"
        j["desc"] = text(grab(r'description__text[^>]*>(.*?)</section>', body))
        crit = {text(a): text(b) for a, b in re.findall(
            r'description__job-criteria-subheader">(.*?)</h3>.*?description__job-criteria-text[^>]*>(.*?)</span>',
            body, re.S)}
        j["seniority"] = crit.get("Seniority level", "")
        j["type"] = crit.get("Employment type", "")
        j["closed"] = "No longer accepting applications" in body
        j["salary_box"] = text(grab(r'salary compensation__salary">(.*?)</div>', body))
        if j["closed"]:
            return "closed"
        if not j["desc"]:
            note_fail("LinkedIn", "empty page")
            return "failed"
        return "ok"
    except Exception:
        note_fail("LinkedIn", "parse error")
        return "failed"


# ---------- source: employer watchlist (public ATS feeds) ----------

def watchlist():
    jobs = {}
    for w in CFG.get("watchlist", []):
        ats, name, slug = w.get("ats", "").lower(), w.get("company", ""), w.get("slug", "")
        fn = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "workday": workday}.get(ats)
        if not fn:
            HEALTH.append(f"Watchlist: unknown ats '{ats}' for {name}.")
            continue
        try:
            got = fn(w, name, slug)
        except Exception as e:  # one broken employer must not stop the scan
            HEALTH.append(f"Watchlist: {name} ({ats}) failed: {e}")
            continue
        if got is None:
            HEALTH.append(f"Watchlist: {name} ({ats}) returned nothing. Check the slug.")
            continue
        jobs.update(got)
    return jobs


def greenhouse(w, name, slug):
    code, body = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    if code != 200:
        return None
    out = {}
    for p in json.loads(body).get("jobs", []):
        try:
            # first_published is the posting date. updated_at changes on every edit, so it is kept apart.
            j = job("greenhouse", slug, p["id"], p.get("title"), name, (p.get("location") or {}).get("name", ""),
                    p.get("first_published") or "", p.get("absolute_url"),
                    html.unescape(p.get("content", "")), updated=p.get("updated_at") or "")
            out[j["id"]] = j
        except Exception:
            continue
    return out


def lever(w, name, slug):
    code, body = get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if code != 200:
        return None
    out = {}
    for p in json.loads(body):
        try:
            cat = p.get("categories") or {}
            parts = [p.get("descriptionPlain") or text(p.get("description", ""))]
            for lst in p.get("lists") or []:
                parts.append(f"{text(lst.get('text', ''))}: {text(lst.get('content', ''))}")
            parts.append(p.get("additionalPlain") or text(p.get("additional", "")))
            extra = p.get("allLocations") or cat.get("allLocations") or []
            sr = p.get("salaryRange")
            j = job("lever", slug, p["id"], p.get("text"), name, cat.get("location", ""),
                    ms_to_iso(p.get("createdAt")), p.get("hostedUrl"), "\n".join(x for x in parts if x),
                    type=cat.get("commitment", ""), extra_loc=[text(x) for x in extra],
                    country_hint=p.get("country") or "",
                    remote_search=p.get("workplaceType") == "remote",
                    salary_struct=({"min": sr.get("min"), "max": sr.get("max"), "currency": sr.get("currency"),
                                    "interval": sr.get("interval")} if sr else None))
            out[j["id"]] = j
        except Exception:
            continue
    return out


def ashby(w, name, slug):
    code, body = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    if code != 200:
        return None
    out = {}
    for p in json.loads(body).get("jobs", []):
        try:
            comp = (p.get("compensation") or {}).get("compensationTierSummary", "")
            addr = ((p.get("address") or {}).get("postalAddress") or {})
            sec = [(s.get("location") if isinstance(s, dict) else s) or "" for s in p.get("secondaryLocations") or []]
            j = job("ashby", slug, p.get("id"), p.get("title"), name, p.get("location", ""), p.get("publishedAt"),
                    p.get("jobUrl"), p.get("descriptionPlain", ""), type=p.get("employmentType", ""),
                    salary_box=comp or "", remote_search=bool(p.get("isRemote")), extra_loc=sec,
                    country_hint=addr.get("addressCountry") or "")
            out[j["id"]] = j
        except Exception:
            continue
    return out


def workday(w, name, slug):
    """slug = 'tenant/site', host = e.g. 'company.wd3.myworkdayjobs.com' (both from the careers URL)."""
    tenant, site = slug.split("/", 1)
    base = f"https://{w['host']}/wday/cxs/{tenant}/{site}"
    cap = int(w.get("max_results", CFG.get("workday_cap", 200)))
    out, today = {}, dt.date.today()
    for kw in w.get("keywords") or CFG.get("keywords", [])[:5]:
        offset, total = 0, None
        while offset < (cap if total is None else min(total, cap)):
            code, body = get(f"{base}/jobs", data={"limit": 20, "offset": offset, "searchText": kw,
                                                    "appliedFacets": {}})
            if code != 200:
                if not out and offset == 0:
                    return None
                HEALTH.append(f"Workday: {name} stopped at result {offset} for '{kw}' (HTTP {code}).")
                break
            try:
                data = json.loads(body)
            except ValueError:
                HEALTH.append(f"Workday: {name} returned a page that is not JSON for '{kw}'.")
                break
            if total is None:  # later pages often report 0, so only the first count is trusted
                total = int(data.get("total") or 0)
            posts = data.get("jobPostings") or []
            if not posts:
                break
            for p in posts:
                when = (p.get("postedOn") or "").lower()
                n = re.search(r"\d+", when)
                days = 0 if "today" in when else 1 if "yesterday" in when else int(n.group()) if n else None
                path = p.get("externalPath", "")
                if not path:
                    continue
                j = job("workday", f"{tenant}/{site}", path, p.get("title"), name, p.get("locationsText", ""),
                        (today - dt.timedelta(days=days)).isoformat() if days is not None else "",
                        f"https://{w['host']}/{site}{path}", wd_detail=f"{base}{path}")
                if days:
                    j["flags"].append(f"posting date estimated from '{p.get('postedOn')}'")
                out[j["id"]] = j
            offset += 20
            pause(base, 1)
        if total and total > cap:
            HEALTH.append(f"Workday: {name} has {total} results for '{kw}'; only the first {cap} were read.")
    return out


def workday_detail(j):
    """-> 'ok', 'closed' or 'failed'. Never raises."""
    try:
        code, body = get(j["wd_detail"])
        if code in (404, 410):
            j["closed"] = True
            return "closed"
        if code != 200:
            note_fail("Workday", code)
            return "failed"
        info = json.loads(body).get("jobPostingInfo") or {}
        j["desc"] = text(info.get("jobDescription", ""))
        j["type"] = info.get("timeType", "") or j.get("type", "")
        j["location"] = text(info.get("location", "")) or j["location"]
        j["extra_loc"] = [text(x) for x in (info.get("additionalLocations") or [])]
        j["country_hint"] = (info.get("country") or {}).get("descriptor") or ""
        if not j["desc"]:
            note_fail("Workday", "empty page")
            return "failed"
        return "ok"
    except Exception:
        note_fail("Workday", "parse error")
        return "failed"


# ---------- pay ----------

_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_SYM = r"US\$|CA\$|C\$|CAD\$|AU\$|A\$|NZ\$|\$|£|€"
_COD = r"USD|CAD|AUD|NZD|EUR|GBP|CHF|INR|SGD"
_RANGE = re.compile(
    r"(?<![\w.,])(?P<c1>" + _SYM + "|" + _COD + r")?\s*(?P<n1>" + _NUM + r")\s*(?P<k1>[kK])?(?![a-zA-Z])"
    r"\s*(?P<d1>" + _COD + r")?\s*(?:-|\u2013|\u2014|to|and)\s*"
    r"(?P<c2>" + _SYM + "|" + _COD + r")?\s*(?P<n2>" + _NUM + r")\s*(?P<k2>[kK])?(?![a-zA-Z])"
    r"\s*(?P<d2>" + _COD + r")?")
_CUR_CODE = {"US$": "USD", "USD": "USD", "CA$": "CAD", "C$": "CAD", "CAD$": "CAD", "CAD": "CAD",
             "AU$": "AUD", "A$": "AUD", "AUD": "AUD", "NZ$": "NZD", "NZD": "NZD", "£": "GBP", "GBP": "GBP",
             "€": "EUR", "EUR": "EUR", "CHF": "CHF", "INR": "INR", "SGD": "SGD", "$": None}
_PERIODS = [
    ("hour", re.compile(r"/\s*(?:hr|hour)\b|per\s+hour|\ban?\s+hour|hourly|\bph\b", re.I)),
    ("day", re.compile(r"/\s*day\b|per\s+day|\ba\s+day|daily|day rate", re.I)),
    ("week", re.compile(r"/\s*(?:wk|week)\b|per\s+week|\ba\s+week|weekly", re.I)),
    ("month", re.compile(r"/\s*(?:mo|month)\b|per\s+month|\ba\s+month|monthly", re.I)),
    ("year", re.compile(r"/\s*(?:yr|year|annum)\b|per\s+(?:year|annum)|\ba\s+year|annual|yearly|\bp\.?a\.?\b", re.I)),
]
PER_YEAR = {"hour": 2080, "day": 260, "week": 52, "month": 12, "year": 1}


def _find_period(after, before):
    for window in (after, before):
        best = None
        for name, rx in _PERIODS:
            m = rx.search(window)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), name)
        if best:
            return best[1]
    return None


def _interval_name(s):
    s = (s or "").lower()
    for name in ("hour", "day", "week", "month", "year"):
        if name in s:
            return name
    return "year" if "annual" in s or "salary" in s else None


def _make_pay(lo, hi, cur, period, raw):
    """Build the pay record, or None if the numbers make no sense."""
    if hi < lo or lo <= 0:
        return None
    if period is None:  # nothing said: a small number is hourly, a big one is yearly, the middle is unclear
        period = "hour" if hi < 1000 else "year" if lo >= 20000 else None
    if period is None:
        return None
    mult = PER_YEAR[period]
    return {"low": lo, "high": hi, "currency": cur, "period": period, "raw": raw.strip(),
            "annual_low": lo * mult, "annual_high": hi * mult,
            "comparable": cur in (None, CURRENCY)}


def pay(j):
    """Find the pay range in a posting. Returns a dict (low, high, currency, period, raw, annual_low,
    annual_high, comparable) or None. 'currency' is None when the posting only says '$'."""
    st = j.get("salary_struct")
    if st and st.get("min") and st.get("max"):
        cur = (st.get("currency") or "").upper() or None
        p = _make_pay(float(st["min"]), float(st["max"]), cur, _interval_name(st.get("interval")) or "year",
                      f"{st['min']} to {st['max']} {cur or ''} {st.get('interval') or ''}")
        if p:
            return p
    src = (j.get("salary_box") or "") + " " + (j.get("desc") or "")
    cands = []
    for m in _RANGE.finditer(src):
        if not (m.group("c1") or m.group("c2") or m.group("d1") or m.group("d2") or m.group("k2")):
            continue  # "100 and 200 employees" is not pay
        n1, n2 = float(m.group("n1").replace(",", "")), float(m.group("n2").replace(",", ""))
        if m.group("k1") or m.group("k2"):  # "$90-110k" and "$90k-110" both mean thousands
            n1, n2 = [n * 1000 if n < 1000 else n for n in (n1, n2)]
        sym = m.group("d2") or m.group("d1") or m.group("c2") or m.group("c1")
        cur = _CUR_CODE.get(sym) if sym else None
        period = _find_period(src[m.end():m.end() + 35], src[max(0, m.start() - 30):m.start()])
        p = _make_pay(n1, n2, cur, period, m.group(0))
        if not p:
            continue
        ctx = src[max(0, m.start() - 40):m.end() + 60]
        p["_score"] = (0 if PAY_AVOID.search(src[m.start():m.end() + 30]) else 1,
                       1 if PAY_PREFER.search(ctx) else 0, 1 if p["comparable"] else 0)
        cands.append(p)
    if not cands:
        return None
    best = max(cands, key=lambda c: c["_score"])  # max keeps the first of equal scores
    best.pop("_score")
    return best


def pay_label(p):
    a = f"${p['annual_low']:,.0f} to ${p['annual_high']:,.0f} a year"
    if not p["comparable"]:
        return f"{p['raw']} ({p['currency']}, not compared with your floor)"
    return a if p["period"] == "year" else f"{a} (listed as {p['raw']})"


# ---------- contracts ----------

CONTRACT_TYPE = re.compile(r"contract|temporary|\btemp\b|fixed[- ]term|freelance|c2c", re.I)
CONTRACT_TITLE = re.compile(r"\b(?:contract|contractor|temporary|temp|c2c|fixed[- ]term)\b|contract[- ]to[- ](?:hire|perm)", re.I)
CONTRACT_DESC = re.compile(
    r"contract[- ](?:position|role|opportunity|assignment|to[- ]hire|to[- ]perm)|temporary (?:position|role|assignment)"
    r"|fixed[- ]term (?:contract|position|role)|\b\d+[- ]month (?:contract|assignment|engagement)"
    r"|(?:w2|c2c|1099) contract|contract (?:duration|length|term)|(?:is|be) a (?:contract|temporary)", re.I)
CONTRACT_TO_PERM = re.compile(
    r"contract[- ]to[- ](?:hire|perm\w*)|temp(?:orary)?[- ]to[- ](?:hire|perm\w*)|(?:possibility|option|opportunity|potential)"
    r" (?:of|for) (?:conversion|permanent|full[- ]time)|convert(?:ed)? to (?:a )?(?:permanent|full[- ]time)", re.I)
_DUR = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\+|plus)?\s*(?:(?:-|\u2013|to)\s*(\d+(?:\.\d+)?)\s*)?[- ]?(month|mo|year|yr)s?\b", re.I)
_CTX = re.compile(r"contract|term\b|duration|assignment|engagement|temporary|\btemp\b|length|initial|project", re.I)
_EXPERIENCE = re.compile(r"^\W*(?:of\s+)?(?:\w+\s+){0,2}(?:experience|exp\b)|^\W*in\b", re.I)
_LONG = re.compile(r"long[- ]term (?:contract|assignment|engagement|role)|ongoing contract|indefinite", re.I)


def is_contract(j):
    """True when the posting is a contract. Uses the employment type; if that is missing, the title and text."""
    typ = j.get("type", "") or ""
    if CONTRACT_TYPE.search(typ):
        return True
    if re.search(r"permanent|regular", typ, re.I):
        return False
    # "Full time" / "Part time" only describe hours, so contract wording in the title or text still counts.
    return bool(CONTRACT_TITLE.search(j.get("title", "")) or CONTRACT_DESC.search(j.get("desc", "")))


def contract_months(s):
    """Contract length in months from wording like '6 month contract' or 'Term: 1 year', else None.
    A number only counts near contract/term wording, never when it describes experience ('10 years experience')."""
    s = s or ""
    for m in _DUR.finditer(s):
        after = s[m.end():m.end() + 30]
        if _EXPERIENCE.search(after):
            continue
        if not _CTX.search(s[max(0, m.start() - 70):m.end() + 30]):
            continue
        n = float(m.group(1))   # a range like '6 to 12 months' only guarantees the low end
        return n * 12 if m.group(3).lower() in ("year", "yr") else n
    return 999.0 if _LONG.search(s) else None


# ---------- location ----------

REMOTE_RE = re.compile(r"remote|work from home|\bwfh\b|anywhere|telecommut", re.I)
WORLDWIDE_RE = re.compile(r"worldwide|global(?:ly)?|anywhere in the world", re.I)
US_STATES = ("alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|hawaii|idaho|"
             "illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|"
             "mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|"
             "north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|"
             "south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming|"
             "district of columbia")
# State abbreviations only count after a comma or bar ("Chicago, IL"), so "in" and "or" in plain text don't match.
US_ABBR = (r"(?:(?<=,)|(?<=, )|(?<=\| )|(?<=\|))(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|"
           r"MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)")
# (case-insensitive aliases, case-sensitive aliases). A short list; extend it if you search elsewhere.
COUNTRIES = {
    "united states": (r"united states|america(?!s)|u\.s\.a?\b|" + US_STATES, r"US|USA|" + US_ABBR),
    "canada": (r"canada|ontario|quebec|british columbia|alberta|manitoba|saskatchewan|nova scotia|new brunswick", ""),
    "united kingdom": (r"united kingdom|england|scotland|wales|great britain", r"UK|U\.K\."),
    "ireland": (r"(?<!northern )ireland", ""), "india": (r"india", ""), "germany": (r"germany|deutschland", ""),
    "france": (r"france", ""), "australia": (r"australia", ""), "netherlands": (r"netherlands|holland", ""),
    "spain": (r"spain|espa\u00f1a", ""), "mexico": (r"(?<!new )mexico|m\u00e9xico", ""), "brazil": (r"brazil|brasil", ""),
    "poland": (r"poland|polska", ""), "singapore": (r"singapore", ""), "philippines": (r"philippines", ""),
    "japan": (r"japan", ""), "israel": (r"israel", ""), "new zealand": (r"new zealand", ""),
    "portugal": (r"portugal", ""), "italy": (r"italy|italia", ""), "sweden": (r"sweden", ""),
    "norway": (r"norway", ""), "denmark": (r"denmark", ""), "finland": (r"finland", ""),
    "switzerland": (r"switzerland", ""), "austria": (r"austria", ""), "belgium": (r"belgium", ""),
    "czech republic": (r"czech republic|czechia", ""), "romania": (r"romania", ""), "hungary": (r"hungary", ""),
    "greece": (r"greece", ""), "turkey": (r"turkey|t\u00fcrkiye|turkiye", ""), "ukraine": (r"ukraine", ""),
    "lithuania": (r"lithuania", ""), "estonia": (r"estonia", ""), "latvia": (r"latvia", ""),
    "bulgaria": (r"bulgaria", ""), "serbia": (r"serbia", ""), "croatia": (r"croatia", ""),
    "luxembourg": (r"luxembourg", ""), "south africa": (r"south africa", ""), "nigeria": (r"nigeria", ""),
    "kenya": (r"kenya", ""), "egypt": (r"egypt", ""), "morocco": (r"morocco", ""),
    "united arab emirates": (r"united arab emirates|dubai|abu dhabi", r"UAE"),
    "saudi arabia": (r"saudi arabia", ""), "china": (r"china", ""), "hong kong": (r"hong kong", ""),
    "taiwan": (r"taiwan", ""), "south korea": (r"south korea|korea, republic", ""), "vietnam": (r"vietnam", ""),
    "thailand": (r"thailand", ""), "malaysia": (r"malaysia", ""), "indonesia": (r"indonesia", ""),
    "pakistan": (r"pakistan", ""), "bangladesh": (r"bangladesh", ""), "sri lanka": (r"sri lanka", ""),
    "argentina": (r"argentina", ""), "chile": (r"chile", ""), "colombia": (r"colombia", ""), "peru": (r"peru", ""),
    "costa rica": (r"costa rica", ""), "uruguay": (r"uruguay", ""),
}
_CTRY_RE = {k: (re.compile(r"(?<![\w])(?:" + ci + r")(?![\w])", re.I),
                re.compile(r"(?<![\w])(?:" + cs + r")(?![\w])") if cs else None)
            for k, (ci, cs) in COUNTRIES.items()}


def countries_in(s):
    found = {k for k, (ci, cs) in _CTRY_RE.items() if ci.search(s) or (cs and cs.search(s))}
    if re.search(r"north america|\bamericas\b", s, re.I):
        found |= {"united states", "canada"}
    return found


def location_text(j):
    return " | ".join([j.get("location", "")] + list(j.get("extra_loc") or []))


def needs_detail(j):
    loc = (j.get("location") or "").strip()
    return not loc or bool(re.search(r"\d+\s+locations?", loc, re.I))


def geo(j):
    """One eligibility test for every source. -> (ok, flag or None)."""
    locs = location_text(j)
    if PLACES and PLACES.search(locs):
        return True, None
    remote = CFG.get("allow_remote", True) and (
        j.get("remote_search") or REMOTE_RE.search(locs) or REMOTE_RE.search(j.get("title", "")))
    if not remote:
        if not locs.strip(" |"):
            return True, "location unknown, check the posting"
        return False, None
    want = (CFG.get("remote_country") or "").strip()
    if not want:
        return True, None
    blob = locs + " | " + (j.get("country_hint") or "")
    found = countries_in(blob)
    key = want.lower()
    if key in ("usa", "us", "u.s.", "united states of america"):
        key = "united states"
    if key in COUNTRIES:
        if found:
            return (key in found), None
    elif re.search(re.escape(want), blob, re.I):
        return True, None
    elif found:
        return False, None
    if WORLDWIDE_RE.search(blob):
        return True, None
    return True, "remote country unknown, check the posting"


# ---------- filtering ----------

def is_sent(j, seen, today):
    if j["id"] in seen["ids"]:
        return True
    d = seen["keys"].get(dedupe_key(j))
    if not d:
        return False
    return d >= (today - dt.timedelta(days=KEY_DAYS)).isoformat()


def not_included(j):
    """include_companies limits LinkedIn results to employers whose name has one of the words (a lane tied to a
    kind of employer: schools, hospitals, government). Watchlist employers were picked by the user and pass."""
    return bool(INCLUDE_CO) and j["source"] == "linkedin" and not INCLUDE_CO.search(j["company"])


def early_reject(j, seen, queued, today):
    """Rejects that need neither dates, location nor detail. Run before cross-source merging."""
    if EXCLUDE_CO and EXCLUDE_CO.search(j["company"]):
        return "excluded employer"
    if not_included(j):
        return "employer not on include list"
    if is_sent(j, seen, today):
        return "already sent"
    if j["id"] in queued["ids"] or dedupe_key(j) in queued["keys"]:
        return "already queued"
    keep = TITLE_KEEP and TITLE_KEEP.search(j["title"])
    if SENIOR and SENIOR.search(j["title"]) and not keep:
        return "title too senior"
    if OFFLANE and OFFLANE.search(j["title"]) and not keep:
        return "title off lane"
    return None


def requeue_reject(j):
    """Re-check a job waiting in the outbox against today's config. -> reason or None."""
    if EXCLUDE_CO and EXCLUDE_CO.search(j["company"]):
        return "excluded employer"
    if not_included(j):
        return "employer not on include list"
    keep = TITLE_KEEP and TITLE_KEEP.search(j["title"])
    if SENIOR and SENIOR.search(j["title"]) and not keep:
        return "title too senior"
    if OFFLANE and OFFLANE.search(j["title"]) and not keep:
        return "title off lane"
    if not geo(j)[0]:
        return "location"
    floor = float(CFG.get("pay_floor", 0) or 0)
    high = j.get("pay_annual_high")
    if high and j.get("pay_comparable", True):
        hf = CFG.get("contracts", {}).get("hourly_floor")
        if j.get("pay_hourly_basis") and hf:
            if high / PER_YEAR["hour"] < float(hf):
                return "under hourly floor"
        elif floor and high < floor:
            return "under pay floor"
    return None


def late_reject(j):
    """Age and place, after merging and date resolution."""
    if j["age_hours"] > MAX_AGE_H:
        return "too old"
    if not needs_detail(j) and not geo(j)[0]:
        return "location"
    return None


SOURCE_RANK = {"greenhouse": 0, "lever": 0, "ashby": 0, "workday": 1, "linkedin": 2}


def merge_duplicates(cands):
    """Group by company|title. Keep the best record per posting (an ATS copy with a description beats a
    LinkedIn card) and fill its gaps from the other source's copy. Same-source siblings (one title in two
    cities) are kept. -> (kept list, list of dropped duplicates)."""
    groups = {}
    for j in cands:
        groups.setdefault(dedupe_key(j), []).append(j)
    kept, dropped = [], []
    for grp in groups.values():
        grp.sort(key=lambda j: (SOURCE_RANK.get(j["source"], 3), not j.get("desc")))
        first = grp[0]
        for j in grp:
            if j["source"] == first["source"]:
                kept.append(j)
                continue
            dropped.append(j)
            for f in ("salary_box", "type", "salary_struct", "seniority"):
                if not first.get(f) and j.get(f):
                    first[f] = j[f]
            if not parse_when(first.get("published_at"))[0] and parse_when(j.get("published_at"))[0]:
                first["published_at"] = j["published_at"]
    return kept, dropped


def judge(j):
    """Final judgement after the detail page. Returns a reject reason or None. Sets flags, stack_hits, pay.
    A job whose posting could not be read has j['uncertain'] set and is returned (None) for the digest's
    'could not check' list instead of being rejected."""
    flags = j.setdefault("flags", [])
    if j.get("closed"):
        return "closed"
    ok, flag = geo(j)
    if not ok:
        return "location"
    if flag:
        flags.append(flag)
    if j.get("seniority") in ("Director", "Executive"):
        return "level too senior"
    d = j.get("desc", "")
    if j.get("uncertain"):
        return None
    if not d.strip() and STACK:
        j["uncertain"] = "the posting text was empty"
        return None
    hits = [k for k in STACK if term_re(k).search(d)]
    j["stack_hits"] = hits
    if LANE and not LANE.search(j["title"]) and len(hits) < int(CFG.get("min_stack_hits_offtitle", 5)):
        return "off lane"
    if STACK and (len(hits) < int(CFG.get("min_stack_hits", 4)) or (CORE and not any(term_re(k).search(d) for k in CORE))):
        return "stack too thin"
    typ = j.get("type", "") or ""
    if re.search(r"intern|seasonal", typ, re.I):
        return "internship or seasonal"
    c = CFG.get("contracts", {})
    contract = is_contract(j)
    if contract:
        if not c.get("allowed", True):
            return "contract"
        c2p = bool(CONTRACT_TO_PERM.search(f"{j['title']} {typ} {d}"))
        if c.get("contract_to_perm_only") and not c2p:
            return "contract (not to perm)"
        if not CONTRACT_TYPE.search(typ):
            flags.append("contract (the employment type did not say so, read from the text)")
        if c2p:
            flags.append("contract to perm")
        elif c.get("min_months"):
            months = contract_months(f"{typ}. {d}")
            if months is None:
                flags.append("contract length unknown")
            elif months < float(c["min_months"]):
                return "short contract"
    p = pay(j)
    if p:
        j.update(pay=pay_label(p), pay_annual_high=p["annual_high"], pay_comparable=p["comparable"],
                 pay_hourly_basis=bool(contract and c.get("hourly_floor")))
        if not p["comparable"]:
            flags.append(f"Pay is in {p['currency']}: not compared with your floor.")
        else:
            floor = float(CFG.get("pay_floor", 0) or 0)
            hfloor = c.get("hourly_floor") if contract else None
            if hfloor:
                if p["annual_high"] / PER_YEAR["hour"] < float(hfloor):
                    return "under hourly floor"
            elif floor and p["annual_high"] < floor:
                return "under pay floor"
            elif floor and p["annual_low"] < floor <= p["annual_high"]:
                flags.append("Pay range crosses your floor: the bottom is under it, the top is not.")
            if CFG.get("pay_ceiling") and p["annual_low"] > float(CFG["pay_ceiling"]):
                return "pay says too senior"
    elif CFG.get("require_pay"):
        return "no pay posted"
    return None


# ---------- output ----------

def digest(today, batch_id, picks, uncertain, counts, total, overflow=0):
    lines = []
    if HEALTH:
        lines += ["SCAN PROBLEMS (fix these, the results below may be incomplete):"] + \
                 [f"- {h}" for h in HEALTH] + [""]
    lines += [f"Job scan {today}: {len(picks)} picks.", ""]
    if picks:
        lines += ["Each pick is a preliminary match from keyword and stack filters. Read the full posting "
                  "before you act.", ""]
    elif total == 0 and HEALTH:
        lines += ["NO RESULTS BECAUSE THE SOURCES FAILED (see the problems above). This does not mean "
                  "nothing was posted.", ""]
    else:
        lines += [f"No new matches today: {total} postings were checked and none cleared the filters.", ""]
    if overflow:
        lines += [f"{overflow} more picks are queued and will come in the next email.", ""]
    for i, j in enumerate(picks, 1):
        flags = list(j.get("flags", []))
        if FLAG_CO and FLAG_CO.search(j["company"]):
            flags.append("Check first: on your flag list.")
        if AGENCY and AGENCY.search(j["company"]):
            flags.append("Agency: RATE-FIRST. No resume until the client and rate are settled.")
        if not j.get("pay"):
            flags.append("No pay posted: get the number first.")
        if j.get("date_unknown"):
            flags.append("Posting date unknown: first seen today, so it may be older.")
        carried = f"  [carried over from {j['queued_at'][:10]}]" if j.get("queued_at", today)[:10] < today else ""
        lines += [f"{i}. {j['title']} - {j['company']}{carried}",
                  f"Where: {j['location']}",
                  f"Posted: {j['posted']}  (source: {j['source']})",
                  f"Pay: {j.get('pay', 'not posted')}",
                  f"Type: {j.get('type') or 'unknown'}; level: {j.get('seniority') or 'unknown'}",
                  f"Stack: {', '.join(j.get('stack_hits', [])[:8])}",
                  f"Link: {j['link']}"] + [f"Flag: {f}" for f in flags] + [""]
    if uncertain:
        lines += ["COULD NOT CHECK (the posting page would not load, was empty, or was skipped by the "
                  "detail-fetch cap; not rejected, open the link and judge for yourself):"]
        for j in uncertain[:15]:
            lines.append(f"- {j['title']} - {j['company']} ({j['location'] or 'location unknown'}): "
                         f"{j['link']}  [{j['uncertain']}]")
        if len(uncertain) > 15:
            lines.append(f"- ...and {len(uncertain) - 15} more (see the .json file)")
        lines.append("")
    rej = ", ".join(f"{v} {k}" for k, v in sorted(counts.items(), key=lambda x: -x[1]))
    lines.append(f"{total} listings checked; rejected: {rej or 'none'}.")
    lines.append(f"Batch: {batch_id}")
    return "\n".join(lines)


def load_seen():
    seen = load(SEEN, {})
    today = dt.date.today().isoformat()
    ids, keys = seen.get("ids", {}), seen.get("keys", {})
    if isinstance(ids, list):   # old format: plain lists with no dates
        ids = dict.fromkeys(ids, today)
    if isinstance(keys, list):
        keys = dict.fromkeys(keys, today)
    return {"ids": ids, "keys": keys}


def load_outbox(now, today):
    ob = load(OUTBOX, {})
    cutoff = (now - dt.timedelta(days=int(CFG.get("outbox_max_days", 7)))).isoformat()
    jobs = [j for j in ob.get("jobs", []) if j.get("queued_at", today) >= cutoff]
    return {"jobs": jobs, "batches": ob.get("batches", {})}


def save_status(**changes):
    st = load(STATUS, {})
    st.update(changes)
    write_json(STATUS, st)


def mark_sent(batch_id):
    """Acknowledge exactly one batch: move its jobs from the outbox into seen."""
    if not batch_id:
        print("Usage: jobscan.py --mark-sent <batch-id>")
        return 2
    with run_lock():
        now = dt.datetime.now(UTC)
        today = dt.date.today().isoformat()
        ob = load(OUTBOX, {})
        ob.setdefault("jobs", [])
        ob.setdefault("batches", {})
        if batch_id not in ob["batches"]:
            if (load(STATUS, {}).get("last_delivery") or {}).get("batch") == batch_id:
                print(f"Batch {batch_id} was already acknowledged.")
                return 0
            print(f"Unknown batch {batch_id}. Nothing was marked as sent.")
            return 2
        ids = set(ob["batches"].pop(batch_id))
        seen = load_seen()
        sent = [j for j in ob["jobs"] if j["id"] in ids]
        for j in sent:
            seen["ids"][j["id"]] = today
            seen["keys"][dedupe_key(j)] = today
        cutoff = (dt.date.today() - dt.timedelta(days=KEY_DAYS)).isoformat()
        seen["keys"] = {k: v for k, v in seen["keys"].items() if v >= cutoff}
        write_json(SEEN, seen)        # seen first: a crash here only leaves a harmless duplicate in the outbox
        ob["jobs"] = [j for j in ob["jobs"] if j["id"] not in ids]
        write_json(OUTBOX, ob)
        save_status(last_delivery={"batch": batch_id, "at": now.astimezone().strftime("%Y-%m-%d %H:%M"),
                                   "count": len(sent)})
    print(f"Marked {len(sent)} picks as sent (batch {batch_id}); {len(ob['jobs'])} still queued.")
    return 0


def mark_latest():
    """Digest-only mode: acknowledge the newest queued batch (the one the user has just read)."""
    ob = load(OUTBOX, {})
    batches = ob.get("batches") or {}
    if not batches:
        print("No unacknowledged batch. Nothing to do.")
        return 0
    return mark_sent(max(batches))


# ---------- status ----------

def next_run():
    import shutil
    import subprocess
    try:
        if sys.platform == "win32":
            ps = shutil.which("powershell") or shutil.which("pwsh")
            if ps:
                r = subprocess.run([ps, "-NoProfile", "-Command",
                                    "(Get-ScheduledTaskInfo -TaskName 'Job Search Assistant - daily scan').NextRunTime"],
                                   capture_output=True, text=True, timeout=20)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout.strip()
            return "no 'Job Search Assistant - daily scan' task found (run scanner/install-task.ps1)"
        plist = Path.home() / "Library/LaunchAgents/com.jobsearchassistant.scan.plist"
        if plist.exists():
            import plistlib
            sched = plistlib.loads(plist.read_bytes()).get("StartCalendarInterval", {})
            return f"daily at {sched.get('Hour', 0):02d}:{sched.get('Minute', 0):02d} (launchd)"
        if shutil.which("crontab"):
            r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
            line = next((ln for ln in r.stdout.splitlines() if "run.sh" in ln and not ln.startswith("#")), "")
            if line:
                return f"cron: {line.strip()}"
    except Exception:
        pass
    return "not detected (no scheduled task, launch agent or cron line found)"


def status():
    st = load(STATUS, {})
    ob = load(OUTBOX, {"jobs": []})
    d = st.get("last_delivery")
    health = st.get("health") or []
    print(f"Last scan:       {st.get('last_scan', 'never')}"
          + (f" ({st.get('picks', 0)} picks, {len(health)} problems)" if st.get("last_scan") else ""))
    print("Last delivery:   " + (f"batch {d['batch']} at {d['at']} ({d['count']} picks)" if d else "none acknowledged yet"))
    print(f"Queued unsent:   {len(ob.get('jobs', []))}")
    if ob.get("batches"):
        print("Digest-only mode: picks stay queued until acknowledged. After the user has read the newest digest, "
              "run: <python> scanner/jobscan.py --mark-read-latest")
    print(f"Next run:        {next_run()}")
    print("Recent problems: " + ("none" if not health else ""))
    for h in health[-5:]:
        print(f"  - {h}")
    return 0


# ---------- main ----------

ROUTINE_REJECTS = {"already sent", "already queued", "duplicate across sources", "too old", "dropped from queue"}


def one_reason_dominates(counts, total, picks):
    """A zero-pick day where one filter threw out at least 80% of the listings means the searches are finding
    the wrong jobs. Say so, or the digest looks healthy every day. -> warning text or None."""
    if picks or total < 20:
        return None
    why, n = max(((k, v) for k, v in counts.items() if k not in ROUTINE_REJECTS),
                 key=lambda x: x[1], default=(None, 0))
    if not why or n < 0.8 * total:
        return None
    return (f"{n} of {total} listings were rejected for one reason ('{why}'). The searches are probably finding "
            "the wrong jobs: change keywords or linkedin.searches (docs/06-daily-scan.md), not the filters.")


def scan(dry=False, now=None):
    """Run one scan. Returns (digest text, batch id, digest path)."""
    now = now or dt.datetime.now(UTC)
    today = dt.date.today().isoformat()
    HEALTH.clear()
    DETAIL_FAILS.clear()
    seen = load_seen()
    ob = load_outbox(now, today)
    carried, dropped_queue = [], 0
    for j in ob["jobs"]:
        if j["id"] not in seen["ids"]:
            if requeue_reject(j):
                dropped_queue += 1
            else:
                carried.append(j)
    queued = {"ids": {j["id"] for j in carried}, "keys": {dedupe_key(j) for j in carried}}
    firstseen = load(FIRSTSEEN, {})

    jobs = {**linkedin(), **watchlist()}
    counts, rows, picks, uncertain = {}, [], [], []
    if dropped_queue:
        counts["dropped from queue"] = dropped_queue

    def record(j, why):
        if why:
            counts[why] = counts.get(why, 0) + 1
        rows.append({**{k: v for k, v in j.items() if k != "desc"}, "reject": why})

    survivors = []
    for j in jobs.values():
        why = early_reject(j, seen, queued, dt.date.today())
        if why:
            record(j, why)
        else:
            survivors.append(j)
    survivors, dupes = merge_duplicates(survivors)
    for j in dupes:
        record(j, "duplicate across sources")
    cap = int(CFG.get("max_detail_fetches", 60))
    fetched = 0
    need = sum(1 for j in survivors if j["source"] in ("linkedin", "workday"))
    for j in survivors:
        resolve_dates(j, now, firstseen)
        why = late_reject(j)
        if not why:
            if j["source"] in ("linkedin", "workday"):
                if fetched >= cap:
                    j["uncertain"] = "skipped: detail-fetch cap"
                else:
                    fetched += 1
                    progress(f"checked {fetched} of up to {min(need, cap)} postings...")
                    fetch = linkedin_detail if j["source"] == "linkedin" else workday_detail
                    if fetch(j) == "failed":
                        j["uncertain"] = "the full posting could not be loaded"
            why = judge(j)
        record(j, why)
        if not why:
            (uncertain if j.get("uncertain") else picks).append(j)
    picks.sort(key=lambda j: (-len(j.get("stack_hits", [])), j["age_hours"]))
    for j in picks:
        j["queued_at"] = now.isoformat()

    skipped = sum(1 for j in uncertain if j.get("uncertain") == "skipped: detail-fetch cap")
    if skipped:
        HEALTH.append(f"{skipped} postings were not opened because of the detail-fetch cap "
                      f"({cap}). They are listed under 'could not check'. Raise max_detail_fetches to read more.")
    for (src, code), n in DETAIL_FAILS.items():
        HEALTH.append(f"{src}: could not read {n} full postings (HTTP {code}). Those jobs are listed under "
                      "'could not check' instead of being rejected.")
    lopsided = one_reason_dominates(counts, len(jobs), len(picks) + len(carried))
    if lopsided:
        HEALTH.append(lopsided)

    queue = carried + picks                 # earlier unsent jobs go first
    batch = queue[:int(CFG.get("max_picks", 10))]
    overflow = len(queue) - len(batch)
    batch_id = now.strftime("%Y%m%d-%H%M%S")
    body = digest(today, batch_id, batch, uncertain, counts, len(jobs), overflow)
    path = OUT / f"{today}.txt"
    write_text(path, body)
    write_json(OUT / f"{today}.json", rows)
    if not dry:
        batches = ob["batches"]
        batches[batch_id] = [j["id"] for j in batch]
        for k in sorted(batches)[:-10]:
            batches.pop(k)
        slim = [{k: v for k, v in j.items() if k != "desc"} for j in queue]
        write_json(OUTBOX, {"jobs": slim, "batches": batches})
        write_json(FIRSTSEEN, {k: v for k, v in firstseen.items()
                               if v >= (now - dt.timedelta(days=90)).isoformat()})
        save_status(last_scan=now.astimezone().strftime("%Y-%m-%d %H:%M"), picks=len(batch), total=len(jobs),
                    health=list(HEALTH), last_batch=batch_id)
    return body, batch_id, path


def apply_quick(cfg):
    """--quick: a short setup test. 1 keyword, 1 page per search, at most 15 full postings opened."""
    cfg = dict(cfg)
    cfg["keywords"] = list(cfg.get("keywords", []))[:1]
    cfg["linkedin"] = {**cfg.get("linkedin", {}), "pages": 1}
    cfg["max_detail_fetches"] = min(15, int(cfg.get("max_detail_fetches", 60)))
    return cfg


def main():
    if "-h" in sys.argv or "--help" in sys.argv:    # before any config is read
        print(__doc__)
        return 0
    if "--status" in sys.argv:
        if arg("--state-dir"):
            set_state(arg("--state-dir"))
        return status()
    cfg = load_config(arg("--config", str(paths.data_dir() / "scanner-config.json")))
    if "--quick" in sys.argv:
        cfg = apply_quick(cfg)
    init(cfg, arg("--state-dir"))
    if "--mark-read-latest" in sys.argv:
        return mark_latest()
    if "--mark-sent" in sys.argv:
        return mark_sent(arg("--mark-sent"))
    dry = "--dry" in sys.argv
    with run_lock():
        body, batch_id, path = scan(dry)
    print(body)
    if not dry:
        print(f"BATCH {batch_id} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
