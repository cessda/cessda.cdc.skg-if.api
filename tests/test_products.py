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
from unittest.mock import MagicMock, patch
from starlette.requests import Request
from cessda_skgif_api.routes import products
from tests import FakeCollection
from cessda_skgif_api.cache.product_index import ProductIndex, ProductRef
from cessda_skgif_api.utils.identifier_utils import (
    generate_related_publication_local_identifier,
)
from unittest.mock import MagicMock


def make_fake_request():
    app = MagicMock()
    app.state = MagicMock()

    app.state.product_index = None
    app.state.product_index_lock = None

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


class TestAsyncEndpoints(unittest.IsolatedAsyncioTestCase):

    async def test_get_products(self):
        req = make_fake_request()

        fake_ref = ProductRef(
            product_id="ABC123",
            product_type="research data",
            titles=["Test"],
        )

        req.app.state.product_index = ProductIndex(
            refs=[fake_ref],
            ref_by_id={"ABC123": fake_ref},
        )

        with (
            patch(
                "cessda_skgif_api.routes.products.fetch_docs_for_refs"
            ) as mock_fetch_docs,
            patch(
                "cessda_skgif_api.routes.products.materialise_product_from_ref"
            ) as mock_materialise,
        ):

            mock_fetch_docs.return_value = {
                "ABC123": {
                    "_aggregator_identifier": "ABC123",
                }
            }

            product = MagicMock()
            product.model_dump.return_value = {
                "id": "ABC123",
            }

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
        fake_ref = ProductRef(
            product_id="ABC123",
            product_type="research data",
        )

        req = make_fake_request()

        req.app.state.product_index = ProductIndex(
            refs=[fake_ref],
            ref_by_id={
                "ABC123": fake_ref,
            },
        )

        fake_doc = {
            "_aggregator_identifier": "ABC123",
        }

        fake_coll = FakeCollection(
            docs=[fake_doc],
            one=fake_doc,
            count=1,
        )

        with (
            patch(
                "cessda_skgif_api.routes.products.get_collection",
                return_value=fake_coll,
            ),
            patch(
                "cessda_skgif_api.routes.products.transform_study_to_skgif_product"
            ) as mock_transform,
        ):

            product = MagicMock()

            product.model_dump.return_value = {
                "id": "ABC123",
            }

            mock_transform.return_value = product

            response = await products.get_product_by_id(
                request=req,
                local_identifier="ABC123",
            )

        self.assertIn(
            "ABC123",
            response.body.decode(),
        )

    async def test_get_product_by_id_not_found(self):
        req = make_fake_request()

        req.app.state.product_index = ProductIndex(
            refs=[],
            ref_by_id={},
        )

        response = await products.get_product_by_id(
            request=req,
            local_identifier="XYZ",
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        body = response.body.decode()

        self.assertIn(
            '"entity_type":"single_entity"',
            body,
        )

        self.assertIn(
            '"@graph":[]',
            body,
        )

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

        req.app.state.product_index = ProductIndex(
            refs=[ref],
            ref_by_id={
                relpub_id: ref,
            },
        )

        with patch(
            "cessda_skgif_api.routes.products.transform_related_publication_to_skgif_product"
        ) as mock_transform:

            product = MagicMock()

            product.model_dump.return_value = {
                "product_type": "literature",
                "related_products": {
                    "cites": [
                        "ABC123",
                        "XYZ456",
                    ]
                },
            }

            mock_transform.return_value = product

            response = await products.get_product_by_id(
                request=req,
                local_identifier=relpub_id,
            )

        body = response.body.decode()

        self.assertIn("literature", body)
