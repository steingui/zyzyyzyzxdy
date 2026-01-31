#!/bin/bash
# ============================================
# run_rodada.sh - Wrapper para execução do Scraper
# ============================================
# Uso: ./scripts/run_rodada.sh <NUMERO_RODADA>
# Exemplo: ./scripts/run_rodada.sh 1
# ============================================

set -e  # Parar em caso de erro

# Configurações
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
RODADA=$1
LINKS_FILE="${PROJECT_ROOT}/data/links_rodada_${RODADA}.txt"
LOG_FILE="${PROJECT_ROOT}/logs/rodada_${RODADA}.log"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funções de log
log_info() { echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1" | tee -a "$LOG_FILE"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"; }

# Validação de argumentos
if [ -z "$RODADA" ]; then
    echo "Uso: $0 <NUMERO_RODADA>"
    echo "Exemplo: $0 1"
    exit 1
fi

if [ "$RODADA" -lt 1 ] || [ "$RODADA" -gt 38 ]; then
    log_error "Rodada deve estar entre 1 e 38"
    exit 1
fi

if [ ! -f "$LINKS_FILE" ]; then
    log_error "Arquivo de links não encontrado: $LINKS_FILE"
    echo "Crie o arquivo com as 10 URLs da rodada, uma por linha."
    exit 1
fi

# Verificar variáveis de ambiente (Regra S01)
if [ -z "$DATABASE_URL" ]; then
    log_error "DATABASE_URL não definida. Configure a variável de ambiente."
    echo "Exemplo: export DATABASE_URL=postgresql://user:pass@localhost:5432/brasileirao_2026"
    exit 1
fi

# Criar diretório de logs se não existir
mkdir -p "${PROJECT_ROOT}/logs"

# Iniciar processamento
echo "============================================" | tee -a "$LOG_FILE"
log_info "⚽ Iniciando extração da Rodada ${RODADA}..."
log_info "Data/Hora: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================" | tee -a "$LOG_FILE"

# Contador de sucesso/falha
TOTAL=0
SUCCESS=0
FAILED=0

# Processar cada URL
while IFS= read -r url || [ -n "$url" ]; do
    # Ignorar linhas vazias e comentários
    [[ -z "$url" || "$url" =~ ^# ]] && continue
    
    TOTAL=$((TOTAL + 1))
    log_info "🔍 Processando jogo ${TOTAL}: $url"
    
    # Executar Scraper Python e pipe para db_importer
    if python3 "${PROJECT_ROOT}/scripts/scraper.py" "$url" 2>> "$LOG_FILE" | \
       python3 "${PROJECT_ROOT}/scripts/db_importer.py" 2>> "$LOG_FILE"; then
        log_success "Jogo ${TOTAL} processado com sucesso"
        SUCCESS=$((SUCCESS + 1))
    else
        log_warning "Falha ao processar jogo ${TOTAL} (pode já existir no banco)"
        FAILED=$((FAILED + 1))
    fi
    
    # Delay entre requisições para não sobrecarregar o servidor
    log_info "Aguardando 3 segundos antes do próximo..."
    sleep 3
    
done < "$LINKS_FILE"

# Resumo final
echo "============================================" | tee -a "$LOG_FILE"
log_info "📊 Resumo da Rodada ${RODADA}:"
log_info "   Total de jogos: ${TOTAL}"
log_success "   Sucesso: ${SUCCESS}"
[ "$FAILED" -gt 0 ] && log_warning "   Falhas/Duplicados: ${FAILED}"
log_info "   Log salvo em: ${LOG_FILE}"
echo "============================================" | tee -a "$LOG_FILE"

# Código de saída
if [ "$SUCCESS" -eq "$TOTAL" ]; then
    log_success "✅ Rodada ${RODADA} concluída com sucesso!"
    exit 0
elif [ "$SUCCESS" -gt 0 ]; then
    log_warning "⚠️ Rodada ${RODADA} concluída parcialmente"
    exit 0
else
    log_error "❌ Nenhum jogo foi processado"
    exit 1
fi
