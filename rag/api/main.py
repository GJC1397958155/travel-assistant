from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import (
    DEFAULT_SESSION_ID,
    DEFAULT_USER_ID,
    ask_agent_with_metadata,
    build_agent,
    stream_agent_with_metadata,
)
from state import memory_manager
from tools.amap_base import amap_request


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with memory_manager.async_agent_checkpointer() as checkpointer:
        app.state.agent = await build_agent(checkpointer=checkpointer)
        yield


app = FastAPI(title="Travel Assistant API", lifespan=lifespan)

cors_allow_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    session_id: str = DEFAULT_SESSION_ID
    user_id: str = DEFAULT_USER_ID


class RoutePoint(BaseModel):
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    lng: Optional[float] = None
    lat: Optional[float] = None


class MapRouteRequest(BaseModel):
    origin: RoutePoint
    destination: RoutePoint
    city: str = ""
    mode: str = "walking"


ROUTE_MODE_TO_PATH = {
    "walking": "/v3/direction/walking",
    "driving": "/v3/direction/driving",
    "transit": "/v3/direction/transit/integrated",
}


def _parse_polyline(polyline: str) -> list[list[float]]:
    points: list[list[float]] = []
    for pair in str(polyline or "").split(";"):
        parts = [part.strip() for part in pair.split(",")]
        if len(parts) < 2:
            continue
        try:
            points.append([float(parts[0]), float(parts[1])])
        except ValueError:
            continue
    return points


def _append_unique_points(target: list[list[float]], points: list[list[float]]) -> None:
    for point in points:
        if not target or target[-1] != point:
            target.append(point)


def _safe_optional_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_walk_drive_route(route_data: dict) -> tuple[list[list[float]], Optional[float], Optional[float]]:
    route = route_data.get("route", {})
    paths = route.get("paths", []) or []
    if not paths:
        return [], None, None

    best = paths[0]
    path_points: list[list[float]] = []
    for step in best.get("steps", []) or []:
        _append_unique_points(path_points, _parse_polyline(step.get("polyline", "")))

    if not path_points:
        _append_unique_points(path_points, _parse_polyline(best.get("polyline", "")))

    distance = _safe_optional_float(best.get("distance"))
    duration = _safe_optional_float(best.get("duration"))
    return path_points, distance, duration


def _extract_transit_route(route_data: dict) -> tuple[list[list[float]], Optional[float], Optional[float]]:
    route = route_data.get("route", {})
    transits = route.get("transits", []) or []
    if not transits:
        return [], None, None

    best = transits[0]
    path_points: list[list[float]] = []
    for segment in best.get("segments", []) or []:
        walking = segment.get("walking", {}) or {}
        for step in walking.get("steps", []) or []:
            _append_unique_points(path_points, _parse_polyline(step.get("polyline", "")))

        bus = segment.get("bus", {}) or {}
        for busline in bus.get("buslines", []) or []:
            _append_unique_points(path_points, _parse_polyline(busline.get("polyline", "")))

        railway = segment.get("railway", {}) or {}
        if railway.get("departure_stop") and railway.get("arrival_stop"):
            departure_location = railway.get("departure_stop", {}).get("location", "")
            arrival_location = railway.get("arrival_stop", {}).get("location", "")
            _append_unique_points(path_points, _parse_polyline(f"{departure_location};{arrival_location}"))

    distance = _safe_optional_float(best.get("distance"))
    duration = _safe_optional_float(best.get("duration"))
    return path_points, distance, duration


def _fallback_path(origin: RoutePoint, destination: RoutePoint) -> list[list[float]]:
    origin_longitude, origin_latitude = _resolve_route_point(origin)
    destination_longitude, destination_latitude = _resolve_route_point(destination)
    return [
        [origin_longitude, origin_latitude],
        [destination_longitude, destination_latitude],
    ]


def _resolve_route_point(point: RoutePoint) -> tuple[float, float]:
    longitude = point.longitude if point.longitude is not None else point.lng
    latitude = point.latitude if point.latitude is not None else point.lat
    if longitude is None or latitude is None:
        raise ValueError("地图路线接口缺少坐标字段，请提供 longitude/latitude 或 lng/lat。")
    return float(longitude), float(latitude)


def _format_sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/chat")
async def chat(req: ChatRequest):
    return await ask_agent_with_metadata(
        app.state.agent,
        req.message,
        session_id=req.session_id,
        user_id=req.user_id,
    )


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    async def event_stream():
        yield _format_sse("status", {"stage": "started"})
        try:
            async for item in stream_agent_with_metadata(
                app.state.agent,
                req.message,
                session_id=req.session_id,
                user_id=req.user_id,
            ):
                body = dict(item)
                event = str(body.pop("event", "message"))
                yield _format_sse(event, body)
        except Exception as exc:
            yield _format_sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/map/route")
def map_route(req: MapRouteRequest):
    mode = req.mode.strip().lower() or "walking"
    if mode not in ROUTE_MODE_TO_PATH:
        mode = "walking"

    origin_longitude, origin_latitude = _resolve_route_point(req.origin)
    destination_longitude, destination_latitude = _resolve_route_point(req.destination)

    params = {
        "origin": f"{origin_longitude},{origin_latitude}",
        "destination": f"{destination_longitude},{destination_latitude}",
    }
    if mode == "transit" and req.city.strip():
        params["city"] = req.city.strip()

    try:
        data = amap_request(ROUTE_MODE_TO_PATH[mode], params)
        if mode == "transit":
            path, distance, duration = _extract_transit_route(data)
        else:
            path, distance, duration = _extract_walk_drive_route(data)

        if not path:
            path = _fallback_path(req.origin, req.destination)
            return {
                "mode": mode,
                "path": path,
                "distance_meters": distance,
                "duration_seconds": duration,
                "fallback": True,
                "error_message": "未查询到完整路线，已使用直线补位。",
            }

        return {
            "mode": mode,
            "path": path,
            "distance_meters": distance,
            "duration_seconds": duration,
            "fallback": False,
            "error_message": "",
        }
    except Exception as exc:
        return {
            "mode": mode,
            "path": _fallback_path(req.origin, req.destination),
            "distance_meters": None,
            "duration_seconds": None,
            "fallback": True,
            "error_message": str(exc),
        }


@app.get("/health")
def health():
    return {"status": "ok"}
