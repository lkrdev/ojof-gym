test: lineitem_filtered_measures_exist {
  explore_source: lineitem {
    column: count_late_deliveries {}
    column: count_returned_items {}
    column: total_returned_charge {}
  }

  assert: late_deliveries_greater_than_zero {
    expression: ${lineitem.count_late_deliveries} > 0 ;;
  }

  assert: returned_items_greater_than_zero {
    expression: ${lineitem.count_returned_items} > 0 ;;
  }

  assert: returned_charge_greater_than_zero {
    expression: ${lineitem.total_returned_charge} > 0 ;;
  }
}
