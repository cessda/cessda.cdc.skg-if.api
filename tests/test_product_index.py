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
from cessda_skgif_api.cache.product_index import (
    BoundClause,
    FilterOp,
    ProductRef,
    _contains_name_match,
    build_related_publication_ref,
    build_study_product_ref,
    evaluate_clause,
    group_related_publications,
    parse_product_filter_raw,
)
from cessda_skgif_api.utils.errors import InvalidFilterException


class TestGrouping(unittest.TestCase):
    def test_group_related_publications_groups_languages_together(self):
        pubs = [
            {
                "identifier_agency": "doi",
                "identifier": "10.1234/test",
                "language": "en",
                "related_publication": "English",
            },
            {
                "identifier_agency": "doi",
                "identifier": "10.1234/test",
                "language": "fi",
                "related_publication": "Finnish",
            },
        ]

        groups = group_related_publications(pubs)

        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 2)

    def test_group_related_publications_ignores_empty_entries(self):
        pubs = [
            {},
            {
                "related_publication": "",
                "description": "",
                "identifier": "",
                "uri": "",
            },
        ]

        groups = group_related_publications(pubs)

        self.assertEqual(groups, [])


class TestRelatedPublicationRefs(unittest.TestCase):
    def test_build_related_publication_ref_uses_doi_identifier(self):
        group = [
            {
                "identifier_agency": "doi",
                "identifier": "10.1234/test",
                "related_publication": "Publication",
                "distribution_date": "2020",
            }
        ]

        ref = build_related_publication_ref(group)

        self.assertEqual(
            ref.product_id,
            "https://doi.org/10.1234/test",
        )

        self.assertEqual(
            ref.product_type,
            "literature",
        )


class TestStudyRefs(unittest.TestCase):
    def test_build_study_product_ref_extracts_orcid(self):
        doc = {
            "_aggregator_identifier": "ABC123",
            "principal_investigators": [
                {
                    "principal_investigator": "Alice",
                    "external_link": "0000-0003-1831-203X",
                    "external_link_title": "orcid",
                }
            ],
        }

        ref = build_study_product_ref(doc)

        self.assertEqual(
            ref.contribution_orcids,
            ["0000-0003-1831-203X"],
        )

    def test_build_study_product_ref_extracts_ror_affiliation(self):
        doc = {
            "_aggregator_identifier": "ABC123",
            "principal_investigators": [
                {
                    "organization": "University",
                    "external_link": "03yrm5c26",
                    "external_link_title": "ror",
                    "external_link_role": "affiliation-pid",
                }
            ],
        }

        ref = build_study_product_ref(doc)

        self.assertEqual(
            ref.contribution_aff_rors,
            ["03yrm5c26"],
        )


class TestFiltering(unittest.TestCase):
    def test_contains_name_match_handles_name_order(self):
        self.assertTrue(
            _contains_name_match(
                ["Alice Smith"],
                "Smith Alice",
            )
        )

    def test_contains_name_match_partial_name(self):
        self.assertTrue(
            _contains_name_match(
                ["Alice Jane Smith"],
                "Alice Smith",
            )
        )

    def test_parse_product_filter_raw(self):
        clauses = parse_product_filter_raw("product_type:literature")

        self.assertEqual(len(clauses), 1)
        self.assertEqual(
            clauses[0].key,
            "product_type",
        )

    def test_parse_product_filter_unsupported(self):
        with self.assertRaises(InvalidFilterException):
            parse_product_filter_raw("foo:bar")

    def test_cf_cites_filter_matches(self):
        ref = ProductRef(
            product_id="pub",
            product_type="literature",
            cited_studies=["https://w3id.org/cessda/cessda_product_research_data_abc"],
        )

        clause = BoundClause(
            key="cf.cites",
            op=FilterOp.EXACT,
            value="https://w3id.org/cessda/cessda_product_research_data_abc",
            extractor_name="cited_studies",
        )

        self.assertTrue(
            evaluate_clause(
                ref,
                clause,
            )
        )
