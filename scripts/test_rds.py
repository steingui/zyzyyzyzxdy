import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def test_connection():
    url = os.getenv('DATABASE_URL')
    print(f"Testando conexão com: {url.split('@')[1] if '@' in url else 'URL INVÁLIDA'}")
    
    conn = None
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute('SELECT version();')
        print(f"✅ Conectado com sucesso! Versão: {cur.fetchone()[0]}")
        
        # Executar migrações
        migrations = [
            'database/migrations/001_create_database.sql',
            'database/migrations/002_add_detailed_player_stats.sql'
        ]
        
        for migration in migrations:
            path = os.path.join(os.getcwd(), migration)
            if os.path.exists(path):
                print(f"🚀 Executando {migration}...")
                with open(path, 'r') as f:
                    cur.execute(f.read())
                conn.commit()
                print(f"✅ {migration} aplicado com sucesso!")
            else:
                print(f"⚠️ Erro: {path} não encontrado.")
            
        cur.close()
    except Exception as e:
        print(f"❌ Erro na conexão: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    test_connection()
