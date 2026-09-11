# ojof-gym: Outer Join On False (OJOF) Evaluation Gym

`ojof-gym` is an evaluation benchmark and gym designed to evaluate AI coding agents on designing, extending, and maintaining multi-fact LookML data models. In particular, it benchmarks whether agents apply **Outer Join On False (OJOF)** architectural patterns to eliminate cartesian fanout, preserve separate fact grains, and minimize code churn over incremental query requirements.

---

## 1. Architectural Principles & Overview

When modeling complex analytics warehouses with multiple independent fact tables (e.g., `order_items` and `inventory_items`) sharing common dimension entities (e.g., `products` and `users`), standard LookML explores suffer from severe architectural traps:
1. **Grain Bias**: Joining child facts directly to a parent fact causes severe row multiplication (fanout traps) and inflated aggregate measures (SUM, COUNT).
2. **Derived Table Rigidity**: Using PDTs/subqueries pre-aggregates facts, destroying filter drill-down flexibility and exploding maintenance overhead.
3. **High Churn on New Queries**: Adding new business questions requires frequent structural edits, explore re-factoring, or duplicate explore sprawl.

### The OJOF Solution
The **Outer Join On False** pattern resolves this by:
- Using a **zero-row dummy base view** (`from: none` / `sql_always_where: 1=2` or empty derived table) to eliminate base-grain bias.
- Joining peer fact tables via `type: full_outer` with `sql_on: FALSE ;;` (preventing any direct row pairing/fanout in the database).
- Guarding shared dimension table joins dynamically with **Liquid `_in_query` conditional logic** so dimension filters inject cleanly into whichever fact branches participate in the query.
- Housing cross-fact ratios and composite calculations in dedicated **field-only calculation views**.

---

## 2. Benchmark Architecture & Workflow

The benchmark executes a multi-turn evaluation comparing a **Baseline Agent (No Skill)** against an agent equipped with the **`lookml-ojof` Skill**:

```
+-----------------------------------------------------------------------------------+
| Turn 1: Greenfield Architecture                                                   |
| - Agent is given schema metadata for BigQuery tables (e.g., TheLook eCommerce).    |
| - Prompts agent to design a multi-fact semantic model supporting diverse grains.  |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| Turns 2 to N: Sequential Incremental Query Extension                              |
| - Target queries are introduced one at a time (e.g., 3 in --light, 10 in full).   |
| - Agent decides whether existing LookML suffices or if incremental edits needed.  |
| - Evaluates: % Queries Served Zero-Touch, Avg. Lines Modified, Cumulative Churn.  |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| Final Turn: Agent Qualitative Insights                                            |
| - Agents briefly summarize (max 3 bullets) top challenges encountered.            |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| Automated Verifiers & Metric Compilation                                          |
| 1. Static Linter: Verifies zero-row base, full_outer / sql_on: FALSE, Liquid joins|
| 2. Looker Project Validator: Tests syntax and compilation via Looker API.         |
| 3. Target Query Verifier: Compiles & executes queries against BigQuery.          |
| 4. BQ Performance & Discrepancy: Compares byte scans, shuffle output, and fanout. |
+-----------------------------------------------------------------------------------+
```

---

## 3. Environment & Connectivity Prerequisites

### Looker API Access
The benchmark environment connects to Looker using standard Looker API credentials configured via `looker-cli` (`~/.config/looker-cli/config.yaml`) or environment variables:

```bash
export LOOKER_BASE_URL="https://<your-looker-instance>.looker.com"
export LOOKER_CLIENT_ID="<your-client-id>"
export LOOKER_CLIENT_SECRET="<your-client-secret>"
export LOOKER_PROJECT="lookml_sandbox"
export LOOKER_MODEL="sandbox"
```

Verify your Looker CLI session:
```bash
looker-cli session get
```

### BigQuery Credentials
Ensure Google Cloud Application Default Credentials (ADC) or `gcloud` authentication are active to allow query dry-runs and performance telemetry collection.

### Pre-Flight Environment Validation
Before launching runs, you can deterministically verify all CLI tools (`agy`, `bq`, `looker-cli`), local validators (`lookml-parser`, `looker-sync`), Looker API sessions, and BigQuery service account authentication:

```bash
python3 eval/validate_environment.py
# Or equivalently:
python3 eval/run_benchmark.py --validate-env
```

---

## 4. Running the Benchmark

The primary benchmark runner is located at `eval/run_benchmark.py`.

### Fast Iteration Mode (`--light`)
Limits execution to **3 query turns** and runs pre-flight connectivity verification before full agent evaluation:
```bash
python3 eval/run_benchmark.py --task task_thelook_ecommerce --execute --light
```

### Full Benchmark Execution (All 10 Queries)
Runs greenfield design and all 10 sequential query turns across both agents:
```bash
python3 eval/run_benchmark.py --task task_thelook_ecommerce --execute
```

### Custom Query Count
```bash
python3 eval/run_benchmark.py --task task_thelook_ecommerce --execute --max-queries 5
```

### Dry-Run / Simulation Mode
Simulates the workflow without making LLM API calls, generating sample structures and verifying report tooling:
```bash
python3 eval/run_benchmark.py --task task_thelook_ecommerce
```

---

## 5. Report Generation & Instant Iteration

The report generator is **completely decoupled** from live network calls, allowing sub-second visual edits and styling iterations.

### Instant Local Rebuild (<2 seconds)
Rebuilds HTML and Markdown reports from saved run artifacts on disk without hitting Looker or BigQuery:
```bash
# Rebuild the most recent run:
python3 eval/rebuild_report.py

# Rebuild a specific run directory:
python3 eval/rebuild_report.py eval_exports/run_20260901_165433
```

### Live Re-Verification (`--live`)
If you explicitly want to re-execute queries against Looker and BigQuery during report generation:
```bash
python3 eval/rebuild_report.py --live
```

---

## 6. Report Structure & Diagnostics

The generated report (`thelook_ecommerce_evaluation_report.html`) contains:

1. **🛠️ Run Diagnostics & Tooling Health Banner** (Top of report):
   - **Run Mode**: Live Agent Execution vs Simulation / Dry-Run
   - **Codebase Health**: LookML file counts generated by each agent
   - **Looker Validator Status**: Project compile/syntax health
   - **Looker API Status**: Looker API connectivity and explore resolution
2. **1. Executive Scorecard**: High-level comparison across Static Linter Invariants, Looker Project Validation, Query Pass Rate, Model Maintainability (% Zero-Touch, Churn, Token Overhead), and BigQuery Shuffle / Byte consumption.
3. **2. Agent Insights & Implementation Challenges**: Top 3 challenges self-reported by each agent during implementation.
4. **3. Scenario Overview**: Task description, architecture prompt, schema scale, and target query list.
5. **4. Static LookML Analysis (Final Model)**: Analysis of OJOF explores, zero-row views, fact joins, Liquid joins, and composite measure views.
6. **5. Incremental Model Maintainability**: Token consumption, % queries served without changes, average lines modified per query, and cumulative churn.
7. **6. Target Queries & Outcomes**: Side-by-side comparison for each query displaying outcomes, maintenance badges, diffs, fields used, compiled SQL, 10-row sample data, and metric discrepancy analysis.
8. **7. BigQuery Performance & Warehouse Consumption**: Total bytes scanned, shuffle output bytes (revealing hidden cartesian duplication), memory spill, and latency.
9. **8. LookML Codebase Assets Index**: Links to generated LookML models, diff files, compiled SQL queries, and sample datasets.

---

## 7. Spectacles CLI Commands

You can also run standalone LookML and SQL checks with Spectacles:

```bash
# Test Looker API connection:
spectacles connect

# Validate LookML syntax:
spectacles lookml

# Validate SQL queries against the warehouse:
spectacles sql

# Run Looker data tests:
spectacles assert
```

---

## 8. Production Deployment Workaround (Sandbox / Ephemeral Testing)

> [!NOTE]
> **Temporary Workaround:** Enabling instance-level Looker feature flags (specifically `dev_mode_in_ca` for Conversational Analytics in developer workspaces) is an onerous process. Furthermore, on this dedicated testing/sandbox instance, there is only a single user running evaluations.
>
> To support queries against newly generated LookML without requiring `dev_mode_in_ca`, the evaluation harness automatically deploys the LookML project branch to production (`looker-cli project deploy <project_id>` / `POST /api/4.0/projects/{project_id}/deploy_to_production`) after each turn's LookML changes are validated and before preparing or executing queries.
>
> When the upstream Looker product change supporting native development mode in Conversational Analytics (`dev_mode_in_ca`) or dev-scoped session queries becomes available on this instance, this production deployment workaround can be deprecated to make the evaluation pipeline more streamlined.

