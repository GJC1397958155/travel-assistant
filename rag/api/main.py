import os
import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import (
    DEFAULT_SESSION_ID,
    DEFAULT_USER_ID,
    ask_agent_with_metadata,
    build_day_route_map,
    build_agent,
    build_structured_itinerary_with_model,
    stream_agent_with_metadata,
)

app = FastAPI(title="Travel Assistant API")

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

agent = build_agent()


class ChatRequest(BaseModel):
    message: str
    session_id: str = DEFAULT_SESSION_ID
    user_id: str = DEFAULT_USER_ID


class RoutePointPayload(BaseModel):
    order: int
    label: str = ""
    title: str = ""
    location: str = ""
    time_slot: str = ""
    lng: float | None = None
    lat: float | None = None


class RouteLegPayload(BaseModel):
    from_order: int
    to_order: int
    from_label: str = ""
    to_label: str = ""
    mode: str = "walking"
    distance_text: str = ""
    duration_text: str = ""
    summary: str = ""
    polyline: str = ""


class DayRouteMapRequest(BaseModel):
    city: str = ""
    route_points: list[RoutePointPayload]
    route_legs: list[RouteLegPayload] = []


class StructuredItineraryRequest(BaseModel):
    user_input: str
    answer: str
    session_state: dict = {}


def _format_sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/chat")
def chat(req: ChatRequest):
    return ask_agent_with_metadata(
        agent,
        req.message,
        session_id=req.session_id,
        user_id=req.user_id,
    )


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    def event_stream():
        try:
            for item in stream_agent_with_metadata(
                agent,
                req.message,
                session_id=req.session_id,
                user_id=req.user_id,
            ):
                event = str(item.pop("event", "message"))
                yield _format_sse(event, item)
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


@app.post("/map/day-route")
def map_day_route(req: DayRouteMapRequest):
    return build_day_route_map(
        city=req.city,
        route_points=[
            point.model_dump() if hasattr(point, "model_dump") else point.dict()
            for point in req.route_points
        ],
        route_legs=[
            leg.model_dump() if hasattr(leg, "model_dump") else leg.dict()
            for leg in req.route_legs
        ],
    )


@app.post("/itinerary/structure")
def structure_itinerary(req: StructuredItineraryRequest):
    return build_structured_itinerary_with_model(
        req.user_input,
        req.session_state or {},
        req.answer,
    )


@app.get("/health")
def health():
    return {"status": "ok"}
