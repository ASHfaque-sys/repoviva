from __future__ import annotations
from typing import Any

from .db import (
    init_db, upsert_repositories, list_repositories, get_repository,
    replace_repository_edges, list_repository_edges, portfolio_overview,
)
from .github_client import GitHubClient
from .similarity import calculate_edges, compare_two
from .questions import rebuild_questions
from .config import GITHUB_TOKEN, MAX_REPOSITORIES


def sync_portfolio(username: str | None = None, max_repositories: int = 100) -> dict[str, Any]:
    init_db()
    limit = max(1, min(int(max_repositories), MAX_REPOSITORIES))
    client = GitHubClient(GITHUB_TOKEN or None)
    repos = client.fetch_portfolio(username=username, max_repositories=limit)
    if not repos:
        target = f"user '{username}'" if username else "the configured account"
        return {
            "synced_repositories": 0,
            "stored_repositories": len(list_repositories(500)),
            "repository_relationships": len(list_repository_edges()),
            "generated_question_candidates": len(list_questions()),
            "mode": "authenticated-account" if GITHUB_TOKEN else "public-account",
            "note": f"No repositories found for {target}.",
        }
    upsert_repositories(repos)
    stored = list_repositories(500)
    edges = calculate_edges(stored)
    replace_repository_edges(edges)
    question_count = rebuild_questions()
    return {
        "synced_repositories": len(repos),
        "stored_repositories": len(stored),
        "repository_relationships": len(edges),
        "generated_question_candidates": question_count,
        "mode": "authenticated-account" if GITHUB_TOKEN else "public-account",
        "note": "Similarity is calculated from language overlap, topic overlap and README/description text; it is not a code-duplication percentage.",
    }


def recalculate() -> dict[str, Any]:
    init_db()
    repos = list_repositories(500)
    edges = calculate_edges(repos)
    replace_repository_edges(edges)
    question_count = rebuild_questions()
    return {"repositories": len(repos), "repository_relationships": len(edges), "question_candidates": question_count}


def graph_payload(min_similarity: float = 0.15, max_nodes: int = 100) -> dict[str, Any]:
    repos = list_repositories(max_nodes)
    allowed = {r["full_name"] for r in repos}
    edges = [e for e in list_repository_edges(min_similarity=min_similarity, limit=5000)
             if e["source"] in allowed and e["target"] in allowed]
    nodes = [{
        "data": {
            "id": r["full_name"], "label": r["name"], "full_name": r["full_name"],
            "url": r["html_url"], "description": r["description"],
            "languages": r["languages"], "topics": r["topics"],
            "stars": r["stars"], "forks": r["forks"], "private": r["is_private"],
            "updated": r["updated_at"],
        }
    } for r in repos]
    edge_nodes = [{
        "data": {
            "id": f"{edge['source']}::{edge['target']}",
            "source": edge["source"], "target": edge["target"],
            "score": edge["overall_score"], "label": f"{edge['overall_score'] * 100:.0f}%",
            "technology_score": edge["technology_score"], "topic_score": edge["topic_score"],
            "content_score": edge["content_score"], "evidence": edge["evidence"],
        }
    } for edge in edges]
    return {"nodes": nodes, "edges": edge_nodes, "meta": {"repository_count": len(nodes), "edge_count": len(edge_nodes), "min_similarity": min_similarity}}
