import json
import io
import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from app import wembley_browser as browser


DATE = "2026-10-08"
ORIGIN = "https://www.wembleygolf.com.au"
CALENDAR = f"{ORIGIN}/guests/bookings/ViewPublicCalendar.msp?bookingResourceId=3000000&selectedDate={DATE}&mobile=true"
EXECUTABLE = os.environ.get("GOLFHUB_BROWSER_EXECUTABLE") or shutil.which("chromium")


def source(fee):
    return f"{ORIGIN}/guests/bookings/ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate={DATE}&feeGroupId={fee}&mobile=true"


def payload(products=("102184", "102193")):
    return {"calendar_url": CALENDAR, "date_str": DATE, "booking_resource_id": "3000000",
            "products": {fee: source(fee) for fee in products},
            "executable_path": EXECUTABLE}


class WembleyBrowserBoundsTests(unittest.TestCase):
    def setUp(self):
        browser.reset_browser_collection_state()
        self.enabled = patch.dict(os.environ, {"GOLFHUB_WEMBLEY_BROWSER": "1"})
        self.enabled.start()
        self.addCleanup(self.enabled.stop)
        self.addCleanup(browser.reset_browser_collection_state)

    def collect(self, **changes):
        args = payload()
        args.update(changes)
        return browser.collect_wembley_rows(**args)

    def test_desktop_is_disabled_without_importing_or_starting_browser(self):
        with patch.dict(os.environ, {"GOLFHUB_WEMBLEY_BROWSER": "0"}), patch.object(browser.subprocess, "Popen") as start:
            self.assertEqual(self.collect(), browser._result("browser_disabled"))
        start.assert_not_called()

    def test_unsupported_platform_does_not_launch(self):
        with patch.object(browser.sys, "platform", "win32"), patch.object(browser.subprocess, "Popen") as start:
            self.assertEqual(self.collect()["stop_reason"], "unsupported_platform")
        start.assert_not_called()

    def test_invalid_or_token_bearing_inputs_never_start_a_browser(self):
        cases = [
            {"calendar_url": CALENDAR + "&captchaResponse=private"},
            {"calendar_url": CALENDAR.replace("https:", "http:")},
            {"calendar_url": CALENDAR.replace("www.wembleygolf.com.au", "evil.example")},
            {"calendar_url": CALENDAR + "#secret"},
            {"date_str": "2026-10-09"},
            {"date_str": "invalid"},
            {"booking_resource_id": "3000000; dangerous"},
            {"products": {"102184": source("102193")}},
            {"products": {"102184": source("102184") + "&token=private"}},
            {"products": {"102184": source("102184"), "102193": source("102193"), "102211": source("102211")}},
            {"products": {}},
        ]
        with patch.object(browser.subprocess, "Popen") as start:
            for case in cases:
                browser.reset_browser_collection_state()
                with self.subTest(case=case):
                    self.assertEqual(self.collect(**case)["stop_reason"], "invalid_request")
        start.assert_not_called()

    def test_timeout_cleans_worker_tree_and_latches_stop_until_new_shard(self):
        process = MagicMock(pid=12345)
        process.communicate.side_effect = subprocess.TimeoutExpired("worker", 45)
        with patch.object(browser.subprocess, "Popen", return_value=process) as start, patch.object(browser, "_WorkerTree") as tree:
            self.assertEqual(self.collect()["stop_reason"], "timeout")
            self.assertEqual(self.collect()["stop_reason"], "timeout")
            self.assertEqual(start.call_count, 1)
            self.assertEqual(process.communicate.call_args.kwargs["timeout"], 43)
            tree.assert_called_once_with(12345)
            tree.return_value.terminate.assert_called_once()
            process.wait.assert_called_once()
            browser.reset_browser_collection_state()
            self.collect()
            self.assertEqual(start.call_count, 2)

    def test_worker_errors_never_expose_exception_urls_and_are_not_retried(self):
        with patch.object(browser.subprocess, "Popen", side_effect=OSError("secret captchaResponse=private")) as start:
            result = self.collect()
            self.assertEqual(result, browser._result("browser_error"))
            self.assertNotIn("private", json.dumps(result))
            self.collect()
        start.assert_called_once()

    @unittest.skipUnless(os.path.isdir("/proc") and os.name == "posix", "Linux process-group cleanup")
    def test_real_timeout_terminates_worker_and_detached_descendants(self):
        real_popen = subprocess.Popen
        started = []
        with tempfile.TemporaryDirectory() as temporary:
            pid_file = Path(temporary) / "child-pid"
            grandchild_file = Path(temporary) / "grandchild-pid"
            detached_child = (
                "import pathlib, subprocess, sys, time; "
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True); "
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(60)"
            )
            helper = (
                "import pathlib, subprocess, sys, time; "
                "child = subprocess.Popen([sys.executable, '-c', sys.argv[3], sys.argv[2]], start_new_session=True); "
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(60)"
            )

            def start_helper(_command, **kwargs):
                process = real_popen([browser.sys.executable, "-c", helper, str(pid_file), str(grandchild_file), detached_child], **kwargs)
                started.append(process)
                return process

            with patch.object(browser.subprocess, "Popen", side_effect=start_helper), patch.object(browser, "TOTAL_TIMEOUT_SECONDS", 0.5):
                self.assertEqual(self.collect(), browser._result("timeout"))
            self.assertEqual(started[0].returncode, -signal.SIGKILL)
            self.assertTrue(pid_file.exists(), "worker must spawn its child before the timeout")
            self.assertTrue(grandchild_file.exists(), "detached child must spawn detached grandchild before timeout")
            for file in (pid_file, grandchild_file):
                child_stat = Path("/proc") / file.read_text() / "stat"
                # A container's PID 1 can leave a dead child as a zombie briefly;
                # verify the descendant is no longer executing, rather than PID reuse.
                for _ in range(20):
                    if not child_stat.exists() or child_stat.read_text().split()[2] in {"Z", "X"}:
                        break
                    time.sleep(0.01)
                else:
                    self.fail("detached browser descendant survived timeout cleanup")

    def test_partial_success_keeps_rows_and_stops_later_collections(self):
        result = {"rows": [{"time": "05:48 am", "spots": 3, "course_raw": "Old Course", "source_url": source("102184")}],
                  "completed_products": ["102184"], "stop_reason": "interactive_challenge"}
        process = MagicMock(pid=12345, returncode=0)
        process.communicate.return_value = (json.dumps(result), None)
        with patch.object(browser.subprocess, "Popen", return_value=process) as start, patch.object(browser, "_WorkerTree"):
            self.assertEqual(self.collect(), result)
            self.assertEqual(self.collect(), browser._result("interactive_challenge"))
        start.assert_called_once()

    @unittest.skipUnless(os.path.isdir("/proc") and os.name == "posix", "Linux orphan adoption")
    def test_guardian_cleans_detached_descendants_after_executor_crash(self):
        with tempfile.TemporaryDirectory() as temporary:
            child_file = Path(temporary) / "child-pid"
            grandchild_file = Path(temporary) / "grandchild-pid"
            child_code = (
                "import pathlib, subprocess, sys, time\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
                "start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid))\n"
                "time.sleep(60)\n"
            )
            crash_code = (
                "import pathlib, subprocess, sys, time\n"
                "child = subprocess.Popen([sys.executable, '-c', sys.argv[3], sys.argv[2]], "
                "start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid))\n"
                "while not pathlib.Path(sys.argv[2]).exists(): time.sleep(0.01)\n"
                "raise SystemExit(1)\n"
            )
            executor_command = [browser.sys.executable, "-c", crash_code, str(child_file), str(grandchild_file), child_code]
            guardian_code = (
                "import json, sys\nfrom app.wembley_browser import _guardian_main\n"
                "raise SystemExit(_guardian_main(json.loads(sys.argv[1])))\n"
            )
            unrelated = subprocess.Popen([browser.sys.executable, "-c", "import time; time.sleep(60)"])
            try:
                run = subprocess.run(
                    [browser.sys.executable, "-c", guardian_code, json.dumps(executor_command)],
                    input=json.dumps(payload()), text=True, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, timeout=5,
                )
                self.assertEqual(run.returncode, 0)
                self.assertEqual(json.loads(run.stdout), browser._result("browser_error"))
                self.assertIsNone(unrelated.poll(), "cleanup must leave unrelated processes running")
                for pid_file in (child_file, grandchild_file):
                    self.assertTrue(pid_file.exists())
                    stat = Path("/proc") / pid_file.read_text() / "stat"
                    for _ in range(20):
                        if not stat.exists() or stat.read_text().split()[2] in {"Z", "X"}:
                            break
                        time.sleep(0.01)
                    else:
                        self.fail("detached descendant survived executor crash")
            finally:
                unrelated.terminate()
                unrelated.wait()

    def test_guardian_fails_closed_without_subreaper_support(self):
        output = io.StringIO()
        with patch.object(browser.sys, "stdin", io.StringIO(json.dumps(payload()))), patch.object(browser.sys, "stdout", output), patch.object(browser, "_enable_subreaper", return_value=False), patch.object(browser.subprocess, "Popen") as start:
            self.assertEqual(browser._guardian_main(), 0)
        self.assertEqual(json.loads(output.getvalue()), browser._result("browser_unavailable"))
        start.assert_not_called()

    def test_success_can_continue_and_worker_debugging_is_disabled(self):
        result = {"rows": [], "completed_products": ["102184", "102193"], "stop_reason": None}
        process = MagicMock(pid=12345, returncode=0)
        process.communicate.return_value = (json.dumps(result), None)
        with patch.dict(os.environ, {"DEBUG": "pw:*", "PWDEBUG": "1", "DEBUG_FILE": "/tmp/debug"}), patch.object(browser.subprocess, "Popen", return_value=process) as start, patch.object(browser, "_WorkerTree"):
            self.assertEqual(self.collect(), result)
            self.assertEqual(self.collect(), result)
        self.assertEqual(start.call_count, 2)
        options = start.call_args.kwargs
        self.assertTrue(options["start_new_session"])
        self.assertEqual(options["stderr"], subprocess.DEVNULL)
        self.assertFalse({"DEBUG", "PWDEBUG", "DEBUG_FILE"} & options["env"].keys())

    def test_only_safe_row_fields_leave_the_parser(self):
        projected = [{"time": "05:48 am", "course": "OLD Course 18 Holes", "available": 3, "taken": 1}]
        self.assertEqual(browser._parse_projections(projected, source("102184")), [{
            "time": "05:48 am", "course_raw": "OLD Course", "spots": 3, "source_url": source("102184"),
        }])

    def test_worker_response_is_rebuilt_without_unknown_fields_or_token_urls(self):
        row = {"time": "05:48 am", "spots": 3, "course_raw": "Old Course", "source_url": source("102184"), "token": "private"}
        candidate = {"rows": [row], "completed_products": ["102184"], "stop_reason": None, "url": "private"}
        cleaned = browser._validated_result(candidate, {"102184": source("102184")})
        self.assertNotIn("private", json.dumps(cleaned))
        row["source_url"] += "&captchaResponse=private"
        self.assertEqual(browser._validated_result(candidate, {"102184": source("102184")}), browser._result("browser_error"))

    def test_malformed_rendered_rows_are_unknown_instead_of_falsely_full(self):
        for changes in ({"time": "unknown"}, {"course": ""}, {"course": "Tuart Course"}, {"available": 5}, {"available": 0, "taken": 0}):
            row = {"time": "05:48 am", "course": "Old Course 1st Tee", "available": 3, "taken": 1, **changes}
            with self.subTest(changes=changes), self.assertRaises(browser._Stop) as stopped:
                browser._parse_projections([row], source("102184"))
            self.assertEqual(stopped.exception.reason, "unrecognized_page")


@unittest.skipUnless(os.environ.get("GOLFHUB_BROWSER_TESTS") == "1", "requires installed Playwright Chromium")
class WembleyRenderedBrowserTests(unittest.TestCase):
    """Normal Chromium runs with every request fulfilled from local fixtures."""
    def setUp(self):
        self.requests = []
        self.calendar_loads = 0
        self.timesheet_loads = []
        self.calendar_prefix = ""
        self.sheet_prefix = {}
        self.sheet_names = {}
        self.sheet_status = {}
        self.empty_sheets = set()
        self.wrong_identity = False
        self.duplicate_cell = False
        self.calendar_calls = ""

    def calendar(self):
        rows = []
        for fee in ("102184", "102193", "102211", "102202"):
            cell = f'''<div class="cell" onclick="redirectToTimesheet('{fee}','{DATE}');">Available</div>'''
            rows.append(f'<div class="feeGroupRow" data-feeid="{fee}"><h3>Course</h3>{cell * (2 if self.duplicate_cell else 1)}</div>')
        return self.calendar_prefix + "".join(rows) + '''<script>
            function redirectToTimesheet(fee, date) {
                window.location.href = '/guests/bookings/ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate='
                    + date + '&feeGroupId=' + fee + '&captchaResponse=fixture-private';
            }
        </script>''' + self.calendar_calls

    def sheet(self, fee):
        if fee in self.empty_sheets:
            return '<div id="no-rows">No rows meeting selected criteria</div>'
        course = "Old" if fee in {"102184", "102211"} else "Tuart"
        holes = "18" if fee in {"102184", "102193"} else "9"
        heading = f'<h1 class="feeName">{self.sheet_names.get(fee, f"{course} Course {holes} Holes")}</h1>'
        rows = []
        for index, (time, available) in enumerate((("05:48 am", 3), ("06:04 am", 4), ("06:12 am", 1))):
            cells = '<div class="cell cell-available" onclick="fetch(\'/booking-was-clicked\')">Available</div>' * available
            cells += '<div class="cell cell-taken">Taken</div>' * (4 - available)
            rows.append(f'<div id="row-secret-{index}" class="row row-time"><h3>{time}</h3><h4>{course} Course 1st Tee</h4>{cells}</div>')
        wrong = "<script>history.replaceState({}, '', location.href.replace('selectedDate=2026-10-08', 'selectedDate=2026-10-09'));</script>" if self.wrong_identity else ""
        return self.sheet_prefix.get(fee, "") + heading + "".join(rows) + wrong

    def route(self, route):
        url = urlsplit(route.request.url)
        self.requests.append(url.path)
        if url.path.endswith("ViewPublicCalendar.msp"):
            self.calendar_loads += 1
            route.fulfill(status=200, content_type="text/html", body=self.calendar())
        elif url.path.endswith("ViewPublicTimesheet.msp"):
            fee = parse_qs(url.query)["feeGroupId"][0]
            self.timesheet_loads.append(fee)
            route.fulfill(status=self.sheet_status.get(fee, 200), content_type="text/html", body=self.sheet(fee))
        else:
            # Even fixture challenge frames/resources cannot contact the network.
            route.fulfill(status=200, content_type="text/html", body="")

    def collect(self, products=("102184", "102193")):
        result = browser._collect_in_browser(payload(products), route_handler=self.route)
        self.assertNotIn("booking-was-clicked", " ".join(self.requests))
        self.assertNotIn("fixture-private", json.dumps(result))
        self.assertNotIn("row-secret", json.dumps(result))
        return result

    def test_reads_both_courses_and_both_rounds_by_only_calendar_navigation(self):
        for products in (("102184", "102193"), ("102211", "102202")):
            with self.subTest(products=products):
                result = self.collect(products)
                self.assertIsNone(result["stop_reason"])
                self.assertEqual(result["completed_products"], list(products))
                self.assertEqual([row["spots"] for row in result["rows"]], [3, 4, 1] * 2)
                self.assertEqual([row["time"] for row in result["rows"][:3]], ["05:48 am", "06:04 am", "06:12 am"])
                self.assertEqual({row["course_raw"] for row in result["rows"]}, {"Old Course", "Tuart Course"})
        self.assertEqual(self.calendar_loads, 4)
        self.assertEqual(self.timesheet_loads, ["102184", "102193", "102211", "102202"])

    def test_visible_challenge_on_calendar_stops_without_any_click(self):
        self.calendar_prefix = '<iframe src="https://www.google.com/recaptcha/api2/anchor?size=normal"></iframe>'
        result = self.collect()
        self.assertEqual(result, browser._result("interactive_challenge"))
        self.assertEqual(self.calendar_loads, 1)
        self.assertEqual(self.timesheet_loads, [])

    def test_invisible_badge_is_ignored_but_visible_challenge_stops_second_product(self):
        self.calendar_prefix = '<iframe src="https://www.google.com/recaptcha/api2/anchor?size=invisible"></iframe>'
        self.sheet_prefix["102193"] = '<iframe src="https://www.google.com/recaptcha/api2/bframe?size=invisible"></iframe>'
        result = self.collect()
        self.assertEqual(result["stop_reason"], "interactive_challenge")
        self.assertEqual(result["completed_products"], ["102184"])
        self.assertEqual(len(result["rows"]), 3)
        self.assertEqual(self.calendar_loads, 2)

    def test_hidden_or_offscreen_challenge_frames_do_not_block_ordinary_navigation(self):
        self.calendar_prefix = '''
            <iframe style="width:0;height:0;border:0" src="https://www.google.com/recaptcha/api2/bframe"></iframe>
            <iframe style="position:absolute;top:-10000px" src="https://www.google.com/recaptcha/api2/bframe"></iframe>
            <div style="display:none"><iframe src="https://www.google.com/recaptcha/api2/bframe"></iframe></div>
        '''
        result = self.collect(("102184",))
        self.assertIsNone(result["stop_reason"])
        self.assertEqual(len(result["rows"]), 3)

    def test_access_denial_status_stops_first_product(self):
        self.sheet_status["102184"] = 403
        result = self.collect()
        self.assertEqual(result, browser._result("access_denied"))
        self.assertEqual(self.calendar_loads, 1)
        self.assertEqual(self.timesheet_loads, ["102184"])

    def test_access_denial_and_login_text_stop_before_click(self):
        for html, reason in (("Access denied", "access_denied"), ("Verify you are human", "interactive_challenge"), ('<input type="password">', "login_required")):
            with self.subTest(reason=reason):
                self.calendar_prefix = html
                result = self.collect()
                self.assertEqual(result, browser._result(reason))
        self.assertEqual(self.timesheet_loads, [])

    def test_no_rows_is_complete_only_after_matching_timesheet_identity(self):
        self.empty_sheets.add("102184")
        result = self.collect(("102184",))
        self.assertEqual(result, {"rows": [], "completed_products": ["102184"], "stop_reason": None})

    def test_wrong_date_never_leaks_times_into_requested_date(self):
        self.wrong_identity = True
        with patch.object(browser, "NAVIGATION_TIMEOUT_SECONDS", 0.4):
            result = self.collect()
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["completed_products"], [])
        self.assertEqual(result["stop_reason"], "timeout")
        self.assertEqual(self.calendar_loads, 1)

    def test_ambiguous_calendar_cells_stop_without_click(self):
        self.duplicate_cell = True
        self.assertEqual(self.collect(), browser._result("unrecognized_page"))
        self.assertEqual(self.timesheet_loads, [])

    def test_wrong_round_heading_is_rejected_even_when_url_matches(self):
        self.sheet_names["102184"] = "OLD Course 9 Holes"
        self.assertEqual(self.collect(), browser._result("unrecognized_page"))
        self.assertEqual(self.timesheet_loads, ["102184"])


if __name__ == "__main__":
    unittest.main()
