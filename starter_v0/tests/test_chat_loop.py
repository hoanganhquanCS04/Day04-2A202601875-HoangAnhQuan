"""Tests for chat.run_model_tool_loop, agent.ResearchAgent and transcript writing.

A scripted fake provider replaces the network so the loop's control flow —
stop on answer, pause on clarification, cap on rounds, survive tool errors — is
verified deterministically.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import chat
from agent import ResearchAgent
from chat import (
    assistant_tool_message,
    execute_tool_call,
    json_text,
    run_model_tool_loop,
    safe_slug,
    tool_results_message,
    trim_history,
    write_transcript,
)
from providers.base import ModelResponse, ToolCall


class ScriptedProvider:
    """Returns the next canned ModelResponse for each complete() call."""

    default_model = "fake-model"

    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def complete(self, messages, tools=None, *, model=None, temperature=0.0, tool_choice=None):
        self.calls.append({
            "messages": [dict(m) for m in messages],
            "tools": tools,
            "model": model,
            "temperature": temperature,
            "tool_choice": tool_choice,
        })
        if not self._responses:
            raise AssertionError("provider called more times than the script allows")
        return self._responses.pop(0)


class ExplodingProvider:
    default_model = "fake-model"

    def complete(self, *args: Any, **kwargs: Any):
        raise RuntimeError("upstream 502")


@pytest.fixture
def loop_kwargs() -> dict[str, Any]:
    return {"tools": [], "model": None, "max_tool_rounds": 4}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def test_trim_history_keeps_the_last_n_pairs():
    history = [{"role": "user", "content": str(i)} for i in range(10)]
    assert trim_history(history, 2) == history[-4:]


def test_trim_history_window_zero_returns_nothing():
    assert trim_history([{"role": "user", "content": "a"}], 0) == []


def test_trim_history_shorter_than_window_is_unchanged():
    history = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    assert trim_history(history, 5) == history


def test_json_text_truncates_with_a_marker():
    text = json_text({"key": "x" * 500}, max_chars=50)
    assert len(text) <= 50 + len("\n...<truncated>")
    assert text.endswith("<truncated>")


def test_json_text_keeps_unicode_readable():
    assert "hôm nay" in json_text({"q": "hôm nay"})


def test_json_text_serializes_non_json_types():
    assert "Path" in json_text({"p": Path("x")}) or "x" in json_text({"p": Path("x")})


def test_safe_slug():
    assert safe_slug("v3") == "v3"
    assert safe_slug("v 3/base") == "v_3_base"


def test_assistant_tool_message_embeds_the_calls():
    message = assistant_tool_message(None, [ToolCall(name="lookup", args={"query": "AI"})])
    assert message["role"] == "assistant"
    assert "TOOL_CALLS_JSON" in message["content"]
    assert "lookup" in message["content"]


def test_tool_results_message_is_a_user_turn_with_the_payload():
    message = tool_results_message([{"tool": "lookup", "args": {}, "result": {"items": []}}])
    assert message["role"] == "user"
    assert "TOOL_RESULTS_JSON" in message["content"]


# --------------------------------------------------------------------------- #
# execute_tool_call
# --------------------------------------------------------------------------- #
def test_execute_tool_call_runs_the_registered_function():
    event = execute_tool_call(ToolCall(name="clarify", args={"question": "Của ai?", "response_type": "text"}))
    assert event["tool"] == "clarify"
    assert event["result"]["awaiting_user"] is True


def test_execute_tool_call_reports_unknown_tool_without_raising():
    event = execute_tool_call(ToolCall(name="nope", args={}))
    assert event["result"]["error"] == "unknown_tool"


def test_execute_tool_call_captures_tool_exceptions():
    event = execute_tool_call(ToolCall(name="clarify", args={"unexpected_kwarg": 1}))
    assert event["result"]["error"] == "TypeError"


# --------------------------------------------------------------------------- #
# run_model_tool_loop
# --------------------------------------------------------------------------- #
def test_loop_returns_immediately_when_the_model_answers(loop_kwargs):
    provider = ScriptedProvider([ModelResponse(text="Mình là research agent.", tool_calls=[])])
    result = run_model_tool_loop(provider=provider, messages=[{"role": "user", "content": "bạn là gì"}], **loop_kwargs)

    assert result["status"] == "answered"
    assert result["assistant_text"] == "Mình là research agent."
    assert result["rounds"][0]["tool_calls"] == []
    assert result["tool_events"] == []
    assert len(provider.calls) == 1


def test_loop_runs_a_tool_then_answers(loop_kwargs):
    provider = ScriptedProvider([
        ModelResponse(text=None, tool_calls=[ToolCall(name="format", args={"items": [{"title": "T", "url": "u"}], "template": "bullets"})]),
        ModelResponse(text="Đây là digest.", tool_calls=[]),
    ])
    result = run_model_tool_loop(provider=provider, messages=[{"role": "user", "content": "digest"}], **loop_kwargs)

    assert result["status"] == "answered"
    assert result["assistant_text"] == "Đây là digest."
    assert len(result["rounds"]) == 2
    assert result["tool_events"][0]["tool"] == "format"
    assert "markdown" in result["tool_events"][0]["result"]
    # Round 2 must see the assistant call summary and the tool results.
    round_two_messages = provider.calls[1]["messages"]
    assert "TOOL_CALLS_JSON" in round_two_messages[-2]["content"]
    assert "TOOL_RESULTS_JSON" in round_two_messages[-1]["content"]


def test_loop_pauses_on_the_clarification_flag(loop_kwargs):
    provider = ScriptedProvider([
        ModelResponse(text=None, tool_calls=[ToolCall(name="clarify", args={"question": "Của ai?", "response_type": "text"})]),
        ModelResponse(text="should never be requested", tool_calls=[]),
    ])
    result = run_model_tool_loop(provider=provider, messages=[{"role": "user", "content": "tóm tắt tweet"}], **loop_kwargs)

    assert result["status"] == "waiting_for_user"
    assert result["assistant_text"] == "Của ai?"
    assert len(provider.calls) == 1, "the loop must stop asking the model once it is waiting on the user"


def test_pause_detection_is_rename_proof(loop_kwargs, monkeypatch: pytest.MonkeyPatch):
    """The pause is keyed on the awaiting_user flag, not on the tool name."""
    monkeypatch.setitem(chat.TOOL_FUNCTIONS, "ask_anything", lambda **kwargs: {"awaiting_user": True, "question": "Chi tiết?"})
    provider = ScriptedProvider([ModelResponse(text=None, tool_calls=[ToolCall(name="ask_anything", args={})])])
    result = run_model_tool_loop(provider=provider, messages=[{"role": "user", "content": "x"}], **loop_kwargs)
    assert result["status"] == "waiting_for_user"
    assert result["assistant_text"] == "Chi tiết?"


def test_pause_falls_back_to_the_call_argument_for_the_question(loop_kwargs, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(chat.TOOL_FUNCTIONS, "ask_anything", lambda **kwargs: {"awaiting_user": True})
    provider = ScriptedProvider([ModelResponse(text=None, tool_calls=[ToolCall(name="ask_anything", args={"question": "Từ args"})])])
    result = run_model_tool_loop(provider=provider, messages=[{"role": "user", "content": "x"}], **loop_kwargs)
    assert result["assistant_text"] == "Từ args"


def test_loop_stops_at_max_tool_rounds(loop_kwargs):
    loop_kwargs["max_tool_rounds"] = 2
    call = ToolCall(name="format", args={"items": [], "template": "bullets"})
    provider = ScriptedProvider([ModelResponse(text=None, tool_calls=[call]) for _ in range(2)])
    result = run_model_tool_loop(provider=provider, messages=[{"role": "user", "content": "loop"}], **loop_kwargs)

    assert result["status"] == "max_tool_rounds"
    assert len(result["rounds"]) == 2
    assert len(provider.calls) == 2


def test_loop_keeps_going_when_a_tool_errors(loop_kwargs):
    provider = ScriptedProvider([
        ModelResponse(text=None, tool_calls=[ToolCall(name="lookup", args={"query": "AI"})]),
        ModelResponse(text="Tool lookup bị lỗi thiếu key.", tool_calls=[]),
    ])
    result = run_model_tool_loop(provider=provider, messages=[{"role": "user", "content": "tin AI"}], **loop_kwargs)

    assert result["status"] == "answered"
    assert "error" in result["tool_events"][0]["result"], "no TAVILY_API_KEY in tests, so lookup must report an error"


def test_loop_executes_every_call_in_a_parallel_round(loop_kwargs):
    provider = ScriptedProvider([
        ModelResponse(text=None, tool_calls=[
            ToolCall(name="lookup", args={"query": "AI"}),
            ToolCall(name="social_search", args={"query": "AI"}),
        ]),
        ModelResponse(text="xong", tool_calls=[]),
    ])
    result = run_model_tool_loop(provider=provider, messages=[{"role": "user", "content": "cả hai"}], **loop_kwargs)
    assert [event["tool"] for event in result["tool_events"]] == ["lookup", "social_search"]


def test_loop_does_not_mutate_the_caller_messages(loop_kwargs):
    messages = [{"role": "user", "content": "hi"}]
    provider = ScriptedProvider([
        ModelResponse(text=None, tool_calls=[ToolCall(name="format", args={"items": [], "template": "bullets"})]),
        ModelResponse(text="done", tool_calls=[]),
    ])
    run_model_tool_loop(provider=provider, messages=messages, **loop_kwargs)
    assert messages == [{"role": "user", "content": "hi"}]


def test_loop_answer_with_none_text_becomes_empty_string(loop_kwargs):
    provider = ScriptedProvider([ModelResponse(text=None, tool_calls=[])])
    result = run_model_tool_loop(provider=provider, messages=[{"role": "user", "content": "x"}], **loop_kwargs)
    assert result["assistant_text"] == ""


def test_loop_propagates_provider_errors_to_the_caller(loop_kwargs):
    with pytest.raises(RuntimeError, match="upstream 502"):
        run_model_tool_loop(provider=ExplodingProvider(), messages=[{"role": "user", "content": "x"}], **loop_kwargs)


# --------------------------------------------------------------------------- #
# ResearchAgent (used by run_eval)
# --------------------------------------------------------------------------- #
def test_agent_prepends_the_system_prompt_and_forwards_tool_choice():
    provider = ScriptedProvider([ModelResponse(text="ok", tool_calls=[])])
    agent = ResearchAgent(provider, system_prompt="SYSTEM", tools=[{"type": "function"}], model="m")
    agent.run([{"role": "user", "content": "hi"}], tool_choice="required")

    call = provider.calls[0]
    assert call["messages"][0] == {"role": "system", "content": "SYSTEM"}
    assert call["messages"][1] == {"role": "user", "content": "hi"}
    assert call["tool_choice"] == "required"
    assert call["model"] == "m"
    assert call["temperature"] == 0.0


def test_agent_executes_calls_and_collects_results():
    provider = ScriptedProvider([ModelResponse(
        text=None,
        tool_calls=[ToolCall(name="clarify", args={"question": "Của ai?", "response_type": "text"})],
    )])
    run = ResearchAgent(provider, system_prompt="S").run([{"role": "user", "content": "x"}])
    assert run.tool_calls[0].name == "clarify"
    assert run.tool_results[0]["result"]["awaiting_user"] is True


def test_agent_records_unknown_tool_instead_of_raising():
    provider = ScriptedProvider([ModelResponse(text=None, tool_calls=[ToolCall(name="ghost", args={})])])
    run = ResearchAgent(provider, system_prompt="S").run([{"role": "user", "content": "x"}])
    assert run.tool_results[0]["error"] == "unknown_tool"


def test_agent_records_tool_exception_instead_of_raising():
    provider = ScriptedProvider([ModelResponse(text=None, tool_calls=[ToolCall(name="clarify", args={"bad": 1})])])
    run = ResearchAgent(provider, system_prompt="S").run([{"role": "user", "content": "x"}])
    assert run.tool_results[0]["result"]["error"] == "TypeError"


# --------------------------------------------------------------------------- #
# transcripts
# --------------------------------------------------------------------------- #
def test_write_transcript_creates_parents_and_stamps_updated_at(tmp_path: Path):
    path = tmp_path / "nested" / "dir" / "x.transcript.json"
    transcript = {"transcript_id": "x", "turns": [{"user": "chào bạn"}]}
    write_transcript(path, transcript)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["turns"][0]["user"] == "chào bạn"
    assert saved["updated_at"]


def test_write_transcript_survives_unpaired_surrogates(tmp_path: Path):
    """Regression: a mis-decoded console turn used to kill the whole transcript."""
    path = tmp_path / "x.transcript.json"
    write_transcript(path, {"turns": [{"user": "H\udc9d Nội"}]})
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["turns"][0]["user"].endswith("Nội")


def test_write_transcript_is_idempotent_overwrite(tmp_path: Path):
    path = tmp_path / "x.transcript.json"
    write_transcript(path, {"turns": [1]})
    write_transcript(path, {"turns": [1, 2]})
    assert len(json.loads(path.read_text(encoding="utf-8"))["turns"]) == 2
