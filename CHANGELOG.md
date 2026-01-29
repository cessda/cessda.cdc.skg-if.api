CESSDA SKG-IF API Changelog
===========================

## 0.2.0 - 2026-xx-xx

### Added

- Cache file for results from CESSDA Topic Classification CV API

### Changed

- FastAPI to set up MongoDB client for the lifespan of app
- Local identifiers have resolvable URI if possible, e.g. ORCID or ROR

### Fixed

- Function to wrap meta and results as JSON-LD fixed to not add extraneous List

## 0.1.0 - 2025-12-01

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17572658.svg)](https://doi.org/10.5281/zenodo.17572658)

### Migration Notes

* Products endpoint with some of the filters available
