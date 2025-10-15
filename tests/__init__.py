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

from unittest import TestCase, IsolatedAsyncioTestCase


def test_case_base(parent):
    class _Base(parent):
        maxDiff = None

        def setUp(self):
            self._resets = []
            super().setUp()

        def tearDown(self):
            for reset in self._resets:
                reset()

        def _init_patcher(self, patcher):
            _mock = patcher.start()
            self._resets.append(patcher.stop)
            return _mock

    return _Base


AsyncTestCaseBase = test_case_base(IsolatedAsyncioTestCase)
TestCaseBase = test_case_base(TestCase)
