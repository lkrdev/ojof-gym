#!/usr/bin/env python3
"""
Rebuilds HTML and Markdown benchmark reports from persisted run exports in milliseconds.
Decoupled from remote Looker/BigQuery network calls for instant presentational iterations.
"""

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.generate_rich_artifacts import process_run_artifacts

def get_latest_run_dir(exports_base: Path) -> Path:
    runs = sorted([d for d in exports_base.glob("run_*") if d.is_dir()])
    if not runs:
        raise FileNotFoundError(f"No run exports found in {exports_base}")
    return runs[-1]

def rebuild_run_report(
    run_dir: Path,
    live_eval: bool = False
):
    print(f"[Report Rebuilder] Rebuilding report from saved artifacts in: {run_dir} (live_eval={live_eval})")
    process_run_artifacts(run_dir, live_eval=live_eval)
    print(f"[Report Rebuilder] Finished regenerating report for: {run_dir.name}")

def main():
    parser = argparse.ArgumentParser(description="Rebuild Benchmark Reports from Persisted Run Exports")
    parser.add_argument("run_dir", nargs="?", default=None, help="Path to run export dir (default: latest run in eval_exports/)")
    parser.add_argument("--live", action="store_true", help="Re-query Looker API & BigQuery over network tunnel (default: False / local instant)")
    args = parser.parse_args()

    exports_base = PROJECT_ROOT / "eval_exports"
    if args.run_dir:
        target_dir = Path(args.run_dir)
    else:
        target_dir = get_latest_run_dir(exports_base)

    rebuild_run_report(target_dir, live_eval=args.live)

if __name__ == "__main__":
    main()
