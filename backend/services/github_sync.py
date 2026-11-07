"""
backend/services/github_sync.py
GitHub commit synchronization service for OneContext.
Polls GitHub repositories every 45s and synchronizes new commits into Hindsight memory and the live room event stream.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

from backend.core.broadcaster import broadcaster
from backend.storage import local_db

logger = logging.getLogger("onecontext.github_sync")


def get_github_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "OneContext-Sync",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def sync_repo_commits(
    project_id: str,
    repo: str,
    memory_service=None,
    custom_client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Fetch the latest commits for a repo and synchronize new ones into Hindsight & SQLite events.
    Handles rate limits and API errors gracefully.
    """
    repo = repo.strip()
    if not repo:
        return {"status": "error", "message": "No repository specified", "synced_count": 0}

    url = f"https://api.github.com/repos/{repo}/commits?per_page=10"
    headers = get_github_headers()
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        if custom_client:
            res = await custom_client.get(url, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=headers)

        if res.status_code == 403 or res.status_code == 429:
            msg = "GitHub API rate limit exceeded. Provide GITHUB_TOKEN in .env for higher limits."
            logger.warning(f"Project {project_id} ({repo}): {msg}")
            local_db.update_project_github_sync(project_id, now_iso, "rate_limited")
            return {"status": "rate_limited", "message": msg, "synced_count": 0}

        if res.status_code == 404:
            msg = f"Repository '{repo}' not found or private. Ensure owner/repo is correct."
            local_db.update_project_github_sync(project_id, now_iso, "not_found")
            return {"status": "error", "message": msg, "synced_count": 0}

        res.raise_for_status()
        commits = res.json()

        synced_count = 0
        project = local_db.get_project(project_id)
        bank_id = project["bank_id"] if project else f"onecontext-{project_id}"

        for item in reversed(commits):  # Process oldest to newest so timeline is chronological
            sha = item.get("sha")
            if not sha:
                continue

            commit_info = item.get("commit", {})
            message = commit_info.get("message", "").strip()
            author_info = commit_info.get("author", {})
            author_name = author_info.get("name") or item.get("author", {}).get("login") or "GitHub"
            commit_date = author_info.get("date") or now_iso

            # First line of commit message for the title
            headline = message.split("\n")[0][:80] if message else "Commit"
            title = f"Commit {sha[:7]}: {headline}"

            # 1. Deduplicate & Record Event in SQLite
            event = local_db.record_event(
                project_id=project_id,
                type="commit",
                title=title,
                body=f"{message}\nCommit: {sha}\nAuthor: {author_name}\nDate: {commit_date}",
                author=author_name,
                source_ref=sha,
                created_at=commit_date,
            )

            # If event is None, it means (project_id, sha) already existed (deduplicated)
            if not event:
                continue

            synced_count += 1

            # 2. Retain into Hindsight bank if memory service is available
            if memory_service:
                try:
                    memory_service.hindsight.retain(
                        bank_id=bank_id,
                        text=f"[GitHub Commit {sha[:7]}] {message} (Author: {author_name}, Date: {commit_date})",
                        metadata={
                            "source_type": "commit",
                            "sha": sha,
                            "author": author_name,
                            "date": commit_date,
                            "repo": repo,
                        },
                    )
                except Exception as ex:
                    logger.warning(f"Could not retain commit {sha} in Hindsight: {ex}")

            # 3. Broadcast to live room subscribers
            broadcaster.publish_nowait(project_id, event)

        local_db.update_project_github_sync(project_id, now_iso, "synced")
        return {
            "status": "success",
            "message": f"Synced {synced_count} new commits",
            "synced_count": synced_count,
            "last_sync": now_iso,
        }

    except Exception as e:
        err_msg = str(e)
        logger.error(f"Error syncing GitHub commits for {repo}: {err_msg}")
        local_db.update_project_github_sync(project_id, now_iso, f"error: {err_msg[:60]}")
        return {"status": "error", "message": err_msg, "synced_count": 0}


async def run_github_polling_worker(app_state) -> None:
    """Background daemon task polling configured GitHub repos every 45 seconds."""
    logger.info("Starting GitHub sync background worker (interval: 45s)...")
    while True:
        try:
            repos = local_db.list_all_github_projects()
            for r in repos:
                p_id = r["project_id"]
                repo = r["repo"]
                memory_service = getattr(app_state, "memory_service", None)
                await sync_repo_commits(p_id, repo, memory_service=memory_service)
        except Exception as e:
            logger.error(f"GitHub polling worker error: {e}")

        await asyncio.sleep(45)
