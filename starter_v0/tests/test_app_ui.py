"""Tests for the Streamlit UI module.

Streamlit widgets need a script run context, so these cover the pure helpers plus
the guarantees that matter: importing app.py must not launch the UI, and it must
reuse chat.run_model_tool_loop rather than re-implementing the agent loop.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import app
import chat


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"


def test_app_reuses_the_chat_loop():
    assert app.run_model_tool_loop is chat.run_model_tool_loop


def test_app_reuses_the_transcript_writer():
    assert app.write_transcript is chat.write_transcript


def test_importing_app_does_not_run_the_ui():
    """main() must sit behind the __main__ guard, or `import app` would render."""
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    top_level_calls = [
        node for node in tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    ]
    called = {
        node.value.func.id
        for node in top_level_calls
        if isinstance(node.value.func, ast.Name)
    }
    assert "main" not in called


def test_available_versions_lists_every_snapshot_plus_current():
    options = app.available_versions()
    for name in ("v0", "v1", "v2", "v3", "v4", "v5", "current"):
        assert name in options, f"{name} should be selectable in the sidebar"
    for name, (prompt_path, tools_path) in options.items():
        assert prompt_path.is_file(), f"{name}: {prompt_path} missing"
        assert tools_path.is_file(), f"{name}: {tools_path} missing"


def test_default_version_is_the_newest_snapshot():
    assert app.default_version(app.available_versions()) == "v5"


def test_default_version_compares_numerically_not_alphabetically():
    options = {name: (Path("a"), Path("b")) for name in ("v2", "v10", "v9", "current")}
    assert app.default_version(options) == "v10"


def test_default_version_falls_back_to_current():
    assert app.default_version({"current": (Path("a"), Path("b"))}) == "current"


def test_default_version_falls_back_to_the_first_entry():
    assert app.default_version({"experimental": (Path("a"), Path("b"))}) == "experimental"


def test_new_transcript_carries_the_artifact_identity():
    prompt = ROOT / "artifacts" / "system_prompt.md"
    tools = ROOT / "artifacts" / "tools.yaml"
    transcript = app.new_transcript(
        version="v5", provider="yescale", model="gpt-4o-mini",
        prompt_path=prompt, tools_path=tools,
    )
    assert transcript["provider"] == "yescale"
    assert transcript["surface"] == "streamlit_ui"
    assert transcript["artifact_version"].startswith("v5+p")
    assert len(transcript["prompt_hash"]) == 64
    assert transcript["turns"] == []
    assert "ui" in transcript["transcript_id"]


def test_new_transcript_ids_do_not_collide():
    prompt = ROOT / "artifacts" / "system_prompt.md"
    tools = ROOT / "artifacts" / "tools.yaml"
    made = [
        app.new_transcript(version="v5", provider="yescale", model=None, prompt_path=prompt, tools_path=tools)["transcript_id"]
        for _ in range(3)
    ]
    assert len(set(made)) == 3


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({"error": "RuntimeError", "message": "boom"}, True),
        ({"items": []}, False),
        ("plain string", False),
        (None, False),
    ],
)
def test_result_is_error(result, expected: bool):
    assert app.result_is_error(result) is expected


def test_export_transcript_json_roundtrips():
    import json

    transcript = {"transcript_id": "x", "turns": [{"user": "thời tiết Hà Nội"}]}
    assert json.loads(app.export_transcript_json(transcript)) == transcript


def test_status_labels_cover_every_loop_status():
    """Any status the loop can emit must render with a label in the UI."""
    source = (ROOT / "chat.py").read_text(encoding="utf-8")
    emitted = {'"answered"', '"waiting_for_user"', '"max_tool_rounds"'}
    for literal in emitted:
        assert f'"status": {literal}' in source
        assert literal.strip('"') in app.STATUS_LABEL
    assert "provider_error" in app.STATUS_LABEL


def test_requirements_pin_streamlit():
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "streamlit" in text


# --------------------------------------------------------------------------- #
# End-to-end render, driven by Streamlit's own test harness
# --------------------------------------------------------------------------- #
from streamlit.testing.v1 import AppTest  # noqa: E402  (kept next to its users)

from providers.base import ModelResponse, ToolCall  # noqa: E402


def run_app(**kwargs):
    return AppTest.from_file(str(APP_PATH), default_timeout=90, **kwargs).run()


def test_ui_renders_without_exception():
    at = run_app()
    assert at.exception == []
    assert at.title[0].value.startswith("🔎 Research Agent")


def test_ui_defaults_to_yescale_and_the_newest_version():
    at = run_app()
    values = {box.label: box.value for box in at.sidebar.selectbox}
    assert values["Provider"] == "yescale"
    assert values["Artifact version"] == "v5"


def test_ui_shows_the_artifact_version_of_the_selected_snapshot():
    at = run_app()
    shown_current = at.sidebar.code[0].value
    assert shown_current.startswith("v5+p")

    at.sidebar.selectbox[1].set_value("v0").run()
    shown_v0 = at.sidebar.code[0].value
    assert shown_v0.startswith("v0+p")
    assert shown_v0 != shown_current, "switching version must change the displayed artifact hash"


def test_ui_lists_the_active_team_tools():
    at = run_app()
    body = " ".join(str(element.value) for element in at.sidebar.markdown)
    assert "tool được khai báo" in body
    for name in ("wikipedia", "hackernews", "crossref"):
        assert f"`{name}`" in body, f"{name} should be listed in the sidebar tool inventory"
    for retired in ("weather", "currency", "crypto"):
        assert f"`{retired}`" not in body, f"{retired} was retired at v5 and must not be offered"


def test_ui_shows_the_retired_tools_when_a_frozen_version_is_selected():
    """Selecting v0 must load that snapshot's inventory, not the live one."""
    at = run_app()
    at.sidebar.selectbox[1].set_value("v0").run()
    body = " ".join(str(element.value) for element in at.sidebar.markdown)
    for name in ("weather", "currency", "crypto"):
        assert f"`{name}`" in body
    assert "`wikipedia`" not in body


def test_ui_runs_a_full_turn_and_shows_the_tool_trace(monkeypatch: pytest.MonkeyPatch):
    """Drives the real UI: type a message, let the loop call a tool, check the render."""
    import providers

    class ScriptedProvider:
        default_model = "fake-model"

        def __init__(self) -> None:
            self._responses = [
                ModelResponse(text=None, tool_calls=[ToolCall(name="clarify", args={
                    "question": "Bạn muốn xem tweet của tài khoản nào?",
                    "response_type": "text",
                })]),
            ]

        def complete(self, messages, tools=None, **kwargs):
            return self._responses.pop(0)

    saved: list = []
    monkeypatch.setattr(providers, "make_provider", lambda name: ScriptedProvider())
    monkeypatch.setattr(chat, "write_transcript", lambda path, transcript: saved.append((path, transcript)))

    at = run_app()
    at.chat_input[0].set_value("Tóm tắt 5 tweet mới nhất giúp mình").run()

    assert at.exception == []
    rendered = " ".join(str(element.value) for element in at.markdown)
    assert "Bạn muốn xem tweet của tài khoản nào?" in rendered
    assert "clarify" in rendered, "the tool trace must name the tool that ran"

    assert saved, "a transcript must be written after every turn"
    _, transcript = saved[-1]
    turn = transcript["turns"][-1]
    assert turn["status"] == "waiting_for_user"
    assert turn["rounds"][0]["tool_calls"][0]["name"] == "clarify"
    assert turn["tool_events"][0]["result"]["awaiting_user"] is True


def test_ui_surfaces_a_provider_error_instead_of_crashing(monkeypatch: pytest.MonkeyPatch):
    import providers

    class ExplodingProvider:
        default_model = "fake-model"

        def complete(self, *args, **kwargs):
            raise RuntimeError("upstream 502")

    saved: list = []
    monkeypatch.setattr(providers, "make_provider", lambda name: ExplodingProvider())
    monkeypatch.setattr(chat, "write_transcript", lambda path, transcript: saved.append((path, transcript)))

    at = run_app()
    at.chat_input[0].set_value("Tin AI hôm nay?").run()

    assert at.exception == [], "a provider failure must be shown, not raised"
    assert any("upstream 502" in str(error.value) for error in at.error)
    assert saved[-1][1]["turns"][-1]["status"] == "provider_error"
