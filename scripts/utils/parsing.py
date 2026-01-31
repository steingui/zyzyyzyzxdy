"""
parsing.py - Utilitários para parsing e normalização de dados
"""

import re
import unicodedata
from typing import Optional, Union


def parse_value(text: Optional[str], field_name: str = '') -> Optional[Union[int, float]]:
    """
    Converte texto para valor numérico de forma flexível.
    
    Args:
        text: Texto a ser convertido
        field_name: Nome do campo (para contexto em logs)
        
    Returns:
        Valor numérico (int ou float) ou None se não conseguir converter
    """
    if text is None:
        return None
        
    if isinstance(text, (int, float)):
        return text
        
    text = str(text).strip()
    
    # Remover % 
    has_percent = '%' in text
    text_clean = text.replace('%', '').strip()
    
    # Se tem vírgula como decimal (padrão BR)
    if ',' in text_clean and '.' not in text_clean:
        text_clean = text_clean.replace(',', '.')
    
    try:
        # Se é claramente decimal (xG, por exemplo)
        if '.' in text_clean:
            return float(text_clean)
        # Inteiro
        return int(text_clean)
    except ValueError:
        # Fallback: extrair primeiro número
        match = re.search(r'(\d+)', text)
        if match:
            return int(match.group(1))
    
    return None


def normalize_name(name: str) -> str:
    """
    Normaliza nome para comparação (remove acentos, minúsculas).
    
    Args:
        name: Nome a ser normalizado
        
    Returns:
        Nome normalizado sem acentos e em minúsculas
    """
    nfkd_form = unicodedata.normalize('NFKD', name)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()


def extract_numbers_from_text(text: str) -> list[str]:
    """
    Extrai todos os números (incluindo decimais e percentuais) de um texto.
    
    Args:
        text: Texto contendo números
        
    Returns:
        Lista de strings representando números encontrados
    """
    return re.findall(r'[\d.,]+%?', text)


def clean_player_name(name: str) -> str:
    """
    Limpa nome de jogador removendo sufixos como (C) de capitão.
    
    Args:
        name: Nome do jogador
        
    Returns:
        Nome limpo
    """
    # Remove (C) de capitão mas mantém para exibição
    return name.strip()


def slugify(text: str) -> str:
    """
    Converte texto para slug (URL-friendly).
    
    Args:
        text: Texto a ser convertido
        
    Returns:
        Slug do texto
    """
    normalized = normalize_name(text)
    return re.sub(r'\s+', '-', normalized)
