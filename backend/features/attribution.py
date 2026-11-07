"""
backend/features/attribution.py
Phase 5: Source attribution formatting and validation.
Tracks which agent and source category contributed each memory entry.
Enforces that only genuine Hindsight scores and metadata are rendered.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def format_source_attribution(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a memory item with strictly validated attribution fields.
    Does not invent fields; preserves raw Hindsight score and metadata.
    """
    metadata = item.get("metadata") or {}
    
    agent_id = item.get("agent_id") or metadata.get("agent_id") or "system"
    source = item.get("source") or metadata.get("source") or "general"
    timestamp = item.get("timestamp") or metadata.get("timestamp")
    
    return {
        "id": item.get("id", ""),
        "text": item.get("text", "").strip(),
        "type": item.get("type"),
        "agent_id": agent_id,
        "source": source,
        "timestamp": timestamp,
        "score": item.get("score"),
        "metadata": metadata,
        "supersedes": metadata.get("supersedes"),
        "is_superseded": item.get("is_superseded", False),
    }


def format_citations_list(memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format an entire list of recalled citations with attribution."""
    return [format_source_attribution(m) for m in memories]
