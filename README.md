# agrotrust-metrics

[![CI](https://github.com/kozhanov7/agrotrust/actions/workflows/ci.yml/badge.svg)](https://github.com/kozhanov7/agrotrust/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue)

Reliability metrics for IoT agricultural monitoring data. The tool takes the readings that
sensor nodes actually delivered, finds where data is missing, and turns that into
availability, MTBF, MTTR, data completeness and packet delivery ratio per node. If a
failure log is available, it splits downtime by cause. Security incidents are one cause
among others (hardware, power, radio, software), which is how dependability research
treats them.

It is part of the master's research *Methods for assessing reliability and security in IoT
agricultural monitoring systems* (Astana IT University) and is used to evaluate a LoRaWAN
greenhouse testbed.

![Outage timeline of a simulated 14-node greenhouse, coloured by cause](docs/timeline.png)

## Installation

```bash
git clone https://github.com/kozhanov7/agrotrust.git
cd agrotrust-metrics
pip install -e .            # or: pip install -e ".[dev]" for tests and linting
```

Python 3.10 to 3.13. Dependencies: NumPy, pandas, Matplotlib.

## Quick start

```bash
# 1. synthetic month of data for 14 nodes, with the true outages saved next to it
agrometrics simulate --nodes 14 --days 30 --seed 42 --out data

# 2. metrics per node, fleet summary and downtime by cause
agrometrics summarize data/readings.csv --events data/events.csv --out summary.csv

# 3. figures
agrometrics plot data/readings.csv --events data/events.csv --out timeline.png --causes-out causes.png
```

A small real-format dataset (3 nodes, 7 days) is in `examples/`:

```bash
agrometrics summarize examples/sample_readings.csv --events examples/sample_events.csv
```

From Python:

```python
import pandas as pd
from agrotrust_metrics.io import load_readings
from agrotrust_metrics.metrics import summarize, overall

readings = load_readings("examples/sample_readings.csv")
table = summarize(readings, interval=pd.Timedelta(minutes=10))
print(overall(table))
```

## Input format

`readings.csv`, one row per received uplink:

| column      | required | meaning                                   |
|-------------|----------|-------------------------------------------|
| `timestamp` | yes      | time of reception (ISO 8601, UTC assumed) |
| `node_id`   | yes      | sensor node identifier                    |
| `fcnt`      | no       | LoRaWAN uplink frame counter, enables PDR |
| other       | no       | measured values, ignored by the metrics   |

`events.csv`, one row per logged failure: `start`, `end`, `node_id`, `cause`, where cause is
one of `hardware`, `power`, `radio`, `software`, `security`, `unknown`.

## Metric definitions

| metric | definition |
|---|---|
| gap | time between two consecutive readings of a node longer than 1.5 sampling intervals |
| outage | gap with at least `--min-missed` (default 3) missing readings; shorter gaps count as packet loss |
| downtime | sum over outages of (gap length - one interval) |
| availability | (observation time - downtime) / observation time |
| MTBF | uptime / number of outages |
| MTTR | downtime / number of outages |
| completeness | share of sampling slots with at least one reading (readings snap to the nearest slot) |
| PDR | received frames / frames sent, from the frame counter; a counter decrease starts a new segment |

The frame counter separates two kinds of failure: when the node itself is down (power,
hardware, software) the counter stops, when the link is down (radio, jamming) the counter
keeps running and PDR falls.

## Validation

The simulator injects outages with known start, end and cause, so detection can be checked
against a ground truth:

```bash
python examples/validate_detection.py --seeds 20
```

With 1% random packet loss and up to 30 s of timing jitter, all injected outages of three
or more intervals were detected (recall 1.0, precision 1.0 over 20 seeds), with a median
error in outage length of about 3 minutes. The test suite repeats a strict version of this
check on every commit.

## Docker

```bash
docker build -t agrotrust-metrics .
mkdir -p data && chmod 777 data
docker run --rm -v "$PWD/data:/data" agrotrust-metrics simulate --nodes 14 --days 30 --out /data
docker run --rm -v "$PWD/data:/data" agrotrust-metrics summarize /data/readings.csv --events /data/events.csv
```

The image is built in two stages: the first one builds the wheel, the second one only
installs it, so build tools do not end up in the final image. The tool runs as a non-root
user.

## Jenkins pipeline

`Jenkinsfile` describes the pipeline that runs on a local Jenkins:

1. checkout, Python virtual environment, `ruff` lint and format check;
2. unit tests with `pytest` (JUnit report and coverage, 90% gate);
3. Docker image build, tagged with the build number and short commit hash;
4. a run of the image on a small simulated dataset, the summary is kept as an artifact;
5. optional push to Docker Hub (parameter `PUSH_IMAGE`, credentials id `dockerhub`);
6. deploy to Minikube: the image is loaded into the cluster and `k8s/job.yaml` runs the
   analysis as a Kubernetes Job.

Jenkins polls the repository every 2 minutes, so each commit to `main` starts a build.
On macOS the setup is: Docker Desktop, `brew install jenkins-lts minikube kubectl python@3.12`,
`minikube start --driver=docker`, `brew services start jenkins-lts`, then a Pipeline job
"Pipeline script from SCM" pointing to this repository.

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest --cov=agrotrust_metrics
```

Continuous integration (`.github/workflows/ci.yml`) runs on every push and pull request:
lint and format check, tests on Python 3.10 to 3.13 (Ubuntu) and 3.12 (Windows) with a 90%
coverage gate, a reproduction run of the example analysis with its figures uploaded as an
artifact, and a package build with a smoke test of the wheel. Pushing a tag `v*` publishes a
GitHub release with the wheel and the example results. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Limitations

- Availability is measured from what arrived. A node that sends wrong values on time looks
  healthy; value plausibility checks are planned.
- Outages shorter than `--min-missed` intervals are counted as packet loss, not downtime.
- Cause attribution relies on the failure log; outages without a matching log entry are
  `unknown`.

## Citation and license

See [CITATION.cff](CITATION.cff). Released under the [MIT License](LICENSE).
# agrotrust
