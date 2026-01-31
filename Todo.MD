# Roadmap do Projeto

## 🚀 Roadmap v2.0 (Próximos Passos)

**DevOps & Infraestrutura**
- [ ] **Hosted DB Migration**: Configurar `.env` para apontar para banco remoto (Neon/Supabase/RDS).
- [ ] **SSL Support**: Garantir que a conexão PostgreSQL aceite `sslmode=require`.
- [ ] **Dockerização**: Facilitar execução local limpa vinculada ao banco remoto.

**Dados & Analytics**
- [ ] **Backfill Histórico**: Script para raspar temporadas passadas (2020-2025).
- [ ] **Dashboard de Visualização**: Criar app (Streamlit/Metabase) para explorar:
    - Ranking de xG vs Gols.
    - Mapa de calor de chutes.
    - Performance de árbitros (Cartões/Faltas).
- [ ] **API Rest**: Expor os dados do PostgreSQL via FastAPI para consumo externo.

**Refinamento Técnico**
- [ ] **Testes Automatizados**: Aumentar cobertura de testes unitários (`tests/`).
- [ ] **Proxy Rotation**: Integrar rotação de proxies para escalar volume de raspagem.

---

## ✅ Histórico de Versões

### v1.6 (Automação Autônoma) - 2026-01-31
- [x] **Autonomia**: `crawl_round.py` detecta e busca apenas a próxima rodada disponível.
- [x] **Estado de Banco**: `state.py` gerencia o cursor de execução (Last Round + 1).
- [x] **Override Manual**: Possibilidade de rodar `run_pipeline.sh <rodada>` para correções.
- [x] **Graceful Exit**: Pipeline encerra sem erro se a rodada futura não tiver jogos.

### v1.5 (Pipeline E2E & Robustez) - 2026-01-31
- [x] **Orquestração**: Script `run_pipeline.sh` unificado.
- [x] **Dados**: Normalização rigorosa (Datas, Números) e limpeza de strings.
- [x] **Anti-Block**: Execução Headless com headers furtivos e taxa de requisição humana.
- [x] **Lazy Loading**: "Smart Scroll" implementado para carregar escalações e stats ocultos.

### v1.0 - v1.4 (Fundação)
- [x] **Scraper Core**: Playwright engine para Ogol.com.br.
- [x] **Banco de Dados**: Schema PostgreSQL relacional (Partidas, Times, Jogadores, Eventos, Stats).
- [x] **Batch Processing**: Execução paralela/sequencial configurável.