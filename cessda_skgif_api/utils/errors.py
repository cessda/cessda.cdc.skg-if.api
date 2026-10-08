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

from fastapi import Request
from fastapi.responses import JSONResponse


class ProblemDetailException(Exception):
    def __init__(
        self,
        *,
        status: int,
        type: str,
        title: str,
        detail: str,
        instance: str | None = None,
    ):
        self.status = status
        self.type = type
        self.title = title
        self.detail = detail
        self.instance = instance


class InvalidFilterException(ProblemDetailException):
    def __init__(
        self,
        detail: str,
        instance: str | None = None,
    ):
        super().__init__(
            status=422,
            type="https://skg-if.github.io/api/errors#INVALID_FILTER",
            title="INVALID_FILTER",
            detail=detail,
            instance=instance,
        )


async def problem_detail_exception_handler(
    request: Request,
    exc: ProblemDetailException,
):
    return JSONResponse(
        status_code=exc.status,
        content={
            "type": exc.type,
            "title": exc.title,
            "status": str(exc.status),
            "detail": exc.detail,
            "instance": exc.instance or str(request.url),
        },
    )
