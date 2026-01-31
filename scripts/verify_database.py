#!/usr/bin/env python3
"""
Verificar estrutura do banco de dados Render
"""
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

def verify_database():
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("🔍 Verificando estrutura do banco de dados...\n")
    
    # Check leagues
    cursor.execute("SELECT COUNT(*) FROM leagues;")
    num_leagues = cursor.fetchone()[0]
    print(f"✅ Leagues: {num_leagues} encontradas")
    
    cursor.execute("SELECT name, slug, country FROM leagues ORDER BY country, name;")
    leagues = cursor.fetchall()
    for name, slug, country in leagues:
        print(f"   - {name} ({slug}) - {country}")
    
    # Check seasons
    cursor.execute("SELECT COUNT(*) FROM seasons;")
    num_seasons = cursor.fetchone()[0]
    print(f"\n✅ Seasons: {num_seasons} encontradas")
    
    cursor.execute("""
        SELECT l.name, s.year, s.is_current 
        FROM seasons s 
        JOIN leagues l ON l.id = s.league_id 
        ORDER BY l.name, s.year DESC;
    """)
    seasons = cursor.fetchall()
    for league_name, year, is_current in seasons:
        current_marker = " (CURRENT)" if is_current else ""
        print(f"   - {league_name} {year}{current_marker}")
    
    # Check tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    tables = cursor.fetchall()
    print(f"\n✅ Tabelas criadas: {len(tables)}")
    for table in tables:
        print(f"   - {table[0]}")
    
    # Check views
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.views 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    views = cursor.fetchall()
    print(f"\n✅ Views criadas: {len(views)}")
    for view in views:
        print(f"   - {view[0]}")
    
    cursor.close()
    conn.close()
    
    print("\n🎉 Database Render está configurado e pronto!")

if __name__ == '__main__':
    verify_database()
