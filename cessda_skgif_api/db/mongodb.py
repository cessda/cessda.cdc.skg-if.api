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

"""This module handles connection and operations with MongoDB"""

import urllib.parse
from pymongo import AsyncMongoClient
from fastapi import HTTPException
from cessda_skgif_api.config_loader import load_config


def parse_filter_string(
    filter_str: str,
    filter_map: dict,
    disallowed_keys: set,
    exact_match_keys: set,
    special_case_handlers: dict = None,
) -> dict:
    """
    Parses a SKG-IF filter string into a MongoDB query using AND logic.

    Args:
        filter_str (str): Comma-separated key:value filter string.
        filter_map (dict): Maps SKG-IF filter keys to MongoDB field paths.
        disallowed_keys (set): Keys that should trigger a 422 error.
        exact_match_keys (set): Keys that should use exact matching.
        special_case_handlers (dict): Optional dict of key -> handler(value) for custom logic.

    Returns:
        dict: MongoDB query dictionary using $and.

    Raises:
        HTTPException: If any filter keys are disallowed (422) or unknown (400).
    """
    query = {"$and": []}
    if not filter_str:
        return {}

    invalid_keys = []
    disallowed_keys_used = []

    for pair in filter_str.split(","):
        if ":" not in pair:
            continue
        key, value = pair.split(":", 1)
        key = key.strip().replace(" ", "")
        value = value.strip()

        if key in disallowed_keys:
            disallowed_keys_used.append(key)
            continue

        if special_case_handlers and key in special_case_handlers:
            handler = special_case_handlers[key]
            query["$and"].append(handler(value))
            continue

        field = filter_map.get(key)
        if not field:
            invalid_keys.append(key)
            continue

        if key in exact_match_keys:
            query["$and"].append({field: {"$regex": f"^{value}$", "$options": "i"}})
        else:
            query["$and"].append({field: {"$regex": value, "$options": "i"}})

    if disallowed_keys_used:
        raise HTTPException(
            status_code=422,
            detail=f"Filter keys not implemented: {', '.join(disallowed_keys_used)}",
        )
    if invalid_keys:
        raise HTTPException(status_code=400, detail=f"Invalid filter keys: {', '.join(invalid_keys)}")

    return query if query["$and"] else {}


def get_collection():
    """Get collection from MongoDB according to the configuration"""
    config = load_config()

    username = urllib.parse.quote(config.mongodb_username)
    password = urllib.parse.quote(config.mongodb_password)
    server = config.mongodb_server
    database = config.mongodb_database

    if username and password:
        uri = f"mongodb://{username}:{password}@{server}/{database}"
    else:
        uri = f"mongodb://{server}/{database}"

    try:
        client = AsyncMongoClient(uri)
        db = client[database]
        return db[config.mongodb_collection]
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        raise
