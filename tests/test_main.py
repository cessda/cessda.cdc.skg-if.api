# Copyright CESSDA ERIC 2025

# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from fastapi.testclient import TestClient
from cessda_skgif_api.main import app

client = TestClient(app)


class TestMain(unittest.TestCase):

    def test_app_metadata(self):
        self.assertEqual(app.title, "CESSDA Data Catalogue SKG-IF API")
        self.assertEqual(app.openapi_url, "/openapi_skg-if_cessda_dynamic.yaml")

    def test_root_info_page(self):
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("CESSDA SKG-IF API Info", response.text)
        self.assertIn("Products", response.text)

    def test_docs_page(self):
        response = client.get("/docs")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Swagger UI", response.text)

    def test_redoc_page(self):
        response = client.get("/redoc")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ReDoc", response.text)

    def test_docs_static_page(self):
        response = client.get("/docs-static")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Swagger UI", response.text)

    def test_products_router_included(self):
        response = client.get("/products")
        self.assertIn(response.status_code, (200, 422))


if __name__ == "__main__":
    unittest.main()
