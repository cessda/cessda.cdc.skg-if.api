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
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient

from cessda_skgif_api import main, pages

client = TestClient(main.app)


class TestMainPages(unittest.TestCase):
    def test_expected_routes_are_registered(self):
        registered_paths = {route_context.path for route_context in iter_route_contexts(main.app.router.routes)}

        expected_paths = {
            "/",
            "/accessibility",
            "/docs",
            "/docs-dynamic",
            "/redoc",
            "/products",
            "/persons",
            "/organisations",
            "/topics",
        }

        self.assertTrue(expected_paths.issubset(registered_paths))

    def test_root_info_page(self):
        response = client.get("/")

        self.assertEqual(response.status_code, 200)

        self.assertIn('<html lang="en">', response.text)

        self.assertIn("CESSDA SKG-IF API", response.text)

        self.assertIn("CESSDA Data Catalogue (CDC)", response.text)

        self.assertIn("European Language Social Science Thesaurus (ELSST)", response.text)

        self.assertIn("Accessibility Statement", response.text)

        self.assertIn("https://www.cessda.eu/Privacy-Policy", response.text)

        self.assertIn("https://www.cessda.eu/Acceptable-Use-Policy", response.text)


class TestPages(unittest.TestCase):
    def test_example_renders_link_and_description(self):
        result = pages._example(
            "/products?page=1&page_size=10",
            "Returns products.",
        )

        self.assertIn(
            f'href="{pages.API_PREFIX}/products?page=1&amp;page_size=10"',
            result,
        )
        self.assertIn(
            f"{pages.API_PREFIX}/products?page=1&amp;page_size=10",
            result,
        )
        self.assertIn("Returns products.", result)

    def test_example_escapes_unsafe_path_content(self):
        result = pages._example(
            '/products?filter=<script>&value="test"',
            "Unsafe-looking example.",
        )

        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)
        self.assertIn("&quot;test&quot;", result)


class TestScheduling(unittest.TestCase):
    @patch("cessda_skgif_api.main.datetime")
    def test_seconds_until_target_time_later_today(self, mock_datetime):
        timezone = ZoneInfo("UTC")

        mock_datetime.now.return_value = datetime(2026, 10, 20, 10, 0, tzinfo=timezone)

        seconds = main.seconds_until_target_time("12:30", "UTC")

        self.assertEqual(seconds, 2.5 * 60 * 60)

    @patch("cessda_skgif_api.main.datetime")
    def test_seconds_until_target_time_rolls_to_next_day(self, mock_datetime):
        timezone = ZoneInfo("UTC")

        mock_datetime.now.return_value = datetime(2026, 10, 20, 15, 0, tzinfo=timezone)

        seconds = main.seconds_until_target_time("14:00", "UTC")

        self.assertEqual(seconds, 23 * 60 * 60)


class TestLifespan(unittest.IsolatedAsyncioTestCase):
    async def test_lifespan_initialises_and_closes_resources(self):
        fake_app = SimpleNamespace(state=SimpleNamespace())

        mongo_client = MagicMock()
        mongo_client.close = MagicMock()

        collection = MagicMock()
        product_index = MagicMock()
        agent_index = MagicMock()

        rebuild_started = asyncio.Event()

        async def fake_rebuild_loop(app):
            self.assertIs(app, fake_app)

            rebuild_started.set()

            # Remain alive until lifespan shutdown cancels the task.
            await asyncio.Event().wait()

        with (
            patch("cessda_skgif_api.main.preload_vocabs", new=AsyncMock()) as mock_preload,
            patch(
                "cessda_skgif_api.main.create_client",
                return_value=mongo_client,
            ) as mock_create_client,
            patch("cessda_skgif_api.main.get_collection_from_app", return_value=collection) as mock_get_collection,
            patch(
                "cessda_skgif_api.main.build_product_index",
                new=AsyncMock(return_value=product_index),
            ) as mock_build_products,
            patch(
                "cessda_skgif_api.main.build_agent_index",
                new=AsyncMock(return_value=agent_index),
            ) as mock_build_agents,
            patch(
                "cessda_skgif_api.main.rebuild_indexes_loop",
                side_effect=fake_rebuild_loop,
            ),
        ):
            async with main.lifespan(fake_app):
                await rebuild_started.wait()

                self.assertIs(fake_app.state.mongo_client, mongo_client)

                self.assertIs(fake_app.state.product_index, product_index)

                self.assertIs(fake_app.state.agent_index, agent_index)

                self.assertIsInstance(fake_app.state.product_index_lock, asyncio.Lock)

                self.assertIsInstance(fake_app.state.agent_index_lock, asyncio.Lock)

                self.assertFalse(fake_app.state.index_rebuild_task.done())

        mock_preload.assert_awaited_once_with(["en", "de", "fr", "fi", "sl"])

        mock_create_client.assert_called_once_with()
        mock_get_collection.assert_called_once_with(fake_app)
        mock_build_products.assert_awaited_once_with(collection)
        mock_build_agents.assert_awaited_once_with(collection)

        self.assertTrue(fake_app.state.index_rebuild_task.cancelled())

        mongo_client.close.assert_called_once_with()


class TestRebuildIndexesLoop(unittest.IsolatedAsyncioTestCase):
    async def test_rebuild_indexes_loop_replaces_indexes(self):
        old_product_index = MagicMock()
        old_agent_index = MagicMock()

        app = SimpleNamespace(
            state=SimpleNamespace(
                product_index=old_product_index,
                agent_index=old_agent_index,
                product_index_lock=asyncio.Lock(),
                agent_index_lock=asyncio.Lock(),
            )
        )

        collection = MagicMock()
        new_product_index = MagicMock()
        new_agent_index = MagicMock()

        sleep_calls = 0

        async def sleep_once_then_stop(seconds):
            nonlocal sleep_calls
            sleep_calls += 1

            if sleep_calls > 1:
                raise asyncio.CancelledError()

        with (
            patch("cessda_skgif_api.main.seconds_until_target_time", return_value=60) as mock_seconds,
            patch("cessda_skgif_api.main.asyncio.sleep", side_effect=sleep_once_then_stop),
            patch("cessda_skgif_api.main.get_collection_from_app", return_value=collection) as mock_get_collection,
            patch(
                "cessda_skgif_api.main.build_product_index",
                new=AsyncMock(return_value=new_product_index),
            ) as mock_build_products,
            patch(
                "cessda_skgif_api.main.build_agent_index",
                new=AsyncMock(return_value=new_agent_index),
            ) as mock_build_agents,
            patch("cessda_skgif_api.main._logger.info") as mock_log_info,
            self.assertRaises(asyncio.CancelledError),
        ):
            await main.rebuild_indexes_loop(app)

        self.assertIs(app.state.product_index, new_product_index)

        self.assertIs(app.state.agent_index, new_agent_index)

        mock_seconds.assert_called()
        mock_get_collection.assert_called_once_with(app)
        mock_build_products.assert_awaited_once_with(collection)
        mock_build_agents.assert_awaited_once_with(collection)
        mock_log_info.assert_called()

    async def test_rebuild_indexes_loop_logs_failure_and_preserves_indexes(self):
        old_product_index = MagicMock()
        old_agent_index = MagicMock()

        app = SimpleNamespace(
            state=SimpleNamespace(
                product_index=old_product_index,
                agent_index=old_agent_index,
                product_index_lock=asyncio.Lock(),
                agent_index_lock=asyncio.Lock(),
            )
        )

        collection = MagicMock()
        sleep_calls = 0

        async def sleep_once_then_stop(seconds):
            nonlocal sleep_calls
            sleep_calls += 1

            if sleep_calls > 1:
                raise asyncio.CancelledError()

        with (
            patch("cessda_skgif_api.main.seconds_until_target_time", return_value=60),
            patch("cessda_skgif_api.main.asyncio.sleep", side_effect=sleep_once_then_stop),
            patch("cessda_skgif_api.main.get_collection_from_app", return_value=collection),
            patch(
                "cessda_skgif_api.main.build_product_index",
                new=AsyncMock(side_effect=ValueError("Invalid source data")),
            ),
            patch(
                "cessda_skgif_api.main.build_agent_index",
                new=AsyncMock(return_value=MagicMock()),
            ),
            patch("cessda_skgif_api.main._logger.exception") as mock_log_exception,
            self.assertRaises(asyncio.CancelledError),
        ):
            await main.rebuild_indexes_loop(app)

        self.assertIs(app.state.product_index, old_product_index)

        self.assertIs(app.state.agent_index, old_agent_index)

        mock_log_exception.assert_called_once_with("Index rebuild failed")


if __name__ == "__main__":
    unittest.main()
