"""
Production Database Integration Tests

SAFETY: All tests in this directory:
- Use hardcoded TEST_USER_UUIDs
- Run within transactions that ROLLBACK (never commit)
- Include explicit WHERE user_id = ... clauses

These tests require DATABASE_URL to be set and will be skipped in CI without DB access.
"""
