"""Seal scoped reconciliation metadata without changing retained evidence."""
import csv
import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import time

START = time.process_time()
ROOT = Path(__file__).resolve().parents[3]
D = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(path):
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, SHA256=sha(path))


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def main():
    old_checks = []
    for relative in ["reports/information-skill-01/checkpoint-follow-through-01/MANIFEST.json",
                     "reports/information-skill-01/MANIFEST.json",
                     "reports/targeted-accuracy-w1w9-01/M3/MANIFEST.json"]:
        manifest = json.loads((ROOT / relative).read_text())
        files = manifest["files"]
        for entry in files:
            assert sha(ROOT / entry["path"]) == entry["SHA256"], entry["path"]
        old_checks.append(dict(manifest=relative, preserved_files=len(files)))
    for path in D.rglob("*.py"):
        compile(path.read_text(), str(path), "exec")
    ledger = json.loads((D / "LEDGER_APPEND_RECEIPT.json").read_text())
    target = ROOT / ledger["target"]
    assert sha(target) == ledger["SHA256"]
    data = gzip.decompress(target.read_bytes())
    parent = gzip.decompress((ROOT / ledger["parent"]).read_bytes())
    assert data.startswith(parent)
    fields = next(csv.reader(io.StringIO(data.decode())))
    assert len(fields) == 44
    # Rows cannot contain embedded physical newlines under this retained schema.
    assert sum(1 for _ in csv.DictReader(io.StringIO(data.decode()))) == 37451
    resources = json.loads((D / "C05-outcomes/FINAL_RESOURCE.json").read_text())
    assert resources["total_charged_CPU"] < 30 and resources["source_GET_used"] == 3
    assert resources["source_HEAD_used"] == 1 and resources["source_bytes"] <= 5242880
    for name in ["PUBLIC_INTAKE_CHECK.json", "C05_GRADE_CHECK.json"]:
        check = json.loads((D / "verification" / name).read_text())
        assert "PASS" in check.get("status", check.get("state", "")), name
    assert "PENDING_ROOT" not in (D / "README.md").read_text()
    assert not subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True).returncode
    new_evidence = [p for p in D.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    outcome_dir = ROOT / "prospective/outcomes/C-NATIVE-GRADE-20261116-NEDET-01"
    outcome_files = [p for p in outcome_dir.rglob("*") if p.is_file()]
    grade = ROOT / "prospective/grades/C-NATIVE-GRADE-20261116-NEDET-01-C-C05-NEDET-FIRST-01.json"
    public_bytes = sum(p.stat().st_size for p in new_evidence + outcome_files + [grade, target])
    assert public_bytes <= 8 * 1024 * 1024
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    write(D / "VALIDATION.json", dict(
        recorded_UTC=now, status="PASS_SCOPED_RECONCILIATION",
        old_sealed_manifests=old_checks, V8_decoded_prefix_preserved=True,
        V9_rows=37451, V9_columns=44, public_aggregate_scope_only=True,
        original_forecasts_unchanged=True, C05_independent_grade_check=bind(D / "verification/C05_GRADE_CHECK.json"),
        focused_existing_contract_checks=bind(D / "FOCUSED_CHECKS.json"),
        Python_compile="PASS_NEW_REPORT_ADAPTERS", git_diff_check="PASS",
        new_model_fits=0, source_history_searches=0, peer_writes=0,
        new_primary_activation=False, CPU_seconds_through_validation=time.process_time()-START))
    prior = 402.21233500999995
    metadata_charge = 100.0
    outcome_charge = resources["total_charged_CPU"]
    write(D / "RESOURCE_CLOSURE.json", dict(
        recorded_UTC=now, unchanged_C_parent_CPU_cap=600,
        prior_charged_CPU=prior, conservative_metadata_checks_publication_charge=metadata_charge,
        metadata_registered_ceiling_including_reserve=140,
        C05_outcome_operation_charge=outcome_charge, C05_cap_unchanged=30,
        total_C_charged_CPU=prior+metadata_charge+outcome_charge,
        parent_recorded_remaining_CPU=600-prior-metadata_charge-outcome_charge,
        measurement_limit="100 is a conservative bookkeeping charge for metadata, independent checks, failed checkers, sealing and ordinary publication/retention; not100 measured seconds or a complete all-process/remote-CI CPU certificate. Earlier limitations remain. C05 includes measured full-process attempts, focused checks and explicit conservative retention/independent-check charges.",
        peer_publication_GETs=dict(A=4, B=6, website=4),
        peer_publication_GET_caps=dict(A=6, B=6, website=4),
        C05_HEADs=1, C05_GETs=3, C05_response_bytes=3053465,
        planned_publication_readback_GET_cap=6, planned_publication_payload_cap=5242880,
        measured_new_public_bytes_before_seal=public_bytes, new_public_cap=8388608,
        A_M3_CPU_cap_unchanged=1260, A_M3_last_received_charged_CPU=1056.334180015,
        A_M3_worker_ceiling_after_reserves=63.665819985,
        additional_allowance=0, budget_transfers=0, new_paid_services=0,
        new_model_fits=0, new_research_forecasts=0, new_original_picks=0))
    # Discovery files are outside the seal so manifest bindings do not self-reference.
    paths = sorted({p for p in D.rglob("*") if p.is_file() and p.name != "MANIFEST.json"
                    and "__pycache__" not in p.parts} | set(outcome_files) | {grade, target})
    write(D / "MANIFEST.json", dict(
        id="C-EXECUTED-RECEIPTS-GAP-CLOSURE-MANIFEST-v1", recorded_UTC=now,
        base_commit="6aaab67d213826d0b2545a24d34cf9ee54d7ff4c", files=[bind(p) for p in paths],
        scope="Permitted public aggregate intake, minimal qualified outcome facts and append-only original forecast grades. No protected peer rows/models or new primary product."))
    for name in ["CURRENT_PROTOCOL.json", "EXPORT_INDEX.json", "ADMISSION_LEDGER.json"]:
        path = ROOT / "reports/abc-championship" / name
        obj = json.loads(path.read_text())
        obj["executed_receipts_gap_closure_01"].update(
            sealed_manifest=bind(D / "MANIFEST.json"), validation=bind(D / "VALIDATION.json"),
            resources=bind(D / "RESOURCE_CLOSURE.json"))
        write(path, obj)
    print(json.dumps(dict(status="SEALED", files=len(paths), ledger_rows=37451,
                         old_manifests=old_checks, total_C_charge=prior+metadata_charge+outcome_charge)))


if __name__ == "__main__":
    main()
