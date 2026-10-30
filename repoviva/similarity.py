"""Explainable repository similarity. Scores are heuristic similarity estimates, not probabilities."""
from __future__ import annotations
from itertools import combinations
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

WEIGHTS = {"technology": 0.40, "topics": 0.20, "content": 0.40}


def jaccard(left: list[str], right: list[str]) -> float | None:
    a, b = {x.casefold() for x in left if x}, {x.casefold() for x in right if x}
    if not a or not b:
        return None
    union = a | b
    return len(a & b) / len(union) if union else None


def _text(repo: dict[str, Any]) -> str:
    description = repo.get("description") or ""
    readme = repo.get("readme_text") or ""
    return f"{description}\n{readme[:20000]}".strip()


def score_pair(a: dict[str, Any], b: dict[str, Any], text_score: float | None = None) -> dict[str, Any]:
    tech = jaccard(a.get("languages", []), b.get("languages", []))
    topics = jaccard(a.get("topics", []), b.get("topics", []))
    # Content score is computed for the whole portfolio with TF-IDF. A text_score is passed here.
    available = {"technology": tech, "topics": topics, "content": text_score}
    usable = {key: value for key, value in available.items() if value is not None}
    denominator = sum(WEIGHTS[key] for key in usable)
    overall = sum(float(value) * WEIGHTS[key] for key, value in usable.items()) / denominator if denominator else 0.0
    shared_languages = sorted(set(a.get("languages", [])) & set(b.get("languages", [])))
    shared_topics = sorted(set(a.get("topics", [])) & set(b.get("topics", [])))
    return {
        "source": a["full_name"],
        "target": b["full_name"],
        "overall_score": round(overall, 4),
        "technology_score": round(tech, 4) if tech is not None else None,
        "topic_score": round(topics, 4) if topics is not None else None,
        "content_score": round(text_score, 4) if text_score is not None else None,
        "evidence": {
            "shared_languages": shared_languages,
            "shared_topics": shared_topics,
            "score_weights": WEIGHTS,
            "content_method": "TF-IDF cosine similarity over description + README",
            "interpretation": "Heuristic similarity score; not a probability and not code-duplication percentage.",
        },
    }


def calculate_edges(repositories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    repos = sorted(repositories, key=lambda r: r["full_name"].casefold())
    if len(repos) < 2:
        return []

    texts = [_text(repo) for repo in repos]
    if any(text for text in texts):
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=10000)
        try:
            matrix = vectorizer.fit_transform(texts)
            similarities = cosine_similarity(matrix, dense_output=True)
        except ValueError:
            similarities = None
    else:
        similarities = None

    edges = []
    for i, j in combinations(range(len(repos)), 2):
        text_score: float | None = None
        if similarities is not None and texts[i] and texts[j]:
            text_score = float(similarities[i, j])
        edge = score_pair(repos[i], repos[j], text_score)
        edges.append(edge)
    return edges


def compare_two(repositories: list[dict[str, Any]], full_name_a: str, full_name_b: str) -> dict[str, Any] | None:
    a = next((r for r in repositories if r["full_name"].casefold() == full_name_a.casefold()), None)
    b = next((r for r in repositories if r["full_name"].casefold() == full_name_b.casefold()), None)
    if not a or not b:
        return None
    edge = next((e for e in calculate_edges([a, b]) if {e["source"], e["target"]} == {a["full_name"], b["full_name"]}), None)
    return edge
