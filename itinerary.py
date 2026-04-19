from __future__ import annotations

import json
import re
from typing import Any, Optional

from pydantic import BaseModel, Field


PLANNING_KEYWORDS = (
    "行程",
    "旅行计划",
    "旅游计划",
    "攻略",
    "安排",
    "出发",
    "去哪",
    "去哪玩",
    "怎么玩",
    "怎么安排",
    "推荐路线",
    "旅游",
    "旅行",
    "trip",
    "itinerary",
)

DAY_HEADER_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:[#>*\-]+\s*)?(?:\*\*|__)?\s*"
    r"(?:第\s*([0-9一二三四五六七八九十两百]+)\s*[天日]?|day\s*(\d+)|d\s*(\d+))"
    r"\s*(?:\*\*|__)?\s*[:：\-—]?\s*([^\n]*)",
    flags=re.IGNORECASE,
)

SLOT_SECTION_PATTERN = re.compile(
    r"(上午|早上|清晨|早餐后|中午|下午|午后|傍晚|晚上|夜间|夜晚)\s*[:：\-—]?",
    flags=re.IGNORECASE,
)

CLARIFICATION_LABELS = {
    "city": "目的地",
    "days": "出行天数",
}

STRUCTURED_RESPONSE_CONTRACT = """
如果用户正在让你制定旅行方案，请按下面的自然语言结构回答：
1. 先给出“行程概览”，用 1 到 2 句话总结路线思路。
2. 再按“第X天”拆分每日安排，并尽量包含上午 / 下午 / 晚上。
3. 单独给出“酒店区域建议”“预算建议”“注意事项”“备选方案”。
4. 如果信息不足，先明确说明缺少哪些信息，并给出最多 3 个简短追问。
5. 不要输出 JSON，不要编造实时营业时间、票价或未查询到的路线时长。
""".strip()

FORMATTER_SYSTEM_PROMPT = """
你是旅行计划结构化助手。请把给定的旅行助手回复整理成严格的 JSON 对象。
规则：
1. 只能依据 user_input、session_state 和 assistant_answer 提取信息；不确定时留空，不要编造。
2. 如果信息不足以形成完整行程，status 设为 "needs_clarification"，并在 follow_up_questions 中写出需要追问的问题。
3. 如果已经形成可执行计划，status 设为 "ready"；若 days 明确，请尽量输出对应天数的 daily_plans。
4. daily_plans 中的 morning / afternoon / evening 都必须是数组，元素结构固定为 {"title": "", "location": "", "reason": ""}。
5. 输出必须是一个 JSON object，不要输出 Markdown、解释或代码块。
""".strip()

FORMATTER_SCHEMA = {
    "status": "ready",
    "destination": "",
    "days": None,
    "date": "",
    "companions": "",
    "travel_style": "",
    "budget": None,
    "overview": "",
    "weather_summary": "",
    "daily_plans": [
        {
            "day": 1,
            "title": "",
            "weather": "",
            "morning": [{"title": "", "location": "", "reason": ""}],
            "afternoon": [{"title": "", "location": "", "reason": ""}],
            "evening": [{"title": "", "location": "", "reason": ""}],
            "route_points": [
                {
                    "order": 1,
                    "label": "",
                    "title": "",
                    "location": "",
                    "time_slot": "",
                    "lng": None,
                    "lat": None,
                }
            ],
            "route_legs": [
                {
                    "from_order": 1,
                    "to_order": 2,
                    "from_label": "",
                    "to_label": "",
                    "mode": "walking",
                    "distance_text": "",
                    "duration_text": "",
                    "summary": "",
                    "polyline": "",
                }
            ],
            "transport_tip": "",
            "dining_tip": "",
            "notes": [""],
            "alternatives": [""],
        }
    ],
    "hotel_suggestion": {
        "area": "",
        "reason": "",
        "candidates": [""],
    },
    "budget_advice": {
        "level": "",
        "summary": "",
    },
    "alerts": [""],
    "alternatives": [""],
    "follow_up_questions": [""],
    "source_summary": [""],
    "raw_text": "",
}


class Activity(BaseModel):
    title: str = ""
    location: str = ""
    reason: str = ""


class RoutePoint(BaseModel):
    order: int
    label: str = ""
    title: str = ""
    location: str = ""
    time_slot: str = ""
    lng: Optional[float] = None
    lat: Optional[float] = None


class RouteLeg(BaseModel):
    from_order: int
    to_order: int
    from_label: str = ""
    to_label: str = ""
    mode: str = "walking"
    distance_text: str = ""
    duration_text: str = ""
    summary: str = ""
    polyline: str = ""


class DayPlan(BaseModel):
    day: int
    title: str = ""
    weather: str = ""
    morning: list[Activity] = Field(default_factory=list)
    afternoon: list[Activity] = Field(default_factory=list)
    evening: list[Activity] = Field(default_factory=list)
    route_points: list[RoutePoint] = Field(default_factory=list)
    route_legs: list[RouteLeg] = Field(default_factory=list)
    transport_tip: str = ""
    dining_tip: str = ""
    notes: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)


class HotelSuggestion(BaseModel):
    area: str = ""
    reason: str = ""
    candidates: list[str] = Field(default_factory=list)


class BudgetAdvice(BaseModel):
    level: str = ""
    summary: str = ""


class StructuredItinerary(BaseModel):
    status: str = "ready"
    destination: str = ""
    days: Optional[int] = None
    date: str = ""
    companions: str = ""
    travel_style: str = ""
    budget: Optional[int] = None
    overview: str = ""
    weather_summary: str = ""
    daily_plans: list[DayPlan] = Field(default_factory=list)
    hotel_suggestion: HotelSuggestion = Field(default_factory=HotelSuggestion)
    budget_advice: BudgetAdvice = Field(default_factory=BudgetAdvice)
    alerts: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    source_summary: list[str] = Field(default_factory=list)
    raw_text: str = ""


def should_generate_structured_itinerary(user_input: str, session_state: dict[str, Any]) -> bool:
    text = user_input.strip().lower()
    if not text:
        return False
    if any(keyword in text for keyword in PLANNING_KEYWORDS):
        return True
    if session_state.get("days") and any(
        session_state.get(key) for key in ("date", "budget", "companions", "preference_tags", "pace")
    ):
        return True
    return bool(session_state.get("city") and session_state.get("days"))


def build_formatter_user_prompt(
    *,
    user_input: str,
    session_state: dict[str, Any],
    assistant_answer: str,
) -> str:
    serialized_state = json.dumps(session_state, ensure_ascii=False, indent=2)
    serialized_schema = json.dumps(FORMATTER_SCHEMA, ensure_ascii=False, indent=2)
    return (
        f"user_input:\n{user_input}\n\n"
        f"session_state:\n{serialized_state}\n\n"
        f"assistant_answer:\n{assistant_answer}\n\n"
        f"请严格输出符合以下 schema 的 JSON：\n{serialized_schema}"
    )


def parse_structured_itinerary_text(
    text: str,
    *,
    session_state: dict[str, Any] | None = None,
    raw_text: str = "",
) -> StructuredItinerary | None:
    payload = _extract_json_payload(text)
    if payload is None:
        return None
    itinerary = _model_validate(StructuredItinerary, payload)
    return normalize_structured_itinerary(itinerary, session_state=session_state or {}, raw_text=raw_text)


def parse_natural_language_itinerary(
    text: str,
    *,
    session_state: dict[str, Any] | None = None,
    raw_text: str = "",
) -> StructuredItinerary | None:
    if not text.strip():
        return None

    session_state = session_state or {}
    itinerary = build_fallback_itinerary(session_state=session_state, raw_text=raw_text or text)
    itinerary.overview = _extract_overview_text(text) or itinerary.overview

    day_plans = _extract_day_plans_from_text(text)
    if not day_plans and session_state.get("days") == 1:
        single_day = _build_day_plan_from_segment(1, "第1天行程", text)
        if single_day.morning or single_day.afternoon or single_day.evening or single_day.notes:
            day_plans = [single_day]

    if day_plans:
        itinerary.status = "ready"
        itinerary.daily_plans = day_plans
        if not itinerary.days:
            itinerary.days = len(day_plans)
        itinerary.follow_up_questions = []

    return normalize_structured_itinerary(
        itinerary,
        session_state=session_state,
        raw_text=raw_text or text,
    )


def normalize_structured_itinerary(
    itinerary: StructuredItinerary,
    *,
    session_state: dict[str, Any],
    raw_text: str,
) -> StructuredItinerary:
    if not itinerary.destination:
        itinerary.destination = str(session_state.get("city", "") or "")
    if not itinerary.days:
        days = session_state.get("days")
        itinerary.days = int(days) if isinstance(days, int) else days
    if not itinerary.date:
        itinerary.date = str(session_state.get("date", "") or "")
    if not itinerary.companions:
        itinerary.companions = str(session_state.get("companions", "") or "")
    if not itinerary.travel_style:
        itinerary.travel_style = str(session_state.get("pace", "") or "")
    if itinerary.budget is None and session_state.get("budget"):
        itinerary.budget = int(session_state["budget"])
    if raw_text:
        itinerary.raw_text = raw_text

    if itinerary.days and not itinerary.daily_plans and itinerary.status == "ready":
        itinerary.daily_plans = _build_placeholder_day_plans(int(itinerary.days), raw_text)

    itinerary.daily_plans = sorted(
        [day for day in itinerary.daily_plans if day.day > 0],
        key=lambda item: item.day,
    )

    if not itinerary.follow_up_questions and itinerary.status != "ready":
        itinerary.follow_up_questions = _build_missing_info_questions(session_state)
    if itinerary.status == "ready" and itinerary.follow_up_questions:
        itinerary.follow_up_questions = []

    return itinerary


def build_fallback_itinerary(
    *,
    session_state: dict[str, Any],
    raw_text: str,
) -> StructuredItinerary:
    missing_questions = _build_missing_info_questions(session_state)
    status = (
        "ready"
        if not missing_questions and session_state.get("city") and session_state.get("days")
        else "needs_clarification"
    )
    itinerary = StructuredItinerary(
        status=status,
        destination=str(session_state.get("city", "") or ""),
        days=session_state.get("days"),
        date=str(session_state.get("date", "") or ""),
        companions=str(session_state.get("companions", "") or ""),
        travel_style=str(session_state.get("pace", "") or ""),
        budget=session_state.get("budget"),
        overview=_compact_text(raw_text, limit=180),
        raw_text=raw_text,
        follow_up_questions=missing_questions if status != "ready" else [],
    )
    if itinerary.status == "ready" and itinerary.days:
        itinerary.daily_plans = _build_placeholder_day_plans(int(itinerary.days), raw_text)
    return itinerary


def _extract_overview_text(text: str) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        return ""

    for paragraph in paragraphs:
        if not DAY_HEADER_PATTERN.search(paragraph):
            return _compact_text(paragraph, limit=180)

    return _compact_text(paragraphs[0], limit=180)


def _extract_day_plans_from_text(text: str) -> list[DayPlan]:
    matches = list(DAY_HEADER_PATTERN.finditer(text))
    if not matches:
        return []

    plans: list[DayPlan] = []
    for index, match in enumerate(matches):
        day_number = _parse_day_number(match.groups()[:3], default=index + 1)
        raw_title = _normalize_text_line(match.group(4).strip())
        title = raw_title or f"第{day_number}天行程"
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segment = text[start:end].strip()
        plans.append(_build_day_plan_from_segment(day_number, title, segment))

    return plans


def _build_day_plan_from_segment(day: int, title: str, segment: str) -> DayPlan:
    slot_aliases = {
        "morning": ("上午", "早上", "清晨", "早餐后"),
        "afternoon": ("中午", "下午", "午后"),
        "evening": ("傍晚", "晚上", "夜间", "夜晚"),
    }
    slot_items: dict[str, list[Activity]] = {
        "morning": [],
        "afternoon": [],
        "evening": [],
    }
    notes: list[str] = []
    ungrouped_candidates: list[str] = []
    current_slot: str | None = None
    slot_sections = _extract_slot_sections(segment)

    if slot_sections:
        for slot_name, content in slot_sections:
            activity_candidates = _split_activity_candidates(content)
            if activity_candidates:
                slot_items[slot_name].extend(_candidate_to_activity(item) for item in activity_candidates[:3])
        return _finalize_day_plan(
            day=day,
            title=title,
            slot_items=slot_items,
            notes=notes,
            ungrouped_candidates=ungrouped_candidates,
        )

    for raw_line in segment.splitlines():
        line = _normalize_text_line(raw_line)
        if not line:
            continue

        matched_slot = None
        for slot_name, aliases in slot_aliases.items():
            prefix = next((alias for alias in aliases if line.startswith(alias)), "")
            if prefix:
                matched_slot = slot_name
                current_slot = slot_name
                line = _normalize_text_line(line[len(prefix):])
                break

        activity_candidates = _split_activity_candidates(line)
        if not activity_candidates:
            continue

        if matched_slot or current_slot:
            target_slot = matched_slot or current_slot or "morning"
            slot_items[target_slot].extend(_candidate_to_activity(item) for item in activity_candidates[:3])
            continue

        ungrouped_candidates.extend(activity_candidates[:3])

    return _finalize_day_plan(
        day=day,
        title=title,
        slot_items=slot_items,
        notes=notes,
        ungrouped_candidates=ungrouped_candidates,
    )


def _finalize_day_plan(
    *,
    day: int,
    title: str,
    slot_items: dict[str, list[Activity]],
    notes: list[str],
    ungrouped_candidates: list[str],
) -> DayPlan:
    if not any(slot_items.values()) and ungrouped_candidates:
        slots = ("morning", "afternoon", "evening")
        for index, candidate in enumerate(ungrouped_candidates[:3]):
            slot_items[slots[index]].append(_candidate_to_activity(candidate))
        notes.extend(ungrouped_candidates[3:5])
    else:
        notes.extend(ungrouped_candidates[:2])

    return DayPlan(
        day=day,
        title=title or f"第{day}天行程",
        morning=slot_items["morning"],
        afternoon=slot_items["afternoon"],
        evening=slot_items["evening"],
        notes=notes[:4],
    )


def _parse_day_number(groups: tuple[str | None, ...], *, default: int) -> int:
    for group in groups:
        if not group:
            continue
        if group.isdigit():
            return int(group)
        parsed = _parse_chinese_number(group)
        if parsed is not None:
            return parsed
    return default


def _parse_chinese_number(text: str) -> int | None:
    mapping = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
        "百": 100,
    }
    normalized = text.strip()
    if not normalized:
        return None
    if normalized.isdigit():
        return int(normalized)
    if normalized in mapping and normalized not in {"十", "百"}:
        return mapping[normalized]
    if normalized == "十":
        return 10
    if "十" in normalized:
        left, _, right = normalized.partition("十")
        tens = mapping.get(left, 1) if left else 1
        ones = mapping.get(right, 0) if right else 0
        return tens * 10 + ones
    return None


def _extract_slot_sections(segment: str) -> list[tuple[str, str]]:
    matches = list(SLOT_SECTION_PATTERN.finditer(segment))
    if not matches:
        return []

    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        slot_name = _slot_alias_to_name(match.group(1))
        if not slot_name:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(segment)
        content = _normalize_text_line(segment[start:end])
        if content:
            sections.append((slot_name, content))
    return sections


def _slot_alias_to_name(alias: str) -> str | None:
    normalized = alias.strip()
    if normalized in ("上午", "早上", "清晨", "早餐后"):
        return "morning"
    if normalized in ("中午", "下午", "午后"):
        return "afternoon"
    if normalized in ("傍晚", "晚上", "夜间", "夜晚"):
        return "evening"
    return None


def _normalize_text_line(line: str) -> str:
    cleaned = line.strip()
    cleaned = re.sub(r"^[#>\-\*\u2022\u2023\u25E6\u2043\d\.\)\(、\s]+", "", cleaned).strip()
    cleaned = re.sub(r"^(?:\*\*|__)+", "", cleaned).strip()
    cleaned = re.sub(r"(?:\*\*|__)+$", "", cleaned).strip()
    cleaned = re.sub(r"^[：:\-—，,。；;]+", "", cleaned).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned


def _split_activity_candidates(text: str) -> list[str]:
    if not text:
        return []

    normalized_text = text.replace("→", " -> ").replace("｜", "\n").replace("|", "\n")
    normalized_text = re.sub(r"(?<!\d)[1-9]\d*[\.、)]\s*", "\n", normalized_text)
    chunks = re.split(r"\n+|；|;|\s*->\s*|。(?=\S)|(?<=\))\s+(?=\S)", normalized_text)

    candidates: list[str] = []
    for chunk in chunks:
        normalized = _normalize_text_line(chunk)
        if not normalized or len(normalized) <= 1:
            continue
        candidates.append(normalized)
    return candidates


def _candidate_to_activity(text: str) -> Activity:
    normalized = _compact_text(text, limit=60)
    title = normalized
    location = normalized

    bracket_match = re.match(r"(.+?)[（(](.+)[）)]$", normalized)
    if bracket_match:
        title = _compact_text(bracket_match.group(1).strip(), limit=40)
        location = _compact_text(bracket_match.group(2).strip(), limit=40)
    elif " - " in normalized:
        left, right = normalized.split(" - ", 1)
        title = _compact_text(left.strip(), limit=40)
        location = _compact_text(right.strip(), limit=40)

    return Activity(
        title=title,
        location=location,
        reason="",
    )


def _build_missing_info_questions(session_state: dict[str, Any]) -> list[str]:
    questions = []
    for key, label in CLARIFICATION_LABELS.items():
        if not session_state.get(key):
            questions.append(f"请补充{label}")
    return questions[:3]


def _build_placeholder_day_plans(days: int, raw_text: str) -> list[DayPlan]:
    excerpt = _compact_text(raw_text, limit=80)
    plans = []
    for day in range(1, max(1, days) + 1):
        notes: list[str] = []
        if day == 1 and excerpt:
            notes.append(f"可结合自然语言回答补充细节：{excerpt}")
        plans.append(DayPlan(day=day, title=f"第{day}天行程", notes=notes))
    return plans


def _compact_text(text: str, *, limit: int) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def _extract_json_payload(text: str) -> dict[str, Any] | None:
    candidate = _extract_fenced_json(text)
    if candidate is None:
        candidate = _extract_first_json_object(text)
    if candidate is None:
        return None
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _extract_fenced_json(text: str) -> str | None:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _model_validate(model_cls: type[BaseModel], payload: dict[str, Any]) -> Any:
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(payload)
    return model_cls.parse_obj(payload)
