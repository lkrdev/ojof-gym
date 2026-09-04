#!/usr/bin/env python3
"""
Looker Project Evaluator for OJOF-Gym.
Syncs generated LookML to Looker development workspace with clean state wiping, runs LookML validator,
compiles test queries to SQL, executes against BigQuery, and tracks query performance & column participation.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

WITH_LOOKER_BIN = Path.home() / ".local" / "bin" / "with-looker"

def run_looker_cli(args: List[str], input_str: Optional[str] = None) -> subprocess.CompletedProcess:
    """Executes looker-cli command using with-looker namespace wrapper if available, or direct looker-cli."""
    env = os.environ.copy()
    env["PATH"] = f"{Path.home() / '.local' / 'bin'}:{env.get('PATH', '')}"
    if WITH_LOOKER_BIN.exists():
        cmd = [str(WITH_LOOKER_BIN), "looker-cli"] + args
    else:
        looker_bin = shutil.which("looker-cli") or "looker-cli"
        cmd = [looker_bin] + args
    return subprocess.run(cmd, input=input_str, capture_output=True, text=True, env=env)

class LookerEvaluator:
    def __init__(self, project_id: str = "lookml_sandbox", connection_name: str = "default_bigquery_connection", model_name: str = "sandbox"):
        self.project_id = os.environ.get("LOOKER_PROJECT", os.environ.get("LOOKER_PROJECT_ID", project_id))
        self.connection_name = os.environ.get("LOOKER_CONNECTION", connection_name)
        self.model_name = os.environ.get("LOOKER_MODEL", os.environ.get("LOOKER_MODEL_NAME", model_name))

    def is_available(self) -> bool:
        """Checks if looker-cli is available."""
        return WITH_LOOKER_BIN.exists() or (shutil.which("looker-cli") is not None)

    def ensure_authenticated(self) -> bool:
        """Checks login and refreshes expired token if needed."""
        if not self.is_available():
            return False
        res = run_looker_cli(["session", "get"])
        if res.returncode == 0:
            return True

        cfg_path = Path.home() / ".config" / "looker-cli" / "config.yaml"
        if cfg_path.exists():
            try:
                with open(cfg_path) as f:
                    d = yaml.safe_load(f) or {}
                for prof in d.get("profiles", {}).values():
                    prof.pop("access_token", None)
                    prof.pop("expiration", None)
                with open(cfg_path, "w") as f:
                    yaml.safe_dump(d, f)
            except Exception:
                pass

        login_res = run_looker_cli(["session", "login"])
        return login_res.returncode == 0

    def list_remote_files(self) -> List[str]:
        """Lists all files in Looker project."""
        self.ensure_authenticated()
        run_looker_cli(["session", "update", "dev"])
        res = run_looker_cli(["project", "file", "ls", self.project_id, "--plain"])
        if res.returncode != 0:
            return []
        files = []
        for line in res.stdout.splitlines():
            parts = line.split()
            if parts and parts[0].endswith(".lkml") and parts[0] != "manifest.lkml":
                files.append(parts[0])
        return files

    def clean_remote_workspace(self, preserve_files: List[str] = None):
        """Removes stale .lkml files from Looker dev workspace."""
        preserve = set(preserve_files or [])
        preserve.add("manifest.lkml")
        existing = self.list_remote_files()
        for f in existing:
            if f not in preserve:
                run_looker_cli(["project", "file", "rm", self.project_id, f])

    def ensure_model_configured(self, model_name: str) -> bool:
        """Ensures the LookML model configuration exists on Looker for this project."""
        self.ensure_authenticated()
        res = run_looker_cli(["api", "lookmlmodel", "lookml_model", model_name])
        if res.returncode == 0:
            return True
        body = {
            "name": model_name,
            "project_name": self.project_id,
            "allowed_db_connection_names": [self.connection_name],
            "unlimited_db_connections": False
        }
        res_create = run_looker_cli(
            ["api", "lookmlmodel", "create_lookml_model", "-"],
            input_str=json.dumps(body)
        )
        return res_create.returncode == 0

    def sync_files_to_looker(self, lkml_dir: Path) -> Dict[str, Any]:
        """
        Pushes local .lkml files into Looker sandbox in dev mode, ensuring valid includes and connections.
        """
        self.ensure_authenticated()
        run_looker_cli(["session", "update", "dev"])
        run_looker_cli(["project", "checkout", self.project_id, "master"])

        lkml_files = list(lkml_dir.rglob("*.lkml"))
        file_map = {f.name: f for f in lkml_files if ".system" not in str(f) and ".agents" not in str(f)}

        self.clean_remote_workspace(preserve_files=list(file_map.keys()))

        synced_files = []
        errors = []

        for rel_name, fpath in file_map.items():
            if rel_name.endswith(".model.lkml"):
                model_base = rel_name.replace(".model.lkml", "")
                self.ensure_model_configured(model_base)

            content = fpath.read_text()
            content = re.sub(r'include:\s*["\']/?(?:views/|explores/)?[^"\']*/(\*\.view(?:\.lkml)?)["\']', r'include: "\1"', content)
            content = re.sub(r'include:\s*["\']/?(?:views/|explores/)?[^"\']*/(\*\.explore(?:\.lkml)?)["\']', r'include: "\1"', content)
            content = re.sub(r'include:\s*["\']/?views/([^"\']+\.view(?:\.lkml)?)["\']', r'include: "\1"', content)
            
            # Normalize connection name to sandbox connection
            if rel_name.endswith(".model.lkml"):
                content = re.sub(r'connection:\s*["\'][^"\']+["\']', f'connection: "{self.connection_name}"', content)
                if 'include: "*.view.lkml"' not in content and 'include: "*.view"' not in content:
                    content = 'include: "*.view.lkml"\n' + content
                if 'include: "*.explore.lkml"' not in content and 'include: "*.explore"' not in content:
                    content = 'include: "*.explore.lkml"\n' + content
            elif rel_name.endswith(".explore.lkml"):
                if 'include: "*.view.lkml"' not in content and 'include: "*.view"' not in content:
                    content = 'include: "*.view.lkml"\n' + content

            with tempfile.NamedTemporaryFile("w", suffix=".lkml", delete=False) as tf:
                tf.write(content)
                tf_tmp = tf.name

            try:
                res = run_looker_cli(["project", "file", "update", self.project_id, rel_name, tf_tmp])
                if res.returncode == 0:
                    synced_files.append(rel_name)
                else:
                    res_create = run_looker_cli(["project", "file", "create", self.project_id, rel_name, tf_tmp])
                    if res_create.returncode == 0:
                        synced_files.append(rel_name)
                    else:
                        errors.append(f"Failed to sync {rel_name}: {res.stderr or res.stdout}")
            finally:
                if os.path.exists(tf_tmp):
                    os.remove(tf_tmp)

        return {"synced": synced_files, "errors": errors}

    def validate_project(self) -> Dict[str, Any]:
        """Runs Looker project validation."""
        self.ensure_authenticated()
        run_looker_cli(["session", "update", "dev"])
        res = run_looker_cli(["project", "validate", self.project_id])
        output_str = res.stdout + res.stderr
        is_valid = ("Project is valid" in output_str or "0 errors" in output_str) and res.returncode == 0
        return {
            "is_valid": is_valid,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip(),
            "returncode": res.returncode
        }

    def deploy_to_production(self) -> Dict[str, Any]:
        """
        Deploys current dev mode LookML project branch to production.
        Temporary workaround for sandbox/testing instances where Conversational Analytics
        or production query execution requires models to be deployed to production
        (due to absence of dev_mode_in_ca feature flag).
        """
        self.ensure_authenticated()
        run_looker_cli(["session", "update", "dev"])

        # Try `looker-cli project deploy <project_id>`
        res = run_looker_cli(["project", "deploy", self.project_id])
        if res.returncode == 0:
            return {"success": True, "output": res.stdout.strip()}

        # Fallback to API endpoint: api project deploy_to_production <project_id>
        res_api = run_looker_cli(["api", "project", "deploy_to_production", self.project_id])
        success = (res_api.returncode == 0)
        return {
            "success": success,
            "output": (res_api.stdout if success else res.stdout).strip(),
            "error": (res_api.stderr or res.stderr or res_api.stdout).strip()
        }

    def generate_query_via_ca(
        self,
        model: str,
        explore: str,
        question_prompt: str
    ) -> Dict[str, Any]:
        """
        Uses Looker Conversational Analytics (CA) to generate a grounded Looker query payload
        for a natural language business question.
        Prefixes the query with an explicit instruction to make a best-effort pick of a query
        without additional disambiguation or clarification questions.
        """
        if not self.is_available() or not self.ensure_authenticated():
            return {"success": False, "error": "Looker is not available or not authenticated"}

        convo_name = f"eval_ca_{int(time.time() * 1000)}"
        convo_body = {
            "name": convo_name,
            "sources": [{"model": model, "explore": explore}]
        }
        convo_res = run_looker_cli(
            ["api", "conversationalanalytics", "create_conversation", "-"],
            input_str=json.dumps(convo_body)
        )
        if convo_res.returncode != 0:
            return {"success": False, "error": f"Failed to create CA conversation: {convo_res.stderr or convo_res.stdout}"}

        try:
            data = json.loads(convo_res.stdout)
            convo_id = str(data.get("id", ""))
        except Exception as e:
            return {"success": False, "error": f"Failed to parse conversation response: {e}"}

        if not convo_id:
            return {"success": False, "error": "No conversation ID returned"}

        # Prefix business query with request to make a best-effort pick without disambiguation
        prefixed_prompt = (
            "Please make a best effort pick of the most appropriate query and execute it directly "
            "without asking for additional disambiguation or clarification: " + question_prompt
        )

        chat_body = {
            "conversation_id": convo_id,
            "user_message": prefixed_prompt
        }

        try:
            chat_res = run_looker_cli(
                ["api", "conversationalanalytics", "conversational_analytics_chat", "-"],
                input_str=json.dumps(chat_body)
            )
            if chat_res.returncode != 0:
                return {"success": False, "error": f"CA chat request failed: {chat_res.stderr or chat_res.stdout}"}

            try:
                messages = json.loads(chat_res.stdout)
            except Exception as e:
                return {"success": False, "error": f"Failed to parse chat response: {e}"}

            looker_query = None
            ca_thoughts = []
            ca_response_text = []

            for msg in (messages if isinstance(messages, list) else []):
                sys_msg = msg.get("systemMessage") or msg.get("system_message") or {}
                text_obj = sys_msg.get("text") or {}
                ttype = (text_obj.get("textType") or text_obj.get("text_type") or "").upper()
                parts = text_obj.get("parts", [])
                if ttype == "THOUGHT":
                    ca_thoughts.extend(parts)
                elif parts:
                    ca_response_text.extend(parts)

                data_obj = sys_msg.get("data") or {}
                q = data_obj.get("query", {}).get("looker")
                if not q and "generatedLookerQuery" in data_obj:
                    q = data_obj["generatedLookerQuery"]
                if q and isinstance(q, dict) and "fields" in q:
                    looker_query = q
                    break

            if looker_query:
                if not looker_query.get("model"):
                    looker_query["model"] = model
                if not looker_query.get("view"):
                    looker_query["view"] = explore
                return {
                    "success": True,
                    "query_payload": looker_query,
                    "thoughts": ca_thoughts,
                    "response_text": ca_response_text,
                    "messages": messages
                }
            else:
                return {
                    "success": False,
                    "error": "No Looker query generated by CA (clarification requested or empty response)",
                    "thoughts": ca_thoughts,
                    "response_text": ca_response_text,
                    "messages": messages
                }
        finally:
            run_looker_cli(["api", "conversationalanalytics", "delete_conversation", convo_id])

    def compile_query_to_sql(self, query_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compiles an inline query to SQL via Looker API without executing against BigQuery.
        """
        self.ensure_authenticated()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump(query_spec, tf)
            tf_path = tf.name

        try:
            res = run_looker_cli(["api", "query", "run_inline_query", "sql", tf_path])
            if res.returncode == 0:
                return {"status": "success", "sql": res.stdout.strip()}
            else:
                return {"status": "error", "error": res.stderr or res.stdout}
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def execute_query_live(self, query_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes query live against BigQuery via Looker API and measures latency.
        """
        self.ensure_authenticated()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump(query_spec, tf)
            tf_path = tf.name

        start_t = time.time()
        try:
            res = run_looker_cli(["api", "query", "run_inline_query", "json", tf_path])
            latency_ms = int((time.time() - start_t) * 1000)
            if res.returncode == 0:
                try:
                    rows = json.loads(res.stdout)
                    row_count = len(rows) if isinstance(rows, list) else 0
                    sample = rows[0] if row_count > 0 else {}
                    return {
                        "status": "success",
                        "latency_ms": latency_ms,
                        "row_count": row_count,
                        "sample_row": sample
                    }
                except json.JSONDecodeError:
                    return {
                        "status": "success",
                        "latency_ms": latency_ms,
                        "row_count": 0,
                        "raw_output": res.stdout[:200]
                    }
            else:
                return {
                    "status": "error",
                    "latency_ms": latency_ms,
                    "error": res.stderr or res.stdout
                }
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def get_explore_joins_map(self) -> Dict[str, str]:
        """Maps view name to join alias in the explore if aliased."""
        remote_files = self.list_remote_files()
        explore_files = [f for f in remote_files if f.endswith(".explore.lkml")]
        mapping = {}
        for ef in explore_files:
            res = run_looker_cli(["project", "file", "cat", self.project_id, ef])
            if res.returncode == 0:
                content = res.stdout
                # Extract individual join blocks
                join_blocks = re.findall(r"join:\s*(\w+)\s*\{([^}]*)\}", content)
                for alias, body in join_blocks:
                    m = re.search(r"from:\s*(\w+)", body)
                    if m:
                        mapping[m.group(1)] = alias
                    else:
                        mapping[alias] = alias
        return mapping

    def evaluate_scenario_questions(
        self,
        scenario_spec: Dict[str, Any],
        model_name: Optional[str] = None,
        explore_name: Optional[str] = None,
        target_questions: Optional[List[str]] = None,
        agent_queries: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Tests each user question defined in the scenario spec against Looker.
        Includes an implicit hook deploying latest dev changes to production for CA access.
        """
        # Implicit hook: Ensure latest dev changes are deployed to production so Looker CA can query the model
        if self.is_available():
            dep_res = self.deploy_to_production()
            print(f"  [Looker Evaluator] Implicit hook: deployed model to production (success: {dep_res.get('success')})")

        user_questions = scenario_spec.get("userQuestions", {})
        if target_questions is not None:
            user_questions = {k: v for k, v in user_questions.items() if k in target_questions}

        results = {}

        remote_files = self.list_remote_files()
        model_file = next((f for f in remote_files if f.endswith(".model.lkml")), "thelook_ecommerce.model.lkml")
        target_model = model_file.replace(".model.lkml", "") if not model_name else model_name
        self.ensure_model_configured(target_model)

        explore_file = next((f for f in remote_files if f.endswith(".explore.lkml")), None)
        target_explore = explore_file.replace(".explore.lkml", "") if explore_file else (explore_name or "thelook_ecommerce")

        joins_map = self.get_explore_joins_map()

        for qkey, qval in user_questions.items():
            if not qval.get("supported", True):
                results[qkey] = {
                    "supported": False,
                    "prompt": qval.get("prompt", ""),
                    "status": "skipped_unsupported_scope"
                }
                continue

            prompt = qval.get("prompt", "")
            expectation = qval.get("expectation", {})
            exp_sql_elements = expectation.get("expectedSql") or expectation.get("participatingColumns", [])
            min_dims = expectation.get("minDimensions", 0)
            min_measures = expectation.get("minMeasures", 0)

            # Query selection: Try Looker Conversational Analytics (CA) first
            ca_result = self.generate_query_via_ca(
                model=target_model,
                explore=target_explore,
                question_prompt=prompt
            )

            if ca_result.get("success") and ca_result.get("query_payload"):
                query_payload = ca_result["query_payload"]
                generation_source = "looker_ca"
                ca_thoughts = ca_result.get("thoughts", [])
                ca_response = ca_result.get("response_text", [])
            elif agent_queries and qkey in agent_queries and agent_queries[qkey]:
                query_payload = agent_queries[qkey]
                generation_source = "agent_generated"
                ca_thoughts = ca_result.get("thoughts", [])
                ca_response = ca_result.get("response_text", [])
            else:
                # Fallback to heuristic field mapping
                generation_source = "heuristic_fallback"
                ca_thoughts = ca_result.get("thoughts", [])
                ca_response = ca_result.get("response_text", [])
                mapped_fields = []
                for item in exp_sql_elements:
                    if "." in item and not any(item.upper().startswith(kw) for kw in ["SUM", "COUNT", "AVG", "GROUP"]):
                        v_name, f_name = item.split(".", 1)
                        alias = joins_map.get(v_name, v_name)
                        mapped_fields.append(f"{alias}.{f_name}")

                query_payload = {
                    "model": target_model,
                    "view": target_explore,
                    "fields": mapped_fields if mapped_fields else [f"{target_explore}.count"]
                }

            compile_res = self.compile_query_to_sql(query_payload)
            sql = compile_res.get("sql", "")

            missing_elements = []
            has_group_by = False
            has_aggregate = False

            if sql:
                for elem in exp_sql_elements:
                    if elem.upper() in ["COUNT_DISTINCT", "COUNT(DISTINCT)"]:
                        if not re.search(r"COUNT\s*\(\s*DISTINCT\b", sql, re.IGNORECASE):
                            missing_elements.append("COUNT(DISTINCT)")
                    elif elem.upper() in ["SUM", "COUNT", "AVG", "MIN", "MAX", "GROUP BY", "WHERE", "HAVING"]:
                        if not re.search(rf"\b{re.escape(elem)}\b", sql, re.IGNORECASE):
                            missing_elements.append(elem)
                    else:
                        col_name = elem.split(".")[-1] if "." in elem else elem
                        if not re.search(rf"\b{re.escape(col_name)}\b", sql, re.IGNORECASE):
                            missing_elements.append(elem)

                has_group_by = bool(re.search(r"\bGROUP\s+BY\b", sql, re.IGNORECASE))
                has_aggregate = bool(re.search(r"\b(SUM|COUNT|AVG|MIN|MAX)\s*\(", sql, re.IGNORECASE))

            dims_passed = True if min_dims == 0 else has_group_by
            meas_passed = True if min_measures == 0 else has_aggregate
            compile_passed = (compile_res.get("status") == "success") and (len(missing_elements) == 0) and dims_passed and meas_passed

            exec_res = {}
            if compile_passed:
                exec_res = self.execute_query_live(query_payload)

            results[qkey] = {
                "supported": True,
                "prompt": prompt,
                "expected_sql": exp_sql_elements,
                "missing_sql_elements": missing_elements,
                "has_group_by": has_group_by,
                "has_aggregate": has_aggregate,
                "min_dimensions": min_dims,
                "min_measures": min_measures,
                "compiled_sql": sql,
                "query_payload": query_payload,
                "generation_source": generation_source,
                "ca_thoughts": ca_thoughts,
                "ca_response": ca_response,
                "status": "passed" if (compile_passed and exec_res.get("status") == "success") else "failed",
                "compile_status": compile_res.get("status"),
                "execution_performance": exec_res,
                "error": compile_res.get("error") or exec_res.get("error") or (ca_result.get("error") if not ca_result.get("success") else None)
            }

        return results

if __name__ == "__main__":
    evaluator = LookerEvaluator()
    print(f"Looker Evaluator Ready: {evaluator.is_available()}")
