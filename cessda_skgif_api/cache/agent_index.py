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
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

import urllib.parse
from cessda_skgif_api.cache.product_index import (
    _contains_match,
    _contains_name_match,
    _exact_identifier_match,
    _exact_match,
)
from cessda_skgif_api.utils.constants import (
    ROR_LOOKUP,
    ROR_PRIMARY_NAMES,
    STATIC_ORGANISATIONS,
)
from cessda_skgif_api.utils.errors import InvalidFilterException
from cessda_skgif_api.utils.helpers import (
    dedupe_preserve_order,
    normalize_ror_lookup_name,
    normalize_text,
)
from cessda_skgif_api.utils.identifier_utils import (
    generate_person_local_identifier,
    normalize_pid_url,
    resolve_organisation_local_identifier,
)

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AffiliationRef:
    local_identifier: str
    name: str


@dataclass(slots=True)
class AgentRef:
    local_identifier: str
    entity_type: str
    name: str

    short_name: Optional[str] = None
    website: Optional[str] = None

    identifiers: List[str] = field(default_factory=list)
    identifier_schemes: List[str] = field(default_factory=list)

    affiliations: List[AffiliationRef] = field(default_factory=list)

    affiliation_local_identifiers: List[str] = field(default_factory=list)
    affiliation_names: List[str] = field(default_factory=list)
    affiliation_roles: List[str] = field(default_factory=list)

    other_names: List[str] = field(default_factory=list)

    source_data: List[Dict[str, Any]] = field(default_factory=list)

    sort_name: str = ""


@dataclass(slots=True)
class AgentIndex:
    persons: List[AgentRef]
    organisations: List[AgentRef]

    person_by_id: Dict[str, AgentRef]
    organisation_by_id: Dict[str, AgentRef]


def _clean(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    return value.strip()


def _select_preferred_name_entry(
    entries: List[Dict[str, Any]],
    name_field: str,
) -> Optional[Dict[str, Any]]:
    valid_entries = [entry for entry in entries if _clean(entry.get(name_field))]

    if not valid_entries:
        return None

    return next(
        (
            entry
            for entry in valid_entries
            if _clean(entry.get("language")).lower() == "en"
        ),
        valid_entries[0],
    )


def _group_organisation_entries(
    entries: List[Dict[str, Any]],
    name_field: str,
) -> List[List[Dict[str, Any]]]:

    """
    Group multilingual publisher or distributor entries.

    Entries sharing an abbreviation are grouped together.

    Entries without an abbreviation are grouped as multilingual variants only
    when every entry has a non-empty, unique language. If a language is missing
    or occurs more than once, the entries are treated as separate organisations
    because their relationship is ambiguous.
    """
    valid_entries = [
        entry
        for entry in entries or []
        if isinstance(entry, dict) and _clean(entry.get(name_field))
    ]

    if not valid_entries:
        return []

    groups: List[List[Dict[str, Any]]] = []

    abbreviation_groups: Dict[str, List[Dict[str, Any]]] = {}
    no_abbreviation_entries: List[Dict[str, Any]] = []

    for entry in valid_entries:
        abbreviation = normalize_text(
            _clean(entry.get("abbreviation"))
        )

        if abbreviation:
            abbreviation_groups.setdefault(
                abbreviation,
                [],
            ).append(entry)
        else:
            no_abbreviation_entries.append(entry)

    groups.extend(abbreviation_groups.values())

    if no_abbreviation_entries:
        languages = [
            _clean(entry.get("language")).lower()
            for entry in no_abbreviation_entries
        ]

        has_unique_languages = (
            all(languages)
            and len(languages) == len(set(languages))
        )

        if has_unique_languages:
            groups.append(no_abbreviation_entries)
        else:
            groups.extend(
                [entry]
                for entry in no_abbreviation_entries
            )

    return groups


def _index_organisation_source(
    organisations_by_id: Dict[str, AgentRef],
    entries: List[Dict[str, Any]],
    *,
    name_field: str,
) -> None:

    for group in _group_organisation_entries(
        entries,
        name_field,
    ):

        preferred_entry = _select_preferred_name_entry(
            group,
            name_field,
        )

        if preferred_entry is None:
            continue

        preferred_name = _clean(preferred_entry.get(name_field))

        ror_id = None

        for entry in group:
            candidate = _clean(entry.get(name_field))

            ror_id = ROR_LOOKUP.get(normalize_ror_lookup_name(candidate))

            if ror_id:
                break

        short_name = next(
            (
                _clean(entry.get("abbreviation"))
                for entry in group
                if _clean(entry.get("abbreviation"))
            ),
            "",
        )

        website = next(
            (_clean(entry.get("uri")) for entry in group if _clean(entry.get("uri"))),
            "",
        )

        preferred_language = _clean(preferred_entry.get("language")).lower()

        other_names = dedupe_preserve_order(
            _clean(entry.get(name_field))
            for entry in group
            if (
                _clean(entry.get(name_field))
                and normalize_text(_clean(entry.get(name_field)))
                != normalize_text(preferred_name)
            )
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


def _extract_identifier(
    pi: Dict[str, Any],
) -> tuple[str, str, str]:
    """
    Return scheme, original value and canonical PID URL.
    """
    scheme = _clean(pi.get("external_link_title")).lower()
    value = _clean(pi.get("external_link"))

    canonical_url = normalize_pid_url(scheme, value) if scheme and value else None

    return scheme, value, canonical_url or ""


def determine_agent_type(
    pi: Dict[str, Any],
) -> Optional[str]:
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
    if person_name and (
        organisation_name or scheme == "orcid" or role == "affiliation-pid"
    ):
        return "person"

    # An organisation field without a person name is explicit enough.
    if organisation_name and not person_name:
        return "organisation"

    # A ROR attached directly to a named entry indicates an organisation.
    if person_name and scheme == "ror" and role != "affiliation-pid":
        return "organisation"

    # Name-only entries remain generic Agents and are excluded.
    return None


def _get_or_create_organisation(
    organisations_by_id: Dict[str, AgentRef],
    *,
    name: str,
    language: str = "",
    identifier_value: str = "",
    identifier_scheme: str = "",
    short_name: Optional[str] = None,
    website: Optional[str] = None,
    source_data: Optional[Dict[str, Any]] = None,
    local_identifier: Optional[str] = None,
    other_names: Optional[List[str]] = None,
) -> AgentRef:
    ror_value = identifier_value if identifier_scheme == "ror" else None

    if local_identifier is None:
        local_identifier = resolve_organisation_local_identifier(
            name=name,
            ror=ror_value,
        )

    incoming_name = name

    canonical_name = ROR_PRIMARY_NAMES.get(ror_value) if ror_value else None

    if canonical_name:
        name = canonical_name

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

    elif language == "en" and not canonical_name:
        previous_name = organisation.name

        if previous_name and normalize_text(previous_name) != normalize_text(name):
            organisation.other_names.append(previous_name)

        organisation.name = name
        organisation.sort_name = normalize_text(name)

    elif normalize_text(name) != normalize_text(organisation.name):
        organisation.other_names.append(name)

    if incoming_name and normalize_text(incoming_name) != normalize_text(
        organisation.name
    ):
        organisation.other_names.append(incoming_name)

    for other_name in other_names or []:
        if other_name and normalize_text(other_name) != normalize_text(
            organisation.name
        ):
            organisation.other_names.append(other_name)

    if short_name and not organisation.short_name:
        organisation.short_name = short_name

    if website and not organisation.website:
        organisation.website = website

    if identifier_value and identifier_scheme:
        organisation.identifiers.append(identifier_value)
        organisation.identifier_schemes.append(identifier_scheme)

    if source_data:
        organisation.source_data.append(source_data)

    return organisation


def _get_or_create_person(
    persons_by_id: Dict[str, AgentRef],
    *,
    pi: Dict[str, Any],
    name: str,
    identifier_value: str = "",
    identifier_scheme: str = "",
) -> AgentRef:
    orcid_value = identifier_value if identifier_scheme == "orcid" else None

    local_identifier = generate_person_local_identifier(
        name=name,
        orcid=orcid_value,
    )

    person = persons_by_id.get(local_identifier)

    if person is None:
        person = AgentRef(
            local_identifier=local_identifier,
            entity_type="person",
            name=name,
            sort_name=normalize_text(name),
        )
        persons_by_id[local_identifier] = person

    if identifier_value and identifier_scheme:
        person.identifiers.append(identifier_value)
        person.identifier_schemes.append(identifier_scheme)

    person.source_data.append(pi)

    return person


def _finalize_agent_ref(ref: AgentRef) -> None:
    identifier_pairs = dedupe_preserve_order(
        zip(
            ref.identifier_schemes,
            ref.identifiers,
        )
    )

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

    ref.affiliation_local_identifiers = dedupe_preserve_order(
        ref.affiliation_local_identifiers
    )

    ref.affiliation_names = dedupe_preserve_order(ref.affiliation_names)

    ref.affiliation_roles = dedupe_preserve_order(ref.affiliation_roles)

    ref.other_names = dedupe_preserve_order(
        name
        for name in ref.other_names
        if name and normalize_text(name) != normalize_text(ref.name)
    )


async def build_agent_index(collection) -> AgentIndex:
    """
    Build a flattened index containing Persons and Organisations discovered
    from study PI metadata.

    Ambiguous generic Agents are intentionally excluded.
    """
    _logger.info("Agent index building...")

    persons_by_id: Dict[str, AgentRef] = {}
    organisations_by_id: Dict[str, AgentRef] = {}

    for org in STATIC_ORGANISATIONS:
        _get_or_create_organisation(
            organisations_by_id,
            name=org["name"],
            short_name=org.get("short_name"),
            website=org.get("website"),
            identifier_value=org.get("ror", ""),
            identifier_scheme="ror" if org.get("ror") else "",
        )

    projection = {
        "principal_investigators": 1,
        "publishers": 1,
        "distributors": 1,
    }

    async for doc in collection.find({}, projection):
        for pi in doc.get("principal_investigators", []) or []:
            if not isinstance(pi, dict):
                continue

            entity_type = determine_agent_type(pi)

            if entity_type is None:
                continue

            person_name = _clean(pi.get("principal_investigator"))
            organisation_name = _clean(pi.get("organization"))

            scheme, identifier_value, _ = _extract_identifier(pi)
            role = _clean(pi.get("external_link_role")).lower()

            if entity_type == "person":
                if not person_name:
                    continue

                person_identifier_value = (
                    identifier_value
                    if scheme == "orcid" and role != "affiliation-pid"
                    else ""
                )
                person_identifier_scheme = scheme if person_identifier_value else ""

                person = _get_or_create_person(
                    persons_by_id,
                    pi=pi,
                    name=person_name,
                    identifier_value=person_identifier_value,
                    identifier_scheme=person_identifier_scheme,
                )

                if organisation_name:
                    organisation_identifier_value = (
                        identifier_value
                        if scheme == "ror"
                        else (ROR_LOOKUP.get(normalize_ror_lookup_name(organisation_name)) or "")
                    )
                    organisation_identifier_scheme = (
                        "ror" if organisation_identifier_value else ""
                    )

                    organisation = _get_or_create_organisation(
                        organisations_by_id,
                        name=organisation_name,
                        language=_clean(pi.get("language")).lower(),
                        identifier_value=organisation_identifier_value,
                        identifier_scheme=organisation_identifier_scheme,
                        source_data=pi,
                    )

                    person.affiliations.append(
                        AffiliationRef(
                            local_identifier=organisation.local_identifier,
                            name=organisation.name,
                        )
                    )
                    person.affiliation_local_identifiers.append(
                        organisation.local_identifier
                    )
                    person.affiliation_names.append(organisation.name)
                    person.affiliation_roles.append("affiliate")

                continue

            if entity_type == "organisation":
                name = organisation_name or person_name

                if not name:
                    continue

                organisation_identifier_value = (
                    identifier_value if scheme == "ror" else ""
                )
                organisation_identifier_scheme = (
                    scheme if organisation_identifier_value else ""
                )

                _get_or_create_organisation(
                    organisations_by_id,
                    name=name,
                    language=_clean(pi.get("language")).lower(),
                    identifier_value=organisation_identifier_value,
                    identifier_scheme=organisation_identifier_scheme,
                    source_data=pi,
                )

        _index_organisation_source(
            organisations_by_id,
            doc.get("publishers", []),
            name_field="publisher",
        )

        _index_organisation_source(
            organisations_by_id,
            doc.get("distributors", []),
            name_field="distributor",
        )

    for person in persons_by_id.values():

        refreshed_affiliations = []

        for affiliation in person.affiliations:

            organisation = organisations_by_id.get(affiliation.local_identifier)

            refreshed_affiliations.append(
                AffiliationRef(
                    local_identifier=affiliation.local_identifier,
                    name=(
                        organisation.name
                        if organisation is not None
                        else affiliation.name
                    ),
                )
            )

        person.affiliations = refreshed_affiliations

        person.affiliation_local_identifiers = [
            affiliation.local_identifier for affiliation in refreshed_affiliations
        ]

        person.affiliation_names = [
            affiliation.name for affiliation in refreshed_affiliations
        ]

    for ref in persons_by_id.values():
        _finalize_agent_ref(ref)

    for ref in organisations_by_id.values():
        _finalize_agent_ref(ref)

    persons = sorted(
        persons_by_id.values(),
        key=lambda ref: (
            ref.sort_name,
            ref.local_identifier,
        ),
    )

    organisations = sorted(
        organisations_by_id.values(),
        key=lambda ref: (
            ref.sort_name,
            ref.local_identifier,
        ),
    )

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
    "identifiers.id": FilterSpec(
        key="identifiers.id",
        extractor_name="identifiers",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "identifiers.scheme": FilterSpec(
        key="identifiers.scheme",
        extractor_name="identifier_schemes",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "affiliations.affiliation.local_identifier": FilterSpec(
        key="affiliations.affiliation.local_identifier",
        extractor_name="affiliation_local_identifiers",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "affiliations.affiliation.name": FilterSpec(
        key="affiliations.affiliation.name",
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
    "cf.search.name": FilterSpec(
        key="cf.search.name",
        extractor_name="name",
        default_op=FilterOp.CONTAINS,
        allowed_ops=(FilterOp.CONTAINS,),
    ),
}


# Declarative filter registry for Organisations
FILTER_SPECS_ORGANISATIONS = {
    "identifiers.id": FilterSpec(
        key="identifiers.id",
        extractor_name="identifiers",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "identifiers.scheme": FilterSpec(
        key="identifiers.scheme",
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
    "cf.search.name": FilterSpec(
        key="cf.search.name",
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


def extract_identifiers(ref: AgentRef) -> List[str]:
    return ref.identifiers


def extract_identifier_schemes(ref: AgentRef) -> List[str]:
    return ref.identifier_schemes


def extract_name(ref: AgentRef) -> List[str]:
    return [ref.name] if ref.name else []


def extract_short_name(ref: AgentRef) -> List[str]:
    return [ref.short_name] if ref.short_name else []


def extract_website(ref: AgentRef) -> List[str]:
    return [ref.website] if ref.website else []


def extract_affiliation_local_identifiers(ref: AgentRef) -> List[str]:
    return ref.affiliation_local_identifiers


def extract_affiliation_names(ref: AgentRef) -> List[str]:
    return ref.affiliation_names


def extract_affiliation_roles(ref: AgentRef) -> List[str]:
    return ref.affiliation_roles


def extract_search_names(ref: AgentRef) -> List[str]:
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


def supported_filter_keys(filter_specs: Dict[str, FilterSpec]) -> str:
    return ", ".join(filter_specs)


def bind_clauses(
    raw_clauses: List[RawClause],
    filter_specs: Dict[str, FilterSpec],
) -> List[BoundClause]:
    """
    Validate raw clauses against supported filter specs.
    """
    bound: List[BoundClause] = []

    supported_filters = supported_filter_keys(
        filter_specs,
    )

    for clause in raw_clauses:

        if clause.key in DISALLOWED_KEYS:
            raise InvalidFilterException(
                detail=(
                    f"The filter '{clause.key}' is not supported "
                    f"by this implementation. Valid filters are: "
                    f"{supported_filters}"
                ),
            )

        spec = filter_specs.get(clause.key)

        if not spec:
            raise InvalidFilterException(
                detail=(
                    f"The filter '{clause.key}' is not supported "
                    f"by this implementation. Valid filters are: "
                    f"{supported_filters}"
                ),
            )

        bound.append(
            BoundClause(
                key=spec.key,
                op=spec.default_op,
                value=clause.value,
                extractor_name=spec.extractor_name,
            )
        )

    return bound


def parse_raw_filter_string(
    filter_raw: Optional[str],
) -> List[RawClause]:

    if not filter_raw:
        return []

    filter_raw = urllib.parse.unquote(filter_raw)

    clauses: List[RawClause] = []

    for part in [p for p in filter_raw.split(",") if p]:

        if ":" not in part:
            raise InvalidFilterException(
                detail=(
                    f"Invalid filter clause '{part}'. "
                    "Expected format: key:value."
                ),
            )

        raw_key, raw_value = part.split(":", 1)

        key = raw_key.strip()
        value = (raw_value or "").strip()

        if not key or not value:
            raise InvalidFilterException(
                detail=(
                    f"Invalid filter clause '{part}'. "
                    "Expected format: key:value."
                ),
            )

        clauses.append(
            RawClause(
                key=key,
                value=value,
            )
        )

    return clauses


def parse_agent_filter_raw(
    filter_raw: Optional[str],
    filter_specs: Dict[str, FilterSpec],
) -> List[BoundClause]:
    raw_clauses = parse_raw_filter_string(filter_raw)

    return bind_clauses(
        raw_clauses,
        filter_specs,
    )


# ---- evaluation ----


def evaluate_clause(
    ref: AgentRef,
    clause: BoundClause,
) -> bool:

    extractor = EXTRACTORS[clause.extractor_name]

    values = extractor(ref)

    # wildcard = attribute exists
    if clause.value == "*":
        return any(value not in ("", None) for value in values)

    if clause.op == FilterOp.CONTAINS:

        if clause.key in {
            "name",
            "affiliations.affiliation.name",
        }:
            return _contains_name_match(
                values,
                clause.value,
            )

        return _contains_match(
            values,
            clause.value,
        )

    if clause.op == FilterOp.EXACT:

        if clause.key in {
            "identifiers.id",
            "affiliations.affiliation.local_identifier",
        }:
            return _exact_identifier_match(
                values,
                clause.value,
            )

        return _exact_match(
            values,
            clause.value,
        )

    return False


def match_agent_ref(
    ref: AgentRef,
    clauses: List[BoundClause],
) -> bool:
    """
    AND semantics across clauses.
    """
    return all(evaluate_clause(ref, clause) for clause in clauses)


def filter_agent_refs(
    refs: List[AgentRef],
    clauses: List[BoundClause],
) -> List[AgentRef]:

    if not clauses:
        return refs

    return [
        ref
        for ref in refs
        if match_agent_ref(
            ref,
            clauses,
        )
    ]
