
from pydantic import BaseModel

IntentReembedInput = tuple[list[str], str] | None


class IntentData(BaseModel):
    languages: list[str]
    stack_areas: list[str]
    text: str
    experience_level: str | None
    updated_at: str | None


class IntentSource(BaseModel):
    populated: bool
    vector_status: str | None
    data: IntentData | None


class ResumeData(BaseModel):
    skills: list[str]
    job_titles: list[str]
    uploaded_at: str | None


class ResumeSource(BaseModel):
    populated: bool
    vector_status: str | None
    data: ResumeData | None


class GitHubData(BaseModel):
    username: str
    languages: list[str]
    topics: list[str]
    fetched_at: str | None


class GitHubSource(BaseModel):
    populated: bool
    vector_status: str | None
    data: GitHubData | None


class ProfileSources(BaseModel):
    intent: IntentSource
    resume: ResumeSource
    github: GitHubSource


class ProfilePreferences(BaseModel):
    preferred_languages: list[str]
    preferred_topics: list[str]
    min_heat_threshold: float


class FullProfile(BaseModel):
    user_id: str
    optimization_percent: int
    combined_vector_status: str | None
    is_calculating: bool
    onboarding_status: str
    updated_at: str | None
    sources: ProfileSources
    preferences: ProfilePreferences


class IntentProfile(BaseModel):
    languages: list[str]
    stack_areas: list[str]
    text: str
    experience_level: str | None
    vector_status: str | None
    updated_at: str | None


__all__ = [
    "FullProfile",
    "GitHubData",
    "GitHubSource",
    "IntentData",
    "IntentProfile",
    "IntentReembedInput",
    "IntentSource",
    "ProfilePreferences",
    "ProfileSources",
    "ResumeData",
    "ResumeSource",
]
