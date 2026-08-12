view: customer {
  sql_table_name: `@{TPCH_DATASET}.customer` ;;

  dimension: cust_key {
    primary_key: yes
    type: number
    sql: ${TABLE}.c_custkey ;;
  }

  dimension: name {
    type: string
    sql: ${TABLE}.c_name ;;
  }

  dimension: address {
    type: string
    sql: ${TABLE}.c_address ;;
  }

  dimension: nation_key {
    type: number
    hidden: yes
    sql: ${TABLE}.c_nationkey ;;
  }

  dimension: phone {
    type: string
    sql: ${TABLE}.c_phone ;;
  }

  dimension: acct_bal {
    type: number
    value_format_name: usd
    sql: ${TABLE}.c_acctbal ;;
  }

  dimension: mkt_segment {
    type: string
    sql: ${TABLE}.c_mktsegment ;;
  }

  dimension: comment {
    type: string
    sql: ${TABLE}.c_comment ;;
  }

  measure: count {
    type: count
    drill_fields: [cust_key, name, mkt_segment, acct_bal]
  }

  measure: total_account_balance {
    type: sum
    value_format_name: usd
    sql: ${acct_bal} ;;
  }
}
