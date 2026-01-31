-- ============================================
-- Migration 002: Adicionar Stats Detalhadas de Jogadores
-- ============================================
-- Data: 2026-01-31
-- Descrição: Adiciona suporte a estatísticas avançadas (xG, heatmaps, duelos) via JSONB na tabela de escalações.

-- Adicionar coluna JSONB flexível para estatísticas (defesa, passe, ataque)
ALTER TABLE escalacoes ADD COLUMN stats JSONB DEFAULT '{}'::jsonb;

-- Adicionar coluna para qualidade da nota (visual/UX)
ALTER TABLE escalacoes ADD COLUMN rating_qualidade VARCHAR(20); -- ex: 'bom', 'medio', 'ruim'

-- Criar índice GIN para permitir consultas performáticas dentro do JSON
-- Ex: Buscar jogadores com xG > 1.0 -> WHERE stats->'ataque'->>'gols_esperados' > '1.0'
CREATE INDEX idx_escalacoes_stats ON escalacoes USING gin (stats);

-- Comentários para documentação
COMMENT ON COLUMN escalacoes.stats IS 'Objeto JSON contendo estatísticas detalhadas (defesa, passe, ataque)';
COMMENT ON COLUMN escalacoes.rating_qualidade IS 'Classificação qualitativa da nota (bom, medio, ruim)';
