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

"""Constant values"""

import re

from cessda_skgif_api.utils.helpers import normalize_ror_lookup_name

STUDY_LOCAL_ID_PREFIX = "cessda_product_research_data_"
RELPUB_LOCAL_ID_PREFIX = "cessda_product_literature_"
PERSON_LOCAL_ID_PREFIX = "cessda_person_"
ORGANISATION_LOCAL_ID_PREFIX = "cessda_organisation_"

STUDY_ID_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
RELPUB_ID_RE = re.compile(r"^[0-9a-f]{24}$", re.IGNORECASE)
PERSON_ID_RE = re.compile(r"^[0-9a-f]{24}$", re.IGNORECASE)
ORGANISATION_ID_RE = re.compile(r"^[0-9a-f]{24}$", re.IGNORECASE)

# -----------------------------
# ROR (Crockford Base32)
# -----------------------------
# Allowed letters: a–z excluding i, l, o, u (Crockford Base32), case-insensitive.
# Pattern: 0 + 6 letters/digits + 2 digits (checksum)

_ROR_CORE = r'0[a-hj-km-np-tv-z|0-9]{6}[0-9]{2}'
# Full URL form (with optional trailing slash)
ROR_URL_RE = re.compile(rf'^https?://(?:www\.)?ror\.org/({_ROR_CORE})/?$', re.IGNORECASE)
# Plain code form
ROR_CODE_RE = re.compile(rf'^({_ROR_CORE})$', re.IGNORECASE)

# -----------------------------
# ORCID (ISO/IEC 7064 MOD 11-2)
# -----------------------------
# Canonical code: dddd-dddd-dddd-ddd[0-9X]
# We accept uppercase X (standard) but also lowercase x by using IGNORECASE.
_ORCID_CORE = r'(?:\d{4}-){3}\d{3}[0-9X]'
# Full URL form (with optional trailing slash)
ORCID_URL_RE = re.compile(rf'^https?://(?:www\.)?orcid\.org/({_ORCID_CORE})/?$', re.IGNORECASE)
# Plain code form
ORCID_CODE_RE = re.compile(rf'^({_ORCID_CORE})$', re.IGNORECASE)

# CESSDA needs to be the first one in this list (STATIC_ORGANISATIONS[0] is used in study transformer)
STATIC_ORGANISATIONS = [
    {
        "name": "Consortium of European Social Science Data Archives",
        "short_name": "CESSDA",
        "ror": "02wg9xc72",
        "website": "https://www.cessda.eu/",
    }
]

ROR_LOOKUP = {
    normalize_ror_lookup_name(name): ror
    for name, ror in {
        "Czech Social Science Data Archive": "01snj4592",
        "DANS-KNAW": "008pnp284",
        "DASSI – Data Archive for Social Sciences in Italy": "028znnm42",
        "EKKE. SoDaNet – Greek Research Infrastructure for Social Science": "035hs9g56",
        "FORS – Swiss Centre of Expertise in the Social Sciences": "00weppy16",
        "PROGEDO": "01esk6458",
        "GESIS – Leibniz-Institute for the Social Sciences": "018afyw53",
        "Lithuanian Data Archive for Social Sciences and Humanities": "00c4rg397",
        "Sciences Po Center for Socio-Political Data": "03aef3108",
        "Sikt – Norwegian Agency for Shared Services in Education and Research": "03zee5r16",
        "State Archives of Belgium. Social Sciences and Digital Humanities Archive": "04y1ast97",
        "Swedish National Data Service": "00ancw882",
        "Tampere University. Finnish Social Science Data Archive": "033003e23",
        "UK Data Service": "0468x4e75",
        "University College Dublin. Irish Social Science Data Archive": "05m7pjf47",
        "University of Iceland. Icelandic Research Data Service": "01db6h964",
        "University of Ljubljana. Social Science Data Archives": "05njb9z20",
        "University of Vienna. Austrian Social Science Data Archive": "03prydq77",
        "University of Zagreb. Croatian Social Science Data Archive": "00mv6sv71",
        "Research Documentation Centre, Centre for Social Sciences, ELTE, RDC CSS": "0492k9x16",
        ###########
        # Aliases #
        ###########
        # ADP
        "Arhiv druzboslovnih podatkov": "05njb9z20",
        "Arhiv družboslovnih podatkov = Social Science Data Archives": "05njb9z20",
        "Arhiv družboslovnih podatkov, Univerza v Ljubljani,": "05njb9z20",
        "Slovenian Social Science Data Archives (ADP), Arhiv družboslovnih podatkov": "05njb9z20",
        "University of Ljubljana, Slovenian Social Science Data Archives": "05njb9z20",
        "Univerza v Ljubljani, Arhiv družboslovnih podatkov": "05njb9z20",
        # AUSSDA
        "The Austrian Social Science Data Archive (AUSSDA)": "03prydq77",
        # CDSP
        "Centre de données socio-politiques": "03aef3108",
        "Centre de Données Socio-Pollituques": "03aef3108",
        "Sciences Po, Centre de données socio-politiques": "03aef3108",
        "Sciences Po, Centre de données socio-politiques (CDSP), CNRS": "03aef3108",
        "Sciences Po, Centre de données socio-politiques (CDSP), CNRS (CDSP)": "03aef3108",
        "Sciences Po, Centre de données socio-politiques (CDSP), CNRS, Paris, France": "03aef3108",
        "data.sciencespo": "03aef3108",
        "Sciences Po, Center for Socio-Political Data (CDSP), CNRS": "03aef3108",
        "Centre de Donnees Socio-Politiques Sciences Po, Paris, France": "03aef3108",
        "Centre de Données Socio-Politiques (CDSP), Sciences-Po": "03aef3108",
        "Sciences Po Center for Socio-Political Data (CDSP)": "03aef3108",
        "CDSP": "03aef3108",
        # CROSSDA
        "Croatian Social Science Data Archive": "00mv6sv71",
        # CSDA
        "CSDA": "01snj4592",
        "Czech social science data archive": "01snj4592",
        "Czech Social Science Data Arcive": "01snj4592",
        "The Czech Social Science Data Archive": "01snj4592",
        "Český sociálněvědní datový archiv": "01snj4592",
        # DANS
        "DANS": "008pnp284",
        "DANS (retired)": "008pnp284",
        "DANS - Data Archiving and Networked Services": "008pnp284",
        "DANS Data Archive": "008pnp284",
        "DANS Data Station Social Sciences and Humanities": "008pnp284",
        "Data Archiving and Networked Services – DANS": "008pnp284",
        "Statistics Netherlands; Data Archiving and Networked Services (DANS)": "008pnp284",
        # EKKE
        "Κατάλογος Δεδομένων SoDaNet": "035hs9g56",
        "EKKE- National Centre for Social Research": "035hs9g56",
        "National Centre for Social Research (EKKE)": "035hs9g56",
        # FORS
        "FORS": "00weppy16",
        "FORS Suisse foundation for research in social sciences, c/o University of Lausanne, Switzerland": "00weppy16",
        "FORS swiss foundation for research in social sciences, c/o University of Lausanne, Switzerland": "00weppy16",
        "FORS swiss foundation for research in soical sciences, c/o University of Lausanne, Switzerland": "00weppy16",
        "FORS, c/o University of Lausanne, Switzerland": "00weppy16",
        "FORS, Swiss Foundation for Research in Social Sciences, Université de Lausanne, Lausanne, Switzerland": "00weppy16",
        "Swiss Foundation for Research in Social Sciences (FORS), University of Lausanne, Switzerland": "00weppy16",
        # FSD
        "Finnish Social Science Data Archive": "033003e23",
        "Yhteiskuntatieteellinen tietoarkisto": "033003e23",
        "University of Tampere. Finnish Social Science Data Archive": "033003e23",
        "Finnish Social Science Data Archive (FSD)": "033003e23",
        "Finnish Social Science Data Archive, University of Tampere, Finland": "033003e23",
        "FSD Finnish Social Science Data Archive University of Tampere, Finland": "033003e23",
        "University of Tampere/ Finnish Social Science Data Archive, Finland": "033003e23",
        # DATICE
        "Gagnaþjónusta félagsvísinda á Íslandi": "01db6h964",
        "Gagnaþjónusta vísinda á Íslandi": "01db6h964",
        "GAGNÍS": "01db6h964",
        "Ganaþjónusta Félagsvísinda": "01db6h964",
        "Icelandic Social Science Data Service": "01db6h964",
        # GESIS
        "GESIS": "018afyw53",
        "GESIS Data Archive": "018afyw53",
        "GESIS Data Archive for the Social Sciences": "018afyw53",
        "GESIS Data Archive, Cologne": "018afyw53",
        "GESIS Mannheim": "018afyw53",
        "GESIS, Mannheim": "018afyw53",
        "GESIS Mannheim, Köln": "018afyw53",
        "GESIS, Germany": "018afyw53",
        "GESIS Leibnitz-Institut für Sozialwissenschaften, Mannheim, Germany": "018afyw53",
        "GESIS - Leibniz Institute for the Social Sciences, Germany": "018afyw53",
        "GESIS - Leibniz Institute for the Social Sciences, Mannheim": "018afyw53",
        "GESIS - Leibniz Institute for the Social Sciences, Mannheim, Germany": "018afyw53",
        "GESIS - Leibniz Institute for the Social Sciences, Cologne": "018afyw53",
        "GESIS - Leibniz Institute for the Social Sciences, Cologne, Germany": "018afyw53",
        "GESIS - Leibniz Institut für Sozialwissenschaften": "018afyw53",
        "GESIS - Leibniz Institut für Sozialwissenschaften, Mannheim": "018afyw53",
        "GESIS - Leibniz-Institut für Sozialwissenschaften": "018afyw53",
        "GESIS - Leibniz-Institut für Sozialwissenschaften, Mannheim": "018afyw53",
        "GESIS - Leibniz-Institut für Sozialwissenschaften, Germany": "018afyw53",
        "GESIS – Leibniz-Institut für Sozialwissenschaften, Mannheim": "018afyw53",
        "GESIS – Leibniz-Institut für Sozialwissenschaften, Köln": "018afyw53",
        "GESIS – Leibniz-Institut für Sozialwissenschaften in Mannheim": "018afyw53",
        "GESIS (Leibniz Institute for the Social Sciences) Data Archive": "018afyw53",
        "Leibniz Institute for Social Sciences (GESIS) Data Archive": "018afyw53",
        "Leibniz Institute for the Social Sciences (GESIS)": "018afyw53",
        "Leibniz Institute for the Social Sciences (GESIS) data archive": "018afyw53",
        # INED
        "Institut national d'études démographiques (Ined)": "02cnsac56",
        "Service des enquêtes et des sondages, Institut national d'études démographiques": "02cnsac56",
        "Service des Enquêtes et Sondages, Institut national d'études démographiques": "02cnsac56",
        # ISSDA
        "Irish Social Science Data Archive": "05m7pjf47",
        # LiDA
        "Lithuanian Data Archive for SSH (LiDA)": "00c4rg397",
        # PROGEDO
        "Archives de données issues de la statistique publique": "01esk6458",
        "Archives de données issues de la Statistique Publique (ADISP)": "01esk6458",
        "ADISP": "01esk6458",
        "Progedo-Adisp": "01esk6458",
        # RDC
        "Research Documentation Centre, Centre for Social Sciences, Hungary": "0492k9x16",
        # Sikt
        "Norwegian Centre for Research Data (NSD); Sikt - Norwegian Agency for Shared Services in Education and Research": "03zee5r16",
        "Sikt": "03zee5r16",
        "Sikt - Kunnskapssektorens tjenesteleverandør": "03zee5r16",
        "Sikt - Norwegian Agency for Shared Services in Education and Research": "03zee5r16",
        # SODHA
        "Social Sciences and Digital Humanities Archive – SODHA": "04y1ast97",
        # SND
        "SND": "00ancw882"
    }.items()
}

URL_TO_DATASOURCE = {
    "https://archivdv.soc.cas.cz/oai": "Czech Social Science Data Archive",
    "https://oai-service.labs.dans.knaw.nl/ss/oai": "DANS-KNAW",
    "https://ssh.datastations.nl/oai": "DANS-KNAW",
    "https://oai.dassi-archive.it/v0/oai": "DASSI – Data Archive for Social Sciences in Italy",
    "https://datacatalogue.sodanet.gr/oai": "EKKE. SoDaNet – Greek Research Infrastructure for Social Science",
    "https://www.swissubase.ch/oai-pmh/v1/oai": "FORS – Swiss Centre of Expertise in the Social Sciences",
    "https://data.progedo.fr/oai": "PROGEDO",
    "https://dbkapps.gesis.org/dbkoai": "GESIS – Leibniz-Institute for the Social Sciences",
    "https://dataverse-ucd.4science.cloud/oai": "Irish Social Science Data Archive",
    "https://lida.dataverse.lt/oai": "Lithuanian Data Archive for Social Sciences and Humanities",
    "https://data.sciencespo.fr/oai": "Sciences Po Center for Socio-Political Data",
    "https://oai-pmh.ethmigsurveydatahub.eu/oai": "Ethnic and Immigrant Minorities' Survey Data Network",
    "https://colectica-ess-published.nsd.no/oai/request": "Sikt – Norwegian Agency for Shared Services in Education and Research",
    "https://colectica-forskningsdata-published.nsd.no/oai/request": "Sikt – Norwegian Agency for Shared Services in Education and Research",
    "https://www.sodha.be/oai": "State Archives of Belgium. Social Sciences and Digital Humanities Archive",
    "https://api.researchdata.se/oai-pmh": "Swedish National Data Service",
    "https://services.fsd.tuni.fi/v0/oai": "Tampere University. Finnish Social Science Data Archive",
    "https://oai.ukdataservice.ac.uk:8443/oai/provider": "UK Data Service",
    "https://dataverse.rhi.hi.is/oai": "University of Iceland. Icelandic Research Data Service",
    "https://gagnis.hi.is/oai": "University of Iceland. Icelandic Research Data Service",
    "https://www.adp.fdv.uni-lj.si/v0/oai": "University of Ljubljana. Social Science Data Archives",
    "https://data.aussda.at/oai": "University of Vienna. Austrian Social Science Data Archive",
    "https://data.crossda.hr/oai": "University of Zagreb. Croatian Social Science Data Archive",
    "https://openarchive.tk.mta.hu/cgi/oai2": "Research Documentation Centre, Centre for Social Sciences, ELTE, RDC CSS",
}

ROR_PRIMARY_NAMES = {
    ror: datasource_name
    for datasource_name in URL_TO_DATASOURCE.values()
    if (ror := ROR_LOOKUP.get(normalize_ror_lookup_name(datasource_name)))
}

ALLOWED_IDENTIFIER_TYPES = {
    "arxiv",
    "bibcode",
    "crossref",
    "doi",
    "eissn",
    "handle",
    "isbn",
    "issn",
    "ivoid",
    "lissn",
    "omid",
    "openalex",
    "opendoar",
    "orcid",
    "pmcid",
    "pmid",
    "ror",
    "spase",
    "url",
    "urn",
    "viaf",
    "w3id",
}
