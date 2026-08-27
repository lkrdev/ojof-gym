include: "/examples/tpch_sf1/views/*.view.lkml"

explore: lineitem {
  label: "Line Items"
  description: "Single-grain explore at Order Line Item level."

  join: orders {
    view_label: "Orders"
    type: left_outer
    relationship: many_to_one
    sql_on: ${lineitem.order_key} = ${orders.order_key} ;;
  }

  join: customer {
    view_label: "Customer"
    type: left_outer
    relationship: many_to_one
    sql_on: ${orders.cust_key} = ${customer.cust_key} ;;
  }

  join: part {
    view_label: "Part"
    type: left_outer
    relationship: many_to_one
    sql_on: ${lineitem.part_key} = ${part.part_key} ;;
  }

  join: supplier {
    view_label: "Supplier"
    type: left_outer
    relationship: many_to_one
    sql_on: ${lineitem.supp_key} = ${supplier.supp_key} ;;
  }

  join: nation {
    view_label: "Supplier Geography - Nation"
    type: left_outer
    relationship: many_to_one
    sql_on: ${supplier.nation_key} = ${nation.nation_key} ;;
  }

  join: region {
    view_label: "Supplier Geography - Region"
    type: left_outer
    relationship: many_to_one
    sql_on: ${nation.region_key} = ${region.region_key} ;;
  }
}
