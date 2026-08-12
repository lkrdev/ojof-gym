# TPC-H SF1 Looker Block (OJOF Multi-Fact Pattern)

This Looker block provides a complete implementation of the **TPC-H Benchmark Schema** modeled on Google BigQuery public data (`bigquery-public-data.tpch_sf1`), showcasing both traditional single-grain explores and a unified multi-fact **OJOF (Outer Join On False)** explore.

## Features

- **Multi-Fact Unified Explore (`tpch_unified`)**: Joins `orders`, `lineitem`, and `partsupp` across different grains into a single explore using `type: full_outer` + `sql_on: FALSE ;;` over a dummy base view (`from: none`).
- **Dynamic Co-Dimensions & Shared Dimension Joins**:
  - `codim_date`: Dynamically pulls `order_date` or `ship_date` depending on active fact fields in the query.
  - `customer`, `part`, `supplier`, `nation`, `region`: Conditionally joins using Liquid `{% if ..._in_query %}` to avoid row multiplication and cartesian traps.
- **Single-Grain Explores**: Dedicated single-grain explores for `orders`, `lineitem`, and `partsupp`.
- **Aggregate Awareness (`tpch.aa.lkml`)**: Materialized aggregate tables for instant queries at nation and monthly region levels.
- **Manifest Constants**: Easily retargetable dataset (`bigquery-public-data.tpch_sf1`, `tpch_sf100`, etc.) and connection name via `manifest.lkml`.

## Schema Structure

```
Fact Tables:
- orders (1 row per order)
- lineitem (1 row per order line item)
- partsupp (1 row per part-supplier inventory combination)

Dimension Tables:
- customer
- supplier
- part
- nation
- region
```

## How OJOF Works in `tpch_unified`

1. **Dummy Base (`none`)**: Starts with a 0-row base view (`SELECT 0 FROM UNNEST([])`), allowing all fact tables to be joined as peers.
2. **Outer Join on False**: `join: <fact> { type: full_outer sql_on: FALSE ;; }` ensures facts never join directly to each other, eliminating SQL cartesian fanouts and symmetric aggregate performance penalties.
3. **Liquid-Coalesced Dimensions**: Dimension joins bind to the foreign key of whichever fact is actively requested in the query (`{% if orders._in_query %} ... {% endif %}`).
