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

import unittest
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from cessda_skgif_api.routes import topics

# Create FastAPI app and include router
app = FastAPI()
app.include_router(topics.router, prefix="/topics")


def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestTopicsEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Mock minimal ELSST data for tests
        topics.ELSST_DATA.clear()
        topics.SEARCH_INDEX.clear()
        concept_id = "https://elsst.cessda.eu/id/5/000e1113-ffda-4088-8278-020b6dc71e20"
        topics.ELSST_DATA[concept_id] = {
            "@id": concept_id,
            "prefLabels": {"en": "Teaching Profession", "fr": "Profession d'enseignant"},
            "altLabels": {"en": ["Education", "Teacher"]},
        }
        topics.SEARCH_INDEX["en"] = [("teaching profession", concept_id), ("education", concept_id)]

    def validate_jsonld_structure(self, data, expect_meta=True):
        self.assertIn("@context", data)
        self.assertIn("@graph", data)
        self.assertIsInstance(data["@graph"], list)
        if expect_meta:
            self.assertIn("meta", data)

    def test_get_single_topic_success_encoded_and_unencoded(self):
        concept_id = "https://elsst.cessda.eu/id/5/000e1113-ffda-4088-8278-020b6dc71e20"
        encoded_id = "https%3A%2F%2Felsst.cessda.eu%2Fid%2F5%2F000e1113-ffda-4088-8278-020b6dc71e20"

        # Encoded URI
        response_encoded = self.client.get(f"/topics/{encoded_id}")
        self.assertEqual(response_encoded.status_code, 200)
        data_encoded = response_encoded.json()
        self.validate_jsonld_structure(data_encoded, expect_meta=False)  # Single topic should NOT have meta
        self.assertEqual(data_encoded["@graph"][0]["local_identifier"], concept_id)

        # Unencoded URI
        response_unencoded = self.client.get(f"/topics/{concept_id}")
        self.assertEqual(response_unencoded.status_code, 200)
        data_unencoded = response_unencoded.json()
        self.validate_jsonld_structure(data_unencoded, expect_meta=False)
        self.assertEqual(data_unencoded["@graph"][0]["local_identifier"], concept_id)

    def test_get_single_topic_not_found(self):
        response = self.client.get("/topics/https%3A%2F%2Felsst.cessda.eu%2Fid%2F5%2Fnonexistent")
        self.assertEqual(response.status_code, 404)

    def test_get_topic_suggestions_success(self):
        response = self.client.get("/topics?filter=cf.search.labels:teaching,cf.search.language:en")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.validate_jsonld_structure(data, expect_meta=True)
        for item in data["@graph"]:
            self.assertIn("local_identifier", item)
            self.assertIn("labels", item)

    def test_get_topic_suggestions_invalid_filter(self):
        response = self.client.get("/topics?filter=invalidfilter")
        self.assertEqual(response.status_code, 422)

    def test_get_topic_suggestions_without_filter(self):
        response = self.client.get("/topics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.validate_jsonld_structure(data, expect_meta=True)
        flat_graph = data["@graph"]
        self.assertGreater(len(flat_graph), 0)

    def test_show_index_data(self):
        response = self.client.get("/topics/show_index_data")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("elsst_data_sample", data)
        self.assertIn("search_index_sample", data)

    def test_compare_with_updated_example_output_structure(self):
        base_dir = Path(__file__).parent
        expected_file = base_dir / "synthetic_topic_example.jsonld"
        self.assertTrue(expected_file.exists(), f"{expected_file} does not exist.")

        expected_output = load_json(expected_file)
        # Validate top-level keys
        self.assertIn("@context", expected_output)
        self.assertIn("@graph", expected_output)
        self.assertIsInstance(expected_output["@graph"], list)
        self.assertIn("meta", expected_output)  # Example output for list response should have meta

        # Validate meta structure
        meta = expected_output["meta"]
        self.assertIn("local_identifier", meta)
        self.assertIn("entity_type", meta)
        self.assertIn("part_of", meta)
        self.assertIn("total_items", meta["part_of"])

        # Validate topics in @graph
        for item in expected_output["@graph"]:
            self.assertIn("local_identifier", item)
            self.assertIn("entity_type", item)
            self.assertIn("labels", item)
