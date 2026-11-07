"""
scripts/seed_data.py
Populates 18 realistic fintech engineering decisions into OneContext memory.
Simulates ApexPay Technologies (a 12-engineer payments startup).
Includes author agent attribution, timestamps, and intentional conflicting evolutions.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import get_settings
from backend.core.hindsight_client import HindsightWrapper
from backend.core.llm_client import LLMClient
from backend.core.memory_service import MemoryService
from backend.storage import local_db

PROJECT_ID = "apexpay-core"
BANK_ID = f"onecontext-{PROJECT_ID}"

SEED_MEMORIES = [
    {
        "agent_id": "db-architect",
        "source": "architecture_decision",
        "date_offset_days": -45,
        "text": (
            "DECISION: Standardize all transactional persistence on PostgreSQL 16 using async SQLAlchemy "
            "with asyncpg driver. Primary keys must strictly be UUIDv4 to prevent enumeration attacks."
        ),
    },
    {
        "agent_id": "db-architect",
        "source": "data_convention",
        "date_offset_days": -44,
        "text": (
            "CONVENTION: All monetary amounts must be stored as 64-bit integers in minor units (cents). "
            "Floating-point numeric types are strictly prohibited in database schemas and ledger tables."
        ),
    },
    {
        "agent_id": "security-lead",
        "source": "compliance_rule",
        "date_offset_days": -40,
        "text": (
            "DECISION: Customer and API authentication is handled via JWT with a 15-minute access token expiry. "
            "Refresh tokens have a 7-day TTL stored in Redis with automatic rotation on each refresh."
        ),
    },
    {
        "agent_id": "security-lead",
        "source": "compliance_rule",
        "date_offset_days": -38,
        "text": (
            "COMPLIANCE RULE: Any transaction or payout exceeding $10,000 USD requires explicit dual-officer "
            "approval from both the compliance officer and finance director before settlement."
        ),
    },
    {
        "agent_id": "infra-lead",
        "source": "messaging_decision",
        "date_offset_days": -35,
        "text": (
            "DECISION: RabbitMQ is selected as the primary message broker instead of Apache Kafka. "
            "Rationale: We require AMQP 0-9-1 priority queues and dead-letter exchanges for dispute processing."
        ),
    },
    {
        "agent_id": "agent-planner",
        "source": "api_design",
        "date_offset_days": -32,
        "text": (
            "API STANDARD: The public API strictly adheres to RESTful conventions with OpenAPI 3.1 specifications. "
            "URL paths use kebab-case, request/response JSON fields use camelCase, and headers use kebab-case."
        ),
    },
    {
        "agent_id": "agent-planner",
        "source": "api_design_change",
        "date_offset_days": -25,
        "text": (
            "EXPERIMENTAL PROPOSAL: The dashboard engineering team evaluated moving the merchant reporting API "
            "from REST to GraphQL to eliminate over-fetching on mobile dashboards."
        ),
    },
    {
        "agent_id": "agent-planner",
        "source": "architecture_decision",
        "date_offset_days": -18,
        "text": (
            "DECISION (SUPERSEDES EXPERIMENT): Revert the merchant reporting API proposal from GraphQL back to REST. "
            "Rationale: GraphQL broke edge CDN response caching and complicated rate-limiting per customer."
        ),
    },
    {
        "agent_id": "infra-lead",
        "source": "reliability_rule",
        "date_offset_days": -22,
        "text": (
            "DECISION: All mutating endpoints (POST /v1/charges, POST /v1/payouts) require a unique 'Idempotency-Key' "
            "header. Cached responses are retained in Redis for 24 hours to prevent duplicate billings."
        ),
    },
    {
        "agent_id": "incident-lead",
        "source": "incident_postmortem",
        "date_offset_days": -15,
        "text": (
            "INCIDENT LESSON (INC-042): During high traffic load, the database connection pool was exhausted. "
            "Action item: SQLAlchemy pool_size increased to 30, max_overflow set to 20, and pool_recycle set to 1800s."
        ),
    },
    {
        "agent_id": "security-lead",
        "source": "security_policy",
        "date_offset_days": -14,
        "text": (
            "POLICY: Encryption at rest uses AES-256-GCM with customer-managed keys via AWS KMS. "
            "Cardholder data (PAN) must never be stored raw; only PCI-compliant vault tokens are permitted."
        ),
    },
    {
        "agent_id": "security-lead",
        "source": "logging_standard",
        "date_offset_days": -12,
        "text": (
            "LOGGING STANDARD: Zero PII or payment credentials in logs. Any email, address, or phone number "
            "must be masked (e.g. j***@domain.com). All application logs must be output in structured JSON format."
        ),
    },
    {
        "agent_id": "infra-lead",
        "source": "operations_rule",
        "date_offset_days": -10,
        "text": (
            "OPERATIONS RULE: Production deployment freeze begins every Friday at 15:00 UTC and ends Monday at 08:00 UTC. "
            "Only P0 security hotfixes approved by two engineering leads can bypass the freeze."
        ),
    },
    {
        "agent_id": "agent-planner",
        "source": "rate_limiting",
        "date_offset_days": -8,
        "text": (
            "DECISION: Standard API rate limits are configured at 100 requests per second per merchant API key, "
            "enforced via Redis sliding-window algorithm. Rate limit violations return HTTP 429 Too Many Requests."
        ),
    },
    {
        "agent_id": "infra-lead",
        "source": "network_policy",
        "date_offset_days": -6,
        "text": (
            "POLICY: Outbound merchant webhooks have a strict connection timeout of 3.0 seconds and read timeout of 5.0 seconds. "
            "Failed webhooks retry with exponential backoff up to 72 hours before being moved to the dead-letter queue."
        ),
    },
    {
        "agent_id": "agent-planner",
        "source": "service_boundary",
        "date_offset_days": -5,
        "text": (
            "ARCHITECTURE: ApexPay is segmented into three decoupled microservices: Payment Gateway, Accounts Ledger, "
            "and Risk Engine. Cross-service communication occurs asynchronously via RabbitMQ events."
        ),
    },
    {
        "agent_id": "db-architect",
        "source": "database_migration",
        "date_offset_days": -3,
        "text": (
            "CONVENTION: All database schema migrations must use Alembic with backward-compatible additive changes. "
            "Dropping columns or renaming tables requires a 2-release deprecation grace period."
        ),
    },
    {
        "agent_id": "agent-planner",
        "source": "version_pinning",
        "date_offset_days": -1,
        "text": (
            "STANDARD: Python services are pinned to Python 3.11+ and FastAPI 0.115+. "
            "All async database models inherit from DeclarativeBase with strict Mapped[T] type annotations."
        ),
    },
]


def seed(target_project_id: str = PROJECT_ID):
    target_bank_id = f"onecontext-{target_project_id}"

    print("=" * 70)
    print(f"  ONECONTEXT SEED DATA GENERATOR ({target_project_id.upper()})")
    print("=" * 70)

    settings = get_settings()
    local_db.init_db()

    hindsight = HindsightWrapper(settings)
    llm = LLMClient(settings)
    service = MemoryService(hindsight=hindsight, llm=llm, db_module=local_db)

    # 1. Ensure project exists
    existing = local_db.get_project(target_project_id)
    if not existing:
        hindsight.create_bank(
            bank_id=target_bank_id,
            name=f"ApexPay Platform ({target_project_id})",
            mission="Payment processing, ledger accounting, and compliance memory bank.",
        )
        local_db.create_project(
            project_id=target_project_id,
            name="ApexPay Payments Platform",
            description="Core payment processing, risk engine, and dual-officer compliance ledger.",
            bank_id=target_bank_id,
        )
        print(f"[Project] Created '{target_project_id}' with Hindsight bank '{target_bank_id}'")
    else:
        print(f"[Project] Using existing project '{target_project_id}'")

    # 2. Register key agents
    agents_to_register = [
        ("agent-planner", "Lead Architect", "Planner / Architect"),
        ("db-architect", "Database Specialist", "Database Lead"),
        ("security-lead", "Chief Security Officer", "Compliance & Security"),
        ("infra-lead", "Platform & DevOps Lead", "Infrastructure"),
        ("incident-lead", "SRE Lead", "Reliability & Incidents"),
        ("agent-builder", "Core Developer", "Builder / Coder"),
        ("agent-validator", "QA & Compliance Auditor", "Validator"),
    ]
    for aid, name, role in agents_to_register:
        local_db.register_agent(aid, target_project_id, name, role)
    print(f"[Agents] Registered {len(agents_to_register)} agents for '{target_project_id}'.")

    # 3. Retain memories idempotently
    existing_audit = local_db.get_audit(target_project_id, limit=500)
    already_retained = {a["query_or_text"] for a in existing_audit if a["action"] == "retain"}

    print(f"\n[Seeding] Ingesting {len(SEED_MEMORIES)} realistic fintech decisions...")
    now = datetime.now(timezone.utc)
    newly_retained_count = 0

    for idx, item in enumerate(SEED_MEMORIES, 1):
        if item["text"] in already_retained:
            print(f"  [{idx:02d}/18] [{item['agent_id']}] ({item['source']}) -> Already exists, skipped.")
            continue

        res = service.retain(
            project_id=target_project_id,
            bank_id=target_bank_id,
            text=item["text"],
            agent_id=item["agent_id"],
            source=item["source"],
        )
        newly_retained_count += 1
        print(f"  [{idx:02d}/18] [{item['agent_id']}] ({item['source']}) -> Retained")

    if newly_retained_count > 0:
        print(f"\n[Hindsight] Waiting 5 s for indexing {newly_retained_count} new memories...")
        time.sleep(5)
    else:
        print("\n[Hindsight] No new memories needed retention (already fully seeded).")

    # Verify recall
    sample_query = "What is our policy for transactions above $10,000?"
    sample_results = service.recall(target_project_id, target_bank_id, sample_query, max_results=3)
    print(f"\n[Verification Query] '{sample_query}'")
    print(f"Recalled {len(sample_results)} results:")
    for r in sample_results:
        print(f"  - (Author: {r.get('agent_id')}) {r.get('text')[:100]}...")

    print("\n" + "=" * 70)
    print(f"  SEEDING COMPLETE ({newly_retained_count} added, {len(SEED_MEMORIES) - newly_retained_count} preserved)")
    print("=" * 70)


if __name__ == "__main__":
    proj_arg = sys.argv[1] if len(sys.argv) > 1 else PROJECT_ID
    seed(proj_arg)
