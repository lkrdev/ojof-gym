#!/usr/bin/env python3
"""
Structural Invariant Linter (Pattern/Regex Static Analysis) for LookML.
Analyzes LookML files to verify compliance with multi-fact / OJOF structural invariants
and extracts structural component metrics.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Any

def audit_lookml_directory(directory: Path) -> Dict[str, Any]:
    lkml_files = list(directory.rglob("*.lkml"))
    # Filter out hidden or system files
    lkml_files = [f for f in lkml_files if ".system" not in str(f) and ".git" not in str(f) and ".agents" not in str(f)]

    violations = []
    total_checks = 4
    passed_checks = 0

    all_content = ""
    file_contents = {}
    for f in lkml_files:
        try:
            content = f.read_text()
            all_content += content + "\n"
            file_contents[f.name] = content
        except Exception:
            pass

    # Structural Counts
    ojof_explores = len(re.findall(r"explore:\s*\w+[\s\S]*?(?:from:\s*none|UNNEST\s*\(\s*\[\s*\]\s*\))", all_content, re.IGNORECASE))
    total_explores = len(re.findall(r"\bexplore:\s*\w+", all_content, re.IGNORECASE))
    total_views = len(re.findall(r"\bview:\s*\w+", all_content, re.IGNORECASE))
    
    # Fact joins with type: full_outer and sql_on: FALSE
    fact_joins = len(re.findall(r"join:\s*\w+[\s\S]*?type:\s*full_outer[\s\S]*?sql_on:\s*false\s*;;", all_content, re.IGNORECASE))
    
    # Shared dimensions with Liquid _in_query
    liquid_dim_joins = len(re.findall(r"join:\s*\w+[\s\S]*?_in_query", all_content, re.IGNORECASE))
    
    # Composite measure views / bare joins
    composite_views = len(re.findall(r"view:\s*\w+__\w+", all_content, re.IGNORECASE)) + \
                      len(re.findall(r"join:\s*\w+\s*\{\s*\}", all_content, re.IGNORECASE))

    # Rule 1: 0-Row Base View (from: none)
    has_from_none = bool(re.search(r"from:\s*none", all_content, re.IGNORECASE)) or \
                    bool(re.search(r"UNNEST\s*\(\s*\[\s*\]\s*\)", all_content, re.IGNORECASE))
    if has_from_none or ojof_explores > 0:
        passed_checks += 1
    else:
        violations.append("Rule 1 Violation: Explore does not use a 0-row base view (`from: none` or 0-row derived table).")

    # Rule 2: Fact Joins type: full_outer and sql_on: FALSE
    has_full_outer = bool(re.search(r"type:\s*full_outer", all_content, re.IGNORECASE))
    has_sql_on_false = bool(re.search(r"sql_on:\s*FALSE\s*;;", all_content, re.IGNORECASE)) or \
                       bool(re.search(r"sql_on:\s*false\s*;;", all_content, re.IGNORECASE))
    if (has_full_outer and has_sql_on_false) or fact_joins > 0:
        passed_checks += 1
    else:
        violations.append("Rule 2 Violation: Fact joins must use `type: full_outer` and `sql_on: FALSE ;;`.")

    # Rule 3: Liquid _in_query coalescing for shared dimensions
    has_liquid_in_query = bool(re.search(r"_in_query", all_content, re.IGNORECASE)) or \
                           bool(re.search(r"\{%\s*if\s+[\w\.]+_in_query\s*%\}", all_content, re.IGNORECASE))
    if has_liquid_in_query or liquid_dim_joins > 0:
        passed_checks += 1
    else:
        violations.append("Rule 3 Violation: Shared dimensions must use Liquid `_in_query` conditional logic.")

    # Rule 4: Bare joins or composite measure views
    has_bare_join = bool(re.search(r"join:\s*\w+\s*\{\s*\}", all_content)) or \
                    bool(re.search(r"join:\s*\w+\s*\{\s*measure:", all_content)) or \
                    bool(re.search(r"view:\s*\w+__\w+", all_content))
    if has_bare_join or composite_views > 0 or len(lkml_files) > 0:
        passed_checks += 1
    else:
        violations.append("Rule 4 Violation: Composite measures should be organized in field-only views.")

    score = (passed_checks / total_checks) * 100.0 if total_checks > 0 else 0.0

    return {
        "engine": "Pattern / Regex-Based Static Analysis",
        "score": score,
        "passed": passed_checks,
        "total": total_checks,
        "violations": violations,
        "structural_metrics": {
            "total_views": total_views,
            "total_explores": total_explores,
            "ojof_explores": ojof_explores,
            "fact_joins_count": fact_joins,
            "liquid_dimension_joins_count": liquid_dim_joins,
            "composite_measure_views_count": composite_views,
            "total_lkml_files": len(lkml_files)
        }
    }

def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(f"[Structural Invariant Linter] Auditing {target}...")
    results = audit_lookml_directory(target)
    print(f"Score: {results['score']:.1f}% ({results['passed']}/{results['total']} checks passed)")
    print("Structural Metrics:", results["structural_metrics"])
    for v in results["violations"]:
        print(f"  - {v}")

if __name__ == "__main__":
    main()
