view: lineitem {
  sql_table_name: `@{TPCH_DATASET}.lineitem` ;;

  dimension: pk {
    primary_key: yes
    hidden: yes
    type: string
    sql: CONCAT(CAST(${TABLE}.l_orderkey AS STRING), '-', CAST(${TABLE}.l_linenumber AS STRING)) ;;
  }

  dimension: order_key {
    type: number
    sql: ${TABLE}.l_orderkey ;;
  }

  dimension: line_number {
    type: number
    sql: ${TABLE}.l_linenumber ;;
  }

  dimension: part_key {
    type: number
    hidden: yes
    sql: ${TABLE}.l_partkey ;;
  }

  dimension: supp_key {
    type: number
    hidden: yes
    sql: ${TABLE}.l_suppkey ;;
  }

  dimension: quantity {
    type: number
    sql: ${TABLE}.l_quantity ;;
  }

  dimension: extended_price {
    type: number
    value_format_name: usd
    sql: ${TABLE}.l_extendedprice ;;
  }

  dimension: discount {
    type: number
    value_format_name: percent_2
    sql: ${TABLE}.l_discount ;;
  }

  dimension: tax {
    type: number
    value_format_name: percent_2
    sql: ${TABLE}.l_tax ;;
  }

  dimension: return_flag {
    type: string
    sql: ${TABLE}.l_returnflag ;;
  }

  dimension: line_status {
    type: string
    sql: ${TABLE}.l_linestatus ;;
  }

  dimension: ship_instruct {
    type: string
    sql: ${TABLE}.l_shipinstruct ;;
  }

  dimension: ship_mode {
    type: string
    sql: ${TABLE}.l_shipmode ;;
  }

  dimension: comment {
    type: string
    sql: ${TABLE}.l_comment ;;
  }

  dimension_group: ship_date {
    type: time
    timeframes: [raw, date, week, month, quarter, year]
    datatype: date
    sql: ${TABLE}.l_shipdate ;;
  }

  dimension_group: commit_date {
    type: time
    timeframes: [raw, date, week, month, quarter, year]
    datatype: date
    sql: ${TABLE}.l_commitdate ;;
  }

  dimension_group: receipt_date {
    type: time
    timeframes: [raw, date, week, month, quarter, year]
    datatype: date
    sql: ${TABLE}.l_receiptdate ;;
  }

  dimension: is_late_delivery {
    type: yesno
    description: "Whether the receipt date was after the committed delivery date"
    sql: ${TABLE}.l_receiptdate > ${TABLE}.l_commitdate ;;
  }

  dimension: is_returned {
    type: yesno
    description: "Whether the line item was marked as returned"
    sql: ${TABLE}.l_returnflag = 'R' ;;
  }

  measure: count {
    type: count
    drill_fields: [order_key, line_number, quantity, extended_price, ship_mode]
  }

  measure: count_late_deliveries {
    type: count
    description: "Count of line items received past the committed delivery date"
    filters: [is_late_delivery: "yes"]
    drill_fields: [order_key, line_number, ship_date_date, commit_date_date, receipt_date_date]
  }

  measure: count_returned_items {
    type: count
    description: "Count of line items returned by customers"
    filters: [is_returned: "yes"]
    drill_fields: [order_key, line_number, quantity, extended_price, return_flag]
  }

  measure: total_quantity {
    type: sum
    sql: ${quantity} ;;
  }

  measure: total_extended_price {
    type: sum
    value_format_name: usd
    sql: ${extended_price} ;;
  }

  measure: total_discounted_price {
    type: sum
    value_format_name: usd
    sql: ${TABLE}.l_extendedprice * (1 - ${TABLE}.l_discount) ;;
  }

  measure: total_charge {
    type: sum
    value_format_name: usd
    sql: ${TABLE}.l_extendedprice * (1 - ${TABLE}.l_discount) * (1 + ${TABLE}.l_tax) ;;
  }

  measure: total_returned_charge {
    type: sum
    value_format_name: usd
    description: "Total charge value of returned line items"
    sql: ${TABLE}.l_extendedprice * (1 - ${TABLE}.l_discount) * (1 + ${TABLE}.l_tax) ;;
    filters: [is_returned: "yes"]
  }

  measure: average_discount {
    type: average
    value_format_name: percent_2
    sql: ${TABLE}.l_discount ;;
  }
}
