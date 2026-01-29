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

import asyncio
import difflib
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch
from cessda_skgif_api.transformers.skgif_transformer import (
    aggregate_funding,
    build_biblio,
    build_contributions,
    extract_access_rights,
    extract_identifiers,
    extract_titles_and_abstracts,
    extract_dates,
    generate_product_local_identifier,
    normalize_scheme,
    select_preferred_language_entries,
    transform_classifications_to_topics,
    transform_study_to_skgif_product,
)
from cessda_skgif_api.routes.products import wrap_jsonld
from cessda_skgif_api.cache.cessda_topic_vocab import (
    cessda_topic_vocab_cache,
    load_cessda_topic_vocab,
)

_cache_patchers = []
_tmpdir = None


def setUpModule():
    """Apply cache isolation for all tests in this module."""
    global _cache_patchers, _tmpdir
    _tmpdir = tempfile.TemporaryDirectory()
    test_cessda = Path(_tmpdir.name) / "test_cessda_topic_classification_vocab_cache.json"

    _cache_patchers = [
        # Redirect cache files to temp paths
        patch.object(cessda_topic_vocab_cache, "cache_file", test_cessda),
        # Disable disk I/O for the duration of this module
        patch.object(cessda_topic_vocab_cache, "save_to_disk", MagicMock()),
        patch.object(cessda_topic_vocab_cache, "load_from_disk", MagicMock()),
    ]
    for p in _cache_patchers:
        p.start()

    # Clear the new in-memory structures so each module starts “fresh”
    cessda_topic_vocab_cache._entries = {}
    cessda_topic_vocab_cache._groups_ts = {}


def tearDownModule():
    """Remove patches and temp files after ALL tests in this module."""
    global _cache_patchers, _tmpdir
    for p in _cache_patchers:
        try:
            p.stop()
        except Exception:
            pass
    if _tmpdir:
        _tmpdir.cleanup()


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


def clean_dict(d):
    if isinstance(d, dict):
        return {
            k: clean_dict(v)
            for k, v in d.items()
            if not (k == "local_identifier" and isinstance(v, str) and v.startswith("otf__"))
        }
    elif isinstance(d, list):
        return [clean_dict(item) for item in d]
    else:
        return d


def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestHelperFunctions(unittest.TestCase):
    def test_extract_identifiers(self):
        doc = {
            "identifiers": [
                {"agency": "doi", "identifier": "10.1234", "language": "en"},
                {"agency": "doi", "identifier": "10.1234", "language": "fi"},
                {"agency": "fsd", "identifier": "FSD1000", "language": "fi"},
            ]
        }
        ids = extract_identifiers(doc)
        self.assertEqual(len(ids), 2)
        self.assertEqual(ids[0].scheme, "doi")
        self.assertEqual(ids[1].scheme, "fsd")

    def test_extract_titles_and_abstracts(self):
        doc = {
            "study_titles": [{"study_title": "Title", "language": "en"}],
            "abstracts": [{"abstract": "Abstract", "language": "en"}],
        }
        titles, abstracts = extract_titles_and_abstracts(doc)
        self.assertIn("en", titles)
        self.assertIn("en", abstracts)

    def test_extract_dates(self):
        doc = {
            "distribution_dates": [{"distribution_date": "2020-01-01"}],
            "collection_periods": [{"collection_period": "2019", "language": "en"}],
        }
        dates = extract_dates(doc)
        self.assertIn("publication", dates)
        self.assertIn("collected", dates)

    def test_aggregate_funding(self):
        doc = {"grant_numbers": [{"grant_number": "G123", "agency": "Agency"}]}
        funding = aggregate_funding(doc)
        self.assertEqual(len(funding), 1)
        self.assertEqual(funding[0].grant_number, "G123")

    def test_build_contributions(self):
        doc = {
            "principal_investigators": [
                {
                    "principal_investigator": "Alice Smith",
                    "organization": "University A",
                    "external_link": "0000-0001-2345-6789",
                    "external_link_title": "orcid",
                }
            ]
        }
        contributions = build_contributions(doc)
        self.assertIsNotNone(contributions)
        self.assertEqual(contributions[0].by.name, "Alice Smith")
        self.assertEqual(contributions[0].by.identifiers[0].scheme, "orcid")

    def test_build_biblio(self):
        doc = {"_direct_base_url": "https://archivdv.soc.cas.cz/oai"}
        biblio = build_biblio(doc)
        self.assertIsNotNone(biblio.in_)
        self.assertEqual(biblio.hosting_data_source.name, "Czech Social Science Data Archive")

    def test_generate_product_local_identifier_fallback(self):
        doc = {
            "_aggregator_identifier": "ABC123",
            "study_titles": [{"study_title": "Title", "language": "de"}],
        }
        url = generate_product_local_identifier(doc)
        self.assertTrue(url.endswith("?lang=de"))

    def test_select_preferred_language_entries_empty_and_fallback(self):
        self.assertEqual(select_preferred_language_entries([]), [])
        entries = [{"language": "fi", "value": "X"}]
        result = select_preferred_language_entries(entries)
        self.assertEqual(result[0]["language"], "fi")

    def test_normalize_scheme_variations(self):
        self.assertEqual(
            normalize_scheme("CESSDA Topic Classification"),
            "CESSDA_Topic_Classification",
        )
        self.assertEqual(normalize_scheme("Some Scheme"), "Some_Scheme")
        self.assertIsNone(normalize_scheme(None))

    @patch("cessda_skgif_api.cache.cessda_topic_vocab.httpx.AsyncClient.get")
    def test_load_cessda_topic_vocab_mocked(self, mock_get):
        # Prepare mock response
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "notation": "T1",
                "title": "Topic",
                "uri": "https://fake/[CODE]",
                "id": 123,
            }
        ]
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp

        # Reset cache between tests
        cessda_topic_vocab_cache._cache = {"timestamp": 0, "entries": {}}

        # Run async function in plain unittest
        vocab = asyncio.run(load_cessda_topic_vocab("en"))

        self.assertIn("T1", vocab)
        self.assertEqual(vocab["T1"]["title"], "Topic")
        self.assertTrue(vocab["T1"]["uri"].endswith("/123"))

    def test_transform_classifications_to_topics_empty_and_unknown_scheme(self):
        # Patch sync accessor used inside transformer
        with patch("cessda_skgif_api.transformers.skgif_transformer.get_cached_vocab") as mock_vocab:
            # Simulate failure or missing vocab
            mock_vocab.return_value = {}

            topics = transform_classifications_to_topics([])
            assert topics == []

            classifications = [
                {
                    "system_name": "Unknown",
                    "uri": "u",
                    "description": "desc",
                    "language": "en",
                }
            ]

            topics = transform_classifications_to_topics(classifications)

            # Should produce exactly one TopicLite with fallback behavior
            assert len(topics) == 1

    def test_build_contributions_org_and_agent(self):
        doc_org = {"principal_investigators": [{"principal_investigator": "OrgName", "external_link_title": "ror"}]}
        contributions_org = build_contributions(doc_org)
        self.assertEqual(contributions_org[0].by.__class__.__name__, "OrganisationLite")
        doc_agent = {"principal_investigators": [{"principal_investigator": "AgentName"}]}
        contributions_agent = build_contributions(doc_agent)
        self.assertEqual(contributions_agent[0].by.__class__.__name__, "Agent")

    def test_build_biblio_fallback_logic(self):
        doc = {"publishers": [{"publisher": "Fallback Publisher", "language": "en"}]}
        biblio = build_biblio(doc)
        self.assertEqual(biblio.hosting_data_source.name, "Fallback Publisher")

    def test_aggregate_funding_empty_and_dedup(self):
        self.assertIsNone(aggregate_funding({}))
        doc = {
            "grant_numbers": [{"grant_number": "G1", "agency": "A"}],
            "funding_agencies": [{"grant_number": "G1", "agency": "A"}],
        }
        funding = aggregate_funding(doc)
        self.assertEqual(len(funding), 1)

    @patch("cessda_skgif_api.transformers.skgif_transformer.requests.get")
    def test_extract_access_rights_mocked_mapping(self, mock_get):
        fake_mapping = {"FSD": {"dataRestrctnXPath": [{"content": "Open", "accessCategory": "open"}]}}
        mock_get.return_value.content = json.dumps(fake_mapping).encode("utf-8")
        mock_get.return_value.raise_for_status = lambda: None
        with patch("builtins.open", mock_open(read_data=json.dumps(fake_mapping))):
            doc = {
                "distributors": [{"abbreviation": "FSD", "language": "en"}],
                "data_access": [{"data_access": "Open", "language": "en"}],
            }
            access = extract_access_rights(doc)
            self.assertEqual(access["status"], "open")

    def test_transform_study_to_skgif_product_minimal(self):
        doc = {"_aggregator_identifier": "X"}
        with patch(
            "cessda_skgif_api.transformers.skgif_transformer.extract_access_rights",
            return_value={"status": "open"},
        ):
            product = transform_study_to_skgif_product(doc)
            self.assertEqual(product.product_type, "research data")


class TestSKGIFTransformer(unittest.TestCase):
    def test_transformation_output(self):
        """
        Tests complete product transformation using mocked CESSDA lookup.
        """
        with patch(
            "cessda_skgif_api.transformers.skgif_transformer.product_base_url",
            "https://datacatalogue.cessda.eu/detail",
        ), patch("cessda_skgif_api.transformers.skgif_transformer.get_cached_vocab") as mock_get_cached_vocab:

            # Mock CESSDA vocab by language
            mock_get_cached_vocab.side_effect = [
                {"SocialStratificationAndGroupings.Youth": {"title": "Youth", "uri": ""}},  # en
                {"SocialStratificationAndGroupings.Youth": {"title": "Nuoret", "uri": ""}},  # fi
            ]

            # Load fixtures
            base_dir = Path(__file__).parent
            input_file = base_dir / "kuha_output.json"
            expected_file = base_dir / "synthetic_product_example.jsonld"

            self.assertTrue(input_file.exists(), f"{input_file} does not exist.")
            self.assertTrue(expected_file.exists(), f"{expected_file} does not exist.")

            input_data = load_json(input_file)
            expected_output = clean_dict(load_json(expected_file))

            # Transform
            raw_output = transform_study_to_skgif_product(input_data).model_dump(
                by_alias=True,
                exclude_none=True,
            )
            actual_output = clean_dict(wrap_jsonld([raw_output]))

            # Compare
            diff = compare_json_structures(expected_output, actual_output)
            if diff:
                print("\nDifferences:\n", diff)
                self.fail("Transformed output does not match expected output.")
