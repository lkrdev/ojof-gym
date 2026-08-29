# Task: TheLook E-Commerce Unified Retail Analytics

## Architecture Objective

You are tasked with building a unified LookML exploration model for our e-commerce business using the public dataset in BigQuery (dataset: `bigquery-public-data.thelook_ecommerce`).

Our business teams (Merchandising, Marketing, and Operations) need a single, intuitive Explore to answer combined business questions without navigating multiple fragmented models. Key reporting scenarios include:
- Comparing sales revenue and product profit margins against warehouse inventory valuation and available stock, sliced by product brand or category.
- Evaluating digital marketing impact by looking at web browsing event activity alongside actual order conversion value and customer volume by acquisition channel and customer geography.
- Monitoring order fulfillment health by tracking total orders placed against item-level returns and cancellations across user locations over time.

Please inspect the tables in `bigquery-public-data.thelook_ecommerce`. Design your LookML explore so that business users can seamlessly combine metrics across order items, warehouse inventory, web events, and order headers alongside shared dimensions (products, users, distribution centers, and common calendar dates) in single queries without duplicate metric aggregations, inflated row counts, or query performance issues.

## Scenario Metadata

- **Status**: draft
- **Target BigQuery Dataset**: `bigquery-public-data.thelook_ecommerce`
- **Anchor Date**: `N/A`

## Target User Questions & Analytics Goals

- **salesRevenueVsInventoryCostByCategory** ([Supported Target Question]):
  - Prompt: *"Create a query for the merchandising dashboard comparing total completed sales revenue against total inventory cost on hand, grouped by product category."*

- **webTrafficVsOrderRevenueByTrafficSource** ([Supported Target Question]):
  - Prompt: *"Create a marketing query comparing total web session events against total order sales revenue, grouped by user acquisition traffic source."*

- **orderVolumeVsReturnedItemsByState** ([Supported Target Question]):
  - Prompt: *"Create a fulfillment query comparing distinct order count against returned item count, grouped by customer state."*

- **unsupportedRealtimeServerLogs** ([Unsupported Scope Check]):
  - Prompt: *"Show real-time container CPU metrics and cluster node memory usage by minute."*


## Modeling Requirements & Quality Standards

1. Model the explore(s) to accurately fulfill the target business questions without causing metric duplication or query fanout errors.
2. Maintain high query performance across large datasets.
3. Validate LookML syntax and model consistency.
