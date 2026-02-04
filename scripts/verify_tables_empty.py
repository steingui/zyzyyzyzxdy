import sys
import os
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db

def verify_tables_empty():
    app = create_app()
    with app.app_context():
        print("🔍 Verifying table row counts...")
        
        # Get all table names
        inspector = db.inspect(db.engine)
        table_names = inspector.get_table_names()
        
        all_empty = True
        
        for table in table_names:
            # We use direct SQL count for speed and simplicity
            # Assuming 'alembic_version' might exist and shouldn't be zero necessarily (if migrations ran)
            # but usually usually reset_database drops everything including alembic_version then create_all might not put it back unless we run flask migrate.
            # create_all() creates schemas but doesn't populate alembic_version.
            
            if table == 'alembic_version':
                continue
                
            count = db.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            
            if count == 0:
                print(f"✅ {table}: 0 rows")
            else:
                print(f"❌ {table}: {count} rows (NOT EMPTY)")
                all_empty = False
                
        if all_empty:
            print("\n✨ All application tables are empty!")
        else:
            print("\n⚠ Some tables contain data.")

if __name__ == "__main__":
    verify_tables_empty()
