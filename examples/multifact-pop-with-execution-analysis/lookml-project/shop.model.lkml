include: "*.view.lkml"

connection: "my_connection"

explore: store_multifact_pop {

  from:  none
  view_name: none

  always_filter: {filters: [
    date.date_filter: "3 months ago for 3 months",
    date_prior.date_filter: "15 months ago for 3 months"
  ]}

  join: orders_current {
    from: fct_orders
    view_label: "Orders"
    relationship: one_to_one
    type: full_outer
    sql_table_name: (
      SELECT * FROM ${fct_orders.SQL_TABLE_NAME}
      WHERE order_date >= {% date_start date.date_filter %}
        AND order_date <= {% date_end   date.date_filter %}
    );;
    sql_on: FALSE;;
  }

  join: orders_prior {
    from: fct_orders
    view_label: "Orders (Prior)"
    relationship: one_to_one
    type: full_outer
    sql_table_name: (
      SELECT * FROM ${fct_orders.SQL_TABLE_NAME}
      WHERE order_date >= {% date_start date_prior.date_filter %}
        AND order_date <= {% date_end   date_prior.date_filter %}
    );;
    sql_on: FALSE;;
  }

  join: plans_current {
    from: fct_plans
    view_label: "Plans"
    relationship: one_to_one
    type: full_outer
    sql_table_name: (
      SELECT * FROM ${fct_plans.SQL_TABLE_NAME}
      WHERE plan_date >= {% date_start date.date_filter %}
        AND plan_date <= {% date_end   date.date_filter %}
    );;
    sql_on: FALSE;;
  }

  join: plans_prior {
    from: fct_plans
    view_label: "Plans (prior)"
    relationship: one_to_one
    type: full_outer
    sql_table_name: (
      SELECT * FROM ${fct_plans.SQL_TABLE_NAME}
      WHERE plan_date >= {% date_start date_prior.date_filter %}
        AND plan_date <= {% date_end   date_prior.date_filter %}
    );;
    sql_on: FALSE;;
  }

  join: dim_account {
    type: left_outer
    relationship: many_to_one
    sql_on: ${dim_account.account_id} = COALESCE(
      NULL
      {% if orders_current._in_query %}, orders_current.account_id {% endif %}
      {% if orders_prior._in_query   %}, orders_prior.account_id   {% endif %}
      {% if plans_current._in_query  %}, plans_current.account_id  {% endif %}
      {% if plans_prior._in_query    %}, plans_prior.account_id    {% endif %}
    );;
  }

  join: date {
    view_label: "[Date]"
    relationship: one_to_one
    type: cross
    sql_table_name: UNNEST([COALESCE(
      CAST(NULL AS DATE)
        {% if orders_current._in_query %}, orders_current.order_date {% endif %}
        {% if plans_current._in_query  %}, plans_current.plan_date  {% endif %}
      )]);;
  }

  join: date_prior {
    from: date
    view_label: "[Date] (Prior)"
    relationship: one_to_one
    type: cross
    sql_table_name: UNNEST([COALESCE(
      CAST(NULL AS DATE)
        {% if orders_prior._in_query %}, orders_prior.order_date {% endif %}
        {% if plans_prior._in_query  %}, plans_prior.plan_date   {% endif %}
      )]);;
  }

}

