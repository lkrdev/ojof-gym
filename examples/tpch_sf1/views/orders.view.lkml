view: orders {
  sql_table_name: `@{TPCH_DATASET}.orders` ;;

  dimension: order_key {
    primary_key: yes
    type: number
    sql: ${TABLE}.o_orderkey ;;
  }

  dimension: cust_key {
    type: number
    hidden: yes
    sql: ${TABLE}.o_custkey ;;
  }

  dimension: order_status {
    type: string
    sql: ${TABLE}.o_orderstatus ;;
  }

  dimension: order_priority {
    type: string
    sql: ${TABLE}.o_orderpriority ;;
  }

  dimension: clerk {
    type: string
    sql: ${TABLE}.o_clerk ;;
  }

  dimension: ship_priority {
    type: number
    sql: ${TABLE}.o_shippriority ;;
  }

  dimension: comment {
    type: string
    sql: ${TABLE}.o_comment ;;
  }

  dimension_group: order_date {
    type: time
    timeframes: [raw, date, week, month, quarter, year]
    datatype: date
    sql: ${TABLE}.o_orderdate ;;
  }

  measure: count {
    type: count
    drill_fields: [order_key, order_date_date, order_status, total_price]
  }

  measure: total_price {
    type: sum
    value_format_name: usd
    sql: ${TABLE}.o_totalprice ;;
  }

  measure: average_price {
    type: average
    value_format_name: usd
    sql: ${TABLE}.o_totalprice ;;
  }
}
