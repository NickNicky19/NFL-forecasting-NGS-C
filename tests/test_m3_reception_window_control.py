"""Exercise the attended launch and operation reservations without invoking football sources or models."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import m3_reception_delivery_window as control


class WindowControlTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.window = control.Window(temporary.name)
        self.state = dict(run=control.RUN, state="PREWINDOW", fit_attempts=[], reads={}, publications={},
                          opened_UTC=None, terminal_UTC=None, prior=[43.958674, 2246.139, 3918325, 23, 6, 6849135],
                          cpu_segments=[], active_meter_start=100, startup_provision=1)
        self.window.put(self.state)
        meter = patch.object(control, "cpu_counter", return_value=100)
        meter.start()
        self.addCleanup(meter.stop)

    def test_wrong_owner_or_static_readiness_cannot_confirm_attendance(self):
        repo = "NickNicky19/nicks-expert-nfl-picks"
        url = "https://github.com/" + repo + "/pull/1#issuecomment-123"
        item = dict(url=url, body="Fictional attended slot", authorAssociation="OWNER")
        response = {"data": {"site": {"nameWithOwner": repo, "nodes": [item]}}}
        self.assertTrue(control.owner_statement(response, repo, url, item["body"]))
        self.assertFalse(control.owner_statement(response, "NickNicky19/NFL-forecasting-V2", url, item["body"]))
        self.assertFalse(control.owner_statement(response, repo, url, "A different statement"))
        item["authorAssociation"] = "NONE"
        self.assertFalse(control.owner_statement(response, repo, url, item["body"]))
        encoded = json.dumps(response).encode()
        self.assertEqual(control.response_body(b"HTTP/2.0 200 OK\nDate: test\n\n" + encoded), encoded)

    def test_read_slots_cannot_be_repurposed_or_repeated(self):
        with self.assertRaisesRegex(ValueError, "Live window"):
            self.window.claim_read("query")
        self.assertEqual(self.window.claim_read("attendance"), 131072)
        self.window.finish_read("attendance", b"fixture", "STOP")
        with self.assertRaisesRegex(ValueError, "spent read"):
            self.window.claim_read("attendance")
        self.assertIsNone(self.window.state()["opened_UTC"])

    def test_held_completion_cost_and_failed_fit_remain_charged(self):
        self.state.update(state="OPEN", opened_UTC=control.WINDOW)
        self.window.put(self.state)
        with patch.object(control, "utc", return_value=control.instant("2026-11-27T19:00:01Z")):
            self.window.claim_fit()
            self.assertEqual(len(self.window.state()["fit_attempts"]), 1)
            with self.assertRaisesRegex(ValueError, "already charged"):
                self.window.claim_fit()
            with self.assertRaisesRegex(ValueError, "CPU or completion reserve"):
                self.window.check(181)
        with patch.object(control, "utc", return_value=control.instant(control.END)):
            with self.assertRaisesRegex(ValueError, "Outside"):
                self.window.check(completion=True)

    def test_calendar_age_does_not_charge_a_never_opened_window(self):
        with patch.object(control, "utc", return_value=control.instant(control.END)):
            self.assertEqual(str(self.window.active_elapsed()), "2246.139")
            with self.assertRaisesRegex(ValueError, "Outside launch"):
                self.window.open()


if __name__ == "__main__":
    unittest.main()
