

from datetime import UTC, datetime

GRACE_PERIOD: float = 2.0
BASE_QUALITY: float = 1.0
GRAVITY: float = 1.5


def calculate_survival_score(q_score: float, days_old: float) -> float:
    denominator = (days_old + GRACE_PERIOD) ** GRAVITY
    return (q_score + BASE_QUALITY) / denominator


def days_since(dt: datetime) -> float:
    now = datetime.now(UTC)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    delta = now - dt
    return delta.total_seconds() / 86400.0
