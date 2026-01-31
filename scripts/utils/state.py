"""
state.py - Gerenciamento de estado do pipeline via Banco de Dados
"""
import logging
import os
import psycopg2
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def get_connection():
    """Cria conexão com o banco de dados."""
    url = os.getenv('DATABASE_URL')
    if not url:
        raise ValueError("DATABASE_URL não definida")
    return psycopg2.connect(url)

def get_last_processed_round() -> int:
    """
    Retorna a maior rodada presente na tabela de partidas.
    Se a tabela estiver vazia, retorna 0.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT MAX(rodada) as last_round FROM partidas")
        result = cursor.fetchone()
        
        if result and result[0] is not None:
            return int(result[0])
        return 0
        
    except Exception as e:
        logger.error(f"Erro ao buscar última rodada: {e}")
        return 0
    finally:
        if conn:
            conn.close()

def check_match_exists(url: str) -> bool:
    """
    Verifica se uma partida com a URL fonte já existe no banco.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Normaliza a URL removendo query params se necessário, mas aqui assume match exato
        cursor.execute("SELECT id FROM partidas WHERE url_fonte = %s", (url,))
        result = cursor.fetchone()
        
        return result is not None
        
    except Exception as e:
        logger.error(f"Erro ao verificar existência da partida {url}: {e}")
        return False
    finally:
        if conn:
            conn.close()
