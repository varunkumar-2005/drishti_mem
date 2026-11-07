#!/usr/bin/env python3
"""
scripts/demo_context_pack.py
Demonstrates the OneContext core workflow:
1. Create a fresh project
2. Ingest 2 documents
3. Query Groq WITHOUT context pack (ungrounded)
4. Query Groq WITH context pack (grounded)
5. Capture a new decision
6. Correct an old decision
7. Print the updated context pack
"""

import os
import sys
import uuid
import time
import requests

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API_URL = os.environ.get("ONECONTEXT_API_URL", os.environ.get("API_URL", "http://localhost:8000"))


def print_step(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    print("Starting OneContext Demo...")
    print(f"Backend API URL: {API_URL}")

    # Check backend health
    try:
        health = requests.get(f"{API_URL}/health", timeout=5).json()
        print(f"Backend Status: {health.get('status')} | Hindsight: {health.get('hindsight')} | Groq: {health.get('groq')}")
    except Exception as exc:
        print(f"Error: Backend is not reachable at {API_URL}. Start the backend first.\n{exc}")
        sys.exit(1)

    # 1. Create fresh project
    print_step("1. CREATE FRESH PROJECT")
    p_id = f"demo-{uuid.uuid4().hex[:6]}"
    res = requests.post(
        f"{API_URL}/projects",
        json={
            "name": f"Cloud Payments Core ({p_id})",
            "description": "Production payment microservice architecture.",
        },
        timeout=15,
    )
    if res.status_code != 201:
        print(f"Failed to create project: {res.text}")
        sys.exit(1)
    project = res.json()
    project_id = project["id"]
    print(f"Created Project: {project['name']} (ID: {project_id})")

    # 2. Ingest 2 short docs
    print_step("2. INGEST 2 SPECIFICATION DOCUMENTS")
    doc_1 = """# Architecture Standards
All external microservice endpoints must strictly implement RESTful HTTP interfaces with OpenAPI v3.1 schemas.
GraphQL and gRPC are prohibited on public internet gateways.
Database pooling is strictly capped at 20 connections per pod to prevent PostgreSQL connection saturation."""

    doc_2 = """# Security Standards
All authentication tokens must use RS256 signed JWTs with a maximum validity lifetime of 15 minutes.
TOTP multi-factor authentication is mandatory on all privileged and tenant-admin accounts.
Plain session cookies are strictly forbidden on cross-origin requests."""

    r1 = requests.post(
        f"{API_URL}/projects/{project_id}/ingest",
        json={"text": doc_1, "source_type": "doc", "source_name": "architecture_standards.md"},
        timeout=30,
    )
    print(f"Ingested doc 1: {r1.json().get('chunks_total')} chunks retained.")

    r2 = requests.post(
        f"{API_URL}/projects/{project_id}/ingest",
        json={"text": doc_2, "source_type": "doc", "source_name": "security_standards.md"},
        timeout=30,
    )
    print(f"Ingested doc 2: {r2.json().get('chunks_total')} chunks retained.")

    # Brief pause for cloud indexing
    print("Waiting 3s for semantic indexing...")
    time.sleep(3)

    # 3. Ask Groq WITHOUT Context Pack
    print_step("3. QUERY GROQ WITHOUT CONTEXT PACK (UNGROUNDED)")
    query = "What is our policy on public API protocols and database pooling?"
    print(f"Question: \"{query}\"\n")
    no_mem = requests.post(
        f"{API_URL}/projects/{project_id}/ask-without-memory",
        json={"question": query},
        timeout=30,
    ).json()
    print("Groq Response (Generic / Ungrounded):")
    print(no_mem.get("answer", "").strip())

    # 4. Generate Context Pack & Ask Groq WITH Context Pack
    print_step("4. GENERATE CONTEXT PACK & QUERY WITH PACK (GROUNDED)")
    pack_res = requests.post(
        f"{API_URL}/projects/{project_id}/context-pack",
        json={"task": query, "target": "generic", "max_chars": 3000},
        timeout=30,
    ).json()

    print("Generated Context Pack:")
    print("-" * 50)
    print(pack_res.get("pack"))
    print("-" * 50)

    # Grounded answer using the project's memory
    with_mem = requests.post(
        f"{API_URL}/projects/{project_id}/ask",
        json={"question": query},
        timeout=30,
    ).json()
    print("\nGroq Response (Grounded in OneContext Project Memory):")
    print(with_mem.get("answer", "").strip())
    print(f"\nModel used: {with_mem.get('model_used')} | Sources cited: {len(with_mem.get('sources', []))}")

    # 5. Capture a new decision
    print_step("5. CAPTURE A NEW DECISION (WITH CONFLICT DETECTION)")
    cap_text = "DECISION-201: Event streaming between internal services must use RabbitMQ with AMQP priority channels."
    cap_res = requests.post(
        f"{API_URL}/projects/{project_id}/capture",
        json={"text": cap_text, "source_name": "DECISION-201"},
        timeout=30,
    ).json()
    print(f"Captured: \"{cap_text}\"")
    print(f"Memory ID: {cap_res.get('memory_id')} | Conflict Detected: {cap_res.get('has_conflict')}")

    # 6. Correct an old decision (Supersede DB pool cap from 20 to 50)
    print_step("6. CORRECT AN OLD DECISION (SUPERSEDE DB POOL CAP)")
    # Find the memory to correct from recall
    recall_res = requests.post(
        f"{API_URL}/projects/{project_id}/recall",
        json={"query": "Database pooling connections per pod"},
        timeout=30,
    ).json()

    results = recall_res.get("results", [])
    if results:
        old_mem = results[0]
        old_id = old_mem["id"]
        old_txt = old_mem["text"]
        new_txt = "DECISION: Database pooling cap is updated to 50 connections per pod following database cluster upgrade."

        corr_res = requests.post(
            f"{API_URL}/projects/{project_id}/correct",
            json={
                "old_memory_id": old_id,
                "new_text": new_txt,
                "agent_id": "architect",
                "reason": "Cluster hardware upgrade",
                "old_memory_text": old_txt,
            },
            timeout=30,
        ).json()
        print(f"Superseded Old Memory ({old_id})")
        print(f"New Decision Recorded: \"{new_txt}\"")
        time.sleep(2)
    else:
        print("Note: No previous memory ID found to supersede directly.")

    # 7. Print the updated context pack
    print_step("7. PRINT UPDATED CONTEXT PACK (TARGET: CURSOR)")
    updated_pack = requests.post(
        f"{API_URL}/projects/{project_id}/context-pack",
        json={"task": "Configure database pool and event messaging client", "target": "cursor", "max_chars": 3000},
        timeout=30,
    ).json()

    print(updated_pack.get("pack"))
    print("\nDemo script completed successfully!")


if __name__ == "__main__":
    main()
