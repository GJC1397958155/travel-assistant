import json
import os

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


@app.get("/health")
def health():
    return {"status": "ok"}
