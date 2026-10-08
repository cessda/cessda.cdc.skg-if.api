# Copyright CESSDA ERIC 2026

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

from cessda_skgif_api.utils.helpers import (
    dedupe_preserve_order,
    first_non_empty,
    normalize_text,
    wrap_jsonld,
)


class TestHelpers(unittest.TestCase):
    def test_wrap_jsonld_with_single_dict(self):
        data = {"id": "123"}

        result = wrap_jsonld(data)

        self.assertIn("@context", result)
        self.assertIn("@graph", result)
        self.assertEqual(result["@graph"], [data])

    def test_wrap_jsonld_with_list(self):
        data = [
            {"id": "1"},
            {"id": "2"},
        ]

        result = wrap_jsonld(data)

        self.assertEqual(result["@graph"], data)

    def test_wrap_jsonld_with_meta(self):
        data = {"id": "123"}
        meta = {
            "count": 1,
            "next": None,
        }

        result = wrap_jsonld(data, meta=meta)

        self.assertEqual(result["meta"], meta)
        self.assertEqual(result["@graph"], [data])

    def test_normalize_text(self):
        self.assertEqual(
            normalize_text("  Hello   World  "),
            "hello world",
        )

    def test_normalize_text_casefold(self):
        self.assertEqual(
            normalize_text("ÄÖÅ"),
            "äöå",
        )

    def test_normalize_text_empty(self):
        self.assertEqual(normalize_text(None), "")
        self.assertEqual(normalize_text(""), "")
        self.assertEqual(normalize_text("   "), "")

    def test_first_non_empty(self):
        result = first_non_empty(
            None,
            "",
            "   ",
            "value",
            "other",
        )

        self.assertEqual(result, "value")

    def test_first_non_empty_strips_whitespace(self):
        result = first_non_empty(
            None,
            "  value  ",
        )

        self.assertEqual(result, "value")

    def test_first_non_empty_returns_none(self):
        self.assertIsNone(
            first_non_empty(
                None,
                "",
                "   ",
            )
        )

    def test_dedupe_preserve_order(self):
        values = [
            "First",
            "Second",
            "First",
            "Third",
        ]

        result = dedupe_preserve_order(values)

        self.assertEqual(
            result,
            [
                "First",
                "Second",
                "Third",
            ],
        )

    def test_dedupe_preserve_order_case_insensitive(self):
        values = [
            "First",
            "first",
            "FIRST",
            "Second",
        ]

        result = dedupe_preserve_order(values)

        self.assertEqual(
            result,
            [
                "First",
                "Second",
            ],
        )

    def test_dedupe_preserve_order_normalizes_whitespace(self):
        values = [
            "Hello World",
            "  Hello    World  ",
            "Other",
        ]

        result = dedupe_preserve_order(values)

        self.assertEqual(
            result,
            [
                "Hello World",
                "Other",
            ],
        )

    def test_dedupe_preserve_order_skips_empty_values(self):
        values = [
            "",
            None,
            "Value",
            "",
        ]

        result = dedupe_preserve_order(values)

        self.assertEqual(
            result,
            [
                "Value",
            ],
        )
