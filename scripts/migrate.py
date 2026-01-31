#!/usr/bin/env python3
"""
migrate.py - Aplica migrations no banco de dados
"""
import os
import sys
import logging
import psycopg2
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def apply_migration(conn, filename):
    with open(filename, 'r') as f:
        sql = f.read()
    
    with conn.cursor() as cur:
        try:
            cur.execute(sql)
            conn.commit()
            logger.info(f"Migration aplicada: {filename}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erro ao aplicar {filename}: {e}")
            # Ignorar erro de 'already exists' se for rerun
            if 'already exists' in str(e) or 'duplicate column' in str(e):
                logger.warning("Migration parece já ter sido aplicada parcial ou totalmente.")
            else:
                raise e

def main():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL não definida")
        sys.exit(1)
        
    try:
        conn = psycopg2.connect(db_url)
    except Exception as e:
        logger.error(f"Erro conexão: {e}")
        sys.exit(1)

    migrations_dir = 'database/migrations'
    files = sorted([f for f in os.listdir(migrations_dir) if f.endswith('.sql')])
    
    for f in files:
        apply_migration(conn, os.path.join(migrations_dir, f))
        
    conn.close()

if __name__ == "__main__":
    main()
