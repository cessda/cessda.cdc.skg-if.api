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
from unittest.mock import patch
from starlette.requests import Request
from fastapi import HTTPException
from cessda_skgif_api.routes import products
from tests import FakeCollection


def make_fake_request():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
        "app": None,
    }
    return Request(scope)


class TestHelperFunctions(unittest.TestCase):
    def test_extract_identifier_with_url(self):
        url = "https://example.com/api/products/ABC123"
        self.assertEqual(products.extract_identifier(url), "ABC123")

    def test_extract_identifier_plain(self):
        self.assertEqual(products.extract_identifier("XYZ789"), "XYZ789")


class TestAsyncEndpoints(unittest.IsolatedAsyncioTestCase):
    @patch("cessda_skgif_api.routes.products.parse_filter_string", return_value={})
    @patch("cessda_skgif_api.routes.products.transform_study_to_skgif_product")
    @patch("cessda_skgif_api.routes.products.get_collection")
    async def test_get_products(self, mock_get_collection, mock_transform, mock_parse):
        # Fake collection
        fake_docs = [{"_id": 1}]
        fake_coll = FakeCollection(docs=fake_docs, one=None, count=1)
        mock_get_collection.return_value = fake_coll

        # Mock transformer output
        mock_transform.return_value.dict.return_value = {"id": "ABC123"}

        req = make_fake_request()

        response = await products.get_products(
            request=req,
            filter_str=None,
            page=1,
            page_size=10,
        )

        body = response.body.decode()

        self.assertIn("meta", body)
        self.assertIn("ABC123", body)

    @patch("cessda_skgif_api.routes.products.get_collection")
    @patch("cessda_skgif_api.routes.products.transform_study_to_skgif_product")
    async def test_get_product_by_id_found(self, mock_transform, mock_get_collection):
        # Fake single document
        fake_doc = {"identifiers": [{"identifier": "ABC123"}]}
        fake_coll = FakeCollection(docs=[fake_doc], one=fake_doc, count=1)

        mock_get_collection.return_value = fake_coll
        mock_transform.return_value.dict.return_value = {"id": "ABC123"}

        req = make_fake_request()

        response = await products.get_product_by_id(
            request=req,
            local_identifier="ABC123",
        )

        self.assertIn("ABC123", response.body.decode())

    async def test_get_product_by_id_not_found(self):
        empty_collection = FakeCollection(docs=[], one=None, count=0)

        req = make_fake_request()

        with patch(
            "cessda_skgif_api.routes.products.get_collection",
            return_value=empty_collection,
        ):
            with self.assertRaises(HTTPException) as exc:
                await products.get_product_by_id(req, "XYZ")

            self.assertEqual(exc.exception.status_code, 404)
