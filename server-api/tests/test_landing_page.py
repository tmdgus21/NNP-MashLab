"""GET / serves the Potato Meet landing page (server-api/landing/index.html)."""
import os
import unittest

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"
import database as database_module
database_module._engine = None

from fastapi.testclient import TestClient

import main
from main import app


class LandingPageTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_root_serves_landing_html(self):
        self.assertTrue(main.LANDING_PAGE.is_file())
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/html"))
        self.assertIn("<title>Potato Meet</title>", response.text)

    def test_root_head(self):
        self.assertEqual(self.client.head("/").status_code, 200)

    def test_api_routes_untouched(self):
        self.assertEqual(self.client.get("/openapi.json").status_code, 200)


if __name__ == "__main__":
    unittest.main()
