# backend/app/routes/recommend.py
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

from ..adapters.tfl import (
    fetch_normalized_stations,
    get_station_by_id,
    get_station_by_name,
)
from ..config import settings
from ..services.scoring import (
    best_dock_score_near_dest,
    haversine_m,
    score_station_candidate,
)

router = APIRouter(prefix="/recommend", tags=["recommend"])


async def _resolve_point(
    *,
    lat: Optional[float],
    lon: Optional[float],
    station_id: Optional[str],
    station_name_q: Optional[str],
    role: str,
) -> Tuple[float, float, Optional[str]]:
    """
    Resolve a point to (lat, lon, name_for_info) using this precedence:
    1) station_id
    2) lat/lon
    3) station_name_q (best-match by name)
    """
    # 1) By BikePoint ID
    if station_id:
        st = await get_station_by_id(station_id)
        if not st:
            raise HTTPException(404, detail=f"{role}: BikePoint ID not found")
        return float(st["lat"]), float(st["lon"]), st.get("name")

    # 2) By raw coordinates
    if lat is not None and lon is not None:
        return float(lat), float(lon), None

    # 3) By name query
    if station_name_q:
        st = await get_station_by_name(station_name_q)
        if not st:
            raise HTTPException(404, detail=f"{role}: no station matched name query")
        return float(st["lat"]), float(st["lon"]), st.get("name")

    raise HTTPException(
        400,
        detail=f"{role}: provide either station_id OR name query OR lat & lon",
    )


@router.get("")
async def recommend(
    # --- ORIGIN: choose ONE of these ways ---
    origin_station_id: str | None = Query(
        None, description="Origin BikePoint ID (e.g., BikePoints_278)"
    ),
    origin_q: str | None = Query(
        None, description="Origin station name query (e.g., 'Golden Square')"
    ),
    origin_lat: float | None = Query(
        None, description="Origin latitude (if not using station_id/name)"
    ),
    origin_lon: float | None = Query(
        None, description="Origin longitude (if not using station_id/name)"
    ),
    # --- DESTINATION influence (optional; hidden in output) ---
    dest_station_id: str | None = Query(
        None, description="Destination BikePoint ID (optional)"
    ),
    dest_q: str | None = Query(
        None, description="Destination station name query (optional)"
    ),
    dest_lat: float | None = Query(None, description="Destination latitude (optional)"),
    dest_lon: float | None = Query(
        None, description="Destination longitude (optional)"
    ),
    # misc
    limit: int = Query(3, ge=1, le=10),
) -> Dict[str, Any]:
    """
    Returns top pickup stations near the origin.
    If a destination is provided (by ID/name/coords), we use it to influence the score,
    but we do NOT include any destination fields in the output.
    """
    stations = await fetch_normalized_stations()
    if not stations:
        raise HTTPException(status_code=503, detail="No TfL station data available")

    # Resolve origin to concrete coords (fail if none provided)
    o_lat, o_lon, o_name = await _resolve_point(
        lat=origin_lat,
        lon=origin_lon,
        station_id=origin_station_id,
        station_name_q=origin_q,
        role="origin",
    )

    # Resolve destination if any; if none, fall back to origin so types are floats
    has_dest = any(
        [dest_station_id, dest_q, dest_lat is not None, dest_lon is not None]
    )
    if has_dest:
        d_lat, d_lon, _ = await _resolve_point(
            lat=dest_lat,
            lon=dest_lon,
            station_id=dest_station_id,
            station_name_q=dest_q,
            role="destination",
        )
        dest_dock_score: float = best_dock_score_near_dest(stations, d_lat, d_lon)
    else:
        d_lat, d_lon = o_lat, o_lon
        dest_dock_score = 0.0

    # Build candidate list: stations within origin radius
    candidates: list[dict[str, Any]] = []
    for s in stations:
        dist_m = haversine_m(o_lat, o_lon, s["lat"], s["lon"])
        if dist_m <= settings.ORIGIN_SEARCH_RADIUS_M and s["capacity"] > 0:
            score = score_station_candidate(
                s,
                o_lat,
                o_lon,
                d_lat,
                d_lon,
                dest_dock_score,
            )
            candidates.append(
                {
                    "station_id": s["id"],
                    "name": s["name"],
                    "lat": s["lat"],
                    "lon": s["lon"],
                    "bikes_available": s["bikes_available"],
                    "docks_available": s["docks_available"],
                    "capacity": s["capacity"],
                    "distance_m": round(dist_m, 1),
                    "score": round(score, 4),
                }
            )

    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Clean output – no destination fields shown
    return {
        "provider": "TfL / Santander Cycles",
        "origin": {"lat": o_lat, "lon": o_lon, **({"name": o_name} if o_name else {})},
        "count": min(len(candidates), limit),
        "results": candidates[:limit],
    }
