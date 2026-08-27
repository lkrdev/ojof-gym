view: region {
  sql_table_name: `@{TPCH_DATASET}.region` ;;

  dimension: region_key {
    primary_key: yes
    type: number
    sql: ${TABLE}.r_regionkey ;;
  }

  dimension: name {
    type: string
    sql: ${TABLE}.r_name ;;
  }

  dimension: comment {
    type: string
    sql: ${TABLE}.r_comment ;;
  }

  measure: count {
    type: count
    drill_fields: [region_key, name]
  }
}
