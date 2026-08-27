view: codim_date {
  view_label: "[Activity Date]"

  filter: view_description {
    label: "(info) -➤"
    description: "Co-dimension date dynamically resolved from active facts (Orders order date, Lineitem ship/receipt/commit date)."
    sql: TRUE ;;
  }

  dimension_group: date {
    type: time
    timeframes: [raw, date, week, month, quarter, year, day_of_week, day_of_month, month_name]
    datatype: timestamp
    sql: ${TABLE} ;;
  }
}
