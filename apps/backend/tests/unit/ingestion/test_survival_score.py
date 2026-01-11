"""Unit tests for survival score calculation"""

from datetime import UTC, datetime, timedelta

from src.ingestion.survival_score import (
    BASE_QUALITY,
    GRACE_PERIOD,
    GRAVITY,
    calculate_survival_score,
    days_since,
)


class TestConstants:
    def test_grace_period_is_2(self):
        assert GRACE_PERIOD == 2.0

    def test_base_quality_is_1(self):
        assert BASE_QUALITY == 1.0

    def test_gravity_is_1_5(self):
        assert GRAVITY == 1.5


class TestCalculateSurvivalScore:
    def test_formula_correctness_known_values(self):
        """S = (Q + 1) / (days + 2)^1.5 with known inputs"""
        # Q=0.8, days=0 -> (0.8 + 1) / (0 + 2)^1.5 = 1.8 / 2.828... = 0.636...
        score = calculate_survival_score(q_score=0.8, days_old=0.0)
        expected = 1.8 / (2.0 ** 1.5)
        assert abs(score - expected) < 0.0001

    def test_zero_q_score_gets_baseline(self):
        """Issues with Q=0 still get BASE_QUALITY survival chance"""
        score = calculate_survival_score(q_score=0.0, days_old=0.0)
        expected = 1.0 / (2.0 ** 1.5)
        assert abs(score - expected) < 0.0001
        assert score > 0

    def test_grace_period_prevents_infinite_score(self):
        """Brand new issues (0 days) dont produce infinite scores"""
        score = calculate_survival_score(q_score=1.0, days_old=0.0)
        assert score < float('inf')
        assert score > 0

    def test_older_issues_score_lower(self):
        """Age decay: 30-day-old issue scores lower than 1-day-old"""
        new_score = calculate_survival_score(q_score=0.8, days_old=1.0)
        old_score = calculate_survival_score(q_score=0.8, days_old=30.0)
        assert old_score < new_score

    def test_higher_q_score_survives_longer(self):
        """Quality boost: higher Q scores produce higher S scores"""
        low_q = calculate_survival_score(q_score=0.2, days_old=5.0)
        high_q = calculate_survival_score(q_score=0.9, days_old=5.0)
        assert high_q > low_q

    def test_negative_q_score_handled(self):
        """Edge case: negative Q (junk penalty) still computes"""
        score = calculate_survival_score(q_score=-0.5, days_old=1.0)
        # (-0.5 + 1) / (1 + 2)^1.5 = 0.5 / 5.196 = 0.096...
        expected = 0.5 / (3.0 ** 1.5)
        assert abs(score - expected) < 0.0001

    def test_very_old_issue_approaches_zero(self):
        """Gravity ensures ancient issues have near-zero survival"""
        score = calculate_survival_score(q_score=1.0, days_old=365.0)
        assert score < 0.001

    def test_exact_threshold_boundary(self):
        """Verify formula at Q=0.6 threshold"""
        score = calculate_survival_score(q_score=0.6, days_old=0.0)
        expected = 1.6 / (2.0 ** 1.5)
        assert abs(score - expected) < 0.0001


class TestDaysSince:
    def test_returns_zero_for_now(self):
        """Current timestamp returns approximately 0 days"""
        now = datetime.now(UTC)
        days = days_since(now)
        assert abs(days) < 0.01  # Within ~15 minutes

    def test_returns_positive_for_past(self):
        """Past timestamps return positive days"""
        past = datetime.now(UTC) - timedelta(days=5)
        days = days_since(past)
        assert 4.9 < days < 5.1

    def test_handles_naive_datetime(self):
        """Naive datetimes treated as UTC"""
        naive_past = datetime.now() - timedelta(days=3)
        days = days_since(naive_past)
        # Allow wider tolerance for timezone differences between now() and utcnow()
        assert 2.5 < days < 3.5

    def test_handles_fractional_days(self):
        """12 hours ago returns 0.5 days"""
        half_day_ago = datetime.now(UTC) - timedelta(hours=12)
        days = days_since(half_day_ago)
        assert 0.4 < days < 0.6

    def test_handles_future_datetime(self):
        """Future timestamps return negative days"""
        future = datetime.now(UTC) + timedelta(days=2)
        days = days_since(future)
        assert days < 0


class TestSurvivalScoreIntegration:
    def test_realistic_scenario_new_high_quality(self):
        """New high-quality issue should have high survival score"""
        score = calculate_survival_score(q_score=0.9, days_old=0.5)
        # (0.9 + 1) / (0.5 + 2)^1.5 = 1.9 / 3.95 = ~0.48
        assert score > 0.4

    def test_realistic_scenario_old_low_quality(self):
        """Old low-quality issue should have low survival score"""
        score = calculate_survival_score(q_score=0.3, days_old=14.0)
        assert score < 0.05

    def test_score_ordering_for_janitor(self):
        """Verify relative ordering for Janitor's bottom-20% logic"""
        issues = [
            ("new_good", calculate_survival_score(0.9, 1.0)),
            ("new_bad", calculate_survival_score(0.3, 1.0)),
            ("old_good", calculate_survival_score(0.9, 30.0)),
            ("old_bad", calculate_survival_score(0.3, 30.0)),
        ]

        sorted_issues = sorted(issues, key=lambda x: x[1], reverse=True)
        order = [i[0] for i in sorted_issues]

        # New good should be first, old bad should be last
        assert order[0] == "new_good"
        assert order[-1] == "old_bad"

