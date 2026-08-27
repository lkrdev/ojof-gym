#!/usr/bin/env python3
"""
Antigravity CLI Agent Driver for OJOF-Gym evaluation harness.
Wraps local `agy` binary execution for automated benchmark runs.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional

AGY_BIN = (
    os.environ.get("AGY_BIN")
    or shutil.which("agy")
    or shutil.which("antigravity")
    or "/google/bin/releases/jetski-devs/tools/cli"
)

class AntigravityDriver:
    def __init__(
        self,
        model: str = "gemini-3.6-flash",
        skip_permissions: bool = False,
        effort: str = "medium",
        output_format: str = "json"
    ):
        self.model = model
        self.skip_permissions = skip_permissions
        self.effort = effort
        self.output_format = output_format

    def run_task(
        self,
        task_dir: Path,
        prompt: str,
        skill_mode: str = "with-skill",
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Executes agy non-interactively against a task directory.
        """
        cmd = [
            AGY_BIN,
            "--model", self.model,
            "--effort", self.effort,
            "--output-format", self.output_format,
            "--add-dir", str(task_dir.resolve()),
        ]

        if self.skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        if skill_mode == "no-skill":
            # Pass flag or point to directory without skill
            cmd.append("--disable-slash-commands")

        cmd.extend(["--print", prompt])

        if dry_run:
            print(f"[AntigravityDriver Dry Run] Prepared command:\n  {' '.join(cmd)}")
            return {
                "dry_run": True,
                "command": cmd,
                "status": "simulated_success",
                "output": "Dry run execution complete. No dangerous permission flags executed."
            }

        # Set up isolated execution environment with agent-specific credentials
        env = os.environ.copy()
        agent_key_path = os.environ.get("AGENT_GOOGLE_APPLICATION_CREDENTIALS") or str(task_dir.parents[1] / "agent-sa-key.json")
        if os.path.exists(agent_key_path):
            env["GOOGLE_APPLICATION_CREDENTIALS"] = str(Path(agent_key_path).resolve())

        print(f"[AntigravityDriver] Executing agy for task {task_dir.name} (skill_mode={skill_mode})...")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
            try:
                data = json.loads(res.stdout)
                return {"status": "success", "data": data, "raw": res.stdout}
            except json.JSONDecodeError:
                return {"status": "success", "raw": res.stdout}
        except subprocess.CalledProcessError as e:
            print(f"[AntigravityDriver Error] agy execution failed with exit code {e.returncode}")
            return {"status": "failed", "error": e.stderr or str(e)}

def main():
    parser = argparse.ArgumentParser(description="Antigravity Driver CLI")
    parser.add_argument("--task-dir", type=str, required=True, help="Path to compiled task directory")
    parser.add_argument("--prompt", type=str, default="Complete the task in task.md", help="Prompt for agy")
    parser.add_argument("--skill-mode", type=str, default="with-skill", choices=["with-skill", "no-skill"])
    parser.add_argument("--model", type=str, default="gemini-3.6-flash")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run mode (default: True)")
    parser.add_argument("--execute", action="store_true", help="Execute agy for real")

    args = parser.parse_args()
    driver = AntigravityDriver(model=args.model, skip_permissions=args.execute)
    res = driver.run_task(
        task_dir=Path(args.task_dir),
        prompt=args.prompt,
        skill_mode=args.skill_mode,
        dry_run=not args.execute
    )
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
