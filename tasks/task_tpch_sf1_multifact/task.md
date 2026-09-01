# Task: TPC-H SF1 Multi-Fact Explore

## Objective

Design a unified multi-fact explore named `tpch_unified` using the Outer Join On False (OJOF) pattern. The explore must connect `orders`, `lineitem_shipped`, `lineitem_received`, and `partsupp` to a 0-row base view (`from: none`). Shared dimensions (like `customer`, `part`, `supplier`, `nation`, `region`) and a unified `codim_date` must be joined conditionally using Liquid (`_in_query`) to avoid cartesian fanout.

## Scenario Background

- **Scenario ID**: tpch_sf1_multifact
- **Complexity**: medium
- **Target BigQuery Dataset**: `bigquery-public-data.tpch_sf1`

## Fact Tables

- **`orders`**:
  - Grain: 1 row per order placed
  - Primary Key: `o_orderkey`
  - Timestamp / Event Date: `o_orderdate`
  - Key Measures: count, total_price

- **`lineitem_shipped`**:
  - Grain: 1 row per lineitem shipped
  - Primary Key: `l_orderkey, l_linenumber`
  - Timestamp / Event Date: `l_shipdate`
  - Key Measures: count, total_extended_price, total_discount, count_late_deliveries

- **`lineitem_received`**:
  - Grain: 1 row per lineitem received
  - Primary Key: `l_orderkey, l_linenumber`
  - Timestamp / Event Date: `l_receiptdate`
  - Key Measures: count, total_charge, count_returned_items

- **`partsupp`**:
  - Grain: 1 row per part-supplier inventory combination
  - Primary Key: `ps_partkey, ps_suppkey`
  - Timestamp / Event Date: `ps_availqty`
  - Key Measures: count, total_availqty, total_supplycost


## Shared Dimension Tables

- **`customer`**:
  - Primary Key: `c_custkey`
  - Key Joins: orders.o_custkey

- **`supplier`**:
  - Primary Key: `s_suppkey`
  - Key Joins: lineitem_shipped.l_suppkey, partsupp.ps_suppkey

- **`part`**:
  - Primary Key: `p_partkey`
  - Key Joins: lineitem_shipped.l_partkey, partsupp.ps_partkey

- **`nation`**:
  - Primary Key: `n_nationkey`
  - Key Joins: customer.c_nationkey, supplier.s_nationkey

- **`region`**:
  - Primary Key: `r_regionkey`
  - Key Joins: nation.n_regionkey


## Architectural Instructions & Best Practices

1. Use a 0-row base view (`from: none`) with `derived_table: { sql: SELECT NULL FROM UNNEST([]) ;; }`.
2. Join all fact tables as peer branches with `type: full_outer`, `relationship: one_to_one`, and `sql_on: FALSE ;;`.
3. Coalesce shared timestamp columns (`codim_date`) across active fact tables.
4. Bind shared dimension joins using Liquid conditional logic (`{% if ..._in_query %}`).
5. Organize composite measures into a field-only view connected with a bare join.
