# Padrões de Extração de Dados

Este documento define os padrões para extração de dados de estatísticas de jogos do site ogol.com.br.

## Container Principal: `.zz-container`

**Todas as informações devem ser extraídas prioritariamente do elemento DOM `.zz-container`**, que é padronizado para páginas de estatísticas de jogos.

### Estrutura do Container

```html
<div class="zz-container">
    <div class="zz-tpl has-childs-3">
        <div class="zz-tpl-main">
            <div class="home">
                <!-- Tabela de estatísticas -->
                <table>...</table>
                
                <!-- Escalações -->
                <div id="game_report">
                    <div class="zz-tpl-col">  <!-- Home Team -->
                        <div class="subtitle">Nome do Time Casa</div>
                        <div class="player">...</div>
                    </div>
                    <div class="zz-tpl-col">  <!-- Away Team -->
                        <div class="subtitle">Nome do Time Visitante</div>
                        <div class="player">...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
```

## Prioridade de Extração

### 1. Estatísticas

| Prioridade | Seletor               | Descrição                                |
| ---------- | --------------------- | ---------------------------------------- |
| 1          | `.zz-container table` | Tabela inline com estatísticas resumidas |
| 2          | `.graph-bar`          | Barras de estatísticas (layout antigo)   |

**Estatísticas suportadas:**
- `posse` - Posse de Bola (%)
- `chutes` - Chutes Totais
- `chutes_gol` - Chutes no Gol
- `escanteios` - Escanteios
- `xg` - Gols Esperados (Expected Goals)
- `xgot` - Gols Esperados no Alvo
- `faltas` - Faltas Cometidas
- `impedimentos` - Impedimentos
- `defesas_goleiro` - Defesas do Goleiro
- `passes` - Passes Certos
- `passes_total` - Total de Passes
- `cortes` - Cortes
- `duelos_ganhos` - Divididas Ganhas

### 2. Escalações

| Prioridade | Seletor                      | Descrição                                |
| ---------- | ---------------------------- | ---------------------------------------- |
| 1          | `.zz-container #game_report` | Relatório de jogo dentro do container    |
| 2          | `.zz-module.game_matchup`    | Módulo de escalação (layout alternativo) |
| 3          | `.player` (linear)           | Fallback: todos os jogadores em ordem    |

**Estrutura de escalação:**
```json
{
    "escalacao_casa": {
        "titulares": [{"nome": "...", "numero": 1}],
        "reservas": [{"nome": "...", "numero": 12}],
        "tecnico": "Nome do Técnico",
        "time": "Nome do Time"
    },
    "escalacao_fora": { ... }
}
```

### 3. Informações do Jogo

| Campo     | Seletor                         | Fallback              |
| --------- | ------------------------------- | --------------------- |
| Times     | `.match-header-team.left/right` | `a[href*="/equipa/"]` |
| Placar    | `.match-header-vs a`            | -                     |
| Rodada    | Texto "Rodada X"                | -                     |
| Data/Hora | `.dateauthor`                   | -                     |
| Estádio   | `a[href*="/estadio/"]`          | -                     |
| Árbitro   | `a[href*="/arbitro/"]`          | -                     |
| Público   | Texto "Lotação: X"              | -                     |

## Validação de Mando (Home/Away)

O sistema valida automaticamente se os times estão na ordem correta (mandante/visitante) usando:

1. **URL do jogo** - Formato: `/jogo/YYYY-MM-DD-time-home-time-away/ID`
2. **Nomes nos containers** - `.subtitle` dentro de `#game_report`
3. **Eventos** - Se marcadores de gol estão na lista correta

Se detectada inversão, o sistema corrige automaticamente trocando:
- `home_team` ↔ `away_team`
- `home_score` ↔ `away_score`
- `stats_home` ↔ `stats_away`
- `escalacao_casa` ↔ `escalacao_fora`

## Formato de Saída JSON

```json
{
    "home_team": "Time Casa",
    "away_team": "Time Visitante",
    "home_score": 2,
    "away_score": 1,
    "rodada": 1,
    "data_hora": "DD-MM-YYYY HH:MM",
    "estadio": {"nome": "..."},
    "arbitro": {"nome": "..."},
    "publico": 50000,
    "stats_home": {
        "posse": 55,
        "chutes": 15,
        "xg": 1.85
    },
    "stats_away": {...},
    "eventos": [...],
    "escalacao_casa": {...},
    "escalacao_fora": {...}
}
```

## Logs e Debug

O scraper gera logs em `logs/scraper_TIMESTAMP.log` com:
- `INFO` - Início/fim do scraping
- `WARNING` - Correções automáticas (inversão de times, etc.)
- `ERROR` - Falhas de extração

---

*Última atualização: Janeiro 2026*
