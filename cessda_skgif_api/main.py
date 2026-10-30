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

import asyncio
import logging
import random
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from py12flogging.log_formatter import setup_app_logging
from starlette.exceptions import HTTPException as StarletteHTTPException

from cessda_skgif_api.cache.agent_index import build_agent_index
from cessda_skgif_api.cache.cessda_topic_vocab import preload_vocabs
from cessda_skgif_api.cache.product_index import build_product_index
from cessda_skgif_api.config_loader import load_config
from cessda_skgif_api.db.mongodb import create_client, get_collection_from_app
from cessda_skgif_api.pages import render_accessibility_page, render_info_page
from cessda_skgif_api.routes.organisations import router as organisations_router
from cessda_skgif_api.routes.persons import router as persons_router
from cessda_skgif_api.routes.products import router as products_router
from cessda_skgif_api.routes.topics import (
    initialize_elsst_data,
)
from cessda_skgif_api.routes.topics import (
    router as topics_router,
)
from cessda_skgif_api.utils.errors import (
    InvalidRequestException,
    NotFoundException,
    ProblemDetailException,
    problem_detail_exception_handler,
)

config = load_config()
api_base_url = config.api_base_url
index_rebuild_time = config.index_rebuild_time
index_rebuild_timezone = config.index_rebuild_timezone
if config.api_prefix:
    API_PREFIX = f"/{config.api_prefix}"
else:
    API_PREFIX = ""

setup_app_logging("cessda_skgif_api", loglevel=config.log_level)
_logger = logging.getLogger(__name__)


def seconds_until_target_time(target_hhmm: str, tz_name: str) -> float:
    """Return the seconds until the next occurrence of the target time."""
    now = datetime.now(ZoneInfo(tz_name))

    hour, minute = map(int, target_hhmm.split(":"))

    target_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if target_today <= now:
        target_today += timedelta(days=1)

    return (target_today - now).total_seconds()


async def rebuild_indexes_loop(application):
    """Periodically rebuild and replace the product and agent indexes."""
    while True:
        wait_seconds = seconds_until_target_time(index_rebuild_time, index_rebuild_timezone)
        wait_seconds += random.uniform(0, 120)

        _logger.info("Index rebuild scheduled in %.2f hours", wait_seconds / 3600)

        await asyncio.sleep(wait_seconds)

        try:
            collection = get_collection_from_app(application)

            new_product_index, new_agent_index = await asyncio.gather(
                build_product_index(collection),
                build_agent_index(collection),
            )

            async with application.state.product_index_lock:
                application.state.product_index = new_product_index

            async with application.state.agent_index_lock:
                application.state.agent_index = new_agent_index

        except Exception:  # pylint: disable=broad-exception-caught
            _logger.exception("Index rebuild failed")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize application resources on startup and clean them up on shutdown."""
    initialize_elsst_data()

    await preload_vocabs(["en", "de", "fr", "fi", "sl"])

    # Startup: create one AsyncMongoClient and store it
    application.state.mongo_client = create_client()

    application.state.product_index_lock = asyncio.Lock()
    application.state.agent_index_lock = asyncio.Lock()

    application.state.product_index = None
    application.state.agent_index = None

    collection = get_collection_from_app(application)

    product_index, agent_index = await asyncio.gather(
        build_product_index(collection),
        build_agent_index(collection),
    )

    async with application.state.product_index_lock:
        application.state.product_index = product_index

    async with application.state.agent_index_lock:
        application.state.agent_index = agent_index

    # Start background rebuild loop
    application.state.index_rebuild_task = asyncio.create_task(rebuild_indexes_loop(application))

    try:
        yield
    finally:
        application.state.index_rebuild_task.cancel()

        try:
            await application.state.index_rebuild_task
        except asyncio.CancelledError:
            # Expected cancellation after explicitly cancelling the background task
            pass

        # Shutdown: close client cleanly
        application.state.mongo_client.close()


app = FastAPI(
    lifespan=lifespan,
    title="CESSDA Data Catalogue and ELSST SKG-IF API",
    servers=[{"url": f"{api_base_url}{API_PREFIX}", "description": "CESSDA SKG-IF API"}],
    root_path=API_PREFIX,
    root_path_in_servers=False,
    openapi_url="/openapi_skg-if_cessda_dynamic.yaml",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware, allow_origin_regex=r"https://.*\.cessda\.eu", allow_methods=["GET"], allow_headers=["*"]
)

app.add_exception_handler(ProblemDetailException, problem_detail_exception_handler)


@app.exception_handler(RequestValidationError)
def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return request validation errors as problem detail responses."""
    error = exc.errors()[0]

    location = error.get("loc", [])

    field = ".".join(str(part) for part in location[1:])

    detail = f"Invalid value for parameter '{field}'. {error.get('msg', 'Validation failed.')}"

    return problem_detail_exception_handler(request, InvalidRequestException(detail=detail))


@app.exception_handler(StarletteHTTPException)
def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Return HTTP errors using the appropriate API error response."""
    if exc.status_code == 404:
        return problem_detail_exception_handler(request, NotFoundException())

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("", include_in_schema=False)
@app.get("/", include_in_schema=False)
async def info():
    """Return introductory information, documentation and usage examples."""
    return HTMLResponse(render_info_page())


@app.get("/accessibility", include_in_schema=False)
async def accessibility():
    """Return the accessibility statement for the CESSDA SKG-IF API."""
    return HTMLResponse(render_accessibility_page())


@app.get("/docs-dynamic", include_in_schema=False)
async def custom_swagger_ui_html():
    """Returns Swagger UI for dynamically created OpenAPI documentation"""
    return get_swagger_ui_html(
        openapi_url=f"{API_PREFIX}/openapi_skg-if_cessda_dynamic.yaml",
        title=app.title + " - Swagger UI",
        swagger_js_url=f"{API_PREFIX}/static/swagger-ui-bundle.js",
        swagger_css_url=f"{API_PREFIX}/static/swagger-ui.css",
        swagger_favicon_url=f"{API_PREFIX}/static/swagger-favicon.png",
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    """Returns ReDoc UI for dynamically created OpenAPI documentation"""
    return get_redoc_html(
        openapi_url=f"{API_PREFIX}/openapi_skg-if_cessda_dynamic.yaml",
        title=app.title + " - ReDoc",
        redoc_js_url=f"{API_PREFIX}/static/redoc.standalone.js",
    )


@app.get("/docs", include_in_schema=False)
async def swagger_static():
    """Returns Swagger UI for static OpenAPI documentation"""
    return HTMLResponse(f"""
<html lang="en">
  <head>
    <link type="text/css" rel="stylesheet" href="{API_PREFIX}/static/swagger-ui.css">
    <link rel="shortcut icon" href="{API_PREFIX}/static/swagger-favicon.png">
    <title>CESSDA SKG-IF API - Swagger UI</title>
  </head>
  <body>
  <div id="swagger-ui"></div>
  <script src="{API_PREFIX}/static/swagger-ui-bundle.js"></script>
  <script>
  const API_PREFIX = "{API_PREFIX}";
  const ORIGIN = window.location.origin;
  const ui = SwaggerUIBundle({{
      url: "{API_PREFIX}/static/openapi_skg-if_cessda.yaml",
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
