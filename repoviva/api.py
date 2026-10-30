from __future__ import annotations
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import STATIC_DIR, GITHUB_TOKEN
from .db import (
    init_db, portfolio_overview, list_repositories, list_questions,
    list_question_edges, save_answer, learning_path,
)
from .service import sync_portfolio, recalculate, graph_payload
from .mcp_server import mcp

app = FastAPI(title="RepoViva Graph", version="0.1.0",
              description="Repository similarity, interview-learning graph, and remote MCP server.")

# Security & CORS: Allow MCP clients and web dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
init_db()

# Mount remote MCP endpoints (/sse and /messages)
sse_app = mcp.sse_app()
app.routes.extend(sse_app.routes)


class SyncRequest(BaseModel):
    username: str | None = Field(default=None, max_length=39, description="Required for public-account mode; ignored when GITHUB_TOKEN is configured.")
    max_repositories: int = Field(default=100, ge=1, le=200)


class AnswerRequest(BaseModel):
    question_id: int = Field(ge=1)
    answer_text: str = Field(min_length=1, max_length=10000)
    self_rating: int = Field(ge=1, le=5)
    notes: str = Field(default="", max_length=2000)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
def status() -> dict[str, Any]:
    data = portfolio_overview()
    data["github_token_configured"] = bool(GITHUB_TOKEN)
    return data


@app.get("/api/repositories")
def repositories(limit: int = Query(default=200, ge=1, le=500)) -> list[dict[str, Any]]:
    output = []
    for repo in list_repositories(limit):
        repo.pop("readme_text", None)
        output.append(repo)
    return output


@app.get("/api/graph")
def repository_graph(min_similarity: float = Query(default=0.15, ge=0, le=1),
                     max_nodes: int = Query(default=100, ge=1, le=200)) -> dict[str, Any]:
    return graph_payload(min_similarity=min_similarity, max_nodes=max_nodes)


@app.get("/api/question-graph")
def question_graph(min_score: float = Query(default=0.5, ge=0, le=1),
                   limit: int = Query(default=300, ge=1, le=1000)) -> dict[str, Any]:
    questions = list_questions(limit=limit)
    allowed = {int(q["id"]) for q in questions}
    edges = [e for e in list_question_edges(min_score=min_score, limit=5000)
             if int(e["source_id"]) in allowed and int(e["target_id"]) in allowed]
    nodes = [{"data": {
        "id": f"q{q['id']}", "question_id": q["id"],
        "label": (q["question_text"][:76] + "…") if len(q["question_text"]) > 76 else q["question_text"],
        "question_text": q["question_text"], "repo_full_name": q["repo_full_name"],
        "concept": q["concept"], "difficulty": q["difficulty"],
        "evidence_type": q["evidence_type"], "evidence_ref": q["evidence_ref"],
        "evidence_excerpt": q["evidence_excerpt"],
    }} for q in questions]
    edge_nodes = [{"data": {
        "id": f"q{e['source_id']}::q{e['target_id']}::{e['relation_type']}",
        "source": f"q{e['source_id']}", "target": f"q{e['target_id']}",
        "score": e["score"], "label": f"{e['score'] * 100:.0f}%",
        "relation_type": e["relation_type"], "explanation": e["explanation"],
    }} for e in edges]
    return {"nodes": nodes, "edges": edge_nodes,
            "meta": {"question_count": len(nodes), "edge_count": len(edge_nodes)}}


@app.get("/api/questions")
def questions(repo_full_name: str | None = None,
              limit: int = Query(default=300, ge=1, le=1000)) -> list[dict[str, Any]]:
    return list_questions(repo_full_name=repo_full_name, limit=limit)


@app.get("/api/learning-path")
def learning_path_endpoint(limit: int = Query(default=10, ge=1, le=100)) -> list[dict[str, Any]]:
    return learning_path(limit)


@app.post("/api/answers")
def submit_answer(request: AnswerRequest) -> dict[str, Any]:
    try:
        attempt_id = save_answer(request.question_id, request.answer_text,
                                 request.self_rating, request.notes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"attempt_id": attempt_id, "saved": True}


@app.post("/api/sync")
def sync(request: SyncRequest) -> dict[str, Any]:
    try:
        return sync_portfolio(request.username, request.max_repositories)
    except Exception as exc:
        # Avoid returning stack traces, environment variables, or token material.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/recalculate")
def recalculate_endpoint() -> dict[str, Any]:
    try:
        return recalculate()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not recalculate local graph. Check server logs.") from exc
