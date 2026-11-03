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

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.requests import Request

from cessda_skgif_api.routes import agents_common


def make_fake_request(*, state: SimpleNamespace | None = None) -> Request:
    if state is None:
        state = SimpleNamespace()

    app = SimpleNamespace(state=state)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
        "app": app,
    }

    return Request(scope)


class PopulateIndexOnEnter:
    """Simulate another task populating the index while this task waits."""

    def __init__(self, state: SimpleNamespace, index):
        self.state = state
        self.index = index
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True

        # Simulate another task having populated the index before this task completed acquiring the lock
        self.state.agent_index = self.index

        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.exited = True
        return False


class TestEnsureAgentIndex(unittest.IsolatedAsyncioTestCase):
    async def test_returns_existing_agent_index(self):
        existing_index = MagicMock()

        request = make_fake_request(state=SimpleNamespace(agent_index=existing_index))

        with (
            patch("cessda_skgif_api.routes.agents_common.get_collection") as mock_get_collection,
            patch(
                "cessda_skgif_api.routes.agents_common.build_agent_index",
                new=AsyncMock(),
            ) as mock_build_index,
        ):
            result = await agents_common.ensure_agent_index(request)

        self.assertIs(result, existing_index)

        mock_get_collection.assert_not_called()
        mock_build_index.assert_not_awaited()

    async def test_creates_lock_and_builds_agent_index_when_missing(self):
        request = make_fake_request(state=SimpleNamespace(agent_index=None))

        collection = MagicMock()
        built_index = MagicMock()

        with (
            patch(
                "cessda_skgif_api.routes.agents_common.get_collection",
                return_value=collection,
            ) as mock_get_collection,
            patch(
                "cessda_skgif_api.routes.agents_common.build_agent_index",
                new=AsyncMock(return_value=built_index),
            ) as mock_build_index,
        ):
            result = await agents_common.ensure_agent_index(request)

        self.assertIs(result, built_index)

        self.assertIs(request.app.state.agent_index, built_index)

        self.assertIsInstance(request.app.state.agent_index_lock, asyncio.Lock)

        mock_get_collection.assert_called_once_with(request)

        mock_build_index.assert_awaited_once_with(collection)

    async def test_uses_existing_lock_and_builds_agent_index_when_missing(self):
        existing_lock = asyncio.Lock()

        request = make_fake_request(state=SimpleNamespace(agent_index=None, agent_index_lock=existing_lock))

        collection = MagicMock()
        built_index = MagicMock()

        with (
            patch(
                "cessda_skgif_api.routes.agents_common.get_collection",
                return_value=collection,
            ) as mock_get_collection,
            patch(
                "cessda_skgif_api.routes.agents_common.build_agent_index",
                new=AsyncMock(return_value=built_index),
            ) as mock_build_index,
        ):
            result = await agents_common.ensure_agent_index(request)

        self.assertIs(result, built_index)

        self.assertIs(request.app.state.agent_index, built_index)

        self.assertIs(request.app.state.agent_index_lock, existing_lock)

        mock_get_collection.assert_called_once_with(request)

        mock_build_index.assert_awaited_once_with(collection)

    async def test_does_not_rebuild_index_populated_before_lock_is_acquired(self):
        index_built_by_other_task = MagicMock()

        state = SimpleNamespace(agent_index=None)

        lock = PopulateIndexOnEnter(state=state, index=index_built_by_other_task)

        state.agent_index_lock = lock

        request = make_fake_request(state=state)

        with (
            patch("cessda_skgif_api.routes.agents_common.get_collection") as mock_get_collection,
            patch(
                "cessda_skgif_api.routes.agents_common.build_agent_index",
                new=AsyncMock(),
            ) as mock_build_index,
        ):
            result = await agents_common.ensure_agent_index(request)

        self.assertIs(result, index_built_by_other_task)

        self.assertTrue(lock.entered)

        self.assertTrue(lock.exited)

        mock_get_collection.assert_not_called()
        mock_build_index.assert_not_awaited()
