import sys
import re
from datetime import date as date_cls
from functools import lru_cache
from typing import Any, Iterator, Optional

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from typing_extensions import NotRequired

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from itinerary import (
    FORMATTER_SYSTEM_PROMPT,
    STRUCTURED_RESPONSE_CONTRACT,
    build_fallback_itinerary,
    build_formatter_user_prompt,
    parse_structured_itinerary_text,
    should_generate_structured_itinerary,
)
from prompts import SYSTEM_PROMPT
from state import memory_manager
from tools.amap_base import amap_request
from tools.amap_geo_tool import geocode_address, reverse_geocode
from tools.amap_hotel_tool import search_hotels
from tools.amap_nearby_tool import search_nearby_pois
from tools.amap_poi_tool import search_pois
from tools.amap_route_tool import plan_route
from tools.budget_tool import estimate_budget
from tools.rag_tool import search_travel_knowledge
from tools.weather_tool import get_weather


DEFAULT_SESSION_ID = "default"
DEFAULT_USER_ID = "default_user"
MAX_SHORT_TERM_MESSAGES = 12
ITINERARY_TIME_BLOCKS = ("morning", "afternoon", "evening")

GENERIC_STOP_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"酒店",
        r"早餐",
        r"午餐",
        r"晚餐",
        r"用餐",
        r"自由活动",
        r"返程",
        r"休息",
        r"入住",
        r"出发",
        r"集合",
    )
)

STOP_DECORATOR_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bcitywalk\b",
        r"打卡",
        r"漫步",
        r"散步",
        r"闲逛",
        r"赏景",
        r"看夜景",
        r"拍照",
        r"拍照点",
        r"早餐",
        r"午餐",
        r"晚餐",
        r"用餐",
        r"休息",
        r"入住",
        r"出发",
        r"返程",
    )
)


class TravelAgentState(AgentState):
    memory_context: NotRequired[str]
    response_contract: NotRequired[str]


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def _normalize_answer_text(text: str) -> str:
    return text.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")


def _build_chat_model(*, temperature: float, timeout: float) -> ChatOpenAI:
    model_kwargs = {
        "model": OPENAI_MODEL,
        "temperature": temperature,
        "http_client": httpx.Client(trust_env=False, timeout=timeout),
    }
    if OPENAI_API_KEY:
        model_kwargs["api_key"] = OPENAI_API_KEY
    if OPENAI_BASE_URL:
        model_kwargs["base_url"] = OPENAI_BASE_URL
    return ChatOpenAI(**model_kwargs)


@lru_cache(maxsize=1)
def _get_formatter_model() -> ChatOpenAI:
    return _build_chat_model(temperature=0.1, timeout=18.0)


def _current_date_context() -> str:
    today = date_cls.today().isoformat()
    return (
        f"当前系统日期：{today}。"
        "处理“今天”“明天”“后天”以及省略年份的日期时，请一律以这个日期为基准理解，"
        "并在回答中优先使用完整日期。"
    )


def _pre_model_hook(state: TravelAgentState) -> dict:
    messages = list(state.get("messages", []))
    short_window = messages[-MAX_SHORT_TERM_MESSAGES:]
    memory_context = state.get("memory_context", "")
    response_contract = state.get("response_contract", "")
    prompt_text = SYSTEM_PROMPT + "\n\n" + _current_date_context()

    if memory_context:
        prompt_text += f"\n\n你还掌握以下记忆信息：\n{memory_context}"
    if response_contract:
        prompt_text += f"\n\n本轮输出要求：\n{response_contract}"

    return {
        "llm_input_messages": [
            SystemMessage(content=prompt_text),
            *short_window,
        ]
    }


def build_agent():
    model = _build_chat_model(temperature=0.3, timeout=60.0)
    tools = [
        get_weather,
        search_pois,
        search_hotels,
        search_nearby_pois,
        geocode_address,
        reverse_geocode,
        plan_route,
        estimate_budget,
        search_travel_knowledge,
    ]

    return create_react_agent(
        model=model,
        tools=tools,
        state_schema=TravelAgentState,
        pre_model_hook=_pre_model_hook,
        checkpointer=memory_manager.checkpointer,
        store=memory_manager.store,
        version="v2",
        name="travel_assistant_agent",
    )


def _extract_ai_text(result: dict) -> str:
    messages = result.get("messages", [])
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return _normalize_answer_text(_message_content_to_text(message.content))
        if getattr(message, "type", "") == "ai":
            return _normalize_answer_text(_message_content_to_text(getattr(message, "content", "")))
    return _normalize_answer_text("No response was returned.")


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if text:
                    parts.append(str(text))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part).strip()
    return str(content)


def _model_dump(model: Any) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _parse_amap_location(value: str) -> Optional[tuple[float, float]]:
    if not value:
        return None
    parts = [part.strip() for part in str(value).split(",")]
    if len(parts) < 2:
        return None
    lng = _safe_float(parts[0])
    lat = _safe_float(parts[1])
    if lng is None or lat is None:
        return None
    return lng, lat


def _is_useful_stop_query(query: str) -> bool:
    return bool(query) and len(query) >= 2 and not any(
        pattern.search(query) for pattern in GENERIC_STOP_PATTERNS
    )


def _dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for raw_query in queries:
        query = _normalize_text(raw_query)
        if not _is_useful_stop_query(query):
            continue
        lowered = query.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(query)
    return deduped


def _strip_stop_decorators(query: str) -> str:
    cleaned = _normalize_text(query)
    cleaned = re.sub(r"[()（）【】\[\]]", " ", cleaned)
    cleaned = re.sub(r"[·•/|]", " ", cleaned)
    cleaned = re.sub(r"[，、。；;:：]", " ", cleaned)
    for pattern in STOP_DECORATOR_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    return _normalize_text(cleaned)


def _build_stop_queries(location: str, title: str) -> list[str]:
    normalized_location = _normalize_text(location)
    normalized_title = _normalize_text(title)
    clean_location = _strip_stop_decorators(normalized_location)
    clean_title = _strip_stop_decorators(normalized_title)
    return _dedupe_queries(
        [
            normalized_location,
            normalized_title,
            clean_location,
            clean_title,
            *clean_location.split(),
            *clean_title.split(),
        ]
    )


def _build_address_queries(query: str, destination: str) -> list[str]:
    clean_query = _normalize_text(query)
    clean_destination = _normalize_text(destination)
    if not clean_query:
        return []
    if not clean_destination or clean_destination in clean_query:
        return [clean_query]
    return _dedupe_queries(
        [
            f"{clean_destination}{clean_query}",
            f"{clean_destination} {clean_query}",
            clean_query,
        ]
    )


def _format_candidate_address(item: dict[str, Any]) -> str:
    address = _normalize_text(item.get("address"))
    district = _normalize_text(item.get("adname") or item.get("district"))
    city = _normalize_text(item.get("cityname") or item.get("city"))
    province = _normalize_text(item.get("pname") or item.get("province"))

    if address:
        return address

    parts: list[str] = []
    for part in (province, city, district):
        if part and part not in parts:
            parts.append(part)
    return "".join(parts)


def _poi_to_candidate(poi: dict[str, Any]) -> Optional[dict[str, Any]]:
    coordinates = _parse_amap_location(str(poi.get("location", "") or ""))
    if not coordinates:
        return None

    lng, lat = coordinates
    formatted_address = _format_candidate_address(poi)
    return {
        "name": _normalize_text(poi.get("name")),
        "formatted_address": formatted_address,
        "address": formatted_address,
        "longitude": lng,
        "latitude": lat,
        "poi_id": _normalize_text(poi.get("id")),
        "source": "poi",
    }


def _geocode_to_candidate(geocode: dict[str, Any]) -> Optional[dict[str, Any]]:
    coordinates = _parse_amap_location(str(geocode.get("location", "") or ""))
    if not coordinates:
        return None

    lng, lat = coordinates
    formatted_address = _normalize_text(geocode.get("formatted_address"))
    return {
        "name": _normalize_text(geocode.get("formatted_address")),
        "formatted_address": formatted_address,
        "address": formatted_address,
        "longitude": lng,
        "latitude": lat,
        "poi_id": "",
        "source": "geocode",
    }


def _search_poi_candidates(
    query: str,
    destination: str,
    cache: dict[tuple[str, str, str], Any],
) -> list[dict[str, Any]]:
    cache_key = ("poi", destination, query)
    if cache_key in cache:
        return cache[cache_key]

    request_params = {
        "keywords": query,
        "extensions": "base",
        "offset": 5,
        "page": 1,
    }
    if destination:
        request_params["city"] = destination
        request_params["citylimit"] = "true"

    data = amap_request("/v3/place/text", request_params)
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for poi in data.get("pois", []) or []:
        candidate = _poi_to_candidate(poi)
        if not candidate:
            continue
        unique_key = candidate["poi_id"] or f'{candidate["name"]}|{candidate["formatted_address"]}'
        if unique_key in seen:
            continue
        seen.add(unique_key)
        candidates.append(candidate)
        if len(candidates) >= 4:
            break

    cache[cache_key] = candidates
    return candidates


def _geocode_candidate(
    query: str,
    destination: str,
    cache: dict[tuple[str, str, str], Any],
) -> Optional[dict[str, Any]]:
    cache_key = ("geo", destination, query)
    if cache_key in cache:
        return cache[cache_key]

    data = amap_request(
        "/v3/geocode/geo",
        {
            "address": query,
            "city": destination,
        },
    )
    geocodes = data.get("geocodes", []) or []
    candidate = _geocode_to_candidate(geocodes[0]) if geocodes else None
    cache[cache_key] = candidate
    return candidate


def _apply_geo_candidate(
    activity: dict[str, Any],
    candidate: dict[str, Any],
    *,
    query: str,
    candidates: list[dict[str, Any]],
) -> None:
    activity["longitude"] = candidate.get("longitude")
    activity["latitude"] = candidate.get("latitude")
    activity["poi_id"] = candidate.get("poi_id", "") or ""
    activity["formatted_address"] = candidate.get("formatted_address", "") or ""
    activity["map_query"] = query
    activity["map_source"] = candidate.get("source", "")
    activity["map_candidates"] = candidates[:3]


def _enrich_activity_geo(
    activity: dict[str, Any],
    *,
    destination: str,
    cache: dict[tuple[str, str, str], Any],
) -> None:
    existing_lng = _safe_float(activity.get("longitude"))
    existing_lat = _safe_float(activity.get("latitude"))
    if existing_lng is not None and existing_lat is not None:
        activity["longitude"] = existing_lng
        activity["latitude"] = existing_lat
        activity["map_candidates"] = list(activity.get("map_candidates") or [])
        return

    queries = _build_stop_queries(
        _normalize_text(activity.get("location")),
        _normalize_text(activity.get("title")),
    )
    if not queries:
        activity["map_candidates"] = list(activity.get("map_candidates") or [])
        return

    best_candidates: list[dict[str, Any]] = []
    for query in queries[:4]:
        try:
            candidates = _search_poi_candidates(query, destination, cache)
        except Exception:
            candidates = []
        if candidates:
            best_candidates = candidates[:3]
            _apply_geo_candidate(activity, best_candidates[0], query=query, candidates=best_candidates)
            return

    address_queries = _dedupe_queries(
        [
            address_query
            for query in queries[:4]
            for address_query in _build_address_queries(query, destination)
        ]
    )
    for address_query in address_queries[:5]:
        try:
            candidate = _geocode_candidate(address_query, destination, cache)
        except Exception:
            candidate = None
        if candidate:
            _apply_geo_candidate(activity, candidate, query=address_query, candidates=best_candidates)
            return

    activity["map_candidates"] = best_candidates


def _enrich_structured_itinerary_geo(itinerary: dict[str, Any], *, session_state: dict[str, Any]) -> dict:
    if itinerary.get("status") != "ready":
        return itinerary

    destination = _normalize_text(itinerary.get("destination") or session_state.get("city"))
    cache: dict[tuple[str, str, str], Any] = {}
    daily_plans = itinerary.get("daily_plans") or []

    try:
        for day in daily_plans:
            if not isinstance(day, dict):
                continue
            for block_name in ITINERARY_TIME_BLOCKS:
                activities = day.get(block_name) or []
                if not isinstance(activities, list):
                    continue
                for activity in activities:
                    if isinstance(activity, dict):
                        _enrich_activity_geo(activity, destination=destination, cache=cache)
    except Exception:
        return itinerary

    return itinerary


def build_structured_itinerary_with_model(
    user_input: str,
    session_state: dict,
    answer: str,
) -> dict:
    fallback = build_fallback_itinerary(session_state=session_state, raw_text=answer)
    fallback_dict = _model_dump(fallback)

    try:
        formatter_prompt = build_formatter_user_prompt(
            user_input=user_input,
            session_state=session_state,
            assistant_answer=answer,
        )
        response = _get_formatter_model().invoke(
            [
                SystemMessage(content=FORMATTER_SYSTEM_PROMPT),
                HumanMessage(content=formatter_prompt),
            ]
        )
        structured = parse_structured_itinerary_text(
            _message_content_to_text(getattr(response, "content", response)),
            session_state=session_state,
            raw_text=answer,
        )
        if structured is None:
            return _enrich_structured_itinerary_geo(fallback_dict, session_state=session_state)
        return _enrich_structured_itinerary_geo(
            _model_dump(structured),
            session_state=session_state,
        )
    except Exception:
        return _enrich_structured_itinerary_geo(fallback_dict, session_state=session_state)


def _prepare_agent_request(
    user_input: str,
    *,
    session_id: str,
    user_id: str,
    client_context: str = "",
) -> tuple[dict, str, bool, str]:
    session_state = memory_manager.update_session_state(session_id, user_input)
    memory_context = memory_manager.build_memory_context(session_id, user_id)
    if client_context.strip():
        extra_context = f"前端补充上下文（用户已在界面确认）：\n{client_context.strip()}"
        memory_context = f"{memory_context}\n\n{extra_context}".strip() if memory_context else extra_context
    structured_requested = should_generate_structured_itinerary(user_input, session_state)
    response_contract = STRUCTURED_RESPONSE_CONTRACT if structured_requested else ""
    return session_state, memory_context, structured_requested, response_contract


def _build_agent_input(
    user_input: str,
    *,
    memory_context: str,
    response_contract: str,
) -> dict:
    return {
        "messages": [HumanMessage(content=user_input)],
        "memory_context": memory_context,
        "response_contract": response_contract,
    }


def _build_agent_response(
    *,
    session_id: str,
    user_id: str,
    user_input: str,
    answer: str,
    structured_itinerary: Optional[dict],
    session_state: dict,
) -> dict:
    return {
        "session_id": session_id,
        "user_id": user_id,
        "user_input": user_input,
        "answer": answer,
        "structured_itinerary": structured_itinerary,
        "session_state": session_state,
        "memory_backend": memory_manager.runtime.backend_name,
        "memory_persistent": memory_manager.runtime.persistent,
    }


def ask_agent_with_metadata(
    agent,
    user_input: str,
    *,
    session_id: str = DEFAULT_SESSION_ID,
    user_id: str = DEFAULT_USER_ID,
    client_context: str = "",
) -> dict:
    session_state, memory_context, structured_requested, response_contract = _prepare_agent_request(
        user_input,
        session_id=session_id,
        user_id=user_id,
        client_context=client_context,
    )
    result = agent.invoke(
        _build_agent_input(
            user_input,
            memory_context=memory_context,
            response_contract=response_contract,
        ),
        config={"configurable": {"thread_id": session_id}},
    )
    answer = _extract_ai_text(result)
    structured_itinerary = None
    if structured_requested:
        structured_itinerary = build_structured_itinerary_with_model(user_input, session_state, answer)
    memory_manager.update_user_profile(
        user_id,
        user_input=user_input,
        session_state=session_state,
    )
    return _build_agent_response(
        session_id=session_id,
        user_id=user_id,
        user_input=user_input,
        answer=answer,
        structured_itinerary=structured_itinerary,
        session_state=session_state,
    )


def stream_agent_with_metadata(
    agent,
    user_input: str,
    *,
    session_id: str = DEFAULT_SESSION_ID,
    user_id: str = DEFAULT_USER_ID,
    client_context: str = "",
) -> Iterator[dict]:
    session_state, memory_context, structured_requested, response_contract = _prepare_agent_request(
        user_input,
        session_id=session_id,
        user_id=user_id,
        client_context=client_context,
    )
    answer_parts: list[str] = []
    final_result: Optional[dict] = None

    for mode, data in agent.stream(
        _build_agent_input(
            user_input,
            memory_context=memory_context,
            response_contract=response_contract,
        ),
        config={"configurable": {"thread_id": session_id}},
        stream_mode=["messages", "values"],
    ):
        if mode == "messages":
            token, _metadata = data
            delta = _message_content_to_text(getattr(token, "content", ""))
            if not delta:
                continue
            answer_parts.append(delta)
            yield {"event": "token", "delta": delta}
        elif mode == "values" and isinstance(data, dict):
            final_result = data

    streamed_answer = _normalize_answer_text("".join(answer_parts))
    answer = _extract_ai_text(final_result) if final_result else streamed_answer
    if (not answer or answer == "No response was returned.") and streamed_answer:
        answer = streamed_answer

    structured_itinerary = None
    if structured_requested:
        yield {"event": "status", "stage": "structuring"}
        structured_itinerary = build_structured_itinerary_with_model(user_input, session_state, answer)

    memory_manager.update_user_profile(
        user_id,
        user_input=user_input,
        session_state=session_state,
    )
    yield {
        "event": "done",
        **_build_agent_response(
            session_id=session_id,
            user_id=user_id,
            user_input=user_input,
            answer=answer,
            structured_itinerary=structured_itinerary,
            session_state=session_state,
        ),
    }


def ask_agent(
    agent,
    user_input: str,
    *,
    session_id: str = DEFAULT_SESSION_ID,
    user_id: str = DEFAULT_USER_ID,
    client_context: str = "",
) -> str:
    return ask_agent_with_metadata(
        agent,
        user_input,
        session_id=session_id,
        user_id=user_id,
        client_context=client_context,
    )["answer"]


def main():
    agent = build_agent()
    session_id = "cli"
    user_id = "cli_user"

    print("=== 智能旅游助手已启动，输入 quit 退出，输入 /reset 清空当前会话 ===")
    while True:
        user_input = input("\n你：").strip()
        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit"}:
            break
        if user_input == "/reset":
            memory_manager.clear_session(session_id)
            print("\n助手：已清空当前会话，我们可以重新开始。")
            continue

        print(
            "\n助手：",
            ask_agent(agent, user_input, session_id=session_id, user_id=user_id),
        )


if __name__ == "__main__":
    main()
