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

from cessda_skgif_api.transformers.organisation_transformer import (
    transform_agent_ref_to_organisation,
)
from cessda_skgif_api.transformers.person_transformer import (
    transform_agent_ref_to_person,
)


class DummyAffiliation:
    def __init__(self, local_identifier, name):
        self.local_identifier = local_identifier
        self.name = name


class DummyAgentRef:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TestPersonTransformer(unittest.TestCase):
    def test_transform_person_with_identifiers_and_affiliations(self):

        ref = DummyAgentRef(
            entity_type="person",
            local_identifier="person:1",
            name="Alice Smith",
            identifier_schemes=["orcid"],
            identifiers=["0000-0001-2345-6789"],
            affiliations=[DummyAffiliation(local_identifier="org:1", name="University A")],
        )

        person = transform_agent_ref_to_person(ref)

        self.assertEqual(person.local_identifier, "person:1")

        self.assertEqual(person.name, "Alice Smith")

        self.assertEqual(len(person.identifiers), 1)

        self.assertEqual(person.identifiers[0].scheme, "orcid")

        self.assertEqual(person.identifiers[0].value, "0000-0001-2345-6789")

        self.assertEqual(len(person.affiliations), 1)

        self.assertEqual(person.affiliations[0].affiliation.local_identifier, "org:1")

        self.assertEqual(person.affiliations[0].affiliation.name, "University A")

    def test_transform_person_without_optional_values(self):

        ref = DummyAgentRef(
            entity_type="person",
            local_identifier="person:1",
            name="",
            identifier_schemes=[],
            identifiers=[],
            affiliations=[],
        )

        person = transform_agent_ref_to_person(ref)

        self.assertIsNone(person.name)

        self.assertIsNone(person.identifiers)

        self.assertIsNone(person.affiliations)

    def test_transform_person_rejects_non_person(self):

        ref = DummyAgentRef(
            entity_type="organisation",
            local_identifier="org:1",
            name="University A",
            identifier_schemes=[],
            identifiers=[],
            affiliations=[],
        )

        with self.assertRaises(ValueError) as context:
            transform_agent_ref_to_person(ref)

        self.assertIn("organisation", str(context.exception))


class TestOrganisationTransformer(unittest.TestCase):
    def test_transform_organisation_full(self):

        ref = DummyAgentRef(
            entity_type="organisation",
            local_identifier="org:1",
            name="University A",
            short_name="UA",
            website="https://example.org",
            identifier_schemes=["ror"],
            identifiers=["01abc1234"],
            other_names=["Old University A"],
        )

        organisation = transform_agent_ref_to_organisation(ref)

        self.assertEqual(organisation.local_identifier, "org:1")

        self.assertEqual(organisation.name, "University A")

        self.assertEqual(organisation.short_name, "UA")

        self.assertEqual(organisation.website, "https://example.org")

        self.assertEqual(organisation.identifiers[0].scheme, "ror")

        self.assertEqual(organisation.identifiers[0].value, "01abc1234")

        self.assertEqual(organisation.other_names, ["Old University A"])

    def test_transform_organisation_without_optional_values(self):

        ref = DummyAgentRef(
            entity_type="organisation",
            local_identifier="org:1",
            name="University A",
            short_name="",
            website="",
            identifier_schemes=[],
            identifiers=[],
            other_names=[],
        )

        organisation = transform_agent_ref_to_organisation(ref)

        self.assertIsNone(organisation.short_name)

        self.assertIsNone(organisation.website)

        self.assertIsNone(organisation.identifiers)

        self.assertIsNone(organisation.other_names)

    def test_transform_organisation_rejects_non_organisation(self):

        ref = DummyAgentRef(
            entity_type="person",
            local_identifier="person:1",
            name="Alice Smith",
            short_name="",
            website="",
            identifier_schemes=[],
            identifiers=[],
            other_names=[],
        )

        with self.assertRaises(ValueError) as context:
            transform_agent_ref_to_organisation(ref)

        self.assertIn("person", str(context.exception))
