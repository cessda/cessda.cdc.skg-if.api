# Copyright CESSDA ERIC 2025

# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import time
import requests
from typing import Dict, Any, List, Tuple
from cessda_skgif_api.config_loader import load_config
from cessda_skgif_api.models.skgif import (
    Product,
    Identifier,
    Contribution,
    Person,
    Organisation,
    Agent,
    Manifestation,
    Biblio,
    Venue,
    DataSource,
    Grant,
    Topic,
    Term,
)


config = load_config()
cessda_vocab_api_url = config.cessda_vocab_api_url
cessda_vocab_api_version = config.cessda_vocab_api_version
finto_api_url = config.finto_api_url
data_access_mapping_dir = os.path.dirname(os.path.abspath(__file__))
data_access_mapping_file_path = os.path.join(data_access_mapping_dir, "data_access_mappings.json")
data_access_mapping_file_url = config.data_access_mapping_file_url

# Caching dictionaries
cessda_vocab_cache: Dict[str, Dict[int, Dict[str, Any]]] = {}
finto_cache: Dict[Tuple[str, str], Dict[str, str]] = {}

ROR_LOOKUP = {
    "Finnish Social Science Data Archive": "033003e23",
    "Consortium of European Social Science Data Archives": "02wg9xc72",
}

DATASOURCE_MODIFIED = {"Finnish Social Science Data Archive": "Tampere University. Finnish Social Science Data Archive"}

ALLOWED_IDENTIFIER_TYPES = {
    "arxiv",
    "bibcode",
    "crossref",
    "doi",
    "eissn",
    "handle",
    "isbn",
    "issn",
    "ivoid",
    "lissn",
    "omid",
    "openalex",
    "opendoar",
    "orcid",
    "pmcid",
    "pmid",
    "ror",
    "spase",
    "url",
    "urn",
    "viaf",
    "w3id",
}


def generate_local_id(prefix: str, index: int) -> str:
    """
    Generate a local ID string based on the current time, a prefix, and an index.

    Args:
        prefix (str): A string prefix to include in the ID.
        index (int): An integer index to append to the ID.

    Returns:
        str: A formatted string representing the local ID.
    """
    return f"otf___{int(time.time() * 1000)}___{prefix}-{index}"


def filter_identifiers(raw_identifiers):
    seen = set()
    filtered = []

    # Prioritize English
    english_ids = [i for i in raw_identifiers if i.get("language") == "en"]
    fallback_ids = [i for i in raw_identifiers if i.get("language") != "en"]

    for id_list in [english_ids, fallback_ids]:
        for i in id_list:
            key = (i["agency"], i["identifier"])
            if key not in seen:
                seen.add(key)
                filtered.append(Identifier(value=i["identifier"], scheme=i["agency"]))
    return filtered


def normalize_scheme(scheme: str) -> str:
    if scheme.strip().lower() == "cessda topic classification":
        return "CESSDA_Topic_Classification"
    # TODO Replace spaces with underscore in all schemes
    return scheme.strip()


def load_cessda_vocab(language: str) -> Dict[int, Dict[str, Any]]:
    if language in cessda_vocab_cache:
        return cessda_vocab_cache[language]
    url = f"{cessda_vocab_api_url}/{cessda_vocab_api_version}/{language}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    vocab = {
        item["position"]: {
            "id": item["id"],
            "title": item["title"],
            "notation": item["notation"],
        }
        for item in data
    }
    cessda_vocab_cache[language] = vocab
    return vocab


def search_finto(term: str, lang: str) -> Dict[str, str]:
    key = (term.lower(), lang)
    if key in finto_cache:
        return finto_cache[key]
    url = f"{finto_api_url}&query={term}&lang={lang}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    results = response.json().get("results", [])
    if results:
        result = {
            "id": results[0]["localname"],
            "uri": results[0]["uri"],
            "label": results[0]["prefLabel"],
        }
        finto_cache[key] = result
        return result
    finto_cache[key] = {}
    return {}


def transform_classifications_to_topics(
    classifications: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    metadata_languages = list({c.get("language", "en") for c in classifications})

    cessda_vocab_by_lang = {}
    for lang in metadata_languages:
        try:
            cessda_vocab_by_lang[lang] = load_cessda_vocab(lang)
        except Exception:
            cessda_vocab_by_lang[lang] = {}

    topic_groups = {}
    for c in classifications:
        scheme = normalize_scheme(c.get("system_name", ""))
        uri = c.get("uri", "")
        lang = c.get("language", "en")
        label = c.get("description", "")

        key = None

        if scheme == "CESSDA_Topic_Classification":
            position = None
            for pos, concept in cessda_vocab_by_lang.get(lang, {}).items():
                if concept["title"].lower() == label.lower():
                    position = pos
                    break
            if position is not None:
                key = (scheme, position)
            else:
                key = (scheme, uri, label)

        elif scheme == "OKM":
            finto_result = search_finto(label, lang)
            if finto_result:
                concept_id = finto_result["id"]
                uri = c.get("uri", uri)  # Preserve original URI
                label = c.get("description", label)  # Preserve original label
                key = (scheme, concept_id)
            else:
                key = (scheme, label)

        else:
            key = (scheme, uri, label)

        if key not in topic_groups:
            topic_groups[key] = {"scheme": scheme, "uri": uri, "labels": {}}

        topic_groups[key]["labels"][lang] = label

    topics = []
    for idx, group in enumerate(topic_groups.values(), 1):
        identifier = Identifier(value=group["uri"], scheme=group["scheme"])
        term = Term(
            local_identifier=generate_local_id("topic", idx),
            identifiers=[identifier],
            labels=group["labels"],
        )
        topic = Topic(term=term)
        topics.append(
            {
                "term": {
                    "local_identifier": topic.term.local_identifier,
                    "identifiers": [{"scheme": id.scheme, "value": id.value} for id in topic.term.identifiers],
                    "entity_type": topic.term.entity_type,
                    "labels": topic.term.labels,
                }
            }
        )

    return topics


def transform_study_to_skgif_product(doc: Dict[str, Any]) -> Product:
    """
    Transforms a study document into a SKG-IF Product representation.

    Args:
        doc (Dict[str, Any]): A dictionary containing study information, including identifiers,
                              titles, abstracts, classifications, principal investigators,
                              publication years, collection periods, data access, and funding agencies.

    Returns:
        Product: An instance of the Product class representing the transformed study data.
    """
    identifiers = filter_identifiers(doc.get("identifiers", []))

    titles = {}
    for t in doc.get("study_titles", []):
        lang = t.get("language", "en")
        titles.setdefault(lang, []).append(t["study_title"])

    abstracts = {}
    for a in doc.get("abstracts", []):
        lang = a.get("language", "en")
        abstracts.setdefault(lang, []).append(a["abstract"])

    topics = transform_classifications_to_topics(doc.get("classifications", []))

    # Helper: classify PI type
    def classify_pi(pi):
        title = (pi.get("external_link_title") or "").lower()
        org = pi.get("organization")
        if title == "ror" and org is None:
            return "organisation"
        if org is not None or title == "orcid":
            return "person"
        return "agent"

    # Language-prioritized PI selection
    pis_by_language = {}
    for pi in doc.get("principal_investigators", []):
        lang = pi.get("language", "unknown")
        if lang not in pis_by_language:
            pis_by_language[lang] = []
        pis_by_language[lang].append(pi)

    if "en" in pis_by_language:
        selected_pis = pis_by_language["en"]
    else:
        first_lang = next(iter(pis_by_language))
        selected_pis = pis_by_language[first_lang]

    # Build contributions
    contributions = []
    for idx, pi in enumerate(selected_pis, 1):
        entity_type = classify_pi(pi)
        name = pi["principal_investigator"]
        identifier_value = pi.get("external_link")
        title = (pi.get("external_link_title") or "").lower()
        role = (pi.get("external_link_role") or "").lower()

        # Validate identifier type
        scheme = title if title in ALLOWED_IDENTIFIER_TYPES else None

        # Assign identifiers
        pi_identifiers = None
        org_identifiers = None
        if identifier_value and scheme:
            if role == "affiliation-pid":
                org_identifiers = [Identifier(value=identifier_value, scheme=scheme)]
            else:
                pi_identifiers = [Identifier(value=identifier_value, scheme=scheme)]

        if entity_type == "person":
            person = Person(
                local_identifier=generate_local_id("person", idx),
                name=name,
                identifiers=pi_identifiers,
            )
            declared_affiliations = None
            if pi.get("organization"):
                declared_affiliations = [
                    Organisation(
                        local_identifier=generate_local_id("organisation", idx),
                        name=pi["organization"],
                        identifiers=org_identifiers,
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
            org = Organisation(
                local_identifier=generate_local_id("organisation", idx),
                name=name,
                identifiers=pi_identifiers,
            )
            contributions.append(Contribution(role="author", by=org))

        else:  # agent
            agent = Agent(
                local_identifier=generate_local_id("agent", idx),
                name=name,
                identifiers=pi_identifiers,
            )
            contributions.append(Contribution(role="author", by=agent))

    manifestations = []

    # Dates
    dates = {}
    pub_date = None

    # Try distribution_dates first, but only if it has a usable date
    for item in doc.get("distribution_dates", []):
        pub_date = item.get("distribution_date")
        if pub_date:
            break

    # If not found, try publication_dates
    if not pub_date:
        for item in doc.get("publication_dates", []):
            pub_date = item.get("publication_date")
            if pub_date:
                break

    if pub_date:
        dates["publication"] = [pub_date]  # Wrap in list

    # Deduplicate collection periods by date, prefer English
    collected_periods = {}
    for period in doc.get("collection_periods", []):
        date = period.get("collection_period")
        lang = period.get("language")
        if date:
            if date not in collected_periods or lang == "en":
                collected_periods[date] = lang

    # Already a list of strings
    dates["collected"] = list(collected_periods.keys())

    # Download the mapping file if it doesn't exist
    if not os.path.exists(data_access_mapping_file_path):
        response = requests.get(data_access_mapping_file_url, timeout=10)
        with open(data_access_mapping_file_path, mode="wb") as data_access_mapping_file:
            data_access_mapping_file.write(response.content)

    # Load the mapping file
    with open(data_access_mapping_file_path, "r", encoding="utf-8") as f:
        mappings = json.load(f)

    # Extract distributor abbreviation
    distributor_abbr = doc.get("distributors", [{}])[0].get("abbreviation")

    # Extract access entries
    access_entries = doc.get("data_access", [])

    # Prefer English description
    description = ""
    for entry in access_entries:
        lang = entry.get("language")
        desc = entry.get("data_access")
        if desc:
            if not description or lang == "en":
                description = desc

    # Determine access category using mapping
    access_category = "Uncategorized"
    mapping_sections = ["dataRestrctnXPath", "dataAccessAltXPath"]

    if distributor_abbr in mappings:
        for section in mapping_sections:
            entries = mappings[distributor_abbr].get(section, [])
            for item in entries:
                if item["content"] == description:
                    access_category = item["accessCategory"]
                    break
            if access_category != "Uncategorized":
                break

    # Final access rights dictionary
    access_rights = {"status": access_category.lower(), "description": description}

    # Venue (hardcoded)
    venue_name = "Consortium of European Social Science Data Archives"
    venue = Venue(
        local_identifier=generate_local_id("venue", 1),
        name=venue_name,
        identifiers=[Identifier(value=ROR_LOOKUP[venue_name], scheme="ror")],
    )

    # Hosting data source: prefer English
    distributor_entries = doc.get("distributors", [])
    distributor = None
    for entry in distributor_entries:
        if not distributor or entry.get("language") == "en":
            distributor = entry

    datasource_name = distributor.get("distributor", "") if distributor else ""
    datasource_name_modified = DATASOURCE_MODIFIED.get(datasource_name, datasource_name)
    datasource = DataSource(
        local_identifier=generate_local_id("datasource", 1),
        name=datasource_name_modified,
        identifiers=[Identifier(value=ROR_LOOKUP.get(datasource_name, ""), scheme="ror")],
    )

    biblio = Biblio(in_=venue, hosting_data_source=datasource)

    manifestations.append(Manifestation(dates=dates, access_rights=access_rights, biblio=biblio))

    # Funding
    funding = []
    seen_keys = set()

    combined_sources = []

    for source in ["grant_numbers", "funding_agencies"]:
        for entry in doc.get(source, []):
            agency = entry.get("agency")
            grant_number = entry.get("grant_number")
            language = entry.get("language")
            if agency or grant_number:
                combined_sources.append(
                    {
                        "agency": agency,
                        "grant_number": grant_number,
                        "language": language,
                    }
                )

    english_entries = [g for g in combined_sources if g.get("language") == "en"]
    non_english_entries = [g for g in combined_sources if g.get("language") != "en"]

    if english_entries:
        selected_entries = english_entries
    elif non_english_entries:
        first_lang = non_english_entries[0].get("language")
        selected_entries = [g for g in non_english_entries if g.get("language") == first_lang]
    else:
        selected_entries = []

    for idx, entry in enumerate(selected_entries, 1):
        agency_name = entry.get("agency")
        grant_number = entry.get("grant_number")

        if not agency_name and not grant_number:
            continue

        dedup_key = grant_number if grant_number else agency_name
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        organisation = None
        if agency_name:
            organisation = Organisation(
                local_identifier=generate_local_id("organisation", idx),
                name=agency_name,
            )

        grant_obj = Grant(
            local_identifier=generate_local_id("grant", idx),
            grant_number=grant_number,
            funding_agency=organisation,
        )

        funding.append(grant_obj)

    # Final Product creation
    return Product(
        local_identifier=doc["study_number"],
        product_type="research data",
        identifiers=identifiers,
        titles=titles,
        abstracts=abstracts or None,
        topics=topics or None,
        contributions=contributions or None,
        manifestations=manifestations or None,
        funding=funding or None,
    )
