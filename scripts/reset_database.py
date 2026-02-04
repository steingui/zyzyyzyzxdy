import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
import app.models  # Import models to ensure they are registered with SQLAlchemy

import subprocess

def reset_database():
    """
    Drops all tables and recreates them to reset the database.
    Ensures migration state is synchronized.
    """
    app = create_app()
    with app.app_context():
        print("⚠  Dropping all tables...")
        from sqlalchemy import text
        # Drop application tables
        db.drop_all()
        # Explicitly drop alembic_version to reset migration state
        db.session.execute(text("DROP TABLE IF EXISTS alembic_version"))
        db.session.commit()
        print("✅ Tables and version history dropped.")
        
        print("🔨 Recreating tables via migrations...")
        # Run flask db upgrade to recreate tables and set the head version
        try:
            result = subprocess.run(["flask", "db", "upgrade"], capture_output=True, text=True, check=True)
            print(result.stdout)
            print("✅ Database reset successfully via migrations!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error during flask db upgrade: {e.stderr}")
            print("Falling back to db.create_all()...")
            db.create_all()
            print("✅ Database recreated (no migration history).")

if __name__ == "__main__":
    reset_database()
