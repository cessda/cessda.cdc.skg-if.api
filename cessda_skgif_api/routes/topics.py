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

"""Handles the functionality of Topic endpoints"""

import json
import logging
import os
import random
import re
from typing import Annotated
from urllib.error import URLError
from urllib.parse import unquote, unquote_plus
from urllib.request import urlopen

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from cessda_skgif_api.config_loader import load_config
from cessda_skgif_api.routes.common import (
    Pagination,
    build_meta,
    build_single_entity_meta,
    build_url,
    canonicalize_filter_for_url,
    get_raw_query_param,
    not_found_response,
)
from cessda_skgif_api.utils.errors import InvalidFilterException
from cessda_skgif_api.utils.helpers import wrap_jsonld

config = load_config()
elsst_scheme_name = config.elsst_scheme_name
elsst_scheme_url = config.elsst_scheme_url
elsst_download_url = config.elsst_download_url

router = APIRouter()

_logger = logging.getLogger(__name__)

# --- Data Loading and Processing ---

DATA_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "elsst_current.jsonld")
DATA_FILE_PATH = os.path.abspath(DATA_FILE_PATH)

JSON_LD_GRAPH = "@graph"

# Constants for SKOS URIs
SKOS_CONCEPT = "http://www.w3.org/2004/02/skos/core#Concept"
SKOS_PREF_LABEL = "http://www.w3.org/2004/02/skos/core#prefLabel"
SKOS_ALT_LABEL = "http://www.w3.org/2004/02/skos/core#altLabel"
SKOS_BROADER = "http://www.w3.org/2004/02/skos/core#broader"


def ensure_elsst_data_exists(filepath: str, download_url: str) -> None:
    """
    Ensures the ELSST data file exists. If not, attempts to download it.

    Args:
        filepath: The path to the ELSST JSON-LD file.
        download_url: The URL to download the file from if it doesn't exist.

    Exits:
        If the file cannot be retrieved, exits with an error message.
    """
    if os.path.exists(filepath):
        _logger.info("ELSST data file found at %s", filepath)
        return

    _logger.info("ELSST data file not found at %s", filepath)

    if not download_url:
        _logger.error("No download URL configured (elsst_download_url).")

    _logger.info("Attempting to download ELSST data from %s", download_url)

    try:
        # Create data directory if it doesn't exist
        data_dir = os.path.dirname(filepath)
        os.makedirs(data_dir, exist_ok=True)

        # Download the file
        with urlopen(download_url, timeout=30) as response:
            content = response.read()

        # Save to file
        with open(filepath, "wb") as f:
            f.write(content)

        _logger.info("Successfully downloaded ELSST data to %s", filepath)

        # Verify file exists
        if not os.path.exists(filepath):
            _logger.error("File was downloaded but cannot be found.")

    except URLError as exc:
        raise RuntimeError(f"Failed to download ELSST data from {download_url}") from exc

    except OSError as exc:
        raise RuntimeError(f"Failed to save ELSST data to {filepath}") from exc


def load_elsst_data(filepath: str) -> dict:
    """
    Loads and processes an ELSST JSON-LD export file into a multilingual dictionary.

    Args:
        filepath: The path to the .jsonld file.

    Returns:
        A dictionary where keys are concept URIs and values are dicts
        with multilingual 'prefLabels', 'altLabels', and 'broader' keys.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Navigate into the graph
    graph = []
    if isinstance(data, dict) and JSON_LD_GRAPH in data:
        graph = data[JSON_LD_GRAPH]
    elif isinstance(data, list):
        # Some JSON-LD files wrap data in a list
        for item in data:
            if JSON_LD_GRAPH in item:
                graph.extend(item[JSON_LD_GRAPH])
    else:
        _logger.info("No @graph found in JSON-LD")
        return {}

    processed_data = {}

    for concept in graph:
        if not isinstance(concept, dict) or "@id" not in concept:
            continue

        types = concept.get("@type", [])
        if isinstance(types, str):
            types = [types]

        if SKOS_CONCEPT not in types:
            continue  # Skip non-Concept items

        concept_id = concept["@id"]

        # Get all prefLabels, keyed by language
        pref_labels = {}
        for label in concept.get(SKOS_PREF_LABEL, []):
            lang = label.get("@language")
            value = label.get("@value")
            if lang and value:
                pref_labels[lang] = value

        # Get all altLabels, keyed by language and grouped in a list
        alt_labels = {}
        for label in concept.get(SKOS_ALT_LABEL, []):
            lang = label.get("@language")
            value = label.get("@value")
            if lang and value:
                alt_labels.setdefault(lang, []).append(value)

        # Get broader concept
        broader = concept.get(SKOS_BROADER, [])
        if isinstance(broader, dict):
            broader = [broader]
        broader_id = broader[0].get("@id") if broader else None

        processed_data[concept_id] = {
            "@id": concept_id,
            "prefLabels": pref_labels,
            "altLabels": alt_labels,
            "broader": broader_id,
        }

    _logger.info("Loaded %s concepts with multilingual labels", len(processed_data))
    return processed_data


def build_search_index(processed_data: dict) -> dict:
    """
    Builds a search index from the processed ELSST data for faster lookups.

    Args:
        processed_data: The dictionary of concepts from load_elsst_data.

    Returns:
        A dictionary where keys are language codes (e.g., 'en') and values are
        lists of tuples, with each tuple containing a lowercase label and the
        corresponding concept URI. e.g., {'en': [('poverty', 'uri:1'), ...]}
    """
    search_index = {}
    _logger.info("Building search index...")
    for concept_id, data in processed_data.items():
        # Index preferred labels
        for lang, label in data.get("prefLabels", {}).items():
            search_index.setdefault(lang, []).append((label.lower(), concept_id))

        # Index alternative labels
        for lang, labels in data.get("altLabels", {}).items():
            for label in labels:
                search_index.setdefault(lang, []).append((label.lower(), concept_id))

    for lang, items in search_index.items():
        _logger.info("Indexed %s labels for language '%s'", len(items), lang)

    _logger.info("Search index built.")
    return search_index


# --- In-memory Data Store ---

ELSST_DATA: dict = {}
SEARCH_INDEX: dict = {}


def initialize_elsst_data() -> None:
    """Load ELSST data and build the in-memory search index."""
    global ELSST_DATA, SEARCH_INDEX

    ensure_elsst_data_exists(
        DATA_FILE_PATH,
        elsst_download_url,
    )

    _logger.info(
        "Loading ELSST data from %s",
        DATA_FILE_PATH,
    )

    elsst_data = load_elsst_data(
        DATA_FILE_PATH,
    )

    if not elsst_data:
        raise RuntimeError("ELSST data could not be loaded")

    search_index = build_search_index(
        elsst_data,
    )

    ELSST_DATA = elsst_data
    SEARCH_INDEX = search_index


# --- Helper Functions ---


def format_topic_for_response(concept_data: dict) -> dict:
    """Transforms a single ELSST concept into the API's response format."""
    return {
        "local_identifier": concept_data.get("@id"),
        # "identifiers": [],  # ELSST data does not contain external identifiers like wikidata
        "entity_type": "topic",
        "labels": concept_data.get("prefLabels", {}),
    }


# --- Debugging Endpoint ---


@router.get("/show_index_data", summary="Show a sample of the in-memory data", include_in_schema=False)
async def show_index_data():
    """
    Provides a sample of the loaded ELSST data and the constructed search index
    for debugging purposes. Shows up to 10 random items from the main data store
    and up to 10 random items from the search index for each language.
    """
    # Sample from ELSST_DATA
    elsst_keys = list(ELSST_DATA.keys())
    sample_size_elsst = min(10, len(elsst_keys))
    # Ensure we don't try to sample from an empty list if data loading failed
    random_elsst_keys = random.sample(elsst_keys, sample_size_elsst) if elsst_keys else []
    elsst_sample = {key: ELSST_DATA[key] for key in random_elsst_keys}

    # Sample from SEARCH_INDEX for each language
    search_index_sample = {}
    for lang, items in SEARCH_INDEX.items():
        sample_size_index = min(10, len(items))
        search_index_sample[lang] = random.sample(items, sample_size_index)

    return {"elsst_data_sample": elsst_sample, "search_index_sample": search_index_sample}


# --- API Endpoint ---


@router.get("/{topic_id:path}", summary="Get a single topic by its identifier", response_model=dict)
async def topic_single(topic_id: str = Path(..., description="The persistent identifier (URI) of the topic.")):
    """
    Retrieves a single topic by its persistent identifier (URI).

    - The `topic_id` path parameter is the full URI of the topic.
    - Example: `/api/topics/http%3A%2F%2Fpurl.org%2Felsst%2F4%2Fes%2F368`
    """
    # The topic_id is the key in our ELSST_DATA dictionary.
    # Decode and check if proxying messed up double slash
    decoded_id = unquote(topic_id)
    if decoded_id.startswith("https:/") and not decoded_id.startswith("https://"):
        decoded_id = decoded_id.replace("https:/", "https://", 1)
    concept_data = ELSST_DATA.get(decoded_id)

    if not concept_data:
        return not_found_response(build_single_entity_meta(decoded_id))

    # Format the single topic into the SKG-IF JSON-LD structure.
    topic_graph_item = {
        "local_identifier": concept_data.get("@id"),
        # "identifiers": [
        #    {
        #        "scheme": ELSST_SCHEME_NAME,
        #        "value": ELSST_SCHEME_URL
        #    }
        # ,
        "entity_type": "topic",
        "labels": concept_data.get("prefLabels", {}),
    }

    # Construct the final JSON-LD response
    jsonld_topic = wrap_jsonld(data=topic_graph_item, meta=build_single_entity_meta(decoded_id))

    return JSONResponse(content=jsonld_topic)


@router.get("", summary="Get topic suggestions", response_model=dict)
async def topic_result(
    request: Request,
    pagination: Annotated[Pagination, Depends()],
    filter_str: Annotated[
        str | None,
        Query(
            min_length=19,
            description=("Filter for topics. Format: `cf.search.labels:<term>,cf.search.language:<lang>`"),
            alias="filter",
        ),
    ] = None,
):
    """
    Provides autocomplete suggestions for social science topics.

    - The `filter` query parameter accepts a comma-separated string of key:value pairs.
    - `cf.search.labels` (required): The term to search for (min 3 characters).
    - `cf.search.language` (optional): The 2-letter language code (defaults to 'en').
    - Example: `?filter=cf.search.labels:poverty,cf.search.language:de`

    Parsing note:
    - We parse the raw query string (not the URL-decoded value) to extract the
      filter parameter value, split on literal commas in that raw value, and
      only then URL-decode each individual filter element. This preserves any
      commas that were percent-encoded inside values (%2C).
    """

    # If page or page_size are missing, redirect to canonical URL
    query_params = dict(request.query_params)

    changed = False

    if "page" not in query_params:
        query_params["page"] = str(pagination.page)
        changed = True

    if "page_size" not in query_params:
        query_params["page_size"] = str(pagination.page_size)
        changed = True

    if changed and "text/html" in request.headers.get("accept", ""):
        # Use raw filter so commas inside values stay representable (%2C)
        filter_raw = get_raw_query_param(request, "filter")
        filter_for_url = canonicalize_filter_for_url(filter_raw)
        url = build_url(
            "topics",
            params={"filter": filter_for_url, "page": str(pagination.page), "page_size": str(pagination.page_size)},
            raw_params={"filter"},
        )
        return RedirectResponse(url=url, status_code=302)

    # Prefer raw filter for parsing + canonical meta URLs
    filter_raw = get_raw_query_param(request, "filter")

    results = []

    if filter_str:
        # Parse the complex 'filter' parameter which can contain multiple key:value pairs.
        # IMPORTANT: extract from the raw, percent-encoded query string to split on literal commas.
        raw_qs_bytes = request.scope.get("query_string", b"")
        raw_qs = raw_qs_bytes.decode("latin-1") if isinstance(raw_qs_bytes, (bytes, bytearray)) else str(raw_qs_bytes)

        raw_filter_value = None
        m = re.search(r"(?:^|&)" + re.escape("filter") + r"=([^&]*)", raw_qs)
        if m:
            raw_filter_value = m.group(1)

        # Fallback: if we couldn't find the raw value, use the decoded one (backwards compatibility)
        if raw_filter_value is None:
            raw_filter_value = request.query_params.get("filter")

        filter_params = {}
        try:
            # Split on literal commas in the raw value (so %2C remains part of an element)
            # Fallback to filter_str if raw extraction failed
            filter_value = raw_filter_value if raw_filter_value is not None else filter_str
            parts = filter_value.split(",") if filter_value is not None else []
            for part in parts:
                # URL-decode each individual element (convert %xx and + to spaces)
                decoded = unquote_plus(part)
                key, value = decoded.split(":", 1)
                filter_params[key.strip()] = value.strip()
        except ValueError:
            raise InvalidFilterException(
                detail=(
                    "Filter parameter is malformed. "
                    "Expected format: "
                    "'cf.search.labels:<term>,cf.search.language:<lang>'."
                )
            )

        # Extract and validate search term from the parsed filter
        search_term = filter_params.get("cf.search.labels")

        if not search_term or len(search_term) < 3:
            raise InvalidFilterException(
                detail=("A 'cf.search.labels' filter with a value of at least 3 characters must be provided.")
            )

        # Extract and validate language code, defaulting to 'en'
        language_code = filter_params.get("cf.search.language", "en")

        if not re.match("^[a-z]{2}$", language_code):
            raise InvalidFilterException(
                detail=("If provided, 'cf.search.language' must be a 2-letter ISO 639-1 language code.")
            )

        # Search
        search_lang = language_code
        query = search_term.lower()

        # Find concepts that match the query in the specified language using the search index
        matching_concept_ids = {concept_id for label, concept_id in SEARCH_INDEX.get(search_lang, []) if query in label}

        # Build the results list, sorting for consistent output
        results = [
            format_topic_for_response(ELSST_DATA[concept_id])
            for concept_id in sorted(matching_concept_ids)
            if concept_id in ELSST_DATA
        ]

    else:
        # No filter: return all topics
        results = [format_topic_for_response(concept) for concept in ELSST_DATA.values()]

    # Apply pagination
    total_items = len(results)

    filter_for_meta = canonicalize_filter_for_url(filter_raw)

    meta = build_meta("topics", filter_for_meta, pagination, total_items)

    if total_items == 0:
        return not_found_response(meta)

    paged_results = results[pagination.offset : pagination.offset + pagination.limit]

    jsonld_topics = wrap_jsonld(data=paged_results, meta=meta)

    return JSONResponse(content=jsonld_topics)
