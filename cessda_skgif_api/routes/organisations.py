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

"""Handle SKG-IF Organisation endpoints."""

from cessda_skgif_api.cache.agent_index import FILTER_SPECS_ORGANISATIONS, filter_agent_refs, parse_agent_filter_raw
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from cessda_skgif_api.routes.agents_common import ensure_agent_index
from cessda_skgif_api.routes.common import (
    Pagination,
    build_meta,
    build_single_entity_meta,
    build_url,
    canonicalize_filter_for_url,
    get_raw_query_param,
    not_found_response,
)
from cessda_skgif_api.transformers.organisation_transformer import (
    transform_agent_ref_to_organisation,
)
from cessda_skgif_api.utils.helpers import wrap_jsonld
from cessda_skgif_api.utils.identifier_utils import (
    normalize_agent_lookup_identifier,
)

router = APIRouter()


@router.get("")
async def get_organisations(
    request: Request,
    pagination: Pagination = Depends(),
):
    """Return a paginated list of SKG-IF Organisations."""

    query_params = dict(request.query_params)
    changed = False

    if "page" not in query_params:
        query_params["page"] = str(pagination.page)
        changed = True

    if "page_size" not in query_params:
        query_params["page_size"] = str(pagination.page_size)
        changed = True

    if changed and "text/html" in request.headers.get("accept", ""):

        filter_raw = get_raw_query_param(
            request,
            "filter",
        )

        filter_for_url = canonicalize_filter_for_url(
            filter_raw,
        )

        url = build_url(
            "organisations",
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

    index = await ensure_agent_index(
        request,
    )

    clauses = parse_agent_filter_raw(
        filter_raw,
        FILTER_SPECS_ORGANISATIONS,
    )

    matched_refs = filter_agent_refs(
        index.organisations,
        clauses,
    )
    
    total_count = len(matched_refs)

    filter_for_meta = canonicalize_filter_for_url(
        filter_raw,
    )

    meta = build_meta(
        "organisations",
        filter_for_meta,
        pagination,
        total_count,
    )

    if total_count == 0:
        return not_found_response(meta)

    page_refs = matched_refs[
        pagination.offset:
        pagination.offset + pagination.limit
    ]

    results = [
        transform_agent_ref_to_organisation(ref).model_dump(
            by_alias=True,
            exclude_none=True,
        )
        for ref in page_refs
    ]

    return JSONResponse(
        content=wrap_jsonld(
            data=results,
            meta=meta,
        )
    )


@router.get("/{local_identifier:path}")
async def get_organisation_by_id(
    request: Request,
    local_identifier: str,
):
    """Return a single SKG-IF Organisation by local identifier."""
    normalized_id = normalize_agent_lookup_identifier(
        local_identifier,
        entity_type="organisation",
    )

    index = await ensure_agent_index(request)

    ref = index.organisation_by_id.get(normalized_id)

    if ref is None:
        return not_found_response(
            meta=build_single_entity_meta(
                normalized_id,
            ),
        )

    organisation = transform_agent_ref_to_organisation(ref)

    return JSONResponse(
        content=wrap_jsonld(
            data=organisation.model_dump(
                by_alias=True,
                exclude_none=True,
            ),
            meta=build_single_entity_meta(
                normalized_id,
            ),
        )
    )
