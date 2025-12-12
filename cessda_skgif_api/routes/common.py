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
from urllib.parse import urlencode
from typing import Optional, Dict, Any
from cessda_skgif_api.config_loader import load_config


config = load_config()
api_base_url = config.api_base_url
api_prefix = config.api_prefix


def build_api_url(api_base_url: Optional[str], api_prefix: Optional[str], endpoint: str) -> str:
    """
    Build an API URL from base, optional prefix, and endpoint (e.g., https://example.com/api/products).
    """
    base = (api_base_url or "").rstrip("/")
    path = "/".join(p for p in [(api_prefix or "").strip("/"), endpoint.strip("/")] if p)
    return f"{base}/{path}" if base else f"/{path}"


def build_url(endpoint: str, default_page_size: int = 10, **params) -> str:
    """
    Build a clean URL with optional query parameters.

    Omits `page_size` if it equals the default for the endpoint.

    :param endpoint: Endpoint name to be used in API URL.
    :param default_page_size: Default page size for the endpoint.
    :param params: Query parameters as keyword arguments.
    :return: Full URL as a string.
    """
    api_url = build_api_url(api_base_url, api_prefix, endpoint)
    clean_params: Dict[str, Any] = {}
    for k, v in params.items():
        if v is None:
            continue
        if k == "page_size" and v == default_page_size:
            continue
        clean_params[k] = v

    return f"{api_url}?{urlencode(clean_params)}" if clean_params else api_url


def build_meta(
    endpoint: str,
    filter_str: Optional[str],
    page: int,
    page_size: int,
    total_count: int,
    default_page_size: int = 10,
) -> dict:
    """
    Build a metadata dictionary for paginated search results.

    Includes:
    - Current page URL (`local_identifier`)
    - Previous page (if applicable)
    - Next page (if applicable)
    - Part-of section with total item count, first page and last page

    Behavior:
    - Always returns at least one page (even if total_count == 0).
    - Omits `page_size` from URLs if it equals the default for the endpoint.

    :param endpoint: Endpoint name to be used in API URL.
    :param filter_str: Filter string for the query (e.g., "product_type:literature").
    :param page: Current page number (1-based).
    :param page_size: Number of items per page.
    :param total_count: Total number of items across all pages.
    :param default_page_size: Default page size for this endpoint.
    :return: A dictionary containing metadata for pagination.
    """
    # Ensure at least one page exists (even if no results)
    total_pages = max(1, ceil(total_count / page_size))

    # Current page URL
    local_identifier_url = build_url(
        endpoint,
        default_page_size=default_page_size,
        filter=filter_str,
        page=page,
        page_size=page_size,
    )

    # Part-of URL (only filter)
    local_identifier_part_of_url = build_url(
        endpoint,
        default_page_size=default_page_size,
        filter=filter_str,
    )

    meta = {
        "local_identifier": local_identifier_url,
        "entity_type": "search_result_page",
    }

    # Previous page (only if page > 1)
    if page > 1:
        meta["previous_page"] = {
            "local_identifier": build_url(
                endpoint,
                default_page_size=default_page_size,
                filter=filter_str,
                page=page - 1,
                page_size=page_size,
            ),
            "entity_type": "search_result_page",
        }

    # Next page (only if page < total_pages)
    if page < total_pages:
        meta["next_page"] = {
            "local_identifier": build_url(
                endpoint,
                default_page_size=default_page_size,
                filter=filter_str,
                page=page + 1,
                page_size=page_size,
            ),
            "entity_type": "search_result_page",
        }

    # Part-of section
    meta["part_of"] = {
        "local_identifier": local_identifier_part_of_url,
        "entity_type": "search_result",
        "total_items": total_count,
    }

    # First and last pages (only if more than one page)
    if total_pages > 1:
        meta["part_of"]["first_page"] = {
            "local_identifier": build_url(
                endpoint,
                default_page_size=default_page_size,
                filter=filter_str,
                page=1,
                page_size=page_size,
            ),
            "entity_type": "search_result_page",
        }
        meta["part_of"]["last_page"] = {
            "local_identifier": build_url(
                endpoint,
                default_page_size=default_page_size,
                filter=filter_str,
                page=total_pages,
                page_size=page_size,
            ),
            "entity_type": "search_result_page",
        }

    return meta
