"""Repair current discovery hashes after append-only ledger publication.

No sealed evidence, model, original forecast or grade is modified.
"""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import time

START = time.process_time()
ROOT = Path(__file__).resolve().parents[4]
D = Path(__file__).resolve().parent
COMMON = ROOT / "reports/abc-championship"


def bind(path):
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                SHA256=hashlib.sha256(path.read_bytes()).hexdigest())


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def main():
    receipt = D / "REPAIR_RECEIPT.json"
    assert not receipt.exists(), "Append-only repair receipt already exists"
    old_manifest = ROOT / "reports/information-skill-01/executed-receipts-gap-closure-01/MANIFEST.json"
    for item in json.loads(old_manifest.read_text())["files"]:
        assert bind(ROOT / item["path"])["SHA256"] == item["SHA256"]
    current = COMMON / "CURRENT_PROTOCOL.json"
    obj = json.loads(current.read_text())
    old_bindings = {key: obj[key] for key in ["admission", "tasks"]}
    obj["admission"] = bind(COMMON / "ADMISSION_LEDGER.json")
    obj["tasks"] = bind(COMMON / "TASK_LEDGER.json")
    write(receipt, dict(
        id="C-DISCOVERY-BINDING-REPAIR-v1", recorded_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        failed_commit="e44ac7e509b2edd30aa739f1154dfd6b73beb845",
        failed_run="https://github.com/NickNicky19/NFL-forecasting-NGS-C/actions/runs/43783694847",
        exact_failure="BOUND_HASH_MISMATCH reports/abc-championship/ADMISSION_LEDGER.json; current task hash also stale",
        effect="Packaging/discovery only. New ledgers had been appended after the earlier period check; old hashes remained in current pointers.",
        old_bindings=old_bindings, refreshed_bindings={key: obj[key] for key in ["admission", "tasks"]},
        new_predictions=0, changed_grades=0, new_model_fits=0, new_sources=0,
        all75_new_checkpoint_sealed_members_unchanged=True,
        budget="Existing C metadata/completion allowance; no new grant or A-M3/C05 source allowance."))
    obj["executed_receipts_gap_closure_01"]["packaging_repair"] = bind(receipt)
    write(current, obj)
    export = COMMON / "EXPORT_INDEX.json"
    obj = json.loads(export.read_text())
    obj["common_protocol"] = bind(current)
    obj["executed_receipts_gap_closure_01"]["packaging_repair"] = bind(receipt)
    write(export, obj)
    checked = subprocess.run(["python", "src/abc_period_validation_v2.py"], cwd=ROOT,
                             capture_output=True, text=True)
    write(D / "VALIDATION.json", dict(
        status="PASS" if checked.returncode == 0 else "FAILED",
        command="python src/abc_period_validation_v2.py", returncode=checked.returncode,
        stdout=checked.stdout, stderr=checked.stderr,
        CPU_seconds=time.process_time()-START, no_NFL_fit_or_grade_change=True))
    assert checked.returncode == 0, checked.stderr
    print(checked.stdout.strip())


if __name__ == "__main__":
    main()
