"""Deterministic arithmetic tests only; no NFL data, fitting or sampling."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from shared_game_sim01_repair_projection import project_remainder


class ProjectionContracts(unittest.TestCase):
    def inputs(self):
        canary = dict(local_reopened=True, DP_reopened=True, remote_reopened=True,
                      trajectories=10000, actor_count=20, conditioning_CPU=.1,
                      generation_CPU=.1, serialization_reopen_CPU=.1, wall=.3,
                      source_restore_CPU=.1, body_bytes=1000,
                      uncompressed_member_bytes=2000, peak_RSS_bytes=1000000)
        ledger = dict(charged_CPU_seconds=300, charged_controlled_wall_seconds=400,
                      first_scientific_launch_UTC="2026-11-22T18:05:20.108935+00:00")
        storage = dict(current_whole_bytes=1200000000, current_new_bytes=100000000,
                       baseline_whole_C_bytes=1100000000)
        return canary, [20]*73, ledger, storage, "2026-11-22T21:00:00+00:00"

    def test_complete_path_passes_with_reserve_included_once(self):
        r=project_remainder(*self.inputs(), readback_wall_remaining=300)
        self.assertEqual(r["decision"], "PASS")
        self.assertAlmostEqual(r["projection"]["CPU_remaining"], 73*2*.3+.2+380)

    def test_remote_reopen_is_required(self):
        a=self.inputs();a[0]["remote_reopened"]=False
        self.assertEqual(project_remainder(*a, readback_wall_remaining=300)["reason"], "STOP_NO_COMPLETE_REOPENED_CANARY")

    def test_original_launch_cannot_reset(self):
        a=self.inputs();a[2]["first_scientific_launch_UTC"]="2026-11-22T20:00:00+00:00"
        r=project_remainder(*a, readback_wall_remaining=300)
        self.assertIn("ORIGINAL_LAUNCH_CLOCK_CHANGED", r["missing"][0])

    def test_missing_games_or_network_cost_fail_closed(self):
        a=self.inputs();a[1].pop()
        self.assertEqual(project_remainder(*a, readback_wall_remaining=300)["decision"], "STOP")
        self.assertIn("readback_wall_remaining", project_remainder(*self.inputs())["missing"][0])

    def test_larger_actors_scale_costs_quadratically(self):
        a=self.inputs();a[1][0]=40
        r=project_remainder(*a, readback_wall_remaining=300)
        self.assertEqual(r["projection"]["scaled_game_cost_sum"], 72*2+8)

    def test_cpu_shortfall_does_not_shrink_population(self):
        a=self.inputs();a[0]["conditioning_CPU"]=20
        r=project_remainder(*a, readback_wall_remaining=300)
        self.assertEqual(r["decision"], "STOP_MEASURED_REMAINDER_DOES_NOT_FIT")
        self.assertEqual(r["projection"]["remaining_games"], 73)
        self.assertIn("CPU", [x["resource"] for x in r["shortfalls"]])

    def test_expired_clock_or_storage_shortfall_stop(self):
        a=list(self.inputs());a[4]="2026-11-23T00:06:00+00:00"
        r=project_remainder(*a, readback_wall_remaining=300)
        self.assertIn("fixed_deadline", [x["resource"] for x in r["shortfalls"]])
        a=self.inputs();a[0]["body_bytes"]=4000000
        r=project_remainder(*a, readback_wall_remaining=300)
        self.assertIn("new_retained_bytes", [x["resource"] for x in r["shortfalls"]])


if __name__=="__main__":
    unittest.main()
