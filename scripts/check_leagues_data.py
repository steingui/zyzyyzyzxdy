import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import create_app, db
from app.models import Liga, Temporada, Time
from sqlalchemy import func

app = create_app()

def check_data():
    with app.app_context():
        print("=== Checking Leagues ===")
        leagues = Liga.query.all()
        for l in leagues:
            print(f"League: {l.nome} (slug: {l.slug}, id: {l.id})")
            print(f"  Count Seasons: {len(l.temporadas)}")
            current = next((s for s in l.temporadas if s.is_current), None)
            if current:
                print(f"  Current Season: {current.ano} (id: {current.id})")
            else:
                print("  Current Season: NONE")
            
            # Check teams count
            team_count = Time.query.filter_by(liga_id=l.id).count()
            print(f"  Teams Linked directly: {team_count}")
            print("-" * 20)

        print("\n=== Checking Premier League vs Brasileirao ===")
        for slug in ['brasileirao', 'premier-league']:
            l = Liga.query.filter_by(slug=slug).first()
            if not l:
                print(f"MISSING: {slug}")
                continue
            
            # Check matches per season
            for s in l.temporadas:
                match_count = len(s.partidas)
                print(f"{slug} {s.ano}: {match_count} matches")

if __name__ == "__main__":
    check_data()
