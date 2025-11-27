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
import shutil
from unittest.mock import patch

# Ensure .ini exists
INI = "cessda_skgif_api.ini"
DIST = "cessda_skgif_api.ini.dist"
if (not os.path.exists(INI)) and os.path.exists(DIST):
    shutil.copyfile(DIST, INI)

# Default env vars for tests
os.environ.setdefault("MONGODB_USERNAME", "testuser")
os.environ.setdefault("MONGODB_PASSWORD", "testpass")


# Fakes for MongoDB
class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def skip(self, n):
        return self

    def limit(self, n):
        return self

    def __aiter__(self):
        async def gen():
            for doc in self.docs:
                yield doc

        return gen()


_UNSET = object()


class FakeCollection:
    def __init__(self, docs=None, one=_UNSET, count=1):
        # Default docs: one ABC123 doc unless overridden
        self._docs = [{"_aggregator_identifier": "ABC123"}] if docs is None else docs
        # Respect explicit None; only use default when caller didn't specify 'one'
        self._one = {"_aggregator_identifier": "ABC123"} if one is _UNSET else one
        self._count = count

    async def count_documents(self, *_):
        return self._count

    def find(self, *_):
        return FakeCursor(self._docs)

    async def find_one(self, *_):
        return self._one


patch("cessda_skgif_api.routes.products.get_collection", return_value=FakeCollection()).start()
