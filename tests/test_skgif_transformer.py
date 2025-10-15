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

import difflib
import unittest
import json
from pathlib import Path
from cessda_skgif_api.transformers.skgif_transformer import (
    transform_study_to_skgif_product,
)
from cessda_skgif_api.routes.products import wrap_jsonld


def compare_json_structures(expected, actual):
    expected_str = json.dumps(expected, sort_keys=True, indent=2)
    actual_str = json.dumps(actual, sort_keys=True, indent=2)

    if expected_str != actual_str:
        diff = difflib.unified_diff(
            expected_str.splitlines(),
            actual_str.splitlines(),
            fromfile="expected",
            tofile="actual",
            lineterm="",
        )
        return "\n".join(diff)
    return None


def clean_dict(d):
    if isinstance(d, dict):
        return {
            k: clean_dict(v)
            for k, v in d.items()
            if not (k == "local_identifier" and isinstance(v, str) and v.startswith("otf__"))
        }
    elif isinstance(d, list):
        return [clean_dict(item) for item in d]
    else:
        return d


def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestSKGIFTransformer(unittest.TestCase):
    def test_transformation_output(self):
        base_dir = Path(__file__).parent
        input_file = base_dir / "kuha_output.json"
        expected_file = base_dir / "synthetic_example.json"

        self.assertTrue(input_file.exists(), f"{input_file} does not exist.")
        self.assertTrue(expected_file.exists(), f"{expected_file} does not exist.")

        input_data = load_json(input_file)
        expected_output = clean_dict(load_json(expected_file))
        raw_output = transform_study_to_skgif_product(input_data).model_dump(by_alias=True, exclude_none=True)
        actual_output = clean_dict(wrap_jsonld(raw_output))

        diff = compare_json_structures(expected_output, actual_output)
        if diff:
            print("\nDifferences:\n", diff)
            self.fail("Transformed output does not match expected output.")
