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

"""Transforms metadata of studies stored in MongoDB into SKG-IF Products"""

import json
import os
from typing import Dict, Any, List, Tuple, Optional
import requests
from cessda_skgif_api.config_loader import load_config
from cessda_skgif_api.models.skgif import (
    Product,
    Identifier,
    Contribution,
    PersonLite,
    OrganisationLite,
    Agent,
    Manifestation,
    Biblio,
    Venue,
    DataSource,
    GrantLite,
    TopicLite,
    Term,
)
from cessda_skgif_api.cache.cessda_topic_vocab import get_cached_vocab
from cessda_skgif_api.utils.constants import (
    ALLOWED_IDENTIFIER_TYPES,
    ROR_LOOKUP,
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
data_access_mapping_file_path = os.path.join(
    data_access_mapping_dir, "data_access_mappings.json"
)
data_access_mapping_file_url = config.data_access_mapping_file_url

# Caching dictionaries
cessda_topic_vocab_cache: Dict[str, Dict[int, Dict[str, Any]]] = {}


def select_preferred_language_entries(
    entries: List[Dict[str, Any]], preferred_lang: str = "en"
) -> List[Dict[str, Any]]:
    """
    Select entries in preferred language if available, otherwise fallback to first available language group.
    """
    if not entries:
        return []

    grouped_by_lang = {}
    for entry in entries:
        lang = entry.get("language", "unknown")
        grouped_by_lang.setdefault(lang, []).append(entry)

    if preferred_lang in grouped_by_lang:
        return grouped_by_lang[preferred_lang]

    # Fallback to first available language group
    first_lang = next(iter(grouped_by_lang))
    return grouped_by_lang[first_lang]


def normalize_scheme(scheme: str) -> str:
    """Normalize scheme by replacing spaces with underscores"""
    if scheme:
        # Harmonize CESSDA Topic Classification capitalization
        if scheme.strip().lower() == "cessda topic classification":
            return "CESSDA_Topic_Classification"
        return scheme.replace(" ", "_")
    return None


def transform_classifications_to_topics(
    classifications: List[Dict[str, Any]],
) -> List[TopicLite]:
    """Transform Topic Classifications into Topics using notation for grouping."""
    metadata_languages = sorted({c.get("language", "en") for c in classifications})

    cessda_topic_vocab_by_lang: Dict[str, Dict[str, Any]] = {
        lang: get_cached_vocab(lang) for lang in metadata_languages
    }

    topic_groups = {}
    for c in classifications:
        scheme = normalize_scheme(c.get("system_name", None))
        uri = c.get("uri", "")
        lang = c.get("language", "en")
        label = c.get("description", "")
        # URI from API for local_identifier
        uri_from_api = None

        key = None
        notation = None
        if scheme == "CESSDA_Topic_Classification":
            for cache_notation, concept in cessda_topic_vocab_by_lang.get(
                lang, {}
            ).items():
                # Check cache for title matching label or notation matching classification
                if (concept["title"].lower() == label.lower()) or (
                    c.get("classification") and cache_notation == c["classification"]
                ):
                    notation = cache_notation
                    uri_from_api = concept["uri"]
                    break

            # Fallback to normalized label
            key = (scheme, notation or normalize_text(label) or "")
        else:
            # Not CESSDA Topic Classification CV: unique key per classification (no merging)
            key = (scheme or "", uri or "", normalize_text(label) or "")

        if key not in topic_groups:
            topic_groups[key] = {
                "scheme": scheme,
                "uri": uri,
                "labels": {},
                "uri_from_api": uri_from_api,
            }

        topic_groups[key]["labels"][lang] = label

    # Build Topic objects
    topics = []
    for idx, key in enumerate(sorted(topic_groups.keys()), 1):
        group = topic_groups[key]
        identifiers = None
        local_id = (
            group["uri_from_api"]
            if group["uri_from_api"]
            else generate_otf_local_identifier("topic", idx)
        )
        if group.get("scheme") and group.get("uri"):
            identifiers = [Identifier(value=group["uri"], scheme=group["scheme"])]
        term = Term(
            local_identifier=local_id,
            identifiers=identifiers,
            labels=group["labels"],
        )
        topics.append(TopicLite(term=term))

    return topics


def extract_identifiers(doc: Dict[str, Any]) -> List[Identifier]:
    """Extract identifiers from the document, preferring English but including all unique ones.
    Only include identifiers where both 'agency' and 'identifier' are present.
    """
    raw_identifiers = doc.get("identifiers", [])
    seen = set()
    filtered = []

    english_ids = [i for i in raw_identifiers if i.get("language") == "en"]
    fallback_ids = [i for i in raw_identifiers if i.get("language") != "en"]

    for id_list in [english_ids, fallback_ids]:
        for i in id_list:
            agency = i.get("agency")
            identifier = i.get("identifier")

            # Skip if either is missing
            if not agency or not identifier:
                continue

            key = (agency, identifier)
            if key not in seen:
                seen.add(key)
                filtered.append(Identifier(value=identifier, scheme=agency))

    return filtered if filtered else None


def extract_titles_and_abstracts(
    doc: Dict[str, Any],
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Extract titles and abstracts grouped by language."""
    titles, abstracts = {}, {}
    for t in doc.get("study_titles", []):
        lang = t.get("language", "en")
        titles.setdefault(lang, []).append(t["study_title"])
    for a in doc.get("abstracts", []):
        lang = a.get("language", "en")
        abstracts.setdefault(lang, []).append(a["abstract"])
    return titles, abstracts


def build_contributions(doc: Dict[str, Any]) -> Optional[List["Contribution"]]:
    """Build contributions from principal investigators with stable local IDs when possible."""
    contributions: List["Contribution"] = []
    selected_pis = select_preferred_language_entries(
        doc.get("principal_investigators", [])
    )

    for idx, pi in enumerate(selected_pis, 1):
        title = (pi.get("external_link_title") or "").lower()
        org = pi.get("organization")
        entity_type = (
            "organisation"
            if title == "ror" and org is None
            else "person" if org or title == "orcid" else "agent"
        )

        name = pi.get("principal_investigator")
        # Get name from organization if it's actually None after trying to get from PI
        if not name:
            name = pi.get("organization")
            entity_type = "organisation"
        # If name is still empty, skip this PI
        if not name:
            continue

        identifier_value = pi.get("external_link")
        role = (pi.get("external_link_role") or "").lower()
        scheme = title if title in ALLOWED_IDENTIFIER_TYPES else None

        pi_identifiers = None
        org_identifiers = None
        if identifier_value and scheme:
            if role == "affiliation-pid":
                org_identifiers = [Identifier(value=identifier_value, scheme=scheme)]
            else:
                pi_identifiers = [Identifier(value=identifier_value, scheme=scheme)]

        if entity_type == "person":
            # Prefer ORCID URL if the PI's scheme is orcid
            person_orcid = (
                identifier_value
                if scheme == "orcid" and role != "affiliation-pid"
                else None
            )
            person_local_id = generate_person_local_identifier(
                name=name,
                orcid=person_orcid,
            )
            person = PersonLite(
                local_identifier=person_local_id,
                name=name,
                identifiers=pi_identifiers,
            )

            # Prefer ROR URL as local id if it exists for the affiliation
            declared_affiliations = None
            if org:
                aff_scheme = scheme if role == "affiliation-pid" else None
                aff_value = identifier_value if role == "affiliation-pid" else None
                resolved_ror = resolve_organisation_ror(
                    name=org,
                    ror=aff_value if aff_scheme == "ror" else None,
                )
                org_local_id = resolve_organisation_local_identifier(
                    name=org,
                    ror=resolved_ror,
                )
                affiliation_identifiers = list(org_identifiers or [])
                if resolved_ror and not any(
                    i.scheme == "ror" for i in affiliation_identifiers
                ):
                    affiliation_identifiers.append(
                        Identifier(
                            value=resolved_ror,
                            scheme="ror",
                        )
                    )
                declared_affiliations = [
                    OrganisationLite(
                        local_identifier=org_local_id,
                        name=org,
                        identifiers=affiliation_identifiers or None,
                    )
                ]

            contributions.append(
                Contribution(
                    role="author",
                    by=person,
                    declared_affiliations=declared_affiliations,
                )
            )
        elif entity_type == "organisation":
            resolved_ror = resolve_organisation_ror(
                name=name,
                ror=identifier_value if scheme == "ror" else None,
            )
            org_local_id = resolve_organisation_local_identifier(
                name=name,
                ror=resolved_ror,
            )
            organisation_identifiers = list(pi_identifiers or [])
            if resolved_ror and not any(
                i.scheme == "ror"
                for i in organisation_identifiers
            ):
                organisation_identifiers.append(
                    Identifier(
                        value=resolved_ror,
                        scheme="ror",
                    )
                )
            org_obj = OrganisationLite(
                local_identifier=org_local_id,
                name=name,
                identifiers=organisation_identifiers or None,
            )
            contributions.append(Contribution(role="author", by=org_obj))
        else:
            agent = Agent(
                local_identifier=generate_otf_local_identifier("agent", idx),
                name=name,
                identifiers=pi_identifiers,
            )
            contributions.append(Contribution(role="author", by=agent))

    return contributions or None


def extract_dates(doc: Dict[str, Any]) -> Dict[str, List[str]]:
    """Extract publication and collection dates."""
    dates = {}
    pub_date = None
    for item in doc.get("distribution_dates", []):
        pub_date = item.get("distribution_date")
        if pub_date:
            break
    if not pub_date:
        for item in doc.get("publication_dates", []):
            pub_date = item.get("publication_date")
            if pub_date:
                break
    if pub_date:
        dates["publication"] = [pub_date]
    collected_periods = {}
    for period in doc.get("collection_periods", []):
        date = period.get("collection_period")
        lang = period.get("language")
        if date:
            if date not in collected_periods or lang == "en":
                collected_periods[date] = lang
    if collected_periods:
        dates["collected"] = list(collected_periods.keys())
    return dates if dates else None


def build_biblio(doc: Dict[str, Any]) -> Biblio:
    """Build Biblio object with Venue and DataSource.
    Tries base URL → distributor → publisher for datasource name.
    If all fail, datasource is None.
    """
    cessda = STATIC_ORGANISATIONS[0]

    venue_pid_url = normalize_pid_url("ror", cessda["ror"])

    venue = Venue(
        local_identifier=venue_pid_url,
        name=cessda["name"],
        identifiers=[
            Identifier(
                value=cessda["ror"],
                scheme="ror",
            )
        ],
    )

    # Try base URL first
    datasource_base_url = doc.get("_direct_base_url", "").strip()
    datasource_name_modified = URL_TO_DATASOURCE.get(datasource_base_url)

    # If not found, try distributor
    if not datasource_name_modified:
        distributors = select_preferred_language_entries(doc.get("distributors", []))
        if distributors:
            datasource_name_modified = distributors[0].get("distributor", "")

    # If still not found, try publisher
    if not datasource_name_modified:
        publishers = select_preferred_language_entries(doc.get("publishers", []))
        if publishers:
            datasource_name_modified = publishers[0].get("publisher", "")

    # If still empty, datasource = None
    datasource: Optional[DataSource] = None
    if datasource_name_modified:
        datasource_ror_id = resolve_organisation_ror(
            datasource_name_modified
        )
        datasource_local_id = resolve_organisation_local_identifier(
            name=datasource_name_modified,
            ror=datasource_ror_id,
        )
        datasource = DataSource(
            local_identifier=datasource_local_id,
            name=datasource_name_modified,
            identifiers=(
                [Identifier(value=datasource_ror_id, scheme="ror")]
                if datasource_ror_id
                else None
            ),
        )

    return Biblio(in_=venue, hosting_data_source=datasource)


def aggregate_funding(doc: Dict[str, Any]) -> List[GrantLite]:
    """Aggregate funding information."""
    funding, seen_keys = [], set()
    combined = []
    for source in ["grant_numbers", "funding_agencies"]:
        for entry in doc.get(source, []):
            if entry.get("agency") or entry.get("grant_number"):
                combined.append(entry)
    selected = select_preferred_language_entries(combined)
    for idx, entry in enumerate(selected, 1):
        agency_name = entry.get("agency")
        grant_number = entry.get("grant_number")
        if not agency_name and not grant_number:
            continue
        dedup_key = grant_number or agency_name
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        organisation = None

        if agency_name:
            resolved_ror = resolve_organisation_ror(
                name=agency_name,
            )

            funding_identifiers = []

            if resolved_ror:
                funding_identifiers.append(
                    Identifier(
                        value=resolved_ror,
                        scheme="ror",
                    )
                )

            organisation = OrganisationLite(
                local_identifier=resolve_organisation_local_identifier(
                    name=agency_name,
                    ror=resolved_ror,
                ),
                name=agency_name,
                identifiers=funding_identifiers or None,
            )
        funding.append(
            GrantLite(
                local_identifier=generate_otf_local_identifier("grant", idx),
                grant_number=grant_number,
                funding_agency=organisation,
            )
        )
    return funding or None


def extract_access_rights(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Extract access rights and try to map it to 'open' or 'restricted' if possible."""
    # Download the mapping file if it doesn't exist
    if not os.path.exists(data_access_mapping_file_path):
        response = requests.get(data_access_mapping_file_url, timeout=10)
        with open(data_access_mapping_file_path, mode="wb") as data_access_mapping_file:
            data_access_mapping_file.write(response.content)

    # Load the mapping file
    with open(data_access_mapping_file_path, "r", encoding="utf-8") as f:
        mappings = json.load(f)

    # Extract distributor abbreviation
    distributor_abbr = next(
        (
            val
            for val in [
                # Prefer English distributor abbreviation
                next(
                    (
                        d.get("abbreviation")
                        for d in doc.get("distributors", [])
                        if d.get("language") == "en" and d.get("abbreviation")
                    ),
                    None,
                ),
                # Then English distributor name
                next(
                    (
                        d.get("distributor")
                        for d in doc.get("distributors", [])
                        if d.get("language") == "en" and d.get("distributor")
                    ),
                    None,
                ),
                # Then English publisher abbreviation
                next(
                    (
                        p.get("abbreviation")
                        for p in doc.get("publishers", [])
                        if p.get("language") == "en" and p.get("abbreviation")
                    ),
                    None,
                ),
                # Then English publisher name
                next(
                    (
                        p.get("publisher")
                        for p in doc.get("publishers", [])
                        if p.get("language") == "en" and p.get("publisher")
                    ),
                    None,
                ),
                # Fallback: first distributor abbreviation
                next(
                    (
                        d.get("abbreviation")
                        for d in doc.get("distributors", [])
                        if d.get("abbreviation")
                    ),
                    None,
                ),
                # Fallback: first distributor name
                next(
                    (
                        d.get("distributor")
                        for d in doc.get("distributors", [])
                        if d.get("distributor")
                    ),
                    None,
                ),
                # Fallback: first publisher abbreviation
                next(
                    (
                        p.get("abbreviation")
                        for p in doc.get("publishers", [])
                        if p.get("abbreviation")
                    ),
                    None,
                ),
                # Fallback: first publisher name
                next(
                    (
                        p.get("publisher")
                        for p in doc.get("publishers", [])
                        if p.get("publisher")
                    ),
                    None,
                ),
            ]
            if val
        ),
        None,
    )

    # Prefer English description in access entries
    selected_access_entries = select_preferred_language_entries(
        doc.get("data_access", [])
    )
    access_description = (
        selected_access_entries[0].get("data_access")
        if selected_access_entries
        else None
    )

    # Determine access category using mapping
    access_category = "unavailable"
    mapping_sections = ["dataRestrctnXPath", "dataAccessAltXPath"]

    if distributor_abbr in mappings:
        for section in mapping_sections:
            entries = mappings[distributor_abbr].get(section, [])
            for item in entries:
                if item["content"] == access_description:
                    access_category = item["accessCategory"]
                    break
            if access_category != "unavailable":
                break

    access_rights = {
        "status": access_category.lower(),
        "description": access_description,
    }
    # If access category is "unavailable", only add description if possible, otherwise add status only
    if access_category == "unavailable":
        if access_description is not None:
            access_rights = {"description": access_description}
        else:
            access_rights = {"status": access_category.lower()}

    return access_rights


def transform_study_to_skgif_product(doc: Dict[str, Any]) -> Product:
    """Main transformer function calling helpers."""
    identifiers = extract_identifiers(doc)
    titles, abstracts = extract_titles_and_abstracts(doc)
    topics = transform_classifications_to_topics(doc.get("classifications", []))
    contributions = build_contributions(doc)
    dates = extract_dates(doc)
    biblio = build_biblio(doc)
    access_rights = extract_access_rights(doc)
    manifestations = [
        Manifestation(dates=dates, access_rights=access_rights, biblio=biblio)
    ]
    funding = aggregate_funding(doc)
    return Product(
        local_identifier=generate_study_local_identifier(doc["_aggregator_identifier"]),
        product_type="research data",
        identifiers=identifiers,
        titles=titles,
        abstracts=abstracts or None,
        topics=topics or None,
        contributions=contributions,
        manifestations=manifestations,
        funding=funding,
    )
