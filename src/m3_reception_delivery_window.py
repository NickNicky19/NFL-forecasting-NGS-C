"""Manual controls for the single approved DEN–PIT reception-mean delivery."""
import contextlib
import fcntl
import hashlib
import json
import os
import resource
import subprocess
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/shared-game-sim-01/saved-method-follow-through-v1"
PIN = "65b36a24342608353504bb5a22abdac8eddbae38"
AMENDMENT_SHA = "8fbb66f7cafef7ca6726e201445d6fef44280e4cc458660730efefc24f2e1fde"
B_PIN = "6d05a214a6a7b9c7e582f9adef5679d04cd19cb1"
EVENT = "401873083"
GAME = "2026_12_DEN_PIT"
RUN = "C-M3-REC-MEAN-20261127-DEN-PIT-01"
PRODUCT = "C-M3-v1.1::rec::M3-0::base::MEAN_POINT"
WINDOW = "2026-11-27T19:00:00Z"
ISSUE_DEADLINE = "2026-11-27T19:40:00Z"
EXPIRY = "2026-11-27T19:55:00Z"
END = "2026-11-27T20:00:00Z"
CONDITION = "observed_statistical_appearance_v1"
CONDITION_SHA = "f8a4e007e7d1ffbbf636ba02f0194a995b14cffccc750d71fad98973da0d313b"
FILES = ("draft", "model", "query", "registry", "catalog", "original", "server", "envelope", "pointer", "b_result")
META = ("find_capture_run", "capture_completed", "same_run_terminal", "website_preissue", "website_disposition", "attendance")
SOURCES = ("schedule", "roster", "weekly", "native")
PUBLICATIONS = ("draft", "original", "envelope", "closure")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc)


def stamp():
    return utc().isoformat()


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "Timezone required")
    return parsed


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".writing")
    with temporary.open("wb") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def exclusive(path, raw):
    with Path(path).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def load(path):
    return json.loads(Path(path).read_bytes())


def response_body(wire):
    """Return the body actually received from GitHub, with its original bytes."""
    for separator in (b"\r\n\r\n", b"\n\n"):
        header, marker, body = wire.partition(separator)
        if marker:
            require(header.startswith(b"HTTP/") and b" 200" in header.splitlines()[0], "GitHub handoff status")
            return body
    raise ValueError("Missing GitHub handoff headers")


def owner_statement(response, repository, locator, statement, query=""):
    """Require a real repository-scoped comment or a file on the owner's bound revision."""
    require(bool(statement.strip()), "Empty owner statement")
    def objects(value):
        if isinstance(value, dict):
            yield value
            for item in value.values():
                yield from objects(item)
        elif isinstance(value, list):
            for item in value:
                yield from objects(item)

    for node in objects(response):
        if node.get("nameWithOwner") != repository:
            continue
        for item in objects(node):
            url = item.get("url", item.get("html_url", ""))
            if url == locator and "body" in item and statement in item["body"]:
                return item.get("authorAssociation", item.get("author_association")) in ("OWNER", "MEMBER", "COLLABORATOR")
            if url == locator and "/commit/" in url and statement in item.get("message", ""):
                return True
            if "/blob/" in locator and statement in (item.get("text") or ""):
                revision, _, path = locator.split("/blob/", 1)[1].partition("/")
                # A branch-relative file needs that same branch's resolved revision
                # in the same response. Never substitute a later branch-tip lookup.
                references = [revision]
                references.extend(obj["name"] for obj in objects(node) if isinstance(obj.get("name"), str)
                                  and isinstance(obj.get("target"), dict) and obj["target"].get("oid") == revision)
                if (len(revision) == 40 and all(c in "0123456789abcdef" for c in revision)
                        and path and any(json.dumps(ref + ":" + path) in query for ref in references)
                        and item.get("oid") == hashlib.sha1(
                            b"blob " + str(len(item["text"].encode())).encode() + b"\0" + item["text"].encode()
                        ).hexdigest()):
                    return True
    return False


def cpu_counter():
    fields = dict(line.split() for line in Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines())
    return int(fields["usage_usec"])


def immutable_amendment():
    path = REPORT / "REC_MEAN_NEXT_WINDOW_AMENDMENT_V1.json"
    raw = path.read_bytes()
    require(sha(raw) == AMENDMENT_SHA, "Changed amendment")
    require(subprocess.check_output(["git", "show", PIN + ":" + str(path.relative_to(ROOT))], cwd=ROOT) == raw,
            "Amendment differs from approved commit")
    return json.loads(raw)


class Window:
    """One writer, one charge per operation, with the original account carried forward."""

    def __init__(self, work):
        self.work = Path(work).resolve()
        self.path = self.work / "DEN_PIT_ACCOUNT.json"
        self.amendment = immutable_amendment()

    @contextlib.contextmanager
    def locked(self):
        with (self.work / "DEN_PIT_WRITER.lock").open("a+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield

    def prepare(self, previous_receipt):
        if self.path.exists():
            current = load(self.path)
            require(current["approval"] == PIN and current["run"] == RUN, "Wrong existing account")
            return current
        previous = load(previous_receipt)
        actual = [previous[k] for k in ("CPU_charge_seconds", "conservative_elapsed_seconds", "source_bytes",
                                       "file_reads", "metadata_reads", "returned_file_bytes")]
        require(actual == [43.958674, 2246.139, 3918325, 23, 6, 6849135], "Unrecognized prior terminal carry")
        require(sha(Path(previous_receipt).read_bytes()) ==
                self.amendment["terminal_carry"]["proof"]["local_terminal_receipt"]["sha256"], "Prior receipt hash")
        prep = load(self.work / "PREPARATION_ACCOUNT.json")
        state = dict(approval=PIN, approval_sha256=AMENDMENT_SHA, run=RUN, product=PRODUCT,
                     state="PREWINDOW", opened_UTC=None, terminal_UTC=None, prior=actual, fit_attempts=[],
                     prior_source_logical=3, prior_source_wire=5, source={}, reads={}, publications={},
                     local_preparation_operations=prep["prewindow_reporting_ops"], prep_start=prep["opening_clock_utc"],
                     cpu_segments=[], active_meter_start=prep["cpu_meter_baseline_usec"],
                     startup_provision=prep["precounter_CPU_provision_s"], b_pin=B_PIN,
                     b_carry_cpu=63, b_carry_wall=1230, b_left_cpu=27, b_left_wall=570,
                     b_base_operations=48, b_conditional_separate_pointer_operation=49)
        exclusive(self.path, canonical(state) + b"\n")
        return state

    def state(self):
        return load(self.path)

    def put(self, state):
        save(self.path, state)

    def charged_cpu(self, state=None):
        state = self.state() if state is None else state
        total = Decimal(str(state["prior"][0])) + Decimal(str(state["startup_provision"]))
        usec = sum(s["charged_usec"] for s in state["cpu_segments"])
        if state["active_meter_start"] is not None:
            delta = cpu_counter() - state["active_meter_start"]
            require(delta >= 0, "CPU meter epoch changed; reconcile before work")
            usec += delta
        return total + Decimal(usec) / 1_000_000

    def park_cpu(self, phase):
        state = self.state()
        require(state["state"] != "OPEN", "The live CPU meter cannot be paused")
        if state["active_meter_start"] is not None:
            delta = cpu_counter() - state["active_meter_start"]
            require(delta >= 0, "Unreconciled CPU meter")
            state["cpu_segments"].append(dict(phase=phase, end_UTC=stamp(), charged_usec=delta))
            state["active_meter_start"] = None
            self.put(state)

    def resume_cpu(self):
        state = self.state()
        if state["active_meter_start"] is None:
            state["active_meter_start"] = cpu_counter()
            self.put(state)

    def active_elapsed(self, state=None):
        state = self.state() if state is None else state
        if state["opened_UTC"] is None:
            return Decimal("2246.139")
        end = instant(state["terminal_UTC"]) if state["terminal_UTC"] else utc()
        return Decimal("2246.139") + Decimal(str(max(0.0, (end - instant(WINDOW)).total_seconds())))

    def check(self, remaining_work_cpu=0, before=None, wall_need=0, completion=False):
        state = self.state()
        require(state["state"] == "OPEN" and state["active_meter_start"] is not None, "Live window is closed")
        now = utc()
        require(instant(WINDOW) <= now < instant(END), "Outside the fixed DEN–PIT window")
        reserve = Decimal(0 if completion else 75)
        require(self.charged_cpu(state) + Decimal(str(remaining_work_cpu)) + reserve <= 300,
                "Cumulative CPU or completion reserve")
        cutoff = instant(before or (END if completion else "2026-11-27T19:50:00Z"))
        require((cutoff - now).total_seconds() > wall_need, "Remaining path exceeds fixed calendar gate")
        require(self.active_elapsed(state) < Decimal("5846.139"), "Cumulative active wall cap")
        require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= 1288490188, "RSS cap")

    def accept_attendance(self, verified):
        """Seal the manually read owner statements and the actual retrieval evidence."""
        require(self.state()["opened_UTC"] is None and utc() < instant("2026-11-27T19:10:00Z"), "Launch gate passed")
        launch = self.state()["reads"].get("attendance", {})
        wire = (self.work / "attendance.http").read_bytes()
        require(launch.get("state") == "RECEIVED" and sha(wire) == launch["SHA256"], "Launch readback is missing")
        payload = response_body(wire)
        owners = {"B": "NickNicky19/NFL-forecasting-V2", "website": "NickNicky19/nicks-expert-nfl-picks"}
        require(set(verified) == set(owners), "Both registered owners must attend")
        for name, repo in owners.items():
            receipt = verified[name]
            raw = (self.work / receipt["wire_file"]).read_bytes()
            require(repo == receipt["repository"] and sha(raw) == receipt["wire_sha256"], "Owner body binding")
            require(receipt["locator"].startswith("https://github.com/" + repo + "/"), "Owner location")
            through = EXPIRY if name == "website" else "2026-11-27T19:48:00Z"
            require(receipt["game"] == EVENT and instant(receipt["covered_until_UTC"]) >= instant(through), "Wrong game or slot")
            query = (self.work / "attendance.graphql").read_text()
            require(sha(query.encode()) == launch["query_SHA256"], "Changed launch query")
            require(raw == payload and owner_statement(json.loads(raw), repo, receipt["locator"], receipt["owner_statement"], query),
                    "Attendance statement absent from the actual owner handoff")
            require(receipt["product"] == PRODUCT and receipt["event_run_id"] == RUN, "Wrong packet agreement")
            if name == "B":
                require(set(receipt["packet_reads"]) == {"C_EVENT_POINTER", "IMMUTABLE_ENVELOPE", "ORIGINAL_VALUES",
                                                          "WEBSITE_VERIFICATION_BUNDLE", "SERVER_RUN_PROOF"},
                        "B delivery locations must be agreed")
                cpu_need = receipt.get("expected_check_CPU_s", 10)
                wall_need = receipt.get("expected_check_wall_s", 240)
                require(0 < cpu_need <= 10 and 0 < wall_need <= 240 and receipt["operation_ceiling"] == 49
                        and cpu_need + 10 <= receipt["cpu_remaining_s"] <= 27
                        and wall_need + 180 <= receipt["controlled_wall_remaining_s"] <= 570,
                        "B account does not cover its declared check and reserves")
            else:
                require(instant(receipt["preissue_until_UTC"]) >= instant("2026-11-27T19:28:00Z") and
                        instant(receipt["preissue_from_UTC"]) <= instant("2026-11-27T19:10:00Z"),
                        "Website preissue stage uncovered")
            require(receipt["attending_role"] == ("final-check" if name == "B" else "preissue-and-final"),
                    "Wrong handoff role")
        exclusive(self.work / "ATTENDED_HANDOFF.json", canonical(verified) + b"\n")

    def open(self):
        state = self.state()
        require(state["state"] == "PREWINDOW" and state["opened_UTC"] is None, "Window already used")
        require(instant(WINDOW) <= utc() < instant("2026-11-27T19:10:00Z"), "Outside launch window")
        attendance = load(self.work / "ATTENDED_HANDOFF.json")
        require(set(attendance) == {"B", "website"}, "Both owner confirmations required")
        for record in attendance.values():
            require(sha((self.work / record["wire_file"]).read_bytes()) == record["wire_sha256"], "Owner bytes changed")
        cpu = self.charged_cpu(state)
        prepared_cpu = cpu - Decimal("43.958674")
        remaining_qualification = max(Decimal(11), Decimal(25) - prepared_cpu)
        require(cpu + remaining_qualification + 120 + 30 + 75 <= 300, "Complete CPU path does not fit")
        require((instant("2026-11-27T19:10:00Z") - utc()).total_seconds() > 360, "Complete draft path cannot fit")
        require(state["active_meter_start"] is not None, "Launch CPU meter is inactive")
        require(state["reads"].get("attendance", {}).get("state") == "RECEIVED", "Launch owner check has not been received")
        b = attendance["B"]
        state.update(state="OPEN", opened_UTC=stamp(), attendance_sha256=sha(canonical(attendance)),
                     b_left_cpu=b["cpu_remaining_s"], b_carry_cpu=90 - b["cpu_remaining_s"],
                     b_left_wall=b["controlled_wall_remaining_s"], b_carry_wall=1800 - b["controlled_wall_remaining_s"],
                     b_packet_operation_ceiling=b["operation_ceiling"])
        self.put(state)

    def claim_fit(self):
        self.check(150, "2026-11-27T19:10:00Z", 180)
        state = self.state()
        require(not state["fit_attempts"], "Single fit already charged")
        exclusive(self.work / "FIT_ATTEMPT.json", canonical(dict(run=RUN, UTC=stamp())) + b"\n")
        state["fit_attempts"].append(dict(entered_UTC=stamp(), state="ENTERED"))
        self.put(state)

    def claim_read(self, slot):
        state = self.state()
        require(slot in FILES + META and slot not in state["reads"], "Unreserved or spent read")
        if slot != "attendance":
            self.check(completion=slot in ("server", "envelope", "pointer", "b_result", "website_disposition"))
        else:
            require(state["state"] == "PREWINDOW", "Attendance read belongs before launch")
        config = self.amendment["C_limits"]["readback"]
        cap = config["file_purposes_and_bytes"][FILES.index(slot)][1] if slot in FILES else config["metadata_bytes_each_max"]
        spent = sum(r.get("received_bytes", r["limit"]) for r in state["reads"].values())
        cap = min(cap, config["next_returned_bytes_max_including_overhead"] - spent)
        require(cap > 0, "Returned-byte allowance exhausted")
        state["reads"][slot] = dict(started_UTC=stamp(), limit=cap, state="ENTERED")
        self.put(state)
        return cap

    def finish_read(self, slot, raw, status):
        state = self.state()
        receipt = state["reads"][slot]
        require(receipt["state"] == "ENTERED", "Read was already finalized")
        receipt.update(state=status, finished_UTC=stamp(), received_bytes=len(raw), SHA256=sha(raw))
        self.put(state)
        require(len(raw) <= receipt["limit"], "Oversized response")

    def claim_publication(self, stage):
        state = self.state()
        require(stage in PUBLICATIONS and stage not in state["publications"], "Publication already attempted")
        if stage != "closure":
            cutoff = {"draft": "2026-11-27T19:10:00Z", "original": "2026-11-27T19:34:00Z",
                      "envelope": "2026-11-27T19:44:00Z"}[stage]
            self.check(completion=stage == "envelope", before=cutoff)
        state["publications"][stage] = dict(started_UTC=stamp(), state="ENTERED")
        self.put(state)

    def terminal(self, reason):
        state = self.state()
        require(state["terminal_UTC"] is None, "Terminal record already exists")
        state.update(state="CLOSED", terminal_UTC=stamp(), reason=reason)
        self.put(state)
        self.park_cpu("terminal")
        return self.state()
