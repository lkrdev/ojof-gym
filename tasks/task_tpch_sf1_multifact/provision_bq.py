#!/usr/bin/env python3
"""
BigQuery Provisioning Script for Scenario: tpch_sf1_multifact
Supports caching/reuse of existing dataset and tables to prevent costly rebuilds.
"""

import sys

DATASET_ID = "bigquery-public-data.tpch_sf1"
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


        sql_fact_orders = """
        CREATE TABLE IF NOT EXISTS `bigquery-public-data.tpch_sf1.orders` AS
        SELECT
          1 AS o_orderkey,
          CURRENT_TIMESTAMP() AS o_orderdate,
          100.0 AS amount
        FROM UNNEST(GENERATE_ARRAY(1, 1500000)) AS id;
        """
        try:
            client.query(sql_fact_orders).result()
            print("[Provision BQ] Verified table 'orders'.")
        except Exception as e:
            print(f"[Provision BQ Warning] Could not provision table 'orders': {e}")

        sql_fact_lineitem_shipped = """
        CREATE TABLE IF NOT EXISTS `bigquery-public-data.tpch_sf1.lineitem_shipped` AS
        SELECT
          1 AS l_orderkey,
          CURRENT_TIMESTAMP() AS l_shipdate,
          100.0 AS amount
        FROM UNNEST(GENERATE_ARRAY(1, 6000000)) AS id;
        """
        try:
            client.query(sql_fact_lineitem_shipped).result()
            print("[Provision BQ] Verified table 'lineitem_shipped'.")
        except Exception as e:
            print(f"[Provision BQ Warning] Could not provision table 'lineitem_shipped': {e}")

        sql_fact_lineitem_received = """
        CREATE TABLE IF NOT EXISTS `bigquery-public-data.tpch_sf1.lineitem_received` AS
        SELECT
          1 AS l_orderkey,
          CURRENT_TIMESTAMP() AS l_receiptdate,
          100.0 AS amount
        FROM UNNEST(GENERATE_ARRAY(1, 6000000)) AS id;
        """
        try:
            client.query(sql_fact_lineitem_received).result()
            print("[Provision BQ] Verified table 'lineitem_received'.")
        except Exception as e:
            print(f"[Provision BQ Warning] Could not provision table 'lineitem_received': {e}")

        sql_fact_partsupp = """
        CREATE TABLE IF NOT EXISTS `bigquery-public-data.tpch_sf1.partsupp` AS
        SELECT
          1 AS ps_partkey,
          CURRENT_TIMESTAMP() AS ps_availqty,
          100.0 AS amount
        FROM UNNEST(GENERATE_ARRAY(1, 800000)) AS id;
        """
        try:
            client.query(sql_fact_partsupp).result()
            print("[Provision BQ] Verified table 'partsupp'.")
        except Exception as e:
            print(f"[Provision BQ Warning] Could not provision table 'partsupp': {e}")


    except ImportError:
        print("[Provision BQ] google-cloud-bigquery library not installed. Skipping live BQ provisioning.")

if __name__ == "__main__":
    provision()
