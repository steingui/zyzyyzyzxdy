-- ============================================
-- Multi-League Support - Phase 3: Team Associations
-- ============================================
-- Migration: 007_teams_multi_league.sql
-- Created: 2026-01-31
-- Description: Add league associations to teams
-- ============================================

-- ====================
-- 1. ADD LEAGUE_ID TO TIMES
-- ====================

ALTER TABLE times 
ADD COLUMN league_id INTEGER REFERENCES leagues(id);

CREATE INDEX idx_times_league ON times(league_id);

COMMENT ON COLUMN times.league_id IS 'Liga principal do time';

-- Populate league_id for existing Brasileirão teams
UPDATE times 
SET league_id = (SELECT id FROM leagues WHERE slug = 'brasileirao')
WHERE league_id IS NULL;

-- Make league_id NOT NULL for new entries (but keep nullable for flexibility)
-- ALTER TABLE times ALTER COLUMN league_id SET NOT NULL;

-- ====================
-- 2. TEAM-SEASON JUNCTION TABLE
-- ====================

CREATE TABLE team_seasons (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES times(id) ON DELETE CASCADE,
    season_id INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    active BOOLEAN DEFAULT TRUE,
    position INTEGER,                    -- Final position in league table
    points INTEGER,                      -- Total points
    wins INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    goals_for INTEGER DEFAULT 0,
    goals_against INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',         -- Additional stats (top scorer, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT team_season_unica UNIQUE (team_id, season_id)
);

-- Índices
CREATE INDEX idx_team_seasons_team ON team_seasons(team_id);
CREATE INDEX idx_team_seasons_season ON team_seasons(season_id);
CREATE INDEX idx_team_seasons_position ON team_seasons(season_id, position);

COMMENT ON TABLE team_seasons IS 'Associação entre times e temporadas (participação em campeonatos)';
COMMENT ON COLUMN team_seasons.position IS 'Posição final na tabela de classificação';

-- ====================
-- 3. POPULATE TEAM_SEASONS
-- ====================

-- Associate all existing Brasileirão teams with Brasileirão 2026 season
INSERT INTO team_seasons (team_id, season_id, active)
SELECT 
    t.id,
    s.id,
    TRUE
FROM times t
CROSS JOIN seasons s
WHERE s.league_id = (SELECT id FROM leagues WHERE slug = 'brasileirao')
  AND s.year = 2026
  AND t.league_id = (SELECT id FROM leagues WHERE slug = 'brasileirao')
ON CONFLICT (team_id, season_id) DO NOTHING;

-- ====================
-- 4. HELPER VIEWS
-- ====================

-- View: Current season teams
CREATE OR REPLACE VIEW v_current_season_teams AS
SELECT 
    l.name as league_name,
    l.slug as league_slug,
    s.year as season_year,
    t.id as team_id,
    t.nome as team_name,
    ts.position,
    ts.points,
    ts.wins,
    ts.draws,
    ts.losses,
    ts.goals_for,
    ts.goals_against,
    (ts.goals_for - ts.goals_against) as goal_difference
FROM team_seasons ts
JOIN times t ON t.id = ts.team_id
JOIN seasons s ON s.id = ts.season_id
JOIN leagues l ON l.id = s.league_id
WHERE s.is_current = TRUE
ORDER BY l.name, ts.position NULLS LAST, ts.points DESC;

COMMENT ON VIEW v_current_season_teams IS 'Times participantes das temporadas atuais com estatísticas';

-- ====================
-- 5. UPDATE FUNCTION FOR STATS
-- ====================

-- Function to update team_seasons stats from partidas
CREATE OR REPLACE FUNCTION update_team_season_stats(p_season_id INTEGER)
RETURNS void AS $$
BEGIN
    -- Update home team stats
    UPDATE team_seasons ts
    SET 
        wins = subq.wins,
        draws = subq.draws,
        losses = subq.losses,
        goals_for = subq.goals_for,
        goals_against = subq.goals_against,
        points = (subq.wins * 3) + subq.draws,
        updated_at = CURRENT_TIMESTAMP
    FROM (
        SELECT 
            time_casa_id as team_id,
            COUNT(*) FILTER (WHERE gols_casa > gols_fora) as wins,
            COUNT(*) FILTER (WHERE gols_casa = gols_fora) as draws,
            COUNT(*) FILTER (WHERE gols_casa < gols_fora) as losses,
            SUM(gols_casa) as goals_for,
            SUM(gols_fora) as goals_against
        FROM partidas
        WHERE season_id = p_season_id AND status = 'finished'
        GROUP BY time_casa_id
    ) subq
    WHERE ts.team_id = subq.team_id AND ts.season_id = p_season_id;
    
    -- Update away team stats
    UPDATE team_seasons ts
    SET 
        wins = COALESCE(ts.wins, 0) + subq.wins,
        draws = COALESCE(ts.draws, 0) + subq.draws,
        losses = COALESCE(ts.losses, 0) + subq.losses,
        goals_for = COALESCE(ts.goals_for, 0) + subq.goals_for,
        goals_against = COALESCE(ts.goals_against, 0) + subq.goals_against,
        points = (COALESCE(ts.wins, 0) + subq.wins) * 3 + (COALESCE(ts.draws, 0) + subq.draws),
        updated_at = CURRENT_TIMESTAMP
    FROM (
        SELECT 
            time_fora_id as team_id,
            COUNT(*) FILTER (WHERE gols_fora > gols_casa) as wins,
            COUNT(*) FILTER (WHERE gols_fora = gols_casa) as draws,
            COUNT(*) FILTER (WHERE gols_fora < gols_casa) as losses,
            SUM(gols_fora) as goals_for,
            SUM(gols_casa) as goals_against
        FROM partidas
        WHERE season_id = p_season_id AND status = 'finished'
        GROUP BY time_fora_id
    ) subq
    WHERE ts.team_id = subq.team_id AND ts.season_id = p_season_id;
    
    RAISE NOTICE 'Team stats updated for season %', p_season_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_team_season_stats IS 'Atualiza estatísticas dos times baseado em partidas finalizadas';

-- ====================
-- VERIFICATION QUERIES
-- ====================

-- Verify team associations
-- SELECT 
--     l.name as league,
--     s.year,
--     COUNT(DISTINCT ts.team_id) as num_teams
-- FROM team_seasons ts
-- JOIN seasons s ON s.id = ts.season_id
-- JOIN leagues l ON l.id = s.league_id
-- GROUP BY l.name, s.year
-- ORDER BY l.name, s.year DESC;

-- View current season teams
-- SELECT * FROM v_current_season_teams WHERE league_slug = 'brasileirao';
