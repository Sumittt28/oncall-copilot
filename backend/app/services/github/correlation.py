"""Commit correlation service for incident investigation."""

import logging
from dataclasses import dataclass
from datetime import timedelta

from app.core.encryption import decrypt_token
from app.models.incident import Incident
from app.models.repository import Repository
from app.services.github.client import GitHubClient, GitHubCommit, GitHubError

logger = logging.getLogger(__name__)

# Default correlation window (commits within this time before incident are flagged)
DEFAULT_CORRELATION_WINDOW_MINUTES = 60


@dataclass
class CommitCorrelation:
    """A correlated commit with relevance information."""

    commit: GitHubCommit
    minutes_before_incident: int
    relevance_score: float  # 0-1, higher = more relevant
    correlation_reason: str

    @property
    def evidence_id(self) -> str:
        """Generate evidence ID for this commit."""
        return f"commit-{self.commit.short_sha}"

    @property
    def evidence_content(self) -> str:
        """Generate evidence content for RAG."""
        files_str = ", ".join(self.commit.files_changed[:5]) if self.commit.files_changed else "unknown files"
        if len(self.commit.files_changed) > 5:
            files_str += f" (+{len(self.commit.files_changed) - 5} more)"

        return f"""Commit: {self.commit.short_sha}
Author: {self.commit.author_name}
Time: {self.minutes_before_incident} minutes before incident
Files: {files_str}

{self.commit.message}"""


async def correlate_commits_with_incident(
    repository: Repository,
    incident: Incident,
    window_minutes: int = DEFAULT_CORRELATION_WINDOW_MINUTES,
) -> list[CommitCorrelation]:
    """Find commits that may be related to an incident.

    Looks for commits made within the correlation window before
    the incident was created.

    Args:
        repository: The repository to search.
        incident: The incident to correlate.
        window_minutes: Time window in minutes before incident to search.

    Returns:
        List of correlated commits, sorted by relevance.
    """
    if not incident.created_at:
        logger.warning(f"Incident {incident.id} has no created_at timestamp")
        return []

    # Calculate time window
    incident_time = incident.created_at
    window_start = incident_time - timedelta(minutes=window_minutes)

    # Parse repository name
    parts = repository.github_full_name.split("/")
    if len(parts) != 2:
        logger.error(f"Invalid repository name: {repository.github_full_name}")
        return []

    owner, repo = parts

    try:
        async with GitHubClient(decrypt_token(repository.access_token)) as client:
            # Fetch commits in the time window
            commits = await client.list_commits(
                owner=owner,
                repo=repo,
                since=window_start,
                until=incident_time,
                branch=repository.default_branch,
                per_page=50,  # Get more commits to ensure we have the window covered
            )

            correlations = []
            for commit in commits:
                # Calculate minutes before incident
                time_diff = incident_time - commit.committed_at
                minutes_before = int(time_diff.total_seconds() / 60)

                # Skip commits after incident (shouldn't happen with until filter)
                if minutes_before < 0:
                    continue

                # Skip commits outside window
                if minutes_before > window_minutes:
                    continue

                # Calculate relevance score
                # Higher score for commits closer to incident time
                relevance = 1.0 - (minutes_before / window_minutes)
                relevance = max(0.0, min(1.0, relevance))

                # Determine correlation reason
                if minutes_before <= 15:
                    reason = "Committed immediately before incident"
                elif minutes_before <= 30:
                    reason = "Committed shortly before incident"
                else:
                    reason = "Committed within correlation window"

                correlations.append(
                    CommitCorrelation(
                        commit=commit,
                        minutes_before_incident=minutes_before,
                        relevance_score=relevance,
                        correlation_reason=reason,
                    )
                )

            # Sort by relevance (most relevant first)
            correlations.sort(key=lambda c: c.relevance_score, reverse=True)

            logger.info(
                f"Found {len(correlations)} correlated commits for incident {incident.id}"
            )
            return correlations

    except GitHubError as e:
        logger.error(f"GitHub API error during correlation: {e}")
        return []


def calculate_commit_relevance(
    commit: GitHubCommit,
    incident: Incident,
    minutes_before: int,
    window_minutes: int,
) -> float:
    """Calculate relevance score for a commit.

    Factors:
    1. Time proximity (closer = more relevant)
    2. Keyword matching in commit message
    3. File types changed

    Args:
        commit: The commit to score.
        incident: The incident to correlate with.
        minutes_before: Minutes before the incident.
        window_minutes: Total window size in minutes.

    Returns:
        Relevance score between 0 and 1.
    """
    # Base score from time proximity (0.5 weight)
    time_score = 1.0 - (minutes_before / window_minutes)
    time_score = max(0.0, time_score) * 0.5

    # Keyword matching score (0.3 weight)
    keyword_score = 0.0
    incident_keywords = set(incident.title.lower().split())
    incident_keywords.update(incident.description.lower().split())

    commit_words = set(commit.message.lower().split())
    matching_words = incident_keywords & commit_words

    if matching_words:
        # Normalize by incident keywords count
        keyword_score = len(matching_words) / len(incident_keywords) * 0.3

    # File type score (0.2 weight)
    file_score = 0.0
    if commit.files_changed:
        # Higher score for config/deployment files
        high_risk_patterns = [
            ".env",
            "config",
            "docker",
            "deploy",
            "kubernetes",
            "k8s",
            "helm",
            "terraform",
            ".yaml",
            ".yml",
        ]
        for filename in commit.files_changed:
            filename_lower = filename.lower()
            if any(pattern in filename_lower for pattern in high_risk_patterns):
                file_score = 0.2
                break

    return min(1.0, time_score + keyword_score + file_score)
