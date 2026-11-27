"""Finite source and GitHub operations on the registered manual producer route."""
import json
import os
import re
import subprocess
import select
import time
from urllib import error, parse, request

from m3_reception_delivery_window import (
    EVENT, FILES, GAME, META, PIN, REPORT, ROOT, RUN, SOURCES, exclusive,
    instant, load, require, sha, stamp, utc,
)

REPO = "NickNicky19/NFL-forecasting-NGS-C"
SITE = "NickNicky19/nicks-expert-nfl-picks"
CHECKER = "NickNicky19/NFL-forecasting-V2"
BRANCH = "research/shared-game-sim-01-follow-through-v1"


class DeclineAutomaticRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def source_body(window, key):
    require(key in SOURCES, "Unregistered football source")
    if key == "native":
        require(utc() > instant("2026-11-27T19:25:00Z") and (window.work / "PREISSUE_ADMISSION.json").exists(),
                "Native observation requires actual preissue admission and a viable expiry")
        window.check(30, "2026-11-27T19:34:00Z", 15)
    else:
        window.check(150, "2026-11-27T19:10:00Z", 185)
    state = window.state()
    require(key not in state["source"], "Source already attempted")
    limits = window.amendment["C_limits"]["sources"]
    idx = SOURCES.index(key)
    spec = load(REPORT / "REC_MEAN_CURRENT_DELIVERY_REQUEST_V1.json")
    url = limits["native_URL"] if key == "native" else spec["inputs"]["fresh_route"][idx]["url"]
    _, wire_limit, byte_limit = limits["next_purposes_and_wire_byte_caps"][idx]
    rec = dict(url=url, state="ENTERED", started_UTC=stamp(), wire=[])
    state["source"][key] = rec
    window.put(state)
    opener = request.build_opener(DeclineAutomaticRedirect)
    try:
        for hop in range(wire_limit):
            wire_count = sum(len(s["wire"]) for s in state["source"].values())
            all_bytes = sum(r["bytes"] for s in state["source"].values() for r in s["wire"])
            require(wire_count + 5 < 11 and len(state["source"]) + 3 <= 7, "Source count cap")
            limit = min(byte_limit - sum(r["bytes"] for r in rec["wire"]), 4470283 - all_bytes, 4194304)
            require(limit > 0, "Source byte cap")
            wire = dict(host=parse.urlsplit(url).hostname, started_UTC=stamp(), bytes=0)
            rec["wire"].append(wire)
            window.put(state)
            req = request.Request(url, headers={"User-Agent": "NFL-forecasting-NGS-C/manual-current-reception",
                                                "Accept-Encoding": "identity"})
            try:
                response = opener.open(req, timeout=20)
            except error.HTTPError as exc:
                response = exc
            with response as res:
                declared = res.headers.get("Content-Length")
                require(declared is None or 0 <= int(declared) <= limit, "Declared source body exceeds budget")
                raw = res.read(limit)
                wire.update(status=res.status, bytes=len(raw), observed_UTC=stamp())
                window.put(state)
                require(len(raw) < limit or (declared is not None and int(declared) == limit), "Unconfirmed EOF at cap")
                if res.status in (301, 302, 303, 307, 308):
                    dest = parse.urlsplit(parse.urljoin(url, res.headers.get("Location", "")))
                    require(key in ("roster", "weekly") and hop == 0 and dest.scheme == "https" and
                            dest.hostname in ("github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"),
                            "Unapproved redirect")
                    url = dest.geturl()
                    continue
                require(res.status == 200 and (declared is None or int(declared) == len(raw)), "Incomplete source response")
                rec.update(state="OBTAINED", bytes=len(raw), sha256=sha(raw), observed_UTC=wire["observed_UTC"],
                           headers={k: res.headers.get(k) for k in ("Date", "Age", "Last-Modified", "ETag", "Content-Encoding")})
                path = window.work / (key + ".source")
                exclusive(path, raw)
                require(path.read_bytes() == raw, "Source did not reopen")
                window.put(state)
                return rec
        raise ValueError("Source redirect count exhausted")
    except Exception as exc:
        rec.update(state="STOP", reason=str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
        window.put(state)
        raise


def github_read(window, slot, endpoint, *, graphql=None):
    """Persist one bounded response before decoding. gh supplies the existing credential."""
    cap = window.claim_read(slot)
    require(slot in FILES + META and (
        endpoint == "graphql" and graphql is not None or
        any(endpoint.startswith("repos/" + repo + "/") for repo in (REPO, SITE, CHECKER))
    ), "Unregistered GitHub route")
    args = ["gh", "api", "--include"]
    if slot in FILES:
        args.extend(["-H", "Accept: application/vnd.github.raw+json"])
    args.append(endpoint)
    if graphql is not None:
        args.extend(["-f", "query=" + graphql])
    proc = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    parts = bytearray()
    deadline = time.monotonic() + 30
    try:
        while len(parts) < cap:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([proc.stdout], [], [], remaining)[0]:
                raise TimeoutError("Registered GitHub read timed out")
            chunk = os.read(proc.stdout.fileno(), min(65536, cap - len(parts)))
            if not chunk:
                break
            parts.extend(chunk)
        raw = bytes(parts)
        if len(raw) == cap and proc.poll() is None:
            proc.kill()
        code = proc.wait(timeout=max(1, deadline - time.monotonic()))
    except BaseException:
        proc.kill()
        proc.wait()
        window.finish_read(slot, bytes(parts), "INTERRUPTED")
        raise
    finally:
        proc.stdout.close()
    exclusive(window.work / (slot + ".http"), raw)
    header, boundary, body = raw.partition(b"\r\n\r\n")
    if not boundary:
        header, boundary, body = raw.partition(b"\n\n")
    ok = code == 0 and len(raw) < cap and bool(boundary) and bool(re.match(rb"HTTP/[\d.]+ 200\b", header))
    window.finish_read(slot, raw, "RECEIVED" if ok else "STOP")
    require(ok, "Capped GitHub read failed for " + slot)
    if graphql is not None:
        require(not json.loads(body).get("errors"), "Incomplete owner metadata response")
    return body


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def push_once(window, stage):
    require(git("branch", "--show-current") == BRANCH, "Wrong C producer branch")
    require(git("remote", "get-url", "origin") == "https://github.com/" + REPO + ".git", "Wrong C destination")
    require(not git("status", "--porcelain", "--untracked-files=no"), "Uncommitted tracked producer files")
    validate_payload(window)
    window.claim_publication(stage)
    argv = ["git", "-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential",
            "push", "origin", BRANCH]
    result = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=45)
    state = window.state()
    ack = state["publications"][stage]
    ack.update(finished_UTC=stamp(), state="ACCEPTED" if result.returncode == 0 else "REJECTED",
               commit=git("rev-parse", "HEAD"), response_bytes=len(result.stdout), response_sha256=sha(result.stdout))
    window.put(state)
    require(result.returncode == 0, "Publication rejected on C's existing branch")
    require(sum(x.get("response_bytes", 0) for x in state["publications"].values()) +
            sum(x.get("received_bytes", x["limit"]) for x in state["reads"].values()) <= 6291456,
            "Unexpected publication/readback payload size")
    return ack


def read_c_file(window, slot, path, commit):
    require(re.fullmatch("[0-9a-f]{40}", commit) and path.is_relative_to(ROOT), "Exact C file revision required")
    body = github_read(window, slot, "repos/" + REPO + "/contents/" + str(path.relative_to(ROOT)) + "?ref=" + commit)
    expected = subprocess.check_output(["git", "show", commit + ":" + str(path.relative_to(ROOT))], cwd=ROOT)
    require(body == expected, "Immutable C file readback mismatch")
    return body


def validate_payload(window):
    """Review names in every newly reachable commit, including subsequently removed files."""
    run = "prospective/runs/" + RUN + "/"
    report = REPORT.relative_to(ROOT).as_posix() + "/"
    allowed = {run + n for n in ("CURRENT_MODEL.json.gz", "QUERY_PROJECTION.json", "INPUT_MANIFEST.json",
                                  "FORECASTS.json.xz", "RUN.json", "REC_MEAN_ENVELOPE.json")}
    allowed |= {"src/m3_reception_delivery" + suffix + ".py" for suffix in ("", "_inputs", "_io", "_window", "_manual")}
    allowed |= {"reports/abc-championship/" + n + ".json" for n in ("EXPORT_INDEX", "CURRENT_PROTOCOL", "TASK_LEDGER", "ADMISSION_LEDGER")}
    allowed |= {"prospective/receipts/" + RUN + "-server.json", report + "DEN_PIT_TERMINAL_V1.json",
                "tests/test_m3_reception_window_control.py"}
    commits = git("rev-list", "--reverse", PIN + "..HEAD").splitlines()
    for commit in commits:
        paths = set(git("diff-tree", "-r", "--no-commit-id", "--name-only", "--no-renames", commit).splitlines())
        require(paths <= allowed, "Unreviewed path in reachable C history")
    objects = [line.split(" ", 1)[0] for line in git("rev-list", "--objects", PIN + "..HEAD").splitlines()]
    result = subprocess.run(["git", "cat-file", "--batch-check=%(objecttype) %(objectsize)"], cwd=ROOT,
                            input="\n".join(objects) + "\n", text=True, capture_output=True, check=True)
    total = sum(int(line.split()[1]) for line in result.stdout.splitlines() if line.startswith("blob "))
    require(total <= window.amendment["C_limits"]["storage"]["next_durable_derived_versions_max"],
            "Cumulative derived publication-size limit")
    return total


def commit_files(paths, message):
    require(not git("diff", "--cached", "--name-only"), "Unrelated staged files")
    names = [str(p.relative_to(ROOT)) for p in paths]
    git("add", "--", *names)
    require(set(git("diff", "--cached", "--name-only").splitlines()) == set(names), "Unexpected staged publication")
    git("diff", "--cached", "--check")
    git("commit", "-m", message)
    return git("rev-parse", "HEAD")


def publish_stage(window, stage):
    from m3_reception_delivery import FOLDER, SERVER, bind
    index = ROOT / "reports/abc-championship/EXPORT_INDEX.json"
    files = {"draft": ["CURRENT_MODEL.json.gz", "QUERY_PROJECTION.json", "INPUT_MANIFEST.json"],
             "original": ["FORECASTS.json.xz", "RUN.json"], "envelope": ["REC_MEAN_ENVELOPE.json"]}[stage]
    paths = [FOLDER / name for name in files]
    if stage == "envelope":
        paths.append(SERVER)
    commit = commit_files(paths, "Preserve DEN–PIT reception mean " + stage)
    if stage in ("draft", "envelope"):
        d = load(index)
        group = d["shared_game_sim_01_saved_method_followthrough"]
        route = group.setdefault("den_pit_reception_mean_delivery", {})
        require(stage not in route, "Stage already published")
        route[stage] = dict(commit=commit, product=window.state()["product"], game_id=GAME,
                            event=EVENT, run=RUN, files=[bind(p) for p in paths])
        if stage == "envelope":
            packet = load(FOLDER / "REC_MEAN_ENVELOPE.json")
            route[stage].update(original_capture_commit=packet["server"]["capture_commit"],
                                website_verification_bundle=packet["actual_website_admission"]["review"]["locator"],
                                github_run_proof=packet["server"]["workflow_run_url"], expires_at=packet["expires_at"])
        index.write_text(json.dumps(d, indent=2, ensure_ascii=True, allow_nan=False) + "\n")
        commit_files([index], "Bind immutable C " + stage + " files for DEN–PIT owner readback")
    publication = push_once(window, stage)
    return commit, publication["commit"]
