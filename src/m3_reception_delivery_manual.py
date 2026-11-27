"""Single-owner manual entry points. Nothing runs on import or on a schedule."""
import argparse
import fcntl
import json
import os
import re
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

from m3_reception_delivery_window import (
    END, EVENT, EXPIRY, FILES, GAME, META, PRODUCT, REPORT, ROOT, RUN, WINDOW, Window,
    canonical, exclusive, instant, load, require, save, sha, stamp, utc,
)
from m3_reception_delivery_io import BRANCH, CHECKER, REPO, SITE, commit_files, github_read, publish_stage, push_once, read_c_file, source_body


def source_and_fit(window, previous):
    from m3_reception_delivery import check_storage, draft
    check_storage(window, previous)
    for name in ("schedule", "roster", "weekly"):
        source_body(window, name)
    return draft(window, previous)


def monitor_stage(window, phase, prior):
    """A single numerical worker. The parent only enforces this account's hard limits."""
    cutoff = "2026-11-27T19:10:00Z" if phase == "draft" else "2026-11-27T19:34:00Z"
    window.check(150 if phase == "draft" else 30, cutoff)
    argv = [sys.executable, str(Path(__file__).resolve()), "--work", str(window.work),
            "--prior", str(prior), "_child", phase]
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", OMP_THREAD_LIMIT="1", MKL_NUM_THREADS="1",
               NUMEXPR_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1", BLIS_NUM_THREADS="1", ARROW_NUM_THREADS="1")
    with (window.work / (phase + "-worker.log")).open("xb") as log:
        reader, writer = os.pipe()
        try:
            os.write(writer, f"{os.getpid()}:{phase}".encode())
            env["M3_STAGE_PIPE"] = str(reader)
            proc = subprocess.Popen(argv, env=env, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True, pass_fds=(reader,))
        finally:
            os.close(reader)
            os.close(writer)
        largest = 0
        try:
            while proc.poll() is None:
                window.check(before=cutoff)
                status = Path("/proc") / str(proc.pid) / "status"
                try:
                    fields = status.read_text()
                    match = re.search(r"^VmRSS:\s+(\d+) kB", fields, re.M)
                    if match:
                        largest = max(largest, int(match[1]) * 1024)
                        require(largest <= 1288490188, "Worker RSS cap")
                    threads = re.search(r"^Threads:\s+(\d+)", fields, re.M)
                    if threads:
                        require(int(threads[1]) <= 1, "Single-thread worker limit")
                except FileNotFoundError:
                    pass
                time.sleep(0.1)
            require(proc.returncode == 0, "Worker stopped. Preserve the private log and original attempt.")
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            state = window.state()
            state.setdefault("worker_peaks", {})[phase] = largest
            state.setdefault("worker_exits", {})[phase] = {"status": proc.returncode, "UTC": stamp()}
            window.put(state)


def child(window, phase, prior):
    descriptor = int(os.environ.pop("M3_STAGE_PIPE", "-1"))
    require(descriptor >= 0 and stat.S_ISFIFO(os.fstat(descriptor).st_mode), "Manual stage supervisor required")
    with os.fdopen(descriptor, "rb") as stream:
        require(stream.read(96) == f"{os.getppid()}:{phase}".encode(), "Stage supervisor mismatch")
    with (window.work / "DEN_PIT_WRITER.lock").open("rb") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise ValueError("Single writer supervision was lost")
    state = window.state()
    require(state["state"] == "OPEN" and state["active_meter_start"] is not None, "Child outside active window")
    # Enforce a hard process CPU limit even if the parent stops. The parent watches actual
    # cgroup consumption and RSS separately and reserves the final 75 CPU seconds.
    import resource
    remaining = int(225 - float(window.charged_cpu()))
    require(remaining > 0, "No precompletion CPU")
    resource.setrlimit(resource.RLIMIT_CPU, (remaining, remaining))
    if phase == "draft":
        source_and_fit(window, prior)
    else:
        from m3_reception_delivery import issue
        source_body(window, "native")
        issue(window)


def publish_and_reopen(window, stage):
    from m3_reception_delivery import FOLDER, SERVER
    content, tip = publish_stage(window, stage)
    refs = {"draft": [("model", FOLDER / "CURRENT_MODEL.json.gz"), ("query", FOLDER / "QUERY_PROJECTION.json"),
                      ("draft", FOLDER / "INPUT_MANIFEST.json")],
            "original": [("original", FOLDER / "FORECASTS.json.xz")],
            "envelope": [("envelope", FOLDER / "REC_MEAN_ENVELOPE.json"), ("server", SERVER)]}[stage]
    for slot, path in refs:
        body = read_c_file(window, slot, path, content)
        if slot == "original":
            exclusive(window.work / "ORIGINAL_READBACK.xz", body)
    if stage == "envelope":
        read_c_file(window, "pointer", ROOT / "reports/abc-championship/EXPORT_INDEX.json", tip)
    return dict(content=content, discovery=tip)


def check_run(window, mode):
    from m3_reception_delivery import server_proof
    original = window.state()["publications"]["original"]
    require(original["state"] == "ACCEPTED", "No published original capture")
    commit = original["commit"]
    if mode == "find":
        endpoint = ("repos/" + REPO + "/actions/workflows/c-checks-pages.yml/runs?event=pull_request&branch=" +
                    quote(BRANCH, safe="") + "&created=2026-11-27&per_page=6")
        runs = json.loads(github_read(window, "find_capture_run", endpoint))["workflow_runs"]
        matching = [r for r in runs if r["head_sha"] == commit or
                    any(p["number"] == 65 and p["head"]["sha"] == commit for p in r.get("pull_requests", []))]
        require(len(matching) == 1, "No unique normal PR check for the capture commit")
        run = matching[0]
        write_id = {"id": run["id"], "commit": commit}
        save(window.work / "CAPTURE_RUN_ID.json", write_id)
        if run["status"] != "completed":
            return {"id": run["id"], "status": run["status"]}
    else:
        run_id = load(window.work / "CAPTURE_RUN_ID.json")
        require(run_id["commit"] == commit, "Run belongs to different capture")
        reads = window.state()["reads"]
        slot = "capture_completed" if "capture_completed" not in reads else "same_run_terminal"
        run = json.loads(github_read(window, slot, f"repos/{REPO}/actions/runs/{int(run_id['id'])}"))
        if run["status"] != "completed":
            return {"id": run["id"], "status": run["status"]}
    return server_proof(window, run, commit, (window.work / "ORIGINAL_READBACK.xz").read_bytes())


def owner_file(window, slot, descriptor):
    repo = CHECKER if slot == "b_result" else SITE
    require(descriptor["repository"] == repo and re.fullmatch("[a-f0-9]{40}", descriptor["commit"]),
            "An immutable owner file is required")
    clean = Path(descriptor["path"])
    require(not clean.is_absolute() and ".." not in clean.parts and len(clean.parts) > 0,
            "Unbound owner artifact location")
    body = github_read(window, slot, f"repos/{repo}/contents/{quote(clean.as_posix())}?ref={descriptor['commit']}")
    require(sha(body) == descriptor["sha256"], "Owner's actual bytes differ from the handoff")
    return body


def consume_registration(window, handoff):
    from m3_reception_delivery import verify_owner_admission
    window.check(30, "2026-11-27T19:28:00Z")
    require(handoff["game"] == EVENT and handoff["product"] == PRODUCT, "Wrong website handoff")
    def body(slot):
        ref = handoff[slot]
        if "inline" not in ref:
            return owner_file(window, slot, ref)
        # Inline owner documents use the actual PR1 response already retrieved.
        wire = load(window.work / "website_preissue-body.json")
        comments = wire if isinstance(wire, list) else [wire]
        matches = [c for c in comments if c.get("html_url") == handoff["owner_verification"]["locator"]]
        require(len(matches) == 1 and ref["inline"] in matches[0]["body"], "Inline admission body outside owner receipt")
        raw = ref["inline"].encode()
        require(sha(raw) == ref["sha256"], "Inline owner body binding")
        return raw
    registry = body("registry")
    catalog = body("catalog")
    return verify_owner_admission(window, registry, catalog, handoff["owner_verification"])


def account_totals(window):
    state = window.state()
    sources, reads = state["source"], state["reads"]
    hops = [r for source in sources.values() for r in source["wire"]]
    return dict(cumulative_CPU_s=str(window.charged_cpu(state)),
                cumulative_active_elapsed_s=str(window.active_elapsed(state)),
                cumulative_source_logical=3 + len(sources), cumulative_source_wire=5 + len(hops),
                cumulative_source_bytes=3918325 + sum(r["bytes"] for r in hops),
                cumulative_file_reads=23 + sum(k in FILES for k in reads),
                cumulative_metadata_reads=6 + sum(k in META for k in reads),
                file_bytes=6849135 + sum(r.get("received_bytes", r["limit"]) for k, r in reads.items() if k in FILES),
                window_metadata_bytes=sum(r.get("received_bytes", r["limit"]) for k, r in reads.items() if k in META),
                returned_publication_bytes=sum(p.get("response_bytes", 0) for p in state["publications"].values()),
                publication_attempts=len(state["publications"]), fit_attempts=len(state["fit_attempts"]))


def close_event(window, operator):
    """Publish the one event closure, and retain the charge through its push privately."""
    from m3_reception_delivery import FOLDER, SERVER, bind
    require(utc() >= instant(WINDOW), "An upcoming event cannot be closed for missing launch receipts")
    state = window.state()
    require(state["state"] in ("PREWINDOW", "OPEN") and state["terminal_UTC"] is None, "Event already closed")
    require(bool(operator["reason"].strip()), "Specific closure reason required")
    index = ROOT / "reports/abc-championship/EXPORT_INDEX.json"
    doc = load(index)
    group = doc["shared_game_sim_01_saved_method_followthrough"]
    delivery = group.setdefault("den_pit_reception_mean_delivery", {})
    run = load(FOLDER / "RUN.json") if (FOLDER / "RUN.json").exists() else None
    ready = (state["publications"].get("envelope", {}).get("state") == "ACCEPTED" and
             all(state["reads"].get(k, {}).get("state") == "RECEIVED" for k in ("envelope", "server", "pointer")))
    if not state["opened_UTC"]:
        require(not state["fit_attempts"] and not state["source"] and run is None, "Unopened event contains science")
    site_evidence, b_evidence = operator.get("website_receipt"), operator.get("B_receipt")
    if b_evidence:
        require(ready and state["reads"].get("b_result", {}).get("state") == "RECEIVED"
                and b_evidence.startswith("https://github.com/" + CHECKER + "/"), "Missing delivered B evidence")
    if site_evidence:
        require(ready and state["reads"].get("website_disposition", {}).get("state") == "RECEIVED"
                and site_evidence.startswith("https://github.com/" + SITE + "/"), "Missing delivered website evidence")
    site_status = operator.get("website_status", "NO_NEW_ADMISSION")
    require(site_status in ("NO_NEW_ADMISSION", "DELIVERED_SHADOW", "SERVED_NUMERICAL"), "Invalid delivery disposition")
    if site_status != "NO_NEW_ADMISSION":
        require(site_evidence and operator.get("site_reason"), "Actual owner disposition required")
    if site_status == "SERVED_NUMERICAL":
        require(operator.get("served") and instant(EXPIRY) <= utc() and operator["served"].get("expiry_fallback_receipt"),
                "Actual served observations and expiry/fallback evidence required")
    result = dict(event=EVENT, game=GAME, product=PRODUCT, kickoff_UTC=END, run=RUN, window_opened_UTC=state["opened_UTC"],
                  as_of_UTC=stamp(), reason=operator["reason"], status=operator["status"],
                  cumulative_fit_attempts=len(state["fit_attempts"]), fit_status=state["fit_attempts"],
                  original_local_forecasts=run["native"] + run["prior_only"] if run else 0,
                  supported_player_counts=run["coverage"] if run else None, qualified_typed_feed=ready,
                  qualified_forecasts=(run["native"] + run["prior_only"]) if ready else 0,
                  original_native=run["native"] if run else 0, original_prior_only=run["prior_only"] if run else 0,
                  immutable_envelope=delivery.get("envelope") if ready else None,
                  persistence=bind(SERVER) if SERVER.exists() else None, producer_expiry_UTC=EXPIRY if ready else None,
                  B_delivered_check_receipt=b_evidence, website_status=site_status, website_receipt=site_evidence,
                  site_reason=operator.get("site_reason"), served=operator.get("served"),
                  attendance=operator["attendance"], resource_totals_before_closure=account_totals(window),
                  separate_preparation_operations=state["local_preparation_operations"], accounting="Cgroup segments include supervisory overhead. The final push and its return are measured at local terminal close.",
                  previous_activated_elapsed_s=2246.139, old_close_to_nominated_open_s=80553.860746,
                  registered_owner_routes=operator["registered_owner_routes"], next_dependency=operator.get("next_dependency"))
    report = REPORT / "DEN_PIT_TERMINAL_V1.json"
    exclusive(report, canonical(result) + b"\n")
    delivery["terminal"] = bind(report)
    group.update(producer_status=result["status"], new_current_feed=bool(ready and utc() < instant(EXPIRY)),
                 den_pit_feed_qualified_at_delivery=ready, website_release=site_status == "SERVED_NUMERICAL")
    index.write_text(json.dumps(doc, indent=2, ensure_ascii=True, allow_nan=False) + "\n")
    commit_files([report, index], "Close the single DEN–PIT reception-mean delivery window")
    try:
        receipt = push_once(window, "closure")
        print(json.dumps({"closure_commit": receipt["commit"], "publication": receipt["state"]}))
    finally:
        window.terminal(operator["reason"])
        exclusive(window.work / "TERMINAL_ACCOUNT.json", canonical(account_totals(window)) + b"\n")


def main():
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                 "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
        os.environ[name] = "1"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True, type=Path, help="Existing private single-writer event account")
    parser.add_argument("--prior", required=True, type=Path, help="Read-only PHI–DAL terminal evidence")
    parser.add_argument("action", choices=("prepare", "park", "resume", "attendance-read", "attended", "open",
                                          "draft", "native-issue", "publish", "website-receipt",
                                          "register", "find-run", "proof", "envelope", "owner-result", "close", "_child"))
    parser.add_argument("argument", nargs="?")
    args = parser.parse_args()
    window = Window(args.work)
    if args.action == "_child":
        require(args.argument in ("draft", "native-issue"), "Invalid child stage")
        return child(window, args.argument, args.prior)
    with window.locked():
        if args.action == "prepare":
            window.prepare(args.prior / "publication-receipt.json")
        elif args.action == "park":
            window.park_cpu("prewindow preparation")
        elif args.action == "resume":
            window.resume_cpu()
        elif args.action == "attendance-read":
            # User-supplied or prearranged direct owner bulletins only, in one launch operation.
            require(instant("2026-11-27T18:59:30Z") <= utc() < instant("2026-11-27T19:04:00Z"), "Read attendance at launch")
            query = Path(args.argument).read_text()
            require(all(('"'+name+'"') in query for name in ("NFL-forecasting-V2", "nicks-expert-nfl-picks"))
                    and "search(" not in query and "history(" not in query and "mutation" not in query,
                    "Use only prebound owner handoffs")
            exclusive(window.work / "attendance.graphql", query.encode())
            body = github_read(window, "attendance", "graphql", graphql=query)
            exclusive(window.work / "ATTENDANCE_RESPONSE.json", body)
            state = window.state()
            state["reads"]["attendance"]["query_SHA256"] = sha(query.encode())
            window.put(state)
        elif args.action == "attended":
            window.accept_attendance(load(Path(args.argument)))
        elif args.action == "open":
            window.open()
        elif args.action in ("draft", "native-issue"):
            monitor_stage(window, args.action, args.prior)
        elif args.action == "publish":
            require(args.argument in ("draft", "original", "envelope"), "Unknown publication stage")
            print(json.dumps(publish_and_reopen(window, args.argument)))
        elif args.action == "website-receipt":
            slot = args.argument
            require(slot in ("website_preissue", "website_disposition"), "Unknown site receipt")
            # The attendee can supply the actual comment ID; otherwise use a single bounded
            # event-window read on the already-agreed original website PR1.
            direct = load(window.work / "ATTENDED_HANDOFF.json")["website"].get(slot + "_comment_id")
            endpoint = (f"repos/{SITE}/issues/comments/{int(direct)}" if direct else
                        f"repos/{SITE}/issues/1/comments?since=2026-11-27T19:00:00Z&per_page=8")
            body = github_read(window, slot, endpoint)
            exclusive(window.work / (slot + "-body.json"), body)
        elif args.action == "register":
            consume_registration(window, load(Path(args.argument)))
        elif args.action in ("find-run", "proof"):
            print(json.dumps(check_run(window, "find" if args.action == "find-run" else "completed")))
        elif args.action == "envelope":
            from m3_reception_delivery import envelope
            envelope(window)
        elif args.action == "owner-result":
            owner_file(window, "b_result", load(Path(args.argument)))
        elif args.action == "close":
            close_event(window, load(Path(args.argument)))
        state = window.state()
        print(json.dumps(dict(phase=state["state"], fit_attempts=len(state["fit_attempts"]),
                              active_elapsed_s=str(window.active_elapsed()), charged_CPU_s=str(window.charged_cpu()))))


if __name__ == "__main__":
    main()
