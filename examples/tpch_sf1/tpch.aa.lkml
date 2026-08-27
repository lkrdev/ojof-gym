explore: +tpch_unified {
  aggregate_table: monthly_sales_by_region {
    query: {
      dimensions: [region.name, codim_date.date_month]
      measures: [orders.count, orders.total_price, lineitem_shipped.total_quantity, lineitem_shipped.total_discounted_price]
    }
    materialization: {
      datagroup_trigger: tpch_default_datagroup
    }
  }

  aggregate_table: nation_order_summary {
    query: {
      dimensions: [nation.name]
      measures: [orders.count, orders.total_price, lineitem_shipped.total_charge, partsupp.total_available_quantity]
    }
    materialization: {
      datagroup_trigger: tpch_default_datagroup
    }
  }
}
