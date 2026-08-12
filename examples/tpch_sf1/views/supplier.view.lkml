view: supplier {
  sql_table_name: `@{TPCH_DATASET}.supplier` ;;

  dimension: supp_key {
    primary_key: yes
    type: number
    sql: ${TABLE}.s_suppkey ;;
  }

  dimension: name {
    type: string
    sql: ${TABLE}.s_name ;;
  }

  dimension: address {
    type: string
    sql: ${TABLE}.s_address ;;
  }

  dimension: nation_key {
    type: number
    hidden: yes
    sql: ${TABLE}.s_nationkey ;;
  }

  dimension: phone {
    type: string
    sql: ${TABLE}.s_phone ;;
  }

  dimension: acct_bal {
    type: number
    value_format_name: usd
    sql: ${TABLE}.s_acctbal ;;
  }

  dimension: comment {
    type: string
    sql: ${TABLE}.s_comment ;;
  }

  measure: count {
    type: count
    drill_fields: [supp_key, name, phone, acct_bal]
  }

  measure: total_account_balance {
    type: sum
    value_format_name: usd
    sql: ${acct_bal} ;;
  }
}
