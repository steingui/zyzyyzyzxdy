**🔥 Prioridade Alta (Imediato)**
- [ ] Integrar `db_importer.py` ao fluxo do `run_batch.py` {cm:2026-01-31}
- [ ] Testar pipeline completo: Scraper → JSON → PostgreSQL {cm:2026-01-31}
- [ ] Validar integridade dos dados no banco (Schema vs Dados Reais) {cm:2026-01-31}
- [ ] Refinar limpeza de dados (ex: remover prefixo "ÁRBITRO" de `arbitro.nome`) {cm:2026-01-31}

**🔄 Prioridade Média (Refinamento)**
- [ ] Otimizar lazy loading (scroll ainda mais robusto para escalações) {cm:2026-01-31}
- [ ] Criar script CLI unificado (`manage.py` ou `main.py`) {cm:2026-01-31}
- [ ] Dashboard simples para visualizar dados ingeridos (SQL ou Streamlit) {cm:2026-01-31}

**✅ Concluído (v1.3)**
- [x] Descoberta automática de jogos (`crawl_round.py`) {cm:2026-01-31}
- [x] Coletar todos os links de jogos de uma rodada {cm:2026-01-31}
- [x] Execução paralela e robusta (`run_batch.py`) {cm:2026-01-31}
- [x] Sistema de Retry com backoff exponencial {cm:2026-01-31}
- [x] Extração modular (Lineups, Events, Stats) {cm:2026-01-31}
- [x] Log estruturado e tratamento de erros {cm:2026-01-31}
- [x] Opção de debug visual (`--no-headless`) {cm:2026-01-31}

**📈 Futuro**
- [ ] Dashboard de visualização
- [ ] Frontend para explorar dados
- [ ] Gráficos de xG por time/rodada
- [ ] API REST para expor dados
- [ ] Análises avançadas (xG acumulado, comparativos)