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
)

CLARIFICATION_LABELS = {
    "city": "目的地",
    "days": "出行天数",
}

STRUCTURED_RESPONSE_CONTRACT = """
如果用户正在让你制定旅行方案，请按下面的自然语言结构回答：
1. 先给出“行程概览”，用 1 到 2 句话总结适合这次出行的路线思路。
2. 再按“第X天”拆分每日安排，并尽量包含上午 / 下午 / 晚上。
3. 单独给出“酒店区域建议”“预算建议”“注意事项”“备选方案”。
4. 如果信息不足，先明确指出缺少哪些信息，并给出最多 3 个简短追问。
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


class DayPlan(BaseModel):
    day: int
    title: str = ""
    weather: str = ""
    morning: list[Activity] = Field(default_factory=list)
    afternoon: list[Activity] = Field(default_factory=list)
    evening: list[Activity] = Field(default_factory=list)
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
    text = user_input.strip()
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
