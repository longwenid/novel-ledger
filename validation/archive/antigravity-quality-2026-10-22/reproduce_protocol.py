"""Read-only audit of source behavior; all projects are created in a temp directory.

Run against the audited release:
  python3 reproduce_protocol.py --repo /path/to/novel-ledger --output /tmp/protocol.json

Requires that repository's scripts/ and tests/support.py. This is a defect probe,
not an implementation or a claim that a future release should keep these results.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.repo.resolve()
    if not (root / "scripts/novel.py").is_file():
        parser.error("--repo must point to novel-ledger with scripts/ and tests/")
    sys.path[:0] = [str(root / "scripts"), str(root / "tests")]
    from novel_ledger.bootstrap import open_local_runtime
    from novel_ledger import store_keys
    from support import contract, drive, response

    env0 = {k: v for k, v in os.environ.items() if not k.startswith("NOVEL_")}

    def run(argv, env):
        result = subprocess.run(argv, env={**env0, **env}, text=True,
                                capture_output=True, timeout=20)
        try:
            data = json.loads(result.stdout)
        except ValueError:
            data = {"stdout": result.stdout, "stderr": result.stderr}
        return {"exit_code": result.returncode, "result": data}

    def view_for(task):
        return json.loads(Path(task["task_path"]).read_text(encoding="utf-8"))

    evidence = {}
    with tempfile.TemporaryDirectory(prefix="novel-quality-probe-") as temp:
        base = Path(temp)

        runtime = open_local_runtime(base / "replay", initialize=True, contract=contract(2))
        try:
            app = runtime.app
            task = drive(app, until="write")["task"]
            prepared = app.prepare_worker(task["task_id"], "host-context-A")
            view = view_for(task)
            receipt = response(app, session="host-context-A")
            receipt["session"] = ""
            receipt.pop("execution_claim", None)
            Path(view["result_path"]).write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
            first = run(view["commands"]["submit"], prepared["worker_env"])
            repeated = run(view["commands"]["submit"], prepared["worker_env"])
            canonical = app.submit(runtime.repo.task(task["task_id"])["result"])
            evidence["CR-01"] = {
                "first": first, "repeated": repeated, "canonical_api_replay": canonical,
                "chapter_count": len(runtime.repo.headers("main")),
                "defect_observed": first["exit_code"] == 0 and repeated["result"].get("error") == "stale_task",
            }
        finally:
            runtime.close()

        runtime = open_local_runtime(base / "materials", initialize=True, contract=contract(2))
        try:
            app = runtime.app
            task = drive(app, until="write")["task"]
            first_prepared = app.prepare_worker(task["task_id"], "host-context-A", seconds=1)
            view = view_for(task)
            old_read = run(view["commands"]["read"], first_prepared["worker_env"])
            time.sleep(1.1)
            resync = {"status": app.status(), "advance": app.advance(compact=True)}
            new_prepared = app.prepare_worker(task["task_id"], "host-context-B")
            new_read = run(view["commands"]["read"], new_prepared["worker_env"])
            explicit_all = run(view["commands"]["read"] + ["--all"], new_prepared["worker_env"])
            evidence["CR-02"] = {
                "old": old_read, "resync": resync, "new": new_read, "explicit_all": explicit_all,
                "defect_observed": bool(old_read["result"].get("records")) and not new_read["result"].get("records")
                    and bool(explicit_all["result"].get("records")),
            }
        finally:
            runtime.close()

        runtime = open_local_runtime(base / "retry", initialize=True, contract=contract(2))
        try:
            app = runtime.app
            task = drive(app, until="write")["task"]
            prepared = app.prepare_worker(task["task_id"], "host-context-A")
            view = view_for(task)
            cycles = []
            for _ in range(5):
                failure = run(view["commands"]["preflight"], prepared["worker_env"])
                reread = run(view["commands"]["read"], prepared["worker_env"])
                cycles.append({"failure": failure, "reread": reread,
                               "counter": runtime.repo.get(store_keys.technical_failure(task["task_id"]))})
            action = app.advance()["action"]
            evidence["AR-03"] = {
                "cycles": cycles, "final_action": action,
                "defect_observed": all(c["failure"]["exit_code"] == 2 and c["counter"] is None for c in cycles)
                    and action == "task_ready",
            }
        finally:
            runtime.close()

        runtime = open_local_runtime(base / "diagnostics", initialize=True, contract=contract(2))
        try:
            app = runtime.app
            drive(app, until="write")
            receipt = response(app)
            receipt["data"]["prose"] += (
                "他等了许久，窗外的雨沿着破损的玻璃往下流。值班室另一头有人收起了钥匙，"
                "走廊的灯熄了一盏，门后的脚步声渐渐远去。"
            )
            preview = app.submit(receipt, preview=True)
            submitted = app.submit(receipt)
            findings = runtime.repo.load()["draft"]["findings"]
            evidence["WF-04-current"] = {
                "preview": preview, "submitted": submitted, "stored_findings": findings,
                "defect_observed": bool(findings) and "findings" not in submitted
                    and submitted.get("committed_chapter") is None,
            }
        finally:
            runtime.close()

    result = {"repository": str(root), "temporary_projects_removed": True, "evidence": evidence}
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    print(json.dumps({k: v["defect_observed"] for k, v in evidence.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
