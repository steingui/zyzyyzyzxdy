# Contexto do Projeto

## Visão Geral
Sistema de extração e armazenamento de estatísticas do **Brasileirão 2026**.

## Fluxo de Dados
```
URLs (ogol.com.br) → Scraper (Playwright) → JSON → db_importer.py → PostgreSQL
```

## Arquitetura
- **Entrada:** URLs de partidas do [ogol.com.br](https://www.ogol.com.br/competicao/brasileirao)
- **Scraper:** Python + Playwright para extração estruturada
- **Saída:** PostgreSQL com schema normalizado (8 tabelas)
- **Execução:** Local, pós-rodada (manual ou via cron)

## Métricas do Campeonato
| Métrica               | Valor   |
| --------------------- | ------- |
| Rodadas               | 38      |
| Times                 | 20      |
| Jogos/Rodada          | 10      |
| **Total de Partidas** | **380** |

## Stack Tecnológico
- **Banco:** PostgreSQL 15+
- **Scraper:** Python 3.11+ com Playwright
- **Libs:** playwright, psycopg2, python-dotenv