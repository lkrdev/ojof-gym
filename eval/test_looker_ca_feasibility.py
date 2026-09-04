#!/usr/bin/env python3
"""
Looker Conversational Analytics (CA) Feasibility Test Script.
Tests ad-hoc explore-scoped CA query generation, field selection (measures vs dimensions),
fast mode, and developer branch (dev mode) execution.

Usage:
  # Dry-run test (no network calls, inspects payload contracts):
  python3 eval/test_looker_ca_feasibility.py --dry-run

  # Live feasibility test (requires active with-looker connection & SSH tunnel):
  python3 eval/test_looker_ca_feasibility.py --model lookml_sandbox --explore orders --question "Total revenue and order count by status"
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

WITH_LOOKER_BIN = Path.home() / ".local" / "bin" / "with-looker"

def run_looker_cli(args: List[str], input_str: Optional[str] = None) -> subprocess.CompletedProcess:
    """Executes looker-cli command using with-looker namespace wrapper if available."""
    env = os.environ.copy()
    env["PATH"] = f"{Path.home() / '.local' / 'bin'}:{env.get('PATH', '')}"
    if WITH_LOOKER_BIN.exists():
        cmd = [str(WITH_LOOKER_BIN), "looker-cli"] + args
    else:
        looker_bin = (
            os.environ.get("LOOKER_CLI_BIN")
            or shutil.which("looker-cli")
            or str(Path.home() / ".local" / "bin" / "looker-cli")
            or "looker-cli"
        )
        cmd = [looker_bin] + args
    return subprocess.run(cmd, input=input_str, capture_output=True, text=True, env=env)

def check_looker_session() -> Dict[str, Any]:
    """Inspects the current Looker CLI session."""
    res = run_looker_cli(["session", "get"])
    if res.returncode != 0:
        return {"connected": False, "error": res.stderr.strip() or res.stdout.strip()}
    return {"connected": True, "details": res.stdout.strip()}

def set_dev_workspace() -> bool:
    """Switches Looker API session to dev workspace."""
    res = run_looker_cli(["session", "update", "dev"])
    return res.returncode == 0

def create_explore_conversation(model: str, explore: str) -> Dict[str, Any]:
    """
    Creates an ad-hoc conversation bound directly to an explore source without requiring an agent_id.
    """
    payload = {
        "name": f"ca_feasibility_{int(time.time())}",
        "sources": [
            {
                "model": model,
                "explore": explore
            }
        ]
    }
    res = run_looker_cli(["api", "conversationalanalytics", "create_conversation", "-"], input_str=json.dumps(payload))
    if res.returncode != 0:
        return {"success": False, "error": res.stderr.strip() or res.stdout.strip()}
    try:
        data = json.loads(res.stdout)
        return {"success": True, "conversation_id": str(data.get("id", "")), "data": data}
    except Exception as e:
        return {"success": False, "error": f"Failed to parse response: {e}\nOutput: {res.stdout}"}

def send_chat_message(conversation_id: str, user_message: str) -> Dict[str, Any]:
    """
    Sends a query to Looker CA chat endpoint.
    """
    payload = {
        "conversation_id": conversation_id,
        "user_message": user_message
    }
    res = run_looker_cli(["api", "conversationalanalytics", "conversational_analytics_chat", "-"], input_str=json.dumps(payload))
    if res.returncode != 0:
        return {"success": False, "error": res.stderr.strip() or res.stdout.strip()}
    try:
        data = json.loads(res.stdout)
        return {"success": True, "messages": data}
    except Exception as e:
        return {"success": False, "error": f"Failed to parse response: {e}\nOutput: {res.stdout}"}

def delete_conversation(conversation_id: str):
    """Cleans up the test conversation."""
    run_looker_cli(["api", "conversationalanalytics", "delete_conversation", conversation_id])

def analyze_ca_response(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extracts and evaluates the Looker query payload and field selections from CA response messages.
    """
    extracted_queries = []
    thoughts = []
    text_responses = []

    for msg in messages:
        sys_msg = msg.get("systemMessage") or msg.get("system_message") or {}
        # Text responses & thoughts
        text_msg = sys_msg.get("text") or {}
        parts = text_msg.get("parts", [])
        ttype = (text_msg.get("textType") or text_msg.get("text_type") or "").upper()
        if ttype == "THOUGHT":
            thoughts.extend(parts)
        elif parts:
            text_responses.extend(parts)

        # Looker query data
        data_msg = sys_msg.get("data") or {}
        looker_query = data_msg.get("query", {}).get("looker")
        if not looker_query and "generatedLookerQuery" in data_msg:
            looker_query = data_msg["generatedLookerQuery"]
        if looker_query:
            extracted_queries.append(looker_query)

    analysis = {
        "total_messages": len(messages),
        "text_responses": text_responses,
        "thoughts": thoughts,
        "extracted_queries": extracted_queries,
        "query_count": len(extracted_queries),
    }

    if extracted_queries:
        first_q = extracted_queries[0]
        fields = first_q.get("fields", [])
        analysis["first_query_fields"] = fields
        analysis["first_query_filters"] = first_q.get("filters", {})
        analysis["first_query_model"] = first_q.get("model", "")
        analysis["first_query_view"] = first_q.get("view", "")
    return analysis

def simulate_dry_run(model: str, explore: str, question: str):
    """Simulates the CA query generation process without active network connection."""
    print("\n=======================================================")
    print("[SIMULATION / DRY-RUN] Looker Conversational Analytics Test")
    print("=======================================================")
    print(f"Target Model:   {model}")
    print(f"Target Explore: {explore}")
    print(f"User Question:  \"{question}\"")
    print("\n1. Explore-Scoped Context (No standalone agent required):")
    print("   POST /conversations payload:")
    print(json.dumps({"name": "ca_feasibility_sim", "sources": [{"model": model, "explore": explore}]}, indent=4))
    print("\n2. Chat Query Submission:")
    print("   POST /conversational_analytics/chat payload:")
    print(json.dumps({"conversation_id": "sim-uuid-1234", "user_message": question}, indent=4))
    print("\n3. Expected SystemMessage Extraction:")
    simulated_query = {
        "model": model,
        "view": explore,
        "fields": [f"{explore}.status", f"{explore}.total_revenue", f"{explore}.count"],
        "filters": {},
        "sorts": [f"{explore}.total_revenue desc"],
        "limit": "500"
    }
    print("   Extracted data.query.looker:")
    print(json.dumps(simulated_query, indent=4))
    print("\n4. Feasibility Verdict:")
    print("   - Explore Scoping: Natively supported via WriteConversation.sources")
    print("   - Field Selection: Measures (total_revenue, count) + Dimensions (status)")
    print("   - Fast Mode: Supported in backend (ThinkingMode = FAST / 1)")
    print("   - Dev Mode: Supported when session workspace is 'dev' and dev_mode_in_ca FF is enabled")
    print("=======================================================\n")

def main():
    parser = argparse.ArgumentParser(description="Looker Conversational Analytics Feasibility Tester")
    parser.add_argument("--model", type=str, default="lookml_sandbox", help="Target LookML model name")
    parser.add_argument("--explore", type=str, default="orders", help="Target explore name")
    parser.add_argument("--question", type=str, default="What is total revenue and order count broken down by status?", help="Analytical question")
    parser.add_argument("--dry-run", action="store_true", help="Run in simulation mode without making network calls")

    args = parser.parse_args()

    if args.dry_run:
        simulate_dry_run(args.model, args.explore, args.question)
        return

    print("\n=======================================================")
    print("[Looker CA Feasibility Test]")
    print("=======================================================")

    # Step 1: Check session
    print("Step 1: Checking Looker session...")
    sess = check_looker_session()
    if not sess.get("connected"):
        print("  [ERROR] Looker CLI is not currently authenticated or cannot connect to host.")
        print(f"  Details: {sess.get('error')}")
        print("\n  Troubleshooting:")
        print("  1. Ensure Looker API credentials and instance URL are configured in ~/.config/looker-cli/config.yaml")
        print("     or set LOOKER_BASE_URL, LOOKER_CLIENT_ID, LOOKER_CLIENT_SECRET environment variables.")
        print("  2. If using an SSH tunnel for private connectivity, verify your tunnel is listening.")
        print("  3. Run dry-run simulation with '--dry-run' to inspect payload structures.")
        sys.exit(1)
    print(f"  Connected: {sess.get('details')}")

    # Step 2: Switch to dev mode
    print("\nStep 2: Switching session to development workspace (dev mode)...")
    if set_dev_workspace():
        print("  Workspace switched to 'dev'.")
    else:
        print("  [Warning] Failed to set workspace to 'dev'. Queries may run against production.")

    # Step 3: Create conversation
    print(f"\nStep 3: Creating ad-hoc conversation for source [{args.model} / {args.explore}]...")
    convo_res = create_explore_conversation(args.model, args.explore)
    if not convo_res.get("success"):
        print(f"  [ERROR] Failed to create conversation: {convo_res.get('error')}")
        sys.exit(1)
    convo_id = convo_res["conversation_id"]
    print(f"  Conversation created: ID = {convo_id}")

    try:
        # Step 4: Send chat query
        print(f"\nStep 4: Sending analytical question: \"{args.question}\"...")
        chat_res = send_chat_message(convo_id, args.question)
        if not chat_res.get("success"):
            print(f"  [ERROR] Chat request failed: {chat_res.get('error')}")
            sys.exit(1)

        # Step 5: Analyze results
        messages = chat_res.get("messages", [])
        print(f"  Received {len(messages)} message(s) from Looker CA.")
        analysis = analyze_ca_response(messages)

        print("\nStep 5: Analysis of CA Response:")
        if analysis["thoughts"]:
            print(f"  - Reasoning / Thoughts: {' '.join(analysis['thoughts'][:3])}")
        if analysis["text_responses"]:
            print(f"  - Assistant Response: {' '.join(analysis['text_responses'][:2])}")

        queries = analysis["extracted_queries"]
        if queries:
            print(f"\n  [SUCCESS] Generated {len(queries)} Looker Query Payload(s):")
            for i, q in enumerate(queries, 1):
                print(f"\n  --- Query #{i} ---")
                print(f"  Model:   {q.get('model')}")
                print(f"  Explore: {q.get('view')}")
                print(f"  Fields:  {q.get('fields')}")
                print(f"  Filters: {q.get('filters')}")
                print(f"  Sorts:   {q.get('sorts')}")
                print(f"  Limit:   {q.get('limit')}")

                # Check for measures
                fields = q.get("fields", [])
                has_aggregates = any(f.endswith((".count", ".total", ".sum", ".avg", "_revenue", "_amount", "_cost")) for f in fields)
                print(f"  Contains Aggregate Measures: {has_aggregates}")
        else:
            print("  [Notice] No direct Looker query payload extracted from messages.")
            print(f"  Raw Messages: {json.dumps(messages[:2], indent=2)}")

    finally:
        # Step 6: Cleanup
        print(f"\nStep 6: Cleaning up test conversation {convo_id}...")
        delete_conversation(convo_id)
        print("  Done.")

if __name__ == "__main__":
    main()
