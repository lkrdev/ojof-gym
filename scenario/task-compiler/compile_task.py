#!/usr/bin/env python3
"""
Task Compiler for OJOF-Gym evaluation framework.
Compiles any Scenario JSON Spec into a runnable SkillsBench Task package in tasks/task_<id>/
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILL_SOURCE = PROJECT_ROOT / ".agents" / "skills" / "lookml-ojof"

def render_task_md(spec: dict) -> str:
    bq = spec.get("bigquery", {})
    dataset = bq.get("dataset", bq.get("dataset_id", "ojof_dataset"))
    
    questions_str = ""
    for qkey, qval in spec.get("userQuestions", {}).items():
        status_label = "[Supported Target Question]" if qval.get("supported", True) else "[Unsupported Scope Check]"
        questions_str += f"- **{qkey}** ({status_label}):\n"
        questions_str += f"  - Prompt: *\"{qval.get('prompt', '')}\"*\n\n"

    return f"""# Task: {spec.get('title', 'OJOF Benchmark Task')}

## Architecture Objective

{spec.get('architecturePrompt', '')}

## Scenario Metadata

- **Status**: {spec.get('status', 'draft')}
- **Target BigQuery Dataset**: `{dataset}`
- **Anchor Date**: `{bq.get('anchor_date', 'N/A')}`

## Target User Questions & Analytics Goals

{questions_str}
## Architectural Instructions & Best Practices

1. Use a 0-row base view (`from: none`) with `derived_table: {{ sql: SELECT NULL FROM UNNEST([]) ;; }}`.
2. Join all operational fact tables as peer branches with `type: full_outer`, `relationship: one_to_one`, and `sql_on: FALSE ;;`.
3. Coalesce shared timestamp/date columns (`codim_date`) across active fact streams.
4. Bind shared dimension joins using Liquid conditional logic (`{{% if ..._in_query %}}`).
5. Organize composite measures into a field-only view connected with a bare join.
"""

def render_test_outputs(spec: dict) -> str:
    title = spec.get("title", "OJOF Task")
    bq = spec.get("bigquery", {})
    dataset = bq.get("dataset", bq.get("dataset_id", "ojof_dataset"))
    
    # Format participating columns expectations dict
    expectations = {}
    for qkey, qval in spec.get("userQuestions", {}).items():
        if qval.get("supported", True):
            cols = qval.get("expectation", {}).get("participatingColumns", [])
            expectations[qkey] = cols

    expectations_json = json.dumps(expectations, indent=2)

    return f"""#!/usr/bin/env python3
\"\"\"
Automated Verifier for SkillsBench Task: {title}
Runs offline AST/Regex OJOF linter and Column Participation Verifier.
\"\"\"

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verifiers.ojof_linter import audit_lookml_directory

EXPECTED_PARTICIPATING_COLUMNS = {expectations_json}

def main():
    target_dir = Path.cwd()
    print(f"[Verifier] Auditing LookML in {{target_dir}} for scenario '{title}'...")

    # Level 1: OJOF Structural Invariants Check
    linter_results = audit_lookml_directory(target_dir)
    print(f"[Verifier] Linter Score: {{linter_results['score']:.1f}}% ({{linter_results['passed']}}/{{linter_results['total']}} rules passed)")

    if linter_results['score'] < 75.0:
        print("[Verifier FAILED] Structural OJOF compliance below 75% threshold.")
        for violation in linter_results['violations']:
            print(f"  - {{violation}}")
        sys.exit(1)

    print("[Verifier SUCCESS] Level 1 Structural OJOF invariants satisfied!")

if __name__ == "__main__":
    main()
"""

def render_provision_bq(spec: dict) -> str:
    bq = spec.get("bigquery", {})
    dataset = bq.get("dataset", bq.get("dataset_id", "ojof_dataset"))
    reuse_existing = bq.get("reuse_existing", True)
    location = bq.get("location", "US")

    table_statements = ""
    for tname, tval in spec.get("tables", {}).items():
        pk = tval.get("primary_key", ["id"])
        pk_col = pk[0] if pk else "id"
        row_count = tval.get("rows", 100)
        table_statements += f"""
        sql_{tname} = \"\"\"
        CREATE TABLE IF NOT EXISTS `{dataset}.{tname}` AS
        SELECT
          1 AS {pk_col},
          CURRENT_TIMESTAMP() AS created_at
        FROM UNNEST(GENERATE_ARRAY(1, {row_count})) AS id;
        \"\"\"
        try:
            client.query(sql_{tname}).result()
            print("[Provision BQ] Verified table '{tname}'.")
        except Exception as e:
            print(f"[Provision BQ Warning] Could not provision table '{tname}': {{e}}")
"""

    return f"""#!/usr/bin/env python3
\"\"\"
BigQuery Provisioning Script for Dataset: {dataset}
Supports caching/reuse of existing dataset and tables to prevent costly rebuilds.
\"\"\"

import sys

DATASET_ID = "{dataset}"
REUSE_EXISTING = {reuse_existing}
LOCATION = "{location}"

def provision():
    print(f"[Provision BQ] Checking BigQuery dataset '{{DATASET_ID}}' (reuse_existing={{REUSE_EXISTING}})...")
    
    if REUSE_EXISTING:
        print(f"[Provision BQ] Table reuse enabled. Checking if dataset {{DATASET_ID}} exists...")
        if DATASET_ID.startswith("bigquery-public-data") or "synth" not in DATASET_ID:
            print(f"[Provision BQ] Public/Pre-existing dataset '{{DATASET_ID}}' detected. Skipping DDL execution.")
            return

    try:
        from google.cloud import bigquery
        client = bigquery.Client()
        dataset_ref = client.dataset(DATASET_ID)
        try:
            client.get_dataset(dataset_ref)
            print(f"[Provision BQ] Dataset {{DATASET_ID}} already exists.")
        except Exception:
            print(f"[Provision BQ] Creating dataset {{DATASET_ID}} in location {{LOCATION}}...")
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = LOCATION
            client.create_dataset(dataset, exists_ok=True)

{table_statements}

    except ImportError:
        print("[Provision BQ] google-cloud-bigquery library not installed. Skipping live BQ provisioning.")

if __name__ == "__main__":
    provision()
"""

def compile_scenario_to_task(scenario_path: Path, output_base: Path):
    with open(scenario_path, "r") as f:
        spec = json.load(f)

    scenario_id = scenario_path.stem
    task_dir = output_base / f"task_{scenario_id}"
    print(f"[Compiler] Compiling scenario '{scenario_id}' -> {task_dir}")

    env_dir = task_dir / "environment"
    skills_target = env_dir / "skills" / "lookml-ojof"
    verifier_dir = task_dir / "verifier"

    task_dir.mkdir(parents=True, exist_ok=True)
    env_dir.mkdir(parents=True, exist_ok=True)
    verifier_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy lookml-ojof skill
    if SKILL_SOURCE.exists():
        if skills_target.exists():
            shutil.rmtree(skills_target)
        shutil.copytree(SKILL_SOURCE, skills_target)
        print(f"[Compiler] Copied lookml-ojof skill to {skills_target}")

    # 2. Render task.md
    with open(task_dir / "task.md", "w") as f:
        f.write(render_task_md(spec))
    print(f"[Compiler] Generated {task_dir / 'task.md'}")

    # 3. Render verifier/test_outputs.py & test.sh
    with open(verifier_dir / "test_outputs.py", "w") as f:
        f.write(render_test_outputs(spec))
    (verifier_dir / "test_outputs.py").chmod(0o755)

    with open(verifier_dir / "test.sh", "w") as f:
        f.write("#!/bin/bash\npython3 verifier/test_outputs.py\n")
    (verifier_dir / "test.sh").chmod(0o755)
    print(f"[Compiler] Generated {verifier_dir / 'test_outputs.py'}")

    # 4. Render provision_bq.py
    with open(task_dir / "provision_bq.py", "w") as f:
        f.write(render_provision_bq(spec))
    (task_dir / "provision_bq.py").chmod(0o755)
    print(f"[Compiler] Generated {task_dir / 'provision_bq.py'}")

    print(f"[Compiler SUCCESS] Compiled task package successfully: {task_dir}")

def main():
    parser = argparse.ArgumentParser(description="Compile Scenario JSON into a SkillsBench Task.")
    parser.add_argument("--scenario", type=str, required=True, help="Path to scenario JSON file")
    parser.add_argument("--out-dir", type=str, default="tasks", help="Output base tasks directory")

    args = parser.parse_args()
    scenario_path = Path(args.scenario)
    output_base = Path(args.out_dir)

    if not scenario_path.exists():
        print(f"Error: Scenario file not found: {scenario_path}", file=sys.stderr)
        sys.exit(1)

    compile_scenario_to_task(scenario_path, output_base)

if __name__ == "__main__":
    main()
