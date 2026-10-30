# RepoViva Graph — starter implementation

A local-first learning project combining a repository similarity graph, a question-concept graph, a local dashboard, and an MCP interface.

## What is implemented

- GitHub repository listing for a public username, or repositories the configured token can access.
- README and language metadata retrieval.
- SQLite persistence.
- Explainable heuristic similarity using language Jaccard similarity, GitHub topic Jaccard similarity, and TF-IDF cosine similarity over description + README.
- Local Cytoscape.js graph dashboard.
- Metadata-based question candidates and shared-concept question edges (bounded to four candidate questions per repository).
- Local answer-attempt tracking and a basic learning-path query.
- MCP tools, resources, and a prompt using the MCP Python SDK v2 API.

## Important limitations

- Similarity is NOT a probability and NOT a measure of duplicated source-code percentage.
- The initial question generator uses README/description/language/topic metadata. It does not yet parse source code or prove that a question is answerable from code.
- The dashboard loads Cytoscape.js from a CDN; the first dashboard load needs Internet access. For a fully offline build, install/vendor Cytoscape via npm and serve a local bundle.
- The starter uses a local fine-grained GitHub Personal Access Token for authenticated account access. A production app should implement GitHub App/OAuth authorization and encrypted/token-store handling rather than a shared .env token.
- The API is intended for local development and binds to 127.0.0.1. Do not expose it publicly without authentication, authorization, rate limits, CSRF/origin protections, and a security review.

## Requirements

- Python 3.11+
- Node.js/npm only if using MCP Inspector through `npx`
- GitHub token is optional for public-only account import, and required to list private repositories/read private README files.

## Setup — Windows PowerShell

```powershell
cd repoviva_graph_starter
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and optionally set `GITHUB_TOKEN` to a fine-grained GitHub token. Only give the permissions needed. At minimum, listing the authenticated user's accessible repositories needs repository Metadata read; reading private README contents also needs Contents read. Never commit `.env`.

## Run the graph dashboard

```powershell
python main.py
```

Open http://127.0.0.1:8000. For public-only use, enter a GitHub username. If `GITHUB_TOKEN` is configured, sync uses the authenticated account's accessible repositories; leave username blank. Start with 20 repos for the first run.

## Test similarity logic

```powershell
pytest -q
```

The tests cover Jaccard similarity, missing feature handling, score bounds, and pair count. After installing dependencies, check that all tests pass before adding features.

## Test the MCP server without Claude Desktop

```powershell
mcp dev repoviva/mcp_server.py
```

The command opens MCP Inspector. Inspect tools, resources, and prompts. The server itself uses stdio; it does not open a TCP port. The MCP SDK v2 line currently documents `MCPServer` and follows the 2026-07-28 protocol revision. Older tutorials that import `FastMCP` from `mcp.server.fastmcp` are v1 examples; do not mix imports between SDK versions.

## Exposed MCP functionality

Tools: `get_portfolio_overview`, `list_repositories_tool`, `get_repository_context`, `compare_repositories`, `get_portfolio_graph`, `find_related_repositories`, `list_interview_questions`, `get_learning_path`.

Resources: `repoviva://portfolio/overview`, `repoviva://portfolio/repositories`.

Prompt: `interview_my_repository`.

## Useful commands

```powershell
# Dashboard/API
python main.py

# MCP Inspector (run in another terminal)
mcp dev repoviva/mcp_server.py

# Run tests
pytest -q

# Check the API docs when the dashboard process is running
# http://127.0.0.1:8000/docs
```

## Intended next milestones

1. Source-file indexing with strict allowlists, file-size limits, symlink/path protections, and secret redaction.
2. AST/tree-sitter extraction of classes, functions, imports, and code symbols.
3. Evidence records with repository, commit SHA, file path, and start/end line numbers.
4. Question relationships for shared concepts, prerequisite relationships, and common code evidence.
5. OAuth/GitHub App onboarding, account selection, token revocation, and data deletion.
6. Incremental indexing, retries, GitHub rate-limit backoff, and cache validators.
7. Semantic embeddings as an optional component evaluated against labelled data.
8. Calibrated evaluations: retrieval precision/recall, ranking metrics, graph quality, latency, and memory usage.
