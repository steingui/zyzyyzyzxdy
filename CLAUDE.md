# Project Rules

## Regras de Segurança e Execução
- **S01:** Credenciais de API devem ser carregadas via ENV VAR (nunca hardcoded).
- **S02:** O script de banco deve usar `COMMIT` apenas após validação completa.
- **S03:** Idempotência obrigatória: não inserir dados duplicados.

## Estratégia de Resolução de Problemas
- Always think with divide and conquer.
- Break complex problems into smaller, testable pieces.

## Estrutura do Projeto
```
scripts/
├── scraper.py        # Scraper principal
├── config.py         # Configurações centralizadas
├── main.py           # Orquestrador do pipeline
├── db_importer.py    # Importador para PostgreSQL
├── extractors/       # Módulos de extração
└── utils/            # Utilitários

database/
└── migrations/       # Migrations SQL

tests/                # Testes
docs/                 # Documentação
```

## Padrões de Código
- Type hints em todas as funções públicas
- Docstrings em todas as funções
- Logs via `logging` module (não print)
- Configurações em `scripts/config.py`
