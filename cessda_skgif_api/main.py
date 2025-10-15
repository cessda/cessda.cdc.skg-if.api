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

import os
import yaml
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from cessda_skgif_api.routes.products import router as products_router


app = FastAPI(
    title="CESSDA Data Catalogue SKG-IF API",
    openapi_url="/openapi_skg-if_cessda_dynamic.yaml",
    root_path="/api"
)


@app.get("/", include_in_schema=False)
async def info():
    return HTMLResponse(
        """
    <html>
      <head>
        <title>CESSDA SKG-IF API Info</title>
        <style>
          body {
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #f9f9f9;
            color: #333;
          }
          h1, h2, h3 {
            color: #005a9c;
          }
          a {
            color: #007acc;
            text-decoration: none;
          }
          a:hover {
            text-decoration: underline;
          }
          p {
            margin: 8px 0;
          }
        </style>
    </head>
      <body>
        <h1>CESSDA Data Catalogue SKG-IF API</h1>
        <h2>Documentation</h2>
        <p><a href="api/docs-static">Static complete OpenAPI docs</a></p>
        <p><a href="api/docs">Dynamically created OpenAPI docs</a></p>
        <h2>Endpoints</h2>
        <p><a href="api/products">Products</a></p>
        <p><a href="api/products?page_size=100">Products with 100 page size (10 by default)</a></p>
        <h3>Filtered products</h3>
        <p><a href="api/products?filter=identifiers.id:10.60686/t-fsd3217">Study by identifier (10.60686/t-fsd3217 (DOI) in this example)</a></p>
        <p><a href="api/products?filter=identifiers.scheme:doi">Studies with DOI</a></p>
        <p><a href="api/products?filter=cf.search.title_abstract:health">Search from title and abstracts (health in this example)</a></p>
        <p><a href="api/products?filter=cf.search.title_abstract:health,cf.search.title_abstract:nurse">Search from title and abstracts with two terms (health and nurse in this example)</a></p>
        <p><a href="api/products?filter=contributions.by.name:statistics finland">By author name (Statistics Finland in this example)</a></p>
        <p><a href="api/products?filter=contributions.by.name:statistics finland,cf.search.title:citizen's pulse&page_size=20">By author name and study title with page size 20 (Statistics Finland and Citizen's Pulse in this example)</a></p>
        <p><a href="api/products?filter=contributions.by.identifiers.scheme:orcid">At least one author has ORCID</a></p>
        <p><a href="api/products?filter=contributions.by.identifiers.scheme:ror">At least one author or author's organization has ROR</a></p>
      </body>
    </html>
    """
    )


@app.get("/openapi-static", include_in_schema=False)
async def openapi_static():
    yaml_path = os.path.join(os.path.dirname(__file__), "static", "openapi_skg-if_cessda.yaml")
    with open(yaml_path, "r") as f:
        spec = yaml.safe_load(f)
    return JSONResponse(content=spec)


@app.get("/docs-static", include_in_schema=False)
async def swagger_static():
    return HTMLResponse(
        """
    <html><head><link type="text/css" rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"><link rel="shortcut icon" href="https://fastapi.tiangolo.com/img/favicon.png"><title>CESSDA SKG-IF API - Swagger UI</title></head><body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <!-- `SwaggerUIBundle` is now available on the page -->
    <script>
    const ui = SwaggerUIBundle({
        url: "api/openapi-static",
        "dom_id": "#swagger-ui",
        "layout": "BaseLayout",
        "deepLinking": true,
        "showExtensions": true,
        "showCommonExtensions": true,
        presets: [
            SwaggerUIBundle.presets.apis,
            SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
    })
    </script>
    </body></html>
    """
    )


# Register endpoints
app.include_router(products_router, prefix="/products", tags=["products"])
