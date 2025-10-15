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

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from typing import List, Dict, Optional, Union


class Identifier(BaseModel):
    value: str
    scheme: str


class Person(BaseModel):
    local_identifier: str
    name: str
    identifiers: Optional[List[Identifier]] = None
    entity_type: str = "person"


class Organisation(BaseModel):
    local_identifier: str
    name: str
    identifiers: Optional[List[Identifier]] = None
    entity_type: str = "organisation"


class Agent(BaseModel):
    local_identifier: str
    name: str
    identifiers: Optional[List[Identifier]] = None
    entity_type: str = "agent"


class Contribution(BaseModel):
    role: str
    by: Union[Person, Organisation, Agent]
    declared_affiliations: Optional[List[Organisation]] = None


class Term(BaseModel):
    local_identifier: str
    identifiers: Optional[List[Identifier]] = None
    entity_type: str = "topic"
    labels: Dict[str, str]


class Topic(BaseModel):
    term: Term


class Venue(BaseModel):
    local_identifier: str
    name: str
    identifiers: Optional[List[Identifier]] = None
    entity_type: str = "venue"


class DataSource(BaseModel):
    local_identifier: str
    name: str
    identifiers: Optional[List[Identifier]] = None
    entity_type: str = "datasource"


class Biblio(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    in_: Optional[Venue] = Field(None, alias="in")
    hosting_data_source: Optional[DataSource]


class Manifestation(BaseModel):
    dates: Optional[Dict[str, List[str]]] = None
    access_rights: Optional[Dict[str, str]] = None
    biblio: Optional[Biblio] = None


class Grant(BaseModel):
    local_identifier: str
    entity_type: str = "grant"
    grant_number: Optional[str] = None
    funding_agency: Optional[Organisation] = None


class Product(BaseModel):
    local_identifier: str
    entity_type: str = "product"
    product_type: str
    identifiers: List[Identifier]
    titles: Dict[str, List[str]]
    abstracts: Optional[Dict[str, List[str]]] = None
    topics: Optional[List[Topic]] = None
    contributions: Optional[List[Contribution]] = None
    manifestations: Optional[List[Manifestation]] = None
    funding: Optional[List[Grant]] = None


class PaginationMeta(BaseModel):
    count: int
    page: int
    page_size: int
    pages: int


class ProductListResponse(BaseModel):
    meta: PaginationMeta
    results: List[Product]
