#!/bin/bash

# Validar se estamos na raiz (se rodar de dentro de scripts/)
cd "$(dirname "$0")/.."

# ==============================================================================
# BR-Statistics Hub API - Startup Script
# ==============================================================================

set -e  # Exit on error

echo "=== 🌐 Iniciando BR-Statistics Hub API ==="

# Load environment variables safely (handles spaces in paths)
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo "⚠️  AVISO: Arquivo .env não encontrado!"
    echo "📝 Copie .env.example para .env e configure suas credenciais."
    exit 1
fi

# Security: Validate required environment variables
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERRO: DATABASE_URL não configurado no .env"
    exit 1
fi

if [ -z "$SECRET_KEY" ]; then
    echo "❌ ERRO: SECRET_KEY não configurado no .env"
    echo "💡 Gere uma chave com: python3 -c \"import secrets; print(secrets.token_hex(32))\""
    exit 1
fi

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "❌ Ambiente virtual não encontrado!"
    echo "💡 Crie com: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Start Flask API
PORT=${PORT:-5000}
echo "🚀 Servidor rodando em http://127.0.0.1:$PORT"
echo "📚 Documentação EN: http://127.0.0.1:$PORT/api/docs/en"
echo "📚 Documentação PT: http://127.0.0.1:$PORT/api/docs/pt"
echo "Pressione CTRL+C para encerrar."
echo ""

# Security: Run with production settings
export FLASK_APP=api_app.py
export FLASK_ENV=production
# Default to REDIS_URL if available, otherwise localhost
export CACHE_REDIS_URL=${CACHE_REDIS_URL:-${REDIS_URL:-redis://localhost:6379/0}}


# Kill any existing process on the target port
if fuser "$PORT/tcp" >/dev/null 2>&1; then
    echo "⚠️  Porta $PORT em uso — matando processo anterior..."
    fuser -k "$PORT/tcp" >/dev/null 2>&1
    sleep 1
    echo "✅ Porta $PORT liberada"
fi

flask run --host=0.0.0.0 --port=$PORT
