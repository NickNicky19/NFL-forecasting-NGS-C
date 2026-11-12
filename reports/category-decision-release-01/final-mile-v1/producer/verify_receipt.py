"""Verify this public retention receipt without network, imports or model execution."""
import hashlib
import json
import lzma
from pathlib import Path


def verify():
    root = Path(__file__).resolve().parent
    ledger = json.loads((root / "FETCH_LEDGER.json").read_text())
    assert len(ledger) <= 14
    assert sum(row.get("normalized_return_bytes", 0) for row in ledger) <= 8 << 20
    assert all(row["state"] != "REGISTERED_NOT_READ" for row in ledger)
    checked = 0
    for row in ledger:
        path = root / (row["name"] + ".json.xz")
        if path.exists() and "decoded_SHA256" in row:
            data = lzma.decompress(path.read_bytes())
            assert len(data) == row["decoded_bytes"], row["name"]
            assert hashlib.sha256(data).hexdigest() == row["decoded_SHA256"], row["name"]
            checked += 1
    members = json.loads((root / "PATCH_DERIVED_MEMBERS.json").read_text())
    for member in members:
        data = lzma.decompress((root / member["retained"]).read_bytes())
        assert len(data) == member["bytes"], member["path"]
        assert hashlib.sha256(data).hexdigest() == member["sha256"], member["path"]
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + bytes([0]) + data).hexdigest()
        assert blob == member["expected_git_blob_sha1"], member["path"]
        checked += 1
    admission = json.loads((root / "ADMISSION.json").read_text())
    assert admission["PR"]["state"] == "open"
    assert admission["PR"]["draft"] and not admission["PR"]["merged"]
    ci = admission["source_evidence"]["actual_current_head_source_CI"]
    assert ci["head_sha"] == admission["PR"]["head_sha"]
    assert ci["status"] == "completed" and ci["conclusion"] == "success"
    assert ci["path"] != ".github/workflows/lab.yml"
    assert admission["resources"]["new_fits"] == admission["resources"]["new_inference"] == 0
    assert admission["source_evidence"]["prepared_config"]["public_export_authorized"] is False
    assert admission["admission"].startswith("ADMIT_PUBLIC_SOURCE_AND_STAGE_RECEIPT_ONLY")
    manifest = root / "MANIFEST.json"
    if manifest.exists():
        for member in json.loads(manifest.read_text())["files"]:
            data = (root / member["path"]).read_bytes()
            assert len(data) == member["bytes"], member["path"]
            assert hashlib.sha256(data).hexdigest() == member["SHA256"], member["path"]
        checked += len(json.loads(manifest.read_text())["files"])
    return {"state": "PASS_PUBLIC_RETENTION_AND_STAGE_BOUNDARIES", "checked_bindings": checked,
            "network_reads": 0, "fits": 0, "inference": 0, "new_NFL_evidence": 0}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
