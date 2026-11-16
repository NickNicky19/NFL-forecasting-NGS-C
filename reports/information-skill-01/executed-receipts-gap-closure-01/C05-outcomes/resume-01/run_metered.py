"""Meter one already authorized C05 source/grading process; no retry."""
import datetime
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

root = Path("/workspace/ngs-c")
folder = root / "reports/information-skill-01/executed-receipts-gap-closure-01/C05-outcomes/resume-01"
assert not (folder / "PROCESS_RESOURCE.json").exists()
assert (folder / "EXECUTION_GO.json").exists()
import hashlib
expected_code_SHA256 = "42f5e5ac0937d18622558bbc2da4c99e49a082c75c644a1d858abd3f65a7d79e"
assert hashlib.sha256((folder / "execute_grading.py").read_bytes()).hexdigest() == expected_code_SHA256
assert json.loads((folder / "EXECUTION_GO.json").read_bytes())["code_SHA256"] == expected_code_SHA256
start = time.monotonic()
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
wrapper_start_cpu = time.process_time()
before = resource.getrusage(resource.RUSAGE_CHILDREN)
env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
           MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1", PYTHONPATH="src")

def cap():
    # Carry prior failure and new preparation; retain headroom below total 30.
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))

with Path("/tmp/gap-c05-resume-01-execution.log").open("w") as log:
    proc = subprocess.run([sys.executable, "-u", str(folder / "execute_grading.py")],
                          cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
                          preexec_fn=cap)
after = resource.getrusage(resource.RUSAGE_CHILDREN)
child_cpu = after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
wrapper_cpu = time.process_time() - wrapper_start_cpu
receipt = dict(
    id="C-C05-NEDET-RESUME-01-FULL-PROCESS-RESOURCE-v1", started_UTC=started,
    completed_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    returncode=proc.returncode, full_child_CPU_seconds=child_cpu,
    wrapper_CPU_seconds=wrapper_cpu, conservative_preparation_CPU=1.0,
    resume_charged_CPU_seconds=child_cpu + wrapper_cpu + 1.0,
    prior_charged_CPU_seconds=4.767533874,
    total_charged_CPU_seconds=4.767533874 + child_cpu + wrapper_cpu + 1.0,
    child_CPU_hard_cap=20, overall_operation_CPU_cap=30,
    wall_seconds=time.monotonic()-start,
    child_peak_RSS_bytes=after.ru_maxrss*1024,
    version_HEAD_cap=1, conditional_body_GET_cap=3, source_bytes_cap=5242880,
    new_fits=0, new_forecasts=0, new_original_picks=0,
    preparation_limit="Additional conservative one second covers repair, static reads, AST IO fixture, compile and wrapper preparation; original failed process and original preparation charged separately.",
    scope="Measured complete child includes imports and restoration verification. "
          "No new issuance, model search, account or A-M3 budget used.")
(folder / "PROCESS_RESOURCE.json").write_text(json.dumps(receipt, indent=2)+"\n")
print(json.dumps(receipt))
raise SystemExit(proc.returncode)
