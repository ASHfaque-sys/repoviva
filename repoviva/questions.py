"""Deterministic starter questions. Treat these as scaffolding, not deep code understanding."""
from __future__ import annotations
from itertools import combinations
from typing import Any

from .db import list_questions, replace_question_edges, save_questions, list_repositories

LANGUAGE_TEMPLATES = {
    "python": "Where does Python appear in {repo}, and why is it a suitable choice for that part of the system?",
    "javascript": "What responsibilities does JavaScript have in {repo}, and how is it tested?",
    "typescript": "What benefits does TypeScript provide in {repo}, and where are its types enforced?",
    "java": "Which parts of {repo} are implemented in Java, and what design choices matter most?",
    "c++": "Which performance or memory concerns matter in the C++ parts of {repo}?",
    "go": "What concurrency or deployment considerations matter for the Go code in {repo}?",
    "rust": "How does {repo} use Rust's ownership and error-handling model?",
}


def _readme_excerpt(text: str, max_chars: int = 360) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip() and not line.strip().startswith("#")]
    return " ".join(lines)[:max_chars]


def rebuild_questions() -> int:
    repos = list_repositories(500)
    generated: list[dict[str, Any]] = []
    for repo in repos:
        name = repo["full_name"]
        excerpt = _readme_excerpt(repo.get("readme_text", "")) or (repo.get("description") or "No README description available.")[:360]
        languages = repo.get("languages", [])
        for language in languages[:2]:
            template = LANGUAGE_TEMPLATES.get(language.casefold(),
                f"What trade-offs does {language} introduce in {{repo}}, and how would you validate those trade-offs?")
            generated.append({
                "repo_full_name": name,
                "question_text": template.format(repo=name),
                "concept": f"language:{language.casefold()}",
                "difficulty": "intermediate",
                "evidence_type": "repository_metadata",
                "evidence_ref": f"{name}: language metadata",
                "evidence_excerpt": excerpt,
            })
        for topic in repo.get("topics", [])[:1]:
            generated.append({
                "repo_full_name": name,
                "question_text": f"How does the concept '{topic}' contribute to {name}, and what evidence in the project supports your explanation?",
                "concept": f"topic:{topic.casefold()}",
                "difficulty": "intermediate",
                "evidence_type": "repository_metadata",
                "evidence_ref": f"{name}: GitHub topic '{topic}'",
                "evidence_excerpt": excerpt,
            })
        if repo.get("description") or repo.get("readme_text"):
            generated.append({
                "repo_full_name": name,
                "question_text": f"Explain the problem {name} solves, its major components, and one important design trade-off.",
                "concept": "project:architecture",
                "difficulty": "beginner",
                "evidence_type": "readme_or_description",
                "evidence_ref": f"{name}: README / description",
                "evidence_excerpt": excerpt,
            })

    save_questions(generated)
    all_questions = list_questions(limit=1000)
    edges: list[dict[str, Any]] = []
    # For the starter version, question relations represent shared concepts only.
    # Cross-repository source-code dependencies are a later milestone.
    for q1, q2 in combinations(all_questions, 2):
        if q1["id"] == q2["id"] or q1["concept"] != q2["concept"]:
            continue
        if q1["repo_full_name"] == q2["repo_full_name"]:
            continue
        edges.append({
            "source_id": q1["id"], "target_id": q2["id"],
            "relation_type": "shared_concept", "score": 1.0,
            "explanation": f"Both questions concern {q1['concept']}; this is an exact metadata tag match, not a learned probability.",
        })
    replace_question_edges(edges)
    return len(generated)
