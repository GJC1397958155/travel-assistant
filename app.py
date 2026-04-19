import sys
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
    parse_natural_language_itinerary,
    parse_structured_itinerary_text,
    should_generate_structured_itinerary,
)
from prompts import SYSTEM_PROMPT
from state import memory_manager
from tools.amap_geo_tool import geocode_address, reverse_geocode
from tools.amap_hotel_tool import search_hotels
from tools.amap_nearby_tool import search_nearby_pois
from tools.amap_poi_tool import search_pois
from tools.amap_route_tool import geocode_location, parse_location_text, plan_route, plan_route_structured
from tools.budget_tool import estimate_budget
from tools.rag_tool import search_travel_knowledge
from tools.weather_tool import get_weather


DEFAULT_SESSION_ID = "default"
DEFAULT_USER_ID = "default_user"
MAX_SHORT_TERM_MESSAGES = 12
MAX_ROUTE_POINTS_PER_DAY = 4
MAX_ROUTE_LEGS_TOTAL = 6
SYSTEM_PROMPT_WITH_GUARDRAILS = (
    SYSTEM_PROMPT
    + "\n\n"
    + "补充规则：当某个工具缺少数据时，只说明该工具或该数据源缺失。"
    + "不要把局部缺数概括成所有工具都不可用。"
    + "如果天气工具返回了正常结果，就不要说天气不可用。"
    + "如果没有拿到天气工具的结果，不要自行推断某年某月某日的天气，也不要编造气候统计。"
)


class TravelAgentState(AgentState):
    memory_context: NotRequired[str]
    response_contract: NotRequired[str]


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def _normalize_answer_text(text: str) -> str:
    return (
        text.replace("<br />", "\n")
        .replace("<br/>", "\n")
        .replace("<br>", "\n")
    )


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
        "处理“今天”“明天”“后天”“4月14日”这类相对或省略年份的日期时，"
        "请一律以这个日期为基准理解，并在回答中优先使用完整日期。"
    )


def _pre_model_hook(state: TravelAgentState) -> dict:
    messages = list(state.get("messages", []))
    short_window = messages[-MAX_SHORT_TERM_MESSAGES:]
    memory_context = state.get("memory_context", "")
    response_contract = state.get("response_contract", "")
    prompt_text = SYSTEM_PROMPT_WITH_GUARDRAILS + "\n\n" + _current_date_context()
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


def _model_dump(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _normalize_route_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _extract_day_route_points(day_plan: dict[str, Any]) -> list[dict[str, Any]]:
    route_points: list[dict[str, Any]] = []
    time_slots = (
        ("morning", "上午"),
        ("afternoon", "下午"),
        ("evening", "晚上"),
    )

    for slot_key, slot_label in time_slots:
        activities = day_plan.get(slot_key, []) or []
        for activity in activities:
            if not isinstance(activity, dict):
                continue

            title = _normalize_route_text(activity.get("title"))
            location = _normalize_route_text(activity.get("location"))
            label = location or title
            if not label or label == "待补充安排":
                continue

            if route_points and route_points[-1]["label"] == label:
                continue

            route_points.append(
                {
                    "order": len(route_points) + 1,
                    "label": label,
                    "title": title,
                    "location": location,
                    "time_slot": slot_label,
                    "lng": None,
                    "lat": None,
                    "_location_text": "",
                }
            )
            if len(route_points) >= MAX_ROUTE_POINTS_PER_DAY:
                return route_points

    return route_points


def _is_long_transfer_point(point: dict[str, Any]) -> bool:
    label = _normalize_route_text(point.get("label") or point.get("location") or point.get("title")).lower()
    keywords = ("机场", "高铁", "火车站", "码头", "客运站", "north station", "airport", "railway")
    return any(keyword in label for keyword in keywords)


def _choose_route_mode(origin_point: dict[str, Any], destination_point: dict[str, Any]) -> str:
    if _is_long_transfer_point(origin_point) or _is_long_transfer_point(destination_point):
        return "driving"

    origin_slot = _normalize_route_text(origin_point.get("time_slot"))
    destination_slot = _normalize_route_text(destination_point.get("time_slot"))
    if origin_slot and destination_slot and origin_slot != destination_slot:
        return "transit"

    return "walking"


def _default_duration_text(mode: str) -> str:
    if mode == "driving":
        return "约 15-35 分钟"
    if mode == "transit":
        return "约 20-45 分钟"
    return "约 10-25 分钟"


def _default_distance_text(mode: str) -> str:
    if mode == "driving":
        return "建议打车接驳"
    if mode == "transit":
        return "建议跨片区换乘"
    return "建议同片区步行"


def _build_route_summary(origin_label: str, destination_label: str, mode: str) -> str:
    if mode == "driving":
        return f"{origin_label} -> {destination_label}，建议优先打车前往，减少换乘和找路成本。"
    if mode == "transit":
        return f"{origin_label} -> {destination_label}，建议优先乘地铁/公交，必要时可改打车。"
    return f"{origin_label} -> {destination_label}，建议步行衔接，顺路浏览沿线街区。"


def _build_route_leg(
    origin_point: dict[str, Any],
    destination_point: dict[str, Any],
) -> dict[str, Any]:
    preferred_mode = _choose_route_mode(origin_point, destination_point)
    origin_label = str(origin_point.get("label") or origin_point.get("location") or origin_point.get("title"))
    destination_label = str(
        destination_point.get("label")
        or destination_point.get("location")
        or destination_point.get("title")
    )

    return {
        "from_order": origin_point["order"],
        "to_order": destination_point["order"],
        "from_label": origin_label,
        "to_label": destination_label,
        "mode": preferred_mode,
        "distance_text": _default_distance_text(preferred_mode),
        "duration_text": _default_duration_text(preferred_mode),
        "summary": _build_route_summary(origin_label, destination_label, preferred_mode),
        "polyline": "",
    }


def _serialize_route_point(point: dict[str, Any]) -> dict[str, Any]:
    return {
        "order": point.get("order"),
        "label": point.get("label", ""),
        "title": point.get("title", ""),
        "location": point.get("location", ""),
        "time_slot": point.get("time_slot", ""),
        "lng": point.get("lng"),
        "lat": point.get("lat"),
    }


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _display_route_label(point: dict[str, Any]) -> str:
    label = _normalize_route_text(point.get("label") or point.get("location") or point.get("title"))
    if label:
        return label
    order = point.get("order")
    return f"第 {order} 站" if order else "路线点"


def _prepare_map_route_points(route_points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared_points: list[dict[str, Any]] = []

    for index, raw_point in enumerate(route_points[:MAX_ROUTE_POINTS_PER_DAY]):
        if not isinstance(raw_point, dict):
            continue

        prepared_points.append(
            {
                "order": int(raw_point.get("order") or index + 1),
                "label": _display_route_label(raw_point),
                "title": _normalize_route_text(raw_point.get("title")),
                "location": _normalize_route_text(raw_point.get("location")),
                "time_slot": _normalize_route_text(raw_point.get("time_slot")),
                "lng": _safe_float(raw_point.get("lng")),
                "lat": _safe_float(raw_point.get("lat")),
                "_location_text": "",
            }
        )

    return prepared_points


def _hydrate_map_route_point(
    point: dict[str, Any],
    *,
    city: str,
    geocode_cache: dict[tuple[str, str], str],
) -> None:
    if point.get("lng") is not None and point.get("lat") is not None:
        return

    query = _normalize_route_text(point.get("location") or point.get("label") or point.get("title"))
    if not query:
        return

    cache_key = (city, query)
    if cache_key not in geocode_cache:
        try:
            geocode_cache[cache_key] = geocode_location(query, city)
        except Exception:
            geocode_cache[cache_key] = ""

    location_text = geocode_cache[cache_key]
    if not location_text:
        return

    lng, lat = parse_location_text(location_text)
    if lng is None or lat is None:
        return

    point["_location_text"] = location_text
    point["lng"] = lng
    point["lat"] = lat


def _parse_polyline_path(polyline: str) -> list[list[float]]:
    path: list[list[float]] = []
    if not polyline:
        return path

    for point_text in polyline.split(";"):
        try:
            lng_text, lat_text = point_text.split(",", 1)
            path.append([float(lng_text), float(lat_text)])
        except (TypeError, ValueError):
            continue

    return path


def _build_fallback_leg_path(origin_point: dict[str, Any], destination_point: dict[str, Any]) -> list[list[float]]:
    origin_lng = origin_point.get("lng")
    origin_lat = origin_point.get("lat")
    destination_lng = destination_point.get("lng")
    destination_lat = destination_point.get("lat")
    if None in (origin_lng, origin_lat, destination_lng, destination_lat):
        return []
    return [
        [float(origin_lng), float(origin_lat)],
        [float(destination_lng), float(destination_lat)],
    ]


def _serialize_map_route_leg(
    *,
    leg_payload: dict[str, Any],
    path: list[list[float]],
    error: str = "",
) -> dict[str, Any]:
    return {
        "from_order": leg_payload.get("from_order"),
        "to_order": leg_payload.get("to_order"),
        "from_label": leg_payload.get("from_label", ""),
        "to_label": leg_payload.get("to_label", ""),
        "mode": leg_payload.get("mode", "walking"),
        "mode_label": {
            "walking": "步行",
            "driving": "驾车",
            "transit": "公交/地铁",
        }.get(str(leg_payload.get("mode", "walking")), str(leg_payload.get("mode", "walking"))),
        "distance_text": leg_payload.get("distance_text", ""),
        "duration_text": leg_payload.get("duration_text", ""),
        "summary": leg_payload.get("summary", ""),
        "polyline": leg_payload.get("polyline", ""),
        "path": path,
        "error": error,
    }


def build_day_route_map(
    *,
    city: str,
    route_points: list[dict[str, Any]],
    route_legs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_city = _normalize_route_text(city)
    prepared_points = _prepare_map_route_points(route_points)
    warnings: list[str] = []

    if not prepared_points:
        return {
            "city": normalized_city,
            "route_points": [],
            "route_legs": [],
            "warnings": ["当前没有足够的站点可用于绘制地图。"],
        }

    geocode_cache: dict[tuple[str, str], str] = {}
    for point in prepared_points:
        _hydrate_map_route_point(point, city=normalized_city, geocode_cache=geocode_cache)

    requested_legs = route_legs or []
    resolved_legs: list[dict[str, Any]] = []
    leg_count = min(max(0, len(prepared_points) - 1), MAX_ROUTE_LEGS_TOTAL)

    for index in range(leg_count):
        origin_point = prepared_points[index]
        destination_point = prepared_points[index + 1]
        requested_leg = requested_legs[index] if index < len(requested_legs) and isinstance(requested_legs[index], dict) else {}
        mode = _normalize_route_text(requested_leg.get("mode")) or _choose_route_mode(origin_point, destination_point)
        if not normalized_city and mode == "transit":
            mode = "walking"

        origin_label = _display_route_label(origin_point)
        destination_label = _display_route_label(destination_point)
        fallback_leg = {
            "from_order": origin_point["order"],
            "to_order": destination_point["order"],
            "from_label": origin_label,
            "to_label": destination_label,
            "mode": mode,
            "distance_text": _normalize_route_text(requested_leg.get("distance_text")) or _default_distance_text(mode),
            "duration_text": _normalize_route_text(requested_leg.get("duration_text")) or _default_duration_text(mode),
            "summary": _normalize_route_text(requested_leg.get("summary")) or _build_route_summary(origin_label, destination_label, mode),
            "polyline": "",
        }

        result = plan_route_structured(
            origin=origin_label,
            destination=destination_label,
            city=normalized_city,
            mode=mode,
            origin_location=origin_point.get("_location_text") or None,
            destination_location=destination_point.get("_location_text") or None,
        )
        if result.get("ok"):
            if result.get("origin_location"):
                origin_point["_location_text"] = result["origin_location"]
            if result.get("destination_location"):
                destination_point["_location_text"] = result["destination_location"]
            if result.get("origin_lng") is not None and result.get("origin_lat") is not None:
                origin_point["lng"] = result["origin_lng"]
                origin_point["lat"] = result["origin_lat"]
            if result.get("destination_lng") is not None and result.get("destination_lat") is not None:
                destination_point["lng"] = result["destination_lng"]
                destination_point["lat"] = result["destination_lat"]

            resolved_legs.append(
                _serialize_map_route_leg(
                    leg_payload={
                        **fallback_leg,
                        "mode": result.get("mode", mode),
                        "distance_text": result.get("distance_text", fallback_leg["distance_text"]),
                        "duration_text": result.get("duration_text", fallback_leg["duration_text"]),
                        "summary": result.get("summary", fallback_leg["summary"]),
                        "polyline": result.get("polyline", ""),
                    },
                    path=_parse_polyline_path(str(result.get("polyline", "")))
                    or _build_fallback_leg_path(origin_point, destination_point),
                )
            )
            continue

        warnings.append(str(result.get("error", f"{origin_label} 到 {destination_label} 的地图路线获取失败。")))
        resolved_legs.append(
            _serialize_map_route_leg(
                leg_payload=fallback_leg,
                path=_build_fallback_leg_path(origin_point, destination_point),
                error=str(result.get("error", "")),
            )
        )

    return {
        "city": normalized_city,
        "route_points": [_serialize_route_point(point) for point in prepared_points],
        "route_legs": resolved_legs,
        "warnings": warnings[:6],
    }


def _enrich_structured_itinerary_routes(
    itinerary_payload: dict[str, Any],
    *,
    session_state: dict[str, Any],
) -> dict[str, Any]:
    if itinerary_payload.get("status") != "ready":
        return itinerary_payload

    daily_plans = itinerary_payload.get("daily_plans")
    if not isinstance(daily_plans, list):
        return itinerary_payload

    remaining_leg_budget = MAX_ROUTE_LEGS_TOTAL

    for day_plan in daily_plans:
        if not isinstance(day_plan, dict):
            continue

        route_points = _extract_day_route_points(day_plan)

        route_legs: list[dict[str, Any]] = []
        max_legs_for_day = min(max(0, len(route_points) - 1), remaining_leg_budget)
        for index in range(max_legs_for_day):
            route_legs.append(_build_route_leg(route_points[index], route_points[index + 1]))
        remaining_leg_budget -= len(route_legs)

        day_plan["route_points"] = [_serialize_route_point(point) for point in route_points]
        day_plan["route_legs"] = route_legs

    return itinerary_payload


def _build_structured_itinerary_local(
    user_input: str,
    session_state: dict[str, Any],
    answer: str,
) -> dict[str, Any]:
    fallback = build_fallback_itinerary(session_state=session_state, raw_text=answer)
    try:
        structured = parse_structured_itinerary_text(
            answer,
            session_state=session_state,
            raw_text=answer,
        )
        if structured is None:
            structured = parse_natural_language_itinerary(
                answer,
                session_state=session_state,
                raw_text=answer,
            )
        if structured is None:
            return _enrich_structured_itinerary_routes(
                _model_dump(fallback),
                session_state=session_state,
            )
        return _enrich_structured_itinerary_routes(
            _model_dump(structured),
            session_state=session_state,
        )
    except Exception:
        return _enrich_structured_itinerary_routes(
            _model_dump(fallback),
            session_state=session_state,
        )


def build_structured_itinerary_with_model(
    user_input: str,
    session_state: dict[str, Any],
    answer: str,
) -> dict[str, Any]:
    local_payload = _build_structured_itinerary_local(
        user_input,
        session_state,
        answer,
    )

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
            return local_payload
        return _enrich_structured_itinerary_routes(
            _model_dump(structured),
            session_state=session_state,
        )
    except Exception:
        return local_payload


def _prepare_agent_request(
    user_input: str,
    *,
    session_id: str,
    user_id: str,
) -> tuple[dict[str, Any], str, bool, str]:
    session_state = memory_manager.update_session_state(session_id, user_input)
    memory_context = memory_manager.build_memory_context(session_id, user_id)
    structured_requested = should_generate_structured_itinerary(user_input, session_state)
    response_contract = STRUCTURED_RESPONSE_CONTRACT if structured_requested else ""
    return session_state, memory_context, structured_requested, response_contract


def _build_agent_input(
    user_input: str,
    *,
    memory_context: str,
    response_contract: str,
) -> dict[str, Any]:
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
    structured_itinerary: Optional[dict[str, Any]],
    session_state: dict[str, Any],
) -> dict[str, Any]:
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
) -> dict[str, Any]:
    session_state, memory_context, structured_requested, response_contract = _prepare_agent_request(
        user_input,
        session_id=session_id,
        user_id=user_id,
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
        structured_itinerary = _build_structured_itinerary_local(user_input, session_state, answer)
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
) -> Iterator[dict[str, Any]]:
    session_state, memory_context, structured_requested, response_contract = _prepare_agent_request(
        user_input,
        session_id=session_id,
        user_id=user_id,
    )
    answer_parts: list[str] = []
    final_result: Optional[dict[str, Any]] = None

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
        structured_itinerary = _build_structured_itinerary_local(user_input, session_state, answer)

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
) -> str:
    return ask_agent_with_metadata(
        agent,
        user_input,
        session_id=session_id,
        user_id=user_id,
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
