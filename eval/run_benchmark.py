#!/usr/bin/env python3
"""
Benchmark Orchestration Runner for OJOF-Gym evaluation suite.
Runs compiled tasks with Antigravity CLI driver across skill modes and produces comparative scorecards.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verifiers.agy_driver import AntigravityDriver
from verifiers.ojof_linter import audit_lookml_directory

def run_task_verification(task_dir: Path) -> Dict[str, Any]:
    verifier_script = task_dir / "verifier" / "test_outputs.py"
    if not verifier_script.exists():
        return {"status": "missing_verifier", "score": 0.0}

    try:
        res = subprocess.run([sys.executable, str(verifier_script)], capture_output=True, text=True, check=True)
        linter_data = audit_lookml_directory(task_dir)
        return {
            "status": "passed",
            "linter_score": linter_data["score"],
            "stdout": res.stdout
        }
    except subprocess.CalledProcessError as e:
        linter_data = audit_lookml_directory(task_dir)
        return {
            "status": "failed",
            "linter_score": linter_data["score"],
            "error": e.stderr or e.stdout
        }

def run_benchmark(
    tasks_dir: Path,
    model: str = "gemini-3.6-flash",
    dry_run: bool = True,
    output_report: Path = Path("eval_results.json")
) -> Dict[str, Any]:
    task_dirs = [d for d in tasks_dir.glob("task_*") if d.is_dir()]
    print(f"[Benchmark Runner] Found {len(task_dirs)} compiled tasks in {tasks_dir}")

    driver = AntigravityDriver(model=model, skip_permissions=not dry_run)
    results = {
        "benchmark_summary": {
            "total_tasks": len(task_dirs),
            "model": model,
            "dry_run": dry_run
        },
        "tasks": []
    }

    for task_dir in task_dirs:
        task_name = task_dir.name
        print(f"\n[Benchmark Runner] Evaluating task: {task_name}")

        task_md = task_dir / "task.md"
        prompt = task_md.read_text() if task_md.exists() else "Build an OJOF multi-fact explore."

        # 1. Run WITH skill
        print(f"  -> Running --skill-mode with-skill...")
        res_with = driver.run_task(task_dir, prompt=prompt, skill_mode="with-skill", dry_run=dry_run)
        verif_with = run_task_verification(task_dir)

        # 2. Run WITHOUT skill
        print(f"  -> Running --skill-mode no-skill...")
        res_no = driver.run_task(task_dir, prompt=prompt, skill_mode="no-skill", dry_run=dry_run)
        verif_no = run_task_verification(task_dir)

        task_entry = {
            "task_id": task_name,
            "with_skill": {
                "driver_result": res_with,
                "verification": verif_with
            },
            "no_skill": {
                "driver_result": res_no,
                "verification": verif_no
            }
        }
        results["tasks"].append(task_entry)

    with open(output_report, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n[Benchmark Runner SUCCESS] Report saved to {output_report}")
    return results

def main():
    parser = argparse.ArgumentParser(description="Run OJOF-Gym Benchmark Suite")
    parser.add_argument("--tasks-dir", type=str, default="tasks", help="Path to tasks directory")
    parser.add_argument("--model", type=str, default="gemini-3.6-flash")
    parser.add_argument("--execute", action="store_true", help="Run live agy execution (default is dry-run)")
    parser.add_argument("--out", type=str, default="eval_results.json", help="Output report JSON file")

    args = parser.parse_args()
    tasks_dir = Path(args.tasks_dir)
    out_report = Path(args.out)

    run_benchmark(
        tasks_dir=tasks_dir,
        model=args.model,
        dry_run=not args.execute,
        output_report=out_report
    )

if __name__ == "__main__":
    main()
