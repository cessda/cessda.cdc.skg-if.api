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

"""Handles the functionality of Topic endpoints"""

import os
import re
import random
import json
from urllib.parse import unquote
from fastapi import HTTPException, Query, Path, APIRouter, HTTPException
from fastapi.responses import JSONResponse
from cessda_skgif_api.config_loader import load_config
from cessda_skgif_api.routes.common import build_meta
from cessda_skgif_api.transformers.skgif_transformer import wrap_jsonld


config = load_config()
api_base_url = config.api_base_url
api_prefix = config.api_prefix
elsst_datasource_id = config.elsst_datasource_id
elsst_scheme_name = config.elsst_scheme_name
elsst_scheme_url = config.elsst_scheme_url

router = APIRouter()

# --- Data Loading and Processing ---

DATA_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "elsst_current.jsonld")
DATA_FILE_PATH = os.path.abspath(DATA_FILE_PATH)

# Constants for SKOS URIs
SKOS_CONCEPT = "http://www.w3.org/2004/02/skos/core#Concept"
SKOS_PREF_LABEL = "http://www.w3.org/2004/02/skos/core#prefLabel"
SKOS_ALT_LABEL = "http://www.w3.org/2004/02/skos/core#altLabel"
SKOS_BROADER = "http://www.w3.org/2004/02/skos/core#broader"


def load_elsst_data(filepath: str) -> dict:
    """
    Loads and processes an ELSST JSON-LD export file into a multilingual dictionary.

    Args:
        filepath: The path to the .jsonld file.

    Returns:
        A dictionary where keys are concept URIs and values are dicts
        with multilingual 'prefLabels', 'altLabels', and 'broader' keys.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Data file not found at '{filepath}'.")
        print("Please download the ELSST JSON-LD export and place it in the correct path.")
        # Return a minimal dataset to allow the server to start, but it will be empty.
        return {}
    except json.JSONDecodeError:
        print(f"ERROR: Could not decode JSON from '{filepath}'. The file might be corrupt.")
        return {}

    # Navigate into the graph
    graph = []
    if isinstance(data, dict) and '@graph' in data:
        graph = data['@graph']
    elif isinstance(data, list):
        # Some JSON-LD files wrap data in a list
        for item in data:
            if '@graph' in item:
                graph.extend(item['@graph'])
    else:
        print("No @graph found in JSON-LD")
        return {}

    processed_data = {}

    for concept in graph:
        if not isinstance(concept, dict) or '@id' not in concept:
            continue

        types = concept.get('@type', [])
        if isinstance(types, str):
            types = [types]

        if SKOS_CONCEPT not in types:
            continue  # Skip non-Concept items

        concept_id = concept['@id']

        # Get all prefLabels, keyed by language
        pref_labels = {}
        for label in concept.get(SKOS_PREF_LABEL, []):
            lang = label.get('@language')
            value = label.get('@value')
            if lang and value:
                pref_labels[lang] = value

        # Get all altLabels, keyed by language and grouped in a list
        alt_labels = {}
        for label in concept.get(SKOS_ALT_LABEL, []):
            lang = label.get('@language')
            value = label.get('@value')
            if lang and value:
                alt_labels.setdefault(lang, []).append(value)

        # Get broader concept
        broader = concept.get(SKOS_BROADER, [])
        if isinstance(broader, dict):
            broader = [broader]
        broader_id = broader[0].get('@id') if broader else None

        processed_data[concept_id] = {
            '@id': concept_id,
            'prefLabels': pref_labels,
            'altLabels': alt_labels,
            'broader': broader_id,
        }

    print(f"Loaded {len(processed_data)} concepts with multilingual labels")
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
    print("Building search index...")
    for concept_id, data in processed_data.items():
        # Index preferred labels
        for lang, label in data.get('prefLabels', {}).items():
            search_index.setdefault(lang, []).append((label.lower(), concept_id))

        # Index alternative labels
        for lang, labels in data.get('altLabels', {}).items():
            for label in labels:
                search_index.setdefault(lang, []).append((label.lower(), concept_id))

    for lang, items in search_index.items():
        print(f"  - Indexed {len(items)} labels for language '{lang}'")

    print("Search index built.")
    return search_index


# --- In-memory Data Store ---
# The data is loaded once when the application starts.
print("Loading ELSST data from file...")
ELSST_DATA = load_elsst_data(DATA_FILE_PATH)
SEARCH_INDEX = build_search_index(ELSST_DATA)


# --- Helper Functions ---


def format_topic_for_response(concept_data: dict) -> dict:
    """Transforms a single ELSST concept into the API's response format."""
    return {
        "local_identifier": concept_data.get('@id'),
        # "identifiers": [],  # ELSST data does not contain external identifiers like wikidata
        "entity_type": "topic",
        "labels": concept_data.get("prefLabels", {}),
    }


# --- Debugging Endpoint ---


@router.get('/show_index_data', summary="Show a sample of the in-memory data", include_in_schema=False)
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


@router.get('/{topic_id:path}', summary="Get a single topic by its identifier", response_model=dict)
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
        raise HTTPException(status_code=404, detail=f"Topic with ID '{decoded_id}' not found.")

    # Format the single topic into the SKG-IF JSON-LD structure.
    topic_graph_item = {
        "local_identifier": concept_data.get('@id'),
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
    jsonld_topic = wrap_jsonld(topic_graph_item)

    return JSONResponse(content=jsonld_topic)


@router.get('', summary="Get topic suggestions", response_model=dict)
async def topic_result(
    filter_str: str = Query(
        None,
        min_length=19,
        description="Filter for topics. Format: `cf.search.labels:<term>,cf.search.language:<lang>`",
        alias="filter",
    ),
    page: int = Query(1, ge=1, description="Page number (starting from 1)"),
    page_size: int = Query(10, ge=1, description="Number of items per page"),
):
    """
    Provides autocomplete suggestions for social science topics.

    - The `filter` query parameter accepts a comma-separated string of key:value pairs.
    - `cf.search.labels` (required): The term to search for (min 3 characters).
    - `cf.search.language` (optional): The 2-letter language code (defaults to 'en').
    - Example: `?filter=cf.search.labels:poverty,cf.search.language:de`
    """

    results = []

    if filter_str:
        # Parse the complex 'filter' parameter which can contain multiple key:value pairs.
        filter_params = {}
        try:
            for part in filter_str.split(','):
                key, value = part.split(':', 1)
                filter_params[key.strip()] = value.strip()
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=[
                    {
                        "loc": ["query", "filter"],
                        "msg": "Filter parameter is malformed. Expected format: 'key1:value1,key2:value2'.",
                        "type": "value_error.format",
                    }
                ],
            )

        # Extract and validate search term from the parsed filter
        search_term = filter_params.get("cf.search.labels")
        if not search_term or len(search_term) < 3:
            raise HTTPException(
                status_code=422,
                detail=[
                    {
                        "loc": ["query", "filter"],
                        "msg": "A 'cf.search.labels' key with a value of at least 3 characters must be provided in the filter.",
                        "type": "value_error.missing",
                    }
                ],
            )

        # Extract and validate language code, defaulting to 'en'
        language_code = filter_params.get("cf.search.language", "en")
        if not re.match("^[a-z]{2}$", language_code):
            raise HTTPException(
                status_code=422,
                detail=[
                    {
                        "loc": ["query", "filter"],
                        "msg": "If provided, the value for 'cf.search.language' must be a 2-letter ISO 639-1 code.",
                        "type": "value_error.pattern",
                    }
                ],
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

    # Build paginated results according to page and page size
    start = (page - 1) * page_size
    end = start + page_size
    paginated_results = results[start:end]

    # Construct the final JSON-LD response
    api_url = f"{api_base_url.rstrip('/')}/{api_prefix.lstrip('/').rstrip('/')}/topics"
    meta = build_meta(api_url, filter_str, page=page, page_size=page_size, total_count=len(results))

    return JSONResponse(content=wrap_jsonld(data=paginated_results, meta=meta))
