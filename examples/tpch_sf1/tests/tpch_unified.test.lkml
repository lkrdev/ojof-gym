test: tpch_unified_milestone_filtered_measures_exist {
  explore_source: tpch_unified {
    column: shipped_late_deliveries {
      field: lineitem_shipped.count_late_deliveries
    }
    column: received_returned_items {
      field: lineitem_received.count_returned_items
    }
    column: received_returned_charge {
      field: lineitem_received.total_returned_charge
    }
  }

  assert: shipped_late_deliveries_greater_than_zero {
    expression: ${lineitem_shipped.count_late_deliveries} > 0 ;;
  }

  assert: received_returned_items_greater_than_zero {
    expression: ${lineitem_received.count_returned_items} > 0 ;;
  }

  assert: received_returned_charge_greater_than_zero {
    expression: ${lineitem_received.total_returned_charge} > 0 ;;
  }
}
