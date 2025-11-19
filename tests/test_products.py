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
from unittest.mock import patch, AsyncMock
from cessda_skgif_api.routes import products


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def skip(self, n):
        return self

    def limit(self, n):
        return self

    def __aiter__(self):
        async def gen():
            for doc in self.docs:
                yield doc

        return gen()


class TestHelperFunctions(unittest.TestCase):
    def test_extract_identifier_with_url(self):
        url = "https://example.com/api/products/ABC123"
        self.assertEqual(products.extract_identifier(url), "ABC123")

    def test_extract_identifier_plain(self):
        self.assertEqual(products.extract_identifier("XYZ789"), "XYZ789")

    def test_build_url_with_params(self):
        url = products.build_url("https://example.com/api/products", filter="x", page=2)
        self.assertIn("filter=x", url)
        self.assertIn("page=2", url)

    def test_build_meta_first_page(self):
        meta = products.build_meta(
            "https://example.com/api/products",
            "filter=test",
            page=1,
            page_size=10,
            total_count=50,
        )
        self.assertNotIn("previous_page", meta)
        self.assertIn("next_page", meta)
        self.assertEqual(meta["part_of"]["total_items"], 50)

    def test_build_meta_middle_page(self):
        meta = products.build_meta(
            "https://example.com/api/products",
            "filter=test",
            page=2,
            page_size=10,
            total_count=50,
        )
        self.assertIn("previous_page", meta)
        self.assertIn("next_page", meta)

    def test_build_meta_last_page(self):
        meta = products.build_meta(
            "https://example.com/api/products",
            "filter=test",
            page=5,
            page_size=10,
            total_count=50,
        )
        self.assertNotIn("next_page", meta)
        self.assertIn("last_page", meta)


class TestAsyncEndpoints(unittest.IsolatedAsyncioTestCase):
    @patch("cessda_skgif_api.routes.products.get_collection")
    @patch("cessda_skgif_api.routes.products.parse_filter_string", return_value={})
    @patch("cessda_skgif_api.routes.products.transform_study_to_skgif_product")
    async def test_get_products(self, mock_transform, mock_parse, mock_collection):
        mock_collection.return_value.count_documents = AsyncMock(return_value=1)
        fake_cursor = FakeCursor([{"_aggregator_identifier": "ABC123"}])
        mock_collection.return_value.find.return_value = fake_cursor

        async def fake_find():
            yield {"_aggregator_identifier": "ABC123"}

        mock_collection.return_value.find.return_value.__aiter__ = lambda self=None: fake_find()
        mock_transform.return_value.dict.return_value = {"id": "ABC123"}

        response = await products.get_products(filter_str=None, page=1, page_size=10)
        body = response.body.decode()
        self.assertIn("meta", body)
        self.assertIn("ABC123", body)

    @patch("cessda_skgif_api.routes.products.get_collection")
    @patch("cessda_skgif_api.routes.products.transform_study_to_skgif_product")
    async def test_get_product_by_id_found(self, mock_transform, mock_collection):
        mock_collection.return_value.find_one = AsyncMock(return_value={"_aggregator_identifier": "ABC123"})
        mock_transform.return_value.dict.return_value = {"id": "ABC123"}

        response = await products.get_product_by_id("ABC123")
        body = response.body.decode()
        self.assertIn("ABC123", body)

    @patch("cessda_skgif_api.routes.products.get_collection")
    async def test_get_product_by_id_not_found(self, mock_collection):
        mock_collection.return_value.find_one = AsyncMock(return_value=None)
        with self.assertRaises(Exception) as exc:
            await products.get_product_by_id("XYZ")
        self.assertEqual(exc.exception.status_code, 404)
