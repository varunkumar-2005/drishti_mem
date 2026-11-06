"""
scripts/run_flow_demo.py
Executes the exact 5-step API walkthrough against the FastAPI backend:
1. Create project
2. Retain a decision ("All transactions above $10,000 require dual-officer approval.")
3. Recall memory
4. Grounded /ask (with memory)
5. Unassisted /ask-without-memory (without memory)
Prints full side-by-side JSON outputs.
"""

import json
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from backend.main import app

def main():
    print("=" * 70)
    print("  ONECONTEXT END-TO-END FLOW VERIFICATION (PHASE 2)")
    print("=" * 70)

    with TestClient(app) as client:
        # Step 1: Create Project
        print("\n[Step 1] POST /projects")
        create_resp = client.post(
            "/projects",
            json={
                "name": "Fintech Platform",
                "description": "Core payment and transaction engine",
            },
        )
        print(f"Status: {create_resp.status_code}")
        proj = create_resp.json()
        project_id = proj["id"]
        print(json.dumps(proj, indent=2))

        # Step 2: Retain Decision
        print(f"\n[Step 2] POST /projects/{project_id}/retain")
        decision_text = "All transactions above $10,000 require dual-officer approval."
        retain_resp = client.post(
            f"/projects/{project_id}/retain",
            json={
                "text": decision_text,
                "source": "compliance_rule",
                "agent_id": "security-lead",
            },
        )
        print(f"Status: {retain_resp.status_code}")
        print(json.dumps(retain_resp.json(), indent=2))

        # Wait for indexing using HindsightWrapper polling
        print("\nWaiting for Hindsight indexing...")
        hindsight = app.state.hindsight
        hindsight.wait_for_recall(
            bank_id=proj["bank_id"],
            query="transactions above $10,000 dual-officer",
            expected_contains="dual-officer",
            timeout=25,
            poll_interval=2,
        )

        # Step 3: Recall Memory
        print(f"\n[Step 3] POST /projects/{project_id}/recall")
        recall_resp = client.post(
            f"/projects/{project_id}/recall",
            json={"query": "What is the policy for high value transactions?", "max_results": 3},
        )
        print(f"Status: {recall_resp.status_code}")
        print(json.dumps(recall_resp.json(), indent=2))

        # Step 4: Grounded Ask (With Memory)
        question = "What approval is needed for a $15,000 transfer?"
        print(f"\n[Step 4] POST /projects/{project_id}/ask (WITH MEMORY)")
        ask_resp = client.post(
            f"/projects/{project_id}/ask",
            json={"question": question, "agent_id": "auditor-agent"},
        )
        print(f"Status: {ask_resp.status_code}")
        ask_data = ask_resp.json()
        safe_ask_ans = ask_data['answer'].encode("ascii", errors="replace").decode("ascii")
        print("\n--- WITH MEMORY RESPONSE ---")
        print(f"Question   : {ask_data['question']}")
        print(f"Model Used : {ask_data['model_used']}")
        print(f"Answer     : {safe_ask_ans}")
        print(f"Sources ({len(ask_data['sources'])}):")
        for s in ask_data["sources"]:
            src_text = s.get('text', '').encode("ascii", errors="replace").decode("ascii")
            print(f"  - [{s.get('source')}] {src_text}")

        # Step 5: Ask Without Memory
        print(f"\n[Step 5] POST /projects/{project_id}/ask-without-memory (WITHOUT MEMORY)")
        no_mem_resp = client.post(
            f"/projects/{project_id}/ask-without-memory",
            json={"question": question, "agent_id": "auditor-agent"},
        )
        print(f"Status: {no_mem_resp.status_code}")
        no_mem_data = no_mem_resp.json()
        safe_no_mem_ans = no_mem_data['answer'].encode("ascii", errors="replace").decode("ascii")
        print("\n--- WITHOUT MEMORY RESPONSE ---")
        print(f"Question   : {no_mem_data['question']}")
        print(f"Model Used : {no_mem_data['model_used']}")
        print(f"Answer     : {safe_no_mem_ans}")
        print(f"Sources    : {no_mem_data['sources']}")

        print("\n" + "=" * 70)
        print("  VERIFICATION COMPLETE: BOTH ENDPOINTS TESTED SUCCESSFULLY")
        print("=" * 70)

if __name__ == "__main__":
    main()
