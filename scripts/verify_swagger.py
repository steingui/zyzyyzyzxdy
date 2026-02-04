import sys
import os
import json
# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

def verify_swagger():
    app = create_app()
    client = app.test_client()
    
    # 1. Test Spec JSON
    print("\n--- Testing GET /api/docs/spec.json ---")
    response = client.get('/api/docs/spec.json')
    
    if response.status_code != 200:
        print(f"FAILED: Status code {response.status_code}")
        print(response.get_json())
        return
        
    spec = response.get_json()
    
    # Verify Version
    if spec.get('info', {}).get('version') == 'v2.0.0':
        print("PASSED: Info version correct")
    else:
        print("FAILED: Info version mismatch")
        
    # Verify Paths
    paths = spec.get('paths', {})
    if '/api/v2/matches/' in paths:
        print("PASSED: /api/v2/matches/ path present")
    else:
        print("FAILED: /api/v2/matches/ path missing")
        print("Found paths:", paths.keys())
        
    if '/api/v2/matches/{match_id}' in paths:
         print("PASSED: /api/v2/matches/{match_id} path present")
    else:
         print("FAILED: /api/v2/matches/{match_id} path missing")

    # Verify Components
    schemas = spec.get('components', {}).get('schemas', {})
    if 'Partida' in schemas and 'PaginationMeta' in schemas:
        print("PASSED: Schemas present")
    else:
        print("FAILED: Schemas missing")
        print("Found schemas:", schemas.keys())

if __name__ == "__main__":
    verify_swagger()
