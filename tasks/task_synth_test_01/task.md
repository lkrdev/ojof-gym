# Task: Synthetic Ecommerce Multi-Fact Explore (3 Facts)

## Objective

Design a multi-fact LookML explore for ecommerce combining inventory_snapshots, orders, order_items using the Outer Join On False (OJOF) pattern. Base view must be `from: none`. Shared dimensions must use Liquid conditional joins.

## Scenario Background

- **Scenario ID**: synth_test_01
- **Complexity**: medium
- **Target BigQuery Dataset**: `ojof_synth_synth_test_01`

## Fact Tables

- **`inventory_snapshots`**:
  - Grain: 1 row per product warehouse snapshot
  - Primary Key: `product_id, warehouse_id`
  - Timestamp / Event Date: `snapshot_date`
  - Key Measures: count, stock_quantity, reorder_threshold

- **`orders`**:
  - Grain: 1 row per order
  - Primary Key: `order_id`
  - Timestamp / Event Date: `order_timestamp`
  - Key Measures: count, total_amount, tax_amount

- **`order_items`**:
  - Grain: 1 row per order item
  - Primary Key: `order_id, item_id`
  - Timestamp / Event Date: `shipped_at`
  - Key Measures: count, item_price, discount_amount


## Shared Dimension Tables

- **`customers`**:
  - Primary Key: `customer_id`
  - Key Joins: orders.customer_id

- **`products`**:
  - Primary Key: `product_id`
  - Key Joins: order_items.product_id, inventory_snapshots.product_id

- **`warehouses`**:
  - Primary Key: `warehouse_id`
  - Key Joins: inventory_snapshots.warehouse_id


## Architectural Instructions & Best Practices

1. Use a 0-row base view (`from: none`) with `derived_table: { sql: SELECT NULL FROM UNNEST([]) ;; }`.
2. Join all fact tables as peer branches with `type: full_outer`, `relationship: one_to_one`, and `sql_on: FALSE ;;`.
3. Coalesce shared timestamp columns (`codim_date`) across active fact tables.
4. Bind shared dimension joins using Liquid conditional logic (`{% if ..._in_query %}`).
5. Organize composite measures into a field-only view connected with a bare join.
