# Copyright CESSDA ERIC 2026
# Copyright Finnish Social Science Data Archive FSD / University of Tampere 2026

# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from typing import Any, Dict, List
from pathlib import Path
import httpx
from cessda_skgif_api.cache.cache import AsyncTTLCache
from cessda_skgif_api.config_loader import load_config

config = load_config()
cessda_topic_vocab_api_url = config.cessda_topic_vocab_api_url
cessda_topic_vocab_api_version = config.cessda_topic_vocab_api_version
cessda_topic_vocab_cache_filename = config.cessda_topic_vocab_cache_filename
cessda_topic_vocab_cache_dir = os.path.dirname(os.path.abspath(__file__))
cessda_topic_vocab_CACHE_FILE_PATH = Path(cessda_topic_vocab_cache_dir, cessda_topic_vocab_cache_filename)
cessda_topic_vocab_TTL_SECONDS = 604800  # 1 week

# One cache instance for all languages
cessda_topic_vocab_cache = AsyncTTLCache(
    cache_file=cessda_topic_vocab_CACHE_FILE_PATH, ttl_seconds=cessda_topic_vocab_TTL_SECONDS, group_fn=lambda lang: lang
)


async def _fetch_cessda_topic_vocab(language: str) -> Dict[str, Dict[str, Any]]:
    url = f"{cessda_topic_vocab_api_url}/{cessda_topic_vocab_api_version}/{language}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    vocab = {}
    for item in data:
        uri = item.get("uri", "")
        # Only replace if the placeholder is present AND item has an id
        if "[CODE]" in uri and "id" in item:
            uri = uri.replace("[CODE]", str(item["id"]))

        vocab[item["notation"]] = {
            "title": item.get("title"),
            "uri": uri,
        }

    return vocab


# Async load/ensure
async def load_cessda_topic_vocab(language: str) -> Dict[str, Dict[str, Any]]:
    return await cessda_topic_vocab_cache.get(language, _fetch_cessda_topic_vocab)


# Startup preload
async def preload_vocabs(languages: List[str]) -> None:
    await cessda_topic_vocab_cache.preload(languages, _fetch_cessda_topic_vocab)


# Sync accessor for transformer
def get_cached_vocab(language: str) -> Dict[str, Dict[str, Any]]:
    vocab = cessda_topic_vocab_cache.get_in_memory(language)
    return vocab if isinstance(vocab, dict) else {}
