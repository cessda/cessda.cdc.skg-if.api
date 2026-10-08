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

import difflib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from cessda_skgif_api.transformers.related_publication_transformer import (
    extract_related_publication_dates,
    extract_related_publication_identifiers,
    extract_related_publication_titles,
    transform_related_publication_to_skgif_product,
)
from cessda_skgif_api.utils.helpers import wrap_jsonld

EXPECTED_LOCAL_IDENTIFIER = "https://w3id.org/cessda/cessda_product_literature_b2de4c47a19c0c5103fc9f48"

CITED_STUDY = (
    "https://w3id.org/cessda/"
    "cessda_product_research_data_f648dfcb5cd0a4e87fcabe7b7e04a7976ae6f321aa463e4abba2e99d092785ec"
)


def compare_json_structures(expected, actual):
    expected_str = json.dumps(expected, sort_keys=True, indent=2)
    actual_str = json.dumps(actual, sort_keys=True, indent=2)

    if expected_str != actual_str:
        diff = difflib.unified_diff(
            expected_str.splitlines(),
            actual_str.splitlines(),
            fromfile="expected",
            tofile="actual",
            lineterm="",
        )
        return "\n".join(diff)

    return None


def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestRelatedPublicationHelperFunctions(unittest.TestCase):
    def test_extract_related_publication_titles(self):
        group = [
            {
                "related_publication": "Publication title",
                "language": "en",
            }
        ]

        titles = extract_related_publication_titles(group)

        self.assertEqual(
            titles,
            {
                "en": [
                    "Publication title",
                ]
            },
        )

    def test_extract_related_publication_titles_uses_description_fallback(self):
        group = [
            {
                "description": "Fallback title",
                "language": "en",
            }
        ]

        titles = extract_related_publication_titles(group)

        self.assertEqual(
            titles,
            {
                "en": [
                    "Fallback title",
                ]
            },
        )

    def test_extract_related_publication_titles_defaults_to_en(self):
        group = [
            {
                "related_publication": "Publication title",
            }
        ]

        titles = extract_related_publication_titles(group)

        self.assertEqual(
            titles,
            {
                "en": [
                    "Publication title",
                ]
            },
        )

    def test_extract_related_publication_titles_deduplicates_by_language_and_value(self):
        group = [
            {
                "related_publication": "Publication title",
                "language": "en",
            },
            {
                "related_publication": "Publication title",
                "language": "en",
            },
            {
                "related_publication": "Publication title",
                "language": "fi",
            },
        ]

        titles = extract_related_publication_titles(group)

        self.assertEqual(
            titles,
            {
                "en": [
                    "Publication title",
                ],
                "fi": [
                    "Publication title",
                ],
            },
        )

    def test_extract_related_publication_titles_returns_none_when_empty(self):
        group = [
            {
                "language": "en",
            },
            {
                "related_publication": "",
                "description": "",
                "language": "en",
            },
        ]

        titles = extract_related_publication_titles(group)

        self.assertIsNone(titles)

    def test_extract_related_publication_identifiers(self):
        group = [
            {
                "identifier_agency": "DOI",
                "identifier": "10.1234/example",
            },
            {
                "identifier_agency": "URN",
                "identifier": "URN:NBN:fi:tuni-202105124917",
            },
        ]

        identifiers = extract_related_publication_identifiers(group)

        self.assertIsNotNone(identifiers)
        self.assertEqual(len(identifiers), 2)
        self.assertEqual(identifiers[0].scheme, "doi")
        self.assertEqual(identifiers[0].value, "10.1234/example")
        self.assertEqual(identifiers[1].scheme, "urn")
        self.assertEqual(identifiers[1].value, "URN:NBN:fi:tuni-202105124917")

    def test_extract_related_publication_identifiers_strips_and_lowercases_scheme(self):
        group = [
            {
                "identifier_agency": " DOI ",
                "identifier": " 10.1234/example ",
            }
        ]

        identifiers = extract_related_publication_identifiers(group)

        self.assertIsNotNone(identifiers)
        self.assertEqual(len(identifiers), 1)
        self.assertEqual(identifiers[0].scheme, "doi")
        self.assertEqual(identifiers[0].value, "10.1234/example")

    def test_extract_related_publication_identifiers_deduplicates_by_scheme_and_value(self):
        group = [
            {
                "identifier_agency": "doi",
                "identifier": "10.1234/example",
            },
            {
                "identifier_agency": "doi",
                "identifier": "10.1234/example",
            },
            {
                "identifier_agency": "urn",
                "identifier": "10.1234/example",
            },
        ]

        identifiers = extract_related_publication_identifiers(group)

        self.assertIsNotNone(identifiers)
        self.assertEqual(len(identifiers), 2)
        self.assertEqual(identifiers[0].scheme, "doi")
        self.assertEqual(identifiers[1].scheme, "urn")

    def test_extract_related_publication_identifiers_returns_none_when_empty(self):
        group = [
            {
                "identifier_agency": "",
                "identifier": "10.1234/example",
            },
            {
                "identifier_agency": "doi",
                "identifier": "",
            },
            {
                "identifier_agency": None,
                "identifier": None,
            },
        ]

        identifiers = extract_related_publication_identifiers(group)

        self.assertIsNone(identifiers)

    def test_extract_related_publication_dates(self):
        group = [
            {
                "distribution_date": "1997",
            }
        ]

        dates = extract_related_publication_dates(group)

        self.assertEqual(
            dates,
            {
                "publication": [
                    "1997",
                ]
            },
        )

    def test_extract_related_publication_dates_strips_and_deduplicates(self):
        group = [
            {
                "distribution_date": " 1997 ",
            },
            {
                "distribution_date": "1997",
            },
            {
                "distribution_date": "1998",
            },
        ]

        dates = extract_related_publication_dates(group)

        self.assertEqual(
            dates,
            {
                "publication": [
                    "1997",
                    "1998",
                ]
            },
        )

    def test_extract_related_publication_dates_returns_none_when_empty(self):
        group = [
            {
                "distribution_date": "",
            },
            {
                "distribution_date": None,
            },
            {},
        ]

        dates = extract_related_publication_dates(group)

        self.assertIsNone(dates)


class TestRelatedPublicationTransformer(unittest.TestCase):
    def test_transform_related_publication_to_skgif_product_minimal(self):
        group = [
            {
                "related_publication": "Publication title",
                "language": "en",
            }
        ]

        with patch(
            "cessda_skgif_api.transformers.related_publication_transformer."
            "generate_related_publication_local_identifier",
            return_value=EXPECTED_LOCAL_IDENTIFIER,
        ):
            product = transform_related_publication_to_skgif_product(
                related_publication_group=group,
                cited_studies=[CITED_STUDY],
            )

        self.assertEqual(product.local_identifier, EXPECTED_LOCAL_IDENTIFIER)
        self.assertEqual(product.product_type, "literature")
        self.assertEqual(
            product.titles,
            {
                "en": [
                    "Publication title",
                ]
            },
        )
        self.assertIsNone(product.identifiers)
        self.assertIsNone(product.manifestations)
        self.assertEqual(
            product.related_products,
            {
                "cites": [
                    CITED_STUDY,
                ]
            },
        )

    def test_transform_related_publication_to_skgif_product_with_identifier_and_date(self):
        group = [
            {
                "related_publication": "Publication title",
                "language": "en",
                "identifier_agency": "doi",
                "identifier": "10.1234/example",
                "distribution_date": "1997",
            }
        ]

        with patch(
            "cessda_skgif_api.transformers.related_publication_transformer."
            "generate_related_publication_local_identifier",
            return_value=EXPECTED_LOCAL_IDENTIFIER,
        ):
            product = transform_related_publication_to_skgif_product(
                related_publication_group=group,
                cited_studies=[CITED_STUDY],
            )

        self.assertEqual(product.local_identifier, EXPECTED_LOCAL_IDENTIFIER)
        self.assertEqual(product.product_type, "literature")

        self.assertIsNotNone(product.identifiers)
        self.assertEqual(len(product.identifiers), 1)
        self.assertEqual(product.identifiers[0].scheme, "doi")
        self.assertEqual(product.identifiers[0].value, "10.1234/example")

        self.assertIsNotNone(product.manifestations)
        self.assertEqual(len(product.manifestations), 1)
        self.assertEqual(
            product.manifestations[0].dates,
            {
                "publication": [
                    "1997",
                ]
            },
        )

        self.assertEqual(
            product.related_products,
            {
                "cites": [
                    CITED_STUDY,
                ]
            },
        )

    def test_transformation_output(self):
        """
        Tests complete related publication product transformation.

        The local identifier is patched here so this test only verifies the
        related publication transformer output shape, not the hashing logic.
        The identifier generation should be tested separately in identifier_utils.
        """
        group = [
            {
                "related_publication": (
                    "A Comparison of 1994/1995 International Survey of " "Economic Attitudes Data with Censuses"
                ),
                "language": "en",
                "distribution_date": "1997",
            }
        ]

        base_dir = Path(__file__).parent
        expected_file = base_dir / "product_related_publication_example.jsonld"

        self.assertTrue(expected_file.exists(), f"{expected_file} does not exist.")

        expected_output = load_json(expected_file)

        with patch(
            "cessda_skgif_api.transformers.related_publication_transformer."
            "generate_related_publication_local_identifier",
            return_value=EXPECTED_LOCAL_IDENTIFIER,
        ):
            raw_output = transform_related_publication_to_skgif_product(
                related_publication_group=group,
                cited_studies=[CITED_STUDY],
            ).model_dump(
                by_alias=True,
                exclude_none=True,
            )

        actual_output = wrap_jsonld([raw_output])

        diff = compare_json_structures(expected_output, actual_output)
        if diff:
            print("\nDifferences:\n", diff)
            self.fail("Transformed related publication output does not match expected output.")
