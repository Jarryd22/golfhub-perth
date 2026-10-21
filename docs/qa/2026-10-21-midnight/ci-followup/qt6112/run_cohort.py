"""Predeclared paired cache-close cohort; preserve every outcome without retry."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
ROOTS = {
    "pr13": Path("/workspace/golfhub-midnight-baseline-20261021"),
    "pr14": Path("/workspace/golfhub-midnight-20261021"),
}
EXPECTED = {"pr13": "8b01866f3783d9ef021e114c81c139dede1facc1",
            "pr14": "9ed31ad463e00637732162e0592442ae3f66668a"}
HARNESS = ROOTS["pr14"] / "tests/test_thread_lifecycle.py"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import qVersion

report = {
    "started_utc": datetime.now(timezone.utc).isoformat(),
    "python": sys.version, "python_executable": sys.executable,
    "pyside": pyside_version, "qt": qVersion(),
    "scenario": "cache_close", "planned_rounds": 10,
    "planned_invocations": 20, "timeout_seconds": 30,
    "predeclared_stop": "Stop immediately after the fourth timeout (>3 total); no retries or discarded outcomes.",
    "order": "Odd rounds PR13 then PR14; even rounds PR14 then PR13.",
    "harness": str(HARNESS), "harness_sha256": sha(HARNESS),
    "sources": {}, "runs": [],
}
for label, root in ROOTS.items():
    commit = git(root, "rev-parse", "HEAD")
    assert commit == EXPECTED[label], (label, commit)
    assert sha(root / "tests/test_thread_lifecycle.py") == report["harness_sha256"]
    assert git(root, "diff", "HEAD", "--", "app/qt_golfhub_app.py", "tests/test_thread_lifecycle.py") == ""
    report["sources"][label] = {"root": str(root), "commit": commit,
                                "source_sha256": sha(root / "app/qt_golfhub_app.py")}

def save():
    (OUT / "cohort.json").write_text(json.dumps(report, indent=2) + "\n")

save()
timeouts = 0
for round_number in range(1, 11):
    order = ("pr13", "pr14") if round_number % 2 else ("pr14", "pr13")
    for label in order:
        name = f"round-{round_number:02d}-{label}"
        runtime = OUT / "runtime" / name
        runtime.mkdir(parents=True, exist_ok=False)
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", LOCALAPPDATA=str(runtime),
                   XDG_CACHE_HOME=str(runtime), TMP=str(runtime), TEMP=str(runtime),
                   PYTHONUNBUFFERED="1")
        command = [sys.executable, "-X", "faulthandler", str(HARNESS),
                   "--scenario", "cache_close", "--root", str(ROOTS[label])]
        item = {"round": round_number, "source": label, "command": command,
                "runtime": str(runtime), "started_utc": datetime.now(timezone.utc).isoformat()}
        started = time.monotonic()
        try:
            run = subprocess.run(command, cwd=ROOTS[label], env=env,
                                 capture_output=True, timeout=30)
            stdout, stderr = run.stdout, run.stderr
            item["exit_code"] = run.returncode
            item["outcome"] = "pass" if run.returncode == 0 else "error"
            records = [line.split(" ", 1)[1] for line in stdout.decode(errors="replace").splitlines()
                       if line.startswith("LIFECYCLE_RESULT ")]
            if len(records) == 1:
                evidence = json.loads(records[0])
                item["evidence"] = evidence
                valid = (evidence["scenario"] == "cache_close" and
                         evidence["worker_destroyed"] == evidence["thread_destroyed"] and
                         evidence["thread_destroyed"] > 0 and evidence["callback_errors"] == [] and
                         evidence["native_finish_checks"] == [])
                item["evidence_valid"] = valid
                if not valid:
                    item["outcome"] = "invalid_evidence"
            elif run.returncode == 0:
                item["outcome"] = "missing_evidence"
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.stdout or b"", error.stderr or b""
            timeouts += 1
            item.update(outcome="timeout", timeout=True)
        item["elapsed_seconds"] = round(time.monotonic() - started, 6)
        (OUT / (name + ".stdout.log")).write_bytes(stdout)
        (OUT / (name + ".stderr.log")).write_bytes(stderr)
        item["stdout_log"] = name + ".stdout.log"
        item["stderr_log"] = name + ".stderr.log"
        report["runs"].append(item)
        save()
        print(json.dumps({key: item[key] for key in ("round", "source", "outcome", "elapsed_seconds")}), flush=True)
        if timeouts > 3:
            break
    if timeouts > 3:
        break
report["finished_utc"] = datetime.now(timezone.utc).isoformat()
report["stopped_early"] = timeouts > 3
report["completed_invocations"] = len(report["runs"])
report["summary"] = {
    label: {outcome: sum(item["source"] == label and item["outcome"] == outcome for item in report["runs"])
            for outcome in sorted({item["outcome"] for item in report["runs"]})}
    for label in ROOTS
}
save()
print(json.dumps({key: report[key] for key in ("stopped_early", "completed_invocations", "summary")}), flush=True)
