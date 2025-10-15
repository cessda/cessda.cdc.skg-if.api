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

import configargparse
import os
import sys


def load_config(config_file="cessda_skgif_api.ini"):
    if not os.path.exists(config_file):
        print(f"Configuration file '{config_file}' not found. Please create it from 'cessda_skgif_api.ini.dist'.")
        sys.exit(1)

    parser = configargparse.ArgParser(default_config_files=[config_file])

    # MongoDB settings
    parser.add("--mongodb_server", help="MongoDB server and port (e.g., localhost:27017)")
    parser.add("--mongodb_database", help="MongoDB database name")
    parser.add("--mongodb_collection", help="MongoDB collection name")
    parser.add("--mongodb_username", help="MongoDB username", default="")
    parser.add("--mongodb_password", help="MongoDB password", default="")

    # External API URLs
    parser.add(
        "--cessda_vocab_api_url",
        help="Base URL for CESSDA Vocabulary API",
        default="https://vocabularies.cessda.eu/v2/codes/TopicClassification",
    )
    parser.add(
        "--cessda_vocab_api_version",
        help="Version for CESSDA Vocabulary API",
        default="4.2.2",
    )
    parser.add(
        "--finto_api_url",
        help="Base URL for Finto API",
        default="https://api.finto.fi/rest/v1/search?vocab=okm-tieteenala",
    )

    # Data access mapping
    parser.add(
        "--data_access_mapping_file_url",
        help="URL for Data Access mapping file",
        default="https://raw.githubusercontent.com/cessda/cessda.cdc.osmh-indexer.cmm/main/src/main/resources/data_access_mappings.json",
    )

    return parser.parse_known_args()[0]
