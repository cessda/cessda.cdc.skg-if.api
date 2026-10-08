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

"""MongoDB connection helpers (async, FastAPI lifespan-friendly)"""

from urllib.parse import quote
from fastapi import Request
from pymongo import AsyncMongoClient
from cessda_skgif_api.config_loader import load_config

_config = load_config()


def build_uri() -> str:
    username = quote(_config.mongodb_username or "")
    password = quote(_config.mongodb_password or "")
    server = _config.mongodb_server
    database = _config.mongodb_database

    if username and password:
        return f"mongodb://{username}:{password}@{server}/{database}"
    return f"mongodb://{server}/{database}"


def _get_collection_from_client(client: AsyncMongoClient):
    db = client[_config.mongodb_database]
    return db[_config.mongodb_collection]


def get_collection(request: Request):
    """
    Return the configured collection using the AsyncMongoClient stored in app.state
    """
    client: AsyncMongoClient = request.app.state.mongo_client
    return _get_collection_from_client(client)


def get_collection_from_app(app):
    """
    Return the configured collection using the AsyncMongoClient stored in app.state.
    Useful during startup when Request is not available.
    """
    client: AsyncMongoClient = app.state.mongo_client
    return _get_collection_from_client(client)


async def create_client() -> AsyncMongoClient:
    """
    Factory used by lifespan to create one shared AsyncMongoClient.
    """
    uri = build_uri()
    client = AsyncMongoClient(
        uri,
        maxPoolSize=100,
        minPoolSize=1,
    )
    return client
