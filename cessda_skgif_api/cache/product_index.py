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

"""Flattened in-memory index for SKG-IF Products (studies and related publications)"""

import logging
import urllib.parse
from enum import Enum
from collections import defaultdict
from dataclasses import dataclass, field
from cessda_skgif_api.utils.errors import InvalidFilterException
from fastapi import HTTPException
from typing import Any, Dict, List, Optional, Tuple
from cessda_skgif_api.config_loader import load_config
from cessda_skgif_api.utils.helpers import dedupe_preserve_order, first_non_empty, normalize_text, split_search_name
from cessda_skgif_api.utils.identifier_utils import (
    build_publication_identity_key,
    generate_related_publication_local_identifier,
    generate_related_publication_unique_key,
    generate_study_local_identifier,
    normalize_pid_url,
    normalize_product_lookup_identifier,
)

_logger = logging.getLogger(__name__)

config = load_config()
skg_if_cessda_context = config.skg_if_cessda_context


# ============================================================
# Related publication grouping / ids
# ============================================================


def build_related_publication_group_key(pub: Dict[str, Any]) -> tuple[str, ...]:
    """
    Logical grouping key for one publication.

    Grouping follows the same identity rules used elsewhere:
    - identifier (DOI etc.) is preferred
    - URI is next
    - title + year is the fallback
    """
    return build_publication_identity_key([pub])


def group_related_publications(
    entries: Optional[List[Dict[str, Any]]],
) -> List[List[Dict[str, Any]]]:
    grouped: Dict[tuple[str, ...], List[Dict[str, Any]]] = defaultdict(list)

    for pub in entries or []:
        if not any(
            [
                pub.get("related_publication"),
                pub.get("description"),
                pub.get("identifier"),
                pub.get("uri"),
            ]
        ):
            continue

        key = build_related_publication_group_key(pub)

        grouped[key].append(pub)

    return list(grouped.values())


# ============================================================
# Product refs
# ============================================================


@dataclass(slots=True)
class ProductRef:
    product_id: str
    product_type: str = ""

    cited_studies: List[str] = field(default_factory=list)
    cited_by: List[str] = field(default_factory=list)

    # Only for related publications
    publication_key: Optional[str] = None
    relpub_group: Optional[List[Dict[str, Any]]] = None
    relpub_group_key: Optional[Tuple[str, str, str, str, str]] = None

    # Search/filter fields
    titles: List[str] = field(default_factory=list)
    title_abstract_text: List[str] = field(default_factory=list)

    identifiers: List[str] = field(default_factory=list)
    identifier_schemes: List[str] = field(default_factory=list)

    contributor_names: List[str] = field(default_factory=list)
    contributor_local_identifiers: List[str] = field(default_factory=list)
    contributor_identifier_values: List[str] = field(default_factory=list)
    contributor_identifier_schemes: List[str] = field(default_factory=list)

    affiliation_names: List[str] = field(default_factory=list)
    affiliation_local_identifiers: List[str] = field(default_factory=list)
    affiliation_identifier_values: List[str] = field(default_factory=list)
    affiliation_identifier_schemes: List[str] = field(default_factory=list)

    contribution_orcids: List[str] = field(default_factory=list)
    contribution_aff_rors: List[str] = field(default_factory=list)

    funding_grant_numbers: List[str] = field(default_factory=list)

    sort_title: str = ""
    publication_dates: List[str] = field(default_factory=list)


@dataclass(slots=True)
class ProductIndex:
    refs: List[ProductRef]
    ref_by_id: Dict[str, ProductRef]


# ============================================================
# Ref builders
# ============================================================


def build_study_product_ref(doc: Dict[str, Any]) -> ProductRef:
    product_id = generate_study_local_identifier(doc['_aggregator_identifier'])

    titles = dedupe_preserve_order(
        t.get("study_title", "").strip() for t in doc.get("study_titles", []) if t.get("study_title")
    )

    abstracts = dedupe_preserve_order(
        a.get("abstract", "").strip() for a in doc.get("abstracts", []) if a.get("abstract")
    )

    identifiers: List[str] = []
    identifier_schemes: List[str] = []

    for item in doc.get("identifiers", []):
        identifier = (item.get("identifier") or "").strip()
        scheme = (item.get("agency") or "").strip().lower()
        if identifier:
            identifiers.append(identifier)
        if scheme:
            identifier_schemes.append(scheme)

    contributor_names: List[str] = []
    contributor_local_identifiers: List[str] = []
    contributor_identifier_values: List[str] = []
    contributor_identifier_schemes: List[str] = []

    affiliation_names: List[str] = []
    affiliation_local_identifiers: List[str] = []
    affiliation_identifier_values: List[str] = []
    affiliation_identifier_schemes: List[str] = []

    contribution_orcids: List[str] = []
    contribution_aff_rors: List[str] = []

    for pi in doc.get("principal_investigators", []):
        pi_name = (pi.get("principal_investigator") or "").strip()
        org_name = (pi.get("organization") or "").strip()
        external_link = (pi.get("external_link") or "").strip()
        external_link_title = (pi.get("external_link_title") or "").strip().lower()
        external_link_role = (pi.get("external_link_role") or "").strip().lower()

        if pi_name:
            contributor_names.append(pi_name)

        if org_name:
            affiliation_names.append(org_name)

        pid_url = (
            normalize_pid_url(
                external_link_title,
                external_link,
            )
            if external_link and external_link_title
            else None
        )

        if external_link_role != "affiliation-pid":

            if pid_url:
                contributor_local_identifiers.append(pid_url)

            if external_link:
                contributor_identifier_values.append(external_link)

            if external_link_title:
                contributor_identifier_schemes.append(external_link_title)

            if external_link_title == "orcid" and external_link:
                contribution_orcids.append(external_link)
        else:

            if pid_url:
                affiliation_local_identifiers.append(pid_url)

            if external_link:
                affiliation_identifier_values.append(external_link)

            if external_link_title:
                affiliation_identifier_schemes.append(external_link_title)

            if external_link_title == "ror" and external_link:
                contribution_aff_rors.append(external_link)

    funding_grant_numbers = dedupe_preserve_order(
        (entry.get("grant_number") or "").strip() for entry in doc.get("grant_numbers", []) if entry.get("grant_number")
    )

    publication_dates = dedupe_preserve_order(
        (entry.get("distribution_date") or "").strip()
        for entry in doc.get("distribution_dates", [])
        if entry.get("distribution_date")
    )

    sort_title = normalize_text(titles[0] if titles else product_id)

    return ProductRef(
        product_id=product_id,
        product_type="research data",
        titles=titles,
        title_abstract_text=dedupe_preserve_order([*titles, *abstracts]),
        identifiers=dedupe_preserve_order(identifiers),
        identifier_schemes=dedupe_preserve_order(identifier_schemes),
        contributor_names=dedupe_preserve_order(contributor_names),
        contributor_local_identifiers=dedupe_preserve_order(contributor_local_identifiers),
        contributor_identifier_values=dedupe_preserve_order(contributor_identifier_values),
        contributor_identifier_schemes=dedupe_preserve_order(contributor_identifier_schemes),
        affiliation_names=dedupe_preserve_order(affiliation_names),
        affiliation_local_identifiers=dedupe_preserve_order(affiliation_local_identifiers),
        affiliation_identifier_values=dedupe_preserve_order(affiliation_identifier_values),
        affiliation_identifier_schemes=dedupe_preserve_order(affiliation_identifier_schemes),
        contribution_orcids=dedupe_preserve_order(contribution_orcids),
        contribution_aff_rors=dedupe_preserve_order(contribution_aff_rors),
        funding_grant_numbers=funding_grant_numbers,
        sort_title=sort_title,
        publication_dates=publication_dates,
    )


def build_related_publication_ref(
    group: List[Dict[str, Any]],
) -> ProductRef:
    publication_key = generate_related_publication_unique_key(group)

    product_id = generate_related_publication_local_identifier(group)

    titles = dedupe_preserve_order(
        first_non_empty(
            item.get("related_publication"),
            item.get("description"),
        )
        or ""
        for item in group
    )

    descriptions = dedupe_preserve_order(
        (item.get("description") or "").strip() for item in group if item.get("description")
    )

    identifiers: List[str] = []
    identifier_schemes: List[str] = []
    publication_dates: List[str] = []

    for item in group:
        identifier = (item.get("identifier") or "").strip()
        scheme = (item.get("identifier_agency") or "").strip().lower()
        pub_date = (item.get("distribution_date") or "").strip()

        if identifier:
            identifiers.append(identifier)

        if scheme:
            identifier_schemes.append(scheme)

        if pub_date:
            publication_dates.append(pub_date)

    sort_title = normalize_text(titles[0] if titles else product_id)

    return ProductRef(
        product_id=product_id,
        product_type="literature",
        cited_studies=[],
        publication_key=publication_key,
        relpub_group=group,
        relpub_group_key=build_related_publication_group_key(group[0]),
        titles=titles,
        title_abstract_text=dedupe_preserve_order([*titles, *descriptions]),
        identifiers=dedupe_preserve_order(identifiers),
        identifier_schemes=dedupe_preserve_order(identifier_schemes),
        contributor_names=[],
        contributor_local_identifiers=[],
        contributor_identifier_values=[],
        contributor_identifier_schemes=[],
        affiliation_names=[],
        affiliation_local_identifiers=[],
        affiliation_identifier_values=[],
        affiliation_identifier_schemes=[],
        contribution_orcids=[],
        contribution_aff_rors=[],
        funding_grant_numbers=[],
        sort_title=sort_title,
        publication_dates=dedupe_preserve_order(publication_dates),
    )


# ============================================================
# Index builder
# ============================================================


async def build_product_index(collection) -> ProductIndex:
    """
    Build flattened index:
    - one study product per source study
    - one publication product per unique publication
    """

    _logger.info("Product index building...")

    refs: List[ProductRef] = []
    ref_by_id: Dict[str, ProductRef] = {}

    publication_refs: Dict[str, ProductRef] = {}

    projection = {
        "_aggregator_identifier": 1,
        "study_titles": 1,
        "abstracts": 1,
        "identifiers": 1,
        "principal_investigators": 1,
        "grant_numbers": 1,
        "distribution_dates": 1,
        "related_publications": 1,
    }

    async for doc in collection.find({}, projection):

        study_ref = build_study_product_ref(doc)

        refs.append(study_ref)
        ref_by_id[study_ref.product_id] = study_ref

        for group in group_related_publications(doc.get("related_publications", [])):

            publication_key = generate_related_publication_unique_key(group)

            if publication_key not in publication_refs:
                publication_refs[publication_key] = build_related_publication_ref(group)

            publication_ref = publication_refs[publication_key]

            publication_ref.cited_studies.append(doc["_aggregator_identifier"])
            study_ref.cited_by.append(publication_ref.product_id)

    for ref in refs:
        ref.cited_by = dedupe_preserve_order(ref.cited_by)

    for relpub_ref in publication_refs.values():
        relpub_ref.cited_studies = dedupe_preserve_order(relpub_ref.cited_studies)
        refs.append(relpub_ref)
        ref_by_id[relpub_ref.product_id] = relpub_ref

    refs.sort(
        key=lambda ref: (
            ref.sort_title,
            ref.product_id,
        )
    )

    _logger.info(
        "Product index built (%s total products)",
        len(refs),
    )

    return ProductIndex(
        refs=refs,
        ref_by_id=ref_by_id,
    )


# ============================================================
# Filter parsing / matching
# ============================================================


class FilterOp(str, Enum):
    CONTAINS = "contains"
    EXACT = "exact"
    EXISTS = "exists"


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
    description: str = ""


# Keys that should explicitly fail with 422 for now
DISALLOWED_KEYS = {
    "contributions.by.family_name",
    "contributions.by.given_name",
    "funding.local_identifier",
    "funding.identifiers.id",
    "funding.identifiers.scheme",
    "cf.contributions_aff_country",
    "cf.cites_doi",
    "cf.cites_by_doi",
}

# Declarative filter registry
FILTER_SPECS: dict[str, FilterSpec] = {
    "product_type": FilterSpec(
        key="product_type",
        extractor_name="product_type",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
        description="Matches product type such as 'research data' or 'literature'",
    ),
    "identifiers.id": FilterSpec(
        key="identifiers.id",
        extractor_name="identifiers",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT, FilterOp.CONTAINS),
    ),
    "identifiers.scheme": FilterSpec(
        key="identifiers.scheme",
        extractor_name="identifier_schemes",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "contributions.by.local_identifier": FilterSpec(
        key="contributions.by.local_identifier",
        extractor_name="contributor_local_identifiers",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "contributions.by.identifiers.id": FilterSpec(
        key="contributions.by.identifiers.id",
        extractor_name="contributor_identifier_values",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "contributions.by.identifiers.scheme": FilterSpec(
        key="contributions.by.identifiers.scheme",
        extractor_name="contributor_identifier_schemes",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "contributions.by.name": FilterSpec(
        key="contributions.by.name",
        extractor_name="contributor_names",
        default_op=FilterOp.CONTAINS,
        allowed_ops=(FilterOp.CONTAINS, FilterOp.EXACT),
    ),
    "contributions.declared_affiliations.local_identifier": FilterSpec(
        key="contributions.declared_affiliations.local_identifier",
        extractor_name="affiliation_local_identifiers",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "contributions.declared_affiliations.identifiers.id": FilterSpec(
        key="contributions.declared_affiliations.identifiers.id",
        extractor_name="affiliation_identifier_values",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "contributions.declared_affiliations.identifiers.scheme": FilterSpec(
        key="contributions.declared_affiliations.identifiers.scheme",
        extractor_name="affiliation_identifier_schemes",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "contributions.declared_affiliations.name": FilterSpec(
        key="contributions.declared_affiliations.name",
        extractor_name="affiliation_names",
        default_op=FilterOp.CONTAINS,
        allowed_ops=(FilterOp.CONTAINS, FilterOp.EXACT),
    ),
    "funding.grant_number": FilterSpec(
        key="funding.grant_number",
        extractor_name="funding_grant_numbers",
        default_op=FilterOp.CONTAINS,
        allowed_ops=(FilterOp.CONTAINS, FilterOp.EXACT),
    ),
    "cf.search.title": FilterSpec(
        key="cf.search.title",
        extractor_name="titles",
        default_op=FilterOp.CONTAINS,
        allowed_ops=(FilterOp.CONTAINS, FilterOp.EXACT),
    ),
    "cf.search.title_abstract": FilterSpec(
        key="cf.search.title_abstract",
        extractor_name="title_abstract_text",
        default_op=FilterOp.CONTAINS,
        allowed_ops=(FilterOp.CONTAINS,),
    ),
    "cf.contributions_orcid": FilterSpec(
        key="cf.contributions_orcid",
        extractor_name="contribution_orcids",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "cf.contributions_aff_ror": FilterSpec(
        key="cf.contributions_aff_ror",
        extractor_name="contribution_aff_rors",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "cf.cites": FilterSpec(
        key="cf.cites",
        extractor_name="cited_studies",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
    "cf.cited_by": FilterSpec(
        key="cf.cited_by",
        extractor_name="cited_by",
        default_op=FilterOp.EXACT,
        allowed_ops=(FilterOp.EXACT,),
    ),
}


# ---- extractors ----


def extract_product_type(ref: ProductRef) -> List[str]:
    return [ref.product_type] if getattr(ref, "product_type", None) else []


def extract_identifiers(ref: ProductRef) -> List[str]:
    return ref.identifiers


def extract_identifier_schemes(ref: ProductRef) -> List[str]:
    return ref.identifier_schemes


def extract_contributor_local_identifiers(ref: ProductRef) -> List[str]:
    return ref.contributor_local_identifiers


def extract_contributor_identifier_values(ref: ProductRef) -> List[str]:
    return ref.contributor_identifier_values


def extract_contributor_identifier_schemes(ref: ProductRef) -> List[str]:
    return ref.contributor_identifier_schemes


def extract_contributor_names(ref: ProductRef) -> List[str]:
    return ref.contributor_names


def extract_affiliation_local_identifiers(ref: ProductRef) -> List[str]:
    return ref.affiliation_local_identifiers


def extract_affiliation_identifier_values(ref: ProductRef) -> List[str]:
    return ref.affiliation_identifier_values


def extract_affiliation_identifier_schemes(ref: ProductRef) -> List[str]:
    return ref.affiliation_identifier_schemes


def extract_affiliation_names(ref: ProductRef) -> List[str]:
    return ref.affiliation_names


def extract_funding_grant_numbers(ref: ProductRef) -> List[str]:
    return ref.funding_grant_numbers


def extract_titles(ref: ProductRef) -> List[str]:
    return ref.titles


def extract_title_abstract_text(ref: ProductRef) -> List[str]:
    return ref.title_abstract_text


def extract_contribution_orcids(ref: ProductRef) -> List[str]:
    return ref.contribution_orcids


def extract_contribution_aff_rors(ref: ProductRef) -> List[str]:
    return ref.contribution_aff_rors


def extract_cited_studies(ref: ProductRef) -> List[str]:
    return ref.cited_studies


def extract_cited_by(ref: ProductRef) -> List[str]:
    return ref.cited_by


EXTRACTORS = {
    "product_type": extract_product_type,
    "identifiers": extract_identifiers,
    "identifier_schemes": extract_identifier_schemes,
    "contributor_local_identifiers": extract_contributor_local_identifiers,
    "contributor_identifier_values": extract_contributor_identifier_values,
    "contributor_identifier_schemes": extract_contributor_identifier_schemes,
    "contributor_names": extract_contributor_names,
    "affiliation_local_identifiers": extract_affiliation_local_identifiers,
    "affiliation_identifier_values": extract_affiliation_identifier_values,
    "affiliation_identifier_schemes": extract_affiliation_identifier_schemes,
    "affiliation_names": extract_affiliation_names,
    "funding_grant_numbers": extract_funding_grant_numbers,
    "titles": extract_titles,
    "title_abstract_text": extract_title_abstract_text,
    "contribution_orcids": extract_contribution_orcids,
    "contribution_aff_rors": extract_contribution_aff_rors,
    "cited_studies": extract_cited_studies,
    "cited_by": extract_cited_by,
}


# ---- parsing / binding ----


def parse_raw_filter_string(filter_raw: Optional[str]) -> List[RawClause]:

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


def bind_clauses(raw_clauses: List[RawClause]) -> List[BoundClause]:
    """
    Validate raw clauses against supported filter specs.
    """
    bound: List[BoundClause] = []

    for clause in raw_clauses:
        if clause.key in DISALLOWED_KEYS:
            raise InvalidFilterException(
                detail=(
                    f"The filter '{clause.key}' is not supported "
                    f"by this implementation. Valid filters are: "
                    f"{', '.join(FILTER_SPECS)}"
                ),
            )

        spec = FILTER_SPECS.get(clause.key)

        if not spec:
            raise InvalidFilterException(
                detail=(
                    f"The filter '{clause.key}' is not supported "
                    f"by this implementation. Valid filters are: "
                    f"{', '.join(FILTER_SPECS)}"
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


def parse_product_filter_raw(filter_raw: Optional[str]) -> List[BoundClause]:
    raw_clauses = parse_raw_filter_string(filter_raw)
    return bind_clauses(raw_clauses)


# ---- evaluation ----


def _exact_identifier_match(
    values: List[str],
    expected: str,
) -> bool:

    expected_norm = normalize_product_lookup_identifier(expected)

    return any(normalize_product_lookup_identifier(v) == expected_norm for v in values)


def _contains_name_match(
    values: List[str],
    expected: str,
) -> bool:

    expected_parts = split_search_name(expected)

    return any(
        expected_parts.issubset(
            split_search_name(value)
        )
        for value in values
    )


def _contains_match(values: List[str], expected: str) -> bool:
    expected_norm = normalize_text(expected)
    return any(expected_norm in normalize_text(v) for v in values)


def _exact_match(values: List[str], expected: str) -> bool:
    expected_norm = normalize_text(expected)
    return any(normalize_text(v) == expected_norm for v in values)


def evaluate_clause(ref: ProductRef, clause: BoundClause) -> bool:
    extractor = EXTRACTORS[clause.extractor_name]
    values = extractor(ref)

    # wildcard = attribute exists
    if clause.value == "*":
        return any(value not in ("", None) for value in values)

    if clause.op == FilterOp.CONTAINS:

        if clause.key == "contributions.by.name":
            return _contains_name_match(
                values,
                clause.value,
            )

        return _contains_match(
            values,
            clause.value,
        )

    if clause.op == FilterOp.EXACT:
        if clause.key in {"cf.cites", "cf.cited_by"}:
            return _exact_identifier_match(
                values,
                clause.value,
            )

        return _exact_match(
            values,
            clause.value,
        )

    if clause.op == FilterOp.EXISTS:
        return bool(values)

    return False


def match_product_ref(ref: ProductRef, clauses: List[BoundClause]) -> bool:
    """
    AND semantics across clauses.
    """
    return all(evaluate_clause(ref, clause) for clause in clauses)


def filter_product_refs(index: ProductIndex, clauses: List[BoundClause]) -> List[ProductRef]:
    if not clauses:
        return index.refs
    return [ref for ref in index.refs if match_product_ref(ref, clauses)]
