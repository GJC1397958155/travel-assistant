from __future__ import annotations

import argparse
import json
import sys
from datetime import date as date_cls, timedelta
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from itinerary import build_fallback_itinerary, should_generate_structured_itinerary
from state import _extract_trip_facts, memory_manager


CASES_PATH = Path(__file__).with_name("regression_cases.json")


def load_cases() -> list[dict[str, Any]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def filter_cases(cases: list[dict[str, Any]], case_filter: str) -> list[dict[str, Any]]:
    if not case_filter:
        return cases
    keyword = case_filter.strip().lower()
    return [case for case in cases if keyword in case["id"].lower()]


def compare_subset(actual: dict[str, Any], expected: dict[str, Any], prefix: str) -> list[str]:
    errors = []
    for key, expected_value in expected.items():
        expected_value = resolve_expected_value(expected_value)
        actual_value = actual.get(key)
        if actual_value != expected_value:
            errors.append(f"{prefix}.{key}: expected {expected_value!r}, got {actual_value!r}")
    return errors


def resolve_expected_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if value.startswith("__TODAY_PLUS__:"):
        offset = int(value.split(":", maxsplit=1)[1])
        return (date_cls.today() + timedelta(days=offset)).isoformat()
    if value.startswith("__NEXT_MM_DD__:"):
        month_day = value.split(":", maxsplit=1)[1]
        month, day = map(int, month_day.split("-"))
        today = date_cls.today()
        target = date_cls(today.year, month, day)
        if target < today:
            target = date_cls(today.year + 1, month, day)
        return target.isoformat()
    return value


def check_itinerary(case: dict[str, Any], itinerary: dict[str, Any] | None) -> list[str]:
    errors = []
    expect_structured = case.get("expect_structured", False)
    if expect_structured and itinerary is None:
        return ["structured_itinerary: expected a structured result, got None"]
    if not expect_structured and itinerary is not None:
        return ["structured_itinerary: expected None, got a structured result"]
    if not expect_structured:
        return errors

    expected_itinerary = case.get("expected_itinerary", {})
    errors.extend(compare_subset(itinerary or {}, expected_itinerary, "itinerary"))

    if not itinerary:
        return errors

    if itinerary.get("status") == "ready":
        days = itinerary.get("days")
        daily_plans = itinerary.get("daily_plans", [])
        if days and len(daily_plans) < int(days):
            errors.append(
                f"itinerary.daily_plans: expected at least {days} entries for a ready itinerary, got {len(daily_plans)}"
            )
    else:
        follow_ups = itinerary.get("follow_up_questions", [])
        if not follow_ups:
            errors.append("itinerary.follow_up_questions: expected clarification questions for non-ready itinerary")

    return errors


def run_offline_case(case: dict[str, Any]) -> list[str]:
    errors = []
    extracted = _extract_trip_facts(case["user_input"])
    errors.extend(compare_subset(extracted, case.get("expected_session_state", {}), "session_state"))

    should_structure = should_generate_structured_itinerary(case["user_input"], extracted)
    if should_structure != case.get("expect_structured", False):
        errors.append(
            f"should_generate_structured_itinerary: expected {case.get('expect_structured', False)!r}, got {should_structure!r}"
        )

    structured = None
    if case.get("expect_structured", False):
        structured = build_fallback_itinerary(
            session_state=extracted,
            raw_text="这是回归测试的占位回答，用于验证结构化行程 schema。",
        )
    errors.extend(check_itinerary(case, model_dump(structured) if structured else None))
    return errors


def run_live_case(case: dict[str, Any], agent) -> list[str]:
    from app import ask_agent_with_metadata

    errors = []
    session_id = f"regression-{case['id']}"
    user_id = f"regression-user-{case['id']}"
    try:
        memory_manager.clear_session(session_id)
    except Exception:
        pass

    result = ask_agent_with_metadata(
        agent,
        case["user_input"],
        session_id=session_id,
        user_id=user_id,
    )
    errors.extend(compare_subset(result.get("session_state", {}), case.get("expected_session_state", {}), "session_state"))
    errors.extend(check_itinerary(case, result.get("structured_itinerary")))
    if not result.get("answer", "").strip():
        errors.append("answer: expected non-empty natural language answer")
    return errors


def model_dump(model: Any) -> dict[str, Any]:
    if model is None:
        return {}
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run regression checks for the travel assistant.")
    parser.add_argument("--live", action="store_true", help="Run live end-to-end checks with the configured model and APIs.")
    parser.add_argument("--case", default="", help="Only run cases whose id contains this keyword.")
    args = parser.parse_args()

    cases = filter_cases(load_cases(), args.case)
    if not cases:
        print("No regression cases matched the current filter.")
        return 1

    agent = None
    if args.live:
        from app import build_agent

        agent = build_agent()

    failures = 0
    for case in cases:
        errors = run_live_case(case, agent) if args.live else run_offline_case(case)
        if errors:
            failures += 1
            print(f"[FAIL] {case['id']}")
            for error in errors:
                print(f"  - {error}")
        else:
            mode = "live" if args.live else "offline"
            print(f"[PASS] {case['id']} ({mode})")

    total = len(cases)
    passed = total - failures
    print(f"\nSummary: {passed}/{total} cases passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
