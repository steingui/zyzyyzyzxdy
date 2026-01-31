"""
normalization.py - Utilitários para limpeza e padronização de dados
"""
import re
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

MONTH_MAP = {
    'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04', 'mai': '05', 'jun': '06',
    'jul': '07', 'ago': '08', 'set': '09', 'out': '10', 'nov': '11', 'dez': '12',
    'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04', 'maio': '05', 'junho': '06',
    'julho': '07', 'agosto': '08', 'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
}

def parse_date(date_str: str) -> Optional[str]:
    """
    Converte datas variadas para ISO 8601 (YYYY-MM-DD HH:MM:SS) ou (YYYY-MM-DD).
    Suporta:
    - "13 Abr 2024"
    - "13/04/2024 16:00"
    - "2024-04-13" (já ISO)
    """
    if not date_str:
        return None
        
    s = date_str.strip().lower()
    
    # Caso 1: DD/MM/YYYY HH:MM
    match_br_full = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}:\d{2}))?', s)
    if match_br_full:
        day, month, year, time = match_br_full.groups()
        if time:
            return f"{year}-{month.zfill(2)}-{day.zfill(2)} {time}:00"
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    # Caso 2: DD Mes YYYY (Ex: 14 abr 2024 16:00)
    # Regex para pegar dia, mes (texto), ano e opcional hora
    match_text = re.search(r'(\d{1,2})\s+([a-zç]+)\.?\s+(\d{4})(?:\s+(\d{1,2}:\d{2}))?', s)
    if match_text:
        day, month_name, year, time = match_text.groups()
        # Tentar mapear o mês (3 primeiras letras resolvem a maioria)
        month_key = month_name[:3]
        if month_key in MONTH_MAP:
            month = MONTH_MAP[month_key]
            if time:
                return f"{year}-{month}-{day.zfill(2)} {time}:00"
            return f"{year}-{month}-{day.zfill(2)}"
    
    # Caso 3: Formato com traços (tentativa de ISO direta)
    if re.match(r'\d{4}-\d{2}-\d{2}', s):
        return s
        
    logger.warning(f"Formato de data desconhecido: {date_str}")
    return None

def clean_number(value: Any) -> Any:
    """
    Remove caracteres não numéricos de strings e converte para int/float.
    Ex: "52%" -> 52
        "12 km" -> 12
        "1.200" -> 1200
    """
    if isinstance(value, (int, float)):
        return value
        
    if not value or not isinstance(value, str):
        return None
        
    # Remove % e espaços
    s = value.replace('%', '').replace('km', '').strip()
    
    # Remove pontos de milhar "1.200" -> "1200" (Cuidado com decimais BR, mas stats costumam ser inteiros ou float com ponto/virgula)
    # Assumindo padrão BR onde . é milhar e , é decimal se houver duvida?
    # Na maioria das stats esportivas aqui:
    # "10" -> 10
    # "52%" -> 52
    # "4.5" (nota) -> 4.5
    
    try:
        if ',' in s and '.' in s: # Ex: 1.200,50 -> dificil ocorrer em stats simples
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s:
            s = s.replace(',', '.')
            
        # Converter
        if '.' in s:
            return float(s)
        return int(s)
    except ValueError:
        return value # Retorna original se falhar

def clean_text(text: str) -> Optional[str]:
    """Remove prefixos comuns e espaços extras."""
    if not text:
        return None
        
    s = text.strip()
    # Remove prefixos (insensitive)
    prefixes = ['ÁRBITRO:', 'ESTÁDIO:', 'ARBITRO:', 'ESTADIO:']
    
    upper_s = s.upper()
    for p in prefixes:
        if upper_s.startswith(p):
            s = s[len(p):].strip()
            break
            
    return s

def normalize_match_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aplica normalização em todo o objeto de partida.
    Modifica o dicionário in-place e o retorna.
    """
    # 1. Metadados e Info
    if 'data_hora' in data:
        data['data_hora'] = parse_date(data['data_hora'])
        
    if 'arbitro' in data and isinstance(data['arbitro'], dict):
        if 'nome' in data['arbitro']:
            data['arbitro']['nome'] = clean_text(data['arbitro']['nome'])
            
    if 'estadio' in data and isinstance(data['estadio'], dict):
        if 'nome' in data['estadio']:
            data['estadio']['nome'] = clean_text(data['estadio']['nome'])
            
    if 'publico' in data:
        data['publico'] = clean_number(data['publico'])
        
    # 2. Estatísticas (garantir numéricos)
    for team_stats in ['stats_home', 'stats_away']:
        if team_stats in data:
            for k, v in data[team_stats].items():
                data[team_stats][k] = clean_number(v)
                
    # 3. Escalações (stats internas)
    for side in ['escalacao_casa', 'escalacao_fora']:
        if side in data:
            # Iterar titulares e reservas
            for group in ['titulares', 'reservas']:
                if group in data[side]:
                    for player in data[side][group]:
                        # Converter ratings
                        if 'rating' in player:
                            player['rating'] = clean_number(player['rating'])
                        if 'rating_qualidade' in player:
                            player['rating_qualidade'] = clean_number(player['rating_qualidade'])
                            
    return data
