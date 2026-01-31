#!/bin/bash

# ==============================================================================
# BR-Statistics Hub - API Runner
# ==============================================================================

# Cores para o terminal
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== 🌐 Iniciando BR-Statistics Hub API ===${NC}"

# Verificar ambiente virtual
if [ ! -d ".venv" ]; then
    echo "❌ Erro: Ambiente virtual .venv não encontrado. Execute a instalação primeiro."
    exit 1
fi

# Carregar variáveis de ambiente
if [ -f ".env" ]; then
    set -a  # Automatically export all variables
    source .env
    set +a
else
    echo "⚠️  Aviso: Arquivo .env não encontrado. Usando configurações padrão."
fi

# Ativar ambiente virtual
source .venv/bin/activate

# Configurações do Flask
export FLASK_APP=api_app.py
export FLASK_ENV=development  # Mude para production em produção

echo -e "${GREEN}🚀 Servidor rodando em http://127.0.0.1:5000${NC}"
echo -e "Pressione CTRL+C para encerrar."

# Executar servidor
python3 -m flask run --host=0.0.0.0 --port=5000
