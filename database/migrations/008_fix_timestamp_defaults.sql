-- Migration 008: Fix timestamp defaults (P1)
-- Adds DB-level DEFAULT NOW() to timestamp columns that previously relied on ORM defaults.
-- Also backfills existing rows that have NULL timestamps.

-- =====================
-- 1. Add column-level defaults
-- =====================

-- times.created_at
ALTER TABLE times ALTER COLUMN created_at SET DEFAULT NOW();

-- partidas.created_at
ALTER TABLE partidas ALTER COLUMN created_at SET DEFAULT NOW();

-- partidas.updated_at
ALTER TABLE partidas ALTER COLUMN updated_at SET DEFAULT NOW();

-- estatisticas_partidas.updated_at
ALTER TABLE estatisticas_partidas ALTER COLUMN updated_at SET DEFAULT NOW();

-- =====================
-- 2. Backfill existing NULL timestamps
-- =====================

-- Backfill times.created_at for records inserted before this migration
UPDATE times SET created_at = NOW() WHERE created_at IS NULL;

-- Backfill partidas.created_at
UPDATE partidas SET created_at = NOW() WHERE created_at IS NULL;

-- Backfill partidas.updated_at
UPDATE partidas SET updated_at = NOW() WHERE updated_at IS NULL;

-- Backfill estatisticas_partidas.updated_at
UPDATE estatisticas_partidas SET updated_at = NOW() WHERE updated_at IS NULL;
