

from __future__ import annotations

import re
from dataclasses import dataclass

from gim_shared.constants import (
    DEFAULT_TECH_KEYWORDS,
    JUNK_PATTERNS,
    TECH_KEYWORDS_BY_LANGUAGE,
    TEMPLATE_HEADERS,
)

JUNK_REGEXES: list[re.Pattern[str]] = [re.compile(re.escape(pattern), re.IGNORECASE) for pattern in JUNK_PATTERNS]


@dataclass
class QScoreComponents:

    has_code: bool
    has_headers: bool
    tech_weight: float
    is_junk: bool


def compute_q_score(components: QScoreComponents) -> float:
    return (
        0.4 * float(components.has_code)
        + 0.3 * float(components.has_headers)
        + 0.2 * components.tech_weight
        - 0.5 * float(components.is_junk)
    )


def extract_components(title: str, body: str, language: str) -> QScoreComponents:
    has_code = "```" in body

    body_lower = body.lower()
    has_headers = any(header.lower() in body_lower for header in TEMPLATE_HEADERS)

    keywords = TECH_KEYWORDS_BY_LANGUAGE.get(language, DEFAULT_TECH_KEYWORDS)
    combined_text = f"{title} {body}".lower()
    keyword_hits = sum(1 for kw in keywords if kw.lower() in combined_text)
    tech_weight = min(1.0, keyword_hits / 3.0)

    is_junk = any(pattern.search(body) for pattern in JUNK_REGEXES)

    return QScoreComponents(
        has_code=has_code,
        has_headers=has_headers,
        tech_weight=tech_weight,
        is_junk=is_junk,
    )


def passes_quality_gate(score: float, threshold: float = 0.6) -> bool:
    return score >= threshold


def evaluate_issue(title: str, body: str, language: str, threshold: float = 0.6) -> tuple[float, bool]:
    components = extract_components(title, body, language)
    score = compute_q_score(components)
    return score, passes_quality_gate(score, threshold)
