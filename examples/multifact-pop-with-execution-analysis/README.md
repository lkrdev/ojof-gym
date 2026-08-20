# Multi-fact Period-over-Period Example Model with BigQuery Execution Analysis

This example contains both a simplified two-fact model with each fact joined twice for flexible period-over-period (PoP) analysis, along with an export of a report about BigQuery execution performance.

LookML files are in the (`lookml-project` subdirectory)[lookml-project]

The query execution report, exported from the [BigQuery Information Schema Looker Block](https://github.com/looker-open-source/bigquery_information_schema_block)'s job inspection dashboard, is in the (`query-execution-analysis` subdirectory)[query-execution-analysis].

## Summary of Expected BigQuery Performance Characteristics Under Ideal Assumptions

### 1. Compile-Time Optimization & Plan Simplification

* **Single-Pass Stream Concatenation:** BigQuery's query optimizer evaluates `ON FALSE` as a static constant at compile-time. Rather than instantiating physical join operators between the fact streams, the engine collapses all fact table scans into a single physical execution stage.
  * *What to look for in `job_stages.csv`:* Notice that multiple reads within and across fact tables are combined into a single execution stage (e.g., Stage 03), indicated by `READ` steps with `(1 similar table omitted)` for repeated PoP references to the same table.
* **Subquery Partition Pruning:** Placing date filters directly within large fact table's subqueries ensures BigQuery prunes unneeded partitions at storage scan time before combining the fact streams.
  * *What to look for across report files:* 
    1. Check `referenced_tables.csv` to identify the designated `Partition Column` for each table.
    2. In `job_stages.csv`, locate the corresponding `$` variable mapped to that column in the table `READ` step.
    3. Confirm that the embedded `WHERE` clause in that `READ` step targets that specific partition variable (e.g., `WHERE and(greater_or_equal($X, ...), less_or_equal($X, ...))`), verifying that storage partition pruning is active at scan time.
* **Minimal Fact Shuffle Overhead:** Because `ON FALSE` eliminates row-to-row matching between fact tables, BigQuery unifies the fact branches in memory without shuffling raw fact rows between each other.
  * *What to look for in `stage_metrics.csv`:* `Total Shuffle Output Bytes` remains minimal (typically under 1 MB), provided that joined dimension tables fit within BigQuery's broadcast memory limits and are executed via Broadcast Hash Joins, and provided that the types of aggregations support aggregations being pushed down to each worker.

### 2. Dimension Join Behavior (Broadcast Hash Joins)
* **Automatic Dimension Broadcasting:** When a shared dimension table is joined to the unified fact streams via a `COALESCE(fact1.key, fact2.key, ...)` expression, BigQuery identifies small dimension tables and automatically executes a **Broadcast Hash Join**.
  * *What to look for in `job_stages.csv`:* The physical join step is logged explicitly as `LEFT OUTER HASH JOIN EACH WITH ALL`, where `EACH` worker slot processes a fact data shard and `WITH ALL` worker slots receive a full copy of the broadcast dimension table.
* **Single Physical Join Operator:** By deferring the dimension join until after the fact streams are concatenated, the engine performs **only 1 physical broadcast join** across the dataset, rather than executing separate physical join passes for each fact branch.

### 3. CPU & Resource Profile
* **Linear Slot Scaling:** Because join-driven cartesian expansion is completely eliminated, slot consumption scales predictably with the total volume of raw fact rows scanned and number of columns selected.
* **Primary CPU Drivers:** Total slot consumption (`Total Slot ms` in `basic_info.csv` and `job_stages.csv`) is primarily driven by:
  1. **Schema Unification:** Projecting `NULL` placeholder columns across all fact branches for each row.
  2. **Multi-Way `COALESCE` Evaluation:** Evaluating expression keys across multiple fact streams per row before hashing.
  3. **Row-Level Measure Tracking:** Computing aggregation functions (such as `SUM`, `MIN`, `MAX`) across wide, un-aggregated fact streams.
* **Skew:** Since optimal execution scenarios involve limited network shuffling and are primarily bound by scanning and CPU time, maintaining low skew among these activities is generally important. Monitor that data/scanning/CPU skew remains low, below 5, and ideally below 3. Although this should be assessed in a way that is balanced across typical query patterns, including filtering by the cluster key, be careful not to overindex on apparent skew problems for usage that is skewed but still fast due to being highly selective.
