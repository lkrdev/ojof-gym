view: part {
  sql_table_name: `@{TPCH_DATASET}.part` ;;

  dimension: part_key {
    primary_key: yes
    type: number
    sql: ${TABLE}.p_partkey ;;
  }

  dimension: name {
    type: string
    sql: ${TABLE}.p_name ;;
  }

  dimension: mfgr {
    type: string
    sql: ${TABLE}.p_mfgr ;;
  }

  dimension: brand {
    type: string
    sql: ${TABLE}.p_brand ;;
  }

  dimension: type {
    type: string
    sql: ${TABLE}.p_type ;;
  }

  dimension: size {
    type: number
    sql: ${TABLE}.p_size ;;
  }

  dimension: container {
    type: string
    sql: ${TABLE}.p_container ;;
  }

  dimension: retail_price {
    type: number
    value_format_name: usd
    sql: ${TABLE}.p_retailprice ;;
  }

  dimension: comment {
    type: string
    sql: ${TABLE}.p_comment ;;
  }

  measure: count {
    type: count
    drill_fields: [part_key, name, brand, type, retail_price]
  }

  measure: average_retail_price {
    type: average
    value_format_name: usd
    sql: ${retail_price} ;;
  }
}
