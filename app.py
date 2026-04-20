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
    parse_structured_itinerary_text,
    should_generate_structured_itinerary,
)
from prompts import SYSTEM_PROMPT
from state import memory_manager
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


def build_structured_itinerary_with_model(
    user_input: str,
    session_state: dict,
    answer: str,
) -> dict:
    fallback = build_fallback_itinerary(session_state=session_state, raw_text=answer)

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
            return _model_dump(fallback)
        return _model_dump(structured)
    except Exception:
        return _model_dump(fallback)


def _prepare_agent_request(
    user_input: str,
    *,
    session_id: str,
    user_id: str,
) -> tuple[dict, str, bool, str]:
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
) -> dict:
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
) -> Iterator[dict]:
    session_state, memory_context, structured_requested, response_contract = _prepare_agent_request(
        user_input,
        session_id=session_id,
        user_id=user_id,
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
