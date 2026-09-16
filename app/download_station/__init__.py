"""Synology Download Station API integration."""

from app.download_station.client import (
    DownloadStationAuthenticationError,
    DownloadStationClient,
    DownloadStationConfigurationError,
    DownloadStationError,
)

__all__ = [
    "DownloadStationAuthenticationError",
    "DownloadStationClient",
    "DownloadStationConfigurationError",
    "DownloadStationError",
]
