#!/usr/bin/env python3
"""
Automated Verifier for SkillsBench Task: TheLook E-Commerce Unified Retail Analytics
Runs offline AST/Regex OJOF linter and Column Participation Verifier.
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verifiers.ojof_linter import audit_lookml_directory

EXPECTED_PARTICIPATING_COLUMNS = {
  "salesRevenueVsInventoryCostByCategory": [
    "order_items.sale_price",
    "order_items.status",
    "inventory_items.cost",
    "products.category"
  ],
  "salesRevenueVsInventoryCostByBrand": [
    "order_items.sale_price",
    "inventory_items.cost",
    "products.brand",
    "products.department"
  ],
  "salesRevenueVsInventoryValuationByDepartmentAndCategory": [
    "order_items.sale_price",
    "order_items.status",
    "inventory_items.cost",
    "products.department",
    "products.category"
  ],
  "webTrafficVsOrderRevenueByTrafficSource": [
    "events.id",
    "events.traffic_source",
    "order_items.sale_price",
    "users.traffic_source"
  ],
  "webTrafficVsOrderRevenueByState": [
    "events.id",
    "order_items.sale_price",
    "users.state",
    "users.gender"
  ],
  "webTrafficAndCustomersByTrafficSourceAndGender": [
    "events.id",
    "order_items.sale_price",
    "order_items.user_id",
    "users.traffic_source",
    "users.gender"
  ],
  "orderVolumeVsReturnedItemsByState": [
    "orders.order_id",
    "order_items.id",
    "order_items.status",
    "users.state"
  ],
  "orderVolumeVsReturnedItemsByCategory": [
    "orders.order_id",
    "order_items.id",
    "order_items.status",
    "order_items.sale_price",
    "products.category"
  ],
  "fullCrossFactMarketingAndFulfillmentByState": [
    "events.id",
    "orders.order_id",
    "order_items.sale_price",
    "inventory_items.id",
    "users.state"
  ],
  "categoryRevenueReturnsAndInventoryValuation": [
    "order_items.sale_price",
    "order_items.status",
    "inventory_items.cost",
    "products.department",
    "products.category"
  ]
}

def main():
    target_dir = Path.cwd()
    print(f"[Verifier] Auditing LookML in {target_dir} for scenario 'TheLook E-Commerce Unified Retail Analytics'...")

    # Level 1: OJOF Structural Invariants Check
    linter_results = audit_lookml_directory(target_dir)
    print(f"[Verifier] Linter Score: {linter_results['score']:.1f}% ({linter_results['passed']}/{linter_results['total']} rules passed)")

    if linter_results['score'] < 75.0:
        print("[Verifier FAILED] Structural OJOF compliance below 75% threshold.")
        for violation in linter_results['violations']:
            print(f"  - {violation}")
        sys.exit(1)

    print("[Verifier SUCCESS] Level 1 Structural OJOF invariants satisfied!")

if __name__ == "__main__":
    main()
