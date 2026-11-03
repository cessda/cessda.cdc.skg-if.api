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

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cessda_skgif_api.routes import topics

app = FastAPI()
app.include_router(topics.router, prefix="/topics")


def load_json(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


class TestTopicsEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

        # Preserve the application data so this test module does not
        # permanently modify module-level state used by other tests.
        cls.original_elsst_data = topics.ELSST_DATA.copy()

        cls.original_search_index = {language: items.copy() for language, items in topics.SEARCH_INDEX.items()}

        topics.ELSST_DATA.clear()
        topics.SEARCH_INDEX.clear()

        cls.concept_one = "https://elsst.cessda.eu/id/5/000e1113-ffda-4088-8278-020b6dc71e20"

        cls.concept_two = "https://elsst.cessda.eu/id/test/higher-education"

        cls.concept_three = "https://elsst.cessda.eu/id/test/healthcare"

        topics.ELSST_DATA.update(
            {
                cls.concept_one: {
                    "@id": cls.concept_one,
                    "prefLabels": {
                        "en": "Teaching Profession",
                        "fr": "Profession d'enseignant",
                    },
                    "altLabels": {"en": ["Education", "Teacher"]},
                    "broader": None,
                },
                cls.concept_two: {
                    "@id": cls.concept_two,
                    "prefLabels": {"en": "Higher Education"},
                    "altLabels": {},
                    "broader": cls.concept_one,
                },
                cls.concept_three: {
                    "@id": cls.concept_three,
                    "prefLabels": {"en": "Healthcare"},
                    "altLabels": {},
                    "broader": None,
                },
            }
        )

        topics.SEARCH_INDEX.update(
            {
                "en": [
                    ("teaching profession", cls.concept_one),
                    ("education", cls.concept_one),
                    ("teacher", cls.concept_one),
                    ("higher education", cls.concept_two),
                    ("healthcare", cls.concept_three),
                ],
                "fr": [("profession d'enseignant", cls.concept_one)],
            }
        )

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

        topics.ELSST_DATA.clear()
        topics.ELSST_DATA.update(cls.original_elsst_data)

        topics.SEARCH_INDEX.clear()
        topics.SEARCH_INDEX.update(cls.original_search_index)

    def validate_jsonld_structure(self, data, *, expected_meta_entity_type=None):
        self.assertIn("@context", data)

        self.assertIn("@graph", data)

        self.assertIsInstance(data["@graph"], list)

        if expected_meta_entity_type is not None:
            self.assertIn("meta", data)

            self.assertEqual(data["meta"]["entity_type"], expected_meta_entity_type)

    def test_get_single_topic_success_with_encoded_identifier(self):
        encoded_id = "https%3A%2F%2Felsst.cessda.eu%2Fid%2F5%2F000e1113-ffda-4088-8278-020b6dc71e20"

        response = self.client.get(f"/topics/{encoded_id}")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.validate_jsonld_structure(data, expected_meta_entity_type="single_entity")

        self.assertEqual(data["meta"]["local_identifier"], self.concept_one)

        self.assertEqual(len(data["@graph"]), 1)

        topic = data["@graph"][0]

        self.assertEqual(topic["local_identifier"], self.concept_one)

        self.assertEqual(topic["entity_type"], "topic")

        self.assertEqual(topic["labels"]["en"], "Teaching Profession")

    def test_get_single_topic_success_with_unencoded_identifier(self):
        response = self.client.get(f"/topics/{self.concept_one}")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.validate_jsonld_structure(data, expected_meta_entity_type="single_entity")

        self.assertEqual(data["meta"]["local_identifier"], self.concept_one)

        self.assertEqual(data["@graph"][0]["local_identifier"], self.concept_one)

    def test_get_single_topic_repairs_missing_second_https_slash(self):
        response = self.client.get("/topics/https:/elsst.cessda.eu/id/5/000e1113-ffda-4088-8278-020b6dc71e20")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.validate_jsonld_structure(data, expected_meta_entity_type="single_entity")

        self.assertEqual(data["meta"]["local_identifier"], self.concept_one)

        self.assertEqual(data["@graph"][0]["local_identifier"], self.concept_one)

    def test_get_single_topic_not_found(self):
        missing_id = "https://elsst.cessda.eu/id/5/nonexistent"

        encoded_id = "https%3A%2F%2Felsst.cessda.eu%2Fid%2F5%2Fnonexistent"

        response = self.client.get(f"/topics/{encoded_id}")

        self.assertEqual(response.status_code, 404)

        data = response.json()

        self.validate_jsonld_structure(data, expected_meta_entity_type="single_entity")

        self.assertEqual(data["meta"]["local_identifier"], missing_id)

        self.assertEqual(data["@graph"], [])

    def test_get_topics_without_filter(self):
        response = self.client.get("/topics?page=1&page_size=10")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.validate_jsonld_structure(data, expected_meta_entity_type="search_result_page")

        self.assertEqual(len(data["@graph"]), 3)

        self.assertEqual(data["meta"]["part_of"]["total_items"], 3)

    def test_topic_search_matches_preferred_label(self):
        response = self.client.get("/topics?filter=cf.search.labels:teaching,cf.search.language:en&page=1&page_size=10")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.validate_jsonld_structure(data, expected_meta_entity_type="search_result_page")

        self.assertEqual(len(data["@graph"]), 1)

        self.assertEqual(data["@graph"][0]["local_identifier"], self.concept_one)

        self.assertEqual(data["@graph"][0]["labels"]["en"], "Teaching Profession")

    def test_topic_search_matches_alternative_label(self):
        response = self.client.get("/topics?filter=cf.search.labels:teacher,cf.search.language:en&page=1&page_size=10")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(len(data["@graph"]), 1)

        self.assertEqual(data["@graph"][0]["local_identifier"], self.concept_one)

        self.assertEqual(data["@graph"][0]["labels"]["en"], "Teaching Profession")

    def test_topic_search_defaults_to_english(self):
        response = self.client.get("/topics?filter=cf.search.labels:teaching&page=1&page_size=10")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(len(data["@graph"]), 1)

        self.assertEqual(data["@graph"][0]["local_identifier"], self.concept_one)

        self.assertEqual(data["@graph"][0]["labels"]["en"], "Teaching Profession")

    def test_topic_search_uses_requested_language(self):
        response = self.client.get(
            "/topics?filter=cf.search.labels:profession,cf.search.language:fr&page=1&page_size=10"
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(len(data["@graph"]), 1)

        self.assertEqual(data["@graph"][0]["local_identifier"], self.concept_one)

        self.assertEqual(data["@graph"][0]["labels"]["fr"], "Profession d'enseignant")

    def test_topic_search_preserves_percent_encoded_comma(self):
        comma_concept_id = "https://elsst.cessda.eu/id/test/health-wellbeing"

        comma_concept = {
            "@id": comma_concept_id,
            "prefLabels": {"en": "Health, wellbeing"},
            "altLabels": {},
            "broader": None,
        }

        with (
            patch.dict(topics.ELSST_DATA, {comma_concept_id: comma_concept}, clear=True),
            patch.dict(
                topics.SEARCH_INDEX,
                {"en": [("health, wellbeing", comma_concept_id)]},
                clear=True,
            ),
        ):
            response = self.client.get(
                "/topics?filter=cf.search.labels:health%2C%20wellbeing,cf.search.language:en&page=1&page_size=10"
            )

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(len(data["@graph"]), 1)

        self.assertEqual(data["@graph"][0]["local_identifier"], comma_concept_id)

        self.assertEqual(data["@graph"][0]["labels"]["en"], "Health, wellbeing")

    def test_topic_search_returns_not_found_when_no_topics_match(self):
        response = self.client.get(
            "/topics?filter=cf.search.labels:nonexistent,cf.search.language:en&page=1&page_size=10"
        )

        self.assertEqual(response.status_code, 404)

        data = response.json()

        self.validate_jsonld_structure(data, expected_meta_entity_type="search_result_page")

        self.assertEqual(data["@graph"], [])

        self.assertEqual(data["meta"]["part_of"]["total_items"], 0)

    def test_topics_apply_pagination(self):
        response = self.client.get("/topics?page=2&page_size=1")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.validate_jsonld_structure(data, expected_meta_entity_type="search_result_page")

        self.assertEqual(len(data["@graph"]), 1)

        self.assertEqual(data["meta"]["part_of"]["total_items"], 3)

        self.assertIn("previous_page", data["meta"])

        self.assertIn("next_page", data["meta"])

    def test_topics_redirect_html_request_to_explicit_pagination(self):
        response = self.client.get(
            "/topics?filter=cf.search.labels:teaching",
            headers={"accept": "text/html"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)

        location = response.headers["location"]

        self.assertIn("/topics?", location)

        self.assertIn("page=1", location)

        self.assertIn("page_size=10", location)

        self.assertIn("filter=cf.search.labels:teaching", location)

    def test_topics_do_not_redirect_when_pagination_is_present(self):
        response = self.client.get(
            "/topics?page=1&page_size=10",
            headers={"accept": "text/html"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.json()["@graph"]), 3)

    def test_show_index_data(self):
        response = self.client.get("/topics/show_index_data")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertIn("elsst_data_sample", data)

        self.assertIn("search_index_sample", data)

        self.assertLessEqual(len(data["elsst_data_sample"]), 10)

        for items in data["search_index_sample"].values():
            self.assertLessEqual(len(items), 10)

    def test_compare_with_updated_example_output_structure(self):
        base_dir = Path(__file__).parent
        expected_file = base_dir / "topic_example.jsonld"

        self.assertTrue(expected_file.exists(), f"{expected_file} does not exist.")

        expected_output = load_json(expected_file)

        self.validate_jsonld_structure(expected_output, expected_meta_entity_type="search_result_page")

        meta = expected_output["meta"]

        self.assertIn("local_identifier", meta)

        self.assertIn("part_of", meta)

        self.assertIn("total_items", meta["part_of"])

        for item in expected_output["@graph"]:
            self.assertIn("local_identifier", item)

            self.assertEqual(item["entity_type"], "topic")

            self.assertIn("labels", item)
