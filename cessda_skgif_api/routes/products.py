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

"""Handles the functionality of Product endpoints"""

import asyncio
import logging
from typing import Any, Dict, List, Set
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from cessda_skgif_api.config_loader import load_config
from cessda_skgif_api.cache.cessda_topic_vocab import load_cessda_topic_vocab
from cessda_skgif_api.cache.product_index import (
    ProductIndex,
    ProductRef,
    build_product_index,
    build_related_publication_group_key,
    filter_product_refs,
    group_related_publications,
    parse_product_filter_raw,
)
from cessda_skgif_api.db.mongodb import get_collection
from cessda_skgif_api.utils.helpers import wrap_jsonld
from cessda_skgif_api.routes.common import (
    Pagination,
    build_meta,
    build_single_entity_meta,
    build_url,
    canonicalize_filter_for_url,
    get_raw_query_param,
    not_found_response,
)
from cessda_skgif_api.transformers.related_publication_transformer import (
    transform_related_publication_to_skgif_product,
)
from cessda_skgif_api.transformers.study_transformer import transform_study_to_skgif_product
from cessda_skgif_api.utils.identifier_utils import (
    extract_study_id,
    generate_study_local_identifier,
    normalize_product_lookup_identifier,
)

router = APIRouter()

_logger = logging.getLogger(__name__)

config = load_config()
product_base_url = config.product_base_url


def extract_languages_from_doc(doc: Dict[str, Any]) -> Set[str]:
    """Pull languages from classifications; default to 'en' when absent."""
    classifications = doc.get("classifications", []) or []
    langs = {c.get("language", "en") for c in classifications if isinstance(c, dict)}
    return {lang for lang in langs if isinstance(lang, str) and lang}


async def ensure_product_index(request: Request) -> ProductIndex:
    """
    Use startup-built product index if present.
    Also supports lazy build if startup has not created it yet.
    """
    if getattr(request.app.state, "product_index", None) is not None:
        return request.app.state.product_index

    if not hasattr(request.app.state, "product_index_lock"):
        request.app.state.product_index_lock = asyncio.Lock()

    async with request.app.state.product_index_lock:
        if getattr(request.app.state, "product_index", None) is None:
            collection = get_collection(request)
            request.app.state.product_index = await build_product_index(collection)

    return request.app.state.product_index


async def fetch_docs_for_refs(
    request: Request,
    refs: List[ProductRef],
) -> Dict[str, Dict[str, Any]]:
    """
    Fetch study documents needed to materialise study products.
    Related publications do not require Mongo lookups.
    """

    collection = get_collection(request)

    study_ids = sorted({extract_study_id(ref.product_id) for ref in refs if ref.product_type == "research data"})

    docs_by_id: Dict[str, Dict[str, Any]] = {}

    if not study_ids:
        return docs_by_id

    cursor = collection.find({"_aggregator_identifier": {"$in": study_ids}})

    async for doc in cursor:
        docs_by_id[doc["_aggregator_identifier"]] = doc

    return docs_by_id


def materialise_product_from_ref(ref: ProductRef, doc: Dict[str, Any]):
    """
    Turn one ProductRef + source study doc into a full SKG-IF product
    """
    if ref.product_type == "research data":
        return transform_study_to_skgif_product(doc)

    if ref.product_type == "literature":
        for group in group_related_publications(doc.get("related_publications", [])):
            if build_related_publication_group_key(group[0]) == ref.relpub_group_key:
                return transform_related_publication_to_skgif_product(doc, group)

        raise HTTPException(status_code=404, detail="Related publication not found in parent study")

    raise HTTPException(status_code=500, detail=f"Unknown product type: {ref.product_type}")


@router.get("")
async def get_products(
    request: Request,
    pagination: Pagination = Depends(),
    _filter: str = Query(
        None,
        alias="filter",
        description="Filter for products. Format: `contributions.by.name:<name>,cf.search.title:<title>`",
    ),
):
    """
    Returns a paginated list of SKG-IF products.
    """

    query_params = dict(request.query_params)
    changed = False

    if "page" not in query_params:
        query_params["page"] = str(pagination.page)
        changed = True

    if "page_size" not in query_params:
        query_params["page_size"] = str(pagination.page_size)
        changed = True

    if changed and "text/html" in request.headers.get("accept", ""):
        filter_raw = get_raw_query_param(request, "filter")

        filter_for_url = canonicalize_filter_for_url(filter_raw)

        url = build_url(
            "products",
            params={
                "filter": filter_for_url,
                "page": str(pagination.page),
                "page_size": str(pagination.page_size),
            },
            raw_params={"filter"},
        )

        return RedirectResponse(
            url=url,
            status_code=302,
        )

    filter_raw = get_raw_query_param(
        request,
        "filter",
    )

    clauses = parse_product_filter_raw(filter_raw)

    index = await ensure_product_index(request)

    matched_refs = filter_product_refs(
        index,
        clauses,
    )

    total_count = len(matched_refs)

    filter_for_meta = canonicalize_filter_for_url(
        filter_raw,
    )

    meta = build_meta(
        "products",
        filter_for_meta,
        pagination,
        total_count,
    )

    if total_count == 0:
        return not_found_response(meta)

    page_refs = matched_refs[pagination.offset : pagination.offset + pagination.limit]

    # Only studies require fetching from Mongo
    study_refs = [ref for ref in page_refs if ref.product_type == "research data"]

    docs_by_id = await fetch_docs_for_refs(
        request,
        study_refs,
    )

    langs_needed: Set[str] = set()

    for doc in docs_by_id.values():
        langs_needed.update(extract_languages_from_doc(doc))

    if langs_needed:
        await asyncio.gather(*(load_cessda_topic_vocab(lang) for lang in langs_needed))

    results = []

    for ref in page_refs:

        try:

            #
            # Studies
            #
            if ref.product_type == "research data":

                doc = docs_by_id.get(extract_study_id(ref.product_id))

                if not doc:
                    continue

                product = materialise_product_from_ref(
                    ref,
                    doc,
                )

            #
            # Related publications
            #
            elif ref.product_type == "literature":
                product = transform_related_publication_to_skgif_product(
                    related_publication_group=ref.relpub_group,
                    cited_studies=[generate_study_local_identifier(study_id) for study_id in ref.cited_studies],
                )

            else:
                continue

            results.append(
                product.model_dump(
                    by_alias=True,
                    exclude_none=True,
                )
            )

        except Exception as exc:

            _logger.exception(
                "Error transforming product %s: %s",
                ref.product_id,
                exc,
            )

    jsonld_products = wrap_jsonld(
        data=results,
        meta=meta,
    )

    return JSONResponse(content=jsonld_products)


@router.get("/{local_identifier:path}")
async def get_product_by_id(
    request: Request,
    local_identifier: str,
):
    """
    Returns a single SKG-IF product by identifier.

    Supports:
    - study products
    - related publication products
    """

    normalized_id = normalize_product_lookup_identifier(local_identifier)

    index = await ensure_product_index(request)

    ref = index.ref_by_id.get(normalized_id)

    if ref is None:
        return not_found_response(
            build_single_entity_meta(
                normalized_id,
            ),
        )

    # Find study product in Mongo
    if ref.product_type == "research data":
        study_id = extract_study_id(normalized_id)

        collection = get_collection(request)

        document = await collection.find_one({"_aggregator_identifier": study_id})

        if not document:
            return not_found_response(
                build_single_entity_meta(
                    normalized_id,
                ),
            )

        langs_needed = extract_languages_from_doc(document)

        if langs_needed:
            await asyncio.gather(*(load_cessda_topic_vocab(lang) for lang in langs_needed))

        product = transform_study_to_skgif_product(document)

        return JSONResponse(
            content=wrap_jsonld(
                data=product.model_dump(
                    by_alias=True,
                    exclude_none=True,
                ),
                meta=build_single_entity_meta(
                    normalized_id,
                ),
            )
        )

    # Related publications are fully stored in ProductRef
    if ref.product_type == "literature":

        product = transform_related_publication_to_skgif_product(
            related_publication_group=ref.relpub_group,
            cited_studies=[generate_study_local_identifier(study_id) for study_id in ref.cited_studies],
        )

        return JSONResponse(
            content=wrap_jsonld(
                data=product.model_dump(
                    by_alias=True,
                    exclude_none=True,
                ),
                meta=build_single_entity_meta(
                    normalized_id,
                ),
            )
        )

    return not_found_response(
        build_single_entity_meta(
            normalized_id,
        ),
    )
