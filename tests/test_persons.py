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

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.requests import Request

from cessda_skgif_api.routes import persons
from cessda_skgif_api.routes.common import Pagination


def make_fake_request(*, query_string: bytes = b"", accept: str | None = None):
    app = MagicMock()
    app.state = MagicMock()

    headers = []

    if accept is not None:
        headers.append((b"accept", accept.encode("ascii")))

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "query_string": query_string,
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
        "app": app,
    }

    return Request(scope)


def make_transformed_person(
    local_identifier: str = "https://orcid.org/0000-0002-1066-6039",
):
    person = MagicMock()
    person.model_dump.return_value = {
        "local_identifier": local_identifier,
        "entity_type": "person",
        "name": "Test Person",
    }
    return person


class TestPersonEndpoints(unittest.IsolatedAsyncioTestCase):
    async def test_get_persons_returns_matching_persons(self):
        request = make_fake_request(query_string=b"page=1&page_size=10")

        person_ref = MagicMock()
        index = MagicMock()
        index.persons = [person_ref]

        clauses = [MagicMock()]
        transformed_person = make_transformed_person()

        with (
            patch(
                "cessda_skgif_api.routes.persons.ensure_agent_index",
                new=AsyncMock(return_value=index),
            ),
            patch(
                "cessda_skgif_api.routes.persons.parse_agent_filter_raw",
                return_value=clauses,
            ) as mock_parse_filter,
            patch(
                "cessda_skgif_api.routes.persons.filter_agent_refs",
                return_value=[person_ref],
            ) as mock_filter_refs,
            patch(
                "cessda_skgif_api.routes.persons.transform_agent_ref_to_person",
                return_value=transformed_person,
            ) as mock_transform,
        ):
            response = await persons.get_persons(request=request, pagination=Pagination(page=1, page_size=10))

        self.assertEqual(response.status_code, 200)
        self.assertIn('"entity_type":"person"', response.body.decode())
        self.assertIn('"name":"Test Person"', response.body.decode())

        mock_parse_filter.assert_called_once_with(None, persons.FILTER_SPECS_PERSONS)
        mock_filter_refs.assert_called_once_with(index.persons, clauses)
        mock_transform.assert_called_once_with(person_ref)
        transformed_person.model_dump.assert_called_once_with(by_alias=True, exclude_none=True)

    async def test_get_persons_passes_filter_to_parser(self):
        request = make_fake_request(query_string=b"filter=cf.search.name:test&page=1&page_size=10")

        person_ref = MagicMock()
        index = MagicMock()
        index.persons = [person_ref]

        transformed_person = make_transformed_person()

        with (
            patch(
                "cessda_skgif_api.routes.persons.ensure_agent_index",
                new=AsyncMock(return_value=index),
            ),
            patch(
                "cessda_skgif_api.routes.persons.parse_agent_filter_raw",
                return_value=[],
            ) as mock_parse_filter,
            patch(
                "cessda_skgif_api.routes.persons.filter_agent_refs",
                return_value=[person_ref],
            ),
            patch(
                "cessda_skgif_api.routes.persons.transform_agent_ref_to_person",
                return_value=transformed_person,
            ),
        ):
            response = await persons.get_persons(request=request, pagination=Pagination(page=1, page_size=10))

        self.assertEqual(response.status_code, 200)
        mock_parse_filter.assert_called_once_with("cf.search.name:test", persons.FILTER_SPECS_PERSONS)

    async def test_get_persons_returns_not_found_for_no_matches(self):
        request = make_fake_request(query_string=b"page=1&page_size=10")

        index = MagicMock()
        index.persons = []

        with (
            patch(
                "cessda_skgif_api.routes.persons.ensure_agent_index",
                new=AsyncMock(return_value=index),
            ),
            patch(
                "cessda_skgif_api.routes.persons.parse_agent_filter_raw",
                return_value=[],
            ),
            patch("cessda_skgif_api.routes.persons.filter_agent_refs", return_value=[]),
        ):
            response = await persons.get_persons(request=request, pagination=Pagination(page=1, page_size=10))

        self.assertEqual(response.status_code, 404)
        self.assertIn('"@graph":[]', response.body.decode())
        self.assertIn('"entity_type":"search_result_page"', response.body.decode())

    async def test_get_persons_redirects_html_request_to_explicit_pagination(self):
        request = make_fake_request(query_string=b"filter=cf.search.name:test", accept="text/html")

        with patch("cessda_skgif_api.routes.persons.ensure_agent_index", new=AsyncMock()) as mock_ensure_index:
            response = await persons.get_persons(request=request, pagination=Pagination(page=1, page_size=10))

        self.assertEqual(response.status_code, 302)

        location = response.headers["location"]

        self.assertIn("/persons?", location)
        self.assertIn("page=1", location)
        self.assertIn("page_size=10", location)
        self.assertIn("filter=cf.search.name:test", location)

        mock_ensure_index.assert_not_awaited()

    async def test_get_persons_does_not_redirect_when_pagination_is_present(self):
        request = make_fake_request(query_string=b"page=2&page_size=1", accept="text/html")

        first_ref = MagicMock()
        second_ref = MagicMock()

        index = MagicMock()
        index.persons = [first_ref, second_ref]

        transformed_person = make_transformed_person(local_identifier="second-person")

        with (
            patch(
                "cessda_skgif_api.routes.persons.ensure_agent_index",
                new=AsyncMock(return_value=index),
            ),
            patch(
                "cessda_skgif_api.routes.persons.parse_agent_filter_raw",
                return_value=[],
            ),
            patch(
                "cessda_skgif_api.routes.persons.filter_agent_refs",
                return_value=[first_ref, second_ref],
            ),
            patch(
                "cessda_skgif_api.routes.persons.transform_agent_ref_to_person",
                return_value=transformed_person,
            ) as mock_transform,
        ):
            response = await persons.get_persons(request=request, pagination=Pagination(page=2, page_size=1))

        self.assertEqual(response.status_code, 200)
        mock_transform.assert_called_once_with(second_ref)
        self.assertIn("second-person", response.body.decode())

    async def test_get_person_by_id_found(self):
        request = make_fake_request()

        person_ref = MagicMock()
        index = MagicMock()
        index.person_by_id = {"normalised-person-id": person_ref}

        transformed_person = make_transformed_person(local_identifier="normalised-person-id")

        with (
            patch(
                "cessda_skgif_api.routes.persons.normalize_agent_lookup_identifier",
                return_value="normalised-person-id",
            ) as mock_normalise,
            patch(
                "cessda_skgif_api.routes.persons.ensure_agent_index",
                new=AsyncMock(return_value=index),
            ),
            patch(
                "cessda_skgif_api.routes.persons.transform_agent_ref_to_person",
                return_value=transformed_person,
            ) as mock_transform,
        ):
            response = await persons.get_person_by_id(
                request=request,
                local_identifier="https://orcid.org/0000-0002-1066-6039",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("normalised-person-id", response.body.decode())

        mock_normalise.assert_called_once_with("https://orcid.org/0000-0002-1066-6039", entity_type="person")
        mock_transform.assert_called_once_with(person_ref)
        transformed_person.model_dump.assert_called_once_with(by_alias=True, exclude_none=True)
