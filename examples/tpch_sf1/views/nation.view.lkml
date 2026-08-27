view: nation {
  sql_table_name: `@{TPCH_DATASET}.nation` ;;

  dimension: nation_key {
    primary_key: yes
    type: number
    sql: ${TABLE}.n_nationkey ;;
  }

  dimension: name {
    type: string
    sql: ${TABLE}.n_name ;;
  }

  dimension: region_key {
    type: number
    hidden: yes
    sql: ${TABLE}.n_regionkey ;;
  }

  dimension: comment {
    type: string
    sql: ${TABLE}.n_comment ;;
  }

  measure: count {
    type: count
    drill_fields: [nation_key, name]
  }
}
