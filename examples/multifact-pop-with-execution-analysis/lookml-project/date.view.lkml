view: date {
  view_label: "[Date]"

  filter: date_filter {
    type: date
    datatype: date
    label: "Date Limit"
    #hidden: yes # Hidden for explore-only use with always_filter. Unhidden for ability to select it when linking dsahboard filters to explore filter
    sql: COALESCE({% condition %} ${TABLE} {% endcondition %},TRUE);; # True if null, i.e. applied to a row with no date column
  }

  dimension_group: _ {
    type: time
    datatype: date
    sql: ${TABLE} ;;
    timeframes: [week,date,raw]
  }

  dimension_group: _parts_of {
    type: time
    datatype: date
    sql: ${TABLE} ;;
    timeframes: [day_of_week]
  }
  dimension_group: _parts_of_ {
    type: time
    hidden: yes # This is mainly for use in other dimension definitions
    datatype: date
    sql: ${TABLE} ;;
    timeframes: [day_of_week_index,day_of_month]
  }

  dimension: date_in_filter_format {
    hidden: yes # Only for use in LookML
    type: string
    sql: FORMAT_DATE("%Y/%m/%d", ${__date});;
  }

  dimension_group: current {
    type: time
    datatype: date
    sql: CURRENT_DATE() ;;
    hidden: yes # This is mainly for use in other dimension definitions
    timeframes: [week,date,raw,day_of_week_index, day_of_month]
  }

  dimension: days_ago {
    # Can be helpful in writing custom fields with flexible date logic, since date functions in custom fields are kinda wonky at the moment
    hidden: yes
    type: number
    sql: DATE_DIFF(CURRENT_DATE(),${__date}, DAY) ;;
  }

  dimension: is_wtd {
    group_label: "Is period-to-date?"
    label: "Is WtD?"
    description: "Is week-to-date? Whether the date in question is earlier within its week than the current date. Useful for filtering to comparable parts of the current period and a past period"
    type: yesno
    sql: ${_parts_of__day_of_week_index} < ${current_day_of_week_index}  ;;
  }

  dimension: is_mtd {
    group_label: "Is period-to-date?"
    label: "Is MtD?"
    description: "Is month-to-date? Whether the date in question is earlier within its month than the current date. Useful for filtering to comparable parts of the current period and a past period"
    type: yesno
    sql: ${_parts_of__day_of_month} < ${current_day_of_month}  ;;
  }

  measure: month_range {
    type: number
    sql: MAX(12*(${TABLE}.month_id/100)+(${TABLE}.month_id % 100)) - MIN(12*(${TABLE}.month_id/100)+(${TABLE}.month_id % 100)) ;;
  }


}
