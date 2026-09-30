"""Shared routing primitives: haversine distances and travel-time math."""

import numpy as np

EARTH_RADIUS_M = 6_371_000.0
SPEED_MPS = 13.4  # ~30 mph average urban driving speed
METERS_PER_MILE = 1609.344


def haversine_matrix(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Pairwise great-circle distances in meters."""
    lat = np.radians(lats)
    lon = np.radians(lons)
    dlat = lat[:, None] - lat[None, :]
    dlon = lon[:, None] - lon[None, :]
    a = (np.sin(dlat / 2) ** 2
         + np.cos(lat[:, None]) * np.cos(lat[None, :]) * np.sin(dlon / 2) ** 2)
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


def travel_seconds(dist_m: float) -> float:
    return dist_m / SPEED_MPS


def to_miles(meters: float) -> float:
    return meters / METERS_PER_MILE
