#!/usr/bin/env python3
"""
OJOF-Gym Deterministic Environment Validator.
Verifies that all required execution binaries, local tools, Looker API connectivity,
and BigQuery service account authentication components are functional.
"""

import sys
import os
import shutil
import subprocess
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def run_cmd(cmd: List[str], env: Dict[str, str] = None, timeout: int = 15) -> Tuple[int, str, str]:
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env or os.environ.copy()
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

def check_core_binaries() -> List[Dict[str, Any]]:
    checks = []
    # 1. agy
    agy_path = shutil.which("agy") or str(Path.home() / ".local" / "bin" / "agy")
    if Path(agy_path).exists() and os.access(agy_path, os.X_OK):
        rc, out, err = run_cmd([agy_path, "--help"], timeout=30)
        checks.append({
            "component": "Agent Driver (agy)",
            "status": "PASS" if rc == 0 else "FAIL",
            "details": f"Found at {agy_path} (Exit {rc})" if rc == 0 else f"Failed running {agy_path}: {err or out}"
        })
    else:
        checks.append({
            "component": "Agent Driver (agy)",
            "status": "FAIL",
            "details": f"Binary not found or not executable at {agy_path}"
        })

    # 2. bq
    bq_path = shutil.which("bq")
    if bq_path:
        rc, out, err = run_cmd([bq_path, "version"], timeout=10)
        checks.append({
            "component": "BigQuery CLI (bq)",
            "status": "PASS" if rc == 0 else "FAIL",
            "details": f"Found at {bq_path}" if rc == 0 else f"Failed running bq: {err or out}"
        })
    else:
        checks.append({
            "component": "BigQuery CLI (bq)",
            "status": "FAIL",
            "details": "bq CLI binary not found in PATH"
        })

    # 3. looker-cli
    looker_cli = (
        shutil.which("looker-cli")
        or str(PROJECT_ROOT / "tools" / "bin" / "looker-cli")
        or str(Path.home() / ".local" / "bin" / "looker-cli")
    )
    if Path(looker_cli).exists() and os.access(looker_cli, os.X_OK):
        checks.append({
            "component": "Looker CLI (looker-cli)",
            "status": "PASS",
            "details": f"Found executable binary at {looker_cli}"
        })
    else:
        checks.append({
            "component": "Looker CLI (looker-cli)",
            "status": "FAIL",
            "details": f"Binary not found or not executable at {looker_cli}"
        })

    return checks

def check_project_tools() -> List[Dict[str, Any]]:
    checks = []
    tools_bin = PROJECT_ROOT / "tools" / "bin"

    # 1. tools/bin/lookml-parser
    parser_path = tools_bin / "lookml-parser"
    if parser_path.exists() and os.access(parser_path, os.X_OK):
        # Test on dummy content via tempfile
        with tempfile.NamedTemporaryFile(suffix=".lkml", mode="w", delete=False) as tf:
            tf.write('view: test_view { dimension: id { type: number sql: ${TABLE}.id ;; } }\n')
            temp_lkml = tf.name

        rc, out, err = run_cmd([str(parser_path), temp_lkml, "--validation-mode"])
        try:
            os.remove(temp_lkml)
        except Exception:
            pass

        if rc == 0 and "VALIDATION_PASSED" in out:
            checks.append({
                "component": "LookML Parser (tools/bin/lookml-parser)",
                "status": "PASS",
                "details": "Parsed sample LookML file successfully with 0 errors"
            })
        else:
            checks.append({
                "component": "LookML Parser (tools/bin/lookml-parser)",
                "status": "FAIL",
                "details": f"Parser execution failed (Exit {rc}): {err or out}"
            })
    else:
        checks.append({
            "component": "LookML Parser (tools/bin/lookml-parser)",
            "status": "FAIL",
            "details": f"File not found or missing +x permission at {parser_path}"
        })

    # 2. tools/bin/looker-sync
    sync_path = tools_bin / "looker-sync"
    if sync_path.exists() and os.access(sync_path, os.X_OK):
        rc, out, err = run_cmd([str(sync_path), "--help"])
        checks.append({
            "component": "Looker Sync (tools/bin/looker-sync)",
            "status": "PASS" if rc == 0 else "FAIL",
            "details": "Binary is executable and responds to --help" if rc == 0 else f"Failed: {err or out}"
        })
    else:
        checks.append({
            "component": "Looker Sync (tools/bin/looker-sync)",
            "status": "FAIL",
            "details": f"File not found or missing +x permission at {sync_path}"
        })

    return checks

def check_looker_api() -> List[Dict[str, Any]]:
    checks = []
    from verifiers.looker_evaluator import LookerEvaluator
    evaluator = LookerEvaluator()

    if not evaluator.is_available():
        checks.append({
            "component": "Looker API Availability",
            "status": "FAIL",
            "details": "LookerEvaluator could not locate looker-cli"
        })
        return checks

    # Check authentication and token validity
    authenticated = evaluator.ensure_authenticated()
    if authenticated:
        checks.append({
            "component": "Looker API Connectivity & Session",
            "status": "PASS",
            "details": "Successfully connected and verified active Looker session"
        })
    else:
        checks.append({
            "component": "Looker API Connectivity & Session",
            "status": "FAIL",
            "details": "Looker authentication check failed or connection timed out"
        })

    return checks

def check_bigquery_connectivity() -> List[Dict[str, Any]]:
    checks = []
    from eval.run_benchmark import load_local_env, check_service_account_connectivity
    load_local_env()

    ok, msg = check_service_account_connectivity()
    checks.append({
        "component": "BigQuery & Service Account Impersonation",
        "status": "PASS" if ok else "FAIL",
        "details": msg
    })
    return checks

def main():
    print("=======================================================")
    print("      OJOF-Gym Deterministic Environment Validator     ")
    print("=======================================================\n")

    all_checks = []
    all_checks.extend(check_core_binaries())
    all_checks.extend(check_project_tools())
    all_checks.extend(check_looker_api())
    all_checks.extend(check_bigquery_connectivity())

    total = len(all_checks)
    passed = sum(1 for c in all_checks if c["status"] == "PASS")
    failed = total - passed

    for c in all_checks:
        icon = "\x1b[32m[PASS]\x1b[0m" if c["status"] == "PASS" else "\x1b[31m[FAIL]\x1b[0m"
        print(f"{icon} {c['component']}")
        print(f"       {c['details']}")

    print("\n-------------------------------------------------------")
    print(f"Summary: {passed}/{total} checks passed.")
    if failed > 0:
        print(f"\x1b[31mStatus: NOT READY ({failed} failure(s))\x1b[0m")
        sys.exit(1)
    else:
        print(f"\x1b[32mStatus: ALL CHECKS PASSED - Environment is ready for evaluation.\x1b[0m")
        sys.exit(0)

if __name__ == "__main__":
    main()
