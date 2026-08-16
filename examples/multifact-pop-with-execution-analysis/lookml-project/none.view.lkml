view: none {
  # 0-row table used as the base view in OJOF explores
  derived_table: {
    sql: SELECT NULL FROM UNNEST([]) ;;
  }

  dimension: account_id {hidden: yes}
}
