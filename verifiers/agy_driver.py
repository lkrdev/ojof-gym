#!/usr/bin/env python3
"""
Antigravity / AgentAPI Driver for OJOF-Gym multi-turn evaluation.
Executes multi-turn workflows (Turn 1: Baseline Architecture -> Turns 2-N: Incremental Query Maintenance)
in strict workspace isolation using the Google internal AgentAPI or Antigravity CLI.
"""

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Generic discovery for agentapi or agy binary
AGENTAPI_BIN = (
    os.environ.get("AGENTAPI_BIN")
    or shutil.which("agentapi")
    or None
)
AGY_BIN = (
    os.environ.get("AGY_BIN")
    or shutil.which("agy")
    or shutil.which("antigravity")
    or None
)

def find_transcript_path(conv_id: str) -> Optional[Path]:
    """Dynamically resolves conversation transcript path across environments."""
    if not conv_id:
        return None
    # 1. Environment variable
    if "JETSKI_APP_DATA_DIR" in os.environ:
        p = Path(os.environ["JETSKI_APP_DATA_DIR"]) / "brain" / conv_id / ".system_generated" / "logs" / "transcript.jsonl"
        if p.exists():
            return p
    # 2. Standard user home / agent directories
    candidates = [
        Path.home() / ".gemini" / "jetski" / "brain" / conv_id / ".system_generated" / "logs" / "transcript.jsonl",
        Path.home() / ".agents" / "brain" / conv_id / ".system_generated" / "logs" / "transcript.jsonl",
        Path("/tmp") / "jetski" / "brain" / conv_id / ".system_generated" / "logs" / "transcript.jsonl",
    ]

    for c in candidates:
        if c.exists():
            return c
    return candidates[0] if candidates else None

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
        conversation_id: Optional[str] = None,
        timeout: int = 480
    ) -> Dict[str, Any]:
        """
        Executes a single turn of interaction in the workspace.
        """
        if dry_run:
            return {
                "dry_run": True,
                "turn": turn_num,
                "status": "simulated_success",
                "usage": {"total_tokens": 0, "input_tokens": 0, "output_tokens": 0},
                "duration_seconds": 0,
                "response": "Simulation mode response."
            }

        ws_abs = str(workspace_dir.resolve())
        print(f"    [AntigravityDriver] Executing Turn {turn_num} ({skill_mode}) in {workspace_dir.name}...")

        # Build augmented prompt with strict workspace instructions
        looker_project = os.environ.get("LOOKER_PROJECT", os.environ.get("LOOKER_PROJECT_ID", "lookml_sandbox"))
        looker_model = os.environ.get("LOOKER_MODEL", os.environ.get("LOOKER_MODEL_NAME", "sandbox"))

        prompt_prefix = [
            f"TARGET WORKSPACE: `{ws_abs}`",
            f"You are working in the directory `{ws_abs}`.",
            f"All LookML files (.view.lkml, .explore.lkml, .model.lkml) MUST be created or modified directly in `{ws_abs}`.",
            f"Target Looker Project: `{looker_project}` | Configured Model Name: `{looker_model}`.",
            f"Your primary model file MUST be named `{looker_model}.model.lkml`, and all query JSON payloads MUST specify 'model': '{looker_model}'.",
        ]
        if skill_mode == "with-skill":
            prompt_prefix.append(
                f"You have the `lookml-ojof` skill instructions in your workspace at `{ws_abs}/.agents/skills/lookml-ojof/SKILL.md`.\n"
                f"Always apply the Outer Join On False (OJOF) architecture with zero-row dummy base and dynamic Liquid joins for shared dimensions."
            )
        else:
            prompt_prefix.append("Build standard, direct LookML models and explores without OJOF specialization.")

        full_prompt = "\n".join(prompt_prefix) + "\n\n" + prompt

        start_time = time.time()

        # Preferred path: AgentAPI
        if os.path.exists(AGENTAPI_BIN):
            return self._execute_turn_agentapi(
                ws_abs=ws_abs,
                prompt=full_prompt,
                turn_num=turn_num,
                conversation_id=conversation_id,
                timeout=timeout,
                start_time=start_time
            )

        # Fallback path: CLI binary
        if AGY_BIN:
            return self._execute_turn_cli(
                workspace_dir=workspace_dir,
                prompt=full_prompt,
                turn_num=turn_num,
                conversation_id=conversation_id,
                timeout=timeout,
                start_time=start_time
            )

        return {
            "turn": turn_num,
            "status": "error",
            "error": "No agent runtime available (neither agentapi nor agy binary found)."
        }

    def _execute_turn_agentapi(
        self,
        ws_abs: str,
        prompt: str,
        turn_num: int,
        conversation_id: Optional[str],
        timeout: int,
        start_time: float
    ) -> Dict[str, Any]:
        """Drives agent turn via Google AgentAPI."""
        conv_id = conversation_id
        # Record initial step count before sending message to prevent early exit on previous turn's output
        transcript_path = find_transcript_path(conv_id) if conv_id else None
        initial_step_count = 0
        if transcript_path and transcript_path.exists():
            try:
                c_text = transcript_path.read_text()
                initial_step_count = len([l for l in c_text.strip().splitlines() if l.strip()])
            except Exception:
                pass

        if not conv_id:
            # Turn 1: start new conversation
            cmd = [
                AGENTAPI_BIN,
                "start-conversation",
                "--workspace", ws_abs,
                prompt
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode != 0:
                return {
                    "turn": turn_num,
                    "status": "error",
                    "error": f"agentapi start-conversation failed with code {res.returncode}: {res.stderr or res.stdout}"
                }
            stdout = res.stdout.strip()
            match = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", stdout)
            if not match:
                return {
                    "turn": turn_num,
                    "status": "error",
                    "error": f"Failed to parse conversationId from agentapi output: {stdout}\nStderr: {res.stderr}"
                }
            conv_id = match.group(1)
        else:
            # Subsequent turns: send-message to existing conversation
            cmd = [
                AGENTAPI_BIN,
                "send-message",
                conv_id,
                prompt
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode != 0:
                return {
                    "turn": turn_num,
                    "status": "error",
                    "conversation_id": conv_id,
                    "error": f"agentapi send-message failed: {res.stderr}"
                }

        # Poll transcript for completion of THIS turn
        if not transcript_path or not transcript_path.exists():
            transcript_path = find_transcript_path(conv_id)

        last_response_text = ""
        total_tokens_est = 0
        status = "running"
        turn_done = False

        poll_interval = 3
        deadline = time.time() + timeout

        # Initial small delay for agent startup
        time.sleep(2)

        while time.time() < deadline:
            if not transcript_path or not transcript_path.exists():
                transcript_path = find_transcript_path(conv_id)

            if transcript_path and transcript_path.exists():
                try:
                    content = transcript_path.read_text()
                    lines = [l for l in content.strip().splitlines() if l.strip()]
                    if len(lines) > initial_step_count:
                        new_lines = lines[initial_step_count:]
                        # Check the latest step among newly added steps
                        last_step = json.loads(new_lines[-1])
                        if last_step.get("source") == "MODEL" and last_step.get("type") == "PLANNER_RESPONSE":
                            # If it's a planner response without pending tool calls and status is DONE
                            calls = last_step.get("tool_calls", [])
                            if not calls and last_step.get("status") == "DONE":
                                last_response_text = last_step.get("content", "")
                                turn_done = True
                                status = "success"
                                total_tokens_est = len(content) // 4
                                break
                            elif last_step.get("status") == "ERROR":
                                status = "error"
                                last_response_text = last_step.get("content", "")
                                turn_done = True
                                break
                except Exception as e:
                    pass

            time.sleep(poll_interval)

        duration = time.time() - start_time
        if not turn_done:
            status = "timeout"
            last_response_text = f"Turn timed out after {timeout}s"

        return {
            "turn": turn_num,
            "status": status,
            "conversation_id": conv_id,
            "usage": {
                "input_tokens": total_tokens_est // 2,
                "output_tokens": total_tokens_est // 2,
                "total_tokens": total_tokens_est
            },
            "duration_seconds": round(duration, 2),
            "response": last_response_text,
            "error": "" if status == "success" else f"Turn finished with status {status}"
        }

    def _execute_turn_cli(
        self,
        workspace_dir: Path,
        prompt: str,
        turn_num: int,
        conversation_id: Optional[str],
        timeout: int,
        start_time: float
    ) -> Dict[str, Any]:
        """Drives agent turn via standalone agy CLI binary."""
        cmd = [
            AGY_BIN,
            "--model", self.model,
            "--output-format", self.output_format,
        ]
        if self.effort and "3.6" not in self.model:
            cmd.extend(["--effort", self.effort])
        if self.skip_permissions:
            cmd.append("--dangerously-skip-permissions")
        if turn_num > 1 and conversation_id:
            cmd.extend(["--conversation", conversation_id])
        cmd.extend(["--print", prompt])

        env = os.environ.copy()
        try:
            res = subprocess.run(cmd, cwd=str(workspace_dir.resolve()), capture_output=True, text=True, env=env, timeout=timeout)
            duration = time.time() - start_time
            try:
                data = json.loads(res.stdout)
                return {
                    "turn": turn_num,
                    "status": data.get("status", "success"),
                    "conversation_id": data.get("conversation_id", ""),
                    "usage": data.get("usage", {}),
                    "duration_seconds": round(duration, 2),
                    "response": data.get("response", ""),
                    "error": data.get("error", "")
                }
            except json.JSONDecodeError:
                return {
                    "turn": turn_num,
                    "status": "success",
                    "duration_seconds": round(duration, 2),
                    "raw": res.stdout
                }
        except subprocess.TimeoutExpired:
            return {"turn": turn_num, "status": "timeout", "error": f"Turn timed out after {timeout}s"}
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