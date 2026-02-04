import os
import sys
from datetime import datetime

# Add root project directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Liga

def seed_leagues():
    app = create_app()
    with app.app_context():
        leagues_data = [
            {
                "nome": "Série A - Brasileirão",
                "slug": "brasileirao",
                "ogol_slug": "brasileirao",
                "pais": "Brasil",
                "confederacao": "CONMEBOL",
                "num_times": 20,
                "num_rodadas": 38
            },
            {
                "nome": "Premier League",
                "slug": "premier-league",
                "ogol_slug": "premier-league",
                "pais": "Inglaterra",
                "confederacao": "UEFA",
                "num_times": 20,
                "num_rodadas": 38
            },
            {
                "nome": "La Liga",
                "slug": "la-liga",
                "ogol_slug": "campeonato-espanhol",
                "pais": "Espanha",
                "confederacao": "UEFA",
                "num_times": 20,
                "num_rodadas": 38
            },
            {
                "nome": "Ligue 1",
                "slug": "ligue-1",
                "ogol_slug": "campeonato-frances",
                "pais": "França",
                "confederacao": "UEFA",
                "num_times": 18,
                "num_rodadas": 34
            }
        ]

        print("🌱 Seeding leagues...")
        for data in leagues_data:
            existing = Liga.query.filter_by(slug=data['slug']).first()
            if not existing:
                liga = Liga(**data)
                db.session.add(liga)
                print(f"✅ Added: {data['nome']}")
            else:
                print(f"⏭️  Already exists: {data['nome']}")
        
        db.session.commit()
        print("🏁 Seeding completed!")

if __name__ == "__main__":
    seed_leagues()
