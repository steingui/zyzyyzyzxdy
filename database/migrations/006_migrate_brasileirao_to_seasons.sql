-- ============================================
-- Multi-League Support - Phase 2: Migrate Existing Data
-- ============================================
-- Migration: 006_migrate_brasileirao_to_seasons.sql
-- Created: 2026-01-31
-- Description: Add season_id to partidas and migrate existing Brasileirão data
-- ============================================

-- ====================
-- 1. ADD SEASON_ID TO PARTIDAS
-- ====================

-- Add column (nullable first to allow existing data)
ALTER TABLE partidas 
ADD COLUMN season_id INTEGER REFERENCES seasons(id);

-- Índice para performance
CREATE INDEX idx_partidas_season ON partidas(season_id, rodada);

COMMENT ON COLUMN partidas.season_id IS 'Temporada a qual esta partida pertence';

-- ====================
-- 2. POPULATE SEASON_ID
-- ====================

-- Migrate all existing partidas to Brasileirão 2026 season
UPDATE partidas 
SET season_id = (
    SELECT s.id 
    FROM seasons s 
    JOIN leagues l ON l.id = s.league_id 
    WHERE l.slug = 'brasileirao' AND s.year = 2026
)
WHERE season_id IS NULL;

-- Verify migration
DO $$
DECLARE
    unmigrated_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO unmigrated_count FROM partidas WHERE season_id IS NULL;
    
    IF unmigrated_count > 0 THEN
        RAISE EXCEPTION 'Migration failed: % partidas still have NULL season_id', unmigrated_count;
    ELSE
        RAISE NOTICE 'Success: All partidas migrated to season';
    END IF;
END $$;

-- ====================
-- 3. MAKE SEASON_ID REQUIRED
-- ====================

-- Now make it NOT NULL
ALTER TABLE partidas 
ALTER COLUMN season_id SET NOT NULL;

-- ====================
-- 4. UPDATE CONSTRAINTS
-- ====================

-- Drop old unique constraint (rodada, time_casa, time_fora)
ALTER TABLE partidas 
DROP CONSTRAINT IF EXISTS partida_unica;

-- Add new unique constraint including season
ALTER TABLE partidas 
ADD CONSTRAINT partida_unica UNIQUE (season_id, rodada, time_casa_id, time_fora_id);

-- Remove rodada check constraint (will validate per league in application)
ALTER TABLE partidas 
DROP CONSTRAINT IF EXISTS partidas_rodada_check;

-- ====================
-- 5. UPDATE METADATA COLUMNS
-- ====================

-- Add metadata to partidas if not exists (for league-specific data)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'partidas' AND column_name = 'metadata'
    ) THEN
        ALTER TABLE partidas ADD COLUMN metadata JSONB DEFAULT '{}';
    END IF;
END $$;

-- ====================
-- VERIFICATION QUERIES
-- ====================

-- Verify all partidas have season_id
-- SELECT 
--     COUNT(*) as total_partidas,
--     COUNT(season_id) as with_season,
--     COUNT(*) - COUNT(season_id) as without_season
-- FROM partidas;

-- Verify season association
-- SELECT 
--     l.name as league,
--     s.year,
--     COUNT(p.id) as num_partidas
-- FROM partidas p
-- JOIN seasons s ON s.id = p.season_id
-- JOIN leagues l ON l.id = s.league_id
-- GROUP BY l.name, s.year
-- ORDER BY l.name, s.year DESC;
