#!/usr/bin/env python3
"""
BigQuery Provisioning Script for Dataset: bigquery-public-data.thelook_ecommerce
Supports caching/reuse of existing dataset and tables to prevent costly rebuilds.
"""

import sys

DATASET_ID = "bigquery-public-data.thelook_ecommerce"
REUSE_EXISTING = True
LOCATION = "US"

def provision():
    print(f"[Provision BQ] Checking BigQuery dataset '{DATASET_ID}' (reuse_existing={REUSE_EXISTING})...")
    
    if REUSE_EXISTING:
        print(f"[Provision BQ] Table reuse enabled. Checking if dataset {DATASET_ID} exists...")
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



    except ImportError:
        print("[Provision BQ] google-cloud-bigquery library not installed. Skipping live BQ provisioning.")

if __name__ == "__main__":
    provision()
