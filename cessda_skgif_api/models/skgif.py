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

"""Models for SKG-IF entity types"""

from typing import List, Dict, Optional, Union
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


class Identifier(BaseModel):
    """SKG-IF identifier"""

    value: str
    scheme: str


class PersonLite(BaseModel):
    """SKG-IF person simplified for product"""

    local_identifier: str
    name: str
    identifiers: Optional[List[Identifier]] = None
    entity_type: str = "person"


class OrganisationLite(BaseModel):
    """SKG-IF organization simplified for product"""

    local_identifier: str
    name: str
    identifiers: Optional[List[Identifier]] = None
    entity_type: str = "organisation"


class Agent(BaseModel):
    """SKG-IF generic agent if person or organization can't be determined"""

    local_identifier: str
    name: str
    identifiers: Optional[List[Identifier]] = None
    entity_type: str = "agent"


class Contribution(BaseModel):
    """SKG-IF contributions, e.g. author that is a person that has an affiliated organization"""

    role: str
    by: Union[PersonLite, OrganisationLite, Agent]
    declared_affiliations: Optional[List[OrganisationLite]] = None


class Term(BaseModel):
    """Term with support for multilinguality"""

    local_identifier: str
    identifiers: Optional[List[Identifier]] = None
    entity_type: str = "topic"
    labels: Dict[str, str]


class TopicLite(BaseModel):
    """SKG-IF topic"""

    term: Term


class Venue(BaseModel):
    """SKG-IF venue, e.g. CESSDA"""

    local_identifier: str
    name: str
    identifiers: Optional[List[Identifier]] = None
    entity_type: str = "venue"


class DataSource(BaseModel):
    """SKG-IF data source, e.g. CESSDA SP"""

    local_identifier: str
    name: str
    identifiers: Optional[List[Identifier]] = None
    entity_type: str = "datasource"


class Biblio(BaseModel):
    """SKG-IF biblio contains where venue and data source"""

    model_config = ConfigDict(populate_by_name=True)
    in_: Optional[Venue] = Field(None, alias="in")
    hosting_data_source: Optional[DataSource]


class Manifestation(BaseModel):
    """SKG-IF manifestation contains dates, access rights and biblio"""

    dates: Optional[Dict[str, List[str]]] = None
    access_rights: Optional[Dict[Optional[str], Optional[str]]] = None
    biblio: Optional[Biblio] = None


class GrantLite(BaseModel):
    """SKG-IF grant simplified for product"""

    local_identifier: str
    entity_type: str = "grant"
    grant_number: Optional[str] = None
    funding_agency: Optional[OrganisationLite] = None


class Product(BaseModel):
    """SKG-IF product, e.g. study or related publication"""

    local_identifier: str
    entity_type: str = "product"
    product_type: str
    identifiers: Optional[List[Identifier]]
    titles: Dict[str, List[str]]
    abstracts: Optional[Dict[str, List[str]]] = None
    topics: Optional[List[TopicLite]] = None
    contributions: Optional[List[Contribution]] = None
    manifestations: Optional[List[Manifestation]] = None
    funding: Optional[List[GrantLite]] = None
