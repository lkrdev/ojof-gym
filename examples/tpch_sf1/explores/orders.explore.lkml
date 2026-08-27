include: "/examples/tpch_sf1/views/*.view.lkml"

explore: orders {
  label: "Orders"
  description: "Single-grain explore at Order level."

  join: customer {
    view_label: "Customer"
    type: left_outer
    relationship: many_to_one
    sql_on: ${orders.cust_key} = ${customer.cust_key} ;;
  }

  join: nation {
    view_label: "Customer Geography - Nation"
    type: left_outer
    relationship: many_to_one
    sql_on: ${customer.nation_key} = ${nation.nation_key} ;;
  }

  join: region {
    view_label: "Customer Geography - Region"
    type: left_outer
    relationship: many_to_one
    sql_on: ${nation.region_key} = ${region.region_key} ;;
  }
}
