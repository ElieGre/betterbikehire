from __future__ import annotations

from typing import Any, Dict, List

import httpx


async def fetch_gbfs_index(index_url: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(index_url)
        r.raise_for_status()
        return r.json()


def _find_feed_url(idx: Dict[str, Any], feed_name: str, lang: str = "en") -> str | None:
    data = idx.get("data", {})
    feeds = data.get(lang) or next(iter(data.values()), {})
    for f in feeds.get("feeds", []):
        if f.get("name") == feed_name:
            return f.get("url")
    return None


async def fetch_vehicle_status(index_url: str) -> List[Dict[str, Any]]:
    idx = await fetch_gbfs_index(index_url)
    vehicle_url = _find_feed_url(idx, "vehicle_status") or _find_feed_url(
        idx, "free_bike_status"
    )
    if not vehicle_url:
        return []
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(vehicle_url)
        r.raise_for_status()
        payload = r.json()
    vehicles = (
        payload.get("data", {}).get("vehicles")
        or payload.get("data", {}).get("bikes")
        or []
    )
    # normalize a minimal schema
    norm = []
    for v in vehicles:
        norm.append(
            {
                "id": str(v.get("vehicle_id") or v.get("bike_id")),
                "is_electric": bool(v.get("is_electric", False)),
                "lat": v.get("lat"),
                "lon": v.get("lon"),
                "battery_pct": v.get("battery_level"),
                "is_disabled": bool(v.get("is_disabled", False)),
                "is_reserved": bool(v.get("is_reserved", False)),
            }
        )
    return norm
