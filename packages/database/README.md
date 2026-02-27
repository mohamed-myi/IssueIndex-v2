# Database Package (`packages/database`)

SQLModel models, Alembic migrations, and DB session helpers for IssueIndex.

## Scope

- `gim_database/models/` - canonical ORM models (ingestion, identity, profiles, analytics, staging)
- `migrations/` - Alembic migrations for schema changes
- `gim_database/env.py` - DB configuration/session setup used by apps

## Current Schema Truth (high level)

- Embedding vectors are `VECTOR(256)` across ingestion/profile models
- Analytics tables include `analytics.search_interactions` and `analytics.recommendation_events`
- User session table is `public.session` (singular)

## Tests

```bash
cd packages/database
python3 -m pytest tests -q
```
