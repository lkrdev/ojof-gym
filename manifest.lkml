project_name: "ojof-gym"

constant: CONNECTION_NAME {
  value: "looker-private-demo"
  export: override_optional
}

constant: TPCH_DATASET {
  value: "bigquery-public-data.tpch_sf1"
  export: override_optional
}

constant: CONNECTION {
  value: "looker-private-demo"
  export: override_optional
}

constant: REGION {
  value: "us"
  export: override_optional
}

constant: SCOPE {
  value: "PROJECT"
  export: override_optional
}

constant: BILLING_PROJECT_ID {
  value: " "
  export: override_optional
}

constant: RESERVATION_ADMIN_PROJECT  {
  value: " "
  export: override_optional
}

constant: MAX_JOB_LOOKBACK {
  value: "8 HOUR"
  export: override_optional
}

constant: PII_QUERY_TEXT {
  value: "HIDE"
  export: override_optional
}
