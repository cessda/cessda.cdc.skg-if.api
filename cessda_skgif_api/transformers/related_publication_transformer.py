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

"""
Transforms related publications stored in Product index,
which is built from metadata stored in MongoDB, into SKG-IF Products
"""

from typing import Dict, Any, List, Optional
from cessda_skgif_api.config_loader import load_config
from cessda_skgif_api.models.skgif import (
    Product,
    Identifier,
    Manifestation,
)
from cessda_skgif_api.utils.identifier_utils import generate_related_publication_local_identifier

config = load_config()
skg_if_cessda_context = config.skg_if_cessda_context


def extract_related_publication_titles(
    related_publication_group: List[Dict[str, Any]],
) -> Optional[Dict[str, List[str]]]:
    titles: Dict[str, List[str]] = {}
    seen = set()

    for pub in related_publication_group:
        lang = pub.get("language", "en")
        value = pub.get("related_publication") or pub.get("description")
        if not value:
            continue

        key = (lang, value)
        if key in seen:
            continue
        seen.add(key)

        titles.setdefault(lang, []).append(value)

    return titles or None


def extract_related_publication_identifiers(
    related_publication_group: List[Dict[str, Any]],
) -> Optional[List[Identifier]]:
    identifiers: List[Identifier] = []
    seen = set()

    for pub in related_publication_group:
        scheme = (pub.get("identifier_agency") or "").strip().lower()
        value = (pub.get("identifier") or "").strip()

        if not scheme or not value:
            continue

        key = (scheme, value)
        if key in seen:
            continue
        seen.add(key)

        identifiers.append(Identifier(value=value, scheme=scheme))

    return identifiers or None


def extract_related_publication_dates(
    related_publication_group: List[Dict[str, Any]],
) -> Optional[Dict[str, List[str]]]:
    publication_dates = []
    seen = set()

    for pub in related_publication_group:
        value = (pub.get("distribution_date") or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        publication_dates.append(value)

    return {"publication": publication_dates} if publication_dates else None


def transform_related_publication_to_skgif_product(
    related_publication_group: List[Dict[str, Any]],
    cited_studies: List[str],
) -> Product:
    identifiers = extract_related_publication_identifiers(related_publication_group)

    titles = extract_related_publication_titles(related_publication_group)

    dates = extract_related_publication_dates(related_publication_group)

    manifestations = [Manifestation(dates=dates)] if dates else None

    return Product(
        local_identifier=generate_related_publication_local_identifier(related_publication_group),
        product_type="literature",
        identifiers=identifiers,
        titles=titles,
        manifestations=manifestations,
        related_products={
            "cites": cited_studies,
        },
    )
