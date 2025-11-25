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
from cessda_skgif_api.routes.common import build_meta, build_url


class TestHelperFunctions(unittest.TestCase):
    def test_build_url_with_params(self):
        url = build_url("https://example.com/api/products", filter="x", page=2)
        self.assertIn("filter=x", url)
        self.assertIn("page=2", url)

    def test_build_meta_first_page(self):
        meta = build_meta(
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
        meta = build_meta(
            "https://example.com/api/products",
            "filter=test",
            page=2,
            page_size=10,
            total_count=50,
        )
        self.assertIn("previous_page", meta)
        self.assertIn("next_page", meta)

    def test_build_meta_last_page(self):
        meta = build_meta(
            "https://example.com/api/products",
            "filter=test",
            page=5,
            page_size=10,
            total_count=50,
        )
        self.assertNotIn("next_page", meta)
        self.assertIn("last_page", meta["part_of"])
