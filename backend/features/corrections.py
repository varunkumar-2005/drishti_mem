"""
backend/features/corrections.py
Phase 5: Memory updates and supersession management.
Allows an engineer or agent to correct an outdated or contradicted memory.
Records supersedes metadata so that subsequent recalls and /ask prefer the newest memory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from backend.core.broadcaster import broadcaster


class CorrectionsManager:
    """Manages memory corrections and historical supersession."""

    def __init__(self, memory_service, db_module):
        self.service = memory_service
        self.db = db_module

    def correct(
        self,
        project_id: str,
        bank_id: str,
        old_memory_id: str,
        new_text: str,
        agent_id: str = "user",
        reason: str = "",
        old_memory_text: str = "",
    ) -> Dict[str, Any]:
        """
        Retain a corrective memory that explicitly supersedes old_memory_id.
        Records the relationship and superseded text so recall prioritizes the latest truth
        and filters out all derived facts/observations from the superseded retain.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Retain the new memory in Hindsight with supersedes metadata
        retain_res = self.service.retain(
            project_id=project_id,
            bank_id=bank_id,
            text=new_text,
            agent_id=agent_id,
            source="correction",
            check_conflict=False,  # deliberate correction
            metadata={
                "supersedes": old_memory_id,
                "superseded_text": old_memory_text[:200] if old_memory_text else "",
                "correction_reason": reason,
                "corrected_at": now_iso,
            },
        )

        new_memory_id = retain_res["memory_id"]

        # 2. Record supersession relationship and original text in SQLite
        corr_record = self.db.record_correction(
            project_id=project_id,
            old_memory_id=old_memory_id,
            new_memory_id=new_memory_id,
            reason=reason,
            old_memory_text=old_memory_text,
            created_at=now_iso,
        )

        # 3. Log audit trail
        self.db.log_audit(
            project_id=project_id,
            agent_id=agent_id,
            action="correct",
            query_or_text=f"Supersedes {old_memory_id}: {new_text[:120]} (Reason: {reason})",
            result_count=1,
            timestamp=now_iso,
        )

        # 4. Record event for live room
        corr_event = self.db.record_event(
            project_id=project_id,
            type="correction",
            title=f"Correction by {agent_id}",
            body=f"New: {new_text}\nSuperseded: {old_memory_text}\nReason: {reason}",
            author=agent_id,
        )
        if corr_event:
            broadcaster.publish_nowait(project_id, corr_event)

        return {
            "memory_id": new_memory_id,
            "old_memory_id": old_memory_id,
            "supersedes": old_memory_id,
            "project_id": project_id,
            "reason": reason,
            "timestamp": now_iso,
            "status": "corrected",
        }
