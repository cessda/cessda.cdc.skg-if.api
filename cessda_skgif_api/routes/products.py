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

from typing import Optional
from math import ceil
from fastapi import Query, APIRouter, HTTPException
from fastapi.responses import JSONResponse
from cessda_skgif_api.models.skgif import ProductListResponse
from cessda_skgif_api.db.mongodb import get_collection, parse_filter_string, wrap_jsonld
from cessda_skgif_api.transformers.skgif_transformer import (
    transform_study_to_skgif_product,
)

router = APIRouter()

# Disallowed filter keys that must trigger 422
DISALLOWED_KEYS = {
    "product_type",
    "contributions.by.local_identifier",
    "contributions.by.family_name",
    "contributions.by.given_name",
    "contributions.declared_affiliations.local_identifier",
    "contributions.declared_affiliations.short_name",
    "funding.local_identifier",
    "funding.identifiers.id",
    "funding.identifiers.scheme",
    "cf.contributions_aff_country",
    "cf.cites",
    "cf.cites_by",
    "cf.cites_doi",
    "cf.cites_by_doi",
}

# Valid SKG-IF filter keys mapped to MongoDB fields
FILTER_MAP = {
    # TODO: Support filtering fields that are not part of MongoDB fields so they only exist after transformation
    # fields available only after transformation are marked by # # at the start, other missing fields with just #
    # # "product_type": "product_type",
    "identifiers.id": "identifiers.identifier",
    "identifiers.scheme": "identifiers.agency",
    # # "contributions.by.local_identifier": "principal_investigators.local_identifier",
    "contributions.by.identifiers.id": "principal_investigators.external_link",
    "contributions.by.identifiers.scheme": "principal_investigators.external_link_title",
    "contributions.by.name": "principal_investigators.principal_investigator",
    # # "contributions.declared_affiliations.local_identifier": "principal_investigators.local_identifier",
    "contributions.declared_affiliations.identifiers.id": "principal_investigators.external_link",
    "contributions.declared_affiliations.identifiers.scheme": "principal_investigators.external_link_title",
    "contributions.declared_affiliations.name": "principal_investigators.organization",
    # # "funding.local_identifier": "grant_numbers.local_identifier",
    "funding.grant_number": "grant_numbers.agency",
    # "funding.identifiers.id": "grant_numbers.identifier",
    # "funding.identifiers.scheme": "grant_numbers.agency",
    "cf.search.title": "study_titles.study_title",
    "cf.search.title_abstract": "abstracts.abstract",
    "cf.contributions_orcid": "principal_investigators.external_link",
    "cf.contributions_aff_ror": "principal_investigators.external_link",
}

# Fields that should use exact match
EXACT_MATCH_KEYS = {
    "identifiers.id",
    "identifiers.scheme",
    # # "contributions.by.local_identifier",
    "contributions.by.identifiers.id",
    "contributions.by.identifiers.scheme",
    # # "contributions.declared_affiliations.local_identifier",
    "contributions.declared_affiliations.identifiers.id",
    "contributions.declared_affiliations.identifiers.scheme",
    # # "funding.local_identifier",
    # "funding.identifiers.id",
    # "funding.identifiers.scheme"
}

# Filter keys that require special handling
SPECIAL_CASE_HANDLERS = {
    "cf.search.title_abstract": lambda value: {
        "$or": [
            {"study_titles.study_title": {"$regex": value, "$options": "i"}},
            {"abstracts.abstract": {"$regex": value, "$options": "i"}},
        ]
    }
}


@router.get("", response_model=ProductListResponse)
async def get_products(
    filter: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    """
    Returns a paginated list of SKG-IF products, optionally filtered by SKG-IF filter keys.
    """
    query = parse_filter_string(
        filter_str=filter,
        filter_map=FILTER_MAP,
        disallowed_keys=DISALLOWED_KEYS,
        exact_match_keys=EXACT_MATCH_KEYS,
        special_case_handlers=SPECIAL_CASE_HANDLERS,
    )

    collection = get_collection()
    total_count = await collection.count_documents(query)
    total_pages = ceil(total_count / page_size)
    skip = (page - 1) * page_size

    results = []
    async for doc in collection.find(query).skip(skip).limit(page_size):
        try:
            product = transform_study_to_skgif_product(doc)
            results.append(product)
        except Exception as e:
            print(f"Error transforming document {doc.get('_id')}: {e}")

    return {
        "meta": {
            "count": total_count,
            "page": page,
            "pages": total_pages,
            "page_size": page_size,
        },
        "results": results,
    }


@router.get("/{local_identifier}")
async def get_product_by_id(local_identifier: str):
    """
    Returns a single SKG-IF product by its local identifier.

    Path Parameters:
        local_identifier (str): The study_number of the product.

    Returns:
        JSONResponse: JSON-LD wrapped SKG-IF product.
    """
    collection = get_collection()
    document = await collection.find_one({"study_number": local_identifier})
    if not document:
        raise HTTPException(status_code=404, detail="Product not found")

    product = transform_study_to_skgif_product(document)
    jsonld_product = wrap_jsonld(product.dict(by_alias=True, exclude_none=True))

    return JSONResponse(content=jsonld_product)
