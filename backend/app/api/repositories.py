"""Repository API routes for GitHub integration."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.incident import Incident
from app.models.repository import Repository
from app.services.github.client import (
    GitHubAuthError,
    GitHubClient,
    GitHubError,
    GitHubNotFoundError,
)
from app.services.github.correlation import (
    correlate_commits_with_incident,
)

router = APIRouter()


# ============== Schemas ==============


class RepositoryCreate(BaseModel):
    """Schema for connecting a repository."""

    github_full_name: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$",
        description="Full repository name (owner/repo)",
        examples=["octocat/hello-world"],
    )
    access_token: str = Field(
        ...,
        min_length=10,
        description="GitHub personal access token",
    )
    default_branch: str = Field(
        default="main",
        description="Default branch name",
    )


class RepositoryResponse(BaseModel):
    """Schema for repository response."""

    id: int
    github_full_name: str
    github_url: str
    default_branch: str
    created_at: datetime
    last_synced_at: datetime | None


class RepositoryListResponse(BaseModel):
    """Schema for repository list response."""

    items: list[RepositoryResponse]
    total: int


class CommitResponse(BaseModel):
    """Schema for commit response."""

    sha: str
    short_sha: str
    message: str
    author_name: str
    committed_at: datetime
    url: str
    files_changed: list[str]


class CorrelatedCommitResponse(BaseModel):
    """Schema for correlated commit response."""

    evidence_id: str
    commit: CommitResponse
    minutes_before_incident: int
    relevance_score: float
    correlation_reason: str


class CorrelationResponse(BaseModel):
    """Schema for correlation result."""

    incident_id: int
    repository_id: int
    window_minutes: int
    commits: list[CorrelatedCommitResponse]
    total: int


# ============== Endpoints ==============


@router.post(
    "/repositories",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_repository(
    data: RepositoryCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> RepositoryResponse:
    """Connect a GitHub repository.

    Validates the access token and repository existence before saving.
    """
    # Parse owner/repo
    parts = data.github_full_name.split("/")
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid repository name format. Use owner/repo.",
        )

    owner, repo = parts

    # Verify token and repository
    try:
        async with GitHubClient(data.access_token) as client:
            # Verify token
            if not await client.verify_token():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid GitHub access token",
                )

            # Verify repository exists and is accessible
            repo_data = await client.get_repository(owner, repo)
            github_url = repo_data.get("html_url", f"https://github.com/{data.github_full_name}")
            default_branch = repo_data.get("default_branch", data.default_branch)

    except GitHubAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except GitHubNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{data.github_full_name}' not found or not accessible",
        ) from e
    except GitHubError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API error: {e}",
        ) from e

    # Check if repository already connected
    existing = await db.execute(
        select(Repository).where(
            Repository.github_full_name == data.github_full_name,
            Repository.owner_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository already connected",
        )

    # Create repository
    repository = Repository(
        github_full_name=data.github_full_name,
        github_url=github_url,
        default_branch=default_branch,
        access_token=data.access_token,  # TODO: Encrypt in production
        owner_id=current_user.id,
    )
    db.add(repository)
    await db.commit()
    await db.refresh(repository)

    return RepositoryResponse(
        id=repository.id,
        github_full_name=repository.github_full_name,
        github_url=repository.github_url,
        default_branch=repository.default_branch,
        created_at=repository.created_at,
        last_synced_at=repository.last_synced_at,
    )


@router.get("/repositories", response_model=RepositoryListResponse)
async def list_repositories(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> RepositoryListResponse:
    """List connected repositories."""
    # Count total
    count_result = await db.execute(
        select(Repository).where(Repository.owner_id == current_user.id)
    )
    total = len(count_result.scalars().all())

    # Get paginated results
    result = await db.execute(
        select(Repository)
        .where(Repository.owner_id == current_user.id)
        .order_by(Repository.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    repositories = result.scalars().all()

    return RepositoryListResponse(
        items=[
            RepositoryResponse(
                id=r.id,
                github_full_name=r.github_full_name,
                github_url=r.github_url,
                default_branch=r.default_branch,
                created_at=r.created_at,
                last_synced_at=r.last_synced_at,
            )
            for r in repositories
        ],
        total=total,
    )


@router.get("/repositories/{repository_id}", response_model=RepositoryResponse)
async def get_repository(
    repository_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> RepositoryResponse:
    """Get a specific repository."""
    result = await db.execute(
        select(Repository).where(
            Repository.id == repository_id,
            Repository.owner_id == current_user.id,
        )
    )
    repository = result.scalar_one_or_none()

    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    return RepositoryResponse(
        id=repository.id,
        github_full_name=repository.github_full_name,
        github_url=repository.github_url,
        default_branch=repository.default_branch,
        created_at=repository.created_at,
        last_synced_at=repository.last_synced_at,
    )


@router.delete("/repositories/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_repository(
    repository_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Disconnect a repository."""
    result = await db.execute(
        select(Repository).where(
            Repository.id == repository_id,
            Repository.owner_id == current_user.id,
        )
    )
    repository = result.scalar_one_or_none()

    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    await db.delete(repository)
    await db.commit()


@router.get("/repositories/{repository_id}/commits", response_model=list[CommitResponse])
async def list_commits(
    repository_id: int,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
) -> list[CommitResponse]:
    """List recent commits from a repository."""
    result = await db.execute(
        select(Repository).where(
            Repository.id == repository_id,
            Repository.owner_id == current_user.id,
        )
    )
    repository = result.scalar_one_or_none()

    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    parts = repository.github_full_name.split("/")
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid repository name in database",
        )

    owner, repo = parts

    try:
        async with GitHubClient(repository.access_token) as client:
            commits = await client.list_commits(
                owner=owner,
                repo=repo,
                branch=repository.default_branch,
                per_page=limit,
            )

            return [
                CommitResponse(
                    sha=c.sha,
                    short_sha=c.short_sha,
                    message=c.message,
                    author_name=c.author_name,
                    committed_at=c.committed_at,
                    url=c.url,
                    files_changed=c.files_changed,
                )
                for c in commits
            ]

    except GitHubError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API error: {e}",
        ) from e


@router.get(
    "/incidents/{incident_id}/correlated-commits",
    response_model=CorrelationResponse,
)
async def get_correlated_commits(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
    window_minutes: int = Query(60, ge=5, le=1440, description="Correlation window in minutes"),
) -> CorrelationResponse:
    """Get commits correlated with an incident.

    Finds commits made within the specified time window before
    the incident was created.
    """
    # Get incident
    incident_result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = incident_result.scalar_one_or_none()

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    # Check if incident has a repository
    if incident.repository_id is None:
        return CorrelationResponse(
            incident_id=incident_id,
            repository_id=0,
            window_minutes=window_minutes,
            commits=[],
            total=0,
        )

    # Get repository
    repo_result = await db.execute(
        select(Repository).where(Repository.id == incident.repository_id)
    )
    repository = repo_result.scalar_one_or_none()

    if repository is None:
        return CorrelationResponse(
            incident_id=incident_id,
            repository_id=incident.repository_id,
            window_minutes=window_minutes,
            commits=[],
            total=0,
        )

    # Get correlated commits
    correlations = await correlate_commits_with_incident(
        repository=repository,
        incident=incident,
        window_minutes=window_minutes,
    )

    return CorrelationResponse(
        incident_id=incident_id,
        repository_id=repository.id,
        window_minutes=window_minutes,
        commits=[
            CorrelatedCommitResponse(
                evidence_id=c.evidence_id,
                commit=CommitResponse(
                    sha=c.commit.sha,
                    short_sha=c.commit.short_sha,
                    message=c.commit.message,
                    author_name=c.commit.author_name,
                    committed_at=c.commit.committed_at,
                    url=c.commit.url,
                    files_changed=c.commit.files_changed,
                ),
                minutes_before_incident=c.minutes_before_incident,
                relevance_score=c.relevance_score,
                correlation_reason=c.correlation_reason,
            )
            for c in correlations
        ],
        total=len(correlations),
    )
