-- ============================================
-- Multi-League Support - Phase 1: New Tables
-- ============================================
-- Migration: 005_multi_league_support.sql
-- Created: 2026-01-31
-- Description: Add leagues and seasons tables for multi-league support
-- ============================================

-- ====================
-- 1. LEAGUES TABLE
-- ====================

CREATE TABLE leagues (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,           -- "Premier League", "Brasileirão Série A"
    slug VARCHAR(50) NOT NULL UNIQUE,            -- "premier-league", "brasileirao"
    country VARCHAR(100) NOT NULL,               -- "Inglaterra", "Brasil"
    confederation VARCHAR(20),                   -- "UEFA", "CONMEBOL"
    num_teams INTEGER DEFAULT 20,
    num_rounds INTEGER DEFAULT 38,               -- 38 for most, 34 for Bundesliga
    ogol_slug VARCHAR(100),                      -- Slug usado no ogol.com.br
    metadata JSONB DEFAULT '{}',                 -- Market value, tier, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para queries rápidas
CREATE INDEX idx_leagues_slug ON leagues(slug);
CREATE INDEX idx_leagues_country ON leagues(country);

-- Comentários
COMMENT ON TABLE leagues IS 'Registro de competições/ligas de futebol';
COMMENT ON COLUMN leagues.slug IS 'Identificador único usado em URLs da API';
COMMENT ON COLUMN leagues.ogol_slug IS 'Slug usado no ogol.com.br (ex: campeonato-espanhol)';

-- ====================
-- 2. SEASONS TABLE
-- ====================

CREATE TABLE seasons (
    id SERIAL PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,                       -- 2024, 2025, 2026
    start_date DATE,
    end_date DATE,
    is_current BOOLEAN DEFAULT FALSE,
    ogol_edition_id VARCHAR(50),                 -- External ID from ogol.com.br (e.g., "184443")
    metadata JSONB DEFAULT '{}',                 -- Champion, top scorer, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Uma liga pode ter apenas uma temporada por ano
    CONSTRAINT season_unica UNIQUE (league_id, year),
    
    -- Validação: ano deve ser razoável
    CONSTRAINT year_valid CHECK (year BETWEEN 1900 AND 2100)
);

-- Índices
CREATE INDEX idx_seasons_league ON seasons(league_id, year DESC);
CREATE INDEX idx_seasons_current ON seasons(league_id, is_current) WHERE is_current = TRUE;

-- Comentários
COMMENT ON TABLE seasons IS 'Temporadas de cada liga (ex: Brasileirão 2024, Premier League 2025/26)';
COMMENT ON COLUMN seasons.is_current IS 'Indica se é a temporada atual (apenas uma por liga)';
COMMENT ON COLUMN seasons.ogol_edition_id IS 'ID da edição no ogol.com.br para scraping';

-- ====================
-- 3. INITIAL DATA
-- ====================

-- Insert Brasileirão
INSERT INTO leagues (name, slug, country, confederation, num_teams, num_rounds, ogol_slug, metadata)
VALUES (
    'Brasileirão Série A',
    'brasileirao',
    'Brasil',
    'CONMEBOL',
    20,
    38,
    'brasileirao',
    '{"tier": 1, "market_value": "1.5B"}'::jsonb
);

-- Insert other major leagues (ready for future scraping)
INSERT INTO leagues (name, slug, country, confederation, num_teams, num_rounds, ogol_slug, metadata)
VALUES 
(
    'Premier League',
    'premier-league',
    'Inglaterra',
    'UEFA',
    20,
    38,
    'premier-league',
    '{"tier": 1, "market_value": "11.9B"}'::jsonb
),
(
    'La Liga',
    'la-liga',
    'Espanha',
    'UEFA',
    20,
    38,
    'campeonato-espanhol',
    '{"tier": 1, "market_value": "5.35B"}'::jsonb
),
(
    'Bundesliga',
    'bundesliga',
    'Alemanha',
    'UEFA',
    18,
    34,
    'bundesliga',
    '{"tier": 1, "market_value": "4.8B"}'::jsonb
),
(
    'Serie A',
    'serie-a',
    'Itália',
    'UEFA',
    20,
    38,
    'serie-a',
    '{"tier": 1, "market_value": "4.2B"}'::jsonb
),
(
    'Ligue 1',
    'ligue-1',
    'França',
    'UEFA',
    18,
    34,
    'liga-francesa',
    '{"tier": 1, "market_value": "3.5B"}'::jsonb
);

-- Create current season for Brasileirão (assuming existing data is 2026)
INSERT INTO seasons (league_id, year, is_current, start_date)
VALUES (
    (SELECT id FROM leagues WHERE slug = 'brasileirao'),
    2026,
    TRUE,
    '2026-04-01'  -- Adjust based on actual season start
);

-- ====================
-- 4. HELPER FUNCTION
-- ====================

-- Function to ensure only one current season per league
CREATE OR REPLACE FUNCTION ensure_single_current_season()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_current = TRUE THEN
        -- Desmarcar outras temporadas da mesma liga
        UPDATE seasons 
        SET is_current = FALSE 
        WHERE league_id = NEW.league_id 
          AND id != NEW.id 
          AND is_current = TRUE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_single_current_season
BEFORE INSERT OR UPDATE ON seasons
FOR EACH ROW
EXECUTE FUNCTION ensure_single_current_season();

-- ====================
-- VERIFICATION QUERIES
-- ====================

-- Verify leagues
-- SELECT * FROM leagues ORDER BY country, name;

-- Verify seasons
-- SELECT l.name, s.year, s.is_current 
-- FROM seasons s 
-- JOIN leagues l ON l.id = s.league_id 
-- ORDER BY l.name, s.year DESC;
