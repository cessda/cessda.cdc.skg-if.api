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
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.requests import Request

from cessda_skgif_api.cache.product_index import ProductIndex, ProductRef
from cessda_skgif_api.routes import products
from cessda_skgif_api.utils.identifier_utils import (
    generate_related_publication_local_identifier,
)
from tests import FakeCollection


def make_fake_request(
    *,
    query_string: bytes = b"",
    accept: str | None = None,
    state: SimpleNamespace | None = None,
):
    if state is None:
        state = SimpleNamespace(product_index=None)

    headers = []

    if accept is not None:
        headers.append((b"accept", accept.encode("ascii")))

    app = SimpleNamespace(state=state)

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


class TestAsyncEndpoints(unittest.IsolatedAsyncioTestCase):
    async def test_get_products(self):
        req = make_fake_request()

        fake_ref = ProductRef(product_id="ABC123", product_type="research data", titles=["Test"])

        req.app.state.product_index = ProductIndex(refs=[fake_ref], ref_by_id={"ABC123": fake_ref})

        with (
            patch("cessda_skgif_api.routes.products.fetch_docs_for_refs") as mock_fetch_docs,
            patch("cessda_skgif_api.routes.products.materialise_product_from_ref") as mock_materialise,
        ):
            mock_fetch_docs.return_value = {"ABC123": {"_aggregator_identifier": "ABC123"}}

            product = MagicMock()
            product.model_dump.return_value = {"id": "ABC123"}

            mock_materialise.return_value = product

            response = await products.get_products(
                request=req,
                pagination=products.Pagination(page=1, page_size=10),
                _filter=None,
            )

        body = response.body.decode()

        self.assertIn("meta", body)
        self.assertIn("ABC123", body)

    async def test_get_product_by_id_found(self):
        fake_ref = ProductRef(product_id="ABC123", product_type="research data")

        req = make_fake_request()

        req.app.state.product_index = ProductIndex(refs=[fake_ref], ref_by_id={"ABC123": fake_ref})

        fake_doc = {"_aggregator_identifier": "ABC123"}

        fake_coll = FakeCollection(docs=[fake_doc], one=fake_doc, count=1)

        with (
            patch(
                "cessda_skgif_api.routes.products.get_collection",
                return_value=fake_coll,
            ),
            patch("cessda_skgif_api.routes.products.transform_study_to_skgif_product") as mock_transform,
        ):
            product = MagicMock()

            product.model_dump.return_value = {"id": "ABC123"}

            mock_transform.return_value = product

            response = await products.get_product_by_id(request=req, local_identifier="ABC123")

        self.assertIn("ABC123", response.body.decode())

    async def test_get_product_by_id_not_found(self):
        req = make_fake_request()

        req.app.state.product_index = ProductIndex(refs=[], ref_by_id={})

        response = await products.get_product_by_id(request=req, local_identifier="XYZ")

        self.assertEqual(response.status_code, 404)

        body = response.body.decode()

        self.assertIn('"entity_type":"single_entity"', body)

        self.assertIn('"@graph":[]', body)

    async def test_get_product_by_id_related_publication(self):

        publication = {
            "identifier": "10.1234/test",
            "identifier_agency": "doi",
            "related_publication": "Test publication",
            "distribution_date": "2020",
        }

        relpub_id = generate_related_publication_local_identifier([publication])

        ref = ProductRef(
            product_id=relpub_id,
            product_type="literature",
            relpub_group=[publication],
            cited_studies=["ABC123", "XYZ456"],
            titles=["Test publication"],
        )

        req = make_fake_request()

        req.app.state.product_index = ProductIndex(refs=[ref], ref_by_id={relpub_id: ref})

        with patch("cessda_skgif_api.routes.products.transform_related_publication_to_skgif_product") as mock_transform:
            product = MagicMock()

            product.model_dump.return_value = {
                "product_type": "literature",
                "related_products": {"cites": ["ABC123", "XYZ456"]},
            }

            mock_transform.return_value = product

            response = await products.get_product_by_id(request=req, local_identifier=relpub_id)

        body = response.body.decode()

        self.assertIn("literature", body)

    async def test_get_products_redirects_html_request_to_explicit_pagination(self):
        request = make_fake_request(query_string=b"filter=product_type:research%20data", accept="text/html")

        with patch("cessda_skgif_api.routes.products.ensure_product_index", new=AsyncMock()) as mock_ensure_index:
            response = await products.get_products(
                request=request,
                pagination=products.Pagination(page=1, page_size=10),
                _filter=None,
            )

        self.assertEqual(response.status_code, 302)

        location = response.headers["location"]

        self.assertIn("/products?", location)
        self.assertIn("page=1", location)
        self.assertIn("page_size=10", location)
        self.assertIn("filter=product_type:research%20data", location)

        mock_ensure_index.assert_not_awaited()

    async def test_get_products_returns_not_found_when_filter_matches_nothing(self):
        request = make_fake_request(query_string=b"page=1&page_size=10")

        index = ProductIndex(refs=[], ref_by_id={})

        with (
            patch(
                "cessda_skgif_api.routes.products.ensure_product_index",
                new=AsyncMock(return_value=index),
            ),
            patch(
                "cessda_skgif_api.routes.products.parse_product_filter_raw",
                return_value=[],
            ),
            patch("cessda_skgif_api.routes.products.filter_product_refs", return_value=[]),
        ):
            response = await products.get_products(
                request=request,
                pagination=products.Pagination(page=1, page_size=10),
                _filter=None,
            )

        self.assertEqual(response.status_code, 404)
        self.assertIn('"@graph":[]', response.body.decode())
        self.assertIn('"entity_type":"search_result_page"', response.body.decode())

    async def test_get_products_returns_studies_and_related_publications(self):
        request = make_fake_request(query_string=b"page=1&page_size=10")

        study_ref = ProductRef(product_id="ABC123", product_type="research data")

        literature_ref = ProductRef(
            product_id="publication-id",
            product_type="literature",
            relpub_group=[{"related_publication": "Test publication"}],
            cited_studies=["ABC123"],
        )

        index = ProductIndex(
            refs=[study_ref, literature_ref],
            ref_by_id={"ABC123": study_ref, "publication-id": literature_ref},
        )

        study_product = MagicMock()
        study_product.model_dump.return_value = {
            "local_identifier": "ABC123",
            "product_type": "research data",
        }

        literature_product = MagicMock()
        literature_product.model_dump.return_value = {
            "local_identifier": "publication-id",
            "product_type": "literature",
        }

        with (
            patch(
                "cessda_skgif_api.routes.products.ensure_product_index",
                new=AsyncMock(return_value=index),
            ),
            patch(
                "cessda_skgif_api.routes.products.parse_product_filter_raw",
                return_value=[],
            ),
            patch(
                "cessda_skgif_api.routes.products.filter_product_refs",
                return_value=[study_ref, literature_ref],
            ),
            patch(
                "cessda_skgif_api.routes.products.fetch_docs_for_refs",
                new=AsyncMock(
                    return_value={
                        "ABC123": {
                            "_aggregator_identifier": "ABC123",
                            "classifications": [],
                        }
                    }
                ),
            ),
            patch(
                "cessda_skgif_api.routes.products.materialise_product_from_ref",
                return_value=study_product,
            ),
            patch(
                "cessda_skgif_api.routes.products.transform_related_publication_to_skgif_product",
                return_value=literature_product,
            ) as mock_transform_publication,
            patch(
                "cessda_skgif_api.routes.products.generate_study_local_identifier",
                return_value="study-local-identifier",
            ),
        ):
            response = await products.get_products(
                request=request,
                pagination=products.Pagination(page=1, page_size=10),
                _filter=None,
            )

        self.assertEqual(response.status_code, 200)

        body = response.body.decode()

        self.assertIn("research data", body)
        self.assertIn("literature", body)

        mock_transform_publication.assert_called_once_with(
            related_publication_group=literature_ref.relpub_group,
            cited_studies=["study-local-identifier"],
        )

    async def test_get_products_continues_after_transformation_error(self):
        request = make_fake_request(query_string=b"page=1&page_size=10")

        broken_ref = ProductRef(product_id="BROKEN", product_type="research data")

        valid_ref = ProductRef(product_id="VALID", product_type="research data")

        index = ProductIndex(
            refs=[broken_ref, valid_ref],
            ref_by_id={"BROKEN": broken_ref, "VALID": valid_ref},
        )

        valid_product = MagicMock()
        valid_product.model_dump.return_value = {"local_identifier": "VALID"}

        def materialise(ref, document):
            if ref.product_id == "BROKEN":
                raise ValueError("Invalid source metadata")

            return valid_product

        with (
            patch(
                "cessda_skgif_api.routes.products.ensure_product_index",
                new=AsyncMock(return_value=index),
            ),
            patch(
                "cessda_skgif_api.routes.products.parse_product_filter_raw",
                return_value=[],
            ),
            patch(
                "cessda_skgif_api.routes.products.filter_product_refs",
                return_value=[broken_ref, valid_ref],
            ),
            patch(
                "cessda_skgif_api.routes.products.fetch_docs_for_refs",
                new=AsyncMock(
                    return_value={
                        "BROKEN": {"_aggregator_identifier": "BROKEN"},
                        "VALID": {"_aggregator_identifier": "VALID"},
                    }
                ),
            ),
            patch(
                "cessda_skgif_api.routes.products.materialise_product_from_ref",
                side_effect=materialise,
            ),
            patch("cessda_skgif_api.routes.products._logger.exception") as mock_log,
        ):
            response = await products.get_products(
                request=request,
                pagination=products.Pagination(page=1, page_size=10),
                _filter=None,
            )

        self.assertEqual(response.status_code, 200)

        body = response.body.decode()

        self.assertIn("VALID", body)
        self.assertNotIn('"local_identifier":"BROKEN"', body)
        mock_log.assert_called_once()

    async def test_get_product_by_id_loads_required_topic_languages(self):
        request = make_fake_request()

        ref = ProductRef(product_id="ABC123", product_type="research data")

        request.app.state.product_index = ProductIndex(refs=[ref], ref_by_id={"ABC123": ref})

        document = {
            "_aggregator_identifier": "ABC123",
            "classifications": [{"language": "fi"}, {"language": "en"}],
        }

        collection = MagicMock()
        collection.find_one = AsyncMock(return_value=document)

        product = MagicMock()
        product.model_dump.return_value = {"local_identifier": "ABC123"}

        loaded_languages = []

        async def load_language(language):
            loaded_languages.append(language)

        with (
            patch(
                "cessda_skgif_api.routes.products.get_collection",
                return_value=collection,
            ),
            patch(
                "cessda_skgif_api.routes.products.load_cessda_topic_vocab",
                side_effect=load_language,
            ),
            patch(
                "cessda_skgif_api.routes.products.transform_study_to_skgif_product",
                return_value=product,
            ),
        ):
            response = await products.get_product_by_id(request=request, local_identifier="ABC123")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(loaded_languages), {"en", "fi"})

    def test_extract_languages_from_doc(self):
        document = {
            "classifications": [
                {"language": "fi"},
                {"language": "en"},
                {},
                "invalid",
                {"language": ""},
                {"language": None},
            ]
        }

        self.assertEqual(products.extract_languages_from_doc(document), {"en", "fi"})

    def test_materialise_research_data_product(self):
        ref = ProductRef(product_id="ABC123", product_type="research data")

        document = {"_aggregator_identifier": "ABC123"}

        transformed = MagicMock()

        with patch(
            "cessda_skgif_api.routes.products.transform_study_to_skgif_product",
            return_value=transformed,
        ) as mock_transform:
            result = products.materialise_product_from_ref(ref, document)

        self.assertIs(result, transformed)
        mock_transform.assert_called_once_with(document)

    def test_materialise_related_publication_not_found(self):
        ref = ProductRef(
            product_id="publication-id",
            product_type="literature",
            relpub_group_key="expected-group",
        )

        document = {"related_publications": [{"related_publication": "Different publication"}]}

        with (
            patch(
                "cessda_skgif_api.routes.products.group_related_publications",
                return_value=[document["related_publications"]],
            ),
            patch(
                "cessda_skgif_api.routes.products.build_related_publication_group_key",
                return_value="different-group",
            ),
            self.assertRaises(products.HTTPException) as context,
        ):
            products.materialise_product_from_ref(ref, document)

        self.assertEqual(context.exception.status_code, 404)

    def test_materialise_unknown_product_type(self):
        ref = ProductRef(product_id="unknown-id", product_type="unknown")

        with self.assertRaises(products.HTTPException) as context:
            products.materialise_product_from_ref(ref, {})

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(context.exception.detail, "Unknown product type: unknown")

    async def test_ensure_product_index_returns_existing_index(self):
        request = make_fake_request()

        index = ProductIndex(refs=[], ref_by_id={})

        request.app.state.product_index = index

        result = await products.ensure_product_index(request)

        self.assertIs(result, index)

    async def test_ensure_product_index_builds_missing_index(self):
        request = make_fake_request()

        request.app.state = SimpleNamespace()

        collection = MagicMock()

        built_index = ProductIndex(refs=[], ref_by_id={})

        with (
            patch(
                "cessda_skgif_api.routes.products.get_collection",
                return_value=collection,
            ),
            patch(
                "cessda_skgif_api.routes.products.build_product_index",
                new=AsyncMock(return_value=built_index),
            ) as mock_build,
        ):
            result = await products.ensure_product_index(request)

        self.assertIs(result, built_index)

        self.assertIs(request.app.state.product_index, built_index)

        mock_build.assert_awaited_once_with(collection)

    async def test_fetch_docs_for_refs_returns_empty_when_no_studies(self):
        request = make_fake_request()

        literature_ref = ProductRef(product_id="publication-id", product_type="literature")

        collection = MagicMock()

        with patch("cessda_skgif_api.routes.products.get_collection", return_value=collection):
            result = await products.fetch_docs_for_refs(request, [literature_ref])

        self.assertEqual(result, {})

        collection.find.assert_not_called()

    async def test_get_product_by_id_study_missing_in_mongodb(self):
        ref = ProductRef(product_id="ABC123", product_type="research data")

        request = make_fake_request()

        request.app.state.product_index = ProductIndex(refs=[ref], ref_by_id={"ABC123": ref})

        collection = MagicMock()

        collection.find_one = AsyncMock(return_value=None)

        with patch("cessda_skgif_api.routes.products.get_collection", return_value=collection):
            response = await products.get_product_by_id(request=request, local_identifier="ABC123")

        self.assertEqual(response.status_code, 404)

        self.assertIn('"entity_type":"single_entity"', response.body.decode())

    async def test_get_products_skips_missing_study_document(self):
        request = make_fake_request(query_string=b"page=1&page_size=10")

        ref = ProductRef(product_id="ABC123", product_type="research data")

        index = ProductIndex(refs=[ref], ref_by_id={"ABC123": ref})

        with (
            patch(
                "cessda_skgif_api.routes.products.ensure_product_index",
                new=AsyncMock(return_value=index),
            ),
            patch(
                "cessda_skgif_api.routes.products.parse_product_filter_raw",
                return_value=[],
            ),
            patch(
                "cessda_skgif_api.routes.products.filter_product_refs",
                return_value=[ref],
            ),
            patch(
                "cessda_skgif_api.routes.products.fetch_docs_for_refs",
                new=AsyncMock(return_value={}),
            ),
            patch("cessda_skgif_api.routes.products.materialise_product_from_ref") as mock_materialise,
        ):
            response = await products.get_products(
                request=request,
                pagination=products.Pagination(page=1, page_size=10),
                _filter=None,
            )

        self.assertEqual(response.status_code, 200)

        body = response.body.decode()

        self.assertIn('"@graph":[]', body)

        mock_materialise.assert_not_called()
