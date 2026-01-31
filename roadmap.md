🚀 Roadmap de Implementação Detalhado
Passo 1: Setup de Infra (Segurança)

    Criação do Banco: No diretório data/, rode o SQL de criação das tabelas.

    Ambiente: Instale o OpenClaw via Docker ou binário local.

    Permissões: Garanta que chmod +x scripts/*.sh seja aplicado.

Passo 2: O Script "Wrapper" (A Ponte)

Crie o arquivo scripts/run_rodada.sh para facilitar sua vida. Ele será o seu comando principal.
Bash

#!/bin/bash
# Uso: ./run_rodada.sh 12 (onde 12 é a rodada atual)

RODADA=$1
LINKS_FILE="data/links_rodada_${RODADA}.txt"

echo "⚽ Iniciando extração da Rodada ${RODADA}..."

while read -r url; do
    echo "🔍 Processando jogo: $url"
    # O OpenClaw extrai e o Python salva
    openclaw run --prompt .agents/extraction_prompt.md --url "$url" | python3 scripts/db_importer.py
    sleep 3 # Regra S03: Delay para segurança
done < "$LINKS_FILE"

echo "✅ Rodada ${RODADA} concluída."

Passo 3: Execução de Rotina

    Após o término da rodada, crie um arquivo data/links_rodada_X.txt com as 10 URLs dos jogos (isso pode ser feito manualmente ou com um script simples de "lista de jogos").

    Execute: ./scripts/run_rodada.sh X.

    O banco será populado automaticamente.