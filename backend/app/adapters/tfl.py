from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx

from ..config import settings

# simple in-memory cache to avoid hammering the API
_CACHE: Dict[str, tuple[float, Any]] = {}
_CACHE_TTL_S = 30.0


def _cache_get(key: str):
    now = time.time()
    if key in _CACHE:
        ts, value = _CACHE[key]
        if now - ts < _CACHE_TTL_S:
            return value
    return None


def _cache_set(key: str, value: Any):
    _CACHE[key] = (time.time(), value)


def _build_params() -> dict:
    params = {}
    if settings.TFL_APP_ID and settings.TFL_APP_KEY:
        params["app_id"] = settings.TFL_APP_ID
        params["app_key"] = settings.TFL_APP_KEY
    return params


async def fetch_all_bikepoints() -> List[Dict[str, Any]]:
    """
    Raw BikePoint list from TfL. Each item has additionalProperties where
    NbBikes, NbDocks, NbEmptyDocks live.
    """
    cached = _cache_get("tfl_all_bikepoints")
    if cached is not None:
        return cached

    url = f"{settings.TFL_BASE_URL}/BikePoint"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, params=_build_params())
        r.raise_for_status()
        data = r.json()

    _cache_set("tfl_all_bikepoints", data)
    return data


def _props_to_map(bp: Dict[str, Any]) -> Dict[str, str]:
    props = {}
    for p in bp.get("additionalProperties", []):
        props[p.get("key")] = p.get("value")
    return props


def normalize_station(bp: Dict[str, Any]) -> Dict[str, Any]:
    props = _props_to_map(bp)
    capacity = int(props.get("NbDocks", 0) or 0)
    bikes = int(props.get("NbBikes", 0) or 0)
    empty = int(props.get("NbEmptyDocks", 0) or 0)
    return {
        "id": bp["id"],  # e.g., "BikePoints_123"
        "name": bp.get("commonName"),
        "lat": bp.get("lat"),
        "lon": bp.get("lon"),
        "capacity": capacity,
        "bikes_available": bikes,
        "docks_available": empty,
    }


async def fetch_normalized_stations() -> List[Dict[str, Any]]:
    raw = await fetch_all_bikepoints()
    return [normalize_station(bp) for bp in raw]


async def get_station_by_id(station_id: str) -> Optional[Dict[str, Any]]:
    """Return ONE normalized station by BikePoint ID (e.g., 'BikePoints_278')."""
    data = await fetch_all_bikepoints()
    for bp in data:
        if bp["id"] == station_id:
            return normalize_station(bp)
    return None


async def find_stations_by_name(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Return up to 'limit' normalized stations whose commonName contains the query (case-insensitive)."""
    data = await fetch_all_bikepoints()
    ql = query.strip().lower()
    hits = []
    for bp in data:
        name = (bp.get("commonName") or "").lower()
        if ql and ql in name:
            hits.append(normalize_station(bp))
    # Simple sort: shorter names first (tends to surface exact-ish matches)
    hits.sort(key=lambda s: len(s.get("name") or ""))
    return hits[:limit]


async def get_station_by_name(query: str) -> Optional[Dict[str, Any]]:
    """Best single match by name (first from find_stations_by_name)."""
    matches = await find_stations_by_name(query, limit=1)
    return matches[0] if matches else None
