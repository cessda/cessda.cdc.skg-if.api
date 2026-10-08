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

"""Transform indexed Person references into SKG-IF Persons."""

from cessda_skgif_api.cache.agent_index import AgentRef
from cessda_skgif_api.models.skgif import (
    Affiliation,
    Identifier,
    OrganisationLite,
    Person,
)


def transform_agent_ref_to_person(
    ref: AgentRef,
) -> Person:
    if ref.entity_type != "person":
        raise ValueError(f"Cannot transform {ref.entity_type!r} AgentRef into Person")

    identifiers = [
        Identifier(
            scheme=scheme,
            value=value,
        )
        for scheme, value in zip(
            ref.identifier_schemes,
            ref.identifiers,
        )
    ]

    affiliations = [
        Affiliation(
            affiliation=OrganisationLite(
                local_identifier=aff.local_identifier,
                name=aff.name,
            )
        )
        for aff in ref.affiliations
    ]

    return Person(
        local_identifier=ref.local_identifier,
        name=ref.name or None,
        identifiers=identifiers or None,
        affiliations=affiliations or None,
    )
