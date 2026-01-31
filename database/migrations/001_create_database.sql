-- ============================================
-- Brasileirão 2026 - Schema PostgreSQL
-- ============================================
-- Criado em: 2026-01-30
-- Descrição: Schema completo para armazenar estatísticas do Brasileirão
-- ============================================

-- Habilitar extensões úteis
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- Para busca textual fuzzy

-- ============================================
-- TABELAS DE ENTIDADES BASE
-- ============================================

-- Clubes do Brasileirão
CREATE TABLE times (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE,
    sigla VARCHAR(5),
    cidade VARCHAR(100),
    estado CHAR(2),
    escudo_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Atletas
CREATE TABLE jogadores (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    time_atual_id INTEGER REFERENCES times(id) ON DELETE SET NULL,
    posicao VARCHAR(50),
    nacionalidade VARCHAR(100),
    data_nascimento DATE,
    numero_camisa_padrao INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Árbitros da CBF
CREATE TABLE arbitros (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    estado CHAR(2),
    categoria VARCHAR(50), -- FIFA, CBF Nacional, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Estádios
CREATE TABLE estadios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    cidade VARCHAR(100),
    estado CHAR(2),
    capacidade INTEGER,
    dimensoes VARCHAR(20), -- "105x68"
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- TABELA PRINCIPAL: PARTIDAS
-- ============================================

CREATE TABLE partidas (
    id SERIAL PRIMARY KEY,
    rodada INTEGER NOT NULL CHECK (rodada BETWEEN 1 AND 38),
    time_casa_id INTEGER NOT NULL REFERENCES times(id),
    time_fora_id INTEGER NOT NULL REFERENCES times(id),
    gols_casa INTEGER DEFAULT 0,
    gols_fora INTEGER DEFAULT 0,
    gols_casa_intervalo INTEGER,
    gols_fora_intervalo INTEGER,
    data_hora TIMESTAMP NOT NULL,
    estadio_id INTEGER REFERENCES estadios(id),
    arbitro_id INTEGER REFERENCES arbitros(id),
    publico INTEGER,
    url_fonte TEXT UNIQUE,
    status VARCHAR(20) DEFAULT 'scheduled', -- scheduled, live, finished, postponed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT partida_times_diferentes CHECK (time_casa_id != time_fora_id),
    CONSTRAINT partida_unica UNIQUE (rodada, time_casa_id, time_fora_id)
);

-- ============================================
-- ESTATÍSTICAS DA PARTIDA
-- ============================================

CREATE TABLE estatisticas_partida (
    id SERIAL PRIMARY KEY,
    partida_id INTEGER NOT NULL UNIQUE REFERENCES partidas(id) ON DELETE CASCADE,
    
    -- Posse de Bola (%)
    posse_casa DECIMAL(5,2),
    posse_fora DECIMAL(5,2),
    
    -- Finalizações
    chutes_casa INTEGER DEFAULT 0,
    chutes_fora INTEGER DEFAULT 0,
    chutes_gol_casa INTEGER DEFAULT 0,
    chutes_gol_fora INTEGER DEFAULT 0,
    chutes_bloqueados_casa INTEGER DEFAULT 0,
    chutes_bloqueados_fora INTEGER DEFAULT 0,
    chutes_fora_alvo_casa INTEGER DEFAULT 0,
    chutes_fora_alvo_fora INTEGER DEFAULT 0,
    
    -- Escanteios
    escanteios_casa INTEGER DEFAULT 0,
    escanteios_fora INTEGER DEFAULT 0,
    
    -- Métricas Avançadas (xG) - Expected Goals
    xg_casa DECIMAL(5,2),
    xg_fora DECIMAL(5,2),
    xgot_casa DECIMAL(5,2),  -- xG on Target
    xgot_fora DECIMAL(5,2),
    
    -- Passes
    passes_casa INTEGER DEFAULT 0,
    passes_fora INTEGER DEFAULT 0,
    passes_certos_casa INTEGER DEFAULT 0,
    passes_certos_fora INTEGER DEFAULT 0,
    passes_precisao_casa DECIMAL(5,2),  -- 0.87 = 87%
    passes_precisao_fora DECIMAL(5,2),
    
    -- Faltas e Infrações
    faltas_casa INTEGER DEFAULT 0,
    faltas_fora INTEGER DEFAULT 0,
    impedimentos_casa INTEGER DEFAULT 0,
    impedimentos_fora INTEGER DEFAULT 0,
    
    -- Ações Defensivas
    defesas_goleiro_casa INTEGER DEFAULT 0,
    defesas_goleiro_fora INTEGER DEFAULT 0,
    cortes_casa INTEGER DEFAULT 0,
    cortes_fora INTEGER DEFAULT 0,
    interceptacoes_casa INTEGER DEFAULT 0,
    interceptacoes_fora INTEGER DEFAULT 0,
    
    -- Cartões (resumo rápido)
    amarelos_casa INTEGER DEFAULT 0,
    amarelos_fora INTEGER DEFAULT 0,
    vermelhos_casa INTEGER DEFAULT 0,
    vermelhos_fora INTEGER DEFAULT 0,
    
    -- Duelos
    duelos_ganhos_casa INTEGER DEFAULT 0,
    duelos_ganhos_fora INTEGER DEFAULT 0,
    duelos_aereos_ganhos_casa INTEGER DEFAULT 0,
    duelos_aereos_ganhos_fora INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- EVENTOS DO JOGO (Timeline)
-- ============================================

-- Tipos de evento como ENUM para performance
CREATE TYPE tipo_evento AS ENUM (
    'GOL',
    'GOL_CONTRA', 
    'GOL_PENALTI',
    'CARTAO_AMARELO',
    'CARTAO_VERMELHO',
    'SEGUNDO_AMARELO',
    'SUBSTITUICAO',
    'PENALTI_PERDIDO',
    'VAR_REVISAO'
);

CREATE TABLE eventos (
    id SERIAL PRIMARY KEY,
    partida_id INTEGER NOT NULL REFERENCES partidas(id) ON DELETE CASCADE,
    minuto INTEGER NOT NULL CHECK (minuto >= 0 AND minuto <= 120),
    minuto_adicional INTEGER DEFAULT 0,  -- acréscimos (ex: 90+3)
    periodo SMALLINT DEFAULT 1 CHECK (periodo IN (1, 2, 3, 4)), -- 1=1ºT, 2=2ºT, 3=Prorr1, 4=Prorr2
    tipo tipo_evento NOT NULL,
    jogador_id INTEGER REFERENCES jogadores(id),
    jogador_secundario_id INTEGER REFERENCES jogadores(id),  -- Assistência ou quem saiu
    time_id INTEGER REFERENCES times(id),
    descricao TEXT,  -- "Cabeceio após escanteio"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- ESCALAÇÕES
-- ============================================

CREATE TYPE posicao_tatica AS ENUM (
    'GOL', 'ZAG', 'LD', 'LE', 'VOL', 'MC', 'MEI', 'MD', 'ME', 'SA', 'ATA', 'PE', 'PD'
);

CREATE TABLE escalacoes (
    id SERIAL PRIMARY KEY,
    partida_id INTEGER NOT NULL REFERENCES partidas(id) ON DELETE CASCADE,
    jogador_id INTEGER NOT NULL REFERENCES jogadores(id),
    time_id INTEGER NOT NULL REFERENCES times(id),
    titular BOOLEAN DEFAULT TRUE,
    posicao posicao_tatica,
    numero_camisa INTEGER,
    capitao BOOLEAN DEFAULT FALSE,
    nota DECIMAL(3,1),  -- Nota do jogo (ex: 7.5)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT escalacao_unica UNIQUE (partida_id, jogador_id)
);

-- ============================================
-- TABELA AUXILIAR: TÉCNICOS
-- ============================================

CREATE TABLE tecnicos (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    nacionalidade VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE times_tecnicos (
    id SERIAL PRIMARY KEY,
    time_id INTEGER NOT NULL REFERENCES times(id),
    tecnico_id INTEGER NOT NULL REFERENCES tecnicos(id),
    data_inicio DATE NOT NULL,
    data_fim DATE,  -- NULL = atual
    CONSTRAINT periodo_valido CHECK (data_fim IS NULL OR data_fim >= data_inicio)
);

-- ============================================
-- ÍNDICES OTIMIZADOS
-- ============================================

-- >> ÍNDICES MAIS USADOS: Consultas por rodada e time <<

-- Buscar partidas de uma rodada específica
CREATE INDEX idx_partidas_rodada ON partidas(rodada);

-- Buscar partidas de um time (como mandante ou visitante)
CREATE INDEX idx_partidas_time_casa ON partidas(time_casa_id);
CREATE INDEX idx_partidas_time_fora ON partidas(time_fora_id);

-- Buscar partidas por data (ordenação cronológica)
CREATE INDEX idx_partidas_data ON partidas(data_hora DESC);

-- Buscar partidas por status (jogos ao vivo, finalizados)
CREATE INDEX idx_partidas_status ON partidas(status) WHERE status != 'finished';

-- Índice composto: rodada + times (JOIN frequente)
CREATE INDEX idx_partidas_rodada_times ON partidas(rodada, time_casa_id, time_fora_id);

-- >> ÍNDICES PARA EVENTOS <<

-- Buscar eventos de uma partida (sempre usado)
CREATE INDEX idx_eventos_partida ON eventos(partida_id);

-- Buscar gols (para artilharia)
CREATE INDEX idx_eventos_gols ON eventos(jogador_id, tipo) 
    WHERE tipo IN ('GOL', 'GOL_PENALTI');

-- Buscar eventos por time (estatísticas de cartões por time)
CREATE INDEX idx_eventos_time ON eventos(time_id, tipo);

-- Buscar eventos por minuto (análise temporal)
CREATE INDEX idx_eventos_minuto ON eventos(partida_id, minuto);

-- >> ÍNDICES PARA ESCALAÇÕES <<

-- Buscar escalação de uma partida
CREATE INDEX idx_escalacoes_partida ON escalacoes(partida_id);

-- Buscar partidas de um jogador
CREATE INDEX idx_escalacoes_jogador ON escalacoes(jogador_id);

-- Buscar titulares vs reservas
CREATE INDEX idx_escalacoes_titular ON escalacoes(partida_id, titular);

-- >> ÍNDICES PARA JOGADORES <<

-- Busca por nome (trigram para busca fuzzy)
CREATE INDEX idx_jogadores_nome_trgm ON jogadores USING gin (nome gin_trgm_ops);

-- Buscar jogadores por time atual
CREATE INDEX idx_jogadores_time ON jogadores(time_atual_id);

-- >> ÍNDICES PARA ESTATÍSTICAS <<

-- Buscar estatísticas por partida (1:1)
CREATE INDEX idx_estatisticas_partida ON estatisticas_partida(partida_id);

-- Análise de xG
CREATE INDEX idx_estatisticas_xg ON estatisticas_partida(xg_casa, xg_fora);

-- >> ÍNDICES PARA TIMES <<

-- Busca por nome (trigram)
CREATE INDEX idx_times_nome_trgm ON times USING gin (nome gin_trgm_ops);

-- Busca por sigla
CREATE INDEX idx_times_sigla ON times(sigla);

-- ============================================
-- VIEWS ÚTEIS
-- ============================================

-- Tabela de Classificação
CREATE OR REPLACE VIEW v_classificacao AS
WITH resultados AS (
    SELECT 
        t.id AS time_id,
        t.nome AS time,
        t.sigla,
        CASE 
            WHEN p.time_casa_id = t.id THEN 
                CASE 
                    WHEN p.gols_casa > p.gols_fora THEN 3
                    WHEN p.gols_casa = p.gols_fora THEN 1
                    ELSE 0
                END
            ELSE 
                CASE 
                    WHEN p.gols_fora > p.gols_casa THEN 3
                    WHEN p.gols_fora = p.gols_casa THEN 1
                    ELSE 0
                END
        END AS pontos,
        CASE WHEN p.time_casa_id = t.id THEN p.gols_casa ELSE p.gols_fora END AS gp,
        CASE WHEN p.time_casa_id = t.id THEN p.gols_fora ELSE p.gols_casa END AS gc,
        CASE 
            WHEN (p.time_casa_id = t.id AND p.gols_casa > p.gols_fora) 
              OR (p.time_fora_id = t.id AND p.gols_fora > p.gols_casa) THEN 1 ELSE 0 
        END AS vitoria,
        CASE WHEN p.gols_casa = p.gols_fora THEN 1 ELSE 0 END AS empate,
        CASE 
            WHEN (p.time_casa_id = t.id AND p.gols_casa < p.gols_fora) 
              OR (p.time_fora_id = t.id AND p.gols_fora < p.gols_casa) THEN 1 ELSE 0 
        END AS derrota
    FROM times t
    JOIN partidas p ON t.id = p.time_casa_id OR t.id = p.time_fora_id
    WHERE p.status = 'finished'
)
SELECT 
    ROW_NUMBER() OVER (ORDER BY SUM(pontos) DESC, SUM(gp) - SUM(gc) DESC, SUM(gp) DESC) AS posicao,
    time,
    sigla,
    COUNT(*) AS jogos,
    SUM(vitoria) AS vitorias,
    SUM(empate) AS empates,
    SUM(derrota) AS derrotas,
    SUM(gp) AS gols_pro,
    SUM(gc) AS gols_contra,
    SUM(gp) - SUM(gc) AS saldo,
    SUM(pontos) AS pontos
FROM resultados
GROUP BY time_id, time, sigla
ORDER BY pontos DESC, saldo DESC, gols_pro DESC;

-- Artilheiros do Campeonato
CREATE OR REPLACE VIEW v_artilheiros AS
SELECT 
    j.nome AS jogador,
    t.nome AS time,
    t.sigla AS time_sigla,
    COUNT(*) AS gols,
    COUNT(*) FILTER (WHERE e.tipo = 'GOL_PENALTI') AS gols_penalti
FROM eventos e
JOIN jogadores j ON e.jogador_id = j.id
LEFT JOIN times t ON j.time_atual_id = t.id
WHERE e.tipo IN ('GOL', 'GOL_PENALTI')
GROUP BY j.id, j.nome, t.nome, t.sigla
ORDER BY gols DESC, gols_penalti ASC
LIMIT 50;

-- Assistências
CREATE OR REPLACE VIEW v_assistencias AS
SELECT 
    j.nome AS jogador,
    t.nome AS time,
    COUNT(*) AS assistencias
FROM eventos e
JOIN jogadores j ON e.jogador_secundario_id = j.id
LEFT JOIN times t ON j.time_atual_id = t.id
WHERE e.tipo IN ('GOL', 'GOL_PENALTI')
  AND e.jogador_secundario_id IS NOT NULL
GROUP BY j.id, j.nome, t.nome
ORDER BY assistencias DESC
LIMIT 50;

-- Cartões por Time
CREATE OR REPLACE VIEW v_cartoes_time AS
SELECT 
    t.nome AS time,
    COUNT(*) FILTER (WHERE e.tipo = 'CARTAO_AMARELO') AS amarelos,
    COUNT(*) FILTER (WHERE e.tipo = 'CARTAO_VERMELHO') AS vermelhos,
    COUNT(*) FILTER (WHERE e.tipo = 'SEGUNDO_AMARELO') AS segundos_amarelos
FROM eventos e
JOIN times t ON e.time_id = t.id
WHERE e.tipo IN ('CARTAO_AMARELO', 'CARTAO_VERMELHO', 'SEGUNDO_AMARELO')
GROUP BY t.id, t.nome
ORDER BY vermelhos DESC, amarelos DESC;

-- Estatísticas Médias por Time (Casa)
CREATE OR REPLACE VIEW v_stats_media_casa AS
SELECT 
    t.nome AS time,
    COUNT(*) AS jogos_casa,
    ROUND(AVG(e.posse_casa), 1) AS posse_media,
    ROUND(AVG(e.chutes_casa), 1) AS chutes_media,
    ROUND(AVG(e.xg_casa), 2) AS xg_medio,
    ROUND(AVG(p.gols_casa), 2) AS gols_media
FROM partidas p
JOIN times t ON p.time_casa_id = t.id
JOIN estatisticas_partida e ON p.id = e.partida_id
WHERE p.status = 'finished'
GROUP BY t.id, t.nome
ORDER BY xg_medio DESC;

-- ============================================
-- SEED: 20 TIMES DO BRASILEIRÃO 2026
-- ============================================

INSERT INTO times (nome, sigla, cidade, estado) VALUES
('Atlético Mineiro', 'CAM', 'Belo Horizonte', 'MG'),
('Athletico Paranaense', 'CAP', 'Curitiba', 'PR'),
('Bahia', 'BAH', 'Salvador', 'BA'),
('Botafogo', 'BOT', 'Rio de Janeiro', 'RJ'),
('Corinthians', 'COR', 'São Paulo', 'SP'),
('Cruzeiro', 'CRU', 'Belo Horizonte', 'MG'),
('Flamengo', 'FLA', 'Rio de Janeiro', 'RJ'),
('Fluminense', 'FLU', 'Rio de Janeiro', 'RJ'),
('Fortaleza', 'FOR', 'Fortaleza', 'CE'),
('Grêmio', 'GRE', 'Porto Alegre', 'RS'),
('Internacional', 'INT', 'Porto Alegre', 'RS'),
('Juventude', 'JUV', 'Caxias do Sul', 'RS'),
('Mirassol', 'MIR', 'Mirassol', 'SP'),
('Palmeiras', 'PAL', 'São Paulo', 'SP'),
('Red Bull Bragantino', 'RBB', 'Bragança Paulista', 'SP'),
('Santos', 'SAN', 'Santos', 'SP'),
('São Paulo', 'SAO', 'São Paulo', 'SP'),
('Sport', 'SPO', 'Recife', 'PE'),
('Vasco da Gama', 'VAS', 'Rio de Janeiro', 'RJ'),
('Vitória', 'VIT', 'Salvador', 'BA')
ON CONFLICT (nome) DO NOTHING;

-- ============================================
-- FUNÇÕES ÚTEIS
-- ============================================

-- Função para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para updated_at
CREATE TRIGGER update_partidas_updated_at 
    BEFORE UPDATE ON partidas 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jogadores_updated_at 
    BEFORE UPDATE ON jogadores 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- COMENTÁRIOS NAS TABELAS (Documentação)
-- ============================================

COMMENT ON TABLE partidas IS 'Jogos do Brasileirão 2026 - 38 rodadas, 380 partidas';
COMMENT ON TABLE estatisticas_partida IS 'Estatísticas coletivas de cada partida (1:1 com partidas)';
COMMENT ON TABLE eventos IS 'Timeline de gols, cartões e substituições';
COMMENT ON TABLE escalacoes IS 'Formação tática e jogadores escalados';
COMMENT ON COLUMN estatisticas_partida.xg_casa IS 'Expected Goals - métrica de qualidade de finalizações';
COMMENT ON COLUMN eventos.minuto_adicional IS 'Minutos de acréscimo (ex: 90+3 -> minuto=90, minuto_adicional=3)';
