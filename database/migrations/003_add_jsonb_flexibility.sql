-- ============================================
-- Migration 003: Hybrid Flexibility (JSONB)
-- ============================================
-- Adds metadata columns to handle unpredictable scraping changes
-- without breaking the relational schema.

-- Add metadata column to 'partidas'
ALTER TABLE partidas ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Add metadata column to 'estatisticas_partida'
ALTER TABLE estatisticas_partida ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';
ALTER TABLE estatisticas_partida ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Add Source ID and metadata to 'jogadores' for better identity tracking
ALTER TABLE jogadores ADD COLUMN IF NOT EXISTS id_fonte VARCHAR(100);
ALTER TABLE jogadores ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Create an index for JSONB metadata for performance
CREATE INDEX IF NOT EXISTS idx_partidas_metadata ON partidas USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_estatisticas_metadata ON estatisticas_partida USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_jogadores_metadata ON jogadores USING GIN (metadata);

-- Trigger for updated_at in estatisticas_partida
CREATE OR REPLACE TRIGGER update_estatisticas_updated_at 
    BEFORE UPDATE ON estatisticas_partida 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
