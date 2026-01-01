"""Survival score calculation for Janitor pruning decisions"""

from datetime import datetime, timezone

# Formula constants
GRACE_PERIOD: float = 2.0   # Adds 2 days to age; prevents infinite scores for new issues
BASE_QUALITY: float = 1.0   # Gives issues with 0 q_score a baseline survival chance
GRAVITY: float = 1.5        # Controls decay speed; age eventually outweighs quality


def calculate_survival_score(q_score: float, days_old: float) -> float:
    """
    S = (Q + beta) / (days_old + gamma)^G
    
    Higher Q scores and younger issues survive longer.
    The gravity exponent ensures old issues are eventually pruned
    regardless of quality.
    """
    denominator = (days_old + GRACE_PERIOD) ** GRAVITY
    return (q_score + BASE_QUALITY) / denominator


def days_since(dt: datetime) -> float:
    """Returns fractional days since given datetime (UTC aware)"""
    now = datetime.now(timezone.utc)
    
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    delta = now - dt
    return delta.total_seconds() / 86400.0

