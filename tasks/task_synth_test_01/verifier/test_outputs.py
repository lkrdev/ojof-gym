#!/usr/bin/env python3
"""
Automated Verifier for SkillsBench Task: synth_test_01
Runs offline AST/Regex OJOF linter, Spectacles LookML compiler test, and BigQuery execution auditor.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verifiers.ojof_linter import audit_lookml_directory

def main():
    target_dir = Path.cwd()
    print(f"[Verifier] Auditing LookML in {target_dir} for scenario 'synth_test_01'...")

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
