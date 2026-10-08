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

"""This module handles FastAPI initialization and all the routes and endpoints."""

from html import escape
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from py12flogging.log_formatter import setup_app_logging
from cessda_skgif_api.cache.product_index import build_product_index
from cessda_skgif_api.db.mongodb import create_client, get_collection_from_app
from cessda_skgif_api.config_loader import load_config
from cessda_skgif_api.db.mongodb import create_client
from cessda_skgif_api.routes.products import router as products_router
from cessda_skgif_api.routes.topics import router as topics_router
from cessda_skgif_api.cache.cessda_topic_vocab import preload_vocabs
from cessda_skgif_api.cache.agent_index import build_agent_index
from cessda_skgif_api.routes.persons import router as persons_router
from cessda_skgif_api.routes.organisations import router as organisations_router
from cessda_skgif_api.utils.errors import (
    ProblemDetailException,
    problem_detail_exception_handler,
)

config = load_config()
api_base_url = config.api_base_url
index_rebuild_time = config.index_rebuild_time
index_rebuild_timezone = config.index_rebuild_timezone
if config.api_prefix:
    api_prefix = f"/{config.api_prefix}"
else:
    api_prefix = ""

setup_app_logging("cessda_skgif_api", loglevel=config.log_level)
_logger = logging.getLogger(__name__)


def seconds_until_target_time(target_hhmm: str, tz_name: str) -> float:
    now = datetime.now(ZoneInfo(tz_name))

    hour, minute = map(int, target_hhmm.split(":"))

    target_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if target_today <= now:
        target_today += timedelta(days=1)

    return (target_today - now).total_seconds()


async def rebuild_indexes_loop(app):
    while True:
        wait_seconds = seconds_until_target_time(
            index_rebuild_time,
            index_rebuild_timezone,
        )

        _logger.info(
            "Index rebuild scheduled in %.2f hours",
            wait_seconds / 3600,
        )

        await asyncio.sleep(wait_seconds)

        try:
            collection = get_collection_from_app(app)

            new_product_index, new_agent_index = await asyncio.gather(
                build_product_index(collection),
                build_agent_index(collection),
            )

            async with app.state.product_index_lock:
                app.state.product_index = new_product_index

            async with app.state.agent_index_lock:
                app.state.agent_index = new_agent_index

        except Exception:
            _logger.exception("Index rebuild failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await preload_vocabs(["en", "de", "fr", "fi", "sl"])
    # Startup: create one AsyncMongoClient and store it
    app.state.mongo_client = await create_client()

    app.state.product_index_lock = asyncio.Lock()
    app.state.agent_index_lock = asyncio.Lock()

    app.state.product_index = None
    app.state.agent_index = None

    collection = get_collection_from_app(app)

    product_index, agent_index = await asyncio.gather(
        build_product_index(collection),
        build_agent_index(collection),
    )

    async with app.state.product_index_lock:
        app.state.product_index = product_index

    async with app.state.agent_index_lock:
        app.state.agent_index = agent_index

    # Start background rebuild loop
    app.state.index_rebuild_task = asyncio.create_task(
        rebuild_indexes_loop(app)
    )

    try:
        yield
    finally:
        app.state.index_rebuild_task.cancel()

        try:
            await app.state.index_rebuild_task
        except asyncio.CancelledError:
            pass

        # Shutdown: close client cleanly
        await app.state.mongo_client.close()


app = FastAPI(
    lifespan=lifespan,
    title="CESSDA Data Catalogue and ELSST SKG-IF API",
    servers=[
        {"url": f"{api_base_url}{api_prefix}", "description": "CESSDA SKG-IF API"},
    ],
    root_path=api_prefix,
    root_path_in_servers=False,
    openapi_url="/openapi_skg-if_cessda_dynamic.yaml",
    docs_url=None,
    redoc_url=None,
)

app.add_exception_handler(
    ProblemDetailException,
    problem_detail_exception_handler,
)

app.mount("/static", StaticFiles(directory="static"), name="static")


def _example(path: str, description: str) -> str:
    """Render one linked API example."""
    url = f"{api_prefix}{path}"
    return f"""
        <div class="example">
            <a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">
                {escape(url)}
            </a>
            <p>{description}</p>
        </div>
    """


@app.get("", include_in_schema=False)
@app.get("/", include_in_schema=False)
async def info():
    """Returns introductory information, documentation and usage examples."""

    endpoint_examples = "".join(
        [
            _example(
                "/products",
                "Returns the first page of research products.",
            ),
            _example(
                "/products?page_size=100",
                "Returns up to 100 research products on one page.",
            ),
            _example(
                "/products/7e3c6fee8b0086785724ab698588433727629380e2ee04b7da1d34d94a0a82e4",
                "Returns one product using its CDC identifier.",
            ),
        ]
    )

    product_filters = "".join(
        [
            _example(
                "/products?filter=product_type:research%20data",
                "Returns research data products, such as studies.",
            ),
            _example(
                "/products?filter=product_type:literature",
                "Returns literature related to research data.",
            ),
            _example(
                "/products?filter=identifiers.id:10.60686/t-fsd3217",
                "Searches for a product by an identifier such as a DOI.",
            ),
            _example(
                "/products?filter=identifiers.scheme:doi",
                "Returns products that have a DOI identifier.",
            ),
            _example(
                "/products?filter=cf.search.title_abstract:health",
                "Searches for a term in product titles and abstracts.",
            ),
            _example(
                "/products?filter=cf.search.title_abstract:health,cf.search.title_abstract:nurse",
                "Searches titles and abstracts using two terms combined with AND.",
            ),
            _example(
                "/products?filter=contributions.by.name:statistics%20finland",
                "Filters products by contributor name.",
            ),
            _example(
                "/products?filter=contributions.by.name:statistics%20finland,cf.search.title:citizen%27s%20pulse&page_size=30",
                "Combines contributor and title filters and requests 30 products per page.",
            ),
            _example(
                "/products?filter=contributions.by.identifiers.scheme:orcid",
                "Returns products where at least one contributor has an ORCID identifier.",
            ),
            _example(
                "/products?filter=contributions.by.identifiers.scheme:ror",
                "Returns products where a contributor or a contributor's organisation has a ROR identifier.",
            ),
            _example(
                "/products?filter=cf.cites:8c0aabd6ffa9b2b62012ddfdc661d8f61587021cbed074dd6fb9006566c9135a",
                "Returns related publications that cite the identified research data product.",
            ),
            _example(
                "/products?filter=cf.cited_by:https://urn.fi/URN:NBN:fi:tuni-202304204030",
                "Returns research data products cited by the identified publication.",
            ),
        ]
    )

    return HTMLResponse(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#052438">
    <meta
        name="description"
        content="CESSDA SKG-IF API documentation, endpoints, filters and usage examples."
    >
    <title>CESSDA SKG-IF API</title>
    <link rel="icon" href="{api_prefix}/static/favicon.ico">
    <link
        rel="preload"
        href="{api_prefix}/static/Inter-roman.var.woff2?v=3.19"
        as="font"
        type="font/woff2"
        crossorigin
    >
    <link
        rel="preload"
        href="{api_prefix}/static/Inter-italic.var.woff2?v=3.19"
        as="font"
        type="font/woff2"
        crossorigin
    >
    <link
        rel="stylesheet"
        type="text/css"
        href="{api_prefix}/static/cessda.css"
    >
</head>

<body>
<a class="skip-link" href="#main-content">Skip to main content</a>

<header id="site-header">
    <div class="header-inner">
        <div id="logo" role="img" aria-label="CESSDA"></div>

        <nav id="menu" aria-label="Page navigation">
            <a href="#intro">Introduction</a>
            <a href="#about-skg-if">About SKG-IF</a>
            <a href="#implementation">Implementation</a>
            <a href="#documentation">Documentation</a>
            <a href="#identifiers">Identifiers</a>
            <a href="#endpoints">Endpoints</a>
            <a href="#filters">Filters</a>
            <a href="#meta">Search metadata</a>
        </nav>
    </div>
</header>

<div id="wrapper">
    <main id="content">
        <div id="main-content" tabindex="-1"></div>

        <h1 id="intro">CESSDA SKG-IF API</h1>

        <p class="lead">
            A public API for accessing research information from the
            CESSDA Data Catalogue in an interoperable SKG-IF format.
        </p>

        <p class="long-text">
            The CESSDA SKG-IF API provides structured research information using the
            Scientific Knowledge Graph Interoperability Framework (SKG-IF). Products,
            persons and organisations are derived from metadata held in the
            CESSDA Data Catalogue (CDC). The Topics endpoint exposes concepts from the
            European Language Social Science Thesaurus (ELSST) as SKG-IF Topic entities.
        </p>

        <p class="long-text">
            The API is primarily intended for machine-to-machine use, allowing research
            infrastructures and other services to exchange and reuse information through
            a common data model and REST-based interface. People can also explore the API
            directly using the links and examples on this page.
        </p>

        <h2 id="about-skg-if">About SKG-IF</h2>

        <p class="long-text">
            SKG-IF is a shared interoperability framework for exchanging information between
            scientific knowledge graphs and research information systems. It was originally
            developed by the Research Data Alliance SKG-IF Working Group and has subsequently
            been developed further in the OSTrails project, including an OpenAPI specification
            describing the available entities and operations.
        </p>

        <p class="long-text">
            SKG-IF provides both a common data model and a practical API specification. It
            describes six principal entity types and the relationships between them:
        </p>

        <ul class="entity-list">
            <li>
                <strong>Research Product</strong>
                <span>Literature, research data, software or another type of research output.</span>
            </li>
            <li>
                <strong>Agent</strong>
                <span>A person, organisation or generic agent associated with another entity, such as a contributor to a research product.</span>
            </li>
            <li>
                <strong>Grant</strong>
                <span>Funding associated with a project or research product.</span>
            </li>
            <li>
                <strong>Venue</strong>
                <span>A publication or dissemination venue for a research product.</span>
            </li>
            <li>
                <strong>Topic</strong>
                <span>A concept or controlled vocabulary term used to describe a research product.</span>
            </li>
            <li>
                <strong>Data Source</strong>
                <span>The source or storage location from which research information is provided.</span>
            </li>
        </ul>

        <p class="long-text">
            Research products form the central part of the model. Other entities are connected
            to research products and to each other through references. The API representation
            may also embed selected information directly in a record. For example, a contribution
            can contain information about the contributing person or organisation, and a topic
            can contain multilingual labels resolved from a controlled vocabulary.
        </p>

        <div class="info-box">
            <p><strong>Further information about SKG-IF</strong></p>
            <p>
                See the
                <a
                    href="https://skg-if.github.io/interoperability-framework/"
                    target="_blank"
                    rel="noopener noreferrer"
                >SKG-IF Interoperability Framework documentation</a>
                and the
                <a
                    href="https://skg-if.github.io/api/"
                    target="_blank"
                    rel="noopener noreferrer"
                >SKG-IF API specification documentation</a>.
            </p>
        </div>

        <h2 id="implementation">CESSDA data sources and implementation</h2>

        <p class="long-text">
            The implementation currently exposes products, topics, persons and organisations.
            Products comprise research data in the <a
                href="https://datacatalogue.cessda.eu/"
                target="_blank"
                rel="noopener noreferrer"
            >CDC</a> and publications related to those datasets. Persons and organisations are
            derived from the metadata of the research data and related publications. The standalone
            Topics endpoint exposes <a
                href="https://elsst.cessda.eu/"
                target="_blank"
                rel="noopener noreferrer"
            >ELSST</a> concepts.
        </p>

        <h3>Multilingual topic information in Product records</h3>

        <p class="long-text">
            Product records may contain topic information enriched using the CESSDA Vocabulary
            Service (CVS). When a controlled vocabulary concept contains labels in multiple
            languages, the labels are grouped under the same topic concept and exposed as
            language-specific labels within one embedded SKG-IF Topic entity.
        </p>

        <p class="long-text">
            For example, one concept may include the Finnish label
            <em>“Kansainvälinen politiikka ja järjestöt”</em> and the English label
            <em>“International politics and organisations”</em>. Clients can therefore display
            the same concept in different languages while retaining a shared concept identifier.
        </p>

        <p class="long-text">
            This CVS-based enrichment applies to topic information embedded in Product records.
            It is distinct from the standalone Topics endpoint, which exposes ELSST concepts.
        </p>

        <ul class="resource-list">
            <li>
                <strong>CESSDA Vocabulary Service (CVS)</strong>, accessed through the
                <a
                    href="https://vocabularies.cessda.eu/documentation/rest-api.html"
                    target="_blank"
                    rel="noopener noreferrer"
                >CESSDA Vocabulary Service API</a>
            </li>
        </ul>

        <h2 id="documentation">Documentation</h2>

        <p class="long-text">
            The API is documented using OpenAPI. The documentation is based on the official
            SKG-IF OpenAPI specification and has been modified only to reflect the implementation
            status of the CESSDA endpoints.
        </p>

        <p class="long-text">
            Endpoints that are not available are labelled
            <strong>“Not yet implemented”</strong> next to the endpoint name. Filters that are not
            applicable or not implemented are shown with a strikethrough.
        </p>

        <section class="documentation-card" aria-labelledby="openapi-heading">
            <h3 id="openapi-heading">OpenAPI documentation</h3>
            <p>
                Browse the SKG-IF OpenAPI documentation annotated with the implementation
                status of the CESSDA SKG-IF API.
            </p>
            <p>
                <img
                    src="{api_prefix}/static/swagger-favicon.png"
                    alt=""
                    aria-hidden="true"
                    width="18"
                    height="18"
                    style="vertical-align:middle; margin-right:6px;"
                >
                <a
                    href="{api_prefix}/docs"
                    target="_blank"
                    rel="noopener noreferrer"
                >OpenAPI documentation</a>
            </p>
        </section>

        <h3>Source code</h3>

        <p class="long-text">
            The source code for the CESSDA SKG-IF API is publicly available under the
            Apache License 2.0.
        </p>

        <ul class="resource-list">
            <li>
                <strong>CESSDA SKG-IF API</strong>, available from
                <a
                    href="https://github.com/cessda/cessda.cdc.skg-if.api"
                    target="_blank"
                    rel="noopener noreferrer"
                >the CESSDA SKG-IF API GitHub repository</a>
            </li>
        </ul>

        <h3>Metadata mappings</h3>

        <p class="long-text">
            The following mappings describe how source metadata and controlled vocabularies
            are represented in the CESSDA SKG-IF API.
        </p>

        <ul class="resource-list">
            <li>
                <a
                    href="https://docs.google.com/spreadsheets/d/e/2PACX-1vS5AONSTJeJt5BbkZ-1ec9CWosZNQBpmKG3-HJM4J0rJdTlWKswaOOhhmEP5nkqHnu-3iEo0hecwSl2/pubhtml"
                    target="_blank"
                    rel="noopener noreferrer"
                >CDC DDI 2.5 to CESSDA SKG-IF API mapping</a>
            </li>
            <li>
                <a
                    href="https://docs.google.com/spreadsheets/d/e/2PACX-1vRnhlctTeDBOPICBFDMMrrRwMJz3fdIQwh1PLMWIIDc9Yrf6vYUr3M8HKpCvmE88NPP1Xatr4CrDB0l/pubhtml"
                    target="_blank"
                    rel="noopener noreferrer"
                >ELSST to CESSDA SKG-IF Topic API mapping</a>
            </li>
            <li>
                <a
                    href="https://docs.google.com/spreadsheets/d/e/2PACX-1vRnvTUKe05YbimuX4My4OPMbGXeX-1iT3EmdAugClumVCuQzdJXuK4Mx8ZaMrZFqHAF_tW2nyckV8Fp/pubhtml"
                    target="_blank"
                    rel="noopener noreferrer"
                >CESSDA Vocabulary Service to CESSDA SKG-IF Topic API mapping</a>
            </li>
        </ul>

        <h2 id="identifiers">Identifiers and entity resolution</h2>

        <p class="long-text">
            In SKG-IF, <code>local_identifier</code> acts as the identifier of an entity. The
            CESSDA implementation uses resolvable <code>w3id.org</code> identifiers where possible
            and accepts several equivalent identifier forms when retrieving individual entities.
        </p>

        <p class="long-text">
            For a research data Product, the canonical SKG-IF <code>local_identifier</code> is a
            CESSDA <code>w3id.org</code> URL. Opening that URL redirects to the corresponding
            human-readable record in the CDC. The Products endpoint can resolve the same entity
            from the SKG-IF local identifier, the full CDC URL, or the underlying CDC
            identifier.
        </p>

        <div class="info-box">
            <p><strong>Equivalent research data Product identifier forms</strong></p>
            <p>
                Each of the following forms can be appended to
                <code>{api_prefix}/products/</code> to resolve the same research data Product:
            </p>
            <pre><code>d9933f903b3b7d0c04fb5f720bc2fc513a17cf432a91d62499629bbea4507ab1

cessda_product_research_data_d9933f903b3b7d0c04fb5f720bc2fc513a17cf432a91d62499629bbea4507ab1

https://w3id.org/cessda/cessda_product_research_data_d9933f903b3b7d0c04fb5f720bc2fc513a17cf432a91d62499629bbea4507ab1

https://datacatalogue.cessda.eu/detail/d9933f903b3b7d0c04fb5f720bc2fc513a17cf432a91d62499629bbea4507ab1</code></pre>
        </div>

        <p class="long-text">
            Literature Products, Persons and Organisations follow the same general resolution principle.
            Persistent identifiers are preferred when they are available in the source metadata because
            they can identify the same entity across systems. The API therefore prioritises ORCID for
            persons and ROR for organisations. These full PID URLs can also be supplied to the
            corresponding single-entity endpoint.
        </p>

        <p class="long-text">
            When no suitable external persistent identifier is available, the API uses a generated
            local identifier. CESSDA <code>w3id.org</code> identifiers for persons and organisations
            resolve back to the corresponding single-entity endpoint in the CESSDA SKG-IF API.
        </p>

        <h2 id="endpoints">Endpoints</h2>

        <p class="long-text">
            The API currently exposes endpoints for research products, topics, persons and
            organisations. Collection endpoints return paginated result sets, while entity
            endpoints return an individual record identified by its local or persistent identifier.
        </p>

        <div class="info-box">
            <p><strong>Pagination</strong></p>
            <p>
                Collection endpoints return 10 items per page by default. Use
                <code>?page=N</code> and <code>?page_size=M</code> to request another page or
                change the number of returned items.
            </p>
            <pre><code>{api_prefix}/products?page=2&amp;page_size=20</code></pre>
        </div>

        <h3>Products endpoint</h3>
        <p class="long-text">
            Products include research data from the CDC and literature related to those datasets.
        </p>
        {endpoint_examples}

        <h3>Topics endpoint</h3>
        <p class="long-text">
            The Topics endpoint exposes concepts from ELSST as SKG-IF Topic entities. Topic
            identifiers can be supplied as escaped or unescaped URLs.
        </p>
        {_example('/topics', 'Returns the first page of ELSST topics.')}
        {_example('/topics/https%3A%2F%2Felsst.cessda.eu%2Fid%2F6%2Fdab48525-c485-459b-bb41-730756f1dd65', 'Returns one ELSST topic using an escaped topic identifier.')}
        {_example('/topics/https://elsst.cessda.eu/id/6/dab48525-c485-459b-bb41-730756f1dd65', 'Returns the same ELSST topic using an unescaped identifier.')}

        <h3>Persons endpoint</h3>
        <p class="long-text">
            Persons represent individual contributors found in Product metadata. A person can be
            retrieved using an available persistent identifier such as ORCID.
        </p>
        {_example('/persons', 'Returns the first page of persons.')}
        {_example('/persons/https://orcid.org/0000-0002-1066-6039', 'Returns one person using an ORCID identifier.')}

        <h3>Organisations endpoint</h3>
        <p class="long-text">
            Organisations represent institutions found in Product metadata. An organisation can
            be retrieved using an available persistent identifier such as ROR.
        </p>
        {_example('/organisations', 'Returns the first page of organisations.')}
        {_example('/organisations/https://ror.org/00bwtjf83', 'Returns one organisation using a ROR identifier.')}

        <h2 id="filters">Filters</h2>

        <p class="long-text">
            Collection endpoints support filters for narrowing result sets. Filters are supplied
            through the <code>filter</code> query parameter as <code>field:value</code> pairs.
        </p>

        <div class="info-box">
            <p><strong>Filtering syntax</strong></p>
            <pre><code>?filter=field:value,otherfield:othervalue</code></pre>
            <p>
                Separate multiple filters with a comma. Multiple filters are combined using AND,
                which means that all specified conditions must match.
            </p>
            <p>
                If a filter value contains a comma, encode it as <code>%2C</code>. Spaces may be
                written normally, although clients can also encode them as <code>%20</code>.
            </p>
        </div>

        <p class="long-text">
            The examples below demonstrate commonly used filters. Consult the OpenAPI documentation
            for the complete set of filters supported by each endpoint.
        </p>

        <h3>Product filters</h3>
        {product_filters}

        <h3>Topic filters</h3>
        {_example('/topics?filter=cf.search.labels:barn,cf.search.language:no', 'Searches ELSST topic labels for barn and limits the matching label language to Norwegian.')}

        <h3>Person filters</h3>
        {_example('/persons?filter=identifiers.scheme:orcid', 'Returns persons who have an ORCID identifier.')}
        {_example('/persons?filter=cf.search.name:vuorensyrj%C3%A4', 'Searches for a person by name.')}
        {_example('/persons?filter=affiliations.affiliation.name:police%20university%20college', 'Searches for persons by affiliation name.')}

        <h3>Organisation filters</h3>
        {_example('/organisations?filter=identifiers.scheme:ror', 'Returns organisations that have a ROR identifier.')}
        {_example('/organisations?filter=name:consortium%20of%20european%20social%20science%20data%20archives', 'Searches for an organisation by name.')}

        <h2 id="meta">Search metadata in the response</h2>

        <p class="long-text">
            Collection responses include a <code>meta</code> section describing the current page
            and the complete result set.
        </p>

        <pre class="response-example"><code>{{
  "meta": {{
    "local_identifier": "...?page=2&amp;page_size=20",
    "entity_type": "search_result_page",
    "previous_page": {{
      "local_identifier": "...?page=1&amp;page_size=20",
      "entity_type": "search_result_page"
    }},
    "next_page": {{
      "local_identifier": "...?page=3&amp;page_size=20",
      "entity_type": "search_result_page"
    }},
    "part_of": {{
      "local_identifier": "...",
      "entity_type": "search_result",
      "total_items": 2165,
      "first_page": {{
        "local_identifier": "...?page=1&amp;page_size=20",
        "entity_type": "search_result_page"
      }},
      "last_page": {{
        "local_identifier": "...?page=109&amp;page_size=20",
        "entity_type": "search_result_page"
      }}
    }}
  }}
}}</code></pre>

        <p class="long-text">
            The <code>meta</code> section identifies the current result page and provides links to
            the previous and next pages when applicable. The <code>part_of</code> object describes
            the complete result set, including the total number of matching entities and links to
            its first and last pages.
        </p>
    </main>
</div>

<footer id="footer">
    <p>
        <strong>CESSDA SKG-IF API</strong><br>
        Interoperable access to research information from the CESSDA Data Catalogue.
    </p>
</footer>
</body>
</html>
"""
    )


@app.get("/docs-dynamic", include_in_schema=False)
async def custom_swagger_ui_html():
    """Returns Swagger UI for dynamically created OpenAPI documentation"""
    return get_swagger_ui_html(
        openapi_url=f"{api_prefix}/openapi_skg-if_cessda_dynamic.yaml",
        title=app.title + " - Swagger UI",
        swagger_js_url=f"{api_prefix}/static/swagger-ui-bundle.js",
        swagger_css_url=f"{api_prefix}/static/swagger-ui.css",
        swagger_favicon_url=f"{api_prefix}/static/swagger-favicon.png",
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    """Returns ReDoc UI for dynamically created OpenAPI documentation"""
    return get_redoc_html(
        openapi_url=f"{api_prefix}/openapi_skg-if_cessda_dynamic.yaml",
        title=app.title + " - ReDoc",
        redoc_js_url=f"{api_prefix}/static/redoc.standalone.js",
    )


@app.get("/docs", include_in_schema=False)
async def swagger_static():
    """Returns Swagger UI for static OpenAPI documentation"""
    return HTMLResponse(f"""
<html>
  <head>
    <link type="text/css" rel="stylesheet" href="{api_prefix}/static/swagger-ui.css">
    <link rel="shortcut icon" href="{api_prefix}/static/swagger-favicon.png">
    <title>CESSDA SKG-IF API - Swagger UI</title>
  </head>
  <body>
  <div id="swagger-ui"></div>
  <script src="{api_prefix}/static/swagger-ui-bundle.js"></script>
  <script>
  const API_PREFIX = "{api_prefix}";
  const ORIGIN = window.location.origin;
  const ui = SwaggerUIBundle({{
      url: "{api_prefix}/static/openapi_skg-if_cessda.yaml",
      "dom_id": "#swagger-ui",
      "layout": "BaseLayout",
      "deepLinking": true,
      "showExtensions": true,
      "showCommonExtensions": true,
      presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIBundle.SwaggerUIStandalonePreset
      ],
      requestInterceptor: (req) => {{
        // Never touch the OpenAPI spec request
        if (req.loadSpec) {{
          return req;
        }}
        // Case 1: relative paths (/products)
        if (req.url.startsWith("/")) {{
          req.url = API_PREFIX + req.url;
          return req;
        }}
        // Case 2: absolute same-origin URLs (https://host/products)
        if (req.url.startsWith(ORIGIN + "/")) {{
          req.url = ORIGIN + API_PREFIX + req.url.slice(ORIGIN.length);
          return req;
        }}
        return req;
      }}
  }})
  </script>
  </body>
</html>
    """)


# Register endpoints
app.include_router(products_router, prefix="/products", tags=["products"])
app.include_router(persons_router, prefix="/persons", tags=["persons"])
app.include_router(organisations_router, prefix="/organisations", tags=["organisations"])
app.include_router(topics_router, prefix="/topics", tags=["topics"])
