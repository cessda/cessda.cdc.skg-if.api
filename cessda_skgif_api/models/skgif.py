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

"""Models for SKG-IF entity types"""

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
    identifiers: list[Identifier] | None = None
    entity_type: str = "person"


class OrganisationLite(BaseModel):
    """SKG-IF organization simplified for person affiliation and product"""

    local_identifier: str
    name: str
    identifiers: list[Identifier] | None = None
    entity_type: str = "organisation"


class Affiliation(BaseModel):
    """Affiliated organisation of an SKG-IF person"""

    affiliation: OrganisationLite
    role: str = "affiliate"


class Person(BaseModel):
    """SKG-IF person"""

    local_identifier: str
    entity_type: str = "person"
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    identifiers: list[Identifier] | None = None
    affiliations: list[Affiliation] | None = None


class Organisation(BaseModel):
    """SKG-IF organisation, includes authors and publishers/distributors"""

    local_identifier: str
    entity_type: str = "organisation"
    name: str
    identifiers: list[Identifier] | None = None
    short_name: str | None = None
    other_names: list[str] | None = None
    website: str | None = None
    country: str | None = None
    types: list[str] | None = None


class Agent(BaseModel):
    """SKG-IF generic agent if person or organization can't be determined"""

    local_identifier: str
    name: str
    identifiers: list[Identifier] | None = None
    entity_type: str = "agent"


class Contribution(BaseModel):
    """SKG-IF contributions, e.g. author that is a person that has an affiliated organization"""

    role: str
    by: PersonLite | OrganisationLite | Agent
    declared_affiliations: list[OrganisationLite] | None = None


class Term(BaseModel):
    """Term with support for multilinguality"""

    local_identifier: str
    identifiers: list[Identifier] | None = None
    entity_type: str = "topic"
    labels: dict[str, str]


class TopicLite(BaseModel):
    """SKG-IF topic"""

    term: Term


class Venue(BaseModel):
    """SKG-IF venue, e.g. CESSDA"""

    local_identifier: str
    name: str
    identifiers: list[Identifier] | None = None
    entity_type: str = "venue"


class DataSource(BaseModel):
    """SKG-IF data source, e.g. CESSDA SP"""

    local_identifier: str
    name: str
    identifiers: list[Identifier] | None = None
    entity_type: str = "datasource"


class Biblio(BaseModel):
    """SKG-IF biblio contains where venue and data source"""

    model_config = ConfigDict(populate_by_name=True)
    in_: Venue | None = Field(None, alias="in")
    hosting_data_source: DataSource | None


class Manifestation(BaseModel):
    """SKG-IF manifestation contains dates, access rights and biblio"""

    dates: dict[str, list[str]] | None = None
    access_rights: dict[str | None, str | None] | None = None
    biblio: Biblio | None = None


class GrantLite(BaseModel):
    """SKG-IF grant simplified for product"""

    local_identifier: str
    entity_type: str = "grant"
    grant_number: str | None = None
    funding_agency: OrganisationLite | None = None


class Product(BaseModel):
    """SKG-IF product, e.g. study or related publication"""

    local_identifier: str
    entity_type: str = "product"
    product_type: str
    identifiers: list[Identifier] | None
    titles: dict[str, list[str]]
    abstracts: dict[str, list[str]] | None = None
    topics: list[TopicLite] | None = None
    contributions: list[Contribution] | None = None
    manifestations: list[Manifestation] | None = None
    funding: list[GrantLite] | None = None
    related_products: dict[str, list[str]] | None = None
