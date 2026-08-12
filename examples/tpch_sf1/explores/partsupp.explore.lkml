include: "/examples/tpch_sf1/views/*.view.lkml"

explore: partsupp {
  label: "Part Supplier (Inventory)"
  description: "Single-grain explore at Part-Supplier supply level."

  join: part {
    view_label: "Part"
    type: left_outer
    relationship: many_to_one
    sql_on: ${partsupp.part_key} = ${part.part_key} ;;
  }

  join: supplier {
    view_label: "Supplier"
    type: left_outer
    relationship: many_to_one
    sql_on: ${partsupp.supp_key} = ${supplier.supp_key} ;;
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
