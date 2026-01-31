import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import tabulate

# Carregar variáveis de ambiente
load_dotenv()

def view_comprehensive():
    url = os.getenv('DATABASE_URL')
    if not url:
        print("❌ DATABASE_URL não encontrada no .env")
        return

    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Resumo das Partidas Detalhadas
        query = """
            SELECT 
                rodada as "RD", 
                time_casa as "Casa", 
                gols_casa || ' x ' || gols_fora as "Placar", 
                time_fora as "Fora",
                xg_casa || ' - ' || xg_fora as "xG",
                posse_casa || '%' as "Posse",
                estadio as "Estádio",
                arbitro as "Árbitro"
            FROM v_partidas_detalhadas
            ORDER BY rodada DESC, data_hora DESC
            LIMIT 20;
        """
        
        cur.execute(query)
        matches = cur.fetchall()
        
        print("\n" + "="*80)
        print("🏟️  RESUMO DETALHADO DAS PARTIDAS (AWS RDS)")
        print("="*80)
        
        if not matches:
            print("📭 Nenhuma partida encontrada.")
        else:
            print(tabulate.tabulate(matches, headers="keys", tablefmt="fancy_grid"))

        # 2. Ranking de Performance (xG)
        print("\n" + "="*80)
        print("📈 TOP PERFORMANCE (Média de xG Pro)")
        print("="*80)
        cur.execute("SELECT * FROM v_ranking_xg LIMIT 5;")
        ranking = cur.fetchall()
        print(tabulate.tabulate(ranking, headers="keys", tablefmt="fancy_grid"))
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Erro ao consultar banco: {e}")

if __name__ == "__main__":
    view_comprehensive()
