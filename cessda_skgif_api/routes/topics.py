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
from typing import Annotated, TypedDict
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

JsonObject = dict[str, object]

ELSSTConcept = TypedDict(
    "ELSSTConcept",
    {
        "@id": str,
        "prefLabels": dict[str, str],
        "altLabels": dict[str, list[str]],
        "broader": str | None,
    },
)

ELSSTData = dict[str, ELSSTConcept]
SearchIndex = dict[str, list[tuple[str, str]]]


def ensure_elsst_data_exists(filepath: str, download_url: str) -> None:
    """Ensure that the ELSST JSON-LD data file exists locally."""
    if os.path.exists(filepath):
        _logger.info("ELSST data file found at %s", filepath)
        return

    _logger.info("ELSST data file not found at %s", filepath)

    if not download_url:
        _logger.error("No download URL configured (elsst_download_url).")

    _logger.info("Attempting to download ELSST data from %s", download_url)

    try:
        data_dir = os.path.dirname(filepath)
        os.makedirs(data_dir, exist_ok=True)

        with urlopen(download_url, timeout=30) as response:
            content = response.read()

        with open(filepath, "wb") as file:
            file.write(content)

        _logger.info("Successfully downloaded ELSST data to %s", filepath)

        if not os.path.exists(filepath):
            _logger.error("File was downloaded but cannot be found.")

    except URLError as exc:
        raise RuntimeError(f"Failed to download ELSST data from {download_url}") from exc

    except OSError as exc:
        raise RuntimeError(f"Failed to save ELSST data to {filepath}") from exc


def _extract_jsonld_graph(data: object) -> list[JsonObject]:
    """Extract graph entries from supported JSON-LD structures."""
    graph: list[JsonObject] = []

    if isinstance(data, dict):
        raw_graph = data.get(JSON_LD_GRAPH, [])

        if isinstance(raw_graph, list):
            graph.extend(item for item in raw_graph if isinstance(item, dict))

        return graph

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue

            raw_graph = item.get(JSON_LD_GRAPH, [])

            if isinstance(raw_graph, list):
                graph.extend(graph_item for graph_item in raw_graph if isinstance(graph_item, dict))

    return graph


def _extract_preferred_labels(concept: JsonObject) -> dict[str, str]:
    """Extract preferred labels keyed by language."""
    labels = concept.get(SKOS_PREF_LABEL)

    if not isinstance(labels, list):
        return {}

    preferred_labels = {}

    for label in labels:
        if not isinstance(label, dict):
            continue

        language = label.get("@language")
        value = label.get("@value")

        if isinstance(language, str) and isinstance(value, str):
            preferred_labels[language] = value

    return preferred_labels


def _extract_alternative_labels(concept: JsonObject) -> dict[str, list[str]]:
    """Extract alternative labels grouped by language."""
    labels = concept.get(SKOS_ALT_LABEL)

    if not isinstance(labels, list):
        return {}

    alternative_labels: dict[str, list[str]] = {}

    for label in labels:
        if not isinstance(label, dict):
            continue

        language = label.get("@language")
        value = label.get("@value")

        if isinstance(language, str) and isinstance(value, str):
            alternative_labels.setdefault(language, []).append(value)

    return alternative_labels


def _extract_broader_identifier(concept: JsonObject) -> str | None:
    """Extract the first broader concept identifier."""
    broader = concept.get(SKOS_BROADER)

    if isinstance(broader, dict):
        broader = [broader]

    if not isinstance(broader, list) or not broader:
        return None

    first = broader[0]

    if not isinstance(first, dict):
        return None

    identifier = first.get("@id")
    return identifier if isinstance(identifier, str) else None


def _process_elsst_concept(concept: JsonObject) -> tuple[str, ELSSTConcept] | None:
    """Process one SKOS concept from the ELSST JSON-LD graph."""
    concept_id = concept.get("@id")

    if not isinstance(concept_id, str):
        return None

    concept_types = concept.get("@type", [])

    if isinstance(concept_types, str):
        concept_types = [concept_types]

    if not isinstance(concept_types, list):
        return None

    if SKOS_CONCEPT not in concept_types:
        return None

    return concept_id, {
        "@id": concept_id,
        "prefLabels": _extract_preferred_labels(concept),
        "altLabels": _extract_alternative_labels(concept),
        "broader": _extract_broader_identifier(concept),
    }


def load_elsst_data(filepath: str) -> ELSSTData:
    """Load and process an ELSST JSON-LD export into a multilingual dictionary."""
    with open(filepath, "r", encoding="utf-8") as file:
        data = json.load(file)

    graph = _extract_jsonld_graph(data)

    if not graph:
        _logger.info("No JSON-LD graph found")
        return {}

    processed_data: ELSSTData = {}

    for concept in graph:
        processed_concept = _process_elsst_concept(concept)

        if processed_concept is None:
            continue

        concept_id, concept_data = processed_concept
        processed_data[concept_id] = concept_data

    _logger.info("Loaded %s concepts with multilingual labels", len(processed_data))
    return processed_data


def build_search_index(processed_data: ELSSTData) -> SearchIndex:
    """Build a search index from the processed ELSST data for faster lookups."""
    search_index: SearchIndex = {}
    _logger.info("Building search index...")

    for concept_id, data in processed_data.items():
        for language, label in data["prefLabels"].items():
            search_index.setdefault(language, []).append((label.lower(), concept_id))

        for language, labels in data["altLabels"].items():
            for label in labels:
                search_index.setdefault(language, []).append((label.lower(), concept_id))

    for language, items in search_index.items():
        _logger.info("Indexed %s labels for language '%s'", len(items), language)

    _logger.info("Search index built.")
    return search_index


# --- In-memory Data Store ---

ELSST_DATA: ELSSTData = {}
SEARCH_INDEX: SearchIndex = {}


def initialize_elsst_data() -> None:
    """Load ELSST data and build the in-memory search index."""
    global ELSST_DATA, SEARCH_INDEX

    ensure_elsst_data_exists(DATA_FILE_PATH, elsst_download_url)

    _logger.info("Loading ELSST data from %s", DATA_FILE_PATH)

    elsst_data = load_elsst_data(DATA_FILE_PATH)

    if not elsst_data:
        raise RuntimeError("ELSST data could not be loaded")

    search_index = build_search_index(elsst_data)

    ELSST_DATA = elsst_data
    SEARCH_INDEX = search_index


# --- Helper Functions ---


def format_topic_for_response(concept_data: ELSSTConcept) -> dict[str, object]:
    """Transform a single ELSST concept into the API response format."""
    return {
        "local_identifier": concept_data["@id"],
        # "identifiers": [],  # ELSST data does not contain external identifiers like wikidata
        "entity_type": "topic",
        "labels": concept_data["prefLabels"],
    }


# --- Debugging Endpoint ---


@router.get("/show_index_data", summary="Show a sample of the in-memory data", include_in_schema=False)
async def show_index_data():
    """Return samples of the loaded ELSST data and search index for debugging."""
    elsst_keys = list(ELSST_DATA.keys())
    sample_size_elsst = min(10, len(elsst_keys))
    random_elsst_keys = random.sample(elsst_keys, sample_size_elsst) if elsst_keys else []
    elsst_sample = {key: ELSST_DATA[key] for key in random_elsst_keys}

    search_index_sample = {}
    for language, items in SEARCH_INDEX.items():
        sample_size_index = min(10, len(items))
        search_index_sample[language] = random.sample(items, sample_size_index)

    return {"elsst_data_sample": elsst_sample, "search_index_sample": search_index_sample}


# --- API Endpoint ---


@router.get(
    "/{topic_id:path}",
    summary="Get a single topic by its identifier",
    response_model=dict,
)
async def topic_single(
    topic_id: Annotated[
        str,
        Path(description="The persistent identifier (URI) of the topic."),
    ],
):
    """Retrieve a single topic by its persistent identifier (URI)."""
    decoded_id = unquote(topic_id)

    if decoded_id.startswith("https:/") and not decoded_id.startswith("https://"):
        decoded_id = decoded_id.replace("https:/", "https://", 1)

    concept_data = ELSST_DATA.get(decoded_id)

    if not concept_data:
        return not_found_response(build_single_entity_meta(decoded_id))

    topic_graph_item = format_topic_for_response(concept_data)
    jsonld_topic = wrap_jsonld(
        data=topic_graph_item,
        meta=build_single_entity_meta(decoded_id),
    )

    return JSONResponse(content=jsonld_topic)


def _build_topics_redirect(
    request: Request,
    pagination: Pagination,
) -> RedirectResponse | None:
    """Redirect HTML requests to a URL with explicit pagination."""
    query_params = dict(request.query_params)

    if "page" in query_params and "page_size" in query_params:
        return None

    if "text/html" not in request.headers.get("accept", ""):
        return None

    filter_raw = get_raw_query_param(request, "filter")
    filter_for_url = canonicalize_filter_for_url(filter_raw)

    url = build_url(
        "topics",
        params={
            "filter": filter_for_url,
            "page": str(pagination.page),
            "page_size": str(pagination.page_size),
        },
        raw_params={"filter"},
    )

    return RedirectResponse(url=url, status_code=302)


def _get_raw_topic_filter(
    request: Request,
    filter_str: str,
) -> str:
    """Return the raw topic filter value where possible."""
    raw_query_string = request.scope.get("query_string", b"")

    if isinstance(raw_query_string, (bytes, bytearray)):
        raw_query_string = raw_query_string.decode("latin-1")
    else:
        raw_query_string = str(raw_query_string)

    match = re.search(
        r"(?:^|&)" + re.escape("filter") + r"=([^&]*)",
        raw_query_string,
    )

    if match:
        return match.group(1)

    return request.query_params.get("filter") or filter_str


def _parse_topic_filter(
    request: Request,
    filter_str: str,
) -> tuple[str, str]:
    """Parse and validate the topic search term and language."""
    raw_filter_value = _get_raw_topic_filter(request, filter_str)

    try:
        filter_params = {}

        for part in raw_filter_value.split(","):
            decoded = unquote_plus(part)
            key, value = decoded.split(":", 1)
            filter_params[key.strip()] = value.strip()

    except ValueError as exc:
        raise InvalidFilterException(
            detail=(
                "Filter parameter is malformed. Expected format: 'cf.search.labels:<term>,cf.search.language:<lang>'."
            )
        ) from exc

    search_term = filter_params.get("cf.search.labels")

    if not search_term or len(search_term) < 3:
        raise InvalidFilterException(
            detail=("A 'cf.search.labels' filter with a value of at least 3 characters must be provided.")
        )

    language_code = filter_params.get("cf.search.language", "en")

    if not re.fullmatch(r"[a-z]{2}", language_code):
        raise InvalidFilterException(
            detail=("If provided, 'cf.search.language' must be a 2-letter ISO 639-1 language code.")
        )

    return search_term, language_code


def _search_topics(
    search_term: str,
    language_code: str,
) -> list[dict[str, object]]:
    """Return topics matching a term in the requested language."""
    query = search_term.lower()

    matching_concept_ids = {concept_id for label, concept_id in SEARCH_INDEX.get(language_code, []) if query in label}

    return [
        format_topic_for_response(ELSST_DATA[concept_id])
        for concept_id in sorted(matching_concept_ids)
        if concept_id in ELSST_DATA
    ]


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
    """Provide autocomplete suggestions for social science topics."""
    redirect = _build_topics_redirect(request, pagination)

    if redirect is not None:
        return redirect

    filter_raw = get_raw_query_param(request, "filter")

    if filter_str:
        search_term, language_code = _parse_topic_filter(
            request,
            filter_str,
        )
        results = _search_topics(search_term, language_code)
    else:
        results = [format_topic_for_response(concept) for concept in ELSST_DATA.values()]

    total_items = len(results)

    filter_for_meta = canonicalize_filter_for_url(filter_raw)
    meta = build_meta(
        "topics",
        filter_for_meta,
        pagination,
        total_items,
    )

    if total_items == 0:
        return not_found_response(meta)

    paged_results = results[pagination.offset : pagination.offset + pagination.limit]

    return JSONResponse(
        content=wrap_jsonld(
            data=paged_results,
            meta=meta,
        )
    )
