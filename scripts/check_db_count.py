
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

try:
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM partidas;")
    count = cur.fetchone()[0]
    print(f"TOTAL_PARTIDAS: {count}")
    conn.close()
except Exception as e:
    print(f"ERRO: {e}")
