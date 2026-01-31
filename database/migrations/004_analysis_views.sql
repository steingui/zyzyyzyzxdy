-- ============================================
-- Migration 004: Comprehensive Analysis Views
-- ============================================

-- View principal: Partidas com todas as relações e scouts básicos
CREATE OR REPLACE VIEW v_partidas_detalhadas AS
SELECT 
    p.id as partida_id,
    p.rodada,
    t1.nome as time_casa,
    p.gols_casa,
    p.gols_fora,
    t2.nome as time_fora,
    e.nome as estadio,
    a.nome as arbitro,
    p.data_hora,
    s.posse_casa,
    s.posse_fora,
    s.chutes_casa,
    s.chutes_fora,
    s.xg_casa,
    s.xg_fora,
    p.status,
    p.url_fonte
FROM partidas p
JOIN times t1 ON p.time_casa_id = t1.id
JOIN times t2 ON p.time_fora_id = t2.id
LEFT JOIN estadios e ON p.estadio_id = e.id
LEFT JOIN arbitros a ON p.arbitro_id = a.id
LEFT JOIN estatisticas_partida s ON p.id = s.partida_id;

-- View de Médias de xG por Time
CREATE OR REPLACE VIEW v_ranking_xg AS
SELECT 
    time,
    COUNT(*) as jogos,
    ROUND(AVG(xg_favor), 2) as xg_favor_medio,
    ROUND(AVG(xg_contra), 2) as xg_contra_medio
FROM (
    SELECT time_casa as time, xg_casa as xg_favor, xg_fora as xg_contra FROM v_partidas_detalhadas WHERE status = 'finished'
    UNION ALL
    SELECT time_fora as time, xg_fora as xg_favor, xg_casa as xg_contra FROM v_partidas_detalhadas WHERE status = 'finished'
) sub
GROUP BY time
ORDER BY xg_favor_medio DESC;
