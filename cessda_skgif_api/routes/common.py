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

"""Contains functions used in multiple routes"""

from math import ceil
from urllib.parse import quote, unquote_plus, urlencode
from fastapi import Query, HTTPException
from typing import Iterable, Optional, Dict, Any
from cessda_skgif_api.config_loader import load_config

config = load_config()
api_base_url = config.api_base_url
api_prefix = config.api_prefix


class Pagination:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number starting from 1"),
        page_size: int = Query(10, ge=1, le=150, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def paginate_results(results: list, pagination: Pagination) -> list:
    """
    Apply in-memory pagination to an already-built result list.
    """
    start = (pagination.page - 1) * pagination.page_size
    end = start + pagination.page_size
    return results[start:end]


def canonicalize_filter_for_url(filter_raw: str | None) -> str | None:
    """
    Convert raw filter string to canonical *readable* form:
      - delimiter ':' and delimiter ',' remain unescaped
      - commas inside values become %2C (and other unsafe chars are percent-encoded)

    Returns a percent-encoded string suitable to place directly after `filter=`.
    """
    if not filter_raw:
        return None

    parts: list[str] = []
    for raw_pair in filter_raw.split(","):
        split = split_raw_pair(raw_pair)
        if not split:
            continue

        raw_key, raw_value = split

        key = unquote_plus(raw_key).strip().replace(" ", "")
        value = unquote_plus(raw_value).strip()

        key_enc = quote(key, safe="-._~")
        value_enc = quote(value, safe="-._~:")  # comma not safe so it becomes %2C

        parts.append(f"{key_enc}:{value_enc}")

    return ",".join(parts) if parts else None


def split_raw_pair(raw_pair: str) -> tuple[str, str] | None:
    """
    Split a raw (percent-encoded) filter pair into raw_key and raw_value.

    Supports both:
      key:value
      key%3Avalue
    """
    # Prefer literal ":" if present
    i = raw_pair.find(":")
    if i != -1:
        return raw_pair[:i], raw_pair[i + 1 :]

    # Otherwise look for encoded colon (%3A or %3a)
    lower = raw_pair.lower()
    j = lower.find("%3a")
    if j != -1:
        return raw_pair[:j], raw_pair[j + 3 :]

    return None


def get_raw_query_param(request, name: str) -> str | None:
    """
    Return the raw (percent-encoded) value of a query param from the ASGI scope,
    without framework decoding.

    If the param appears multiple times, raise 400 (since spec says single filter param).
    """
    raw_qs = request.scope.get("query_string", b"") or b""
    qs = raw_qs.decode("ascii", "ignore")

    found = None
    for part in qs.split("&"):
        if not part:
            continue
        k, _, v = part.partition("=")
        if unquote_plus(k) == name:
            if found is not None:
                raise HTTPException(status_code=400, detail=f"Query param '{name}' must appear only once")
            found = v  # still percent-encoded
    return found


def build_api_url(api_base_url: Optional[str], api_prefix: Optional[str], endpoint: str) -> str:
    """
    Build an API URL from base, optional prefix, and endpoint (e.g., https://example.com/api/products).
    """
    base = (api_base_url or "").rstrip("/")
    path = "/".join(p for p in [(api_prefix or "").strip("/"), endpoint.strip("/")] if p)
    return f"{base}/{path}" if base else f"/{path}"


def build_url(
    endpoint: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    include_only: Optional[Iterable[str]] = None,
    exclude: Optional[Iterable[str]] = None,
    raw_params: Optional[Iterable[str]] = None,
) -> str:
    """
    Build a clean URL for an endpoint with fine-grained control over query parameters.

    Args:
        endpoint: Endpoint name to be appended to the API base URL.
        params: Dict of raw query parameters to consider (values of None are dropped).
        include_only: If provided, only these keys will be kept.
        exclude: If provided, these keys will be removed.
        raw_params: Optional iterable of parameter names whose values are already
            URL-encoded and should be included as-is (to avoid double-encoding).

    Returns:
        Full URL as a string.
    """
    api_url = build_api_url(api_base_url, api_prefix, endpoint)

    working: Dict[str, Any] = dict(params or {})
    working = {k: v for k, v in working.items() if v is not None}

    if include_only is not None:
        keep = set(include_only)
        working = {k: v for k, v in working.items() if k in keep}

    if exclude is not None:
        drop = set(exclude)
        working = {k: v for k, v in working.items() if k not in drop}

    if not working:
        return api_url

    raw_set = set(raw_params or [])

    raw_parts = []
    normal_parts = {}

    for k, v in working.items():
        if k in raw_set:
            # v must already be percent-encoded, add as-is
            raw_parts.append(f"{quote(str(k), safe='')}={v}")
        else:
            normal_parts[k] = v

    chunks = []
    if raw_parts:
        chunks.append("&".join(raw_parts))
    if normal_parts:
        chunks.append(urlencode(normal_parts, doseq=True))

    return f"{api_url}?{'&'.join(chunks)}"


def build_meta(
    endpoint: str,
    filter_str: Optional[str],
    pagination: Pagination,
    total_count: int,
) -> dict:
    """
    Build a metadata dictionary for paginated search results.

    - 'local_identifier' (current page) includes pagination.
    - 'previous_page' / 'next_page' / 'first_page' / 'last_page' include pagination.
    - 'part_of.local_identifier' includes only filters (no pagination).
    """
    page = pagination.page
    page_size = pagination.page_size

    effective_page_size = max(1, page_size)
    total_pages = max(1, ceil(total_count / effective_page_size))

    filter_params = {"filter": filter_str}
    raw = {"filter"}

    meta: dict = {
        "local_identifier": build_url(
            endpoint,
            params={**filter_params, "page": page, "page_size": page_size},
            raw_params=raw,
        ),
        "entity_type": "search_result_page",
    }

    if page < total_pages:
        meta["next_page"] = {
            "local_identifier": build_url(
                endpoint,
                params={**filter_params, "page": page + 1, "page_size": page_size},
                raw_params=raw,
            ),
            "entity_type": "search_result_page",
        }

    if page > 1:
        meta["previous_page"] = {
            "local_identifier": build_url(
                endpoint,
                params={**filter_params, "page": page - 1, "page_size": page_size},
                raw_params=raw,
            ),
            "entity_type": "search_result_page",
        }

    meta["part_of"] = {
        "local_identifier": build_url(
            endpoint,
            params=filter_params,
            include_only={"filter"},
            raw_params=raw,
        ),
        "entity_type": "search_result",
        "total_items": total_count,
    }

    if total_pages > 1:
        meta["part_of"]["first_page"] = {
            "local_identifier": build_url(
                endpoint,
                params={**filter_params, "page": 1, "page_size": page_size},
                raw_params=raw,
            ),
            "entity_type": "search_result_page",
        }
        meta["part_of"]["last_page"] = {
            "local_identifier": build_url(
                endpoint,
                params={**filter_params, "page": total_pages, "page_size": page_size},
                raw_params=raw,
            ),
            "entity_type": "search_result_page",
        }

    return meta
