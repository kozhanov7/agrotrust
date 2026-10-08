"""Reliability metrics for IoT agricultural monitoring data."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("agrotrust-metrics")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0+local"
