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

"""Transforms metadata of studies stored in MongoDB into SKG-IF Products."""

import json
import os
from typing import Any

import requests

from cessda_skgif_api.cache.cessda_topic_vocab import get_cached_vocab
from cessda_skgif_api.config_loader import load_config
from cessda_skgif_api.models.skgif import (
    Agent,
    Biblio,
    Contribution,
    DataSource,
    GrantLite,
    Identifier,
    Manifestation,
    OrganisationLite,
    PersonLite,
    Product,
    Term,
    TopicLite,
    Venue,
)
from cessda_skgif_api.utils.constants import (
    ALLOWED_IDENTIFIER_TYPES,
    PRODUCT_TYPE_RESEARCH_DATA,
    STATIC_ORGANISATIONS,
    URL_TO_DATASOURCE,
)
from cessda_skgif_api.utils.helpers import normalize_text
from cessda_skgif_api.utils.identifier_utils import (
    generate_otf_local_identifier,
    generate_person_local_identifier,
    generate_study_local_identifier,
    normalize_pid_url,
    resolve_organisation_local_identifier,
    resolve_organisation_ror,
)

config = load_config()
product_base_url = config.product_base_url
skg_if_context = config.skg_if_context
skg_if_api_context = config.skg_if_api_context
skg_if_cessda_context = config.skg_if_cessda_context
cessda_topic_vocab_api_url = config.cessda_topic_vocab_api_url
cessda_topic_vocab_api_version = config.cessda_topic_vocab_api_version
data_access_mapping_dir = os.path.dirname(os.path.abspath(__file__))
data_access_mapping_file_path = os.path.join(data_access_mapping_dir, "data_access_mappings.json")
data_access_mapping_file_url = config.data_access_mapping_file_url

# Caching dictionaries
cessda_topic_vocab_cache: dict[str, dict[int, dict[str, Any]]] = {}


def select_preferred_language_entries(
    entries: list[dict[str, Any]], preferred_lang: str = "en"
) -> list[dict[str, Any]]:
    """Select preferred-language entries, falling back to the first language group."""
    if not entries:
        return []

    grouped_by_lang = {}
    for entry in entries:
        lang = entry.get("language", "unknown")
        grouped_by_lang.setdefault(lang, []).append(entry)

    if preferred_lang in grouped_by_lang:
        return grouped_by_lang[preferred_lang]

    first_lang = next(iter(grouped_by_lang))
    return grouped_by_lang[first_lang]


def normalize_scheme(scheme: str) -> str | None:
    """Normalize a scheme by replacing spaces with underscores."""
    if scheme:
        if scheme.strip().lower() == "cessda topic classification":
            return "CESSDA_Topic_Classification"
        return scheme.replace(" ", "_")
    return None


def _resolve_cessda_topic(
    classification: dict[str, Any],
    vocab: dict[str, Any],
    label: str,
) -> tuple[str | None, str | None]:
    """Resolve a CESSDA Topic Classification to its notation and URI."""
    classification_notation = classification.get("classification")

    for notation, concept in vocab.items():
        title_matches = concept["title"].lower() == label.lower()
        notation_matches = bool(classification_notation) and notation == classification_notation

        if title_matches or notation_matches:
            return notation, concept["uri"]

    return None, None


def _build_topic_group_key(
    classification: dict[str, Any],
    *,
    scheme: str | None,
    uri: str,
    label: str,
    language: str,
    vocab_by_lang: dict[str, dict[str, Any]],
) -> tuple[tuple[str, ...], str | None]:
    """Build the grouping key and resolved URI for a topic classification."""
    if scheme == "CESSDA_Topic_Classification":
        notation, uri_from_api = _resolve_cessda_topic(
            classification,
            vocab_by_lang.get(language, {}),
            label,
        )
        return (scheme, notation or normalize_text(label) or ""), uri_from_api

    return (
        scheme or "",
        uri or "",
        normalize_text(label) or "",
    ), None


def transform_classifications_to_topics(classifications: list[dict[str, Any]]) -> list[TopicLite]:
    """Transform topic classifications into topics using notation for grouping."""
    metadata_languages = sorted({classification.get("language", "en") for classification in classifications})
    vocab_by_lang = {language: get_cached_vocab(language) for language in metadata_languages}
    topic_groups: dict[tuple[str, ...], dict[str, Any]] = {}

    for classification in classifications:
        scheme = normalize_scheme(classification.get("system_name"))
        uri = classification.get("uri", "")
        language = classification.get("language", "en")
        label = classification.get("description", "")

        key, uri_from_api = _build_topic_group_key(
            classification,
            scheme=scheme,
            uri=uri,
            label=label,
            language=language,
            vocab_by_lang=vocab_by_lang,
        )

        if key not in topic_groups:
            topic_groups[key] = {
                "scheme": scheme,
                "uri": uri,
                "labels": {},
                "uri_from_api": uri_from_api,
            }

        topic_groups[key]["labels"][language] = label

    topics = []
    for idx, key in enumerate(sorted(topic_groups), 1):
        group = topic_groups[key]
        identifiers = None

        if group.get("scheme") and group.get("uri"):
            identifiers = [Identifier(value=group["uri"], scheme=group["scheme"])]

        local_id = group["uri_from_api"] or generate_otf_local_identifier("topic", idx)
        term = Term(
            local_identifier=local_id,
            identifiers=identifiers,
            labels=group["labels"],
        )
        topics.append(TopicLite(term=term))

    return topics


def extract_identifiers(doc: dict[str, Any]) -> list[Identifier] | None:
    """Extract unique identifiers, preferring English-language entries."""
    raw_identifiers = doc.get("identifiers", [])
    seen = set()
    filtered = []

    english_ids = [item for item in raw_identifiers if item.get("language") == "en"]
    fallback_ids = [item for item in raw_identifiers if item.get("language") != "en"]

    for identifier_list in [english_ids, fallback_ids]:
        for item in identifier_list:
            agency = item.get("agency")
            identifier = item.get("identifier")

            if not agency or not identifier:
                continue

            key = (agency, identifier)
            if key not in seen:
                seen.add(key)
                filtered.append(Identifier(value=identifier, scheme=agency))

    return filtered or None


def extract_titles_and_abstracts(
    doc: dict[str, Any],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Extract titles and abstracts grouped by language."""
    titles, abstracts = {}, {}

    for title in doc.get("study_titles", []):
        lang = title.get("language", "en")
        titles.setdefault(lang, []).append(title["study_title"])

    for abstract in doc.get("abstracts", []):
        lang = abstract.get("language", "en")
        abstracts.setdefault(lang, []).append(abstract["abstract"])

    return titles, abstracts


def _build_contribution_identifiers(
    pi: dict[str, Any],
) -> tuple[str | None, str | None, list[Identifier] | None, list[Identifier] | None]:
    """Extract person and affiliation identifiers from a PI entry."""
    identifier_value = pi.get("external_link")
    role = (pi.get("external_link_role") or "").lower()
    title = (pi.get("external_link_title") or "").lower()
    scheme = title if title in ALLOWED_IDENTIFIER_TYPES else None

    if not identifier_value or not scheme:
        return identifier_value, scheme, None, None

    identifier = Identifier(value=identifier_value, scheme=scheme)

    if role == "affiliation-pid":
        return identifier_value, scheme, None, [identifier]

    return identifier_value, scheme, [identifier], None


def _build_declared_affiliation(
    organisation_name: str | None,
    *,
    identifier_value: str | None,
    scheme: str | None,
    role: str,
    identifiers: list[Identifier] | None,
) -> list[OrganisationLite] | None:
    """Build a person's declared organisation affiliation."""
    if not organisation_name:
        return None

    affiliation_value = identifier_value if role == "affiliation-pid" else None
    affiliation_scheme = scheme if role == "affiliation-pid" else None
    resolved_ror = resolve_organisation_ror(
        name=organisation_name,
        ror=affiliation_value if affiliation_scheme == "ror" else None,
    )
    local_identifier = resolve_organisation_local_identifier(
        name=organisation_name,
        ror=resolved_ror,
    )
    affiliation_identifiers = list(identifiers or [])

    if resolved_ror and not any(identifier.scheme == "ror" for identifier in affiliation_identifiers):
        affiliation_identifiers.append(Identifier(value=resolved_ror, scheme="ror"))

    return [
        OrganisationLite(
            local_identifier=local_identifier,
            name=organisation_name,
            identifiers=affiliation_identifiers or None,
        )
    ]


def _build_person_contribution(
    *,
    pi: dict[str, Any],
    name: str,
    organisation_name: str | None,
    identifier_value: str | None,
    scheme: str | None,
    person_identifiers: list[Identifier] | None,
    organisation_identifiers: list[Identifier] | None,
) -> Contribution:
    """Build a person contribution."""
    role = (pi.get("external_link_role") or "").lower()
    person_orcid = identifier_value if scheme == "orcid" and role != "affiliation-pid" else None
    person = PersonLite(
        local_identifier=generate_person_local_identifier(
            name=name,
            orcid=person_orcid,
        ),
        name=name,
        identifiers=person_identifiers,
    )
    affiliations = _build_declared_affiliation(
        organisation_name,
        identifier_value=identifier_value,
        scheme=scheme,
        role=role,
        identifiers=organisation_identifiers,
    )

    return Contribution(
        role="author",
        by=person,
        declared_affiliations=affiliations,
    )


def _build_organisation_contribution(
    *,
    name: str,
    identifier_value: str | None,
    scheme: str | None,
    identifiers: list[Identifier] | None,
) -> Contribution:
    """Build an organisation contribution."""
    resolved_ror = resolve_organisation_ror(
        name=name,
        ror=identifier_value if scheme == "ror" else None,
    )
    organisation_identifiers = list(identifiers or [])

    if resolved_ror and not any(identifier.scheme == "ror" for identifier in organisation_identifiers):
        organisation_identifiers.append(Identifier(value=resolved_ror, scheme="ror"))

    organisation = OrganisationLite(
        local_identifier=resolve_organisation_local_identifier(
            name=name,
            ror=resolved_ror,
        ),
        name=name,
        identifiers=organisation_identifiers or None,
    )

    return Contribution(role="author", by=organisation)


def _build_contribution(pi: dict[str, Any], idx: int) -> Contribution | None:
    """Build a contribution from one principal-investigator entry."""
    title = (pi.get("external_link_title") or "").lower()
    organisation_name = pi.get("organization")

    if title == "ror" and organisation_name is None:
        entity_type = "organisation"
    elif organisation_name or title == "orcid":
        entity_type = "person"
    else:
        entity_type = "agent"

    name = pi.get("principal_investigator")

    if not name:
        name = organisation_name
        entity_type = "organisation"

    if not name:
        return None

    identifier_value, scheme, person_identifiers, organisation_identifiers = _build_contribution_identifiers(pi)

    if entity_type == "person":
        return _build_person_contribution(
            pi=pi,
            name=name,
            organisation_name=organisation_name,
            identifier_value=identifier_value,
            scheme=scheme,
            person_identifiers=person_identifiers,
            organisation_identifiers=organisation_identifiers,
        )

    if entity_type == "organisation":
        return _build_organisation_contribution(
            name=name,
            identifier_value=identifier_value,
            scheme=scheme,
            identifiers=person_identifiers,
        )

    return Contribution(
        role="author",
        by=Agent(
            local_identifier=generate_otf_local_identifier("agent", idx),
            name=name,
            identifiers=person_identifiers,
        ),
    )


def build_contributions(doc: dict[str, Any]) -> list[Contribution] | None:
    """Build contributions from principal investigators with stable local IDs."""
    selected_pis = select_preferred_language_entries(doc.get("principal_investigators", []))
    contributions = [
        contribution
        for idx, pi in enumerate(selected_pis, 1)
        if (contribution := _build_contribution(pi, idx)) is not None
    ]
    return contributions or None


def _first_date(entries: list[dict[str, Any]], field_name: str) -> str | None:
    """Return the first non-empty date from a metadata field."""
    return next(
        (entry.get(field_name) for entry in entries if entry.get(field_name)),
        None,
    )


def extract_dates(doc: dict[str, Any]) -> dict[str, list[str]] | None:
    """Extract publication and collection dates."""
    dates = {}
    publication_date = _first_date(
        doc.get("distribution_dates", []),
        "distribution_date",
    )

    if not publication_date:
        publication_date = _first_date(
            doc.get("publication_dates", []),
            "publication_date",
        )

    if publication_date:
        dates["publication"] = [publication_date]

    collected_periods = {}
    for period in doc.get("collection_periods", []):
        date = period.get("collection_period")
        language = period.get("language")

        if date and (date not in collected_periods or language == "en"):
            collected_periods[date] = language

    if collected_periods:
        dates["collected"] = list(collected_periods)

    return dates or None


def build_biblio(doc: dict[str, Any]) -> Biblio:
    """Build a Biblio object with Venue and DataSource."""
    cessda = STATIC_ORGANISATIONS[0]
    venue_pid_url = normalize_pid_url("ror", cessda["ror"])
    venue = Venue(
        local_identifier=venue_pid_url,
        name=cessda["name"],
        identifiers=[Identifier(value=cessda["ror"], scheme="ror")],
    )

    datasource_base_url = doc.get("_direct_base_url", "").strip()
    datasource_name_modified = URL_TO_DATASOURCE.get(datasource_base_url)

    if not datasource_name_modified:
        distributors = select_preferred_language_entries(doc.get("distributors", []))
        if distributors:
            datasource_name_modified = distributors[0].get("distributor", "")

    if not datasource_name_modified:
        publishers = select_preferred_language_entries(doc.get("publishers", []))
        if publishers:
            datasource_name_modified = publishers[0].get("publisher", "")

    datasource: DataSource | None = None
    if datasource_name_modified:
        datasource_ror_id = resolve_organisation_ror(datasource_name_modified)
        datasource_local_id = resolve_organisation_local_identifier(
            name=datasource_name_modified,
            ror=datasource_ror_id,
        )
        datasource = DataSource(
            local_identifier=datasource_local_id,
            name=datasource_name_modified,
            identifiers=([Identifier(value=datasource_ror_id, scheme="ror")] if datasource_ror_id else None),
        )

    return Biblio(in_=venue, hosting_data_source=datasource)


def _build_funding_organisation(agency_name: str | None) -> OrganisationLite | None:
    """Build the funding organisation for an agency name."""
    if not agency_name:
        return None

    resolved_ror = resolve_organisation_ror(name=agency_name)
    identifiers = [Identifier(value=resolved_ror, scheme="ror")] if resolved_ror else None

    return OrganisationLite(
        local_identifier=resolve_organisation_local_identifier(
            name=agency_name,
            ror=resolved_ror,
        ),
        name=agency_name,
        identifiers=identifiers,
    )


def _collect_funding_entries(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect non-empty grant and funding-agency entries."""
    return [
        entry
        for source in ("grant_numbers", "funding_agencies")
        for entry in doc.get(source, [])
        if entry.get("agency") or entry.get("grant_number")
    ]


def aggregate_funding(doc: dict[str, Any]) -> list[GrantLite] | None:
    """Aggregate funding information."""
    selected = select_preferred_language_entries(_collect_funding_entries(doc))
    funding = []
    seen_keys = set()

    for idx, entry in enumerate(selected, 1):
        agency_name = entry.get("agency")
        grant_number = entry.get("grant_number")

        if not agency_name and not grant_number:
            continue

        dedup_key = grant_number or agency_name
        if dedup_key in seen_keys:
            continue

        seen_keys.add(dedup_key)
        funding.append(
            GrantLite(
                local_identifier=generate_otf_local_identifier("grant", idx),
                grant_number=grant_number,
                funding_agency=_build_funding_organisation(agency_name),
            )
        )

    return funding or None


def _first_metadata_value(
    entries: list[dict[str, Any]],
    field_name: str,
    *,
    language: str | None = None,
) -> str | None:
    """Return the first non-empty metadata value matching the language."""
    for entry in entries:
        if language is not None and entry.get("language") != language:
            continue

        value = entry.get(field_name)
        if value:
            return value

    return None


def _find_data_provider_name(doc: dict[str, Any]) -> str | None:
    """Return the preferred distributor or publisher name or abbreviation."""
    distributors = doc.get("distributors", [])
    publishers = doc.get("publishers", [])
    candidates = (
        _first_metadata_value(distributors, "abbreviation", language="en"),
        _first_metadata_value(distributors, "distributor", language="en"),
        _first_metadata_value(publishers, "abbreviation", language="en"),
        _first_metadata_value(publishers, "publisher", language="en"),
        _first_metadata_value(distributors, "abbreviation"),
        _first_metadata_value(distributors, "distributor"),
        _first_metadata_value(publishers, "abbreviation"),
        _first_metadata_value(publishers, "publisher"),
    )
    return next((candidate for candidate in candidates if candidate), None)


def _find_access_category(
    mappings: dict[str, Any],
    provider_name: str | None,
    description: str | None,
) -> str:
    """Return the mapped access category for an access description."""
    if provider_name not in mappings:
        return "unavailable"

    for section in ("dataRestrctnXPath", "dataAccessAltXPath"):
        for item in mappings[provider_name].get(section, []):
            if item["content"] == description:
                return item["accessCategory"]

    return "unavailable"


def _build_access_rights(
    category: str,
    description: str | None,
) -> dict[str, Any]:
    """Build the access-rights response."""
    if category != "unavailable":
        return {
            "status": category.lower(),
            "description": description,
        }

    if description is not None:
        return {"description": description}

    return {"status": "unavailable"}


def extract_access_rights(doc: dict[str, Any]) -> dict[str, Any]:
    """Extract access rights and map them to a known category where possible."""
    if not os.path.exists(data_access_mapping_file_path):
        response = requests.get(data_access_mapping_file_url, timeout=10)
        with open(
            data_access_mapping_file_path,
            mode="wb",
        ) as data_access_mapping_file:
            data_access_mapping_file.write(response.content)

    with open(data_access_mapping_file_path, "r", encoding="utf-8") as file:
        mappings = json.load(file)

    provider_name = _find_data_provider_name(doc)
    selected_access_entries = select_preferred_language_entries(doc.get("data_access", []))
    access_description = selected_access_entries[0].get("data_access") if selected_access_entries else None
    access_category = _find_access_category(
        mappings,
        provider_name,
        access_description,
    )

    return _build_access_rights(access_category, access_description)


def transform_study_to_skgif_product(doc: dict[str, Any]) -> Product:
    """Transform a study document into an SKG-IF product."""
    identifiers = extract_identifiers(doc)
    titles, abstracts = extract_titles_and_abstracts(doc)
    topics = transform_classifications_to_topics(doc.get("classifications", []))
    contributions = build_contributions(doc)
    dates = extract_dates(doc)
    biblio = build_biblio(doc)
    access_rights = extract_access_rights(doc)
    manifestations = [Manifestation(dates=dates, access_rights=access_rights, biblio=biblio)]
    funding = aggregate_funding(doc)

    return Product(
        local_identifier=generate_study_local_identifier(doc["_aggregator_identifier"]),
        product_type=PRODUCT_TYPE_RESEARCH_DATA,
        identifiers=identifiers,
        titles=titles,
        abstracts=abstracts or None,
        topics=topics or None,
        contributions=contributions,
        manifestations=manifestations,
        funding=funding,
    )
