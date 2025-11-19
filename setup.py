#!/usr/bin/env python3
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
from setuptools import setup, find_packages


with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "VERSION")) as fileobj:
    version = fileobj.readline().strip()


setup(
    name="cessda_skgif_api",
    version=version,
    description="Provide SKG-IF compatible API for metadata of studies in CESSDA Data Catalogue.",
    license='Apache 2.0',
    packages=find_packages(exclude=["tests"]),
    install_requires=[],
    entry_points={},
)
