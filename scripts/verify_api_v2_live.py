import requests
import sys
import time
import os

BASE_URL = "http://localhost:5000/api/v2"

def verify_live():
    print("Waiting for server...")
    # Health check
    try:
        for _ in range(10):
            try:
                requests.get("http://localhost:5000/health")
                break
            except requests.ConnectionError:
                time.sleep(1)
        else:
            print("FAILED: Server not reachable")
            return
            
        # 1. Test List Matches
        print("\n--- Testing GET /api/v2/matches/ ---")
        response = requests.get(f'{BASE_URL}/matches/', params={'per_page': 5})
        
        if response.status_code != 200:
            print(f"FAILED: Status code {response.status_code}")
            print(response.text)
            return
            
        data = response.json()
        
        # Verify Envelope
        if 'data' in data and 'meta' in data and 'links' in data:
            print("PASSED: Envelope structure correct")
        else:
            print("FAILED: Envelope structure incorrect")
            print(data.keys())
            
        # Verify Pagination Meta
        meta = data.get('meta', {})
        if 'pagination' in meta:
            print(f"PASSED: Pagination meta present. Total matches: {meta['pagination']['total']}")
            print(f"Info: Page {meta['pagination']['page']} of {meta['pagination']['pages']}")
        else:
            print("FAILED: Pagination meta missing")
            
        matches = data.get('data', [])
        print(f"Info: Fetched {len(matches)} matches")
        
        if len(matches) > 0:
            first_match_id = matches[0]['id']
            
            # 2. Test Get Match Details
            print(f"\n--- Testing GET /api/v2/matches/{first_match_id} ---")
            response = requests.get(f'{BASE_URL}/matches/{first_match_id}')
            
            if response.status_code == 200:
                detail_data = response.json()
                if 'data' in detail_data and detail_data['data']['id'] == first_match_id:
                    print("PASSED: Match details fetched successfully")
                else:
                    print("FAILED: Match details incorrect")
            else:
                print(f"FAILED: Status code {response.status_code}")
                
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    verify_live()
