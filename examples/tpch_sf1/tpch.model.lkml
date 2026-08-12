connection: "@{CONNECTION_NAME}"

datagroup: tpch_default_datagroup {
  max_cache_age: "24 hours"
  sql_trigger: SELECT CURRENT_DATE() ;;
}

persist_with: tpch_default_datagroup

include: "/examples/tpch_sf1/explores/*.explore.lkml"
include: "/examples/tpch_sf1/tpch.aa.lkml"
