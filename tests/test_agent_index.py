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

from cessda_skgif_api.cache import agent_index
from cessda_skgif_api.cache.agent_index import (
    FILTER_SPECS_ORGANISATIONS,
    FILTER_SPECS_PERSONS,
    AffiliationRef,
    AgentRef,
    BoundClause,
    FilterOp,
    RawClause,
    _clean,
    _extract_identifier,
    _finalize_agent_ref,
    _get_or_create_organisation,
    _get_or_create_person,
    _group_organisation_entries,
    _select_preferred_name_entry,
    bind_clauses,
    build_agent_index,
    determine_agent_type,
    evaluate_clause,
    filter_agent_refs,
    match_agent_ref,
    parse_agent_filter_raw,
    parse_raw_filter_string,
    supported_filter_keys,
)
from cessda_skgif_api.utils.errors import InvalidFilterException


class AsyncCursor:
    """Minimal async iterator representing a MongoDB cursor."""

    def __init__(self, documents):
        self._documents = list(documents)
        self._position = 0

    def __aiter__(self):
        self._position = 0
        return self

    async def __anext__(self):
        if self._position >= len(self._documents):
            raise StopAsyncIteration

        document = self._documents[self._position]
        self._position += 1

        return document


class FakeAgentCollection:
    """MongoDB collection fake used by build_agent_index()."""

    def __init__(self, documents):
        self.documents = list(documents)
        self.find_calls = []

    def find(self, query, projection):
        self.find_calls.append({"query": query, "projection": projection})

        return AsyncCursor(self.documents)


class TestBuildAgentIndex(unittest.IsolatedAsyncioTestCase):
    async def test_build_agent_index_creates_person_with_orcid_and_affiliation(self):
        document = {
            "principal_investigators": [
                {
                    "principal_investigator": "Alice Smith",
                    "organization": "University A",
                    "external_link_title": "orcid",
                    "external_link": "0000-0003-1831-203X",
                    "language": "en",
                }
            ],
            "publishers": [],
            "distributors": [],
        }

        collection = FakeAgentCollection([document])

        with (
            patch.object(agent_index, "STATIC_ORGANISATIONS", []),
            patch.object(agent_index, "ROR_LOOKUP", {}),
        ):
            index = await build_agent_index(collection)

        self.assertEqual(len(index.persons), 1)

        person = index.persons[0]

        self.assertEqual(person.name, "Alice Smith")

        self.assertEqual(person.local_identifier, "https://orcid.org/0000-0003-1831-203X")

        self.assertEqual(person.identifiers, ["0000-0003-1831-203X"])

        self.assertEqual(person.identifier_schemes, ["orcid"])

        self.assertEqual(len(person.affiliations), 1)

        affiliation = person.affiliations[0]

        self.assertEqual(affiliation.name, "University A")

        self.assertEqual(person.affiliation_names, ["University A"])

        self.assertEqual(person.affiliation_roles, ["affiliate"])

        self.assertIn(affiliation.local_identifier, index.organisation_by_id)

        self.assertIs(index.person_by_id[person.local_identifier], person)

        self.assertEqual(
            collection.find_calls,
            [
                {
                    "query": {},
                    "projection": {
                        "principal_investigators": 1,
                        "publishers": 1,
                        "distributors": 1,
                    },
                }
            ],
        )

    async def test_build_agent_index_uses_affiliation_ror_for_person(self):
        document = {
            "principal_investigators": [
                {
                    "principal_investigator": "Alice Smith",
                    "organization": "University A",
                    "external_link_title": "ror",
                    "external_link": "03yrm5c26",
                    "external_link_role": "affiliation-pid",
                    "language": "en",
                }
            ],
            "publishers": [],
            "distributors": [],
        }

        collection = FakeAgentCollection([document])

        with (
            patch.object(agent_index, "STATIC_ORGANISATIONS", []),
            patch.object(agent_index, "ROR_PRIMARY_NAMES", {}),
        ):
            index = await build_agent_index(collection)

        self.assertEqual(len(index.persons), 1)

        self.assertEqual(len(index.organisations), 1)

        person = index.persons[0]
        organisation = index.organisations[0]

        # The ROR belongs to the affiliation, not to the person.
        self.assertEqual(person.identifiers, [])

        self.assertEqual(person.identifier_schemes, [])

        self.assertEqual(organisation.local_identifier, "https://ror.org/03yrm5c26")

        self.assertEqual(organisation.identifiers, ["03yrm5c26"])

        self.assertEqual(organisation.identifier_schemes, ["ror"])

        self.assertEqual(person.affiliations[0].local_identifier, organisation.local_identifier)

    async def test_build_agent_index_creates_direct_organisation_with_ror(self):
        document = {
            "principal_investigators": [
                {
                    "principal_investigator": "University A",
                    "external_link_title": "ror",
                    "external_link": "03yrm5c26",
                    "language": "en",
                }
            ],
            "publishers": [],
            "distributors": [],
        }

        collection = FakeAgentCollection([document])

        with (
            patch.object(agent_index, "STATIC_ORGANISATIONS", []),
            patch.object(agent_index, "ROR_PRIMARY_NAMES", {}),
        ):
            index = await build_agent_index(collection)

        self.assertEqual(index.persons, [])

        self.assertEqual(len(index.organisations), 1)

        organisation = index.organisations[0]

        self.assertEqual(organisation.name, "University A")

        self.assertEqual(organisation.local_identifier, "https://ror.org/03yrm5c26")

        self.assertEqual(organisation.identifiers, ["03yrm5c26"])

        self.assertIs(index.organisation_by_id[organisation.local_identifier], organisation)

    async def test_build_agent_index_creates_organisation_from_organisation_field(self):
        document = {
            "principal_investigators": [{"organization": "University A", "language": "en"}],
            "publishers": [],
            "distributors": [],
        }

        collection = FakeAgentCollection([document])

        with (
            patch.object(agent_index, "STATIC_ORGANISATIONS", []),
            patch.object(agent_index, "ROR_LOOKUP", {}),
        ):
            index = await build_agent_index(collection)

        self.assertEqual(index.persons, [])

        self.assertEqual(len(index.organisations), 1)

        organisation = index.organisations[0]

        self.assertEqual(organisation.name, "University A")

        self.assertEqual(organisation.identifier_schemes, [])

        self.assertTrue(organisation.local_identifier.startswith("https://w3id.org/cessda/"))

    async def test_build_agent_index_excludes_ambiguous_name_only_entry(self):
        document = {
            "principal_investigators": [{"principal_investigator": "Ambiguous Name"}],
            "publishers": [],
            "distributors": [],
        }

        collection = FakeAgentCollection([document])

        with patch.object(agent_index, "STATIC_ORGANISATIONS", []):
            index = await build_agent_index(collection)

        self.assertEqual(index.persons, [])

        self.assertEqual(index.organisations, [])

    async def test_build_agent_index_ignores_invalid_pi_entries(self):
        document = {
            "principal_investigators": [None, "Alice Smith", 123, [], {}],
            "publishers": [],
            "distributors": [],
        }

        collection = FakeAgentCollection([document])

        with patch.object(agent_index, "STATIC_ORGANISATIONS", []):
            index = await build_agent_index(collection)

        self.assertEqual(index.persons, [])

        self.assertEqual(index.organisations, [])

    async def test_build_agent_index_groups_multilingual_publishers(self):
        document = {
            "principal_investigators": [],
            "publishers": [
                {
                    "publisher": "Suomen yliopisto",
                    "language": "fi",
                    "abbreviation": "FU",
                },
                {
                    "publisher": "Finnish University",
                    "language": "en",
                    "abbreviation": "FU",
                    "uri": "https://example.org",
                },
            ],
            "distributors": [],
        }

        collection = FakeAgentCollection([document])

        with (
            patch.object(agent_index, "STATIC_ORGANISATIONS", []),
            patch.object(agent_index, "ROR_LOOKUP", {}),
        ):
            index = await build_agent_index(collection)

        self.assertEqual(len(index.organisations), 1)

        organisation = index.organisations[0]

        self.assertEqual(organisation.name, "Finnish University")

        self.assertEqual(organisation.short_name, "FU")

        self.assertEqual(organisation.website, "https://example.org")

        self.assertEqual(organisation.other_names, ["Suomen yliopisto"])

        self.assertEqual(len(organisation.source_data), 2)

    async def test_build_agent_index_groups_multilingual_distributors(self):
        document = {
            "principal_investigators": [],
            "publishers": [],
            "distributors": [
                {
                    "distributor": "Suomen tietoarkisto",
                    "language": "fi",
                    "abbreviation": "FSD",
                },
                {
                    "distributor": "Finnish Social Science Data Archive",
                    "language": "en",
                    "abbreviation": "FSD",
                    "uri": "https://example.org/fsd",
                },
            ],
        }

        collection = FakeAgentCollection([document])

        with (
            patch.object(agent_index, "STATIC_ORGANISATIONS", []),
            patch.object(agent_index, "ROR_LOOKUP", {}),
        ):
            index = await build_agent_index(collection)

        self.assertEqual(len(index.organisations), 1)

        organisation = index.organisations[0]

        self.assertEqual(organisation.name, "Finnish Social Science Data Archive")

        self.assertEqual(organisation.short_name, "FSD")

        self.assertEqual(organisation.website, "https://example.org/fsd")

        self.assertIn("Suomen tietoarkisto", organisation.other_names)

    async def test_build_agent_index_separates_ambiguous_publishers(self):
        document = {
            "principal_investigators": [],
            "publishers": [
                {"publisher": "First University", "language": "en"},
                {"publisher": "Second University", "language": "en"},
            ],
            "distributors": [],
        }

        collection = FakeAgentCollection([document])

        with (
            patch.object(agent_index, "STATIC_ORGANISATIONS", []),
            patch.object(agent_index, "ROR_LOOKUP", {}),
        ):
            index = await build_agent_index(collection)

        self.assertEqual(len(index.organisations), 2)

        self.assertEqual(
            {organisation.name for organisation in index.organisations},
            {"First University", "Second University"},
        )

    async def test_build_agent_index_uses_ror_alias_lookup_for_affiliation(self):
        organisation_name = "Known University"

        lookup_key = agent_index.normalize_ror_lookup_name(organisation_name)

        document = {
            "principal_investigators": [
                {
                    "principal_investigator": "Alice Smith",
                    "organization": organisation_name,
                    "external_link_title": "orcid",
                    "external_link": "0000-0003-1831-203X",
                    "language": "en",
                }
            ],
            "publishers": [],
            "distributors": [],
        }

        collection = FakeAgentCollection([document])

        with (
            patch.object(agent_index, "STATIC_ORGANISATIONS", []),
            patch.object(agent_index, "ROR_LOOKUP", {lookup_key: "03yrm5c26"}),
            patch.object(agent_index, "ROR_PRIMARY_NAMES", {}),
        ):
            index = await build_agent_index(collection)

        self.assertEqual(len(index.organisations), 1)

        organisation = index.organisations[0]

        self.assertEqual(organisation.local_identifier, "https://ror.org/03yrm5c26")

        self.assertEqual(organisation.identifiers, ["03yrm5c26"])

        self.assertEqual(
            index.persons[0].affiliations[0].local_identifier,
            organisation.local_identifier,
        )

    async def test_build_agent_index_uses_canonical_ror_name(self):
        document = {
            "principal_investigators": [
                {
                    "principal_investigator": "University Alias",
                    "external_link_title": "ror",
                    "external_link": "03yrm5c26",
                    "language": "en",
                }
            ],
            "publishers": [],
            "distributors": [],
        }

        collection = FakeAgentCollection([document])

        with (
            patch.object(agent_index, "STATIC_ORGANISATIONS", []),
            patch.object(agent_index, "ROR_PRIMARY_NAMES", {"03yrm5c26": "Canonical University"}),
        ):
            index = await build_agent_index(collection)

        self.assertEqual(len(index.organisations), 1)

        organisation = index.organisations[0]

        self.assertEqual(organisation.name, "Canonical University")

        self.assertIn("University Alias", organisation.other_names)

    async def test_build_agent_index_deduplicates_person_and_affiliation(self):
        repeated_pi = {
            "principal_investigator": "Alice Smith",
            "organization": "University A",
            "external_link_title": "orcid",
            "external_link": "0000-0003-1831-203X",
            "language": "en",
        }

        collection = FakeAgentCollection(
            [
                {
                    "principal_investigators": [repeated_pi, repeated_pi.copy()],
                    "publishers": [],
                    "distributors": [],
                }
            ]
        )

        with (
            patch.object(agent_index, "STATIC_ORGANISATIONS", []),
            patch.object(agent_index, "ROR_LOOKUP", {}),
        ):
            index = await build_agent_index(collection)

        self.assertEqual(len(index.persons), 1)

        self.assertEqual(len(index.organisations), 1)

        person = index.persons[0]

        self.assertEqual(person.identifiers, ["0000-0003-1831-203X"])

        self.assertEqual(person.identifier_schemes, ["orcid"])

        self.assertEqual(len(person.affiliations), 1)

        self.assertEqual(len(person.affiliation_local_identifiers), 1)

        self.assertEqual(len(person.affiliation_names), 1)

        self.assertEqual(person.affiliation_roles, ["affiliate"])

        # Source records are retained even when the indexed identifiers and
        # affiliations are deduplicated.
        self.assertEqual(len(person.source_data), 2)

    async def test_build_agent_index_refreshes_affiliation_to_canonical_name(self):
        alias_name = "University Alias"
        canonical_name = "Canonical University"

        lookup_key = agent_index.normalize_ror_lookup_name(alias_name)

        document = {
            "principal_investigators": [
                {
                    "principal_investigator": "Alice Smith",
                    "organization": alias_name,
                    "external_link_title": "orcid",
                    "external_link": "0000-0003-1831-203X",
                    "language": "en",
                }
            ],
            "publishers": [],
            "distributors": [],
        }

        collection = FakeAgentCollection([document])

        with (
            patch.object(agent_index, "STATIC_ORGANISATIONS", []),
            patch.object(agent_index, "ROR_LOOKUP", {lookup_key: "03yrm5c26"}),
            patch.object(agent_index, "ROR_PRIMARY_NAMES", {"03yrm5c26": canonical_name}),
        ):
            index = await build_agent_index(collection)

        person = index.persons[0]
        organisation = index.organisations[0]

        self.assertEqual(organisation.name, canonical_name)

        self.assertEqual(person.affiliations[0].name, canonical_name)

        self.assertEqual(person.affiliation_names, [canonical_name])

    async def test_build_agent_index_includes_static_organisations(self):
        collection = FakeAgentCollection([])

        static_organisations = [
            {
                "name": "CESSDA Test Organisation",
                "short_name": "CTO",
                "website": "https://example.org",
                "ror": "03yrm5c26",
            }
        ]

        with (
            patch.object(agent_index, "STATIC_ORGANISATIONS", static_organisations),
            patch.object(agent_index, "ROR_PRIMARY_NAMES", {}),
        ):
            index = await build_agent_index(collection)

        self.assertEqual(index.persons, [])

        self.assertEqual(len(index.organisations), 1)

        organisation = index.organisations[0]

        self.assertEqual(organisation.name, "CESSDA Test Organisation")

        self.assertEqual(organisation.short_name, "CTO")

        self.assertEqual(organisation.website, "https://example.org")

        self.assertEqual(organisation.local_identifier, "https://ror.org/03yrm5c26")

    async def test_build_agent_index_sorts_results_by_normalised_name(self):
        collection = FakeAgentCollection(
            [
                {
                    "principal_investigators": [
                        {
                            "principal_investigator": "Zoe Person",
                            "external_link_title": "orcid",
                            "external_link": "0000-0003-1831-203X",
                        },
                        {
                            "principal_investigator": "Alice Person",
                            "external_link_title": "orcid",
                            "external_link": "0000-0002-1066-6039",
                        },
                    ],
                    "publishers": [
                        {"publisher": "Zulu University", "language": "en"},
                        {"publisher": "Alpha University", "language": "en"},
                    ],
                    "distributors": [],
                }
            ]
        )

        with (
            patch.object(agent_index, "STATIC_ORGANISATIONS", []),
            patch.object(agent_index, "ROR_LOOKUP", {}),
        ):
            index = await build_agent_index(collection)

        self.assertEqual([person.name for person in index.persons], ["Alice Person", "Zoe Person"])

        self.assertEqual(
            [organisation.name for organisation in index.organisations],
            ["Alpha University", "Zulu University"],
        )


class TestAgentHelpers(unittest.TestCase):
    def test_clean_strips_string(self):
        self.assertEqual(_clean("  Alice Smith  "), "Alice Smith")

    def test_clean_returns_empty_for_non_string(self):
        self.assertEqual(_clean(None), "")

        self.assertEqual(_clean(123), "")

        self.assertEqual(_clean({}), "")

    def test_select_preferred_name_entry_prefers_english(self):
        entries = [
            {"language": "fi", "publisher": "Suomen yliopisto"},
            {"language": "en", "publisher": "Finnish University"},
        ]

        result = _select_preferred_name_entry(entries, "publisher")

        self.assertEqual(result["publisher"], "Finnish University")

    def test_select_preferred_name_entry_falls_back_to_first_valid_entry(self):
        entries = [
            {"language": "fi", "publisher": "Suomen yliopisto"},
            {"language": "sv", "publisher": "Finlands universitet"},
        ]

        result = _select_preferred_name_entry(entries, "publisher")

        self.assertEqual(result["publisher"], "Suomen yliopisto")

    def test_select_preferred_name_entry_ignores_empty_names(self):
        entries = [
            {"language": "en", "publisher": ""},
            {"language": "fi", "publisher": "Suomen yliopisto"},
        ]

        result = _select_preferred_name_entry(entries, "publisher")

        self.assertEqual(result["publisher"], "Suomen yliopisto")

    def test_select_preferred_name_entry_returns_none_without_valid_entries(self):
        self.assertIsNone(_select_preferred_name_entry([{"publisher": ""}, {}], "publisher"))


class TestOrganisationGrouping(unittest.TestCase):
    def test_group_organisation_entries_ignores_invalid_entries(self):
        entries = [None, "invalid", {}, {"publisher": ""}]

        self.assertEqual(_group_organisation_entries(entries, "publisher"), [])

    def test_group_organisation_entries_groups_shared_abbreviation(self):
        entries = [
            {"publisher": "Finnish University", "language": "en", "abbreviation": "FU"},
            {"publisher": "Suomen yliopisto", "language": "fi", "abbreviation": "FU"},
        ]

        groups = _group_organisation_entries(entries, "publisher")

        self.assertEqual(len(groups), 1)

        self.assertEqual(len(groups[0]), 2)

    def test_group_organisation_entries_normalises_abbreviation(self):
        entries = [
            {
                "publisher": "Finnish University",
                "language": "en",
                "abbreviation": " FU ",
            },
            {"publisher": "Suomen yliopisto", "language": "fi", "abbreviation": "fu"},
        ]

        groups = _group_organisation_entries(entries, "publisher")

        self.assertEqual(len(groups), 1)

        self.assertEqual(len(groups[0]), 2)

    def test_group_entries_without_abbreviation_by_unique_languages(self):
        entries = [
            {"publisher": "Finnish University", "language": "en"},
            {"publisher": "Suomen yliopisto", "language": "fi"},
        ]

        groups = _group_organisation_entries(entries, "publisher")

        self.assertEqual(len(groups), 1)

        self.assertEqual(groups[0], entries)

    def test_separate_entries_when_language_is_missing(self):
        entries = [
            {"publisher": "First University"},
            {"publisher": "Second University", "language": "fi"},
        ]

        groups = _group_organisation_entries(entries, "publisher")

        self.assertEqual(len(groups), 2)

        self.assertEqual(groups[0], [entries[0]])

        self.assertEqual(groups[1], [entries[1]])

    def test_separate_entries_when_language_is_repeated(self):
        entries = [
            {"publisher": "First University", "language": "en"},
            {"publisher": "Second University", "language": "en"},
        ]

        groups = _group_organisation_entries(entries, "publisher")

        self.assertEqual(len(groups), 2)


class TestDetermineAgentType(unittest.TestCase):
    def test_person_with_organisation_is_person(self):
        result = determine_agent_type({"principal_investigator": "Alice Smith", "organization": "University A"})

        self.assertEqual(result, "person")

    def test_person_with_orcid_is_person(self):
        result = determine_agent_type({"principal_investigator": "Alice Smith", "external_link_title": "orcid"})

        self.assertEqual(result, "person")

    def test_person_with_affiliation_pid_role_is_person(self):
        result = determine_agent_type(
            {
                "principal_investigator": "Alice Smith",
                "external_link_title": "ror",
                "external_link_role": "affiliation-pid",
            }
        )

        self.assertEqual(result, "person")

    def test_organisation_field_without_person_is_organisation(self):
        result = determine_agent_type({"organization": "University A"})

        self.assertEqual(result, "organisation")

    def test_named_entry_with_direct_ror_is_organisation(self):
        result = determine_agent_type({"principal_investigator": "University A", "external_link_title": "ror"})

        self.assertEqual(result, "organisation")

    def test_name_only_entry_is_ambiguous(self):
        result = determine_agent_type({"principal_investigator": "Alice Smith"})

        self.assertIsNone(result)

    def test_empty_entry_is_ambiguous(self):
        self.assertIsNone(determine_agent_type({}))


class TestIdentifierExtraction(unittest.TestCase):
    def test_extract_orcid_identifier(self):
        result = _extract_identifier({"external_link_title": " ORCID ", "external_link": " 0000-0003-1831-203X "})

        self.assertEqual(
            result,
            ("orcid", "0000-0003-1831-203X", "https://orcid.org/0000-0003-1831-203X"),
        )

    def test_extract_ror_identifier(self):
        result = _extract_identifier({"external_link_title": "ror", "external_link": "03yrm5c26"})

        self.assertEqual(result, ("ror", "03yrm5c26", "https://ror.org/03yrm5c26"))

    def test_extract_unknown_identifier_retains_original_value(self):
        result = _extract_identifier({"external_link_title": "doi", "external_link": "10.1234/example"})

        self.assertEqual(result, ("doi", "10.1234/example", ""))

    def test_extract_empty_identifier(self):
        self.assertEqual(_extract_identifier({}), ("", "", ""))


class TestAgentCreation(unittest.TestCase):
    def test_get_or_create_person_creates_person(self):
        persons_by_id = {}

        pi = {
            "principal_investigator": "Alice Smith",
            "external_link_title": "orcid",
            "external_link": "0000-0003-1831-203X",
        }

        person = _get_or_create_person(
            persons_by_id,
            pi=pi,
            name="Alice Smith",
            identifier_value="0000-0003-1831-203X",
            identifier_scheme="orcid",
        )

        self.assertEqual(person.entity_type, "person")

        self.assertEqual(person.name, "Alice Smith")

        self.assertEqual(person.local_identifier, "https://orcid.org/0000-0003-1831-203X")

        self.assertEqual(person.identifiers, ["0000-0003-1831-203X"])

        self.assertEqual(person.identifier_schemes, ["orcid"])

        self.assertEqual(person.source_data, [pi])

        self.assertIs(persons_by_id[person.local_identifier], person)

    def test_get_or_create_person_reuses_existing_person(self):
        persons_by_id = {}

        first_pi = {"principal_investigator": "Alice Smith"}

        second_pi = {"principal_investigator": "Alice Smith", "language": "fi"}

        first = _get_or_create_person(persons_by_id, pi=first_pi, name="Alice Smith")

        second = _get_or_create_person(persons_by_id, pi=second_pi, name="Alice Smith")

        self.assertIs(first, second)

        self.assertEqual(second.source_data, [first_pi, second_pi])

    def test_get_or_create_organisation_creates_generated_identifier(self):
        organisations_by_id = {}

        organisation = _get_or_create_organisation(
            organisations_by_id,
            name="University A",
            short_name="UA",
            website="https://example.org",
        )

        self.assertEqual(organisation.entity_type, "organisation")

        self.assertEqual(organisation.name, "University A")

        self.assertEqual(organisation.short_name, "UA")

        self.assertEqual(organisation.website, "https://example.org")

        self.assertTrue(organisation.local_identifier.startswith("https://w3id.org/cessda/"))

    def test_get_or_create_organisation_uses_ror(self):
        organisations_by_id = {}

        organisation = _get_or_create_organisation(
            organisations_by_id,
            name="University A",
            identifier_value="03yrm5c26",
            identifier_scheme="ror",
        )

        self.assertEqual(organisation.local_identifier, "https://ror.org/03yrm5c26")

        self.assertEqual(organisation.identifiers, ["03yrm5c26"])

        self.assertEqual(organisation.identifier_schemes, ["ror"])

    def test_get_or_create_organisation_prefers_english_name(self):
        organisations_by_id = {}

        local_identifier = "organisation:test"

        organisation = _get_or_create_organisation(
            organisations_by_id,
            local_identifier=local_identifier,
            name="Suomen yliopisto",
            language="fi",
        )

        updated = _get_or_create_organisation(
            organisations_by_id,
            local_identifier=local_identifier,
            name="Finnish University",
            language="en",
        )

        self.assertIs(organisation, updated)

        self.assertEqual(updated.name, "Finnish University")

        self.assertIn("Suomen yliopisto", updated.other_names)

    def test_get_or_create_organisation_retains_non_english_name_as_alias(self):
        organisations_by_id = {}

        local_identifier = "organisation:test"

        organisation = _get_or_create_organisation(
            organisations_by_id,
            local_identifier=local_identifier,
            name="Finnish University",
            language="en",
        )

        updated = _get_or_create_organisation(
            organisations_by_id,
            local_identifier=local_identifier,
            name="Suomen yliopisto",
            language="fi",
        )

        self.assertEqual(updated.name, "Finnish University")

        self.assertIn("Suomen yliopisto", updated.other_names)

        self.assertIs(organisation, updated)

    def test_get_or_create_organisation_only_sets_missing_optional_values(self):
        organisations_by_id = {}

        organisation = _get_or_create_organisation(
            organisations_by_id,
            local_identifier="organisation:test",
            name="University A",
            short_name="UA",
            website="https://first.example.org",
        )

        updated = _get_or_create_organisation(
            organisations_by_id,
            local_identifier="organisation:test",
            name="University A",
            short_name="OTHER",
            website="https://second.example.org",
        )

        self.assertIs(organisation, updated)

        self.assertEqual(updated.short_name, "UA")

        self.assertEqual(updated.website, "https://first.example.org")


class TestFinalizeAgentRef(unittest.TestCase):
    def test_finalize_agent_ref_deduplicates_data(self):
        ref = AgentRef(
            local_identifier="person:1",
            entity_type="person",
            name="Alice Smith",
            identifiers=["0000-0003-1831-203X", "0000-0003-1831-203X"],
            identifier_schemes=["orcid", "orcid"],
            affiliations=[
                AffiliationRef(local_identifier="organisation:1", name="University A"),
                AffiliationRef(local_identifier="organisation:1", name="University A"),
            ],
            affiliation_local_identifiers=["organisation:1", "organisation:1"],
            affiliation_names=["University A", "University A"],
            affiliation_roles=["affiliate", "affiliate"],
            other_names=["Alice Smith", "A. Smith", "A. Smith", ""],
        )

        _finalize_agent_ref(ref)

        self.assertEqual(ref.identifiers, ["0000-0003-1831-203X"])

        self.assertEqual(ref.identifier_schemes, ["orcid"])

        self.assertEqual(len(ref.affiliations), 1)

        self.assertEqual(ref.affiliation_local_identifiers, ["organisation:1"])

        self.assertEqual(ref.affiliation_names, ["University A"])

        self.assertEqual(ref.affiliation_roles, ["affiliate"])

        self.assertEqual(ref.other_names, ["A. Smith"])


class TestFilterParsing(unittest.TestCase):
    def test_supported_filter_keys(self):
        result = supported_filter_keys(
            {
                "name": FILTER_SPECS_PERSONS["name"],
                "identifiers.id": FILTER_SPECS_PERSONS["identifiers.id"],
            }
        )

        self.assertEqual(result, "name, identifiers.id")

    def test_parse_raw_filter_string_none_returns_empty(self):
        self.assertEqual(parse_raw_filter_string(None), [])

    def test_parse_raw_filter_string_empty_returns_empty(self):
        self.assertEqual(parse_raw_filter_string(""), [])

    def test_parse_raw_filter_string_single_clause(self):
        clauses = parse_raw_filter_string("name:Alice Smith")

        self.assertEqual(clauses, [RawClause(key="name", value="Alice Smith")])

    def test_parse_raw_filter_string_multiple_clauses(self):
        clauses = parse_raw_filter_string("name:Alice,identifiers.scheme:orcid")

        self.assertEqual(len(clauses), 2)

        self.assertEqual(clauses[0], RawClause(key="name", value="Alice"))

        self.assertEqual(clauses[1], RawClause(key="identifiers.scheme", value="orcid"))

    def test_parse_raw_filter_string_decodes_url_encoding(self):
        clauses = parse_raw_filter_string("name:Alice%20Smith")

        self.assertEqual(clauses[0].value, "Alice Smith")

    def test_parse_raw_filter_string_missing_colon(self):
        with self.assertRaises(InvalidFilterException):
            parse_raw_filter_string("invalid-filter")

    def test_parse_raw_filter_string_empty_key(self):
        with self.assertRaises(InvalidFilterException):
            parse_raw_filter_string(":value")

    def test_parse_raw_filter_string_empty_value(self):
        with self.assertRaises(InvalidFilterException):
            parse_raw_filter_string("name:")

    def test_bind_person_filter(self):
        clauses = bind_clauses([RawClause(key="name", value="Alice")], FILTER_SPECS_PERSONS)

        self.assertEqual(
            clauses,
            [
                BoundClause(
                    key="name",
                    op=FilterOp.CONTAINS,
                    value="Alice",
                    extractor_name="name",
                )
            ],
        )

    def test_bind_disallowed_filter(self):
        with self.assertRaises(InvalidFilterException):
            bind_clauses([RawClause(key="family_name", value="Smith")], FILTER_SPECS_PERSONS)

    def test_bind_unknown_filter(self):
        with self.assertRaises(InvalidFilterException):
            bind_clauses([RawClause(key="unknown", value="value")], FILTER_SPECS_PERSONS)

    def test_parse_agent_filter_raw(self):
        clauses = parse_agent_filter_raw("name:Alice,identifiers.scheme:orcid", FILTER_SPECS_PERSONS)

        self.assertEqual(len(clauses), 2)

        self.assertEqual(clauses[0].key, "name")

        self.assertEqual(clauses[1].key, "identifiers.scheme")


class TestFilterEvaluation(unittest.TestCase):
    def setUp(self):
        self.person = AgentRef(
            local_identifier="https://orcid.org/0000-0003-1831-203X",
            entity_type="person",
            name="Alice Jane Smith",
            identifiers=["0000-0003-1831-203X"],
            identifier_schemes=["orcid"],
            affiliations=[AffiliationRef(local_identifier="organisation:1", name="University A")],
            affiliation_local_identifiers=["organisation:1"],
            affiliation_names=["University A"],
            affiliation_roles=["affiliate"],
        )

        self.organisation = AgentRef(
            local_identifier="https://ror.org/03yrm5c26",
            entity_type="organisation",
            name="University A",
            short_name="UA",
            website="https://example.org",
            identifiers=["03yrm5c26"],
            identifier_schemes=["ror"],
            other_names=["Former University Name"],
        )

    def test_wildcard_matches_existing_attribute(self):
        clause = BoundClause(
            key="identifiers.scheme",
            op=FilterOp.EXACT,
            value="*",
            extractor_name="identifier_schemes",
        )

        self.assertTrue(evaluate_clause(self.person, clause))

    def test_wildcard_does_not_match_missing_attribute(self):
        ref = AgentRef(local_identifier="person:1", entity_type="person", name="Alice")

        clause = BoundClause(
            key="identifiers.scheme",
            op=FilterOp.EXACT,
            value="*",
            extractor_name="identifier_schemes",
        )

        self.assertFalse(evaluate_clause(ref, clause))

    def test_name_contains_filter(self):
        clause = BoundClause(key="name", op=FilterOp.CONTAINS, value="Smith Alice", extractor_name="name")

        self.assertTrue(evaluate_clause(self.person, clause))

    def test_affiliation_name_contains_filter(self):
        clause = BoundClause(
            key="affiliations.affiliation.name",
            op=FilterOp.CONTAINS,
            value="University",
            extractor_name="affiliation_names",
        )

        self.assertTrue(evaluate_clause(self.person, clause))

    def test_identifier_exact_filter(self):
        clause = BoundClause(
            key="identifiers.id",
            op=FilterOp.EXACT,
            value="https://orcid.org/0000-0003-1831-203X",
            extractor_name="identifiers",
        )

        self.assertTrue(evaluate_clause(self.person, clause))

    def test_affiliation_identifier_exact_filter(self):
        clause = BoundClause(
            key="affiliations.affiliation.local_identifier",
            op=FilterOp.EXACT,
            value="organisation:1",
            extractor_name="affiliation_local_identifiers",
        )

        self.assertTrue(evaluate_clause(self.person, clause))

    def test_identifier_scheme_exact_filter(self):
        clause = BoundClause(
            key="identifiers.scheme",
            op=FilterOp.EXACT,
            value="orcid",
            extractor_name="identifier_schemes",
        )

        self.assertTrue(evaluate_clause(self.person, clause))

    def test_search_names_include_other_names(self):
        clause = BoundClause(
            key="cf.search.name",
            op=FilterOp.CONTAINS,
            value="Former University",
            extractor_name="search_names",
        )

        self.assertTrue(evaluate_clause(self.organisation, clause))

    def test_unknown_operation_returns_false(self):
        clause = BoundClause(key="name", op="unsupported", value="Alice", extractor_name="name")

        self.assertFalse(evaluate_clause(self.person, clause))

    def test_match_agent_ref_and_semantics(self):
        clauses = [
            BoundClause(key="name", op=FilterOp.CONTAINS, value="Alice", extractor_name="name"),
            BoundClause(
                key="identifiers.scheme",
                op=FilterOp.EXACT,
                value="orcid",
                extractor_name="identifier_schemes",
            ),
        ]

        self.assertTrue(match_agent_ref(self.person, clauses))

    def test_match_agent_ref_fails_if_one_clause_fails(self):
        clauses = [
            BoundClause(key="name", op=FilterOp.CONTAINS, value="Alice", extractor_name="name"),
            BoundClause(
                key="affiliations.role",
                op=FilterOp.EXACT,
                value="member",
                extractor_name="affiliation_roles",
            ),
        ]

        self.assertFalse(match_agent_ref(self.person, clauses))

    def test_filter_agent_refs_without_clauses_returns_original_list(self):
        refs = [self.person, self.organisation]

        result = filter_agent_refs(refs, [])

        self.assertIs(result, refs)

    def test_filter_agent_refs_returns_matching_refs(self):
        refs = [self.person, self.organisation]

        clauses = [
            BoundClause(
                key="identifiers.scheme",
                op=FilterOp.EXACT,
                value="orcid",
                extractor_name="identifier_schemes",
            )
        ]

        result = filter_agent_refs(refs, clauses)

        self.assertEqual(result, [self.person])

    def test_organisation_filter_spec_can_be_bound(self):
        clauses = bind_clauses([RawClause(key="website", value="example.org")], FILTER_SPECS_ORGANISATIONS)

        self.assertEqual(clauses[0].extractor_name, "website")
