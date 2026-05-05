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

    parsed_from_text = _parse_freeform_itinerary_text(raw_text, session_state=session_state)
    if parsed_from_text is not None:
        if not itinerary.overview:
            itinerary.overview = parsed_from_text.overview
        if not itinerary.weather_summary:
            itinerary.weather_summary = parsed_from_text.weather_summary
        if not itinerary.daily_plans:
            itinerary.daily_plans = parsed_from_text.daily_plans
        if (
            not itinerary.hotel_suggestion.area
            and not itinerary.hotel_suggestion.reason
            and not itinerary.hotel_suggestion.candidates
        ):
            itinerary.hotel_suggestion = parsed_from_text.hotel_suggestion
        if not itinerary.budget_advice.level and not itinerary.budget_advice.summary:
            itinerary.budget_advice = parsed_from_text.budget_advice
        if not itinerary.alerts:
            itinerary.alerts = parsed_from_text.alerts
        if not itinerary.alternatives:
            itinerary.alternatives = parsed_from_text.alternatives

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
    parsed_from_text = _parse_freeform_itinerary_text(raw_text, session_state=session_state)
    itinerary = StructuredItinerary(
        status=status,
        destination=str(session_state.get("city", "") or ""),
        days=session_state.get("days"),
        date=str(session_state.get("date", "") or ""),
        companions=str(session_state.get("companions", "") or ""),
        travel_style=str(session_state.get("pace", "") or ""),
        budget=session_state.get("budget"),
        overview=(
            parsed_from_text.overview
            if parsed_from_text and parsed_from_text.overview
            else _compact_text(raw_text, limit=180)
        ),
        weather_summary=parsed_from_text.weather_summary if parsed_from_text else "",
        daily_plans=parsed_from_text.daily_plans if parsed_from_text and status == "ready" else [],
        hotel_suggestion=parsed_from_text.hotel_suggestion if parsed_from_text else HotelSuggestion(),
        budget_advice=parsed_from_text.budget_advice if parsed_from_text else BudgetAdvice(),
        alerts=parsed_from_text.alerts if parsed_from_text else [],
        alternatives=parsed_from_text.alternatives if parsed_from_text else [],
        raw_text=raw_text,
        follow_up_questions=missing_questions if status != "ready" else [],
    )
    if itinerary.status == "ready" and itinerary.days:
        if not itinerary.daily_plans:
            itinerary.daily_plans = _build_placeholder_day_plans(int(itinerary.days), raw_text)
    return itinerary


DAY_HEADING_RE = re.compile(r"^第\s*([0-9零〇一二两三四五六七八九十百]+)\s*天(?:\s*[:：\-]\s*|\s+)?(.*)$")
TIME_HEADING_ALIASES = {
    "morning": ("上午", "早上", "早晨", "清晨"),
    "afternoon": ("中午", "午间", "下午", "午后"),
    "evening": ("傍晚", "晚上", "夜间", "夜晚"),
}
TEXT_SECTION_ALIASES = {
    "overview": ("行程概览", "概览", "路线概览", "整体思路"),
    "weather_summary": ("天气概览", "天气提示", "天气建议", "天气"),
    "hotel": ("酒店区域建议", "住宿区域建议", "住宿建议", "酒店建议", "住哪里"),
    "budget": ("预算建议", "预算", "花费建议", "费用建议"),
    "alerts": ("注意事项", "温馨提示", "提醒", "出行提示"),
    "alternatives": ("备选方案", "替代方案", "可替代方案", "下雨方案", "plan b"),
}


def _parse_freeform_itinerary_text(
    text: str,
    *,
    session_state: dict[str, Any],
) -> StructuredItinerary | None:
    normalized_text = _normalize_freeform_text(text)
    if not normalized_text:
        return None

    lines = [_sanitize_freeform_line(line) for line in normalized_text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return None

    sections: dict[str, list[str]] = {key: [] for key in TEXT_SECTION_ALIASES}
    day_buckets: list[dict[str, Any]] = []
    current_section = "overview"
    current_day: dict[str, Any] | None = None
    current_time: str | None = None

    def flush_day() -> None:
        nonlocal current_day, current_time
        if current_day is not None:
            day_buckets.append(current_day)
        current_day = None
        current_time = None

    for line in lines:
        day_match = DAY_HEADING_RE.match(line)
        if day_match:
            flush_day()
            day_number = _parse_day_number(day_match.group(1))
            if day_number is None:
                continue
            current_day = {
                "day": day_number,
                "title": day_match.group(2).strip(),
                "morning": [],
                "afternoon": [],
                "evening": [],
                "notes": [],
            }
            current_section = "overview"
            continue

        section_match = _match_named_heading(line, TEXT_SECTION_ALIASES)
        if section_match is not None:
            flush_day()
            current_section, remainder = section_match
            if remainder:
                sections[current_section].append(remainder)
            continue

        if current_day is None:
            sections[current_section].append(line)
            continue

        time_match = _match_named_heading(line, TIME_HEADING_ALIASES)
        if time_match is not None:
            current_time, remainder = time_match
            if remainder:
                current_day[current_time].append(remainder)
            continue

        if current_time is None:
            current_day["notes"].append(line)
        else:
            current_day[current_time].append(line)

    flush_day()

    daily_plans = [_build_day_plan(bucket) for bucket in day_buckets]
    daily_plans = [plan for plan in daily_plans if plan is not None]
    if not daily_plans:
        single_day = _parse_single_day_blocks(lines, session_state=session_state)
        if single_day is not None:
            daily_plans = [single_day]

    overview_lines = _clean_text_lines(sections["overview"])
    weather_lines = _clean_text_lines(sections["weather_summary"])
    hotel_lines = _clean_text_lines(sections["hotel"])
    budget_lines = _clean_text_lines(sections["budget"])
    alert_lines = _clean_text_lines(sections["alerts"])
    alternative_lines = _clean_text_lines(sections["alternatives"])

    has_meaningful_content = any(
        (
            overview_lines,
            weather_lines,
            hotel_lines,
            budget_lines,
            alert_lines,
            alternative_lines,
            daily_plans,
        )
    )
    if not has_meaningful_content:
        return None

    return StructuredItinerary(
        status="ready",
        destination=str(session_state.get("city", "") or ""),
        days=session_state.get("days"),
        date=str(session_state.get("date", "") or ""),
        companions=str(session_state.get("companions", "") or ""),
        travel_style=str(session_state.get("pace", "") or ""),
        budget=session_state.get("budget"),
        overview=" ".join(overview_lines[:3]),
        weather_summary=" ".join(weather_lines[:2]),
        daily_plans=daily_plans,
        hotel_suggestion=_build_hotel_suggestion(hotel_lines),
        budget_advice=_build_budget_advice(budget_lines),
        alerts=alert_lines,
        alternatives=alternative_lines,
        raw_text=text,
    )


def _normalize_freeform_text(text: str) -> str:
    return (
        text.replace("<br />", "\n")
        .replace("<br/>", "\n")
        .replace("<br>", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )


def _sanitize_freeform_line(line: str) -> str:
    cleaned = line.strip()
    if not cleaned:
        return ""

    previous = None
    while cleaned and cleaned != previous:
        previous = cleaned
        cleaned = re.sub(r"^(?:#+|>+)\s*", "", cleaned)
        cleaned = re.sub(r"^(?:[-*•]+)\s*", "", cleaned)
        cleaned = re.sub(r"^\d+[.)、]\s*", "", cleaned)

    cleaned = cleaned.replace("**", "").replace("__", "").replace("`", "").strip()
    return cleaned


def _match_named_heading(
    line: str,
    alias_map: dict[str, tuple[str, ...]],
) -> tuple[str, str] | None:
    for name, aliases in alias_map.items():
        for alias in aliases:
            pattern = rf"^{re.escape(alias)}(?:\s*[:：\-]\s*|\s+)?(.*)$"
            match = re.match(pattern, line, flags=re.IGNORECASE)
            if match:
                return name, match.group(1).strip()
    return None


def _parse_day_number(value: str) -> int | None:
    token = value.strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)

    digits = {
        "零": 0,
        "〇": 0,
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
    }
    total = 0
    current = 0
    for char in token:
        if char in digits:
            current = digits[char]
            total += current
            continue
        if char == "十":
            total = max(1, total) * 10
            current = 0
            continue
        if char == "百":
            total = max(1, total) * 100
            current = 0
            continue
        return None
    return total or current or None


def _build_day_plan(bucket: dict[str, Any]) -> DayPlan | None:
    notes = _clean_text_lines(bucket.get("notes", []))
    morning_lines = _clean_text_lines(bucket.get("morning", []))
    afternoon_lines = _clean_text_lines(bucket.get("afternoon", []))
    evening_lines = _clean_text_lines(bucket.get("evening", []))

    if not morning_lines and not afternoon_lines and not evening_lines and notes:
        redistributed, remaining_notes = _redistribute_activity_notes(notes)
        morning_lines = redistributed["morning"]
        afternoon_lines = redistributed["afternoon"]
        evening_lines = redistributed["evening"]
        notes = remaining_notes

    if not any((morning_lines, afternoon_lines, evening_lines, notes, bucket.get("title"))):
        return None

    return DayPlan(
        day=bucket["day"],
        title=str(bucket.get("title", "") or ""),
        morning=_build_activity_list(morning_lines),
        afternoon=_build_activity_list(afternoon_lines),
        evening=_build_activity_list(evening_lines),
        notes=notes,
    )


def _parse_single_day_blocks(
    lines: list[str],
    *,
    session_state: dict[str, Any],
) -> DayPlan | None:
    if session_state.get("days") not in (None, 1):
        return None

    bucket = {
        "day": 1,
        "title": "",
        "morning": [],
        "afternoon": [],
        "evening": [],
        "notes": [],
    }
    current_time: str | None = None
    has_time_block = False

    for line in lines:
        section_match = _match_named_heading(line, TEXT_SECTION_ALIASES)
        if section_match is not None:
            continue

        time_match = _match_named_heading(line, TIME_HEADING_ALIASES)
        if time_match is not None:
            current_time, remainder = time_match
            has_time_block = True
            if remainder:
                bucket[current_time].append(remainder)
            continue

        if current_time is None:
            continue

        bucket[current_time].append(line)

    if not has_time_block:
        return None
    return _build_day_plan(bucket)


def _clean_text_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    for line in lines:
        compact = re.sub(r"\s+", " ", line).strip(" -•")
        if compact:
            cleaned.append(compact)
    return cleaned


def _redistribute_activity_notes(notes: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    buckets = {"morning": [], "afternoon": [], "evening": []}
    if not notes:
        return buckets, []

    slots = ("morning", "afternoon", "evening")
    limit = min(len(notes), len(slots))
    for index in range(limit):
        buckets[slots[index]].append(notes[index])
    return buckets, notes[limit:]


def _build_activity_list(lines: list[str]) -> list[Activity]:
    activities: list[Activity] = []
    for line in lines:
        for segment in _split_activity_segments(line):
            title, reason = _split_activity_reason(segment)
            if title:
                activities.append(Activity(title=title, reason=reason))
    return activities


def _split_activity_segments(line: str) -> list[str]:
    if "；" in line:
        segments = [part.strip() for part in line.split("；")]
        return [segment for segment in segments if segment]
    return [line]


def _split_activity_reason(segment: str) -> tuple[str, str]:
    cleaned = segment.strip(" ，。；")
    if not cleaned:
        return "", ""

    parenthetical = re.match(r"^(.*?)[（(]([^()（）]+)[）)]$", cleaned)
    if parenthetical:
        return parenthetical.group(1).strip(), parenthetical.group(2).strip()

    for separator in ("：", ":"):
        if separator in cleaned:
            left, right = cleaned.split(separator, maxsplit=1)
            if len(left.strip()) <= 18:
                return left.strip(), right.strip()

    dash_match = re.match(r"^(.*?)[-—](.+)$", cleaned)
    if dash_match and len(dash_match.group(1).strip()) <= 18:
        return dash_match.group(1).strip(), dash_match.group(2).strip()

    return cleaned, ""


def _build_hotel_suggestion(lines: list[str]) -> HotelSuggestion:
    if not lines:
        return HotelSuggestion()

    area = lines[0]
    reason = " ".join(lines[1:3]) if len(lines) > 1 else ""
    candidates: list[str] = []
    for line in lines[1:]:
        if any(keyword in line for keyword in ("酒店", "民宿", "客栈", "公寓")):
            candidates.append(line)

    return HotelSuggestion(area=area, reason=reason, candidates=candidates[:5])


def _build_budget_advice(lines: list[str]) -> BudgetAdvice:
    if not lines:
        return BudgetAdvice()

    summary = " ".join(lines[:3])
    level = ""
    if any(keyword in summary for keyword in ("紧张", "偏紧", "压缩")):
        level = "偏紧"
    elif any(keyword in summary for keyword in ("充足", "宽松", "舒服")):
        level = "宽松"

    return BudgetAdvice(level=level, summary=summary)


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
