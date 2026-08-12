include: "/examples/tpch_sf1/views/*.view.lkml"

explore: tpch_unified {
  label: "TPC-H Unified (OJOF Multi-Fact)"
  description: "Multi-fact explore combining Orders, Shipped Line Items, Received Line Items, and PartSupp over Outer Join On False without fanout."
  from: none

  # Fact 1: Orders Placed (Grain: 1 row per order placed)
  join: orders {
    view_label: "Orders (Placed)"
    type: full_outer
    relationship: one_to_one
    sql_on: FALSE ;;
  }

  # Milestone Fact 2: Line Items Shipped (Grain: 1 row per order line shipped)
  join: lineitem_shipped {
    from: lineitem
    view_label: "Line Items (Shipped)"
    type: full_outer
    relationship: one_to_one
    sql_on: FALSE ;;
  }

  # Milestone Fact 3: Line Items Received (Grain: 1 row per order line received)
  join: lineitem_received {
    from: lineitem
    view_label: "Line Items (Received)"
    type: full_outer
    relationship: one_to_one
    sql_on: FALSE ;;
  }

  # Fact 4: Part Supplier / Inventory (Grain: 1 row per part-supplier)
  join: partsupp {
    view_label: "Part Supplier (Inventory)"
    type: full_outer
    relationship: one_to_one
    sql_on: FALSE ;;
  }

  # Shared Dimension 1: Customer (Joined conditionally based on active fact in query)
  join: customer {
    view_label: "Customer"
    type: left_outer
    relationship: many_to_one
    sql_on: ${customer.cust_key} = COALESCE(
      {% if orders._in_query %} ${orders.cust_key}, {% endif %}
      NULL
    ) ;;
  }

  # Shared Dimension 2: Part (Joined conditionally across Lineitem and PartSupp)
  join: part {
    view_label: "Part"
    type: left_outer
    relationship: many_to_one
    sql_on: ${part.part_key} = COALESCE(
      {% if lineitem_shipped._in_query %} ${lineitem_shipped.part_key}, {% endif %}
      {% if lineitem_received._in_query %} ${lineitem_received.part_key}, {% endif %}
      {% if partsupp._in_query %} ${partsupp.part_key}, {% endif %}
      NULL
    ) ;;
  }

  # Shared Dimension 3: Supplier (Joined conditionally across Lineitem and PartSupp)
  join: supplier {
    view_label: "Supplier"
    type: left_outer
    relationship: many_to_one
    sql_on: ${supplier.supp_key} = COALESCE(
      {% if lineitem_shipped._in_query %} ${lineitem_shipped.supp_key}, {% endif %}
      {% if lineitem_received._in_query %} ${lineitem_received.supp_key}, {% endif %}
      {% if partsupp._in_query %} ${partsupp.supp_key}, {% endif %}
      NULL
    ) ;;
  }

  # Shared Dimension 4: Nation (Linked via Customer or Supplier)
  join: nation {
    view_label: "Geography - Nation"
    type: left_outer
    relationship: many_to_one
    sql_on: ${nation.nation_key} = COALESCE(
      {% if customer._in_query %} ${customer.nation_key}, {% endif %}
      {% if supplier._in_query %} ${supplier.nation_key}, {% endif %}
      NULL
    ) ;;
  }

  # Shared Dimension 5: Region (Linked via Nation)
  join: region {
    view_label: "Geography - Region"
    type: left_outer
    relationship: many_to_one
    sql_on: ${region.region_key} = ${nation.region_key} ;;
  }

  # Co-dimension: Date (Cross-joined UNNEST of coalesced timestamp expression across milestones)
  join: codim_date {
    view_label: "Activity Date"
    type: cross
    relationship: one_to_one
    sql_table_name: UNNEST([COALESCE(
      {% if orders._in_query %} CAST(orders.o_orderdate AS TIMESTAMP), {% endif %}
      {% if lineitem_shipped._in_query %} CAST(lineitem_shipped.l_shipdate AS TIMESTAMP), {% endif %}
      {% if lineitem_received._in_query %} CAST(lineitem_received.l_receiptdate AS TIMESTAMP), {% endif %}
      CAST(NULL AS TIMESTAMP)
    )]) ;;
  }
}
