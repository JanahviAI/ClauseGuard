import unittest
import os
import sys
import json
from unittest.mock import patch

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from dashboard import app

class TestExtensionAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_analyze_policy_success(self):
        # We need a text that passes the prefilter.
        # "Your IP address is logged for security purposes." is one of the fixture texts.
        payload = {
            "text": "Your IP address is logged for security purposes.",
            "url": "https://example.com/privacy",
            "title": "Example Privacy Policy"
        }
        
        response = self.app.post('/api/analyze-policy', json=payload)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn("service_name", data)
        self.assertEqual(data["service_name"], "Example Privacy Policy")
        self.assertIn("mode", data)
        self.assertIn("clauses", data)
        self.assertIn("canonical_entities", data)
        self.assertIn("risk", data)
        self.assertEqual(data["policy_url"], "https://example.com/privacy")

    def test_analyze_policy_service_name_fallback(self):
        payload = {
            "text": "Your IP address is logged for security purposes.",
            "url": "https://www.spotify.com/privacy"
        }
        response = self.app.post('/api/analyze-policy', json=payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["service_name"], "Spotify")

    def test_analyze_policy_missing_text(self):
        response = self.app.post('/api/analyze-policy', json={"url": "test"})
        self.assertEqual(response.status_code, 400)
        
    def test_analyze_policy_empty_text(self):
        response = self.app.post('/api/analyze-policy', json={"text": "   "})
        self.assertEqual(response.status_code, 400)

    def test_analyze_policy_options_cors(self):
        response = self.app.options('/api/analyze-policy')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), '*')

if __name__ == '__main__':
    unittest.main()
