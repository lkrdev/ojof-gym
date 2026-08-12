view: partsupp {
  sql_table_name: `@{TPCH_DATASET}.partsupp` ;;

  dimension: pk {
    primary_key: yes
    hidden: yes
    type: string
    sql: CONCAT(CAST(${TABLE}.ps_partkey AS STRING), '-', CAST(${TABLE}.ps_suppkey AS STRING)) ;;
  }

  dimension: part_key {
    type: number
    hidden: yes
    sql: ${TABLE}.ps_partkey ;;
  }

  dimension: supp_key {
    type: number
    hidden: yes
    sql: ${TABLE}.ps_suppkey ;;
  }

  dimension: avail_qty {
    type: number
    sql: ${TABLE}.ps_availqty ;;
  }

  dimension: supply_cost {
    type: number
    value_format_name: usd
    sql: ${TABLE}.ps_supplycost ;;
  }

  dimension: comment {
    type: string
    sql: ${TABLE}.ps_comment ;;
  }

  measure: count {
    type: count
  }

  measure: total_available_quantity {
    type: sum
    sql: ${avail_qty} ;;
  }

  measure: total_supply_value {
    type: sum
    value_format_name: usd
    sql: ${TABLE}.ps_availqty * ${TABLE}.ps_supplycost ;;
  }

  measure: average_supply_cost {
    type: average
    value_format_name: usd
    sql: ${supply_cost} ;;
  }
}
