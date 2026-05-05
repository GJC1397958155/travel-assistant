from __future__ import annotations

import atexit
from copy import deepcopy
import re
import sqlite3
from contextlib import ExitStack, asynccontextmanager
from dataclasses import dataclass
from datetime import date as date_cls, datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.memory import InMemoryStore
from langgraph.store.sqlite import SqliteStore

from config import TRAVEL_MEMORY_BACKEND, TRAVEL_MEMORY_DIR


SESSION_NAMESPACE = ("session_state",)
PROFILE_NAMESPACE = ("user_profile",)
DEFAULT_USER_PROFILE = {
    "preference_counts": {},
    "companions_counts": {},
    "budget_bucket_counts": {},
    "travel_style_counts": {},
    "stable_preferences": [],
    "stable_companions": [],
    "budget_range": "",
    "travel_style": "",
    "notes": [],
    "updated_at": "",
}
PREFERENCE_TAGS = ("热门", "美食", "拍照", "轻松", "亲子", "老人", "购物", "夜景", "海景")
COMPANION_PATTERNS = (
    ("亲子", "亲子"),
    ("带娃", "亲子"),
    ("孩子", "亲子"),
    ("爸妈", "老人同行"),
    ("老人", "老人同行"),
    ("情侣", "情侣"),
    ("闺蜜", "朋友同行"),
    ("朋友", "朋友同行"),
    ("家人", "家庭出游"),
    ("一个人", "独自出行"),
    ("自己", "独自出行"),
)
LONG_TERM_PREFERENCE_PATTERNS = (
    ("以后都", 2),
    ("每次都", 2),
    ("一直都", 2),
    ("通常", 1),
    ("一般都", 1),
    ("经常", 1),
)
DATE_KEYWORD_OFFSETS = {
    "今天": 0,
    "明天": 1,
    "后天": 2,
}
HOLIDAY_MONTH_DAY = {
    "五一": (5, 1),
    "十一": (10, 1),
}
CHINESE_NUMBERS = {
    "零": 0,
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
CITY_STOPWORDS = {
    "一个",
    "一下",
    "轻松",
    "紧凑",
    "美食",
    "拍照",
    "老人",
    "亲子",
    "朋友",
    "情侣",
    "夜景",
    "海景",
    "购物",
    "预算",
    "方案",
    "计划",
}


@dataclass
class MemoryRuntime:
    checkpointer: Any
    store: Any
    backend_name: str
    persistent: bool


class TravelMemoryManager:
    """Hybrid memory manager for session memory and user profiles."""

    def __init__(self, memory_dir: str, backend: str = "sqlite"):
        self.memory_dir = Path(memory_dir)
        self.backend = backend
        self._lock = Lock()
        self._stack = ExitStack()
        self.runtime = self._build_runtime()
        atexit.register(self.close)

    @property
    def checkpointer(self):
        return self.runtime.checkpointer

    @property
    def store(self):
        return self.runtime.store

    def close(self) -> None:
        with self._lock:
            self._stack.close()

    def _switch_to_memory_runtime(self) -> None:
        self._stack.close()
        self._stack = ExitStack()
        self.runtime = MemoryRuntime(
            checkpointer=InMemorySaver(),
            store=InMemoryStore(),
            backend_name="memory",
            persistent=False,
        )

    def _probe_sqlite_writable(self, *paths: str) -> None:
        for path in paths:
            conn = sqlite3.connect(path)
            try:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS __travel_assistant_probe ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, marker TEXT NOT NULL)"
                )
                conn.execute(
                    "INSERT INTO __travel_assistant_probe (marker) VALUES (?)",
                    ("ok",),
                )
                conn.execute(
                    "DELETE FROM __travel_assistant_probe "
                    "WHERE id = (SELECT MAX(id) FROM __travel_assistant_probe)"
                )
                conn.commit()
            finally:
                conn.close()

    def _checkpoint_path(self) -> str:
        return str((self.memory_dir / "short_term_memory.sqlite").resolve())

    def _store_path(self) -> str:
        return str((self.memory_dir / "long_term_memory.sqlite").resolve())

    @asynccontextmanager
    async def async_agent_checkpointer(self):
        if self.runtime.backend_name == "memory":
            yield InMemorySaver()
            return

        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            checkpoint_path = self._checkpoint_path()
            self._probe_sqlite_writable(checkpoint_path)
            async with AsyncSqliteSaver.from_conn_string(checkpoint_path) as checkpointer:
                await checkpointer.setup()
                yield checkpointer
        except Exception:
            yield InMemorySaver()

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            try:
                self.checkpointer.delete_thread(session_id)
                self.store.delete(SESSION_NAMESPACE, session_id)
            except Exception:
                if self.runtime.backend_name != "memory":
                    self._switch_to_memory_runtime()
                    self.store.delete(SESSION_NAMESPACE, session_id)
                else:
                    raise

    def get_session_state(self, session_id: str) -> dict[str, Any]:
        item = self.store.get(SESSION_NAMESPACE, session_id)
        if item is None:
            return {}
        return dict(item.value)

    def update_session_state(self, session_id: str, user_input: str) -> dict[str, Any]:
        current = self.get_session_state(session_id)
        extracted = _extract_trip_facts(user_input)
        merged = {**current, **{k: v for k, v in extracted.items() if v not in (None, "", [], {})}}
        merged["updated_at"] = _now_iso()
        try:
            self.store.put(SESSION_NAMESPACE, session_id, merged)
        except Exception:
            if self.runtime.backend_name != "memory":
                self._switch_to_memory_runtime()
                self.store.put(SESSION_NAMESPACE, session_id, merged)
            else:
                raise
        return merged

    def get_user_profile(self, user_id: str) -> dict[str, Any]:
        item = self.store.get(PROFILE_NAMESPACE, user_id)
        if item is None:
            return deepcopy(DEFAULT_USER_PROFILE)
        profile = deepcopy(DEFAULT_USER_PROFILE)
        profile.update(item.value)
        return profile

    def update_user_profile(
        self,
        user_id: str,
        *,
        user_input: str,
        session_state: dict[str, Any],
    ) -> dict[str, Any]:
        profile = self.get_user_profile(user_id)
        boost = _preference_boost(user_input)

        for tag in session_state.get("preference_tags", []):
            _bump_counter(profile["preference_counts"], tag, 1 + boost)
        companions = session_state.get("companions")
        if companions:
            _bump_counter(profile["companions_counts"], companions, 1 + boost)
        budget = session_state.get("budget")
        if budget:
            bucket = _budget_bucket(int(budget))
            _bump_counter(profile["budget_bucket_counts"], bucket, 1)
        travel_style = _travel_style(session_state)
        if travel_style:
            _bump_counter(profile["travel_style_counts"], travel_style, 1 + boost)

        profile["stable_preferences"] = _stable_values(profile["preference_counts"])
        profile["stable_companions"] = _stable_values(profile["companions_counts"])
        profile["budget_range"] = _top_value(profile["budget_bucket_counts"])
        profile["travel_style"] = _top_value(profile["travel_style_counts"])
        profile["notes"] = _build_profile_notes(profile)
        profile["updated_at"] = _now_iso()
        try:
            self.store.put(PROFILE_NAMESPACE, user_id, profile)
        except Exception:
            if self.runtime.backend_name != "memory":
                self._switch_to_memory_runtime()
                self.store.put(PROFILE_NAMESPACE, user_id, profile)
            else:
                raise
        return profile

    def build_memory_context(self, session_id: str, user_id: str) -> str:
        session_state = self.get_session_state(session_id)
        user_profile = self.get_user_profile(user_id)

        lines = []
        if session_state:
            lines.append("短期旅行状态：")
            for label, key in (
                ("目的地", "city"),
                ("天数", "days"),
                ("出发日期", "date"),
                ("预算", "budget"),
                ("同行人", "companions"),
                ("节奏", "pace"),
            ):
                value = session_state.get(key)
                if value:
                    lines.append(f"- {label}：{value}")
            if session_state.get("preference_tags"):
                lines.append(f"- 本次偏好：{'、'.join(session_state['preference_tags'])}")
            if session_state.get("must_visit"):
                lines.append(f"- 想去：{'、'.join(session_state['must_visit'])}")
            if session_state.get("avoid"):
                lines.append(f"- 回避：{'、'.join(session_state['avoid'])}")

        notes = [note for note in user_profile.get("notes", []) if note]
        if notes:
            lines.append("长期用户偏好：")
            lines.extend(f"- {note}" for note in notes)

        if not lines:
            return "暂无可用记忆。"
        return "\n".join(lines)

    def _build_runtime(self) -> MemoryRuntime:
        if self.backend == "memory":
            return MemoryRuntime(
                checkpointer=InMemorySaver(),
                store=InMemoryStore(),
                backend_name="memory",
                persistent=False,
            )

        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            checkpoint_path = self._checkpoint_path()
            store_path = self._store_path()
            checkpointer = self._stack.enter_context(SqliteSaver.from_conn_string(checkpoint_path))
            store = self._stack.enter_context(SqliteStore.from_conn_string(store_path))
            checkpointer.setup()
            store.setup()
            self._probe_sqlite_writable(checkpoint_path, store_path)
            return MemoryRuntime(
                checkpointer=checkpointer,
                store=store,
                backend_name="sqlite",
                persistent=True,
            )
        except Exception:
            self._stack.close()
            self._stack = ExitStack()
            return MemoryRuntime(
                checkpointer=InMemorySaver(),
                store=InMemoryStore(),
                backend_name="memory",
                persistent=False,
            )


def _extract_trip_facts(text: str) -> dict[str, Any]:
    profile: dict[str, Any] = {}

    city = _extract_city(text)
    if city:
        profile["city"] = city

    days = _extract_days(text)
    if days:
        profile["days"] = days

    trip_date = _extract_date(text)
    if trip_date:
        profile["date"] = trip_date

    budget = _extract_budget(text)
    if budget:
        profile["budget"] = budget

    companions = _extract_companions(text)
    if companions:
        profile["companions"] = companions

    preference_tags = [tag for tag in PREFERENCE_TAGS if tag in text]
    if preference_tags:
        profile["preference_tags"] = preference_tags

    must_visit = _extract_named_items(text, ("一定要去", "必须去", "特别想去"))
    if must_visit:
        profile["must_visit"] = must_visit

    avoid = _extract_named_items(text, ("不要", "不想去", "避开", "别去"))
    if avoid:
        profile["avoid"] = avoid

    pace = _extract_pace(text)
    if pace:
        profile["pace"] = pace

    return profile


def _extract_city(text: str) -> str | None:
    patterns = (
        r"(?:去|到|在|想去|准备去|计划去|打算去)([\u4e00-\u9fffA-Za-z]{2,16})",
        r"(?:帮我|给我|请|想要|我想要)?(?:做|安排|规划|制定)?(?:一个)?([\u4e00-\u9fffA-Za-z]{2,16})\s*(?:\d+|[零一二两三四五六七八九十]+)\s*(?:天|日)",
        r"(?:^|[\s，,。；;：:])([\u4e00-\u9fffA-Za-z]{2,16})(?:旅游|旅行|行程|攻略|玩)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = re.split(r"(旅游|旅行|行程|攻略|预算|出发|同行|偏好|玩)", match.group(1), maxsplit=1)[0]
            candidate = re.sub(r"^(帮我|给我|请|想要|我想要|做个|做一个|安排|规划|制定)", "", candidate)
            candidate = candidate.strip("，,。；;：: ")
            if (
                candidate
                and not re.search(r"\d", candidate)
                and not any(stopword in candidate for stopword in CITY_STOPWORDS)
            ):
                return candidate
    return None


def _extract_days(text: str) -> int | None:
    match = re.search(r"(\d+|[零一二两三四五六七八九十]+)\s*(?:天|日)", text)
    if not match:
        return None
    token = match.group(1)
    if token.isdigit():
        return int(token)
    if token in CHINESE_NUMBERS:
        return CHINESE_NUMBERS[token]
    if token == "十":
        return 10
    if "十" in token:
        left, right = token.split("十", maxsplit=1)
        tens = CHINESE_NUMBERS.get(left, 1 if not left else None)
        units = CHINESE_NUMBERS.get(right, 0 if not right else None)
        if tens is not None and units is not None:
            return tens * 10 + units
    return None


def _extract_date(text: str) -> str | None:
    today = date_cls.today()
    for keyword, offset in DATE_KEYWORD_OFFSETS.items():
        if keyword in text:
            return (today + timedelta(days=offset)).isoformat()
    match = re.search(r"\d{4}-\d{1,2}-\d{1,2}", text)
    if match:
        year, month, day = map(int, match.group(0).split("-"))
        return date_cls(year, month, day).isoformat()
    match = re.search(r"\d{1,2}月\d{1,2}(?:日|号)", text)
    if match:
        month, day = map(int, re.findall(r"\d+", match.group(0)))
        return _resolve_month_day(month, day, today=today).isoformat()
    for holiday, (month, day) in HOLIDAY_MONTH_DAY.items():
        if holiday in text:
            return _resolve_month_day(month, day, today=today).isoformat()
    return None


def _resolve_month_day(month: int, day: int, *, today: date_cls) -> date_cls:
    target = date_cls(today.year, month, day)
    if target < today:
        target = date_cls(today.year + 1, month, day)
    return target


def _extract_budget(text: str) -> int | None:
    patterns = (
        r"(?:预算|总预算|控制在|花费|人均)\s*(\d{3,6})",
        r"(\d{3,6})\s*(?:元|块)",
        r"(\d{3,6})\s*预算",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def _extract_companions(text: str) -> str | None:
    values = [label for keyword, label in COMPANION_PATTERNS if keyword in text]
    if not values:
        return None
    return "、".join(dict.fromkeys(values))


def _extract_pace(text: str) -> str | None:
    if "轻松" in text or "慢一点" in text:
        return "轻松"
    if "紧凑" in text or "特种兵" in text:
        return "紧凑"
    return None


def _extract_named_items(text: str, prefixes: tuple[str, ...]) -> list[str]:
    results = []
    for prefix in prefixes:
        pattern = rf"{prefix}([\u4e00-\u9fffA-Za-z0-9、，, ]{{2,24}})"
        for match in re.findall(pattern, text):
            candidate = re.split(r"(但是|不过|预算|天|日|和|跟|带着)", match, maxsplit=1)[0]
            for part in re.split(r"[、，, ]+", candidate):
                part = part.strip()
                if len(part) >= 2 and part not in results:
                    results.append(part)
    return results[:5]


def _preference_boost(text: str) -> int:
    for phrase, boost in LONG_TERM_PREFERENCE_PATTERNS:
        if phrase in text:
            return boost
    return 0


def _travel_style(session_state: dict[str, Any]) -> str:
    pace = session_state.get("pace")
    if pace:
        return pace
    tags = session_state.get("preference_tags", [])
    if "轻松" in tags:
        return "轻松"
    return ""


def _budget_bucket(budget: int) -> str:
    if budget < 1500:
        return "1500以下"
    if budget < 3000:
        return "1500-3000"
    if budget < 5000:
        return "3000-5000"
    return "5000以上"


def _bump_counter(counter: dict[str, int], key: str, value: int) -> None:
    counter[key] = counter.get(key, 0) + value


def _stable_values(counter: dict[str, int], threshold: int = 2) -> list[str]:
    return [key for key, count in sorted(counter.items(), key=lambda item: item[1], reverse=True) if count >= threshold]


def _top_value(counter: dict[str, int]) -> str:
    if not counter:
        return ""
    return sorted(counter.items(), key=lambda item: item[1], reverse=True)[0][0]


def _build_profile_notes(profile: dict[str, Any]) -> list[str]:
    notes = []
    if profile.get("stable_preferences"):
        notes.append(f"常见偏好：{'、'.join(profile['stable_preferences'])}")
    if profile.get("stable_companions"):
        notes.append(f"常见同行人：{'、'.join(profile['stable_companions'])}")
    if profile.get("budget_range"):
        notes.append(f"常见预算区间：{profile['budget_range']}")
    if profile.get("travel_style"):
        notes.append(f"常见旅行节奏：{profile['travel_style']}")
    return notes


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


memory_manager = TravelMemoryManager(
    memory_dir=TRAVEL_MEMORY_DIR,
    backend=TRAVEL_MEMORY_BACKEND,
)
