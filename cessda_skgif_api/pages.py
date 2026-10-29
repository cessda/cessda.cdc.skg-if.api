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

from html import escape

from cessda_skgif_api.config_loader import load_config

config = load_config()
if config.api_prefix:
    API_PREFIX = f"/{config.api_prefix}"
else:
    API_PREFIX = ""


def _example(path: str, description: str) -> str:
    """Render one linked API example."""
    url = f"{API_PREFIX}{path}"
    return f"""
        <div class="example">
            <a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">
                {escape(url)}
            </a>
            <p>{description}</p>
        </div>
    """


def render_info_page() -> str:
    """Render the CESSDA SKG-IF API landing page."""
    endpoint_examples = "".join(
        [
            _example("/products", "Returns the first page of research products."),
            _example("/products?page_size=100", "Returns up to 100 research products on one page."),
            _example(
                "/products/7e3c6fee8b0086785724ab698588433727629380e2ee04b7da1d34d94a0a82e4",
                "Returns one product using its CDC identifier.",
            ),
        ]
    )

    product_filters = "".join(
        [
            _example("/products?filter=product_type:research data", "Returns research data products (studies)."),
            _example(
                "/products?filter=product_type:literature",
                "Returns literature products (publications related to studies).",
            ),
            _example(
                "/products?filter=identifiers.id:10.60686/t-fsd3217",
                "Searches for a product by an identifier such as a DOI.",
            ),
            _example("/products?filter=identifiers.scheme:doi", "Returns products that have a DOI identifier."),
            _example(
                "/products?filter=cf.search.title_abstract:health",
                "Searches for a term in product titles and abstracts.",
            ),
            _example(
                "/products?filter=cf.search.title_abstract:health,cf.search.title_abstract:nurse",
                "Searches titles and abstracts using two terms combined with AND.",
            ),
            _example(
                "/products?filter=contributions.by.name:statistics finland", "Filters products by contributor name."
            ),
            _example(
                "/products?filter=contributions.by.name:statistics finland,"
                "cf.search.title:citizen's pulse&page_size=30",
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

    topic_examples = "".join(
        [
            _example("/topics", "Returns the first page of ELSST topics."),
            _example(
                "/topics/https%3A%2F%2Felsst.cessda.eu%2Fid%2F6%2Fdab48525-c485-459b-bb41-730756f1dd65",
                "Returns one ELSST topic using an escaped topic identifier.",
            ),
            _example(
                "/topics/https://elsst.cessda.eu/id/6/dab48525-c485-459b-bb41-730756f1dd65",
                "Returns the same ELSST topic using an unescaped identifier.",
            ),
        ]
    )

    person_examples = "".join(
        [
            _example("/persons", "Returns the first page of persons."),
            _example(
                "/persons/https://orcid.org/0000-0002-1066-6039",
                "Returns one person using an ORCID identifier.",
            ),
        ]
    )

    organisation_examples = "".join(
        [
            _example("/organisations", "Returns the first page of organisations."),
            _example(
                "/organisations/https://ror.org/00bwtjf83",
                "Returns one organisation using a ROR identifier.",
            ),
        ]
    )

    topic_filters = _example(
        "/topics?filter=cf.search.labels:barn,cf.search.language:no",
        "Searches ELSST topic labels for barn and limits the matching label language to Norwegian.",
    )

    person_filters = "".join(
        [
            _example(
                "/persons?filter=identifiers.scheme:orcid",
                "Returns persons who have an ORCID identifier.",
            ),
            _example(
                "/persons?filter=cf.search.name:vuorensyrjä",
                "Searches for a person by name.",
            ),
            _example(
                "/persons?filter=affiliations.affiliation.name:police university college",
                "Searches for persons by affiliation name.",
            ),
        ]
    )

    organisation_filters = "".join(
        [
            _example(
                "/organisations?filter=identifiers.scheme:ror",
                "Returns organisations that have a ROR identifier.",
            ),
            _example(
                "/organisations?filter=name:consortium of european social science data archives",
                "Searches for an organisation by name.",
            ),
        ]
    )

    return f"""<!DOCTYPE html>
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
    <link rel="icon" href="{API_PREFIX}/static/favicon.ico">
    <link
        rel="preload"
        href="{API_PREFIX}/static/Inter-roman.var.woff2?v=3.19"
        as="font"
        type="font/woff2"
        crossorigin
    >
    <link
        rel="stylesheet"
        type="text/css"
        href="{API_PREFIX}/static/cessda.css"
    >
</head>

<body>
<a class="skip-link" href="#main-content">Skip to main content</a>

<header id="site-header">
    <div class="header-inner">
        <a
            id="logo"
            href="https://www.cessda.eu/"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Visit the CESSDA website"
        ></a>

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
                    src="{API_PREFIX}/static/swagger-favicon.png"
                    alt=""
                    aria-hidden="true"
                    width="18"
                    height="18"
                    style="vertical-align:middle; margin-right:6px;"
                >
                <a
                    href="{API_PREFIX}/docs"
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
                <code>{API_PREFIX}/products/</code> to resolve the same research data Product:
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
            <pre><code>{API_PREFIX}/products?page=2&amp;page_size=20</code></pre>
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
        {topic_examples}

        <h3>Persons endpoint</h3>
        <p class="long-text">
            Persons represent individual contributors found in Product metadata. A person can be
            retrieved using an available persistent identifier such as ORCID.
        </p>
        {person_examples}

        <h3>Organisations endpoint</h3>
        <p class="long-text">
            Organisations represent institutions found in Product metadata. An organisation can
            be retrieved using an available persistent identifier such as ROR.
        </p>
        {organisation_examples}

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
        {topic_filters}

        <h3>Person filters</h3>
        {person_filters}

        <h3>Organisation filters</h3>
        {organisation_filters}

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
        <strong>CESSDA SKG-IF API</strong>
    </p>

    <nav class="footer-links" aria-label="Legal and accessibility information">
        <a
            href="https://www.cessda.eu/Privacy-Policy"
            target="_blank"
            rel="noopener noreferrer"
        >
            Privacy Policy
        </a>

        <a
            href="https://www.cessda.eu/Acceptable-Use-Policy"
            target="_blank"
            rel="noopener noreferrer"
        >
            Acceptable Use Policy
        </a>

        <a href="{API_PREFIX}/accessibility">
            Accessibility Statement
        </a>
    </nav>
</footer>
</body>
</html>
"""


def render_accessibility_page() -> str:
    """Render the accessibility statement."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#052438">
    <title>Accessibility Statement - CESSDA SKG-IF API</title>

    <link rel="icon" href="{API_PREFIX}/static/favicon.ico">
    <link
        rel="preload"
        href="{API_PREFIX}/static/Inter-roman.var.woff2?v=3.19"
        as="font"
        type="font/woff2"
        crossorigin
    >
    <link
        rel="stylesheet"
        type="text/css"
        href="{API_PREFIX}/static/cessda.css"
    >
</head>

<body>
<a class="skip-link" href="#main-content">Skip to main content</a>

<header id="site-header">
    <div class="header-inner">
        <a
            id="logo"
            href="https://www.cessda.eu/"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Visit the CESSDA website"
        ></a>
    </div>
</header>

<div id="wrapper">
    <main id="content">
        <div id="main-content" tabindex="-1"></div>

        <nav class="back-nav" aria-label="Breadcrumb">
            <a class="back-link" href="{API_PREFIX}/">
                ← Back to CESSDA SKG-IF API
            </a>
        </nav>

        <h1>Accessibility Statement</h1>

        <p class="long-text">
            CESSDA is committed to ensuring digital accessibility for people with
            disabilities. We aim to provide an accessible experience for everyone
            and to improve the accessibility of the CESSDA SKG-IF API website and
            documentation as the service develops.
        </p>

        <h2>Conformance status</h2>

        <p class="long-text">
            The
            <a
                href="https://www.w3.org/WAI/standards-guidelines/wcag/"
                target="_blank"
                rel="noopener noreferrer"
            >
                Web Content Accessibility Guidelines (WCAG)
            </a>
            define requirements for designers and developers to improve accessibility
            for people with disabilities. They define three levels of conformance: Level A,
            Level AA and Level AAA.
        </p>

        <p class="long-text">
            The CESSDA SKG-IF API landing page and OpenAPI documentation have been
            assessed against WCAG 2.2 Level AA by self-evaluation.
        </p>

        <p class="long-text">
            No accessibility issues were identified on the CESSDA SKG-IF API
            landing page during the assessment. The OpenAPI documentation has
            known accessibility issues related to colour contrast and missing
            form labels, as described below.
        </p>

        <h2>Known accessibility issues</h2>

        <h3>OpenAPI documentation</h3>

        <p class="long-text">
            Some elements in the OpenAPI documentation do not provide sufficient
            colour contrast. Some form controls also do not have accessible labels,
            which can make their purpose unclear to users of assistive technologies.
        </p>

        <h2>Feedback</h2>

        <p class="long-text">
            If you encounter an accessibility problem when using the CESSDA SKG-IF
            API website or its OpenAPI documentation, please contact CESSDA so that
            the issue can be investigated.
        </p>

        <h2>Assessment approach</h2>

        <p class="long-text">
            CESSDA assessed the accessibility of the CESSDA SKG-IF API landing page
            and OpenAPI documentation by self-evaluation.
        </p>

        <h2>About this accessibility statement</h2>

        <p class="long-text">
            This accessibility statement was created on 19 October 2026.
        </p>
    </main>
</div>

<footer id="footer">
    <p>
        <strong>CESSDA SKG-IF API</strong>
    </p>

    <nav class="footer-links" aria-label="Legal and accessibility information">
        <a
            href="https://www.cessda.eu/Privacy-Policy"
            target="_blank"
            rel="noopener noreferrer"
        >
            Privacy Policy
        </a>

        <a
            href="https://www.cessda.eu/Acceptable-Use-Policy"
            target="_blank"
            rel="noopener noreferrer"
        >
            Acceptable Use Policy
        </a>

        <a href="{API_PREFIX}/accessibility">
            Accessibility Statement
        </a>
    </nav>
</footer>
</body>
</html>"""
