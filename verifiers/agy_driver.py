#!/usr/bin/env python3
"""
Antigravity CLI Agent Driver for OJOF-Gym multi-turn evaluation.
Executes multi-turn workflows (Turn 1: Baseline Architecture -> Turn 2: Question Maintenance)
in strict workspace isolation and tracks turn-level metrics.
"""

import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

AGY_BIN = (
    os.environ.get("AGY_BIN")
    or os.environ.get("AGENT_CLI_PATH")
    or shutil.which("agy")
    or shutil.which("antigravity")
    or shutil.which("cli")
    or "agy"
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def compute_lookml_diff(turn1_files: Dict[str, str], turn2_files: Dict[str, str]) -> Dict[str, Any]:
    """Computes line change metrics between Turn 1 and Turn 2 LookML files."""
    added_lines = 0
    deleted_lines = 0
    modified_files = []
    new_files = []

    all_keys = set(turn1_files.keys()).union(set(turn2_files.keys()))
    for k in all_keys:
        f1 = turn1_files.get(k, "")
        f2 = turn2_files.get(k, "")
        if not f1 and f2:
            new_files.append(k)
            added_lines += len(f2.splitlines())
        elif f1 and not f2:
            deleted_lines += len(f1.splitlines())
        elif f1 != f2:
            modified_files.append(k)
            diff = list(difflib.unified_diff(f1.splitlines(), f2.splitlines()))
            for line in diff:
                if line.startswith("+") and not line.startswith("+++"):
                    added_lines += 1
                elif line.startswith("-") and not line.startswith("---"):
                    deleted_lines += 1

    return {
        "lines_added": added_lines,
        "lines_deleted": deleted_lines,
        "total_lines_changed": added_lines + deleted_lines,
        "new_files": new_files,
        "modified_files": modified_files
    }

class AntigravityDriver:
    def __init__(
        self,
        model: str = "gemini-3.6-flash",
        skip_permissions: bool = True,
        effort: Optional[str] = None,
        output_format: str = "json"
    ):
        self.model = model
        self.skip_permissions = skip_permissions
        self.effort = effort
        self.output_format = output_format

    def execute_turn(
        self,
        workspace_dir: Path,
        prompt: str,
        turn_num: int = 1,
        skill_mode: str = "with-skill",
        dry_run: bool = False,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a single turn of interaction in the workspace.
        """
        cmd = [
            AGY_BIN,
            "--model", self.model,
            "--output-format", self.output_format,
        ]

        if self.effort and "3.6" not in self.model:
            cmd.extend(["--effort", self.effort])

        if self.skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        # In Turn 2, continue conversation if conversation_id is known
        if turn_num > 1 and conversation_id:
            cmd.extend(["--conversation", conversation_id])

        cmd.extend(["--print", prompt])

        if dry_run:
            return {
                "dry_run": True,
                "turn": turn_num,
                "status": "simulated_success",
                "usage": {"total_tokens": 0, "input_tokens": 0, "output_tokens": 0},
                "duration_seconds": 0
            }

        env = os.environ.copy()
        print(f"    [AntigravityDriver] Executing Turn {turn_num} ({skill_mode}) in {workspace_dir.name}...")
        try:
            res = subprocess.run(cmd, cwd=str(workspace_dir.resolve()), capture_output=True, text=True, env=env, timeout=600)
            try:
                data = json.loads(res.stdout)
                return {
                    "turn": turn_num,
                    "status": data.get("status", "success"),
                    "conversation_id": data.get("conversation_id", ""),
                    "usage": data.get("usage", {}),
                    "duration_seconds": data.get("duration_seconds", 0),
                    "response": data.get("response", ""),
                    "error": data.get("error", "")
                }
            except json.JSONDecodeError:
                return {
                    "turn": turn_num,
                    "status": "success",
                    "raw": res.stdout
                }
        except subprocess.TimeoutExpired:
            return {"turn": turn_num, "status": "timeout", "error": "Turn timed out after 600s"}
        except subprocess.CalledProcessError as e:
            return {"turn": turn_num, "status": "failed", "error": e.stderr or str(e)}

    def setup_workspace(
        self,
        workspace_dir: Path,
        task_dir: Path,
        skill_mode: str
    ):
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Skill isolation
        skills_dest = workspace_dir / ".agents" / "skills"
        if skill_mode == "with-skill":
            skills_src = PROJECT_ROOT / ".agents" / "skills" / "lookml-ojof"
            if not skills_src.exists():
                skills_src = task_dir / "environment" / "skills" / "lookml-ojof"
            if skills_src.exists():
                ojof_dest = skills_dest / "lookml-ojof"
                ojof_dest.mkdir(parents=True, exist_ok=True)
                shutil.copytree(skills_src, ojof_dest, dirs_exist_ok=True)
        else:
            if (workspace_dir / ".agents").exists():
                shutil.rmtree(workspace_dir / ".agents")
