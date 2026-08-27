#!/usr/bin/env python3
"""
Procedural Scenario Generator for OJOF-Gym benchmark harness.
Generates synthetic OJOF evaluation scenario JSON specs validating against scenario/schema.json.
"""

import argparse
import json
import random
import sys
from pathlib import Path

DOMAINS = [
    {
        "name": "ecommerce",
        "description": "Multi-fact e-commerce platform schema covering orders, order items, inventory snapshots, and web clickstream events.",
        "tables": {
            "customers": {
                "rows": 1000,
                "primary_key": ["customer_id"],
                "columns": {
                    "customer_id": { "type": "INT64", "generator": "sequence" },
                    "customer_name": { "type": "STRING", "generator": "full_name" },
                    "region": { "type": "STRING", "values": ["North America", "EMEA", "APAC", "LATAM"] }
                }
            },
            "products": {
                "rows": 250,
                "primary_key": ["product_id"],
                "columns": {
                    "product_id": { "type": "INT64", "generator": "sequence" },
                    "product_name": { "type": "STRING", "generator": "product_name" },
                    "category": { "type": "STRING", "values": ["Electronics", "Apparel", "Home", "Beauty"] }
                }
            },
            "orders": {
                "rows": 50000,
                "primary_key": ["order_id"],
                "columns": {
                    "order_id": { "type": "INT64", "generator": "sequence" },
                    "order_timestamp": { "type": "TIMESTAMP", "start_date": "2026-01-01", "end_date": "2026-08-31" },
                    "customer_id": { "type": "INT64", "foreign_key": "customers.customer_id" },
                    "total_amount": { "type": "NUMERIC", "min": 10.0, "max": 1500.0 }
                }
            },
            "order_items": {
                "rows": 120000,
                "primary_key": ["order_item_id"],
                "columns": {
                    "order_item_id": { "type": "INT64", "generator": "sequence" },
                    "order_id": { "type": "INT64", "foreign_key": "orders.order_id" },
                    "product_id": { "type": "INT64", "foreign_key": "products.product_id" },
                    "shipped_at": { "type": "TIMESTAMP", "start_date": "2026-01-01", "end_date": "2026-08-31" },
                    "item_price": { "type": "NUMERIC", "min": 5.0, "max": 500.0 },
                    "discount_amount": { "type": "NUMERIC", "min": 0.0, "max": 50.0 }
                }
            },
            "inventory_snapshots": {
                "rows": 60000,
                "primary_key": ["snapshot_date", "product_id"],
                "columns": {
                    "snapshot_date": { "type": "DATE", "start_date": "2026-01-01", "end_date": "2026-08-31" },
                    "product_id": { "type": "INT64", "foreign_key": "products.product_id" },
                    "stock_quantity": { "type": "NUMERIC", "min": 0.0, "max": 2000.0 }
                }
            }
        },
        "questions": {
            "orderRevenueVsItemDiscounts": {
                "supported": True,
                "prompt": "Create a query showing total order revenue vs total item discount amounts grouped by customer region.",
                "expectation": {
                    "participatingColumns": [
                        "orders.total_amount",
                        "order_items.discount_amount",
                        "customers.region"
                    ]
                }
            },
            "inventoryVsSalesDemand": {
                "supported": True,
                "prompt": "Create a query comparing daily inventory stock levels against order revenue by product category.",
                "expectation": {
                    "participatingColumns": [
                        "inventory_snapshots.stock_quantity",
                        "orders.total_amount",
                        "products.category"
                    ]
                }
            }
        }
    }
]

def generate_scenario(scenario_id: str, num_facts: int = 2, complexity: str = "medium", seed: int = 42) -> dict:
    random.seed(seed)
    domain = random.choice(DOMAINS)
    
    spec = {
        "status": "draft",
        "title": f"Synthetic {domain['name'].capitalize()} Multi-Fact Explore ({num_facts} Facts)",
        "description": domain["description"],
        "bigquery": {
            "dataset": f"ojof_synth_{scenario_id}",
            "location": "US",
            "anchor_date": "2026-08-31",
            "reuse_existing": True
        },
        "architecturePrompt": f"You are tasked with designing a unified multi-fact LookML modeling layer for a multi-channel {domain['name']} platform in BigQuery. The platform tracks operational activities across disparate event lifecycles.\n\nPlease introspect the dataset tables and schemas directly in BigQuery. Key operational event tables record activities at distinct grains and event lifecycles. Your goal is to design a performant LookML architecture (such as an Outer Join On False / OJOF multi-fact explore) that allows seamless cross-fact reporting across these disparate lifecycles without introducing cartesian fanouts, double-counting, or query performance degradation.",
        "userQuestions": domain["questions"],
        "tables": domain["tables"]
    }
    return spec

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic OJOF scenario specs.")
    parser.add_argument("--id", type=str, default="synth_01", help="Scenario ID (snake_case)")
    parser.add_argument("--facts", type=int, default=2, help="Number of fact tables (2 to 4)")
    parser.add_argument("--complexity", type=str, default="medium", choices=["basic", "medium", "complex"])
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--out-dir", dest="out_dir", type=str, default="scenario/scenarios/synthetic", help="Output directory")

    args = parser.parse_args()
    spec = generate_scenario(args.id, num_facts=args.facts, complexity=args.complexity, seed=args.seed)
    
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.id}.json"
    
    with open(out_path, "w") as f:
        json.dump(spec, f, indent=2)
        
    print(f"Generated scenario spec: {out_path}")

if __name__ == "__main__":
    main()
