# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-08

### Added
- Gap and outage detection per node from timestamped readings.
- Availability, MTBF, MTTR, data completeness and packet delivery ratio (from the LoRaWAN frame counter).
- Failure attribution to logged causes, with security events as one cause among others.
- Seeded simulator with ground-truth outages and a validation script.
- `agrometrics` command line with `simulate`, `summarize` and `plot`.
- Test suite (pytest, coverage gate 90%) and GitHub Actions pipeline with lint, test matrix, reproduction run, package build and tag-based release.

### Fixed
- Completeness no longer drops a slot when transmission jitter moves a reading across a slot boundary (readings are snapped to the nearest slot).
