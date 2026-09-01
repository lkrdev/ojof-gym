#!/usr/bin/env python3
"""
Re-evaluates and regenerates benchmark reports from saved run artifacts
WITHOUT re-running the expensive LLM agentic execution.
"""

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.generate_rich_artifacts import generate_markdown_report_with_artifacts as generate_markdown_report

def get_bigquery_table_stats(dataset: str) -> list:
    return []
from verifiers.ojof_linter import audit_lookml_directory
from verifiers.looker_evaluator import LookerEvaluator

def get_latest_run_dir(exports_base: Path) -> Path:
    runs = sorted([d for d in exports_base.glob("run_*") if d.is_dir()])
    if not runs:
        raise FileNotFoundError(f"No run exports found in {exports_base}")
    return runs[-1]

def rebuild_run_report(
    run_dir: Path,
    re_verify_looker: bool = True
):
    print(f"[Report Rebuilder] Rebuilding report from saved artifacts in: {run_dir}")
    master_results = {"tasks": []}
    if eval_json_path.exists() and eval_json_path.stat().st_size > 0:
        try:
            with open(eval_json_path) as f:
                master_results = json.load(f)
        except Exception as e:
            print(f"  [Warning] Could not parse {eval_json_path}: {e}")

    if not master_results.get("tasks"):
        # Auto-discover task folders
        for td in sorted(run_dir.glob("task_*")):
            if td.is_dir():
                master_results["tasks"].append({
                    "task_id": td.name,
                    "with_skill": {},
                    "no_skill": {}
                })

    looker_eval = LookerEvaluator() if re_verify_looker else None

    for task_data in master_results.get("tasks", []):
        task_id = task_data["task_id"]
        task_dir = run_dir / task_id
        print(f"  -> Processing task: {task_id}")

        scenario_name = task_id.replace("task_", "")
        scenario_file = PROJECT_ROOT / "scenario" / "scenarios" / "static" / f"{scenario_name}.json"
        scenario_spec = {}
        if scenario_file.exists():
            try:
                scenario_spec = json.loads(scenario_file.read_text())
            except Exception:
                pass

        bg_ds = scenario_spec.get("bigquery", {}).get("dataset", "")
        bq_stats = get_bigquery_table_stats(bg_ds) if bg_ds else []

        with_skill_ws = task_dir / "with_skill" / "lookml"
        no_skill_ws = task_dir / "no_skill" / "lookml"

        # Re-run structural linter
        if with_skill_ws.exists():
            task_data["with_skill"]["linter_results"] = audit_lookml_directory(with_skill_ws)
        if no_skill_ws.exists():
            task_data["no_skill"]["linter_results"] = audit_lookml_directory(no_skill_ws)

        # Optional Looker & BigQuery re-verification
        if looker_eval and looker_eval.is_available():
            if with_skill_ws.exists():
                print("     Re-evaluating with-skill on Looker...")
                looker_eval.sync_files_to_looker(with_skill_ws)
                task_data["with_skill"]["looker_validation"] = looker_eval.validate_project()
                if task_data["with_skill"]["looker_validation"].get("is_valid"):
                    task_data["with_skill"]["looker_queries"] = looker_eval.evaluate_scenario_questions(scenario_spec)

            if no_skill_ws.exists():
                print("     Re-evaluating no-skill on Looker...")
                looker_eval.sync_files_to_looker(no_skill_ws)
                task_data["no_skill"]["looker_validation"] = looker_eval.validate_project()
                if task_data["no_skill"]["looker_validation"].get("is_valid"):
                    task_data["no_skill"]["looker_queries"] = looker_eval.evaluate_scenario_questions(scenario_spec)

        # Regenerate HTML and Markdown Report
        report_content = generate_markdown_report(
            task_name=task_id,
            scenario_spec=scenario_spec,
            bq_stats=bq_stats,
            with_skill=task_data["with_skill"],
            no_skill=task_data["no_skill"],
            export_dir=task_dir
        )
        report_file_md = task_dir / "eval_report.md"
        report_file_md.write_text(report_content)
        report_file_html = task_dir / "eval_report.html"
        report_file_html.write_text(report_content)
        print(f"  [OK] Saved updated reports: {report_file_html} and {report_file_md}")

        artifact_dir = os.environ.get("ARTIFACT_DIR")
        if artifact_dir and Path(artifact_dir).exists():
            art_file_md = Path(artifact_dir) / f"{scenario_name}_evaluation_report.md"
            art_file_md.write_text(report_content)
            art_file_html = Path(artifact_dir) / f"{scenario_name}_evaluation_report.html"
            art_file_html.write_text(report_content)
            print(f"  [OK] Exported to artifact directory: {art_file_html}")

    # Save updated master JSON
    with open(eval_json_path, "w") as f:
        json.dump(master_results, f, indent=2)
    print(f"[Report Rebuilder] Master JSON updated: {eval_json_path}")

def main():
    parser = argparse.ArgumentParser(description="Rebuild Benchmark Reports from Persisted Run Exports")
    parser.add_argument("run_dir", nargs="?", default=None, help="Path to run export dir (default: latest run in eval_exports/)")
    parser.add_argument("--no-looker", action="store_true", help="Skip live Looker API verification (instant regeneration)")
    args = parser.parse_args()

    exports_base = PROJECT_ROOT / "eval_exports"
    if args.run_dir:
        target_dir = Path(args.run_dir)
    else:
        target_dir = get_latest_run_dir(exports_base)

    rebuild_run_report(target_dir, re_verify_looker=not args.no_looker)

if __name__ == "__main__":
    main()
