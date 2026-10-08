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

"""Shared functionality for Person and Organisation endpoints."""

import asyncio
from fastapi import Request
from cessda_skgif_api.cache.agent_index import (
    AgentIndex,
    build_agent_index,
)
from cessda_skgif_api.db.mongodb import get_collection


async def ensure_agent_index(
    request: Request,
) -> AgentIndex:
    """
    Use the startup-built Agent index if available.

    Also supports lazy initialisation when the startup build has not
    completed or the application is being tested without lifespan handling.
    """
    existing_index = getattr(
        request.app.state,
        "agent_index",
        None,
    )

    if existing_index is not None:
        return existing_index

    if not hasattr(request.app.state, "agent_index_lock"):
        request.app.state.agent_index_lock = asyncio.Lock()

    async with request.app.state.agent_index_lock:
        if getattr(request.app.state, "agent_index", None) is None:
            collection = get_collection(request)

            request.app.state.agent_index = await build_agent_index(
                collection
            )

    return request.app.state.agent_index
