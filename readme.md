# BR-Statistics Hub v2.0 ⚽📊

O **BR-Statistics Hub** é uma plataforma avançada de extração, processamento e análise de dados estatísticos do futebol brasileiro. O projeto coleta dados detalhados (scouts, xG, mapas táticos) de fontes públicas e os consolida em uma infraestrutura escalável e flexível.

## 🚀 Novidades da v2.0
- **Infraestrutura em Nuvem**: Migração completa de SQLite local para **AWS RDS (PostgreSQL 17)**.
- **Arquitetura Híbrida (SQL + NoSQL)**: Uso de colunas **JSONB** para capturar dados semi-estruturados, garantindo que mudanças na fonte de dados não quebrem o pipeline.
- **Processamento Paralelo**: Orquestração multi-thread para extração simultânea de múltiplas partidas.
- **Idempotência Atômica**: Implementação de `ON CONFLICT` para garantir integridade de dados mesmo em execuções paralelas ou repetidas.

## 🏗️ Arquitetura
A plataforma segue o padrão de **Pipeline ETL (Extract, Load, Transform)**:
1. **Extração**: Playwright automatiza o browser para capturar scouts detalhados, incluindo modais de jogadores e eventos em tempo real.
2. **Transformação**: Normalização de nomes de times, estádios e árbitros.
3. **Carga**: Ingestão no PostgreSQL (AWS) com suporte a metadados flexíveis.

## 📂 Estrutura do Projeto
```text
├── database/            # Migrations e esquemas SQL
├── scripts/             # Core engine (Scraper, Importer, Orchestrator)
├── certs/               # Certificados SSL para conexão RDS (Ignorado no Git)
├── .venv/               # Ambiente virtual Python
└── logs/                # Histórico de execuções
```

## 🛠️ Configuração
1. **Ambiente**:
   ```bash
   python3 -m venv .venv
   source .venv/activate
   pip install -r requirements.txt
   ```
2. **Variáveis de Ambiente**:
   Crie um arquivo `.env` baseado no `.env.example`:
   ```env
   DATABASE_URL=postgres://user:pass@host:port/db?sslmode=verify-full&sslrootcert=certs/global-bundle.pem
   ```

## 📊 Execução e Visualização
1. **Rodar a API (REST)**:
   ```bash
   ./run_api.sh
   ```
2. **Visualização Rápida no Terminal**:
   ```bash
   python3 scripts/view_rds.py
   ```

---
*Este projeto foi desenvolvido para fins de análise estatística esportiva.*