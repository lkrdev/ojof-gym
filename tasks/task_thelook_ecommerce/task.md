# Task: TheLook E-Commerce Unified Retail Analytics

## Architecture Objective

You are tasked with building a unified LookML exploration model for our e-commerce business using the public dataset in BigQuery (dataset: `bigquery-public-data.thelook_ecommerce`).

Our business teams (Merchandising, Marketing, and Operations) need a single, intuitive Explore to answer combined business questions without navigating multiple fragmented models. Key reporting scenarios include:
- Comparing sales revenue and product profit margins against warehouse inventory valuation and available stock, sliced by product brand or category.
- Evaluating digital marketing impact by looking at web browsing event activity alongside actual order conversion value and customer volume by acquisition channel and customer geography.
- Monitoring order fulfillment health by tracking total orders placed against item-level returns and cancellations across user locations over time.

Please inspect the tables in `bigquery-public-data.thelook_ecommerce`. Design your LookML explore so that business users can seamlessly combine metrics across order items, warehouse inventory, web events, and order headers alongside shared dimensions (products, users, distribution centers, and common calendar dates) in single queries without duplicate metric aggregations, inflated row counts, or query performance issues.

## Scenario Metadata

- **Status**: active
- **Target BigQuery Dataset**: `bigquery-public-data.thelook_ecommerce`
- **Anchor Date**: `N/A`

## Target User Questions & Analytics Goals

- **salesRevenueVsInventoryCostByCategory** ([Supported Target Question]):
  - Prompt: *"Compare total completed sales revenue against total warehouse inventory cost on hand, grouped by product category."*

- **salesRevenueVsInventoryCostByBrand** ([Supported Target Question]):
  - Prompt: *"Compare total sales revenue against total inventory cost on hand, grouped by product brand for items in the Men department."*

- **salesRevenueVsInventoryValuationByDepartmentAndCategory** ([Supported Target Question]):
  - Prompt: *"Compare total sales revenue and total inventory cost across product department and category for completed transactions."*

- **webTrafficVsOrderRevenueByTrafficSource** ([Supported Target Question]):
  - Prompt: *"Compare total web browsing events and distinct visitor sessions against total order sales revenue, grouped by user acquisition traffic source."*

- **webTrafficVsOrderRevenueByState** ([Supported Target Question]):
  - Prompt: *"Compare total web event traffic against total order sales revenue, grouped by customer state for female customers."*

- **webTrafficAndCustomersByTrafficSourceAndGender** ([Supported Target Question]):
  - Prompt: *"Analyze total web event traffic, distinct purchasing customers count, and total sales revenue across user traffic source and customer gender."*

- **orderVolumeVsReturnedItemsByState** ([Supported Target Question]):
  - Prompt: *"Compare distinct order volume, total line items ordered, and returned item count, grouped by customer state."*

- **orderVolumeVsReturnedItemsByCategory** ([Supported Target Question]):
  - Prompt: *"Compare distinct orders placed against returned items count, grouped by product category for items with non-zero sale price."*

- **fullCrossFactMarketingAndFulfillmentByState** ([Supported Target Question]):
  - Prompt: *"Provide a comprehensive cross-department summary comparing web browsing events, distinct placed orders, total sales revenue, and warehouse inventory items, grouped by customer state."*

- **categoryRevenueReturnsAndInventoryValuation** ([Supported Target Question]):
  - Prompt: *"Evaluate merchandising health by reporting total sales revenue, total returned items count, and total warehouse inventory valuation, grouped by product department and category."*

- **unsupportedRealtimeServerLogs** ([Unsupported Scope Check]):
  - Prompt: *"Show real-time container CPU metrics and cluster node memory usage by minute."*


## Architectural Instructions & Best Practices

1. Use a 0-row base view (`from: none`) with `derived_table: { sql: SELECT NULL FROM UNNEST([]) ;; }`.
2. Join all operational fact tables as peer branches with `type: full_outer`, `relationship: one_to_one`, and `sql_on: FALSE ;;`.
3. Coalesce shared timestamp/date columns (`codim_date`) across active fact streams.
4. Bind shared dimension joins using Liquid conditional logic (`{% if ..._in_query %}`).
5. Organize composite measures into a field-only view connected with a bare join.
