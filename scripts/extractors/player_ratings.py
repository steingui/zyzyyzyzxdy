"""
player_ratings.py - Extrai ratings/notas dos jogadores do campo visual

Este extrator usa a visualização tática do campo (.pitch_eleven_horizontal)
para extrair dados enriquecidos de cada jogador, incluindo:
- ID do jogador (data-player-id)
- Nome
- Número da camisa
- Rating/Nota da partida
- Qualidade do rating (boa, média, ruim)
"""

import logging
import re
from typing import Any, Dict, List, Optional
from playwright.sync_api import Page

from ..utils.browser import safe_eval

logger = logging.getLogger(__name__)


# Mapeamento de cores para qualidade do rating
RATING_COLORS = {
    '#99CC66': 'bom',      # Verde
    '#99cc66': 'bom',      # Verde (lowercase)
    '#FF9900': 'medio',    # Laranja
    '#ff9900': 'medio',    # Laranja (lowercase)
    '#FF6666': 'ruim',     # Vermelho
    '#ff6666': 'ruim',     # Vermelho (lowercase)
    '#CC3333': 'ruim',     # Vermelho escuro
    '#cc3333': 'ruim',
}


def extract_player_ratings(page: Page) -> Dict[str, Any]:
    """
    Extrai ratings dos jogadores a partir da visualização tática do campo.
    
    Estrutura esperada:
    .zz-container > .match_block > .pitch > .pitch_eleven_horizontal
        > table.team (2x: home e away, nessa ordem visual)
            > .campo_onze_bloco_jogador
    
    Args:
        page: Página do Playwright com o jogo carregado
        
    Returns:
        Dicionário com:
        - ratings_home: Lista de jogadores do mandante com ratings
        - ratings_away: Lista de jogadores do visitante com ratings
        - match_id: ID da partida (extraído do data-match-id)
    """
    result = safe_eval(page, r'''
        (() => {
            const result = {
                home: [],
                away: [],
                matchId: null
            };
            
            // Encontrar o campo tático
            const pitch = document.querySelector('.pitch_eleven_horizontal');
            if (!pitch) {
                // Fallback: tentar outros seletores
                const altPitch = document.querySelector('.pitch');
                if (!altPitch) return result;
            }
            
            // Encontrar as tabelas dos times (2 tabelas: home e away)
            const teamTables = pitch 
                ? pitch.querySelectorAll('table.team')
                : document.querySelectorAll('.pitch table.team');
            
            if (teamTables.length < 2) {
                // Fallback: procurar todos os blocos de jogador
                const allBlocks = document.querySelectorAll('.campo_onze_bloco_jogador');
                if (allBlocks.length === 0) return result;
                
                // Tentar identificar times pela posição no DOM (primeiro metade = home)
                const players = [];
                allBlocks.forEach(block => {
                    const player = extractPlayerFromBlock(block);
                    if (player) players.push(player);
                });
                
                // Dividir 11 e 11
                if (players.length >= 22) {
                    result.home = players.slice(0, 11);
                    result.away = players.slice(11, 22);
                }
                
                return result;
            }
            
            // Função para extrair dados de um bloco de jogador
            function extractPlayerFromBlock(block) {
                if (!block) return null;
                
                const playerId = block.getAttribute('data-player-id');
                const matchId = block.getAttribute('data-match-id');
                
                // Capturar match ID
                if (matchId && !result.matchId) {
                    result.matchId = matchId;
                }
                
                // Nome do jogador
                const nameSpan = block.querySelector('.player_name .player span');
                const nome = nameSpan ? nameSpan.textContent.trim() : null;
                
                // Número da camisa (está no SVG)
                let numero = null;
                const svgText = block.querySelector('svg text');
                if (svgText) {
                    const numText = svgText.textContent.trim();
                    numero = parseInt(numText, 10);
                    if (isNaN(numero)) numero = null;
                }
                
                // Rating (nota) - está no span com background-color
                let rating = null;
                let ratingColor = null;
                
                // Procurar span com estilo de rating (tem font-weight: 700 e background-color)
                const ratingSpans = block.querySelectorAll('span[style*="background-color"]');
                for (const span of ratingSpans) {
                    const text = span.textContent.trim();
                    // Verificar se é um número válido (rating)
                    const parsed = parseFloat(text);
                    if (!isNaN(parsed) && parsed >= 0 && parsed <= 10) {
                        rating = parsed;
                        // Extrair cor do background
                        const style = span.getAttribute('style') || '';
                        const colorMatch = style.match(/background-color:\s*(#[0-9A-Fa-f]{6}|#[0-9A-Fa-f]{3})/);
                        if (colorMatch) {
                            ratingColor = colorMatch[1];
                        }
                        break;
                    }
                }
                
                // Retornar apenas se temos dados mínimos
                if (!nome && !playerId) return null;
                
                return {
                    player_id: playerId ? parseInt(playerId, 10) : null,
                    nome: nome,
                    numero: numero,
                    rating: rating,
                    rating_color: ratingColor
                };
            }
            
            // Processar time home (primeira tabela, lado esquerdo)
            const homeTable = teamTables[0];
            const homeBlocks = homeTable.querySelectorAll('.campo_onze_bloco_jogador');
            homeBlocks.forEach(block => {
                const player = extractPlayerFromBlock(block);
                if (player) result.home.push(player);
            });
            
            // Processar time away (segunda tabela, lado direito)
            const awayTable = teamTables[1];
            const awayBlocks = awayTable.querySelectorAll('.campo_onze_bloco_jogador');
            awayBlocks.forEach(block => {
                const player = extractPlayerFromBlock(block);
                if (player) result.away.push(player);
            });
            
            return result;
        })()
    ''', {'home': [], 'away': [], 'matchId': None})
    
    # Processar resultado e adicionar qualidade do rating
    ratings_home = _process_ratings(result.get('home', []))
    ratings_away = _process_ratings(result.get('away', []))
    
    output: Dict[str, Any] = {}
    
    if ratings_home:
        output['ratings_home'] = ratings_home
        
    if ratings_away:
        output['ratings_away'] = ratings_away
        
    match_id = result.get('matchId')
    if match_id:
        output['match_id_ogol'] = int(match_id) if match_id else None
    
    # Log para debug
    logger.info(f"Ratings extraídos: {len(ratings_home)} home, {len(ratings_away)} away")
    
    return output


def _process_ratings(players: List[Dict]) -> List[Dict[str, Any]]:
    """
    Processa lista de jogadores adicionando qualidade do rating.
    
    Args:
        players: Lista de dicionários com dados dos jogadores
        
    Returns:
        Lista processada com campo 'rating_qualidade' adicionado
    """
    processed = []
    
    for player in players:
        if not player:
            continue
            
        entry: Dict[str, Any] = {
            'player_id': player.get('player_id'),
            'nome': player.get('nome'),
            'numero': player.get('numero'),
            'rating': player.get('rating'),
        }
        
        # Determinar qualidade do rating pela cor
        rating_color = player.get('rating_color')
        if rating_color:
            entry['rating_qualidade'] = RATING_COLORS.get(rating_color.lower(), 'desconhecido')
        else:
            # Inferir pela nota se não temos cor
            rating = player.get('rating')
            if rating is not None:
                if rating >= 7.0:
                    entry['rating_qualidade'] = 'bom'
                elif rating >= 6.0:
                    entry['rating_qualidade'] = 'medio'
                else:
                    entry['rating_qualidade'] = 'ruim'
        
        processed.append(entry)
    
    return processed


def extract_formation_from_ratings(ratings: List[Dict]) -> Optional[str]:
    """
    Tenta inferir a formação tática a partir dos ratings.
    
    Nota: Isso é uma heurística baseada no número de jogadores.
    A formação real precisaria de análise posicional mais sofisticada.
    
    Args:
        ratings: Lista de jogadores com ratings
        
    Returns:
        String com formação (ex: "4-3-3") ou None se não identificável
    """
    # Por agora, retornar None - inferir formação é complexo
    # e requer análise do grid de posições, que varia muito
    # Implementar futuramente se necessário
    return None
