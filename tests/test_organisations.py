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

from cessda_skgif_api.routes import organisations
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


def make_transformed_organisation(local_identifier: str = "https://ror.org/00bwtjf83"):
    organisation = MagicMock()
    organisation.model_dump.return_value = {
        "local_identifier": local_identifier,
        "entity_type": "organisation",
        "name": "Test Organisation",
    }
    return organisation


class TestOrganisationEndpoints(unittest.IsolatedAsyncioTestCase):
    async def test_get_organisations_returns_matching_organisations(self):
        request = make_fake_request(query_string=b"page=1&page_size=10")

        organisation_ref = MagicMock()
        index = MagicMock()
        index.organisations = [organisation_ref]

        clauses = [MagicMock()]
        transformed_organisation = make_transformed_organisation()

        with (
            patch(
                "cessda_skgif_api.routes.organisations.ensure_agent_index",
                new=AsyncMock(return_value=index),
            ),
            patch(
                "cessda_skgif_api.routes.organisations.parse_agent_filter_raw",
                return_value=clauses,
            ) as mock_parse_filter,
            patch(
                "cessda_skgif_api.routes.organisations.filter_agent_refs",
                return_value=[organisation_ref],
            ) as mock_filter_refs,
            patch(
                "cessda_skgif_api.routes.organisations.transform_agent_ref_to_organisation",
                return_value=transformed_organisation,
            ) as mock_transform,
        ):
            response = await organisations.get_organisations(
                request=request, pagination=Pagination(page=1, page_size=10)
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('"entity_type":"organisation"', response.body.decode())
        self.assertIn('"name":"Test Organisation"', response.body.decode())

        mock_parse_filter.assert_called_once_with(None, organisations.FILTER_SPECS_ORGANISATIONS)
        mock_filter_refs.assert_called_once_with(index.organisations, clauses)
        mock_transform.assert_called_once_with(organisation_ref)
        transformed_organisation.model_dump.assert_called_once_with(by_alias=True, exclude_none=True)

    async def test_get_organisations_passes_filter_to_parser(self):
        request = make_fake_request(query_string=b"filter=name:test&page=1&page_size=10")

        organisation_ref = MagicMock()
        index = MagicMock()
        index.organisations = [organisation_ref]

        transformed_organisation = make_transformed_organisation()

        with (
            patch(
                "cessda_skgif_api.routes.organisations.ensure_agent_index",
                new=AsyncMock(return_value=index),
            ),
            patch(
                "cessda_skgif_api.routes.organisations.parse_agent_filter_raw",
                return_value=[],
            ) as mock_parse_filter,
            patch(
                "cessda_skgif_api.routes.organisations.filter_agent_refs",
                return_value=[organisation_ref],
            ),
            patch(
                "cessda_skgif_api.routes.organisations.transform_agent_ref_to_organisation",
                return_value=transformed_organisation,
            ),
        ):
            response = await organisations.get_organisations(
                request=request, pagination=Pagination(page=1, page_size=10)
            )

        self.assertEqual(response.status_code, 200)
        mock_parse_filter.assert_called_once_with("name:test", organisations.FILTER_SPECS_ORGANISATIONS)

    async def test_get_organisations_returns_not_found_for_no_matches(self):
        request = make_fake_request(query_string=b"page=1&page_size=10")

        index = MagicMock()
        index.organisations = []

        with (
            patch(
                "cessda_skgif_api.routes.organisations.ensure_agent_index",
                new=AsyncMock(return_value=index),
            ),
            patch(
                "cessda_skgif_api.routes.organisations.parse_agent_filter_raw",
                return_value=[],
            ),
            patch(
                "cessda_skgif_api.routes.organisations.filter_agent_refs",
                return_value=[],
            ),
        ):
            response = await organisations.get_organisations(
                request=request, pagination=Pagination(page=1, page_size=10)
            )

        self.assertEqual(response.status_code, 404)
        self.assertIn('"@graph":[]', response.body.decode())
        self.assertIn('"entity_type":"search_result_page"', response.body.decode())

    async def test_get_organisations_redirects_html_request_to_explicit_pagination(
        self,
    ):
        request = make_fake_request(query_string=b"filter=name:test", accept="text/html")

        with patch("cessda_skgif_api.routes.organisations.ensure_agent_index", new=AsyncMock()) as mock_ensure_index:
            response = await organisations.get_organisations(
                request=request, pagination=Pagination(page=1, page_size=10)
            )

        self.assertEqual(response.status_code, 302)

        location = response.headers["location"]

        self.assertIn("/organisations?", location)
        self.assertIn("page=1", location)
        self.assertIn("page_size=10", location)
        self.assertIn("filter=name:test", location)

        mock_ensure_index.assert_not_awaited()

    async def test_get_organisations_does_not_redirect_when_pagination_is_present(self):
        request = make_fake_request(query_string=b"page=2&page_size=1", accept="text/html")

        first_ref = MagicMock()
        second_ref = MagicMock()

        index = MagicMock()
        index.organisations = [first_ref, second_ref]

        transformed_organisation = make_transformed_organisation(local_identifier="second-organisation")

        with (
            patch(
                "cessda_skgif_api.routes.organisations.ensure_agent_index",
                new=AsyncMock(return_value=index),
            ),
            patch(
                "cessda_skgif_api.routes.organisations.parse_agent_filter_raw",
                return_value=[],
            ),
            patch(
                "cessda_skgif_api.routes.organisations.filter_agent_refs",
                return_value=[first_ref, second_ref],
            ),
            patch(
                "cessda_skgif_api.routes.organisations.transform_agent_ref_to_organisation",
                return_value=transformed_organisation,
            ) as mock_transform,
        ):
            response = await organisations.get_organisations(
                request=request, pagination=Pagination(page=2, page_size=1)
            )

        self.assertEqual(response.status_code, 200)
        mock_transform.assert_called_once_with(second_ref)
        self.assertIn("second-organisation", response.body.decode())

    async def test_get_organisation_by_id_found(self):
        request = make_fake_request()

        organisation_ref = MagicMock()
        index = MagicMock()
        index.organisation_by_id = {"normalised-organisation-id": organisation_ref}

        transformed_organisation = make_transformed_organisation(local_identifier="normalised-organisation-id")

        with (
            patch(
                "cessda_skgif_api.routes.organisations.normalize_agent_lookup_identifier",
                return_value="normalised-organisation-id",
            ) as mock_normalise,
            patch(
                "cessda_skgif_api.routes.organisations.ensure_agent_index",
                new=AsyncMock(return_value=index),
            ),
            patch(
                "cessda_skgif_api.routes.organisations.transform_agent_ref_to_organisation",
                return_value=transformed_organisation,
            ) as mock_transform,
        ):
            response = await organisations.get_organisation_by_id(
                request=request, local_identifier="https://ror.org/00bwtjf83"
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("normalised-organisation-id", response.body.decode())

        mock_normalise.assert_called_once_with("https://ror.org/00bwtjf83", entity_type="organisation")
        mock_transform.assert_called_once_with(organisation_ref)
        transformed_organisation.model_dump.assert_called_once_with(by_alias=True, exclude_none=True)

    async def test_get_organisation_by_id_not_found(self):
        request = make_fake_request()

        index = MagicMock()
        index.organisation_by_id = {}

        with (
            patch(
                "cessda_skgif_api.routes.organisations.normalize_agent_lookup_identifier",
                return_value="missing-organisation-id",
            ),
            patch(
                "cessda_skgif_api.routes.organisations.ensure_agent_index",
                new=AsyncMock(return_value=index),
            ),
            patch("cessda_skgif_api.routes.organisations.transform_agent_ref_to_organisation") as mock_transform,
        ):
            response = await organisations.get_organisation_by_id(
                request=request, local_identifier="missing-organisation-id"
            )

        self.assertEqual(response.status_code, 404)
        self.assertIn('"@graph":[]', response.body.decode())
        self.assertIn("missing-organisation-id", response.body.decode())
        mock_transform.assert_not_called()
