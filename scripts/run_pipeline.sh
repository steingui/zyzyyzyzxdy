#!/bin/bash

# Validar se estamos na raiz
cd "$(dirname "$0")/.."

# run_pipeline.sh
# Script para orquestrar a execução do scraper e carga no banco de dados.
# Garante ambiente virtual ativo e verifica sucesso da carga.

# Configuração
VENV_DIR=".venv"
SCRIPT_BATCH="scripts/run_batch.py"
DB_CHECK_SCRIPT="scripts/check_db_count.py"

# Cores para logs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== 🚀 Iniciando Pipeline de Extração e Carga (v1.4) ===${NC}"
date

# 1. Ativação do Virtual Environment
if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}source $VENV_DIR/bin/activate${NC}"
    source "$VENV_DIR/bin/activate"
else
    echo -e "${RED}❌ Erro: Ambiente virtual não encontrado em $VENV_DIR${NC}"
    echo "Certifique-se de que o venv foi criado corretamente."
    exit 1
fi

# 2. Execução do Batch Scraper
# O run_batch.py já está configurado para:
# - Rodar sequencialmente (Anti-Block)
# - Abrir browser com headers furtivos
# - Persistir no banco automaticamente via db_importer
echo -e "${GREEN}>>> 🕸️  Executando run_batch.py (Buscando dados...)${NC}"

# Capturando exit code para tratamento de erro
# "$@" repassa quaisquer argumentos (ex: 1 para rodada 1)
python3 "$SCRIPT_BATCH" "$@"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo -e "${RED}❌ Erro durante a execução do batch. Código de saída: $EXIT_CODE${NC}"
    # Não sai imediatamente, tenta verificar se algo foi salvo mesmo assim
fi

# 3. Verificação do Banco de Dados
echo -e "${GREEN}>>> 📊 Verificando contagem de registros no Banco de Dados...${NC}"

if [ -f "$DB_CHECK_SCRIPT" ]; then
    python3 "$DB_CHECK_SCRIPT"
else
    # Fallback se o script python de check não existir
    echo "Script de verificação python não encontrado, usando docker exec..."
    docker exec -i brasileirao-db psql -U brasileirao -d brasileirao_2026 -c "SELECT count(*) as total_partidas FROM partidas;"
fi

echo -e "${GREEN}===🏁 Pipeline Concluído ===${NC}"
echo "Logs disponíveis em: logs/batch_run.log"
date
