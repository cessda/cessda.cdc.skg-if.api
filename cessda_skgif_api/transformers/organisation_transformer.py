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

"""Transform indexed Organisation references into SKG-IF Organisations."""

from cessda_skgif_api.cache.agent_index import AgentRef
from cessda_skgif_api.models.skgif import (
    Identifier,
    Organisation,
)


def transform_agent_ref_to_organisation(
    ref: AgentRef,
) -> Organisation:
    if ref.entity_type != "organisation":
        raise ValueError(
            f"Cannot transform {ref.entity_type!r} AgentRef into Organisation"
        )

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

    return Organisation(
        local_identifier=ref.local_identifier,
        name=ref.name,
        short_name=ref.short_name or None,
        website=ref.website or None,
        identifiers=identifiers or None,
        other_names=ref.other_names or None,
    )
