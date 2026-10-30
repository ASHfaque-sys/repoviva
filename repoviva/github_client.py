"""Minimal GitHub REST client; never log or return the token."""
from __future__ import annotations

import base64
import time
from typing import Any
import requests

from .config import GITHUB_API_VERSION, MAX_README_CHARS

API = "https://api.github.com"


class GitHubAPIError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "RepoViva-Graph-Local-Prototype",
        })
        if token:
            self.session.headers["Authorization"] = f"Bearer {token.strip()}"

    def _get(self, url: str, params: dict[str, Any] | None = None, timeout: int = 20) -> Any:
        try:
            response = self.session.get(url, params=params, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            raise GitHubAPIError(f"Network error connecting to GitHub: {exc}") from exc

        if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
            reset = response.headers.get("X-RateLimit-Reset", "unknown")
            raise GitHubAPIError(f"GitHub rate limit reached. Reset epoch: {reset}. Try again later.")
        if response.status_code == 404:
            raise GitHubAPIError("GitHub resource was not found or this token cannot access it.")
        if response.status_code == 401:
            raise GitHubAPIError("GitHub rejected the token. Check it and its permissions.")
        if response.status_code >= 400:
            message = ""
            try:
                message = response.json().get("message", "")
            except ValueError:
                pass
            raise GitHubAPIError(f"GitHub API returned HTTP {response.status_code}: {message or 'request failed'}")
        try:
            return response.json()
        except ValueError as exc:
            raise GitHubAPIError("GitHub API returned a non-JSON response.") from exc

    def list_repositories(self, username: str | None = None, max_repositories: int = 100) -> list[dict[str, Any]]:
        max_repositories = max(1, min(int(max_repositories), 200))
        results: list[dict[str, Any]] = []
        page = 1
        while len(results) < max_repositories:
            if username and username.strip():
                url = f"{API}/users/{username.strip()}/repos"
                params = {"type": "owner", "sort": "pushed", "direction": "desc", "per_page": 100, "page": page}
            elif self.session.headers.get("Authorization"):
                url = f"{API}/user/repos"
                params = {"visibility": "all", "affiliation": "owner,collaborator,organization_member",
                          "sort": "pushed", "direction": "desc", "per_page": 100, "page": page}
            else:
                raise GitHubAPIError("Enter a public GitHub username or configure GITHUB_TOKEN in .env.")
            batch = self._get(url, params)
            if not isinstance(batch, list) or not batch:
                break
            results.extend(batch)
            if len(batch) < 100:
                break
            page += 1
            time.sleep(0.05)
        return results[:max_repositories]

    def _get_optional(self, url: str, params: dict[str, Any] | None = None, timeout: int = 10) -> Any | None:
        try:
            return self._get(url, params, timeout=timeout)
        except Exception:
            # Languages and README are optional enrichments; network timeouts,
            # permission restrictions (403), or missing files (404) should never fail portfolio sync.
            return None

    def enrich_repository(self, item: dict[str, Any]) -> dict[str, Any]:
        full_name = item.get("full_name", "")
        owner_login = item.get("owner", {}).get("login", "")
        name = item.get("name", "")
        languages_payload = self._get_optional(f"{API}/repos/{full_name}/languages") or {}
        languages = sorted(str(key) for key in languages_payload.keys())

        readme_text = ""
        readme_payload = self._get_optional(f"{API}/repos/{full_name}/readme")
        if isinstance(readme_payload, dict) and readme_payload.get("content"):
            try:
                readme_text = base64.b64decode(readme_payload["content"]).decode("utf-8", errors="replace")
            except (ValueError, KeyError):
                readme_text = ""
        readme_text = readme_text[:MAX_README_CHARS]

        return {
            "github_id": item.get("id"),
            "full_name": full_name,
            "name": name,
            "owner": owner_login,
            "html_url": item.get("html_url", f"https://github.com/{full_name}"),
            "description": item.get("description") or "",
            "default_branch": item.get("default_branch") or "main",
            "language": item.get("language"),
            "languages": languages or ([item["language"]] if item.get("language") else []),
            "topics": sorted(str(t) for t in item.get("topics", []) if isinstance(t, str)),
            "stars": int(item.get("stargazers_count") or 0),
            "forks": int(item.get("forks_count") or 0),
            "is_private": bool(item.get("private", False)),
            "pushed_at": item.get("pushed_at"),
            "readme_text": readme_text,
        }

    def fetch_portfolio(self, username: str | None = None, max_repositories: int = 100) -> list[dict[str, Any]]:
        raw_repos = self.list_repositories(username, max_repositories)
        enriched = []
        for index, raw in enumerate(raw_repos, start=1):
            enriched.append(self.enrich_repository(raw))
        return enriched
