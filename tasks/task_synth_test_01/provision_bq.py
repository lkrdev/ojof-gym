#!/usr/bin/env python3
"""
BigQuery Provisioning Script for Scenario: synth_test_01
Supports caching/reuse of existing dataset and tables to prevent costly rebuilds.
"""

import sys

DATASET_ID = "ojof_synth_synth_test_01"
REUSE_EXISTING = True
LOCATION = "US"

def provision():
    print(f"[Provision BQ] Checking BigQuery dataset '{DATASET_ID}' (reuse_existing={REUSE_EXISTING})...")
    
    if REUSE_EXISTING:
        print(f"[Provision BQ] Table reuse enabled. Checking if tables exist in {DATASET_ID}...")
        if DATASET_ID.startswith("bigquery-public-data") or "synth" not in DATASET_ID:
            print(f"[Provision BQ] Public/Pre-existing dataset '{DATASET_ID}' detected. Skipping DDL execution.")
            return

    try:
        from google.cloud import bigquery
        client = bigquery.Client()
        dataset_ref = client.dataset(DATASET_ID)
        try:
            client.get_dataset(dataset_ref)
            print(f"[Provision BQ] Dataset {DATASET_ID} already exists.")
        except Exception:
            print(f"[Provision BQ] Creating dataset {DATASET_ID} in location {LOCATION}...")
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = LOCATION
            client.create_dataset(dataset, exists_ok=True)


        sql_fact_inventory_snapshots = """
        CREATE TABLE IF NOT EXISTS `ojof_synth_synth_test_01.inventory_snapshots` AS
        SELECT
          1 AS product_id,
          CURRENT_TIMESTAMP() AS snapshot_date,
          100.0 AS amount
        FROM UNNEST(GENERATE_ARRAY(1, 100)) AS id;
        """
        try:
            client.query(sql_fact_inventory_snapshots).result()
            print("[Provision BQ] Verified table 'inventory_snapshots'.")
        except Exception as e:
            print(f"[Provision BQ Warning] Could not provision table 'inventory_snapshots': {e}")

        sql_fact_orders = """
        CREATE TABLE IF NOT EXISTS `ojof_synth_synth_test_01.orders` AS
        SELECT
          1 AS order_id,
          CURRENT_TIMESTAMP() AS order_timestamp,
          100.0 AS amount
        FROM UNNEST(GENERATE_ARRAY(1, 100)) AS id;
        """
        try:
            client.query(sql_fact_orders).result()
            print("[Provision BQ] Verified table 'orders'.")
        except Exception as e:
            print(f"[Provision BQ Warning] Could not provision table 'orders': {e}")

        sql_fact_order_items = """
        CREATE TABLE IF NOT EXISTS `ojof_synth_synth_test_01.order_items` AS
        SELECT
          1 AS order_id,
          CURRENT_TIMESTAMP() AS shipped_at,
          100.0 AS amount
        FROM UNNEST(GENERATE_ARRAY(1, 100)) AS id;
        """
        try:
            client.query(sql_fact_order_items).result()
            print("[Provision BQ] Verified table 'order_items'.")
        except Exception as e:
            print(f"[Provision BQ Warning] Could not provision table 'order_items': {e}")


    except ImportError:
        print("[Provision BQ] google-cloud-bigquery library not installed. Skipping live BQ provisioning.")

if __name__ == "__main__":
    provision()
