-- Runs once on first Postgres container boot (docker-entrypoint-initdb.d).
-- The pgvector extension is created per-database by the alembic migration /
-- test fixtures, so only the test database itself is needed here.
CREATE DATABASE context_engine_test;
