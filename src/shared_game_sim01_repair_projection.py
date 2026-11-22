"""Pure complete-path gate for the approved SIM numerical repair.

No fit, source access, simulation, clocks, filesystem work or network operation
occurs here.  The caller supplies measured canary and current-ledger records.
An estimate is permission to execute only after every registered guard passes;
it is never a claim that a larger iteration limit converges.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math

CPU_CAP = 1800.0
CONTROLLED_WALL_CAP = 7200.0
END_TO_END_CAP = 21600.0
COMPLETION_RESERVE = 380.0
RSS_CAP = 1288490188
RETAINED_CAP = 536870912
PEAK_CAP = 805306368
WHOLE_C_CAP = 2684354560
ORIGINAL_LAUNCH = "2026-11-22T18:05:20.108935+00:00"
FIXED_DEADLINE = "2026-11-23T00:05:20.108935+00:00"


def _time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("NAIVE_PROJECTION_CLOCK")
    return parsed.astimezone(timezone.utc)


def _number(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("MISSING_OR_INVALID_COST:" + name)
    value = float(value)
    if not math.isfinite(value) or value < 0 or positive and value <= 0:
        raise ValueError("MISSING_OR_INVALID_COST:" + name)
    return value


def _first(mapping, *keys):
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def project_remainder(canary, remaining_actor_counts, ledger, storage, now_utc,
                      *, implementation_CPU_remaining=0.0,
                      fixed_CPU_remaining=0.0, fixed_wall_remaining=0.0,
                      readback_wall_remaining=None,
                      expected_remaining_games=73):
    """Return PASS or a finite STOP with all shortages and assumptions.

    Root's exact records are accepted directly: canary conditioning_CPU,
    generation_CPU, serialization_reopen_CPU, source_restore_CPU, wall,
    actor_count, body_bytes, uncompressed_member_bytes, peak_RSS_bytes,
    local_reopened/DP_reopened/remote_reopened, trajectories.  The ledger uses
    charged_CPU_seconds and charged_controlled_wall_seconds.  Storage uses
    current_whole_bytes/current_new_bytes and baseline_whole_C_bytes.

    Remaining games are the fixed complete remainder, never a favorable subset.
    All per-game costs and bytes use at least two times measured canary cost,
    scaled quadratically for any larger actor population.  Source restoration
    is charged once for the remainder worker, also with the factor of two.
    """
    result = dict(decision="STOP", assumptions=dict(
        cost_factor=2.0,
        actor_scaling="max(1, remaining actors / canary actors)^2 for all per-game costs and bytes",
        completion_reserve_CPU=COMPLETION_RESERVE,
        reserve_contents="160CPU checks/reproduction +220CPU retention/reporting; included once",
        no_population_reduction=True,
        scope="MEASURED_CONSERVATIVE_PLANNING_GATE;NOT_RUNTIME_OR_CONVERGENCE_PROOF"),
        shortfalls=[], missing=[])
    required = ("local_reopened", "DP_reopened", "remote_reopened")
    if (not canary or canary.get("trajectories") != 10000
            or not all(canary.get(key) is True for key in required)):
        result.update(reason="STOP_NO_COMPLETE_REOPENED_CANARY",
                      required_canary_flags=list(required) + ["trajectories=10000"])
        return result
    try:
        if (isinstance(expected_remaining_games, bool)
                or not isinstance(expected_remaining_games, int)
                or expected_remaining_games < 0
                or len(remaining_actor_counts) != expected_remaining_games):
            raise ValueError("INCOMPLETE_REGISTERED_REMAINDER")
        now, launch = _time(now_utc), _time(ledger["first_scientific_launch_UTC"])
        if launch != _time(ORIGINAL_LAUNCH):
            raise ValueError("ORIGINAL_LAUNCH_CLOCK_CHANGED")
        elapsed = (now-launch).total_seconds()
        if elapsed < 0:
            raise ValueError("CURRENT_CLOCK_BEFORE_ORIGINAL_LAUNCH")
        actor0 = _number(canary["actor_count"], "canary.actor_count", positive=True)
        actors = [_number(x, "remaining_actor_count", positive=True)
                  for x in remaining_actor_counts]
        ratios = [max(1.0, x/actor0) for x in actors]
        scales = [2.0*x*x for x in ratios]
        sums, maximum = sum(scales), max(scales, default=0.0)
        condition = _number(canary["conditioning_CPU"], "conditioning_CPU")
        generation = _number(canary["generation_CPU"], "generation_CPU", positive=True)
        serialize = _number(canary["serialization_reopen_CPU"], "serialization_reopen_CPU")
        restore = _number(_first(canary, "source_restore_CPU", "source_CPU"), "source_restore_CPU")
        per_cpu = condition+generation+serialize
        per_wall = _number(canary["wall"], "canary.wall", positive=True)
        # A wall estimate cannot be below its measured CPU content.
        per_wall = max(per_wall, per_cpu)
        current_cpu = _number(_first(ledger, "charged_CPU_seconds", "CPU_seconds"), "charged_CPU_seconds")
        current_wall = _number(_first(ledger, "charged_controlled_wall_seconds", "controlled_wall_seconds"), "charged_controlled_wall_seconds")
        prep = _number(implementation_CPU_remaining, "implementation_CPU_remaining")
        if prep > 40:
            raise ValueError("IMPLEMENTATION_REMAINDER_EXCEEDS_REGISTERED40CPU")
        fixed_cpu = _number(fixed_CPU_remaining, "fixed_CPU_remaining")
        fixed_wall = _number(fixed_wall_remaining, "fixed_wall_remaining")
        fixed_wall = max(fixed_wall, fixed_cpu)
        remote_wall = _number(readback_wall_remaining, "readback_wall_remaining")
        if generation > 6.0:
            result["shortfalls"].append(dict(resource="canary_generation_CPU", excess=generation-6.0, cap=6.0))
        body = _number(canary["body_bytes"], "body_bytes", positive=True)
        unpacked = _number(canary["uncompressed_member_bytes"], "uncompressed_member_bytes", positive=True)
        rss = _number(canary["peak_RSS_bytes"], "peak_RSS_bytes", positive=True)
        whole = _number(storage["current_whole_bytes"], "current_whole_bytes")
        new = _number(_first(storage, "current_new_retained_bytes", "current_new_bytes"), "current_new_bytes")
        baseline = _number(storage["baseline_whole_C_bytes"], "baseline_whole_C_bytes")
        if whole < baseline or new < whole-baseline:
            raise ValueError("STORAGE_BASELINE_OR_NEW_FOOTPRINT_INCONSISTENT")
        duplication = max(3.0, _number(storage.get("duplication_multiplier", 3), "duplication_multiplier"))
        metadata = _number(storage.get("additional_metadata_retained_bytes", 16*1024*1024), "metadata_retained_bytes")
        additional_raw = body*sums
        # Two persistent copies: local retained body plus Git object.  Readback
        # and decoded working bodies are simultaneous, separately bounded.
        retained_increment = 2.0*additional_raw+metadata
        peak_increment = duplication*additional_raw+unpacked*maximum+metadata
        reserve_wall = COMPLETION_RESERVE*max(1.0, per_wall/per_cpu)
        restore_wall = max(restore, _number(
            canary.get("source_restore_wall", restore), "source_restore_wall"))
        cpu_remaining = sums*per_cpu+2.0*restore+prep+fixed_cpu+COMPLETION_RESERVE
        wall_remaining = sums*per_wall+2.0*restore_wall+prep+fixed_wall+remote_wall+reserve_wall
        projected_rss = max(rss, rss*max(ratios, default=1.0))
        projections = dict(
            remaining_games=len(actors), actor_counts=list(remaining_actor_counts),
            measured_per_game_CPU=per_cpu, measured_per_game_wall=per_wall,
            scaled_game_cost_sum=sums, source_restore_CPU_once_with_factor2=2*restore,
            source_restore_wall_once_with_factor2=2*restore_wall,
            CPU_remaining=cpu_remaining, CPU_final=current_cpu+cpu_remaining,
            controlled_wall_remaining=wall_remaining,
            controlled_wall_final=current_wall+wall_remaining,
            original_launch_elapsed_at_gate=elapsed,
            original_launch_elapsed_projected=elapsed+wall_remaining,
            original_launch_UTC=ORIGINAL_LAUNCH, fixed_deadline_UTC=FIXED_DEADLINE,
            remote_readback_wall_bound=remote_wall,
            new_retained_projected=new+retained_increment,
            new_peak_projected=new+peak_increment,
            whole_C_peak_projected=whole+peak_increment,
            RSS_projected=projected_rss, remaining_compressed_bytes_projected=additional_raw,
            largest_uncompressed_working_bytes_projected=unpacked*maximum,
            storage_duplication_multiplier=duplication, metadata_retained_bytes=metadata)
        result["projection"] = projections
        guards = (
            ("CPU", projections["CPU_final"], CPU_CAP),
            ("controlled_wall", projections["controlled_wall_final"], CONTROLLED_WALL_CAP),
            ("original_launch_elapsed", projections["original_launch_elapsed_projected"], END_TO_END_CAP),
            ("new_retained_bytes", projections["new_retained_projected"], RETAINED_CAP),
            ("new_peak_bytes", projections["new_peak_projected"], PEAK_CAP),
            ("whole_C_peak_bytes", projections["whole_C_peak_projected"], WHOLE_C_CAP),
            ("RSS_bytes", projected_rss, RSS_CAP),
        )
        for resource, total, cap in guards:
            if total > cap:
                result["shortfalls"].append(dict(resource=resource, projected=total, cap=cap, excess=total-cap))
        if now >= _time(FIXED_DEADLINE):
            result["shortfalls"].append(dict(resource="fixed_deadline", observed=now.isoformat(), deadline=FIXED_DEADLINE))
        result.update(decision="PASS" if not result["shortfalls"] else "STOP_MEASURED_REMAINDER_DOES_NOT_FIT",
                      reason="ALL_REGISTERED_LIMITS_AND_COMPLETION_RESERVE_FIT" if not result["shortfalls"] else "NO_AUTOMATIC_EXTENSION_OR_SUBSET")
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        result.update(reason="STOP_MISSING_OR_INVALID_MEASURED_COST", missing=[str(error)])
    return result
