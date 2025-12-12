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

"""This module handles loading settings from a configuration file"""

import os
import sys
import configargparse


def load_config(config_file="cessda_skgif_api.ini"):
    """Loads various settings from specified or default configuration file"""
    if not os.path.exists(config_file):
        print(f"Configuration file '{config_file}' not found. Please create it from 'cessda_skgif_api.ini.dist'.")
        sys.exit(1)

    parser = configargparse.ArgParser(default_config_files=[config_file])

    # MongoDB settings
    parser.add(
        "--mongodb_server",
        env_var="MONGODB_SERVER",
        help="MongoDB server and port (e.g. localhost:27017)",
    )
    parser.add("--mongodb_database", env_var="MONGODB_DATABASE", help="MongoDB database name")
    parser.add(
        "--mongodb_collection",
        env_var="MONGODB_COLLECTION",
        help="MongoDB collection name",
    )
    parser.add(
        "--mongodb_username",
        env_var="MONGODB_USERNAME",
        help="MongoDB username",
        default="",
    )
    parser.add(
        "--mongodb_password",
        env_var="MONGODB_PASSWORD",
        help="MongoDB password",
        default="",
    )

    # API Base URL
    parser.add(
        "--api_base_url",
        env_var="API_BASE_URL",
        help="Base URL of the SKG-IF API, including https:// but without trailing /",
    )

    # API Prefix
    parser.add(
        "--api_prefix",
        env_var="API_PREFIX",
        help="Prefix of the SKG-IF API",
        default="api",
    )

    # JSON-LD context
    parser.add(
        "--skg_if_context",
        help="SKG-IF JSON-LD context",
        default="https://w3id.org/skg-if/context/1.1.0/skg-if.json",
    )
    parser.add(
        "--skg_if_api_context",
        help="SKG-IF API JSON-LD context",
        default="https://w3id.org/skg-if/context/1.0.0/skg-if-api.json",
    )
    parser.add(
        "--skg_if_cessda_context",
        help="SKG-IF CESSDA JSON-LD context",
        default="https://w3id.org/skg-if/sandbox/cessda/",
    )

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

    # Data access mapping
    parser.add(
        "--data_access_mapping_file_url",
        help="URL for Data Access mapping file",
        default="https://raw.githubusercontent.com/cessda/cessda.cdc.osmh-indexer.cmm\
            /main/src/main/resources/data_access_mappings.json",
    )

    # ELSST info for Topics
    parser.add(
        "--elsst_datasource_id",
        help="ELSST data source ID",
        default="urn:cessda:elsst-v5",
    )
    parser.add(
        "--elsst_scheme_name",
        help="ELSST scheme name",
        default="CESSDA ELSST v5",
    )
    parser.add(
        "--elsst_scheme_url",
        help="ELSST scheme URL",
        default="https://thesauri.cessda.eu/elsst-5",
    )
    parser.add(
        "--elsst_download_url",
        help="ELSST JSON-LD download URL",
    )

    return parser.parse_known_args()[0]
