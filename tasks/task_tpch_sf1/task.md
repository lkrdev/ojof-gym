# Task: TPC-H SF1 Unified Supply Chain Analytics

## Architecture Objective

You are tasked with building a LookML exploration model for our wholesale supply chain and commerce data in BigQuery (dataset: `bigquery-public-data.tpch_sf1`).

Our business teams (Executive, Logistics, and Procurement) need a unified Explore where they can build combined reports and dashboards without hopping between separate disconnected explores. For example, our analysts need to:
- Compare overall order sales volume against line-item shipping discounts grouped by customer nation and date.
- Compare supplier parts inventory availability against total order demand grouped by geographic region.
- Track order placements, shipping milestones, and delivery receipts side-by-side along a unified event timeline.

Please inspect the underlying dataset tables in BigQuery. Ensure that your LookML explore model enables these combined queries accurately and performantly—avoiding fanout errors, duplicated sums, or slow query performance when metrics from different tables (like orders, lineitem events, and part-supplier inventory) are queried together alongside common dimensions (customer, nation, region, date).

## Scenario Metadata

- **Status**: draft
- **Target BigQuery Dataset**: `bigquery-public-data.tpch_sf1`
- **Anchor Date**: `N/A`

## Target User Questions & Analytics Goals

- **ordersVsShipmentsByNation** ([Supported Target Question]):
  - Prompt: *"Create a query for an executive dashboard showing total order revenue vs total shipped discount amount grouped by customer nation."*

- **inventoryVsOrderDemandByRegion** ([Supported Target Question]):
  - Prompt: *"Create a query comparing total part supply availability cost against total ordered price grouped by region."*

- **unsupportedIntradayStock** ([Unsupported Scope Check]):
  - Prompt: *"Show intra-day real-time stock ticks by minute for supplier inventory."*


## Modeling Requirements & Quality Standards

1. Model the explore(s) to accurately fulfill the target business questions without causing metric duplication or query fanout errors.
2. Maintain high query performance across large datasets.
3. Validate LookML syntax and model consistency.
