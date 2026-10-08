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
from unittest.mock import patch

from cessda_skgif_api.utils.identifier_utils import (
    build_publication_identity_key,
    extract_study_id,
    generate_otf_local_identifier,
    generate_related_publication_local_identifier,
    generate_related_publication_unique_key,
    generate_study_local_identifier,
    normalize_pid_url,
    normalize_product_lookup_identifier,
    skg_if_cessda_context,
)
from cessda_skgif_api.utils.constants import (
    RELPUB_LOCAL_ID_PREFIX,
    STUDY_LOCAL_ID_PREFIX,
)

STUDY_HASH = "fb27f0a276fefdcea4abe82be6a15c0e0b72ea10f5f5d6308272fd3f48f9c2"
RELPUB_HASH = "b2de4c47a19c0c5103fc9f48"

CANONICAL_STUDY_ID = f"{skg_if_cessda_context}{STUDY_LOCAL_ID_PREFIX}{STUDY_HASH}"
CANONICAL_RELPUB_ID = f"{skg_if_cessda_context}{RELPUB_LOCAL_ID_PREFIX}{RELPUB_HASH}"


class TestNormalizePidUrl(unittest.TestCase):
    def test_normalize_pid_url_ror_code(self):
        self.assertEqual(
            normalize_pid_url("ror", "03yrm5c26"),
            "https://ror.org/03yrm5c26",
        )

    def test_normalize_pid_url_ror_code_uppercase_is_lowercased(self):
        self.assertEqual(
            normalize_pid_url("ror", "03YRM5C26"),
            "https://ror.org/03yrm5c26",
        )

    def test_normalize_pid_url_ror_url(self):
        self.assertEqual(
            normalize_pid_url("ror", "https://ror.org/03yrm5c26"),
            "https://ror.org/03yrm5c26",
        )

    def test_normalize_pid_url_ror_prefixed_code(self):
        self.assertEqual(
            normalize_pid_url("ror", "ror:03yrm5c26"),
            "https://ror.org/03yrm5c26",
        )

    def test_normalize_pid_url_orcid_code(self):
        self.assertEqual(
            normalize_pid_url("orcid", "0000-0003-1831-203X"),
            "https://orcid.org/0000-0003-1831-203X",
        )

    def test_normalize_pid_url_orcid_url(self):
        self.assertEqual(
            normalize_pid_url("orcid", "https://orcid.org/0000-0003-1831-203X"),
            "https://orcid.org/0000-0003-1831-203X",
        )

    def test_normalize_pid_url_strips_scheme_and_value(self):
        self.assertEqual(
            normalize_pid_url(" ORCID ", " 0000-0003-1831-203X "),
            "https://orcid.org/0000-0003-1831-203X",
        )

    def test_normalize_pid_url_returns_none_for_invalid_values(self):
        self.assertIsNone(normalize_pid_url("orcid", "not-valid"))
        self.assertIsNone(normalize_pid_url("ror", "not-valid"))
        self.assertIsNone(normalize_pid_url("doi", "10.1234/example"))
        self.assertIsNone(normalize_pid_url("", "0000-0003-1831-203X"))
        self.assertIsNone(normalize_pid_url("orcid", ""))
        self.assertIsNone(normalize_pid_url(None, "0000-0003-1831-203X"))
        self.assertIsNone(normalize_pid_url("orcid", None))


class TestPublicationIdentityKey(unittest.TestCase):
    def test_build_publication_identity_key_prefers_identifier(self):
        group = [
            {
                "identifier_agency": "doi",
                "identifier": "10.1234/example",
                "uri": "https://example.org/publication",
                "related_publication": "Publication title",
                "distribution_date": "2020",
            }
        ]

        self.assertEqual(
            build_publication_identity_key(group),
            ("identifier", "doi", "10.1234/example"),
        )

    def test_build_publication_identity_key_lowercases_identifier_agency(self):
        group = [
            {
                "identifier_agency": " DOI ",
                "identifier": " 10.1234/example ",
                "related_publication": "Publication title",
                "distribution_date": "2020",
            }
        ]

        self.assertEqual(
            build_publication_identity_key(group),
            ("identifier", "doi", "10.1234/example"),
        )

    def test_build_publication_identity_key_uses_uri_when_identifier_missing(self):
        group = [
            {
                "uri": "https://example.org/publication",
                "related_publication": "Publication title",
                "distribution_date": "2020",
            }
        ]

        self.assertEqual(
            build_publication_identity_key(group),
            ("uri", "https://example.org/publication"),
        )

    def test_build_publication_identity_key_uses_title_and_year_fallback(self):
        group = [
            {
                "related_publication": "Publication title",
                "distribution_date": "2020",
            }
        ]

        self.assertEqual(
            build_publication_identity_key(group),
            ("title", "publication title", "2020"),
        )

    def test_build_publication_identity_key_uses_description_fallback(self):
        group = [
            {
                "description": "Fallback publication title",
                "distribution_date": "2020",
            }
        ]

        self.assertEqual(
            build_publication_identity_key(group),
            ("title", "fallback publication title", "2020"),
        )

    def test_build_publication_identity_key_normalizes_title_whitespace_and_case(self):
        group = [
            {
                "related_publication": "  Publication    TITLE  ",
                "distribution_date": "2020",
            }
        ]

        self.assertEqual(
            build_publication_identity_key(group),
            ("title", "publication title", "2020"),
        )

    def test_build_publication_identity_key_uses_only_first_group_item(self):
        group = [
            {
                "related_publication": "First title",
                "distribution_date": "2020",
            },
            {
                "identifier_agency": "doi",
                "identifier": "10.1234/second",
                "related_publication": "Second title",
                "distribution_date": "2021",
            },
        ]

        self.assertEqual(
            build_publication_identity_key(group),
            ("title", "first title", "2020"),
        )


class TestRelatedPublicationUniqueKey(unittest.TestCase):
    def test_generate_related_publication_unique_key_is_stable(self):
        group = [
            {
                "identifier_agency": "doi",
                "identifier": "10.1234/example",
            }
        ]

        first = generate_related_publication_unique_key(group)
        second = generate_related_publication_unique_key(group)

        self.assertEqual(first, second)

    def test_generate_related_publication_unique_key_has_expected_length(self):
        group = [
            {
                "identifier_agency": "doi",
                "identifier": "10.1234/example",
            }
        ]

        unique_key = generate_related_publication_unique_key(group)

        self.assertEqual(len(unique_key), 24)
        self.assertRegex(unique_key, r"^[0-9a-f]{24}$")

    def test_generate_related_publication_unique_key_changes_when_identity_changes(self):
        group_one = [
            {
                "identifier_agency": "doi",
                "identifier": "10.1234/one",
            }
        ]

        group_two = [
            {
                "identifier_agency": "doi",
                "identifier": "10.1234/two",
            }
        ]

        self.assertNotEqual(
            generate_related_publication_unique_key(group_one),
            generate_related_publication_unique_key(group_two),
        )

    def test_generate_related_publication_unique_key_same_for_normalized_title(self):
        group_one = [
            {
                "related_publication": "Publication Title",
                "distribution_date": "2020",
            }
        ]

        group_two = [
            {
                "related_publication": "  publication   title  ",
                "distribution_date": "2020",
            }
        ]

        self.assertEqual(
            generate_related_publication_unique_key(group_one),
            generate_related_publication_unique_key(group_two),
        )


class TestLocalIdentifierGeneration(unittest.TestCase):
    def test_generate_otf_local_identifier(self):
        with patch("cessda_skgif_api.utils.identifier_utils.time.time", return_value=1234.567):
            identifier = generate_otf_local_identifier("topic", 2)

        self.assertEqual(identifier, "otf___1234567___topic-2")

    def test_generate_study_local_identifier(self):
        self.assertEqual(
            generate_study_local_identifier(STUDY_HASH),
            CANONICAL_STUDY_ID,
        )

    def test_generate_related_publication_local_identifier_uses_http_uri(self):
        group = [
            {
                "uri": "http://example.org/publication",
                "identifier_agency": "doi",
                "identifier": "10.1234/example",
            }
        ]

        self.assertEqual(
            generate_related_publication_local_identifier(group),
            "http://example.org/publication",
        )

    def test_generate_related_publication_local_identifier_uses_https_uri(self):
        group = [
            {
                "uri": "https://example.org/publication",
                "identifier_agency": "doi",
                "identifier": "10.1234/example",
            }
        ]

        self.assertEqual(
            generate_related_publication_local_identifier(group),
            "https://example.org/publication",
        )

    def test_generate_related_publication_local_identifier_uses_doi_resolver(self):
        group = [
            {
                "identifier_agency": "doi",
                "identifier": "10.1234/example",
            }
        ]

        self.assertEqual(
            generate_related_publication_local_identifier(group),
            "https://doi.org/10.1234/example",
        )

    def test_generate_related_publication_local_identifier_strips_doi(self):
        group = [
            {
                "identifier_agency": " DOI ",
                "identifier": " 10.1234/example ",
            }
        ]

        self.assertEqual(
            generate_related_publication_local_identifier(group),
            "https://doi.org/10.1234/example",
        )

    def test_generate_related_publication_local_identifier_ignores_non_http_uri(self):
        group = [
            {
                "uri": "urn:nbn:fi:tuni-202105124917",
                "related_publication": "Publication title",
                "distribution_date": "2020",
            }
        ]

        identifier = generate_related_publication_local_identifier(group)

        self.assertTrue(identifier.startswith(f"{skg_if_cessda_context}{RELPUB_LOCAL_ID_PREFIX}"))
        self.assertRegex(
            identifier.removeprefix(f"{skg_if_cessda_context}{RELPUB_LOCAL_ID_PREFIX}"),
            r"^[0-9a-f]{24}$",
        )

    def test_generate_related_publication_local_identifier_falls_back_to_hash_identifier(self):
        group = [
            {
                "related_publication": "Publication title",
                "distribution_date": "2020",
            }
        ]

        identifier = generate_related_publication_local_identifier(group)

        self.assertTrue(identifier.startswith(f"{skg_if_cessda_context}{RELPUB_LOCAL_ID_PREFIX}"))
        self.assertRegex(
            identifier.removeprefix(f"{skg_if_cessda_context}{RELPUB_LOCAL_ID_PREFIX}"),
            r"^[0-9a-f]{24}$",
        )


class TestProductIdentifierHelpers(unittest.TestCase):
    def test_extract_study_id_from_canonical_identifier(self):
        self.assertEqual(
            extract_study_id(CANONICAL_STUDY_ID),
            STUDY_HASH,
        )

    def test_extract_study_id_from_prefixed_identifier(self):
        self.assertEqual(
            extract_study_id(f"{STUDY_LOCAL_ID_PREFIX}{STUDY_HASH}"),
            STUDY_HASH,
        )


class TestNormalizeProductLookupIdentifier(unittest.TestCase):
    def test_normalize_product_lookup_identifier_keeps_canonical_study_identifier(self):
        self.assertEqual(
            normalize_product_lookup_identifier(CANONICAL_STUDY_ID),
            CANONICAL_STUDY_ID,
        )

    def test_normalize_product_lookup_identifier_keeps_canonical_related_publication_identifier(self):
        self.assertEqual(
            normalize_product_lookup_identifier(CANONICAL_RELPUB_ID),
            CANONICAL_RELPUB_ID,
        )

    def test_normalize_product_lookup_identifier_unquotes_encoded_canonical_identifier(self):
        encoded = CANONICAL_STUDY_ID.replace(":", "%3A").replace("/", "%2F")

        self.assertEqual(
            normalize_product_lookup_identifier(encoded),
            CANONICAL_STUDY_ID,
        )

    def test_normalize_product_lookup_identifier_fixes_lost_https_slash(self):
        broken = CANONICAL_STUDY_ID.replace("https://", "https:/", 1)

        self.assertEqual(
            normalize_product_lookup_identifier(broken),
            CANONICAL_STUDY_ID,
        )

    def test_normalize_product_lookup_identifier_fixes_lost_http_slash(self):
        identifier = "http:/example.org/product"

        self.assertEqual(
            normalize_product_lookup_identifier(identifier),
            "http://example.org/product",
        )

    def test_normalize_product_lookup_identifier_keeps_raw_study_hash_unchanged(self):
        self.assertEqual(
            normalize_product_lookup_identifier(STUDY_HASH),
            STUDY_HASH,
        )

    def test_normalize_product_lookup_identifier_keeps_raw_study_hash_with_whitespace_unchanged_after_strip(self):
        self.assertEqual(
            normalize_product_lookup_identifier(f"  {STUDY_HASH}  "),
            STUDY_HASH,
        )

    def test_normalize_product_lookup_identifier_converts_raw_related_publication_hash(self):
        self.assertEqual(
            normalize_product_lookup_identifier(RELPUB_HASH),
            CANONICAL_RELPUB_ID,
        )

    def test_normalize_product_lookup_identifier_converts_prefixed_study_identifier(self):
        self.assertEqual(
            normalize_product_lookup_identifier(f"{STUDY_LOCAL_ID_PREFIX}{STUDY_HASH}"),
            CANONICAL_STUDY_ID,
        )

    def test_normalize_product_lookup_identifier_converts_prefixed_related_publication_identifier(self):
        self.assertEqual(
            normalize_product_lookup_identifier(f"{RELPUB_LOCAL_ID_PREFIX}{RELPUB_HASH}"),
            CANONICAL_RELPUB_ID,
        )

    def test_normalize_product_lookup_identifier_keeps_cdc_detail_url_with_raw_study_hash_as_raw_hash(self):
        cdc_url = f"https://datacatalogue.cessda.eu/detail/{STUDY_HASH}"

        with patch(
            "cessda_skgif_api.utils.identifier_utils.product_base_url",
            "https://datacatalogue.cessda.eu/detail",
        ):
            self.assertEqual(
                normalize_product_lookup_identifier(cdc_url),
                STUDY_HASH,
            )

    def test_normalize_product_lookup_identifier_keeps_cdc_detail_url_with_raw_study_hash_and_trailing_slash_as_raw_hash(
        self,
    ):
        cdc_url = f"https://datacatalogue.cessda.eu/detail/{STUDY_HASH}/"

        with patch(
            "cessda_skgif_api.utils.identifier_utils.product_base_url",
            "https://datacatalogue.cessda.eu/detail",
        ):
            self.assertEqual(
                normalize_product_lookup_identifier(cdc_url),
                STUDY_HASH,
            )

    def test_normalize_product_lookup_identifier_keeps_encoded_cdc_detail_url_with_raw_study_hash_as_raw_hash(self):
        cdc_url = f"https%3A%2F%2Fdatacatalogue.cessda.eu%2Fdetail%2F{STUDY_HASH}"

        with patch(
            "cessda_skgif_api.utils.identifier_utils.product_base_url",
            "https://datacatalogue.cessda.eu/detail",
        ):
            self.assertEqual(
                normalize_product_lookup_identifier(cdc_url),
                STUDY_HASH,
            )

    def test_normalize_product_lookup_identifier_converts_cdc_detail_url_with_prefixed_study_identifier(self):
        cdc_url = "https://datacatalogue.cessda.eu/detail/" f"{STUDY_LOCAL_ID_PREFIX}{STUDY_HASH}"

        with patch(
            "cessda_skgif_api.utils.identifier_utils.product_base_url",
            "https://datacatalogue.cessda.eu/detail",
        ):
            self.assertEqual(
                normalize_product_lookup_identifier(cdc_url),
                CANONICAL_STUDY_ID,
            )

    def test_normalize_product_lookup_identifier_converts_cdc_detail_url_with_prefixed_related_publication_identifier(
        self,
    ):
        cdc_url = "https://datacatalogue.cessda.eu/detail/" f"{RELPUB_LOCAL_ID_PREFIX}{RELPUB_HASH}"

        with patch(
            "cessda_skgif_api.utils.identifier_utils.product_base_url",
            "https://datacatalogue.cessda.eu/detail",
        ):
            self.assertEqual(
                normalize_product_lookup_identifier(cdc_url),
                CANONICAL_RELPUB_ID,
            )

    def test_normalize_product_lookup_identifier_keeps_doi_url(self):
        doi = "https://doi.org/10.1234/example"

        self.assertEqual(
            normalize_product_lookup_identifier(doi),
            doi,
        )

    def test_normalize_product_lookup_identifier_keeps_urn(self):
        urn = "URN:NBN:fi:tuni-202105124917"

        self.assertEqual(
            normalize_product_lookup_identifier(urn),
            urn,
        )

    def test_normalize_product_lookup_identifier_keeps_arbitrary_url(self):
        url = "https://example.org/publication"

        self.assertEqual(
            normalize_product_lookup_identifier(url),
            url,
        )

    def test_normalize_product_lookup_identifier_keeps_unknown_value(self):
        value = "not-a-known-product-identifier"

        self.assertEqual(
            normalize_product_lookup_identifier(value),
            value,
        )
