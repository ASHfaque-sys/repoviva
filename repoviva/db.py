"""Small SQLite persistence layer. Keep SQL here rather than in the UI/MCP code."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import DB_PATH


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS repositories (
                full_name TEXT PRIMARY KEY,
                github_id INTEGER,
                name TEXT NOT NULL,
                owner TEXT NOT NULL,
                html_url TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                default_branch TEXT NOT NULL DEFAULT 'main',
                language TEXT,
                languages_json TEXT NOT NULL DEFAULT '[]',
                topics_json TEXT NOT NULL DEFAULT '[]',
                stars INTEGER NOT NULL DEFAULT 0,
                forks INTEGER NOT NULL DEFAULT 0,
                is_private INTEGER NOT NULL DEFAULT 0,
                pushed_at TEXT,
                readme_text TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS repository_edges (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                overall_score REAL NOT NULL,
                technology_score REAL,
                topic_score REAL,
                content_score REAL,
                evidence_json TEXT NOT NULL DEFAULT '{}',
                computed_at TEXT NOT NULL,
                PRIMARY KEY (source, target),
                CHECK (source < target),
                FOREIGN KEY (source) REFERENCES repositories(full_name) ON DELETE CASCADE,
                FOREIGN KEY (target) REFERENCES repositories(full_name) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_full_name TEXT NOT NULL,
                question_text TEXT NOT NULL,
                concept TEXT NOT NULL,
                difficulty TEXT NOT NULL DEFAULT 'beginner',
                evidence_type TEXT NOT NULL DEFAULT 'repository_metadata',
                evidence_ref TEXT NOT NULL DEFAULT '',
                evidence_excerpt TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE (repo_full_name, question_text),
                FOREIGN KEY (repo_full_name) REFERENCES repositories(full_name) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS question_edges (
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                relation_type TEXT NOT NULL,
                score REAL NOT NULL,
                explanation TEXT NOT NULL,
                PRIMARY KEY (source_id, target_id, relation_type),
                CHECK (source_id < target_id),
                FOREIGN KEY (source_id) REFERENCES questions(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES questions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS answer_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                answer_text TEXT NOT NULL,
                self_rating INTEGER NOT NULL CHECK (self_rating BETWEEN 1 AND 5),
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_repo_edges_score ON repository_edges(overall_score DESC);
            CREATE INDEX IF NOT EXISTS idx_questions_repo ON questions(repo_full_name);
            CREATE INDEX IF NOT EXISTS idx_answers_question ON answer_attempts(question_id, created_at DESC);
            """
        )


def _decode_repo(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["languages"] = json.loads(item.pop("languages_json", "[]"))
    item["topics"] = json.loads(item.pop("topics_json", "[]"))
    item["is_private"] = bool(item["is_private"])
    return item


def upsert_repositories(repositories: list[dict[str, Any]]) -> int:
    now = utc_now()
    with connection() as conn:
        for repo in repositories:
            conn.execute(
                """INSERT INTO repositories (
                    full_name, github_id, name, owner, html_url, description, default_branch,
                    language, languages_json, topics_json, stars, forks, is_private, pushed_at,
                    readme_text, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(full_name) DO UPDATE SET
                    github_id=excluded.github_id, name=excluded.name, owner=excluded.owner,
                    html_url=excluded.html_url, description=excluded.description,
                    default_branch=excluded.default_branch, language=excluded.language,
                    languages_json=excluded.languages_json, topics_json=excluded.topics_json,
                    stars=excluded.stars, forks=excluded.forks, is_private=excluded.is_private,
                    pushed_at=excluded.pushed_at, readme_text=excluded.readme_text,
                    updated_at=excluded.updated_at""",
                (
                    repo["full_name"], repo.get("github_id"), repo["name"], repo["owner"],
                    repo["html_url"], repo.get("description") or "", repo.get("default_branch") or "main",
                    repo.get("language"), json.dumps(repo.get("languages", [])),
                    json.dumps(repo.get("topics", [])), int(repo.get("stars", 0)),
                    int(repo.get("forks", 0)), int(bool(repo.get("is_private", False))),
                    repo.get("pushed_at"), (repo.get("readme_text") or "")[:20_000], now,
                ),
            )
    return len(repositories)


def list_repositories(limit: int = 500) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM repositories ORDER BY pushed_at DESC, full_name LIMIT ?", (limit,)
        ).fetchall()
    return [_decode_repo(row) for row in rows]


def get_repository(full_name: str) -> dict[str, Any] | None:
    with connection() as conn:
        row = conn.execute("SELECT * FROM repositories WHERE full_name = ?", (full_name,)).fetchone()
    return _decode_repo(row) if row else None


def replace_repository_edges(edges: list[dict[str, Any]]) -> None:
    now = utc_now()
    with connection() as conn:
        conn.execute("DELETE FROM repository_edges")
        for edge in edges:
            source, target = sorted([edge["source"], edge["target"]])
            conn.execute(
                """INSERT INTO repository_edges (
                    source, target, overall_score, technology_score, topic_score,
                    content_score, evidence_json, computed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (source, target, edge["overall_score"], edge.get("technology_score"),
                 edge.get("topic_score"), edge.get("content_score"),
                 json.dumps(edge.get("evidence", {})), now),
            )


def list_repository_edges(min_similarity: float = 0.0, limit: int = 3000) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 10000))
    with connection() as conn:
        rows = conn.execute(
            """SELECT * FROM repository_edges WHERE overall_score >= ?
               ORDER BY overall_score DESC LIMIT ?""", (float(min_similarity), limit)
        ).fetchall()
    output = []
    for row in rows:
        item = dict(row)
        item["evidence"] = json.loads(item.pop("evidence_json"))
        output.append(item)
    return output


def save_questions(questions: list[dict[str, Any]]) -> int:
    with connection() as conn:
        for q in questions:
            conn.execute(
                """INSERT INTO questions (repo_full_name, question_text, concept, difficulty,
                   evidence_type, evidence_ref, evidence_excerpt, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(repo_full_name, question_text) DO UPDATE SET
                   concept=excluded.concept, difficulty=excluded.difficulty,
                   evidence_type=excluded.evidence_type, evidence_ref=excluded.evidence_ref,
                   evidence_excerpt=excluded.evidence_excerpt""",
                (q["repo_full_name"], q["question_text"], q["concept"], q.get("difficulty", "beginner"),
                 q.get("evidence_type", "repository_metadata"), q.get("evidence_ref", ""),
                 q.get("evidence_excerpt", ""), utc_now()),
            )
    return len(questions)


def list_questions(repo_full_name: str | None = None, limit: int = 300) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 1000))
    with connection() as conn:
        if repo_full_name:
            rows = conn.execute(
                "SELECT * FROM questions WHERE repo_full_name=? ORDER BY id LIMIT ?",
                (repo_full_name, limit),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM questions ORDER BY id LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def replace_question_edges(edges: list[dict[str, Any]]) -> None:
    with connection() as conn:
        conn.execute("DELETE FROM question_edges")
        for edge in edges:
            source, target = sorted([int(edge["source_id"]), int(edge["target_id"])])
            conn.execute(
                """INSERT OR REPLACE INTO question_edges
                   (source_id, target_id, relation_type, score, explanation)
                   VALUES (?, ?, ?, ?, ?)""",
                (source, target, edge["relation_type"], float(edge["score"]), edge["explanation"]),
            )


def list_question_edges(min_score: float = 0.0, limit: int = 3000) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 10000))
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM question_edges WHERE score >= ? ORDER BY score DESC LIMIT ?",
            (float(min_score), limit),
        ).fetchall()
    return [dict(row) for row in rows]


def save_answer(question_id: int, answer_text: str, self_rating: int, notes: str = "") -> int:
    if not 1 <= int(self_rating) <= 5:
        raise ValueError("self_rating must be between 1 and 5")
    with connection() as conn:
        cur = conn.execute(
            "INSERT INTO answer_attempts(question_id, answer_text, self_rating, notes, created_at) VALUES (?, ?, ?, ?, ?)",
            (int(question_id), answer_text[:10000], int(self_rating), notes[:2000], utc_now()),
        )
        return int(cur.lastrowid)


def learning_path(limit: int = 10) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    with connection() as conn:
        rows = conn.execute(
            """SELECT q.id, q.repo_full_name, q.question_text, q.concept, q.difficulty,
                    COALESCE(AVG(a.self_rating), 0) AS average_rating,
                    COUNT(a.id) AS attempts
               FROM questions q LEFT JOIN answer_attempts a ON a.question_id=q.id
               GROUP BY q.id
               ORDER BY CASE WHEN COUNT(a.id)=0 THEN 0 ELSE 1 END,
                        COALESCE(AVG(a.self_rating), 0) ASC,
                        q.difficulty DESC, q.id ASC
               LIMIT ?""", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def portfolio_overview() -> dict[str, Any]:
    with connection() as conn:
        repos = conn.execute("SELECT COUNT(*) AS c FROM repositories").fetchone()["c"]
        edges = conn.execute("SELECT COUNT(*) AS c FROM repository_edges").fetchone()["c"]
        questions = conn.execute("SELECT COUNT(*) AS c FROM questions").fetchone()["c"]
        attempts = conn.execute("SELECT COUNT(*) AS c FROM answer_attempts").fetchone()["c"]
        latest = conn.execute("SELECT MAX(updated_at) AS t FROM repositories").fetchone()["t"]
    return {"repositories": repos, "repository_relationships": edges,
            "questions": questions, "answer_attempts": attempts, "last_repository_update": latest}
