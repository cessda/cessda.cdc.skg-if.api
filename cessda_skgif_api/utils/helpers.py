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

"""Various helper functions"""

import re
from typing import Any, Dict, Iterable, List, Optional, Union
from cessda_skgif_api.config_loader import load_config

config = load_config()
skg_if_context = config.skg_if_context
skg_if_api_context = config.skg_if_api_context
skg_if_cessda_context = config.skg_if_cessda_context


def wrap_jsonld(
    data: Union[Dict[str, Any], List[Dict[str, Any]]], meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Wraps array with dictionary in JSON-LD format using SKG-IF context.
    Adds 'meta' before '@graph' if provided.
    """
    # Normalize `data` into a flat list of dicts
    if isinstance(data, dict):
        graph = [data]
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


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().split()).casefold()


def normalize_ror_lookup_name(value: str) -> str:
    value = normalize_text(value)
    return re.sub(r"[^0-9a-zA-Z]+", "", value).lower()


def split_search_name(value: str) -> set[str]:
    normalized = normalize_text(value)

    return {
        part
        for part in re.split(r"[^0-9a-zA-Z]+", normalized)
        if part
    }


def first_non_empty(*values: Optional[str]) -> Optional[str]:
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return None


def dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if not value:
            continue
        norm = normalize_text(value)
        if norm in seen:
            continue
        seen.add(norm)
        result.append(value)
    return result
