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

"""Generate and normalize identifiers"""

import hashlib
import time
from typing import Any, Dict, List, Tuple
from urllib.parse import unquote, urlparse
from cessda_skgif_api.config_loader import load_config
from cessda_skgif_api.utils.constants import (
    ORCID_CODE_RE,
    ORCID_URL_RE,
    ORGANISATION_ID_RE,
    ORGANISATION_LOCAL_ID_PREFIX,
    PERSON_ID_RE,
    PERSON_LOCAL_ID_PREFIX,
    RELPUB_ID_RE,
    RELPUB_LOCAL_ID_PREFIX,
    ROR_CODE_RE,
    ROR_LOOKUP,
    ROR_URL_RE,
    STUDY_ID_RE,
    STUDY_LOCAL_ID_PREFIX,
)
from cessda_skgif_api.utils.helpers import (
    first_non_empty,
    normalize_ror_lookup_name,
    normalize_text,
)

config = load_config()
product_base_url = config.product_base_url
skg_if_cessda_context = config.skg_if_cessda_context


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


def build_publication_identity_key(
    related_publication_group: List[Dict[str, Any]],
) -> Tuple[str, ...]:
    """
    Prefer stable identifiers over titles.
    """

    first = related_publication_group[0]

    identifier = (first.get("identifier") or "").strip()
    agency = (first.get("identifier_agency") or "").strip().lower()
    uri = (first.get("uri") or "").strip()

    title = normalize_text(
        first_non_empty(
            first.get("related_publication"),
            first.get("description"),
        )
    )

    year = (first.get("distribution_date") or "").strip()

    if identifier:
        return ("identifier", agency, identifier)

    if uri:
        return ("uri", uri)

    return ("title", title, year)


def generate_related_publication_unique_key(
    related_publication_group: List[Dict[str, Any]],
) -> str:
    key = build_publication_identity_key(related_publication_group)

    material = "|".join(key)

    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]

    return digest


def generate_otf_local_identifier(prefix: str, index: int) -> str:
    """
    Generate an otf (on-the-fly) identifier string based on the current time, a prefix, and an index.

    Args:
        prefix (str): A string prefix to include in the identifier.
        index (int): An integer index to append to the identifier.

    Returns:
        str: A formatted string representing the local identifier.
    """
    return f"otf___{int(time.time() * 1000)}___{prefix}-{index}"


def generate_study_local_identifier(study_id: str) -> str:
    """Generate a local identifier with full URL for the study Product."""
    return f"{skg_if_cessda_context}{STUDY_LOCAL_ID_PREFIX}{study_id}"


def generate_related_publication_local_identifier(
    related_publication_group: list[dict[str, Any]],
) -> str:
    """Generate a local identifier with full URL for the related publication Product."""
    first = related_publication_group[0]

    uri = (first.get("uri") or "").strip()

    if uri.startswith(("http://", "https://")):
        return uri

    identifier = (first.get("identifier") or "").strip()
    agency = (first.get("identifier_agency") or "").strip().lower()

    if identifier and agency == "doi":
        return f"https://doi.org/{identifier}"

    return (
        f"{skg_if_cessda_context}"
        f"{RELPUB_LOCAL_ID_PREFIX}"
        f"{generate_related_publication_unique_key(related_publication_group)}"
    )


def extract_study_id(local_identifier: str) -> str:
    return local_identifier.rsplit("_", 1)[-1]


def normalize_product_lookup_identifier(identifier: str) -> str:
    identifier = unquote(identifier).strip()

    # Fix URLs that lost a slash in FastAPI path params
    if identifier.startswith("https:/") and not identifier.startswith("https://"):
        identifier = identifier.replace("https:/", "https://", 1)

    if identifier.startswith("http:/") and not identifier.startswith("http://"):
        identifier = identifier.replace("http:/", "http://", 1)

    # Already a canonical w3id identifier
    if identifier.startswith(skg_if_cessda_context):
        return identifier

    # CDC URL
    if identifier.startswith(product_base_url):
        path_parts = [p for p in urlparse(identifier).path.split("/") if p]

        if path_parts:
            identifier = path_parts[-1]

    # Raw study hash
    if STUDY_ID_RE.match(identifier):
        return f"{skg_if_cessda_context}" f"{STUDY_LOCAL_ID_PREFIX}" f"{identifier}"

    # Raw relpub hash
    if RELPUB_ID_RE.match(identifier):
        return f"{skg_if_cessda_context}" f"{RELPUB_LOCAL_ID_PREFIX}" f"{identifier}"

    # Prefixed study identifier
    if identifier.startswith(STUDY_LOCAL_ID_PREFIX):
        return f"{skg_if_cessda_context}{identifier}"

    # Prefixed relpub identifier
    if identifier.startswith(RELPUB_LOCAL_ID_PREFIX):
        return f"{skg_if_cessda_context}{identifier}"

    # Anything else (DOI, URN, etc.) is assumed to already be the canonical identifier
    return identifier


def generate_stable_local_identifier(
    prefix: str,
    *identity_parts: str,
) -> str:
    """
    Generate a deterministic SKG-IF local identifier.

    Empty identity parts are ignored and remaining values are normalised
    before hashing.
    """
    normalized_parts = [
        normalize_text(part) for part in identity_parts if part and normalize_text(part)
    ]

    if not normalized_parts:
        raise ValueError("At least one non-empty identity value is required")

    material = "|".join([prefix, *normalized_parts])
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]

    return f"{skg_if_cessda_context}{prefix}{digest}"


def generate_person_local_identifier(
    name: str,
    orcid: str | None = None,
) -> str:
    """
    Prefer an ORCID URL. Otherwise generate a deterministic identifier
    from the person's normalised name.
    """
    if orcid:
        canonical_orcid = normalize_pid_url("orcid", orcid)
        if canonical_orcid:
            return canonical_orcid

    return generate_stable_local_identifier(
        PERSON_LOCAL_ID_PREFIX,
        name,
    )


def generate_organisation_local_identifier(
    name: str,
    ror: str | None = None,
) -> str:
    """
    Prefer a ROR URL. Otherwise generate a deterministic identifier
    from the organisation's normalised name.
    """
    if ror:
        canonical_ror = normalize_pid_url("ror", ror)
        if canonical_ror:
            return canonical_ror

    return generate_stable_local_identifier(
        ORGANISATION_LOCAL_ID_PREFIX,
        name,
    )


def resolve_organisation_local_identifier(
    name: str,
    ror: str | None = None,
) -> str:
    """
    Resolve an organisation identifier using:
    1. explicit ROR
    2. ROR alias lookup
    3. generated local identifier
    """
    resolved_ror = ror or ROR_LOOKUP.get(normalize_ror_lookup_name(name))

    return generate_organisation_local_identifier(
        name=name,
        ror=resolved_ror,
    )


def resolve_organisation_ror(
    name: str,
    ror: str | None = None,
) -> str | None:
    return ror or ROR_LOOKUP.get(normalize_ror_lookup_name(name))


def normalize_agent_lookup_identifier(
    identifier: str,
    entity_type: str,
) -> str:
    """
    Normalise Person and Organisation endpoint identifiers.

    Supports:
    - full ORCID and ROR URLs
    - raw ORCID and ROR values
    - full CESSDA SKG-IF identifiers
    - prefixed local identifiers
    - raw generated hashes
    """
    identifier = unquote(identifier).strip()

    if identifier.startswith("https:/") and not identifier.startswith("https://"):
        identifier = identifier.replace("https:/", "https://", 1)

    if identifier.startswith("http:/") and not identifier.startswith("http://"):
        identifier = identifier.replace("http:/", "http://", 1)

    if identifier.startswith(skg_if_cessda_context):
        return identifier

    if entity_type == "person":
        canonical_orcid = normalize_pid_url("orcid", identifier)
        if canonical_orcid:
            return canonical_orcid

        if PERSON_ID_RE.fullmatch(identifier):
            return (
                f"{skg_if_cessda_context}" f"{PERSON_LOCAL_ID_PREFIX}" f"{identifier}"
            )

        if identifier.startswith(PERSON_LOCAL_ID_PREFIX):
            return f"{skg_if_cessda_context}{identifier}"

    if entity_type == "organisation":
        canonical_ror = normalize_pid_url("ror", identifier)
        if canonical_ror:
            return canonical_ror

        if ORGANISATION_ID_RE.fullmatch(identifier):
            return (
                f"{skg_if_cessda_context}"
                f"{ORGANISATION_LOCAL_ID_PREFIX}"
                f"{identifier}"
            )

        if identifier.startswith(ORGANISATION_LOCAL_ID_PREFIX):
            return f"{skg_if_cessda_context}{identifier}"

    return identifier
