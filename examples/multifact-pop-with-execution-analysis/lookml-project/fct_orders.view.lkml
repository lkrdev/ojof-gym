view: fct_orders {
  label: "Orders"

  sql_table_name: `my_dataset.orders_monthly_summary` ;;

  dimension: pk {
    primary_key: yes
    hidden: yes
    type: string
    sql: CONCAT(CAST(${TABLE}.account_id AS STRING), '|', CAST(${TABLE}.month_id AS STRING)) ;;
  }

  dimension: account_id {
    hidden: yes
    type: number
    sql: ${TABLE}.account_id ;;
  }

  dimension: month_id {
    hidden: yes
    type: number
    sql: ${TABLE}.month_id ;;
  }

  measure: gross_order_amount {
    group_label: "Gross Cost"
    label: "Total Gross Cost"
    type: sum
    sql: ${TABLE}.gross_order_amount ;;
    value_format_name: usd
  }

}
