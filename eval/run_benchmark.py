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
    workspace_dir: Path
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

    # ----------------------------------------------------
    # TURN 2: Dashboard Maintenance & Extension
    # ----------------------------------------------------
    turn2_prompt = build_turn2_prompt(scenario_spec)
    print(f"  -> [Turn 2] Dashboard Queries Maintenance Prompt...")
    turn2_res = driver.execute_turn(
        workspace_dir=workspace_dir,
        prompt=turn2_prompt,
        turn_num=2,
        skill_mode=skill_mode,
        dry_run=dry_run,
        conversation_id=turn1_res.get("conversation_id")
    )
    turn2_lookml = collect_lookml_files(workspace_dir)
    print(f"  -> [Turn 2 Complete] LookML Files: {len(turn2_lookml)} | Tokens: {turn2_res.get('usage', {}).get('total_tokens', 0)}")

    # Diff metrics between Turn 1 and Turn 2
    diff_metrics = compute_lookml_diff(turn1_lookml, turn2_lookml)
    print(f"  -> [Refactoring Friction] Lines Changed: {diff_metrics['total_lines_changed']} (+{diff_metrics['lines_added']} / -{diff_metrics['lines_deleted']}) across {len(diff_metrics['modified_files'])} modified files")

    # ----------------------------------------------------
    # VERIFICATION ON FINAL MODEL (Turn 2)
    # ----------------------------------------------------
    # Level 1: Structural Invariants Linter
    linter_res = audit_lookml_directory(workspace_dir)
    print(f"  [Level 1 Linter] Score: {linter_res['score']:.1f}% ({linter_res['passed']}/{linter_res['total']}) | Engine: {linter_res['engine']}")

    # Level 2: Looker Project Validation
    looker_val = {"is_valid": False, "skipped": True, "reason": "No LookML files generated" if not turn2_lookml else "Looker unavailable"}
    looker_queries = {}
    if looker_eval.is_available() and turn2_lookml:
        print(f"  [Level 2 Looker] Syncing model to Looker dev workspace...")
        sync_res = looker_eval.sync_files_to_looker(workspace_dir)
        print(f"  [Level 2 Looker] Validating project...")
        looker_val = looker_eval.validate_project()
        looker_val["sync_details"] = sync_res
        print(f"  [Level 2 Looker] is_valid={looker_val['is_valid']}")

        # Level 3: Looker SQL Compilation & BigQuery Execution
        if looker_val.get("is_valid"):
            print(f"  [Level 3 Looker] Compiling queries & running live BigQuery execution...")
            looker_queries = looker_eval.evaluate_scenario_questions(scenario_spec)
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
        "turn2": {
            "driver_result": turn2_res,
            "lookml_files": turn2_lookml
        },
        "maintainability_metrics": {
            "turn1_tokens": turn1_res.get("usage", {}).get("total_tokens", 0),
            "turn2_tokens": turn2_res.get("usage", {}).get("total_tokens", 0),
            "turn1_duration_seconds": turn1_res.get("duration_seconds", 0),
            "turn2_duration_seconds": turn2_res.get("duration_seconds", 0),
            "lines_added": diff_metrics["lines_added"],
            "lines_deleted": diff_metrics["lines_deleted"],
            "total_lines_changed": diff_metrics["total_lines_changed"],
            "modified_files": diff_metrics["modified_files"],
            "new_files": diff_metrics["new_files"]
        },
        "final_lookml_files": turn2_lookml,
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
    lines = []
    lines.append(f"# Benchmark Evaluation Report: {scenario_spec.get('title', task_name)}")
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    lines.append(f"**Generated:** `{now_utc}`  ")
    lines.append(f"**Task ID:** `{task_name}`  ")
    lines.append(f"**Target Dataset:** `{scenario_spec.get('bigquery', {}).get('dataset', 'N/A')}`\n")

    # ------------------------------------------------------------------
    # SECTION 1: SCENARIO CONTEXT
    # ------------------------------------------------------------------
    lines.append("## 1. Scenario Context & Dataset Overview\n")
    lines.append(f"**Description:** {scenario_spec.get('description', '')}\n")
    lines.append("### Architecture Requirements Prompt")
    lines.append(f"> {scenario_spec.get('architecturePrompt', '').replace(chr(10), chr(10) + '> ')}\n")

    lines.append("### Underlying BigQuery Tables & Schema Scale")
    if bq_stats:
        lines.append("| Table Name | Row Count | Storage Size |")
        lines.append("| :--- | :--- | :--- |")
        for s in bq_stats:
            lines.append(f"| `{s['table']}` | **{s['rows']}** | {s['size']} |")
    else:
        lines.append(f"*(BigQuery dataset `{scenario_spec.get('bigquery', {}).get('dataset')}` statistics)*")
    lines.append("\n")

    lines.append("### Target Business Dashboard Queries")
    user_questions = scenario_spec.get("userQuestions", {})
    lines.append("| Query Key | Prompt / Business Goal | Expected Participating Columns |")
    lines.append("| :--- | :--- | :--- |")
    for qk, qv in user_questions.items():
        if qv.get("supported", True):
            cols = ", ".join([f"`{c}`" for c in qv.get("expectation", {}).get("participatingColumns", [])])
            lines.append(f"| **{qk}** | {qv.get('prompt', '')} | {cols} |")
    lines.append("\n---\n")

    # ------------------------------------------------------------------
    # SECTION 2: EXECUTIVE SCORECARD
    # ------------------------------------------------------------------
    lines.append("## 2. Executive Scorecard\n")
    lines.append("| Metric / Evaluation Dimension | With Skill (`lookml-ojof`) | Baseline (No Skill) | Improvement / Delta |")
    lines.append("| :--- | :--- | :--- | :--- |")

    # Level 1 Linter
    l_with = with_skill['linter_results']['score']
    l_no = no_skill['linter_results']['score']
    l_diff = l_with - l_no
    lines.append(f"| **Level 1: Structural Invariants (Static Linter)** | **{l_with:.1f}%** ({with_skill['linter_results']['passed']}/{with_skill['linter_results']['total']}) | **{l_no:.1f}%** ({no_skill['linter_results']['passed']}/{no_skill['linter_results']['total']}) | **{('+' if l_diff >= 0 else '')}{l_diff:.1f}%** |")

    # Level 2 Looker Validation
    v_with = "Passed" if with_skill['looker_validation'].get('is_valid') else "Failed / Skipped"
    v_no = "Passed" if no_skill['looker_validation'].get('is_valid') else "Failed / Skipped"
    v_diff = "+1 Tier" if (v_with == "Passed" and v_no != "Passed") else "Parity"
    lines.append(f"| **Level 2: Looker Project Validation** | **{v_with}** | **{v_no}** | **{v_diff}** |")

    # Level 3 Query SQL & Execution
    q_with_pass = sum(1 for q in with_skill['looker_queries'].values() if isinstance(q, dict) and q.get('status') == 'passed')
    q_no_pass = sum(1 for q in no_skill['looker_queries'].values() if isinstance(q, dict) and q.get('status') == 'passed')
    total_q = sum(1 for q in scenario_spec.get('userQuestions', {}).values() if q.get('supported', True))
    q_diff = f"+{q_with_pass - q_no_pass}" if q_with_pass >= q_no_pass else f"{q_with_pass - q_no_pass}"
    lines.append(f"| **Level 3: Query SQL & BigQuery Execution** | **{q_with_pass}/{total_q} Passed** | **{q_no_pass}/{total_q} Passed** | **{q_diff} Passed** |")

    # Maintainability: Turn 2 Line Diff
    m_with = with_skill['maintainability_metrics']
    m_no = no_skill['maintainability_metrics']
    lines.append(f"| **Turn 2 Maintenance: Lines Changed** | **{m_with['total_lines_changed']} lines** (+{m_with['lines_added']} / -{m_with['lines_deleted']}) | **{m_no['total_lines_changed']} lines** (+{m_no['lines_added']} / -{m_no['lines_deleted']}) | {m_with['total_lines_changed'] - m_no['total_lines_changed']} lines |")
    lines.append(f"| **Total Token Consumption (Turns 1 + 2)** | **{m_with['turn1_tokens'] + m_with['turn2_tokens']:,} tokens** | **{m_no['turn1_tokens'] + m_no['turn2_tokens']:,} tokens** | {(m_with['turn1_tokens'] + m_with['turn2_tokens']) - (m_no['turn1_tokens'] + m_no['turn2_tokens']):,} tokens |")
    lines.append("\n---\n")

    # ------------------------------------------------------------------
    # SECTION 3: STRUCTURAL INVARIANT LINTER COMPARISON (SIDE-BY-SIDE)
    # ------------------------------------------------------------------
    lines.append("## 3. Structural Invariant Linter Breakdown (Pattern/Regex Static Analysis)\n")
    s_with = with_skill['linter_results']['structural_metrics']
    s_no = no_skill['linter_results']['structural_metrics']

    lines.append("| Structural Component | With Skill (`lookml-ojof`) | Baseline (No Skill) | Description |")
    lines.append("| :--- | :--- | :--- | :--- |")
    lines.append(f"| **OJOF Explores (`from: none`)** | **{s_with['ojof_explores']}** | **{s_no['ojof_explores']}** | Zero-row base table avoids single-base grain bias |")
    lines.append(f"| **Fact Joins (`full_outer` / `sql_on: FALSE`)** | **{s_with['fact_joins_count']}** | **{s_no['fact_joins_count']}** | Disconnects fact streams to prevent cartesian fanout |")
    lines.append(f"| **Liquid Dynamic Dimension Joins (`_in_query`)** | **{s_with['liquid_dimension_joins_count']}** | **{s_no['liquid_dimension_joins_count']}** | Prunes dimension joins strictly to active query facts |")
    lines.append(f"| **Composite Measure Views / Bare Joins** | **{s_with['composite_measure_views_count']}** | **{s_no['composite_measure_views_count']}** | Isolates cross-fact ratios without join side-effects |")
    lines.append(f"| **Total LookML Files Generated** | **{s_with['total_lkml_files']} files** | **{s_no['total_lkml_files']} files** | Modular file decomposition |")
    lines.append("\n")

    lines.append("### Linter Rule Diagnostics")
    lines.append("<details>\n<summary>Click to view detailed rule-by-rule pass/fail checklist</summary>\n")
    lines.append("#### With Skill (`lookml-ojof`):")
    if with_skill['linter_results']['violations']:
        for v in with_skill['linter_results']['violations']:
            lines.append(f"- ❌ {v}")
    else:
        lines.append("- ✅ All 4 structural invariants satisfied!")

    lines.append("\n#### Baseline (No Skill):")
    if no_skill['linter_results']['violations']:
        for v in no_skill['linter_results']['violations']:
            lines.append(f"- ❌ {v}")
    else:
        lines.append("- ✅ All 4 structural invariants satisfied!")
    lines.append("\n</details>\n\n---\n")

    # ------------------------------------------------------------------
    # SECTION 4: MAINTAINABILITY & REFACTORING FRICTION (TURN 1 -> TURN 2)
    # ------------------------------------------------------------------
    lines.append("## 4. Model Maintainability & Refactoring Friction\n")
    lines.append("Comparing the effort required to extend the greenfield model (Turn 1) to satisfy new dashboard queries (Turn 2):\n")

    lines.append("| Maintenance Metric | With Skill (`lookml-ojof`) | Baseline (No Skill) | Analysis |")
    lines.append("| :--- | :--- | :--- | :--- |")
    lines.append(f"| **Turn 1 Initial Tokens** | `{m_with['turn1_tokens']:,}` | `{m_no['turn1_tokens']:,}` | Initial architecture synthesis |")
    lines.append(f"| **Turn 2 Maintenance Tokens** | `{m_with['turn2_tokens']:,}` | `{m_no['turn2_tokens']:,}` | Query extension reasoning |")
    lines.append(f"| **Lines Added in Turn 2** | `+{m_with['lines_added']}` | `+{m_no['lines_added']}` | Added dimensions, measures, joins |")
    lines.append(f"| **Lines Deleted in Turn 2** | `-{m_with['lines_deleted']}` | `-{m_no['lines_deleted']}` | Rework / removal of invalid code |")
    lines.append(f"| **Total Lines Refactored** | **{m_with['total_lines_changed']} lines** | **{m_no['total_lines_changed']} lines** | Lower indicates higher model flexibility |")
    lines.append(f"| **Files Modified in Turn 2** | `{len(m_with['modified_files'])} files` ({', '.join(m_with['modified_files']) or 'None'}) | `{len(m_no['modified_files'])} files` ({', '.join(m_no['modified_files']) or 'None'}) | Blast radius of changes |")
    lines.append("\n---\n")

    # ------------------------------------------------------------------
    # SECTION 5: TARGET QUERY PERFORMANCE & COMPILED SQL (SIDE-BY-SIDE)
    # ------------------------------------------------------------------
    lines.append("## 5. Target Query Execution & Performance Comparison\n")
    lines.append("| Target Query Key | With-Skill Status | With-Skill Latency | Baseline Status | Baseline Latency | Columns Participating |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

    for qk, qv in user_questions.items():
        if not qv.get("supported", True):
            continue
        qw = with_skill['looker_queries'].get(qk, {})
        qn = no_skill['looker_queries'].get(qk, {})
        
        st_w = "✅ Passed" if qw.get("status") == "passed" else "❌ Failed"
        lat_w = f"{qw.get('execution_performance', {}).get('latency_ms', 'N/A')} ms" if qw.get('status') == 'passed' else "N/A"
        
        st_n = "✅ Passed" if qn.get("status") == "passed" else "❌ Failed"
        lat_n = f"{qn.get('execution_performance', {}).get('latency_ms', 'N/A')} ms" if qn.get('status') == 'passed' else "N/A"
        
        col_w = "All (100%)" if not qw.get("missing_columns") else f"Missing {len(qw.get('missing_columns'))}"
        lines.append(f"| **`{qk}`** | **{st_w}** | {lat_w} | **{st_n}** | {lat_n} | {col_w} |")

    lines.append("\n### Detailed Query SQL & BigQuery Execution Logs\n")
    for qk, qv in user_questions.items():
        if not qv.get("supported", True):
            continue
        qw = with_skill['looker_queries'].get(qk, {})
        qn = no_skill['looker_queries'].get(qk, {})

        lines.append(f"<details>\n<summary><b>Query: {qk}</b> ({qv.get('prompt', '')})</summary>\n")
        lines.append(f"**Expected Columns:** `{', '.join(qv.get('expectation', {}).get('participatingColumns', []))}`\n")
        
        lines.append("#### With Skill (`lookml-ojof`) Compiled SQL:")
        if qw.get("compiled_sql"):
            lines.append("```sql")
            lines.append(qw["compiled_sql"])
            lines.append("```")
            perf = qw.get("execution_performance", {})
            lines.append(f"- **Execution Status:** `{perf.get('status', 'N/A')}` | **Latency:** `{perf.get('latency_ms', 'N/A')} ms` | **Rows:** `{perf.get('row_count', 'N/A')}`")
        else:
            lines.append(f"*(SQL compilation failed: {qw.get('error', 'N/A')})*")

        lines.append("\n#### Baseline (No Skill) Compiled SQL:")
        if qn.get("compiled_sql"):
            lines.append("```sql")
            lines.append(qn["compiled_sql"])
            lines.append("```")
            perf_n = qn.get("execution_performance", {})
            lines.append(f"- **Execution Status:** `{perf_n.get('status', 'N/A')}` | **Latency:** `{perf_n.get('latency_ms', 'N/A')} ms` | **Rows:** `{perf_n.get('row_count', 'N/A')}`")
        else:
            lines.append(f"*(SQL compilation failed: {qn.get('error', 'N/A')})*")

        lines.append("\n</details>\n")

    lines.append("\n---\n")

    # ------------------------------------------------------------------
    # SECTION 6: LOOKML ARTIFACT INDEX
    # ------------------------------------------------------------------
    lines.append("## 6. Exported LookML Artifact Index\n")
    lines.append("The raw LookML files generated by each mode are saved in the run export directory for manual inspection:\n")
    lines.append("- **With Skill LookML Directory:** [`with_skill/lookml/`](file://" + str((export_dir / "with_skill" / "lookml").resolve()) + ")\n")
    for fname in with_skill.get("final_lookml_files", {}).keys():
        lines.append(f"  - `{fname}`")
    lines.append("\n- **Baseline (No Skill) LookML Directory:** [`no_skill/lookml/`](file://" + str((export_dir / "no_skill" / "lookml").resolve()) + ")\n")
    for fname in no_skill.get("final_lookml_files", {}).keys():
        lines.append(f"  - `{fname}`")

    return "\n".join(lines)

def run_benchmark(
    tasks_dir: Path,
    target_task: Optional[str] = None,
    model: str = "gemini-3.6-flash",
    dry_run: bool = True,
    output_dir: Path = Path("eval_exports")
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

    all_results = {
        "benchmark_summary": {
            "timestamp": timestamp,
            "total_tasks": len(task_dirs),
            "model": model,
            "dry_run": dry_run,
            "looker_connected": looker_eval.is_available()
        },
        "tasks": []
    }

    isolated_base = Path(tempfile.mkdtemp(prefix="ojof_benchmark_"))

    for task_dir in task_dirs:
        task_name = task_dir.name
        print(f"\n=======================================================")
        print(f"[Benchmark Runner] Evaluating Task: {task_name}")
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
        # 1. Run WITH skill (2-Turn Lifecycle)
        # ----------------------------------------------------
        with_skill_ws = isolated_base / f"{task_name}_with_skill"
        res_with = run_multi_turn_mode_evaluation(
            task_dir=task_dir,
            driver=driver,
            skill_mode="with-skill",
            dry_run=dry_run,
            scenario_spec=scenario_spec,
            looker_eval=looker_eval,
            workspace_dir=with_skill_ws
        )

        # Export LookML files
        with_skill_export_dir = task_export_dir / "with_skill" / "lookml"
        with_skill_export_dir.mkdir(parents=True, exist_ok=True)
        for fname, fcontent in res_with["final_lookml_files"].items():
            (with_skill_export_dir / fname).write_text(fcontent)

        # ----------------------------------------------------
        # 2. Run WITHOUT skill (2-Turn Lifecycle)
        # ----------------------------------------------------
        no_skill_ws = isolated_base / f"{task_name}_no_skill"
        res_no = run_multi_turn_mode_evaluation(
            task_dir=task_dir,
            driver=driver,
            skill_mode="no-skill",
            dry_run=dry_run,
            scenario_spec=scenario_spec,
            looker_eval=looker_eval,
            workspace_dir=no_skill_ws
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
    parser.add_argument("--out-dir", type=str, default="eval_exports", help="Export root directory")

    args = parser.parse_args()
    tasks_dir = Path(args.tasks_dir)
    out_dir = Path(args.out_dir)

    run_benchmark(
        tasks_dir=tasks_dir,
        target_task=args.task,
        model=args.model,
        dry_run=not args.execute,
        output_dir=out_dir
    )

if __name__ == "__main__":
    main()
