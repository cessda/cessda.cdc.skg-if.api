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

"""Transforms metadata stored in MongoDB into SKG-IF entities"""

import json
import os
import re
import time
from typing import Dict, Any, List, Tuple, Optional, Union
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


config = load_config()
# api_base_url = config.api_base_url
# api_prefix = config.api_prefix
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
cessda_topic_vocab_cache: Dict[str, Dict[int, Dict[str, Any]]] = {}

ROR_LOOKUP = {
    "Czech Social Science Data Archive": "01snj4592",
    "DANS-KNAW": "008pnp284",
    "DASSI – Data Archive for Social Sciences in Italy": "028znnm42",
    "EKKE. SoDaNet – Greek Research Infrastructure for Social Science": "035hs9g56",
    "FORS – Swiss Centre of Expertise in the Social Sciences": "00weppy16",
    "French National Centre for Scientific Research. PROGEDO": "02feahw73",
    "GESIS – Leibniz-Institute for the Social Sciences": "018afyw53",
    "Lithuanian Data Archive for Social Sciences and Humanities": "00c4rg397",
    "Sciences Po Center for Socio-Political Data": "03aef3108",
    "Sciences Po. Ethnic and Immigrant Minorities Survey Data Network": "05fe7ax82",
    "Sikt": "03zee5r16",
    "Sikt – Norwegian Agency for Shared Services in Education and Research": "03zee5r16",
    "State Archives of Belgium. Social Sciences and Digital Humanities Archive": "04y1ast97",
    "Swedish National Data Service": "00ancw882",
    "Tampere University. Finnish Social Science Data Archive": "033003e23",
    "UK Data Service": "0468x4e75",
    "University College Dublin. Irish Social Science Data Archive": "05m7pjf47",
    "University of Iceland. Icelandic Research Data Service": "01db6h964",
    "University of Ljubljana. Social Science Data Archives": "05njb9z20",
    "University of Vienna. Austrian Social Science Data Archive": "03prydq77",
    "University of Zagreb. Croatian Social Science Data Archive": "00mv6sv71",
}

URL_TO_DATASOURCE = {
    "https://archivdv.soc.cas.cz/oai": "Czech Social Science Data Archive",
    "https://oai-service.labs.dans.knaw.nl/ss/oai": "DANS-KNAW",
    "https://ssh.datastations.nl/oai": "DANS-KNAW",
    "http://oai.unidata.unimib.it/v0/oai": "DASSI – Data Archive for Social Sciences in Italy",
    "https://datacatalogue.sodanet.gr/oai": "EKKE. SoDaNet – Greek Research Infrastructure for Social Science",
    "https://www.swissubase.ch/oai-pmh/v1/oai": "FORS – Swiss Centre of Expertise in the Social Sciences",
    "https://data.progedo.fr/oai": "French National Centre for Scientific Research. PROGEDO",
    "https://dbkapps.gesis.org/dbkoai": "GESIS – Leibniz-Institute for the Social Sciences",
    "https://dataverse-ucd.4science.cloud/oai": "Irish Social Science Data Archive",
    "https://lida.dataverse.lt/oai": "Lithuanian Data Archive for Social Sciences and Humanities",
    "https://data.sciencespo.fr/oai": "Sciences Po Center for Socio-Political Data",
    "https://oai-pmh.ethmigsurveydatahub.eu/oai": "Sciences Po. Ethnic and Immigrant Minorities Survey Data Network",
    "https://colectica-ess-published.nsd.no/oai/request": "Sikt – Norwegian Agency for Shared Services in Education and Research",
    "https://colectica-forskningsdata-published.nsd.no/oai/request": "Sikt – Norwegian Agency for Shared Services in Education and Research",
    "https://www.sodha.be/oai": "State Archives of Belgium. Social Sciences and Digital Humanities Archive",
    "https://api.researchdata.se/oai-pmh": "Swedish National Data Service",
    "https://services.fsd.tuni.fi/v0/oai": "Tampere University. Finnish Social Science Data Archive",
    "https://oai.ukdataservice.ac.uk:8443/oai/provider": "UK Data Service",
    "https://dataverse.rhi.hi.is/oai": "University of Iceland. Icelandic Research Data Service",
    "https://www.adp.fdv.uni-lj.si/v0/oai": "University of Ljubljana. Social Science Data Archives",
    "https://data.aussda.at/oai": "University of Vienna. Austrian Social Science Data Archive",
    "https://data.crossda.hr/oai": "University of Zagreb. Croatian Social Science Data Archive",
}

# Regex for ROR and ORCID

# -----------------------------
# ROR (Crockford Base32)
# -----------------------------
# Allowed letters: a–z excluding i, l, o, u (Crockford Base32), case-insensitive.
# Pattern: 0 + 6 letters/digits + 2 digits (checksum)
_ROR_CORE = r'0[a-hj-km-np-tv-z|0-9]{6}[0-9]{2}'
# Full URL form (with optional trailing slash)
ROR_URL_RE = re.compile(rf'^https?://(?:www\.)?ror\.org/({_ROR_CORE})/?$', re.IGNORECASE)
# Plain code form
ROR_CODE_RE = re.compile(rf'^({_ROR_CORE})$', re.IGNORECASE)

# -----------------------------
# ORCID (ISO/IEC 7064 MOD 11-2)
# -----------------------------
# Canonical code: dddd-dddd-dddd-ddd[0-9X]
# We accept uppercase X (standard) and, optionally, lowercase x by using IGNORECASE.
_ORCID_CORE = r'(?:\d{4}-){3}\d{3}[0-9X]'
# Full URL form (with optional trailing slash)
ORCID_URL_RE = re.compile(rf'^https?://(?:www\.)?orcid\.org/({_ORCID_CORE})/?$', re.IGNORECASE)
# Plain code form
ORCID_CODE_RE = re.compile(rf'^({_ORCID_CORE})$', re.IGNORECASE)

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


JsonObj = Dict[str, Any]
JsonGraph = List[JsonObj]


def wrap_jsonld(data: Union[JsonObj, JsonGraph], meta: Optional[JsonObj] = None) -> JsonObj:
    """
    Wraps array with dictionary in JSON-LD format using SKG-IF context.
    Adds 'meta' before '@graph' if provided.
    """
    # Normalize `data` into a flat list of dicts
    if isinstance(data, dict):
        graph: JsonGraph = [data]
    elif isinstance(data, list):
        graph = data

    wrapped_dict = {
        "@context": [
            skg_if_context,
            skg_if_api_context,
            {"@base": skg_if_cessda_context},
        ]
    }

    if meta is not None:
        wrapped_dict["meta"] = meta

    wrapped_dict["@graph"] = graph

    return wrapped_dict


def generate_local_identifier(prefix: str, index: int) -> str:
    """
    Generate an otf (on-the-fly) identifier string based on the current time, a prefix, and an index.

    Args:
        prefix (str): A string prefix to include in the identifier.
        index (int): An integer index to append to the identifier.

    Returns:
        str: A formatted string representing the local identifier.
    """
    return f"otf___{int(time.time() * 1000)}___{prefix}-{index}"


def generate_product_local_identifier(doc: Dict[str, Any]) -> str:
    """Generate a local identifier with full URL for the Product."""
    # Provide a full URL to the Product in this SKG-IF API instead of link to CDC
    # return f"{api_base_url}/{api_prefix}/products/{doc['_aggregator_identifier']}"

    base_uri = f"{product_base_url}/{doc['_aggregator_identifier']}"

    # Check available languages in study titles
    study_title_langs = {t.get("language") for t in doc.get("study_titles", []) if t.get("language")}

    # If English is available, return base URI
    if "en" in study_title_langs:
        return base_uri

    # Otherwise, append ?lang=<first available>
    fallback_lang = next(iter(study_title_langs), "en")
    return f"{base_uri}?lang={fallback_lang}"


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


def normalize_text(s: Optional[str]) -> str:
    """Normalize text for stable matching/sorting (trim, collapse spaces, casefold)."""
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def transform_classifications_to_topics(
    classifications: List[Dict[str, Any]],
) -> List[TopicLite]:
    """Transform Topic Classifications into Topics using notation for grouping."""
    metadata_languages = sorted({c.get("language", "en") for c in classifications})

    cessda_topic_vocab_by_lang: Dict[str, Dict[str, Any]] = {lang: get_cached_vocab(lang) for lang in metadata_languages}

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
            for cache_notation, concept in cessda_topic_vocab_by_lang.get(lang, {}).items():
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
            topic_groups[key] = {"scheme": scheme, "uri": uri, "labels": {}, "uri_from_api": uri_from_api}

        topic_groups[key]["labels"][lang] = label

    # Build Topic objects
    topics = []
    for idx, key in enumerate(sorted(topic_groups.keys()), 1):
        group = topic_groups[key]
        identifiers = None
        local_id = group["uri_from_api"] if group["uri_from_api"] else generate_local_identifier("topic", idx)
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


def normalize_pid_url(scheme: str, value: str) -> str | None:
    if not scheme or not value:
        return None
    s = scheme.lower().strip()
    v = value.strip()

    if s == "ror":
        # Accept full URL
        m = ROR_URL_RE.match(v)
        if m:
            return f"https://ror.org/{m.group(1).lower()}"
        # Accept plain code
        m = ROR_CODE_RE.match(v)
        if m:
            return f"https://ror.org/{m.group(1).lower()}"
        # Accept "ror:<code>"
        if v.lower().startswith("ror:"):
            code = v.split(":", 1)[1].strip()
            m = ROR_CODE_RE.match(code)
            if m:
                return f"https://ror.org/{m.group(1).lower()}"
        return None

    if s == "orcid":
        m = ORCID_URL_RE.match(v)
        if m:
            return f"https://orcid.org/{m.group(1)}"
        m = ORCID_CODE_RE.match(v)
        if m:
            return f"https://orcid.org/{m.group(1)}"
        return None

    return None


def build_contributions(doc: Dict[str, Any]) -> Optional[List["Contribution"]]:
    """Build contributions from principal investigators with stable local IDs when possible."""
    contributions: List["Contribution"] = []
    selected_pis = select_preferred_language_entries(doc.get("principal_investigators", []))

    for idx, pi in enumerate(selected_pis, 1):
        title = (pi.get("external_link_title") or "").lower()
        org = pi.get("organization")
        entity_type = (
            "organisation" if title == "ror" and org is None else "person" if org or title == "orcid" else "agent"
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

        # Compute canonical URL for use as local_identifier
        canonical_pid_url = normalize_pid_url(scheme, identifier_value) if (identifier_value and scheme) else None

        if entity_type == "person":
            # Prefer ORCID URL if the PI's scheme is orcid
            person_local_id = (
                canonical_pid_url
                if (scheme == "orcid" and canonical_pid_url)
                else generate_local_identifier("person", idx)
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
                aff_pid_url = normalize_pid_url(aff_scheme, aff_value) if (aff_scheme and aff_value) else None
                org_local_id = (
                    aff_pid_url
                    if (aff_scheme == "ror" and aff_pid_url)
                    else generate_local_identifier("organisation", idx)
                )
                declared_affiliations = [
                    OrganisationLite(
                        local_identifier=org_local_id,
                        name=org,
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
            # Prefer ROR URL if scheme is ror
            org_local_id = (
                canonical_pid_url
                if (scheme == "ror" and canonical_pid_url)
                else generate_local_identifier("organisation", idx)
            )
            org_obj = OrganisationLite(
                local_identifier=org_local_id,
                name=name,
                identifiers=pi_identifiers,
            )
            contributions.append(Contribution(role="author", by=org_obj))
        else:
            agent = Agent(
                local_identifier=generate_local_identifier("agent", idx),
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
    venue_pid_url = normalize_pid_url("ror", "02wg9xc72")
    venue = Venue(
        local_identifier=venue_pid_url,
        name="Consortium of European Social Science Data Archives",
        identifiers=[Identifier(value="02wg9xc72", scheme="ror")],
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
        datasource_ror_id = ROR_LOOKUP.get(datasource_name_modified)
        datasource_pid_url = normalize_pid_url("ror", datasource_ror_id) if datasource_ror_id else None
        datasource_local_id = datasource_pid_url if datasource_pid_url else generate_local_identifier("organisation", 1)
        datasource = DataSource(
            local_identifier=datasource_local_id,
            name=datasource_name_modified,
            identifiers=([Identifier(value=datasource_ror_id, scheme="ror")] if datasource_ror_id else None),
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
        organisation = (
            OrganisationLite(
                local_identifier=generate_local_identifier("organisation", idx),
                name=agency_name,
            )
            if agency_name
            else None
        )
        funding.append(
            GrantLite(
                local_identifier=generate_local_identifier("grant", idx),
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
                    (d.get("abbreviation") for d in doc.get("distributors", []) if d.get("abbreviation")),
                    None,
                ),
                # Fallback: first distributor name
                next(
                    (d.get("distributor") for d in doc.get("distributors", []) if d.get("distributor")),
                    None,
                ),
                # Fallback: first publisher abbreviation
                next(
                    (p.get("abbreviation") for p in doc.get("publishers", []) if p.get("abbreviation")),
                    None,
                ),
                # Fallback: first publisher name
                next(
                    (p.get("publisher") for p in doc.get("publishers", []) if p.get("publisher")),
                    None,
                ),
            ]
            if val
        ),
        None,
    )

    # Prefer English description in access entries
    selected_access_entries = select_preferred_language_entries(doc.get("data_access", []))
    access_description = selected_access_entries[0].get("data_access") if selected_access_entries else None

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
    manifestations = [Manifestation(dates=dates, access_rights=access_rights, biblio=biblio)]
    funding = aggregate_funding(doc)
    return Product(
        local_identifier=generate_product_local_identifier(doc),
        product_type="research data",
        identifiers=identifiers,
        titles=titles,
        abstracts=abstracts or None,
        topics=topics or None,
        contributions=contributions,
        manifestations=manifestations,
        funding=funding,
    )
