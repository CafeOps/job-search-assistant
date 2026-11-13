"""Offline tests for scanner/jobscan.py. Run: py -3 -m unittest discover -s scanner/tests
No network: sources are stubbed."""
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import jobscan  # noqa: E402

UTC = dt.timezone.utc
BASE = {
    "keywords": ["data analyst"], "linkedin": {"enabled": False}, "currency": "USD",
    "stack_terms": ["sql", "python", "tableau", "c++", "excel"], "core_terms": ["sql"],
    "min_stack_hits": 2, "min_stack_hits_offtitle": 4,
    "location_words": ["chicago"], "allow_remote": True, "remote_country": "United States",
    "pay_floor": 100000, "pay_ceiling": 300000, "max_age_hours": 48, "max_picks": 2,
    "contracts": {"allowed": True, "min_months": 12, "hourly_floor": 0, "contract_to_perm_only": False},
    "lane_title_words": ["analyst"],
}


def cfg(**over):
    c = dict(BASE)
    c.update(over)
    return c


def mk(title="Data Analyst", company="Acme", location="Chicago, IL", desc="SQL and Python and Tableau",
       src="greenhouse", jid="1", **extra):
    return jobscan.job(src, "acme", jid, title, company, location, "", f"https://x/{jid}", desc, **extra)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        jobscan.init(cfg(), Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()


class PayTests(Base):
    def p(self, s, **kw):
        return jobscan.pay({"desc": s, **kw})

    def test_k_on_second_number_only(self):
        r = self.p("Pay $90-110k per year")
        self.assertEqual((r["annual_low"], r["annual_high"]), (90000, 110000))

    def test_monthly_is_annualised(self):
        r = self.p("$20,000-$25,000 per month")
        self.assertEqual(r["period"], "month")
        self.assertEqual((r["annual_low"], r["annual_high"]), (240000, 300000))

    def test_hourly(self):
        r = self.p("$50 - $60 per hour")
        self.assertEqual(r["annual_high"], 60 * 2080)

    def test_other_currency_not_compared(self):
        r = self.p("£50,000 - £60,000 per year")
        self.assertEqual(r["currency"], "GBP")
        self.assertFalse(r["comparable"])
        j = mk(desc="SQL Python Tableau. Salary £50,000 - £60,000 per year")
        self.assertIsNone(jobscan.judge(j))   # not rejected for being under a USD floor
        self.assertIn("pay", j)

    def test_top_meets_floor_is_kept_and_flagged(self):
        j = mk(desc="SQL Python Tableau. $90,000 - $110,000 per year")
        self.assertIsNone(jobscan.judge(j))
        self.assertTrue(any("crosses your floor" in f for f in j["flags"]))

    def test_top_under_floor_rejected(self):
        j = mk(desc="SQL Python Tableau. $70,000 - $95,000 per year")
        self.assertEqual(jobscan.judge(j), "under pay floor")

    def test_not_a_range_of_money(self):
        self.assertIsNone(self.p("We have 100 and 200 employees"))

    def test_lever_struct(self):
        r = jobscan.pay({"desc": "", "salary_struct": {"min": 40, "max": 60, "currency": "USD",
                                                        "interval": "per-hour-wage"}})
        self.assertEqual(r["period"], "hour")


class ContractTests(Base):
    def test_months(self):
        self.assertEqual(jobscan.contract_months("This is a 6 month contract."), 6)
        self.assertEqual(jobscan.contract_months("Contract duration: 1 year"), 12)
        self.assertEqual(jobscan.contract_months("Term: 6-12 months with extension"), 6)
        self.assertEqual(jobscan.contract_months("A 6 to 12 month contract"), 6)

    def test_experience_years_ignored(self):
        self.assertIsNone(jobscan.contract_months("Contract role. 10 years experience with SQL required."))

    def test_short_contract_rejected(self):
        j = mk(type="Contract", desc="SQL Python Tableau. This is a 6 month contract.")
        self.assertEqual(jobscan.judge(j), "short contract")

    def test_experience_does_not_pass_short_contract(self):
        j = mk(type="Contract", desc="SQL Python Tableau. 10 years experience. 3 month contract.")
        self.assertEqual(jobscan.judge(j), "short contract")

    def test_unknown_length_kept_and_flagged(self):
        j = mk(type="Contract", desc="SQL Python Tableau. Contract role.")
        self.assertIsNone(jobscan.judge(j))
        self.assertIn("contract length unknown", j["flags"])

    def test_missing_type_detected_from_text(self):
        j = mk(title="Data Analyst (Contract)", desc="SQL Python Tableau. 3 month contract.")
        self.assertEqual(jobscan.judge(j), "short contract")

    def test_contract_to_perm_only(self):
        jobscan.init(cfg(contracts={"allowed": True, "min_months": 12, "contract_to_perm_only": True}),
                     Path(self.tmp.name))
        j = mk(type="Contract", desc="SQL Python Tableau. 12 month contract.")
        self.assertEqual(jobscan.judge(j), "contract (not to perm)")

    def test_hourly_floor(self):
        jobscan.init(cfg(contracts={"allowed": True, "min_months": 6, "hourly_floor": 50}), Path(self.tmp.name))
        j = mk(type="Contract", desc="SQL Python Tableau. 12 month contract. $35 - $45 per hour")
        self.assertEqual(jobscan.judge(j), "under hourly floor")

    def test_full_time_type_does_not_hide_contract_wording(self):
        j = mk(type="Full time", desc="SQL Python Tableau. This is a 3 month contract position.")
        self.assertTrue(jobscan.is_contract(j))
        self.assertEqual(jobscan.judge(j), "short contract")

    def test_range_uses_low_end_against_minimum(self):
        j = mk(type="Contract", desc="SQL Python Tableau. 6 to 12 month contract.")
        self.assertEqual(jobscan.judge(j), "short contract")

    def test_workday_estimated_date_is_flagged(self):
        import json as _json
        body = _json.dumps({"total": 1, "jobPostings": [{"title": "Data Analyst", "externalPath": "/job/1",
                                                          "locationsText": "Chicago", "postedOn": "Posted 3 Days Ago"}]})
        orig_get, orig_sleep = jobscan.get, jobscan.time.sleep
        jobscan.get, jobscan.time.sleep = (lambda *a, **k: (200, body)), (lambda s: None)
        try:
            out = jobscan.workday({"host": "h.example.com", "keywords": ["x"]}, "Co", "ten/site")
        finally:
            jobscan.get, jobscan.time.sleep = orig_get, orig_sleep
        flags = list(out.values())[0]["flags"]
        self.assertTrue(any("estimated from 'Posted 3 Days Ago'" in f for f in flags))


class GeoTests(Base):
    def test_remote_canada_fails_us_config(self):
        self.assertFalse(jobscan.geo(mk(location="Remote - Canada"))[0])

    def test_remote_us_ok(self):
        self.assertEqual(jobscan.geo(mk(location="Remote - US")), (True, None))

    def test_plain_remote_kept_with_flag(self):
        ok, flag = jobscan.geo(mk(location="Remote"))
        self.assertTrue(ok)
        self.assertIn("remote country unknown", flag)

    def test_linkedin_remote_does_not_bypass_country(self):
        j = mk(src="linkedin", location="London, United Kingdom", remote_search=True)
        self.assertFalse(jobscan.geo(j)[0])

    def test_city_match(self):
        self.assertTrue(jobscan.geo(mk(location="Chicago, IL"))[0])

    def test_n_locations_needs_detail(self):
        self.assertTrue(jobscan.needs_detail(mk(location="2 Locations")))
        self.assertTrue(jobscan.needs_detail(mk(location="")))
        self.assertIsNone(jobscan.late_reject({**mk(location="3 Locations"), "age_hours": 1}))


class TermTests(Base):
    def test_boundaries(self):
        self.assertFalse(jobscan.term_re("sql").search("We use NoSQL"))
        self.assertFalse(jobscan.term_re("excel").search("an excellent team"))
        self.assertTrue(jobscan.term_re("c++").search("Skills: C++, Python"))
        self.assertTrue(jobscan.term_re(".net").search("uses .NET today"))


class DedupeTests(Base):
    def test_levels_differ(self):
        a, b = mk("Analyst I", jid="1"), mk("Analyst II", jid="2")
        kept, dropped = jobscan.merge_duplicates([a, b])
        self.assertEqual((len(kept), len(dropped)), (2, 0))
        self.assertEqual(jobscan.norm_title("Analyst I"), jobscan.norm_title("Analyst 1"))

    def test_ids_namespaced(self):
        self.assertNotEqual(jobscan.job("workday", "ta/site", "/job/1", "t", "c", "l")["id"],
                            jobscan.job("workday", "tb/site", "/job/1", "t", "c", "l")["id"])

    def test_cross_source_prefers_ats_with_description(self):
        li = mk(src="linkedin", jid="9", desc="")
        li["published_at"] = "2026-11-06"
        gh = mk(src="greenhouse", jid="1")
        kept, dropped = jobscan.merge_duplicates([li, gh])
        self.assertEqual([k["source"] for k in kept], ["greenhouse"])
        self.assertEqual(kept[0]["published_at"], "2026-11-06")  # missing date filled from the copy

    def test_key_expires_after_60_days(self):
        j = mk()
        today = dt.date.today()
        old = {"ids": {}, "keys": {jobscan.dedupe_key(j): (today - dt.timedelta(days=61)).isoformat()}}
        new = {"ids": {}, "keys": {jobscan.dedupe_key(j): (today - dt.timedelta(days=10)).isoformat()}}
        self.assertFalse(jobscan.is_sent(j, old, today))
        self.assertTrue(jobscan.is_sent(j, new, today))


class DateTests(Base):
    def test_no_1970(self):
        self.assertEqual(jobscan.ms_to_iso(0), "")
        self.assertEqual(jobscan.parse_when("1970-01-01"), (None, False))

    def test_unknown_date_uses_first_seen(self):
        now = dt.datetime.now(UTC)
        j = mk(updated="2026-01-01T00:00:00Z")
        jobscan.resolve_dates(j, now, {})
        self.assertTrue(j["date_unknown"])
        self.assertIn("date unknown", j["posted"])
        self.assertLess(j["age_hours"], 1)

    def test_age_in_hours(self):
        now = dt.datetime(2026, 11, 7, 12, tzinfo=UTC)
        j = mk()
        j["published_at"] = "2026-11-05T00:00:00+01:00"
        jobscan.resolve_dates(j, now, {})
        self.assertAlmostEqual(j["age_hours"], 61, delta=0.1)


class OutboxTests(Base):
    """Run scan() with stubbed sources."""

    def setUp(self):
        super().setUp()
        self._orig = (jobscan.linkedin, jobscan.watchlist, jobscan.linkedin_detail)
        self.now = dt.datetime.now(UTC)

    def tearDown(self):
        jobscan.linkedin, jobscan.watchlist, jobscan.linkedin_detail = self._orig
        super().tearDown()

    def run_scan(self, jobs, now):
        jobscan.linkedin = lambda: {}
        jobscan.watchlist = lambda: {j["id"]: j for j in jobs}
        return jobscan.scan(False, now)

    def fresh(self, n):
        j = mk(title=f"Data Analyst Team {n}", jid=str(n))
        j["published_at"] = self.now.isoformat()
        return j

    def test_failed_send_keeps_picks_and_overflow(self):
        jobs = [self.fresh(i) for i in range(1, 5)]          # 4 picks, max_picks 2
        body1, b1, _ = self.run_scan(jobs, self.now)
        self.assertEqual(body1.count("Link: "), 2)
        self.assertIn("2 more picks are queued", body1)
        # the email failed: nothing acknowledged. Next run the sources return nothing new.
        body2, b2, _ = self.run_scan([], self.now + dt.timedelta(seconds=5))
        self.assertEqual(body2.count("Link: "), 2)
        self.assertNotEqual(b1, b2)
        self.assertEqual(jobscan.mark_sent(b2), 0)
        body3, b3, _ = self.run_scan([], self.now + dt.timedelta(seconds=10))
        self.assertEqual(body3.count("Link: "), 2)           # the overflow pair is still waiting
        self.assertEqual(jobscan.mark_sent(b3), 0)
        body4, _, _ = self.run_scan(jobs, self.now + dt.timedelta(seconds=15))
        self.assertEqual(body4.count("Link: "), 0)           # everything sent, nothing repeats

    def test_batch_ack_is_exact(self):
        jobs = [self.fresh(i) for i in range(1, 3)]
        _, b1, _ = self.run_scan(jobs, self.now)
        self.assertEqual(jobscan.mark_sent("20000101-000000"), 2)   # unknown batch changes nothing
        self.assertEqual(len(jobscan.load(jobscan.OUTBOX, {})["jobs"]), 2)
        self.assertEqual(jobscan.mark_sent(b1), 0)
        self.assertEqual(len(jobscan.load(jobscan.OUTBOX, {})["jobs"]), 0)
        self.assertEqual(jobscan.mark_sent(b1), 0)                  # repeating is harmless

    def test_unreadable_posting_is_uncertain_not_rejected(self):
        li = mk(src="linkedin", jid="77", desc="")
        li["published_at"] = self.now.isoformat()
        jobscan.linkedin = lambda: {li["id"]: li}
        jobscan.watchlist = lambda: {}
        jobscan.linkedin_detail = lambda j: (jobscan.note_fail("LinkedIn", 403), "failed")[1]
        body, _, _ = jobscan.scan(True, self.now)
        self.assertIn("COULD NOT CHECK", body)
        self.assertIn("HTTP 403", body)

    def test_detail_fetch_cap_goes_to_could_not_check(self):
        jobscan.init(cfg(max_detail_fetches=1), Path(self.tmp.name))
        a, b = mk(src="linkedin", jid="1"), mk(src="linkedin", jid="2", title="Data Analyst Two")
        for j in (a, b):
            j["published_at"] = self.now.isoformat()
        jobscan.linkedin = lambda: {a["id"]: a, b["id"]: b}
        jobscan.watchlist = lambda: {}
        calls = []

        def detail(j):
            calls.append(j["id"])
            j["desc"] = "SQL and Python and Tableau"
            return "ok"
        jobscan.linkedin_detail = detail
        body, _, _ = jobscan.scan(True, self.now)
        self.assertEqual(len(calls), 1)
        self.assertIn("COULD NOT CHECK", body)
        self.assertIn("skipped: detail-fetch cap", body)
        self.assertEqual(body.count("Link: "), 1)

    def test_queued_jobs_are_rechecked_against_current_config(self):
        jobs = [self.fresh(1), self.fresh(2)]
        _, b1, _ = self.run_scan(jobs, self.now)             # both queued, email "failed"
        jobscan.init(cfg(exclude_companies=["Acme"]), Path(self.tmp.name))
        jobscan.linkedin, jobscan.watchlist = (lambda: {}), (lambda: {})
        body, b2, _ = jobscan.scan(False, self.now + dt.timedelta(seconds=5))
        self.assertEqual(body.count("Link: "), 0)
        self.assertIn("2 dropped from queue", body)
        self.assertEqual(jobscan.load(jobscan.OUTBOX, {})["jobs"], [])

    def test_include_companies_limits_linkedin_only(self):
        jobscan.init(cfg(include_companies=["university", "school board"]), Path(self.tmp.name))
        seen, queued, today = {"ids": set(), "keys": {}}, {"ids": set(), "keys": set()}, dt.date.today()
        off = mk(src="linkedin", jid="1", company="Acme Corp")
        on = mk(src="linkedin", jid="2", company="Lakeside University")
        board = mk(src="linkedin", jid="3", company="Northfield District School Board")
        watch = mk(src="greenhouse", jid="4", company="Acme Corp")
        self.assertEqual(jobscan.early_reject(off, seen, queued, today), "employer not on include list")
        self.assertIsNone(jobscan.early_reject(on, seen, queued, today))
        self.assertIsNone(jobscan.early_reject(board, seen, queued, today))
        self.assertIsNone(jobscan.early_reject(watch, seen, queued, today))   # watchlist employers pass
        self.assertEqual(jobscan.requeue_reject(off), "employer not on include list")

    def test_zero_picks_with_one_dominant_reason_warns(self):
        jobscan.init(cfg(include_companies=["university"]), Path(self.tmp.name))
        jobs = {}
        for i in range(25):
            j = mk(src="linkedin", jid=str(i), title=f"Data Analyst {i}", company=f"Shop {i}")
            jobs[j["id"]] = j
        jobscan.linkedin, jobscan.watchlist = (lambda: jobs), (lambda: {})
        body, _, _ = jobscan.scan(True, self.now)
        self.assertIn("SCAN PROBLEMS", body)
        self.assertIn("25 of 25 listings were rejected for one reason ('employer not on include list')", body)

    def test_no_dominance_warning_when_there_are_picks_or_few_listings(self):
        self.assertIsNone(jobscan.one_reason_dominates({"off lane": 30}, 30, 1))
        self.assertIsNone(jobscan.one_reason_dominates({"off lane": 10}, 10, 0))
        self.assertIsNone(jobscan.one_reason_dominates({"already sent": 30}, 30, 0))
        self.assertIsNone(jobscan.one_reason_dominates({"off lane": 15, "location": 15}, 30, 0))
        self.assertIsNotNone(jobscan.one_reason_dominates({"off lane": 24, "location": 6}, 30, 0))

    def test_queued_job_under_new_pay_floor_dropped(self):
        j = self.fresh(3)
        j["desc"] = "SQL Python Tableau. $105,000 - $110,000 a year"
        self.run_scan([j], self.now)
        jobscan.init(cfg(pay_floor=150000), Path(self.tmp.name))
        jobscan.linkedin, jobscan.watchlist = (lambda: {}), (lambda: {})
        body, _, _ = jobscan.scan(True, self.now + dt.timedelta(seconds=5))
        self.assertIn("1 dropped from queue", body)


if __name__ == "__main__":
    unittest.main()


class CliTests(unittest.TestCase):
    def test_help_exits_zero_without_config(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            env = {**__import__("os").environ, "JOBHUNT_DATA_DIR": d}
            r = subprocess.run([sys.executable, str(Path(jobscan.__file__)), "-h"], capture_output=True, text=True,
                               env=env)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Usage", r.stdout)
        self.assertIn("--quick", r.stdout)

    def test_quick_trims_config(self):
        q = jobscan.apply_quick(cfg(keywords=["a", "b"], linkedin={"pages": 3}, max_detail_fetches=60))
        self.assertEqual((q["keywords"], q["linkedin"]["pages"], q["max_detail_fetches"]), (["a"], 1, 15))

    def test_state_and_us_state_abbreviations(self):
        jobscan.init(cfg(location_words=["nowhere"]), Path(tempfile.mkdtemp()))
        self.assertIn("united states", jobscan.countries_in("Austin, TX"))
        self.assertIn("united states", jobscan.countries_in("Remote - Illinois"))
        self.assertNotIn("united states", jobscan.countries_in("Remote in or around town"))
        self.assertIn("italy", jobscan.countries_in("Milan, Italy"))
        self.assertNotIn("mexico", jobscan.countries_in("Santa Fe, New Mexico"))

    def test_unknown_country_kept_and_flagged(self):
        jobscan.init(cfg(location_words=["nowhere"]), Path(tempfile.mkdtemp()))
        ok, flag = jobscan.geo(mk(location="Remote - Narnia"))
        self.assertTrue(ok)
        self.assertIn("remote country unknown", flag)

    def test_429_slows_host_once(self):
        jobscan.init(cfg(), Path(tempfile.mkdtemp()))
        jobscan.SLOW_HOSTS.clear()
        import urllib.error
        import urllib.request

        def boom(*a, **k):
            raise urllib.error.HTTPError("https://h.example/x", 429, "x", {}, None)
        orig_open, orig_sleep = urllib.request.urlopen, jobscan.time.sleep
        urllib.request.urlopen, jobscan.time.sleep = boom, (lambda s: None)
        try:
            jobscan.get("https://h.example/x")
            jobscan.get("https://h.example/y")
        finally:
            urllib.request.urlopen, jobscan.time.sleep = orig_open, orig_sleep
        self.assertEqual(jobscan.SLOW_HOSTS["h.example"], 2)
        self.assertEqual(sum("429" in h for h in jobscan.HEALTH), 1)


class DigestOnlyTests(unittest.TestCase):
    def test_digest_only_leaves_batch_queued_until_marked_read(self):
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d:
            jobscan.init(cfg(), Path(d))
            orig = (jobscan.linkedin, jobscan.watchlist)
            now = dt.datetime.now(UTC)
            j = mk(title="Data Analyst Q", jid="9")
            j["published_at"] = now.isoformat()
            jobscan.linkedin, jobscan.watchlist = (lambda: {}), (lambda: {j["id"]: j})
            try:
                _, batch, _ = jobscan.scan(False, now)          # digest-only mode: scan, never mark
            finally:
                jobscan.linkedin, jobscan.watchlist = orig
            self.assertEqual(len(jobscan.load(jobscan.OUTBOX, {})["jobs"]), 1)
            self.assertIn(batch, jobscan.load(jobscan.OUTBOX, {})["batches"])
            self.assertIsNone(jobscan.load(jobscan.STATUS, {}).get("last_delivery"))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(jobscan.mark_latest(), 0)
            self.assertEqual(jobscan.load(jobscan.OUTBOX, {})["jobs"], [])
            self.assertEqual(jobscan.load(jobscan.STATUS, {})["last_delivery"]["batch"], batch)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(jobscan.mark_latest(), 0)      # nothing left: harmless

    def test_run_sh_digest_only_does_not_acknowledge(self):
        import json
        import os
        import shutil
        import subprocess
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash not available")
        root = Path(jobscan.__file__).resolve().parent
        with tempfile.TemporaryDirectory() as d:
            data = Path(d)
            (data / "scanner-config.json").write_text(json.dumps(
                {"keywords": [], "linkedin": {"enabled": False}, "watchlist": []}), encoding="utf-8")
            env = {**os.environ, "MAIL": "none", "JOBHUNT_DATA_DIR": str(data)}
            r = subprocess.run([bash, str(root / "run.sh"), "--python", sys.executable, "--data-dir", str(data)],
                               capture_output=True, text=True, env=env, timeout=120)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("DIGEST ", r.stdout)
            ob = json.loads((data / "scan" / "outbox.json").read_text(encoding="utf-8"))
            self.assertEqual(len(ob["batches"]), 1)
            st = json.loads((data / "scan" / "status.json").read_text(encoding="utf-8"))
            self.assertNotIn("last_delivery", st)
