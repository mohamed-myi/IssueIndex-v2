"""Database models for IssueIndex."""

from gim_database.models.identity import LinkedAccount, Session, User
from gim_database.models.ingestion import Issue, Repository
from gim_database.models.persistence import BookmarkedIssue, PersonalNote
from gim_database.models.profiles import UserProfile
from gim_database.models.analytics import RecommendationEvent
from gim_database.models.staging import PendingIssue

__all__ = [
    # Identity
    "User",
    "Session", 
    "LinkedAccount",
    # Ingestion
    "Issue",
    "Repository",
    # Staging
    "PendingIssue",
    # Persistence
    "BookmarkedIssue",
    "PersonalNote",
    # Profiles
    "UserProfile",
    # Analytics
    "RecommendationEvent",
]

