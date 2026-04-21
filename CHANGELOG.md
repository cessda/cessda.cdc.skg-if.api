CESSDA SKG-IF API Changelog
===========================

## 0.2.0 - 2026-xx-xx

### Added

- Cache file for results from CESSDA Topic Classification CV API
- Link to mapping of CDC DDI 2.5 to SKG-IF

### Changed

- FastAPI to set up MongoDB client for the lifespan of app
- Local identifiers have resolvable URI if possible, e.g. ORCID or ROR
- Query parameters page and page_size to always be shown in URL
- OpenAPI documentation to also show information about endpoints that have not been implemented yet

### Fixed

- Function to wrap meta and results as JSON-LD fixed to not add extraneous List
- "Try it out" in OpenAPI documentation to query the implemented endpoints instead of hardcoded example server

## 0.1.0 - 2025-12-01

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17572658.svg)](https://doi.org/10.5281/zenodo.17572658)

### Migration Notes

* Products endpoint with some of the filters available
