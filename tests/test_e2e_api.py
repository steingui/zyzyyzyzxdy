import unittest
import json
import time
from app import create_app
from app.config import Config
from app.models import db, Liga
from dotenv import load_dotenv

load_dotenv()

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    # Disable caching for tests
    CACHE_TYPE = "NullCache"

class TestE2EApi(unittest.TestCase):
    def setUp(self):
        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed Liga
        liga = Liga(ogol_slug='brasileirao', slug='brasileirao', nome='Brasileirão', pais='Brasil', num_rodadas=38)
        db.session.add(liga)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_scrape_endpoint_validation(self):
        """Test validation failures"""
        # Missing year
        resp = self.client.post('/api/scrape', json={'league': 'brasileirao'})
        self.assertEqual(resp.status_code, 400)
        
        # Missing league
        resp = self.client.post('/api/scrape', json={'year': 2026})
        self.assertEqual(resp.status_code, 400)

    def test_scrape_flow(self):
        """Test successful enqueue and status check pattern"""
        payload = {
            'league': 'brasileirao',
            'year': 2026,
            'round': 1
        }
        
        # 1. Enqueue
        resp = self.client.post('/api/scrape', json=payload)
        self.assertEqual(resp.status_code, 202)
        data = resp.get_json()
        self.assertIn('job_id', data)
        job_id = data['job_id']

        # 2. Check Status
        resp_status = self.client.get(f'/api/scrape/status/{job_id}')
        self.assertEqual(resp_status.status_code, 200)
        status_data = resp_status.get_json()
        self.assertEqual(status_data['status'], 'queued')

if __name__ == '__main__':
    unittest.main()
