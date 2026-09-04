#!/usr/bin/env python3
"""
Antigravity CLI Agent Driver for OJOF-Gym multi-turn evaluation.
Executes multi-turn workflows (Turn 1: Baseline Architecture -> Turn 2: Question Maintenance)
in strict workspace isolation and tracks turn-level metrics.
"""

import argparse
import difflib
import getpass
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

AGY_BIN = (
    os.environ.get("AGY_BIN")
    or shutil.which("agy")
    or shutil.which("antigravity")
    or str(Path.home() / ".local" / "bin" / "agy")
    or "agy"
)

BWRAP_BIN = (
    os.environ.get("BWRAP_BIN")
    or shutil.which("bwrap")
    or "/usr/bin/bwrap"
)

AGENTAPI_BIN = (
    os.environ.get("AGENTAPI_BIN")
    or shutil.which("agentapi")
    or str(Path.home() / ".local" / "bin" / "agentapi")
    or "agentapi"
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
        output_format: str = "stream-json",
        use_bwrap: bool = True,
        bwrap_bin: Optional[str] = None,
        extra_masked_paths: Optional[List[Path]] = None
    ):
        self.model = model
        self.skip_permissions = skip_permissions
        self.effort = effort
        self.output_format = output_format
        self.use_bwrap = use_bwrap
        self.bwrap_bin = bwrap_bin or BWRAP_BIN
        self.extra_masked_paths = extra_masked_paths or []

        if self.use_bwrap:
            bwrap_resolved = shutil.which(self.bwrap_bin) or (self.bwrap_bin if Path(self.bwrap_bin).is_file() else None)
            if not bwrap_resolved:
                raise RuntimeError(
                    f"Bubblewrap binary '{self.bwrap_bin}' not found. "
                    "bwrap is required for secure benchmark isolation. "
                    "Install bubblewrap (e.g. 'sudo apt-get install bubblewrap') "
                    "or run with use_bwrap=False if you explicitly wish to disable sandboxing."
                )

    def build_bwrap_command(
        self,
        base_cmd: List[str],
        workspace_dir: Path
    ) -> List[str]:
        """
        Wraps base_cmd with Bubblewrap (bwrap) for filesystem isolation.
        - Mounts host root (/) as read-only.
        - Mounts /proc and /dev.
        - Mounts a fresh tmpfs on /tmp.
        - Mounts virtual /run tmpfs.
        - Binds user runtime, config, and cache directories so agent CLI can maintain state.
        - Mounts workspace_dir read-write.
        - Shadows PROJECT_ROOT and sensitive paths with empty tmpfs.
        - Sets sandbox working directory to workspace_dir.
        - Leaves network unisolated so external APIs / DBs remain reachable.
        """
        resolved_ws = workspace_dir.resolve()
        user = getpass.getuser()
        uid = os.getuid()

        bwrap_cmd = [
            self.bwrap_bin,
            "--ro-bind", "/", "/",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--tmpfs", "/run",
            "--dir", "/run/user",
            "--bind-try", f"/run/user/{uid}", f"/run/user/{uid}",
            # Allow agent CLI to write logs, cache, and state
            "--bind-try", str(Path.home() / ".config"), str(Path.home() / ".config"),
            "--bind-try", str(Path.home() / ".cache"), str(Path.home() / ".cache"),
            "--bind-try", str(Path.home() / ".local"), str(Path.home() / ".local"),
            "--bind", str(resolved_ws), str(resolved_ws),
        ]

        # Support platform/environment specific binds (e.g. credentials, tokens, agent configs)
        extra_binds_env = os.environ.get("BWRAP_EXTRA_BINDS", "")
        if extra_binds_env:
            for item in extra_binds_env.split(":"):
                if item:
                    item_path = Path(item).expanduser()
                    if item_path.exists():
                        if str(item_path).startswith("/run/"):
                            bwrap_cmd.extend(["--dir", str(item_path.parent)])
                        bwrap_cmd.extend(["--bind-try", str(item_path), str(item_path)])

        # Expose DNS resolver if /etc/resolv.conf is a symlink into /run
        resolv_conf = Path("/etc/resolv.conf")
        if resolv_conf.is_symlink():
            try:
                real_target = resolv_conf.resolve()
                if str(real_target).startswith("/run/"):
                    rel_parent = real_target.parent.relative_to("/run")
                    bwrap_cmd.extend([
                        "--dir", f"/run/{rel_parent}",
                        "--bind-try", str(real_target), str(real_target)
                    ])
            except Exception:
                pass

        paths_to_mask: List[Path] = [
            PROJECT_ROOT.resolve(),
        ]
        if PROJECT_ROOT.is_absolute() and PROJECT_ROOT not in paths_to_mask:
            paths_to_mask.append(PROJECT_ROOT)

        for candidate in [
            Path.home() / ".ssh",
            Path.home() / ".gnupg",
            Path.home() / ".aws",
        ]:
            if candidate.exists() and candidate not in paths_to_mask:
                paths_to_mask.append(candidate)

        # Support masking persistent/network storage locations via environment
        mask_env = os.environ.get("BWRAP_MASK_PATHS", "")
        if mask_env:
            for item in mask_env.split(":"):
                if item:
                    item_path = Path(item).expanduser()
                    if item_path.exists() and item_path not in paths_to_mask:
                        paths_to_mask.append(item_path)

        for p in self.extra_masked_paths:
            resolved_p = p.resolve() if isinstance(p, Path) else Path(p).resolve()
            if resolved_p not in paths_to_mask:
                paths_to_mask.append(resolved_p)

        for p in paths_to_mask:
            if p.exists() and p.is_dir():
                bwrap_cmd.extend(["--tmpfs", str(p)])

        bwrap_cmd.extend([
            "--chdir", str(resolved_ws),
            *base_cmd
        ])

        return bwrap_cmd

    def execute_turn(
        self,
        workspace_dir: Path,
        prompt: str,
        turn_num: int = 1,
        skill_mode: str = "with-skill",
        dry_run: bool = False,
        conversation_id: Optional[str] = None,
        timeout_seconds: int = 600,
        warning_seconds: Optional[int] = 480,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes a single turn of interaction in the workspace.
        Enforces timeout_seconds (default: 600s = 10 minutes) and delivers an 80% time warning
        nudge via agentapi send-message at warning_seconds (default: 480s = 8 minutes).
        """
        if timeout is not None:
            timeout_seconds = timeout
        timeout_minutes = max(1, int(timeout_seconds / 60))
        cmd = [
            AGY_BIN,
            "--model", self.model,
            "--output-format", self.output_format,
            "--print-timeout", f"{timeout_minutes}m",
        ]

        if self.effort and "3.6" not in self.model:
            cmd.extend(["--effort", self.effort])

        if self.skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        # In Turn 2+, continue conversation if conversation_id is known
        if turn_num > 1 and conversation_id:
            cmd.extend(["--conversation", conversation_id])

        cmd.extend(["--print", prompt])

        if self.use_bwrap:
            full_cmd = self.build_bwrap_command(cmd, workspace_dir)
        else:
            full_cmd = cmd

        if dry_run:
            return {
                "dry_run": True,
                "turn": turn_num,
                "status": "simulated_success",
                "sandboxed": self.use_bwrap,
                "command": full_cmd,
                "usage": {"total_tokens": 0, "input_tokens": 0, "output_tokens": 0},
                "duration_seconds": 0
            }

        env = os.environ.copy()
        local_bin = str(Path.home() / ".local" / "bin")
        tools_bin = str((PROJECT_ROOT / "tools" / "bin").resolve())
        env["PATH"] = f"{local_bin}:{tools_bin}:{env.get('PATH', '')}"
        print(f"    [AntigravityDriver] Executing Turn {turn_num} ({skill_mode}) in {workspace_dir.name} [bwrap: {self.use_bwrap}, timeout: {timeout_seconds}s]...")

        captured_conversation_id = conversation_id
        result_payload: Optional[Dict[str, Any]] = None
        raw_output_lines: List[str] = []
        warning_sent = False

        start_time = time.time()
        proc = subprocess.Popen(
            full_cmd,
            cwd=str(workspace_dir.resolve()),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            bufsize=1
        )

        def read_stdout():
            nonlocal captured_conversation_id, result_payload
            try:
                for line in proc.stdout:
                    raw_output_lines.append(line)
                    line_s = line.strip()
                    if not line_s:
                        continue
                    try:
                        data = json.loads(line_s)
                        if data.get("event") == "init" and not captured_conversation_id:
                            captured_conversation_id = data.get("conversation_id")
                        elif data.get("event") == "result":
                            result_payload = data.get("result")
                    except Exception:
                        pass
            except Exception:
                pass

        reader_thread = threading.Thread(target=read_stdout, daemon=True)
        reader_thread.start()

        poll_interval = 2.0
        while True:
            ret = proc.poll()
            if ret is not None:
                break

            elapsed = time.time() - start_time

            # 8-minute / 80% mark warning nudge
            if warning_seconds and elapsed >= warning_seconds and not warning_sent:
                warning_sent = True
                target_cid = captured_conversation_id or conversation_id
                if target_cid:
                    try:
                        agentapi_resolved = (
                            shutil.which(AGENTAPI_BIN)
                            or (AGENTAPI_BIN if Path(AGENTAPI_BIN).exists() else None)
                            or "agentapi"
                        )
                        if turn_num == 1:
                            warning_text = (
                                "URGENT TIME WARNING: Only 2 minutes (20% of the available time) remain for Turn 1. "
                                "Please prioritize completing your LookML architecture immediately. Avoid making additional remote tool calls and finalize your files now."
                            )
                        else:
                            warning_text = (
                                f"URGENT TIME WARNING: Only 2 minutes (20% of the available time) remain for Turn {turn_num}. "
                                "Please finalize your current edits immediately without making additional tool calls."
                            )
                        print(f"    [AntigravityDriver] {elapsed:.1f}s elapsed: sending time warning nudge to conversation {target_cid}...")
                        res_warn = subprocess.run(
                            [agentapi_resolved, "send-message", target_cid, warning_text],
                            capture_output=True,
                            text=True,
                            timeout=20
                        )
                        if res_warn.returncode == 0:
                            print(f"    [AntigravityDriver] Warning nudge successfully delivered to agent.")
                        else:
                            print(f"    [AntigravityDriver] Warning delivery returned code {res_warn.returncode}: {res_warn.stderr.strip()}")
                    except Exception as e:
                        print(f"    [AntigravityDriver] Warning delivery encountered exception: {e}")

            if elapsed >= timeout_seconds:
                print(f"    [AntigravityDriver] Turn timed out after {elapsed:.1f}s (timeout: {timeout_seconds}s). Terminating process...")
                proc.kill()
                proc.wait()
                reader_thread.join(timeout=2)
                return {
                    "turn": turn_num,
                    "status": "timeout",
                    "conversation_id": captured_conversation_id or conversation_id or "",
                    "error": f"Turn timed out after {timeout_seconds}s",
                    "sandboxed": self.use_bwrap,
                    "warning_sent": warning_sent,
                    "duration_seconds": elapsed
                }

            time.sleep(poll_interval)

        reader_thread.join(timeout=5)
        stderr_output = proc.stderr.read() if proc.stderr else ""
        elapsed_final = time.time() - start_time

        if result_payload:
            return {
                "turn": turn_num,
                "status": result_payload.get("status", "success"),
                "conversation_id": result_payload.get("conversation_id", captured_conversation_id or ""),
                "usage": result_payload.get("usage", {}),
                "duration_seconds": result_payload.get("duration_seconds", elapsed_final),
                "response": result_payload.get("response", ""),
                "error": result_payload.get("error", ""),
                "sandboxed": self.use_bwrap,
                "warning_sent": warning_sent
            }
        else:
            # Fallback for plain text or unexpected format
            raw_text = "".join(raw_output_lines)
            try:
                data = json.loads(raw_text)
                return {
                    "turn": turn_num,
                    "status": data.get("status", "success"),
                    "conversation_id": data.get("conversation_id", captured_conversation_id or ""),
                    "usage": data.get("usage", {}),
                    "duration_seconds": data.get("duration_seconds", elapsed_final),
                    "response": data.get("response", ""),
                    "error": data.get("error", ""),
                    "sandboxed": self.use_bwrap,
                    "warning_sent": warning_sent
                }
            except Exception:
                return {
                    "turn": turn_num,
                    "status": "success" if proc.returncode == 0 else "failed",
                    "conversation_id": captured_conversation_id or "",
                    "raw": raw_text,
                    "stderr": stderr_output,
                    "sandboxed": self.use_bwrap,
                    "warning_sent": warning_sent,
                    "duration_seconds": elapsed_final
                }

    def setup_workspace(
        self,
        workspace_dir: Path,
        task_dir: Path,
        skill_mode: str
    ):
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Skill isolation
        skills_dest = workspace_dir / ".agents" / "skills"
        skills_dest.mkdir(parents=True, exist_ok=True)

        # Always provide the general Looker CLI & validator skill to both with-skill and no-skill
        looker_cli_src = PROJECT_ROOT / ".agents" / "skills" / "using-looker-cli"
        if not looker_cli_src.exists():
            looker_cli_src = task_dir / "environment" / "skills" / "using-looker-cli"
        if looker_cli_src.exists():
            cli_dest = skills_dest / "using-looker-cli"
            cli_dest.mkdir(parents=True, exist_ok=True)
            shutil.copytree(looker_cli_src, cli_dest, dirs_exist_ok=True)

        if skill_mode == "with-skill":
            skills_src = PROJECT_ROOT / ".agents" / "skills" / "lookml-ojof"
            if not skills_src.exists():
                skills_src = task_dir / "environment" / "skills" / "lookml-ojof"
            if skills_src.exists():
                ojof_dest = skills_dest / "lookml-ojof"
                ojof_dest.mkdir(parents=True, exist_ok=True)
                shutil.copytree(skills_src, ojof_dest, dirs_exist_ok=True)
        else:
            ojof_dest = skills_dest / "lookml-ojof"
            if ojof_dest.exists():
                shutil.rmtree(ojof_dest)

def main():
    parser = argparse.ArgumentParser(description="Antigravity Driver CLI with Bubblewrap Sandboxing")
    parser.add_argument("--workspace-dir", type=str, required=True, help="Path to workspace directory")
    parser.add_argument("--task-dir", type=str, default="tasks/task_thelook_ecommerce", help="Path to task directory")
    parser.add_argument("--prompt", type=str, default="Inspect the workspace.", help="Prompt for agy")
    parser.add_argument("--skill-mode", type=str, default="with-skill", choices=["with-skill", "no-skill"])
    parser.add_argument("--model", type=str, default="gemini-3.6-flash")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Dry run mode")
    parser.add_argument("--no-bwrap", action="store_true", help="Disable bwrap sandboxing")

    args = parser.parse_args()
    ws = Path(args.workspace_dir)
    td = Path(args.task_dir)

    driver = AntigravityDriver(
        model=args.model,
        skip_permissions=True,
        use_bwrap=not args.no_bwrap
    )
    driver.setup_workspace(ws, td, args.skill_mode)
    res = driver.execute_turn(
        workspace_dir=ws,
        prompt=args.prompt,
        turn_num=1,
        skill_mode=args.skill_mode,
        dry_run=args.dry_run
    )
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()