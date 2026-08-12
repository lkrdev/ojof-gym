# TPC-H SF1 Looker Block (OJOF Multi-Fact Pattern)

This Looker block provides a complete implementation of the **TPC-H Benchmark Schema** modeled on Google BigQuery public data (`bigquery-public-data.tpch_sf1`), showcasing both traditional single-grain explores and a unified multi-fact **OJOF (Outer Join On False)** explore.

## Features

- **Multi-Fact Unified Explore (`tpch_unified`)**: Joins `orders`, `lineitem_shipped`, `lineitem_received`, and `partsupp` across different grains and milestone events into a single explore using `type: full_outer` + `sql_on: FALSE ;;` over a dummy base view (`from: none`).
- **Milestone Dates & Filtered Measures**:
  - `lineitem_shipped` and `lineitem_received` model distinct fulfillment lifecycle events on a unified timeline.
  - Filtered measures for `count_late_deliveries`, `count_returned_items`, and `total_returned_charge`.
- **Dynamic Co-Dimensions & Shared Dimension Joins**:
  - `codim_date`: Dynamically binds `order_date`, `ship_date`, or `receipt_date` depending on active fact fields in the query.
  - `customer`, `part`, `supplier`, `nation`, `region`: Conditionally joins using Liquid `{% if ..._in_query %}` to avoid row multiplication and cartesian traps.
- **Single-Grain Explores**: Dedicated single-grain explores for `orders`, `lineitem`, and `partsupp`.
- **Aggregate Awareness (`tpch.aa.lkml`)**: Materialized aggregate tables for instant queries at nation and monthly region levels.
- **Manifest Constants**: Easily retargetable dataset (`bigquery-public-data.tpch_sf1`, `tpch_sf100`, etc.) and connection name via `manifest.lkml`.

## Schema Structure

```
Fact Tables & Milestone Views:
- orders (1 row per order placed)
- lineitem_shipped (1 row per order line shipped)
- lineitem_received (1 row per order line received)
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
4. **Milestone Date Unification**: Aliased milestone facts bind their respective timestamps (`order_date`, `ship_date`, `receipt_date`) to the shared `codim_date`.
