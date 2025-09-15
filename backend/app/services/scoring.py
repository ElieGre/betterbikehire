from __future__ import annotations

from math import asin, cos, exp, radians, sin, sqrt
from typing import Dict, List

from ..config import settings

EARTH_R = 6371000.0  # meters


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    # returns meters
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_R * asin(sqrt(a))


def sigmoid_minutes(m):
    return 1.0 / (1.0 + exp((m - 6) / 1.5))  # ~6 min sweet spot


def availability_ratio(bikes: int, capacity: int) -> float:
    if capacity <= 0:
        return 0.0
    return max(0.0, min(1.0, bikes / capacity))


def dock_ratio(docks: int, capacity: int) -> float:
    if capacity <= 0:
        return 0.0
    return max(0.0, min(1.0, docks / capacity))


def best_dock_score_near_dest(
    stations: List[Dict], dest_lat: float, dest_lon: float, radius_m: int | None = None
) -> float:
    r = radius_m or settings.DEST_STATION_RADIUS_M
    scores = []
    for s in stations:
        d = haversine_m(dest_lat, dest_lon, s["lat"], s["lon"])
        if d <= r:
            scores.append(dock_ratio(s["docks_available"], s["capacity"]))
    return max(scores) if scores else 0.0


def score_station_candidate(
    station: Dict,
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    dest_dock_score: float,
) -> float:
    # proximity by walking time (approx 80 m/min)
    walk_m = haversine_m(origin_lat, origin_lon, station["lat"], station["lon"])
    walk_min = walk_m / 80.0
    proximity = sigmoid_minutes(walk_min)

    avail = availability_ratio(station["bikes_available"], station["capacity"])
    # simple weights tuned for stations (no battery/health here)
    w_prox, w_avail, w_dest = 0.35, 0.35, 0.30
    return w_prox * proximity + w_avail * avail + w_dest * dest_dock_score
