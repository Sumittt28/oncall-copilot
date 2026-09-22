"""GitHub API client for fetching commits and PRs."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

logger = logging.getLogger(__name__)

# GitHub API base URL
GITHUB_API_BASE = "https://api.github.com"

# Timeouts
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 30.0


class GitHubError(Exception):
    """Base exception for GitHub API errors."""

    pass


class GitHubAuthError(GitHubError):
    """Raised when authentication fails."""

    pass


class GitHubNotFoundError(GitHubError):
    """Raised when repository is not found."""

    pass


class GitHubRateLimitError(GitHubError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, reset_at: datetime | None = None):
        super().__init__(message)
        self.reset_at = reset_at


@dataclass
class GitHubCommit:
    """A GitHub commit."""

    sha: str
    message: str
    author_name: str
    author_email: str
    committed_at: datetime
    url: str
    files_changed: list[str]

    @property
    def short_sha(self) -> str:
        """Get short SHA (7 chars)."""
        return self.sha[:7]

    @property
    def first_line(self) -> str:
        """Get first line of commit message."""
        return self.message.split("\n")[0]


@dataclass
class GitHubPullRequest:
    """A GitHub pull request."""

    number: int
    title: str
    state: str  # open, closed, merged
    author: str
    created_at: datetime
    merged_at: datetime | None
    url: str
    head_sha: str


class GitHubClient:
    """Client for GitHub API."""

    def __init__(self, access_token: str):
        """Initialize the client.

        Args:
            access_token: GitHub personal access token.
        """
        self.access_token = access_token
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "GitHubClient":
        """Enter async context."""
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=httpx.Timeout(CONNECT_TIMEOUT, read=READ_TIMEOUT),
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, path: str, **kwargs: object) -> dict:  # type: ignore[type-arg]
        """Make an authenticated request to GitHub API.

        Args:
            method: HTTP method.
            path: API path (without base URL).
            **kwargs: Additional request arguments.

        Returns:
            JSON response data.

        Raises:
            GitHubAuthError: If authentication fails.
            GitHubNotFoundError: If resource not found.
            GitHubRateLimitError: If rate limit exceeded.
            GitHubError: For other errors.
        """
        if not self._client:
            raise GitHubError("Client not initialized. Use async context manager.")

        try:
            response = await self._client.request(method, path, **kwargs)  # type: ignore[arg-type]

            if response.status_code == 401:
                raise GitHubAuthError("Invalid or expired access token")

            if response.status_code == 403:
                # Check for rate limit
                remaining = response.headers.get("X-RateLimit-Remaining", "1")
                if remaining == "0":
                    reset_timestamp = int(response.headers.get("X-RateLimit-Reset", "0"))
                    reset_at = datetime.fromtimestamp(reset_timestamp, tz=UTC) if reset_timestamp else None
                    raise GitHubRateLimitError("Rate limit exceeded", reset_at=reset_at)
                raise GitHubAuthError("Access forbidden")

            if response.status_code == 404:
                raise GitHubNotFoundError(f"Resource not found: {path}")

            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

        except httpx.TimeoutException as e:
            raise GitHubError(f"Request timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            raise GitHubError(f"HTTP error: {e}") from e

    async def get_repository(self, owner: str, repo: str) -> dict:  # type: ignore[type-arg]
        """Get repository information.

        Args:
            owner: Repository owner (user or organization).
            repo: Repository name.

        Returns:
            Repository data.
        """
        return await self._request("GET", f"/repos/{owner}/{repo}")

    async def list_commits(
        self,
        owner: str,
        repo: str,
        since: datetime | None = None,
        until: datetime | None = None,
        branch: str | None = None,
        per_page: int = 30,
    ) -> list[GitHubCommit]:
        """List commits from a repository.

        Args:
            owner: Repository owner.
            repo: Repository name.
            since: Only commits after this date.
            until: Only commits before this date.
            branch: Branch name (defaults to default branch).
            per_page: Number of commits per page.

        Returns:
            List of commits.
        """
        params: dict[str, str | int] = {"per_page": per_page}

        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        if branch:
            params["sha"] = branch

        data = await self._request("GET", f"/repos/{owner}/{repo}/commits", params=params)

        commits = []
        for item in data:
            commit_data = item.get("commit", {})
            author_data = commit_data.get("author", {})

            # Get files changed (requires another API call, so we'll skip for listing)
            commits.append(
                GitHubCommit(
                    sha=item.get("sha", ""),
                    message=commit_data.get("message", ""),
                    author_name=author_data.get("name", "Unknown"),
                    author_email=author_data.get("email", ""),
                    committed_at=datetime.fromisoformat(
                        author_data.get("date", "").replace("Z", "+00:00")
                    ),
                    url=item.get("html_url", ""),
                    files_changed=[],  # Would require additional API call
                )
            )

        return commits

    async def get_commit(self, owner: str, repo: str, sha: str) -> GitHubCommit:
        """Get a specific commit with files changed.

        Args:
            owner: Repository owner.
            repo: Repository name.
            sha: Commit SHA.

        Returns:
            Commit with file information.
        """
        data = await self._request("GET", f"/repos/{owner}/{repo}/commits/{sha}")

        commit_data = data.get("commit", {})
        author_data = commit_data.get("author", {})
        files = data.get("files", [])

        return GitHubCommit(
            sha=data.get("sha", ""),
            message=commit_data.get("message", ""),
            author_name=author_data.get("name", "Unknown"),
            author_email=author_data.get("email", ""),
            committed_at=datetime.fromisoformat(
                author_data.get("date", "").replace("Z", "+00:00")
            ),
            url=data.get("html_url", ""),
            files_changed=[f.get("filename", "") for f in files],
        )

    async def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        sort: str = "updated",
        direction: str = "desc",
        per_page: int = 30,
    ) -> list[GitHubPullRequest]:
        """List pull requests from a repository.

        Args:
            owner: Repository owner.
            repo: Repository name.
            state: PR state (open, closed, all).
            sort: Sort field (created, updated, popularity).
            direction: Sort direction (asc, desc).
            per_page: Number of PRs per page.

        Returns:
            List of pull requests.
        """
        params = {
            "state": state,
            "sort": sort,
            "direction": direction,
            "per_page": per_page,
        }

        data = await self._request("GET", f"/repos/{owner}/{repo}/pulls", params=params)

        prs = []
        for item in data:
            merged_at = item.get("merged_at")
            prs.append(
                GitHubPullRequest(
                    number=item.get("number", 0),
                    title=item.get("title", ""),
                    state="merged" if merged_at else item.get("state", ""),
                    author=item.get("user", {}).get("login", "Unknown"),
                    created_at=datetime.fromisoformat(
                        item.get("created_at", "").replace("Z", "+00:00")
                    ),
                    merged_at=datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
                    if merged_at
                    else None,
                    url=item.get("html_url", ""),
                    head_sha=item.get("head", {}).get("sha", ""),
                )
            )

        return prs

    async def verify_token(self) -> bool:
        """Verify that the access token is valid.

        Returns:
            True if token is valid.
        """
        try:
            await self._request("GET", "/user")
            return True
        except GitHubAuthError:
            return False
