"""
Taxonomy service for reference data APIs.
Thin wrapper around constants for API consistency.
"""
import sys
from dataclasses import dataclass
from pathlib import Path

shared_src = Path(__file__).resolve().parent.parent.parent.parent.parent / "packages" / "shared" / "src"
if str(shared_src) not in sys.path:
    sys.path.insert(0, str(shared_src))

from constants import PROFILE_LANGUAGES, STACK_AREAS  # noqa: E402


@dataclass
class StackAreaInfo:
    """Stack area with display label and description."""
    id: str
    label: str
    description: str


def get_languages() -> list[str]:
    """Returns valid language list from PROFILE_LANGUAGES."""
    return list(PROFILE_LANGUAGES)


def get_stack_areas() -> list[StackAreaInfo]:
    """Returns stack areas with id, label, description."""
    return [
        StackAreaInfo(
            id=key,
            label=key.replace("_", " ").title(),
            description=desc,
        )
        for key, desc in STACK_AREAS.items()
    ]


__all__ = [
    "StackAreaInfo",
    "get_languages",
    "get_stack_areas",
]
