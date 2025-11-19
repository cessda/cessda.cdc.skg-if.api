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

"""This module handles FastAPI initialization and all the routes and endpoints."""

from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse
from cessda_skgif_api.config_loader import load_config
from cessda_skgif_api.routes.products import router as products_router


config = load_config()
api_base_url = config.api_base_url
api_prefix = config.api_prefix

app = FastAPI(
    title="CESSDA Data Catalogue SKG-IF API",
    servers=[
        {"url": api_base_url, "description": "CESSDA SKG-IF API"},
    ],
    root_path=api_prefix,
    root_path_in_servers=False,
    openapi_url="/openapi_skg-if_cessda_dynamic.yaml",
    docs_url=None,
    redoc_url=None,
)


@app.get("/", include_in_schema=False)
async def info():
    """Returns helpful links at the root of the API"""
    return HTMLResponse(
        f"""
<html>
  <head>
    <title>CESSDA SKG-IF API Info</title>
    <style>
      body {{
        font-family: Arial, sans-serif;
        margin: 40px;
        background-color: #f9f9f9;
        color: #333;
      }}
      h1, h2, h3 {{
        color: #005a9c;
      }}
      a {{
        color: #007acc;
        text-decoration: none;
      }}
      a:hover {{
        text-decoration: underline;
      }}
      p {{
        margin: 8px 0;
      }}
    </style>
</head>
  <body>
    <h1>CESSDA Data Catalogue SKG-IF API</h1>
    <h2>Documentation</h2>
    <p><a href="/{api_prefix}/docs-static">Static complete OpenAPI docs</a></p>
    <p><a href="/{api_prefix}/docs">Dynamically created OpenAPI docs</a></p>
    <h2>Endpoints</h2>
    <p><a href="/{api_prefix}/products">Products</a></p>
    <p><a href="/{api_prefix}/products?page_size=100">Products with 100 page size (10 by default)</a></p>
    <p><a href="/{api_prefix}/products/7e3c6fee8b0086785724ab698588433727629380e2ee04b7da1d34d94a0a82e4">
      Single Product by CDC id (7e3c6fee8b0086785724ab698588433727629380e2ee04b7da1d34d94a0a82e4 in this example)
    </a></p>
    <h3>Filtered products</h3>
    <p><a href="/{api_prefix}/products?filter=identifiers.id:10.60686/t-fsd3217">
      Study by identifier such as DOI (10.60686/t-fsd3217 in this example)
    </a></p>
    <p><a href="/{api_prefix}/products?filter=identifiers.scheme:doi">Studies with DOI</a></p>
    <p><a href="/{api_prefix}/products?filter=cf.search.title_abstract:health">
      Search from title and abstracts (health in this example)
    </a></p>
    <p><a href="/{api_prefix}/products?filter=cf.search.title_abstract:health,cf.search.title_abstract:nurse">
      Search from title and abstracts with two terms (health and nurse in this example)
    </a></p>
    <p><a href="/{api_prefix}/products?filter=contributions.by.name:statistics finland">
      By author name (Statistics Finland in this example)
    </a></p>
    <p><a href="/{api_prefix}/products?filter=contributions.by.name:statistics finland,cf.search.title:citizen's pulse&page_size=20">
      By author name and study title with page size 20 (Statistics Finland and Citizen's Pulse in this example)
    </a></p>
    <p><a href="/{api_prefix}/products?filter=contributions.by.identifiers.scheme:orcid">At least one author has ORCID</a></p>
    <p><a href="/{api_prefix}/products?filter=contributions.by.identifiers.scheme:ror">
      At least one author or author's organization has ROR
    </a></p>
  </body>
</html>
    """
    )


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Returns Swagger UI for dynamically created OpenAPI documentation"""
    return get_swagger_ui_html(
        openapi_url=f"/{api_prefix}/openapi_skg-if_cessda_dynamic.yaml",
        title=app.title + " - Swagger UI",
        swagger_js_url=f"/{api_prefix}/static/swagger-ui-bundle.js",
        swagger_css_url=f"/{api_prefix}/static/swagger-ui.css",
        swagger_favicon_url=f"/{api_prefix}/static/swagger-favicon.png",
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    """Returns ReDoc UI for dynamically created OpenAPI documentation"""
    return get_redoc_html(
        openapi_url=f"/{api_prefix}/openapi_skg-if_cessda_dynamic.yaml",
        title=app.title + " - ReDoc",
        redoc_js_url=f"/{api_prefix}/static/redoc.standalone.js",
    )


@app.get("/docs-static", include_in_schema=False)
async def swagger_static():
    """Returns Swagger UI for static OpenAPI documentation"""
    return HTMLResponse(
        f"""
<html>
  <head>
    <link type="text/css" rel="stylesheet" href="/{api_prefix}/static/swagger-ui.css">
    <link rel="shortcut icon" href="/{api_prefix}/static/swagger-favicon">
    <title>CESSDA SKG-IF API - Swagger UI</title>
  </head>
  <body>
  <div id="swagger-ui"></div>
  <script src="/{api_prefix}/static/swagger-ui-bundle.js"></script>
  <script>
  const ui = SwaggerUIBundle({{
      url: "/{api_prefix}/static/openapi_skg-if_cessda.yaml",
      "dom_id": "#swagger-ui",
      "layout": "BaseLayout",
      "deepLinking": true,
      "showExtensions": true,
      "showCommonExtensions": true,
      presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIBundle.SwaggerUIStandalonePreset
      ],
  }})
  </script>
  </body>
</html>
    """
    )


# Register endpoints
app.include_router(products_router, prefix="/products", tags=["products"])
