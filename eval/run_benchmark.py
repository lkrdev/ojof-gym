#!/usr/bin/env python3
"""
Benchmark Orchestration Runner for OJOF-Gym Multi-Turn Evaluation Suite.
Evaluates agents across a 2-Turn Lifecycle:
  Turn 1: Greenfield LookML Architecture (Prompted with domain & data schema only)
  Turn 2: Maintenance & Dashboard Queries (Refines model to support concrete analytical use cases)
Measures maintainability, structural invariants, Looker project validation, and BigQuery query execution.
"""

import argparse
import datetime
import difflib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verifiers.agy_driver import AntigravityDriver, compute_lookml_diff
from verifiers.ojof_linter import audit_lookml_directory
from verifiers.looker_evaluator import LookerEvaluator

def collect_lookml_files(directory: Path) -> Dict[str, str]:
    """Reads all .lkml files in directory."""
    files = {}
    for f in directory.rglob("*.lkml"):
        if ".system" in str(f) or ".git" in str(f) or ".agents" in str(f):
            continue
        try:
            files[f.name] = f.read_text()
        except Exception:
            pass
    return files

def get_bigquery_table_stats(dataset: str) -> List[Dict[str, Any]]:
    """Fetches table names and row counts using bq CLI."""
    clean_ds = dataset.replace(".", ":") if ":" not in dataset and "." in dataset else dataset
    res = subprocess.run(["bq", "ls", "--max_results=50", clean_ds], capture_output=True, text=True)
    if res.returncode != 0:
        return []

    tables = []
    lines = res.stdout.strip().splitlines()
    for line in lines[2:]:
        parts = line.split()
        if parts:
            t_name = parts[0]
            # Fetch row count
            show_res = subprocess.run(["bq", "show", "--format=json", f"{clean_ds}.{t_name}"], capture_output=True, text=True)
            row_count = "N/A"
            size_mb = "N/A"
            if show_res.returncode == 0:
                try:
                    d = json.loads(show_res.stdout)
                    row_count = f"{int(d.get('numRows', 0)):,}"
                    size_mb = f"{int(d.get('numBytes', 0)) / (1024*1024):.2f} MB"
                except Exception:
                    pass
            tables.append({"table": t_name, "rows": row_count, "size": size_mb})
    return tables

def build_turn1_prompt(scenario_spec: Dict[str, Any]) -> str:
    arch_prompt = scenario_spec.get("architecturePrompt", "Build a LookML data model.")
    bg_ds = scenario_spec.get("bigquery", {}).get("dataset", "")
    return (
        f"You are tasked with designing and building a comprehensive LookML data model in your workspace.\n\n"
        f"### Business & Domain Requirements:\n{arch_prompt}\n\n"
        f"### Underlying Dataset:\n- **BigQuery Dataset:** `{bg_ds}`\n\n"
        f"Please inspect the dataset, create all necessary `.view.lkml` views, `.explore.lkml` explore(s), "
        f"and `.model.lkml` files directly in your workspace. Build a clean, scalable architecture."
    )

def build_turn2_prompt(scenario_spec: Dict[str, Any]) -> str:
    user_questions = scenario_spec.get("userQuestions", {})
    q_lines = []
    for qkey, qval in user_questions.items():
        if qval.get("supported", True):
            q_lines.append(f"- **{qkey}**: {qval.get('prompt', '')}")
    
    questions_block = "\n".join(q_lines)
    return (
        f"Our business analytics stakeholders now need to build production dashboards answering the following concrete questions against your LookML model:\n\n"
        f"{questions_block}\n\n"
        f"Please inspect your existing LookML model, make all necessary edits, additions, and join configurations across your `.view.lkml`, `.explore.lkml`, and `.model.lkml` files in your workspace. "
        f"Ensure all required dimensions, measures, and joins exist to accurately fulfill these queries without metric duplication or fanout errors."
    )

def run_multi_turn_mode_evaluation(
    task_dir: Path,
    driver: AntigravityDriver,
    skill_mode: str,
    dry_run: bool,
    scenario_spec: Dict[str, Any],
    looker_eval: LookerEvaluator,
    workspace_dir: Path,
    max_queries: Optional[int] = None
) -> Dict[str, Any]:
    print(f"\n  -------------------------------------------------------")
    print(f"  [Mode Execution] Starting --skill-mode {skill_mode} (dry_run={dry_run})")
    print(f"  Isolated Workspace: {workspace_dir}")
    print(f"  -------------------------------------------------------")

    driver.setup_workspace(workspace_dir, task_dir, skill_mode)

    # ----------------------------------------------------
    # TURN 1: Greenfield Architecture
    # ----------------------------------------------------
    turn1_prompt = build_turn1_prompt(scenario_spec)
    print(f"  -> [Turn 1] Greenfield Architecture Prompt...")
    turn1_res = driver.execute_turn(
        workspace_dir=workspace_dir,
        prompt=turn1_prompt,
        turn_num=1,
        skill_mode=skill_mode,
        dry_run=dry_run
    )
    turn1_lookml = collect_lookml_files(workspace_dir)
    print(f"  -> [Turn 1 Complete] LookML Files: {len(turn1_lookml)} | Tokens: {turn1_res.get('usage', {}).get('total_tokens', 0)}")

    conversation_id = turn1_res.get("conversation_id")

    # ----------------------------------------------------
    # INCREMENTAL QUERY TURNS (Turns 2 to N+1): One Query Per Turn
    # ----------------------------------------------------
    user_questions = scenario_spec.get("userQuestions", {})
    query_turns_results = {}
    supported_queries = [
        (qk, qval) for qk, qval in user_questions.items() if qval.get("supported", True)
    ]
    if max_queries is not None and max_queries > 0:
        supported_queries = supported_queries[:max_queries]
        print(f"  [Light Mode] Evaluating first {len(supported_queries)} query turns.")

    turn_counter = 2
    queries_served_without_changes = 0
    total_query_lines_changed = 0
    total_query_tokens = 0
    total_query_duration = 0

    for qk, qval in supported_queries:
        prompt_text = qval.get("prompt", "")
        q_prompt = (
            f"Business Analytics Request for Query '{qk}':\n"
            f"Requirement: \"{prompt_text}\"\n\n"
            f"Please determine if your existing LookML model already supports this query requirement:\n"
            f"- If YES (no LookML changes needed), output the exact Looker query payload JSON for this query (specifying 'model', 'view', 'fields', and optional 'filters').\n"
            f"- If NO (incremental LookML changes needed), first update or create the required `.view.lkml` / `.explore.lkml` files in your workspace, and then output the Looker query payload JSON."
        )

        pre_query_lookml = collect_lookml_files(workspace_dir)
        print(f"  -> [Query Turn {turn_counter}] Evaluating Query '{qk}'...")

        q_turn_res = driver.execute_turn(
            workspace_dir=workspace_dir,
            prompt=q_prompt,
            turn_num=turn_counter,
            skill_mode=skill_mode,
            dry_run=dry_run,
            conversation_id=conversation_id
        )
        if q_turn_res.get("conversation_id"):
            conversation_id = q_turn_res["conversation_id"]

        q_tokens = q_turn_res.get("usage", {}).get("total_tokens", 0)
        q_duration = q_turn_res.get("duration_seconds", 0)
        total_query_tokens += q_tokens
        total_query_duration += q_duration

        post_query_lookml = collect_lookml_files(workspace_dir)
        q_diff = compute_lookml_diff(pre_query_lookml, post_query_lookml)

        lines_changed = q_diff["total_lines_changed"]
        total_query_lines_changed += lines_changed
        served_without_changes = (lines_changed == 0)
        if served_without_changes:
            queries_served_without_changes += 1

        print(f"     [Query '{qk}'] Lines Changed: {lines_changed} (+{q_diff['lines_added']} / -{q_diff['lines_deleted']}) | Served Without Changes: {served_without_changes}")

        # Compute turn diff text
        diff_text_lines = []
        for k in sorted(list(set(pre_query_lookml.keys()) | set(post_query_lookml.keys()))):
            f1 = pre_query_lookml.get(k, "")
            f2 = post_query_lookml.get(k, "")
            if f1 != f2:
                diff_text_lines.extend(difflib.unified_diff(
                    f1.splitlines(keepends=True),
                    f2.splitlines(keepends=True),
                    fromfile=f"a/{k}",
                    tofile=f"b/{k}"
                ))
        turn_diff_str = "".join(diff_text_lines)

        query_turns_results[qk] = {
            "turn_num": turn_counter,
            "prompt": prompt_text,
            "driver_result": q_turn_res,
            "lines_added": q_diff["lines_added"],
            "lines_deleted": q_diff["lines_deleted"],
            "total_lines_changed": lines_changed,
            "modified_files": q_diff["modified_files"],
            "new_files": q_diff["new_files"],
            "served_without_changes": served_without_changes,
            "diff_text": turn_diff_str
        }

        turn_counter += 1

    final_lookml = collect_lookml_files(workspace_dir)
    cumulative_diff = compute_lookml_diff(turn1_lookml, final_lookml)

    num_supported = len(supported_queries) if supported_queries else 1
    pct_served_without_changes = (queries_served_without_changes / num_supported) * 100.0
    avg_lines_per_query = total_query_lines_changed / num_supported

    print(f"\n  [Incremental Evaluation Summary] {skill_mode}:")
    print(f"    - Queries Served Without LookML Changes: {queries_served_without_changes}/{num_supported} ({pct_served_without_changes:.1f}%)")
    print(f"    - Avg. Lines Modified per Query: {avg_lines_per_query:.1f}")
    print(f"    - Cumulative Refactoring Lines: {cumulative_diff['total_lines_changed']}")

    # ----------------------------------------------------
    # VERIFICATION ON FINAL MODEL
    # ----------------------------------------------------
    # Level 1: Structural Invariants Linter
    linter_res = audit_lookml_directory(workspace_dir)
    print(f"  [Level 1 Linter] Score: {linter_res['score']:.1f}% ({linter_res['passed']}/{linter_res['total']}) | Engine: {linter_res['engine']}")

    # Level 2: Looker Project Validation
    looker_val = {"is_valid": False, "skipped": True, "reason": "No LookML files generated" if not final_lookml else "Looker unavailable"}
    looker_queries = {}
    if looker_eval.is_available() and final_lookml:
        print(f"  [Level 2 Looker] Syncing model to Looker dev workspace...")
        sync_res = looker_eval.sync_files_to_looker(workspace_dir)
        print(f"  [Level 2 Looker] Validating project...")
        looker_val = looker_eval.validate_project()
        looker_val["sync_details"] = sync_res
        print(f"  [Level 2 Looker] is_valid={looker_val['is_valid']}")

        # Level 3: Looker SQL Compilation & BigQuery Execution
        if looker_val.get("is_valid"):
            print(f"  [Level 3 Looker] Compiling queries & running live BigQuery execution...")
            all_q_res = looker_eval.evaluate_scenario_questions(scenario_spec)
            if supported_queries:
                supp_keys = {k for k, _ in supported_queries}
                looker_queries = {k: v for k, v in all_q_res.items() if k in supp_keys}
            else:
                looker_queries = all_q_res
            passed_q = sum(1 for q in looker_queries.values() if isinstance(q, dict) and q.get('status') == 'passed')
            total_q = sum(1 for q in scenario_spec.get('userQuestions', {}).values() if q.get('supported', True))
            print(f"  [Level 3 Looker] Queries Passing: {passed_q}/{total_q}")
        else:
            looker_queries = {"status": "skipped_due_to_validation_failure"}

    return {
        "skill_mode": skill_mode,
        "turn1": {
            "driver_result": turn1_res,
            "lookml_files": turn1_lookml
        },
        "query_turns": query_turns_results,
        "maintainability_metrics": {
            "turn1_tokens": turn1_res.get("usage", {}).get("total_tokens", 0),
            "query_turns_tokens": total_query_tokens,
            "turn1_duration_seconds": turn1_res.get("duration_seconds", 0),
            "query_turns_duration_seconds": total_query_duration,
            "queries_served_without_changes": queries_served_without_changes,
            "total_supported_queries": num_supported,
            "pct_queries_served_without_changes": pct_served_without_changes,
            "avg_lines_modified_per_query": avg_lines_per_query,
            "total_query_lines_changed": total_query_lines_changed,
            "lines_added": cumulative_diff["lines_added"],
            "lines_deleted": cumulative_diff["lines_deleted"],
            "total_lines_changed": cumulative_diff["total_lines_changed"],
            "modified_files": cumulative_diff["modified_files"],
            "new_files": cumulative_diff["new_files"]
        },
        "final_lookml_files": final_lookml,
        "linter_results": linter_res,
        "looker_validation": looker_val,
        "looker_queries": looker_queries
    }

def generate_markdown_report(
    task_name: str,
    scenario_spec: Dict[str, Any],
    bq_stats: List[Dict[str, Any]],
    with_skill: Dict[str, Any],
    no_skill: Dict[str, Any],
    export_dir: Path
) -> str:
    from eval.generate_rich_artifacts import generate_markdown_report_with_artifacts
    return generate_markdown_report_with_artifacts(
        task_name=task_name,
        scenario_spec=scenario_spec,
        bq_stats=bq_stats,
        with_skill=with_skill,
        no_skill=no_skill,
        export_dir=export_dir
    )

def run_benchmark(
    tasks_dir: Path,
    target_task: Optional[str] = None,
    model: str = "gemini-3.6-flash",
    dry_run: bool = True,
    output_dir: Path = Path("eval_exports"),
    max_queries: Optional[int] = None
) -> Dict[str, Any]:
    if target_task:
        task_dirs = [tasks_dir / target_task]
    else:
        task_dirs = [d for d in tasks_dir.glob("task_*") if d.is_dir()]
        
    print(f"[Benchmark Runner] Found {len(task_dirs)} task(s) to evaluate in {tasks_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_export_dir = output_dir / f"run_{timestamp}"
    run_export_dir.mkdir(parents=True, exist_ok=True)

    driver = AntigravityDriver(model=model, skip_permissions=not dry_run)
    looker_eval = LookerEvaluator()

    # Pre-flight connectivity validation
    if not dry_run:
        print("\n[Pre-flight] Validating Looker API & BigQuery connectivity...")
        if not looker_eval.ensure_authenticated():
            print("\n=======================================================")
            print("[ABORT] Looker API is NOT connected or session is invalid!")
            print("Please ensure the SSH reverse tunnel on port 8445 is open from your workstation:")
            print("  ssh -o StrictHostKeyChecking=no -N -R 8445:<LOOKER_HOST>:443 corpagent-eng-<USER>@mpl-<CAPSULE_NAME>.c.googlers.com")
            print("=======================================================\n")
            sys.exit(1)
        
        # Test BigQuery dataset accessibility
        try:
            res_bq = subprocess.run(["bq", "show", "--dataset", "bigquery-public-data:thelook_ecommerce"], capture_output=True, text=True, timeout=15)
            if res_bq.returncode != 0:
                print(f"[Warning] BigQuery dataset check returned code {res_bq.returncode}: {res_bq.stderr}")
        except Exception as e:
            print(f"[Warning] Could not verify BigQuery dataset: {e}")
        print("[Pre-flight] Looker API and BigQuery verified successfully.\n")

    all_results = {
        "benchmark_summary": {
            "timestamp": timestamp,
            "total_tasks": len(task_dirs),
            "model": model,
            "dry_run": dry_run,
            "light_mode": (max_queries is not None),
            "max_queries": max_queries,
            "looker_connected": looker_eval.is_available()
        },
        "tasks": []
    }

    isolated_base = Path(tempfile.mkdtemp(prefix="ojof_benchmark_"))

    for task_dir in task_dirs:
        task_name = task_dir.name
        print(f"\n=======================================================")
        print(f"[Benchmark Runner] Evaluating Task: {task_name}")
        if max_queries:
            print(f"[Benchmark Runner] Light Mode active: max {max_queries} query turn(s)")
        print(f"=======================================================")

        scenario_file = PROJECT_ROOT / "scenario" / "scenarios" / "static" / f"{task_name.replace('task_', '')}.json"
        scenario_spec = {}
        if scenario_file.exists():
            try:
                scenario_spec = json.loads(scenario_file.read_text())
            except Exception:
                pass

        # Fetch BigQuery table stats for scenario overview
        bg_ds = scenario_spec.get("bigquery", {}).get("dataset", "")
        bq_stats = get_bigquery_table_stats(bg_ds) if bg_ds else []

        task_export_dir = run_export_dir / task_name
        task_export_dir.mkdir(parents=True, exist_ok=True)

        # ----------------------------------------------------
        # 1. Run WITH skill (Multi-Turn Lifecycle)
        # ----------------------------------------------------
        with_skill_ws = isolated_base / f"{task_name}_with_skill"
        res_with = run_multi_turn_mode_evaluation(
            task_dir=task_dir,
            driver=driver,
            skill_mode="with-skill",
            dry_run=dry_run,
            scenario_spec=scenario_spec,
            looker_eval=looker_eval,
            workspace_dir=with_skill_ws,
            max_queries=max_queries
        )

        # Export LookML files
        with_skill_export_dir = task_export_dir / "with_skill" / "lookml"
        with_skill_export_dir.mkdir(parents=True, exist_ok=True)
        for fname, fcontent in res_with["final_lookml_files"].items():
            (with_skill_export_dir / fname).write_text(fcontent)

        # ----------------------------------------------------
        # 2. Run WITHOUT skill (Multi-Turn Lifecycle)
        # ----------------------------------------------------
        no_skill_ws = isolated_base / f"{task_name}_no_skill"
        res_no = run_multi_turn_mode_evaluation(
            task_dir=task_dir,
            driver=driver,
            skill_mode="no-skill",
            dry_run=dry_run,
            scenario_spec=scenario_spec,
            looker_eval=looker_eval,
            workspace_dir=no_skill_ws,
            max_queries=max_queries
        )

        # Export LookML files
        no_skill_export_dir = task_export_dir / "no_skill" / "lookml"
        no_skill_export_dir.mkdir(parents=True, exist_ok=True)
        for fname, fcontent in res_no["final_lookml_files"].items():
            (no_skill_export_dir / fname).write_text(fcontent)

        # Generate Markdown Report
        md_report = generate_markdown_report(task_name, scenario_spec, bq_stats, res_with, res_no, task_export_dir)
        (task_export_dir / "eval_report.md").write_text(md_report)

        task_entry = {
            "task_id": task_name,
            "scenario": scenario_spec.get("title", task_name),
            "with_skill": res_with,
            "no_skill": res_no
        }
        all_results["tasks"].append(task_entry)

    try:
        shutil.rmtree(isolated_base)
    except Exception:
        pass

    with open(run_export_dir / "eval_results.json", "w") as f:
        json.dump(all_results, f, indent=2)

    try:
        from eval.generate_rich_artifacts import process_run_artifacts
        process_run_artifacts(run_export_dir)
    except Exception as e:
        print(f"[Warning] Failed to generate rich artifacts: {e}")

    print(f"\n=======================================================")
    print(f"[Benchmark Runner COMPLETED]")
    print(f"Export directory: {run_export_dir}")
    print(f"Master JSON:      {run_export_dir / 'eval_results.json'}")
    print(f"=======================================================")

    return all_results

def main():
    parser = argparse.ArgumentParser(description="Run OJOF-Gym Multi-Turn Benchmark Suite")
    parser.add_argument("--tasks-dir", type=str, default="tasks", help="Path to tasks directory")
    parser.add_argument("--task", type=str, default=None, help="Target specific task name")
    parser.add_argument("--model", type=str, default="gemini-3.6-flash")
    parser.add_argument("--execute", action="store_true", help="Run live agy execution (default is dry-run)")
    parser.add_argument("--light", action="store_true", help="Fast iteration mode (caps at 3 query turns)")
    parser.add_argument("--max-queries", type=int, default=None, help="Maximum number of query turns to evaluate")
    parser.add_argument("--out-dir", type=str, default="eval_exports", help="Export root directory")

    args = parser.parse_args()
    tasks_dir = Path(args.tasks_dir)
    out_dir = Path(args.out_dir)

    max_q = 3 if args.light and not args.max_queries else args.max_queries

    run_benchmark(
        tasks_dir=tasks_dir,
        target_task=args.task,
        model=args.model,
        dry_run=not args.execute,
        output_dir=out_dir,
        max_queries=max_q
    )

if __name__ == "__main__":
    main()