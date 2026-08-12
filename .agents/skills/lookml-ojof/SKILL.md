---
name: lookml-ojof
description: Design, build, refactor, and optimize multi-fact LookML Explores using the Outer Join On False (OJOF) pattern. Eliminates cartesian fanouts, chasm traps, and symmetric aggregate overhead across disparate data grains.
---

# LookML OJOF (Outer Join On False) Skill

## 1. Problem & Core Concept

When querying multiple independent fact tables with different grains (e.g. Sales Orders, Line-Item Fulfillment, Inventory, Web Events) in a standard Looker explore, joins cause **cartesian fanouts**, **chasm traps**, or require heavy **symmetric aggregate calculations**.

**The OJOF Pattern** solves this by treating fact tables as parallel peers connected to a 0-row dummy table, dynamically binding shared dimensions and co-dimensions via Liquid.

```
       [ none (0 rows) ]
       /       |       \
FULL OUTER  FULL OUTER  FULL OUTER
sql_on:FALSE sql_on:FALSE sql_on:FALSE
    /          |          \
[Fact A]   [Fact B]    [Fact C]
    \          |          /
     \         |         /
      LEFT OUTER (Liquid COALESCE)
               |
      [Shared Dimension / Co-dim]
```

---

## 2. The 4 Structural Rules

### Rule 1: The 0-Row Base (`from: none`)
The explore root MUST be a dummy table returning 0 rows so facts are peers:
```lookml
view: none {
  derived_table: {
    sql: SELECT 0 FROM UNNEST([]) ;; # BigQuery standard SQL (or SELECT NULL as x WHERE 1=0)
  }
}
```

### Rule 2: Peer Fact Joins (`FULL OUTER` on `FALSE`)
Every fact table is joined with `type: full_outer`, `relationship: one_to_one`, and `sql_on: FALSE ;;`:
```lookml
join: fact_orders {
  from: orders
  type: full_outer
  relationship: one_to_one
  sql_on: FALSE ;;
}

join: fact_inventory {
  from: inventory
  type: full_outer
  relationship: one_to_one
  sql_on: FALSE ;;
}
```

### Rule 3: Dynamic Shared Dimensions (`COALESCE` + Liquid)
Shared entity dimensions (e.g. Customer, Product, Supplier, Geography) join conditionally to whichever fact table is currently active in the user query:
```lookml
join: customer {
  type: left_outer
  relationship: many_to_one
  sql_on: ${customer.id} = COALESCE(
    {% if fact_orders._in_query %} ${fact_orders.customer_id}, {% endif %}
    {% if fact_web_events._in_query %} ${fact_web_events.customer_id}, {% endif %}
    NULL
  ) ;;
}
```

### Rule 4: Co-Dimension Date View (`codim_date`)
A single unified time dimension that resolves to the timestamp of whatever facts are in query:
```lookml
view: codim_date {
  view_label: "[Activity Date]"
  sql_table_name: COALESCE(
    {% if fact_orders._in_query %} CAST(fact_orders.order_date AS TIMESTAMP), {% endif %}
    {% if fact_inventory._in_query %} CAST(fact_inventory.snapshot_date AS TIMESTAMP), {% endif %}
    CAST(NULL AS TIMESTAMP)
  ) ;;

  dimension_group: date {
    type: time
    timeframes: [raw, date, week, month, quarter, year]
    datatype: timestamp
    sql: ${TABLE} ;;
  }
}

# In Explore:
join: codim_date {
  type: cross
  relationship: one_to_one
  sql_table_name: UNNEST([${codim_date.SQL_TABLE_NAME}]) ;;
}
```

---

## 3. Complete Reference Pattern

```lookml
include: "/views/*.view.lkml"

explore: multi_fact_unified {
  label: "Unified Business Activity (OJOF)"
  description: "Cross-grain analysis of Orders, Shipments, and Inventory without row multiplication."
  from: none

  # --- FACT TABLES ---
  join: orders {
    view_label: "Orders"
    type: full_outer
    relationship: one_to_one
    sql_on: FALSE ;;
  }

  join: lineitem {
    view_label: "Line Items"
    type: full_outer
    relationship: one_to_one
    sql_on: FALSE ;;
  }

  join: inventory {
    view_label: "Inventory / Supply"
    type: full_outer
    relationship: one_to_one
    sql_on: FALSE ;;
  }

  # --- SHARED DIMENSIONS ---
  join: product {
    view_label: "Product"
    type: left_outer
    relationship: many_to_one
    sql_on: ${product.id} = COALESCE(
      {% if lineitem._in_query %} ${lineitem.product_id}, {% endif %}
      {% if inventory._in_query %} ${inventory.product_id}, {% endif %}
      NULL
    ) ;;
  }

  join: customer {
    view_label: "Customer"
    type: left_outer
    relationship: many_to_one
    sql_on: ${customer.id} = COALESCE(
      {% if orders._in_query %} ${orders.customer_id}, {% endif %}
      NULL
    ) ;;
  }

  # --- CO-DIMENSIONS ---
  join: codim_date {
    view_label: "Activity Date"
    type: cross
    relationship: one_to_one
    sql_table_name: UNNEST([${codim_date.SQL_TABLE_NAME}]) ;;
  }
}
```

---

## 4. Aggregate Awareness with OJOF

Aggregate tables work seamlessly on top of OJOF explores. Define rollups on the unified explore using the co-dimension date:

```lookml
explore: +multi_fact_unified {
  aggregate_table: monthly_kpi_rollup {
    query: {
      dimensions: [product.category, codim_date.date_month]
      measures: [orders.total_revenue, lineitem.total_quantity, inventory.total_stock]
    }
    materialization: {
      datagroup_trigger: daily_etl
    }
  }
}
```

---

## 5. Multi-Event & Milestone Dates (Role-Playing Facts)

When an entity lifecycle contains multiple event dates (e.g. Sales Opportunities with `created_date` and `closed_date`), grouping by `created_date` breaks measures like "Opportunities Closed" because it only counts deals created in that same timeframe.

**OJOF Solution**: Model each lifecycle milestone as a separate peer fact alias joined `FULL OUTER` on `FALSE`, binding each milestone timestamp into `codim_date`:

```lookml
explore: sales_pipeline {
  from: none

  # Milestone Fact 1: Creation Event
  join: opps_created {
    from: opportunities
    type: full_outer
    relationship: one_to_one
    sql_on: FALSE ;;
  }

  # Milestone Fact 2: Closing Event
  join: opps_closed {
    from: opportunities
    type: full_outer
    relationship: one_to_one
    sql_on: FALSE ;;
  }

  # Unified Co-Dimension Date binds each milestone to the common calendar
  join: codim_date {
    view_label: "[Activity Date]"
    type: cross
    relationship: one_to_one
    sql_table_name: UNNEST([COALESCE(
      {% if opps_created._in_query %} CAST(opps_created.created_date AS TIMESTAMP), {% endif %}
      {% if opps_closed._in_query  %} CAST(opps_closed.closed_date AS TIMESTAMP),  {% endif %}
      CAST(NULL AS TIMESTAMP)
    )]) ;;
  }
}
```

This allows querying a single calendar dimension (e.g., `codim_date.date_month`) alongside `opps_created.count` and `opps_closed.count` simultaneously without row fanout or cross-filtering interference.

---

## 6. Checklist for Agents

- [ ] `from: none` base view is 0 rows (`UNNEST([])` or `WHERE 1=0`).
- [ ] Every fact join is `type: full_outer`, `relationship: one_to_one`, `sql_on: FALSE ;;`.
- [ ] Multi-event milestones on a single lifecycle entity use aliased peer fact joins.
- [ ] Shared dimensions use `COALESCE` with `{% if <fact>._in_query %}`.
- [ ] Co-dimension dates are cross-joined with `UNNEST([${codim_date.SQL_TABLE_NAME}])`.
- [ ] Aggregate tables use the co-dimension date field in rollup queries.

