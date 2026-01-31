**🔜 Prioridade Alta**
- Melhorar extração de escalações e cartões {cm:2026-01-31}
- O site usa lazy loading intensivo {cm:2026-01-31}
- Testar com headless=False para debugar visualmente {cm:2026-01-31}
- Implementar waits mais específicos {cm:2026-01-31}
- Integrar db_importer.py {cm:2026-01-31}
- Testar pipeline completo: scraper → JSON → PostgreSQL {cm:2026-01-31}
- Verificar mapeamento de campos com o schema {cm:2026-01-31}
- Limpar nome do árbitro {cm:2026-01-31}
- Remover prefixo "ÁRBITRO" do campo arbitro.nome {cm:2026-01-31}

**🔄 Prioridade Média**
- Descoberta automática de jogos {cm:2026-01-31}
- Implementar scraping da página de rodada {cm:2026-01-31}
- Coletar todos os links de jogos automaticamente {cm:2026-01-31}
- Automatizar execução por rodada {cm:2026-01-31}
- Script run_rodada.sh funcional {cm:2026-01-31}
- Processar todos os jogos de uma rodada {cm:2026-01-31}
- Tratamento de erros robusto {cm:2026-01-31}
- Retry em caso de falha {cm:2026-01-31}
- Log estruturado {cm:2026-01-31}

**📈 Futuro**
- Dashboard de visualização {cm:2026-01-31}
- Frontend para explorar dados {cm:2026-01-31}
- Gráficos de xG por time/rodada {cm:2026-01-31}
- API REST {cm:2026-01-31}
- Expor dados via endpoints {cm:2026-01-31}
- Consultas por time, rodada, jogador {cm:2026-01-31}
- Análises avançadas {cm:2026-01-31}
- xG acumulado por temporada {cm:2026-01-31}
- Comparativos de performance {cm:2026-01-31}


***

- Implementar waits mais específicos
- Processar todos os jogos de uma rodada -> Gerar result json de todos os jogos
- Retry em caso de falha
- Log estruturado