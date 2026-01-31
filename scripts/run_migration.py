#!/usr/bin/env python3
"""
Script para executar migrações SQL no banco de dados
"""
import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# Carregar .env
load_dotenv()

def run_migration(migration_file: str):
    """Executa um arquivo de migração SQL"""
    # Carregar DATABASE_URL do ambiente
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not set in environment")
    
    # Ler arquivo SQL
    migration_path = Path(__file__).parent.parent / 'database' / 'migrations' / migration_file
    
    if not migration_path.exists():
        raise FileNotFoundError(f"Migration file not found: {migration_path}")
    
    with open(migration_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Conectar e executar
    print(f"🔄 Running migration: {migration_file}")
    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql_content)
        conn.commit()
        print(f"✅ Migration {migration_file} completed successfully")
        cursor.close()
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration {migration_file} failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python run_migration.py <migration_file>")
        print("Example: python run_migration.py 005_multi_league_support.sql")
        sys.exit(1)
    
    migration_file = sys.argv[1]
    run_migration(migration_file)
