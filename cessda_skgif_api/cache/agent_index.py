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

"""Flattened in-memory index for SKG-IF Persons and Organisations"""

import logging
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from cessda_skgif_api.cache.product_index import _contains_match, _contains_name_match, _exact_match
from cessda_skgif_api.utils.constants import ROR_LOOKUP, ROR_PRIMARY_NAMES, STATIC_ORGANISATIONS
from cessda_skgif_api.utils.errors import InvalidFilterException
from cessda_skgif_api.utils.helpers import dedupe_preserve_order, normalize_ror_lookup_name, normalize_text
from cessda_skgif_api.utils.identifier_utils import (
    generate_person_local_identifier,
    normalize_agent_lookup_identifier,
    normalize_pid_url,
    resolve_organisation_local_identifier,
)

_logger = logging.getLogger(__name__)


IDENTIFIERS_ID = "identifiers.id"
IDENTIFIERS_SCHEME = "identifiers.scheme"

AFFILIATION_LOCAL_IDENTIFIER = "affiliations.affiliation.local_identifier"
AFFILIATION_NAME = "affiliations.affiliation.name"

SEARCH_NAME = "cf.search.name"


@dataclass(slots=True)
class AffiliationRef:
    local_identifier: str
    name: str


@dataclass(slots=True)
class AgentRef:
    local_identifier: str
    entity_type: str
    name: str

    short_name: str | None = None
    website: str | None = None

    identifiers: list[str] = field(default_factory=list)
    identifier_schemes: list[str] = field(default_factory=list)

    affiliations: list[AffiliationRef] = field(default_factory=list)

    affiliation_local_identifiers: list[str] = field(default_factory=list)
    affiliation_names: list[str] = field(default_factory=list)
    affiliation_roles: list[str] = field(default_factory=list)

    other_names: list[str] = field(default_factory=list)

    source_data: list[dict[str, Any]] = field(default_factory=list)

    sort_name: str = ""


@dataclass(slots=True)
class AgentIndex:
    persons: list[AgentRef]
    organisations: list[AgentRef]

    person_by_id: dict[str, AgentRef]
    organisation_by_id: dict[str, AgentRef]


def _clean(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    return value.strip()


def _select_preferred_name_entry(entries: list[dict[str, Any]], name_field: str) -> dict[str, Any] | None:
    valid_entries = [entry for entry in entries if _clean(entry.get(name_field))]

    if not valid_entries:
        return None

    return next((entry for entry in valid_entries if _clean(entry.get("language")).lower() == "en"), valid_entries[0])


def _group_organisation_entries(entries: list[dict[str, Any]], name_field: str) -> list[list[dict[str, Any]]]:
    """
    Group multilingual publisher or distributor entries.

    Entries sharing an abbreviation are grouped together.

    Entries without an abbreviation are grouped as multilingual variants only
    when every entry has a non-empty, unique language. If a language is missing
    or occurs more than once, the entries are treated as separate organisations
    because their relationship is ambiguous.
    """
    valid_entries = [entry for entry in entries or [] if isinstance(entry, dict) and _clean(entry.get(name_field))]

    if not valid_entries:
        return []

    groups: list[list[dict[str, Any]]] = []

    abbreviation_groups: dict[str, list[dict[str, Any]]] = {}
    no_abbreviation_entries: list[dict[str, Any]] = []

    for entry in valid_entries:
        abbreviation = normalize_text(_clean(entry.get("abbreviation")))

        if abbreviation:
            abbreviation_groups.setdefault(abbreviation, []).append(entry)
        else:
            no_abbreviation_entries.append(entry)

    groups.extend(abbreviation_groups.values())

    if no_abbreviation_entries:
        languages = [_clean(entry.get("language")).lower() for entry in no_abbreviation_entries]

        has_unique_languages = all(languages) and len(languages) == len(set(languages))

        if has_unique_languages:
            groups.append(no_abbreviation_entries)
        else:
            groups.extend([entry] for entry in no_abbreviation_entries)

    return groups


def _find_ror_id(group: list[dict[str, Any]], name_field: str) -> str | None:
    """Return the first ROR identifier matching an organisation name."""
    for entry in group:
        candidate = _clean(entry.get(name_field))
        ror_id = ROR_LOOKUP.get(normalize_ror_lookup_name(candidate))

        if ror_id:
            return ror_id

    return None


def _get_other_organisation_names(
    group: list[dict[str, Any]],
    name_field: str,
    preferred_name: str,
) -> list[str]:
    """Return unique organisation names excluding the preferred name."""
    normalized_preferred_name = normalize_text(preferred_name)

    return dedupe_preserve_order(
        name
        for entry in group
        if (name := _clean(entry.get(name_field))) and normalize_text(name) != normalized_preferred_name
    )


def _index_organisation_source(
    organisations_by_id: dict[str, AgentRef],
    entries: list[dict[str, Any]],
    *,
    name_field: str,
) -> None:
    for group in _group_organisation_entries(entries, name_field):
        preferred_entry = _select_preferred_name_entry(group, name_field)

        if preferred_entry is None:
            continue

        preferred_name = _clean(preferred_entry.get(name_field))
        preferred_language = _clean(preferred_entry.get("language")).lower()

        ror_id = _find_ror_id(group, name_field)

        short_name = next(
            (_clean(entry.get("abbreviation")) for entry in group if _clean(entry.get("abbreviation"))),
            "",
        )

        website = next(
            (_clean(entry.get("uri")) for entry in group if _clean(entry.get("uri"))),
            "",
        )

        other_names = _get_other_organisation_names(
            group,
            name_field,
            preferred_name,
        )

        organisation = _get_or_create_organisation(
            organisations_by_id,
            name=preferred_name,
            language=preferred_language,
            identifier_value=ror_id or "",
            identifier_scheme="ror" if ror_id else "",
            source_data=preferred_entry,
            other_names=other_names,
            short_name=short_name or None,
            website=website or None,
        )

        for entry in group:
            if entry is preferred_entry:
                continue

            organisation.source_data.append(entry)


def _extract_identifier(pi: dict[str, Any]) -> tuple[str, str, str]:
    """
    Return scheme, original value and canonical PID URL.
    """
    scheme = _clean(pi.get("external_link_title")).lower()
    value = _clean(pi.get("external_link"))

    canonical_url = normalize_pid_url(scheme, value) if scheme and value else None

    return scheme, value, canonical_url or ""


def determine_agent_type(pi: dict[str, Any]) -> str | None:
    """
    Determine whether a principal-investigator entry represents a Person
    or an Organisation.

    Returns None when the available data is genuinely ambiguous.
    """
    person_name = _clean(pi.get("principal_investigator"))
    organisation_name = _clean(pi.get("organization"))

    scheme = _clean(pi.get("external_link_title")).lower()
    role = _clean(pi.get("external_link_role")).lower()

    # A named PI with an affiliation or ORCID is treated as a Person.
    if person_name and (organisation_name or scheme == "orcid" or role == "affiliation-pid"):
        return "person"

    # An organisation field without a person name is explicit enough.
    if organisation_name and not person_name:
        return "organisation"

    # A ROR attached directly to a named entry indicates an organisation.
    if person_name and scheme == "ror" and role != "affiliation-pid":
        return "organisation"

    # Name-only entries remain generic Agents and are excluded.
    return None


def _append_other_name(organisation: AgentRef, other_name: str | None) -> None:
    """Append a non-empty name when it differs from the preferred name."""
    if not other_name:
        return

    if normalize_text(other_name) == normalize_text(organisation.name):
        return

    organisation.other_names.append(other_name)


def _create_or_update_organisation(
    organisations_by_id: dict[str, AgentRef],
    *,
    local_identifier: str,
    name: str,
    language: str,
    canonical_name: str | None,
    short_name: str | None,
    website: str | None,
) -> AgentRef:
    """Create an organisation or update its preferred name."""
    organisation = organisations_by_id.get(local_identifier)

    if organisation is None:
        organisation = AgentRef(
            local_identifier=local_identifier,
            entity_type="organisation",
            name=name,
            short_name=short_name,
            website=website,
            sort_name=normalize_text(name),
        )
        organisations_by_id[local_identifier] = organisation
        return organisation

    if language == "en" and not canonical_name:
        previous_name = organisation.name

        if previous_name and normalize_text(previous_name) != normalize_text(name):
            organisation.other_names.append(previous_name)

        organisation.name = name
        organisation.sort_name = normalize_text(name)
    else:
        _append_other_name(organisation, name)

    return organisation


def _merge_organisation_metadata(
    organisation: AgentRef,
    *,
    incoming_name: str,
    other_names: list[str] | None,
    short_name: str | None,
    website: str | None,
    identifier_value: str,
    identifier_scheme: str,
    source_data: dict[str, Any] | None,
) -> None:
    """Merge supplementary metadata into an existing organisation."""
    _append_other_name(organisation, incoming_name)

    for other_name in other_names or []:
        _append_other_name(organisation, other_name)

    if short_name and not organisation.short_name:
        organisation.short_name = short_name

    if website and not organisation.website:
        organisation.website = website

    if identifier_value and identifier_scheme:
        organisation.identifiers.append(identifier_value)
        organisation.identifier_schemes.append(identifier_scheme)

    if source_data:
        organisation.source_data.append(source_data)


def _get_or_create_organisation(
    organisations_by_id: dict[str, AgentRef],
    *,
    name: str,
    language: str = "",
    identifier_value: str = "",
    identifier_scheme: str = "",
    short_name: str | None = None,
    website: str | None = None,
    source_data: dict[str, Any] | None = None,
    local_identifier: str | None = None,
    other_names: list[str] | None = None,
) -> AgentRef:
    """Return an organisation after creating or updating its indexed metadata."""
    ror_value = identifier_value if identifier_scheme == "ror" else None

    if local_identifier is None:
        local_identifier = resolve_organisation_local_identifier(
            name=name,
            ror=ror_value,
        )

    incoming_name = name
    canonical_name = ROR_PRIMARY_NAMES.get(ror_value) if ror_value else None
    preferred_name = canonical_name or name

    organisation = _create_or_update_organisation(
        organisations_by_id,
        local_identifier=local_identifier,
        name=preferred_name,
        language=language,
        canonical_name=canonical_name,
        short_name=short_name,
        website=website,
    )

    _merge_organisation_metadata(
        organisation,
        incoming_name=incoming_name,
        other_names=other_names,
        short_name=short_name,
        website=website,
        identifier_value=identifier_value,
        identifier_scheme=identifier_scheme,
        source_data=source_data,
    )

    return organisation


def _get_or_create_person(
    persons_by_id: dict[str, AgentRef],
    *,
    pi: dict[str, Any],
    name: str,
    identifier_value: str = "",
    identifier_scheme: str = "",
) -> AgentRef:
    orcid_value = identifier_value if identifier_scheme == "orcid" else None

    local_identifier = generate_person_local_identifier(name=name, orcid=orcid_value)

    person = persons_by_id.get(local_identifier)

    if person is None:
        person = AgentRef(
            local_identifier=local_identifier, entity_type="person", name=name, sort_name=normalize_text(name)
        )
        persons_by_id[local_identifier] = person

    if identifier_value and identifier_scheme:
        person.identifiers.append(identifier_value)
        person.identifier_schemes.append(identifier_scheme)

    person.source_data.append(pi)

    return person


def _finalize_agent_ref(ref: AgentRef) -> None:
    identifier_pairs = dedupe_preserve_order(zip(ref.identifier_schemes, ref.identifiers))

    ref.identifier_schemes = [scheme for scheme, _ in identifier_pairs]
    ref.identifiers = [value for _, value in identifier_pairs]

    seen = set()
    deduped_affiliations = []

    for affiliation in ref.affiliations:
        key = affiliation.local_identifier

        if key in seen:
            continue

        seen.add(key)
        deduped_affiliations.append(affiliation)

    ref.affiliations = deduped_affiliations

    ref.affiliation_local_identifiers = dedupe_preserve_order(ref.affiliation_local_identifiers)

    ref.affiliation_names = dedupe_preserve_order(ref.affiliation_names)

    ref.affiliation_roles = dedupe_preserve_order(ref.affiliation_roles)

    ref.other_names = dedupe_preserve_order(
        name for name in ref.other_names if name and normalize_text(name) != normalize_text(ref.name)
    )


def _index_static_organisations(organisations_by_id: dict[str, AgentRef]) -> None:
    """Add configured static organisations to the organisation index."""
    for organisation_data in STATIC_ORGANISATIONS:
        ror_id = organisation_data.get("ror", "")

        _get_or_create_organisation(
            organisations_by_id,
            name=organisation_data["name"],
            short_name=organisation_data.get("short_name"),
            website=organisation_data.get("website"),
            identifier_value=ror_id,
            identifier_scheme="ror" if ror_id else "",
        )


def _add_person_affiliation(person: AgentRef, organisation: AgentRef) -> None:
    """Add an organisation affiliation to a person."""
    person.affiliations.append(
        AffiliationRef(
            local_identifier=organisation.local_identifier,
            name=organisation.name,
        )
    )
    person.affiliation_local_identifiers.append(organisation.local_identifier)
    person.affiliation_names.append(organisation.name)
    person.affiliation_roles.append("affiliate")


def _index_person_organisation(
    organisations_by_id: dict[str, AgentRef],
    *,
    pi: dict[str, Any],
    organisation_name: str,
    scheme: str,
    identifier_value: str,
) -> AgentRef:
    """Index the organisation associated with a person."""
    if scheme == "ror":
        organisation_identifier_value = identifier_value
    else:
        organisation_identifier_value = ROR_LOOKUP.get(normalize_ror_lookup_name(organisation_name)) or ""

    return _get_or_create_organisation(
        organisations_by_id,
        name=organisation_name,
        language=_clean(pi.get("language")).lower(),
        identifier_value=organisation_identifier_value,
        identifier_scheme="ror" if organisation_identifier_value else "",
        source_data=pi,
    )


def _index_person_entry(
    persons_by_id: dict[str, AgentRef],
    organisations_by_id: dict[str, AgentRef],
    *,
    pi: dict[str, Any],
    person_name: str,
    organisation_name: str,
    scheme: str,
    identifier_value: str,
    role: str,
) -> None:
    """Index a person and any organisation affiliation from a PI entry."""
    if not person_name:
        return

    person_identifier_value = identifier_value if scheme == "orcid" and role != "affiliation-pid" else ""

    person = _get_or_create_person(
        persons_by_id,
        pi=pi,
        name=person_name,
        identifier_value=person_identifier_value,
        identifier_scheme="orcid" if person_identifier_value else "",
    )

    if not organisation_name:
        return

    organisation = _index_person_organisation(
        organisations_by_id,
        pi=pi,
        organisation_name=organisation_name,
        scheme=scheme,
        identifier_value=identifier_value,
    )

    _add_person_affiliation(person, organisation)


def _index_organisation_entry(
    organisations_by_id: dict[str, AgentRef],
    *,
    pi: dict[str, Any],
    person_name: str,
    organisation_name: str,
    scheme: str,
    identifier_value: str,
) -> None:
    """Index an organisation represented by a PI entry."""
    name = organisation_name or person_name

    if not name:
        return

    organisation_identifier_value = identifier_value if scheme == "ror" else ""

    _get_or_create_organisation(
        organisations_by_id,
        name=name,
        language=_clean(pi.get("language")).lower(),
        identifier_value=organisation_identifier_value,
        identifier_scheme="ror" if organisation_identifier_value else "",
        source_data=pi,
    )


def _index_principal_investigator(
    persons_by_id: dict[str, AgentRef],
    organisations_by_id: dict[str, AgentRef],
    pi: Any,
) -> None:
    """Index a person or organisation from a principal investigator entry."""
    if not isinstance(pi, dict):
        return

    entity_type = determine_agent_type(pi)

    if entity_type is None:
        return

    person_name = _clean(pi.get("principal_investigator"))
    organisation_name = _clean(pi.get("organization"))

    scheme, identifier_value, _ = _extract_identifier(pi)
    role = _clean(pi.get("external_link_role")).lower()

    if entity_type == "person":
        _index_person_entry(
            persons_by_id,
            organisations_by_id,
            pi=pi,
            person_name=person_name,
            organisation_name=organisation_name,
            scheme=scheme,
            identifier_value=identifier_value,
            role=role,
        )
        return

    if entity_type == "organisation":
        _index_organisation_entry(
            organisations_by_id,
            pi=pi,
            person_name=person_name,
            organisation_name=organisation_name,
            scheme=scheme,
            identifier_value=identifier_value,
        )


def _index_agents_from_document(
    persons_by_id: dict[str, AgentRef],
    organisations_by_id: dict[str, AgentRef],
    doc: dict[str, Any],
) -> None:
    """Index agents and organisation sources from one source document."""
    for pi in doc.get("principal_investigators", []) or []:
        _index_principal_investigator(
            persons_by_id,
            organisations_by_id,
            pi,
        )

    _index_organisation_source(
        organisations_by_id,
        doc.get("publishers", []) or [],
        name_field="publisher",
    )

    _index_organisation_source(
        organisations_by_id,
        doc.get("distributors", []) or [],
        name_field="distributor",
    )


def _index_agents_from_document(
    persons_by_id: dict[str, AgentRef],
    organisations_by_id: dict[str, AgentRef],
    doc: dict[str, Any],
) -> None:
    """Index agents and organisation sources from one source document."""
    for pi in doc.get("principal_investigators", []) or []:
        _index_principal_investigator(
            persons_by_id,
            organisations_by_id,
            pi,
        )

    _index_organisation_source(
        organisations_by_id,
        doc.get("publishers", []) or [],
        name_field="publisher",
    )

    _index_organisation_source(
        organisations_by_id,
        doc.get("distributors", []) or [],
        name_field="distributor",
    )


def _refresh_affiliation_name(
    affiliation: AffiliationRef,
    organisations_by_id: dict[str, AgentRef],
) -> AffiliationRef:
    """Return an affiliation using the organisation's current preferred name."""
    organisation = organisations_by_id.get(affiliation.local_identifier)

    return AffiliationRef(
        local_identifier=affiliation.local_identifier,
        name=organisation.name if organisation is not None else affiliation.name,
    )


def _refresh_person_affiliations(
    persons_by_id: dict[str, AgentRef],
    organisations_by_id: dict[str, AgentRef],
) -> None:
    """Refresh affiliation names after organisation names are finalized."""
    for person in persons_by_id.values():
        refreshed_affiliations = [
            _refresh_affiliation_name(affiliation, organisations_by_id) for affiliation in person.affiliations
        ]

        person.affiliations = refreshed_affiliations
        person.affiliation_local_identifiers = [affiliation.local_identifier for affiliation in refreshed_affiliations]
        person.affiliation_names = [affiliation.name for affiliation in refreshed_affiliations]


def _finalize_agent_refs(
    agents_by_id: dict[str, AgentRef],
) -> list[AgentRef]:
    """Finalize and sort indexed agent references."""
    for agent in agents_by_id.values():
        _finalize_agent_ref(agent)

    return sorted(
        agents_by_id.values(),
        key=lambda agent: (agent.sort_name, agent.local_identifier),
    )


async def build_agent_index(collection) -> AgentIndex:
    """
    Build a flattened index containing Persons and Organisations discovered
    from study PI metadata.

    Ambiguous generic Agents are intentionally excluded.
    """
    _logger.info("Agent index building...")

    persons_by_id: dict[str, AgentRef] = {}
    organisations_by_id: dict[str, AgentRef] = {}

    _index_static_organisations(organisations_by_id)

    projection = {
        "principal_investigators": 1,
        "publishers": 1,
        "distributors": 1,
    }

    async for doc in collection.find({}, projection):
        _index_agents_from_document(
            persons_by_id,
            organisations_by_id,
            doc,
        )

    _refresh_person_affiliations(
        persons_by_id,
        organisations_by_id,
    )

    persons = _finalize_agent_refs(persons_by_id)
    organisations = _finalize_agent_refs(organisations_by_id)

    _logger.info(
        "Agent index built (%s persons, %s organisations)",
        len(persons),
        len(organisations),
    )

    return AgentIndex(
        persons=persons,
        organisations=organisations,
        person_by_id=persons_by_id,
        organisation_by_id=organisations_by_id,
    )


# ============================================================
# Filter parsing / matching
# ============================================================


class FilterOp(str, Enum):
    CONTAINS = "contains"
    EXACT = "exact"


@dataclass(frozen=True, slots=True)
class RawClause:
    key: str
    value: str


@dataclass(frozen=True, slots=True)
class BoundClause:
    key: str
    op: FilterOp
    value: str
    extractor_name: str


@dataclass(frozen=True, slots=True)
class FilterSpec:
    key: str
    extractor_name: str
    default_op: FilterOp
    allowed_ops: tuple[FilterOp, ...]


# Declarative filter registry for Persons
FILTER_SPECS_PERSONS = {
    "name": FilterSpec(
        key="name",
        extractor_name="name",
        default_op=FilterOp.CONTAINS,
        allowed_ops=(FilterOp.CONTAINS, FilterOp.EXACT),
    ),
    IDENTIFIERS_ID: FilterSpec(
        key=IDENTIFIERS_ID,
        extractor_name="identifiers",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    IDENTIFIERS_SCHEME: FilterSpec(
        key=IDENTIFIERS_SCHEME,
        extractor_name="identifier_schemes",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    AFFILIATION_LOCAL_IDENTIFIER: FilterSpec(
        key=AFFILIATION_LOCAL_IDENTIFIER,
        extractor_name="affiliation_local_identifiers",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    AFFILIATION_NAME: FilterSpec(
        key=AFFILIATION_NAME,
        extractor_name="affiliation_names",
        default_op=FilterOp.CONTAINS,
        allowed_ops=(FilterOp.CONTAINS, FilterOp.EXACT),
    ),
    "affiliations.role": FilterSpec(
        key="affiliations.role",
        extractor_name="affiliation_roles",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    SEARCH_NAME: FilterSpec(
        key=SEARCH_NAME,
        extractor_name="name",
        default_op=FilterOp.CONTAINS,
        allowed_ops=(FilterOp.CONTAINS,),
    ),
}


# Declarative filter registry for Organisations
FILTER_SPECS_ORGANISATIONS = {
    IDENTIFIERS_ID: FilterSpec(
        key=IDENTIFIERS_ID,
        extractor_name="identifiers",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT),
    ),
    IDENTIFIERS_SCHEME: FilterSpec(
        key=IDENTIFIERS_SCHEME,
        extractor_name="identifier_schemes",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "name": FilterSpec(
        key="name",
        extractor_name="name",
        default_op=FilterOp.CONTAINS,
        allowed_ops=(FilterOp.CONTAINS, FilterOp.EXACT),
    ),
    "short_name": FilterSpec(
        key="short_name",
        extractor_name="short_name",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT, FilterOp.CONTAINS),
    ),
    "website": FilterSpec(
        key="website",
        extractor_name="website",
        default_op=FilterOp.CONTAINS,
        allowed_ops=(FilterOp.CONTAINS, FilterOp.EXACT),
    ),
    SEARCH_NAME: FilterSpec(
        key=SEARCH_NAME,
        extractor_name="search_names",
        default_op=FilterOp.CONTAINS,
        allowed_ops=(FilterOp.CONTAINS, FilterOp.EXACT),
    ),
}


# Keys that should explicitly fail with 422 for now
DISALLOWED_KEYS = {
    "given_name",
    "family_name",
    "country",
    "cf.search.given_name",
    "cf.search.family_name",
    "affiliations.affiliation.short_name",
}


# ---- extractors ----


def extract_identifiers(ref: AgentRef) -> list[str]:
    return ref.identifiers


def extract_identifier_schemes(ref: AgentRef) -> list[str]:
    return ref.identifier_schemes


def extract_name(ref: AgentRef) -> list[str]:
    return [ref.name] if ref.name else []


def extract_short_name(ref: AgentRef) -> list[str]:
    return [ref.short_name] if ref.short_name else []


def extract_website(ref: AgentRef) -> list[str]:
    return [ref.website] if ref.website else []


def extract_affiliation_local_identifiers(ref: AgentRef) -> list[str]:
    return ref.affiliation_local_identifiers


def extract_affiliation_names(ref: AgentRef) -> list[str]:
    return ref.affiliation_names


def extract_affiliation_roles(ref: AgentRef) -> list[str]:
    return ref.affiliation_roles


def extract_search_names(ref: AgentRef) -> list[str]:
    return [ref.name, *ref.other_names]


EXTRACTORS = {
    "identifiers": extract_identifiers,
    "identifier_schemes": extract_identifier_schemes,
    "name": extract_name,
    "short_name": extract_short_name,
    "website": extract_website,
    "affiliation_local_identifiers": extract_affiliation_local_identifiers,
    "affiliation_names": extract_affiliation_names,
    "affiliation_roles": extract_affiliation_roles,
    "search_names": extract_search_names,
}


# ---- parsing / binding ----


def supported_filter_keys(filter_specs: dict[str, FilterSpec]) -> str:
    return ", ".join(filter_specs)


def bind_clauses(raw_clauses: list[RawClause], filter_specs: dict[str, FilterSpec]) -> list[BoundClause]:
    """
    Validate raw clauses against supported filter specs.
    """
    bound: list[BoundClause] = []

    supported_filters = supported_filter_keys(filter_specs)

    for clause in raw_clauses:
        if clause.key in DISALLOWED_KEYS:
            raise InvalidFilterException(
                detail=(
                    f"The filter '{clause.key}' is not supported "
                    f"by this implementation. Valid filters are: "
                    f"{supported_filters}"
                )
            )

        spec = filter_specs.get(clause.key)

        if not spec:
            raise InvalidFilterException(
                detail=(
                    f"The filter '{clause.key}' is not supported "
                    f"by this implementation. Valid filters are: "
                    f"{supported_filters}"
                )
            )

        bound.append(
            BoundClause(key=spec.key, op=spec.default_op, value=clause.value, extractor_name=spec.extractor_name)
        )

    return bound


def parse_raw_filter_string(filter_raw: str | None) -> list[RawClause]:

    if not filter_raw:
        return []

    filter_raw = urllib.parse.unquote(filter_raw)

    clauses: list[RawClause] = []

    for part in [p for p in filter_raw.split(",") if p]:
        if ":" not in part:
            raise InvalidFilterException(detail=(f"Invalid filter clause '{part}'. Expected format: key:value."))

        raw_key, raw_value = part.split(":", 1)

        key = raw_key.strip()
        value = (raw_value or "").strip()

        if not key or not value:
            raise InvalidFilterException(detail=(f"Invalid filter clause '{part}'. Expected format: key:value."))

        clauses.append(RawClause(key=key, value=value))

    return clauses


def parse_agent_filter_raw(filter_raw: str | None, filter_specs: dict[str, FilterSpec]) -> list[BoundClause]:
    raw_clauses = parse_raw_filter_string(filter_raw)

    return bind_clauses(raw_clauses, filter_specs)


# ---- evaluation ----


def _exact_agent_identifier_match(values: list[str], expected: str, *, entity_type: str) -> bool:

    expected_norm = normalize_agent_lookup_identifier(expected, entity_type)

    return any(normalize_agent_lookup_identifier(value, entity_type) == expected_norm for value in values)


def evaluate_clause(ref: AgentRef, clause: BoundClause) -> bool:

    extractor = EXTRACTORS[clause.extractor_name]

    values = extractor(ref)

    # wildcard = attribute exists
    if clause.value == "*":
        return any(value not in ("", None) for value in values)

    if clause.op == FilterOp.CONTAINS:
        if clause.key in {"name", AFFILIATION_NAME}:
            return _contains_name_match(values, clause.value)

        return _contains_match(values, clause.value)

    if clause.op == FilterOp.EXACT:
        if clause.key == IDENTIFIERS_ID:
            return _exact_agent_identifier_match(values, clause.value, entity_type=ref.entity_type)

        if clause.key == AFFILIATION_LOCAL_IDENTIFIER:
            return _exact_agent_identifier_match(values, clause.value, entity_type="organisation")

        return _exact_match(values, clause.value)

    return False


def match_agent_ref(ref: AgentRef, clauses: list[BoundClause]) -> bool:
    """
    AND semantics across clauses.
    """
    return all(evaluate_clause(ref, clause) for clause in clauses)


def filter_agent_refs(refs: list[AgentRef], clauses: list[BoundClause]) -> list[AgentRef]:

    if not clauses:
        return refs

    return [ref for ref in refs if match_agent_ref(ref, clauses)]
