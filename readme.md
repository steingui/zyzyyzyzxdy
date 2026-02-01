# BR-Statistics Hub v2.1 (Refactor v1) ⚽📊

O **BR-Statistics Hub** é uma plataforma avançada de extração, processamento e análise de dados estatísticos do futebol brasileiro. O projeto coleta dados detalhados (scouts, xG, mapas táticos) de fontes públicas e os consolida em uma infraestrutura escalável e flexível.

## 🚀 Novidades da v2.1 (Refactor v1)
- **Schema em Português**: Tabelas renomeadas para `ligas`, `temporadas`, `times`, `partidas`, `estatisticas_partidas`.
- **Performance**: Índices compostos para dashboards e histórico de times.
- **Clean Slate**: Banco reiniciado para garantir consistência total.

## 🏗️ Arquitetura
A plataforma segue o padrão de **Pipeline ETL (Extract, Load, Transform)**:
1. **Extração**: Playwright automatiza o browser para capturar scouts detalhados.
2. **Transformação**: Normalização de nomes e validação de dados.
3. **Carga**: Ingestão no PostgreSQL via SQLAlchemy Async.

## 📂 Estrutura do Projeto
```text
├── app/                 # Aplicação Flask (Blueprints, Models, Schemas)
├── database/            # Migrations e esquemas SQL
├── scripts/             # Core engine (Scraper, Importer, Orchestrator)
├── logs/                # Histórico de execuções
└── migrations/          # Alembic Migrations
```

## 🛠️ Configuração Inicial
1. **Ambiente**:
   ```bash
   python3 -m venv .venv
   source .venv/activate
   pip install -r requirements.txt
   ```
2. **Banco de Dados**:
   Certifique-se que o PostgreSQL está rodando e configure o `.env`.
   ```bash
   # Resetar e Migrar (Cuidado: Apaga dados!)
   flask db upgrade
   
   # Popular dados iniciais (Ligas/Temporadas)
   python3 scripts/seed_data.py  # (Criar se necessário ou usar API)
   ```

## 📊 Execução
1. **Rodar a API (REST)**:
   ```bash
   ./run_api.sh
   ```
2. **Ingestão de Dados (Exemplo)**:
   ```bash
   # Via CURL/Postman
   curl -X POST http://localhost:5000/api/scrape -d '{"league": "brasileirao", "year": 2026, "round": 1}'
   
   # Via Script Manual
   python3 scripts/run_batch.py --league brasileirao --year 2026 1
   ```
3. **Visualização Rápida no Terminal**:
   ```bash
   python3 scripts/view_rds.py
   ```

---
*Este projeto foi desenvolvido para fins de análise estatística esportiva.*