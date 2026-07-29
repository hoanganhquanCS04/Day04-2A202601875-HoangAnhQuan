"""Streamlit UI for the Day04 Research Agent.

Run:  streamlit run app.py

Reuses `run_model_tool_loop` from chat.py so the UI and the CLI execute exactly the
same agent loop, and writes the same `transcripts/*.transcript.json` files.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from chat import (
    ROOT,
    json_text,
    now_iso,
    run_model_tool_loop,
    safe_slug,
    trim_history,
    write_transcript,
)
from env_loader import load_lab_env
from providers import PROVIDER_CHOICES, make_provider
from tools import TOOL_FUNCTIONS, load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


ARTIFACTS_DIR = ROOT / "artifacts"
VERSIONS_DIR = ARTIFACTS_DIR / "versions"
TRANSCRIPTS_DIR = ROOT / "transcripts"

load_lab_env(ROOT)


# --------------------------------------------------------------------------- #
# Artifact discovery
# --------------------------------------------------------------------------- #
def available_versions() -> dict[str, tuple[Path, Path]]:
    """Map version label -> (system_prompt path, tools path).

    "current" is always the live `artifacts/` pair; every subfolder of
    `artifacts/versions/` that holds both files is offered as a frozen snapshot.
    """
    options: dict[str, tuple[Path, Path]] = {}
    if VERSIONS_DIR.is_dir():
        for folder in sorted(VERSIONS_DIR.iterdir()):
            prompt_path = folder / "system_prompt.md"
            tools_path = folder / "tools.yaml"
            if folder.is_dir() and prompt_path.is_file() and tools_path.is_file():
                options[folder.name] = (prompt_path, tools_path)
    options["current"] = (ARTIFACTS_DIR / "system_prompt.md", ARTIFACTS_DIR / "tools.yaml")
    return options


def default_version(options: dict[str, tuple[Path, Path]]) -> str:
    """Preselect the newest vN snapshot, falling back to the live artifacts."""
    numbered = [name for name in options if name.startswith("v") and name[1:].isdigit()]
    if numbered:
        return max(numbered, key=lambda name: int(name[1:]))
    return "current" if "current" in options else next(iter(options))


# --------------------------------------------------------------------------- #
# Session state
# --------------------------------------------------------------------------- #
def new_transcript(*, version: str, provider: str, model: str | None, prompt_path: Path, tools_path: Path) -> dict[str, Any]:
    artifact_version = build_artifact_version(version, prompt_path, tools_path)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = "_".join([safe_slug(version), safe_slug(provider), "ui", timestamp])
    return {
        "transcript_id": transcript_id,
        **artifact_version_dict(artifact_version),
        "provider": provider,
        "model": model,
        "surface": "streamlit_ui",
        "system_prompt": str(prompt_path),
        "tools": str(tools_path),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }


def reset_session() -> None:
    for key in ("transcript", "messages", "history", "transcript_path"):
        st.session_state.pop(key, None)


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #
STATUS_LABEL = {
    "answered": ("✅", "Đã trả lời"),
    "waiting_for_user": ("❓", "Đang chờ bạn bổ sung thông tin"),
    "max_tool_rounds": ("⚠️", "Dừng vì chạm giới hạn số vòng tool"),
    "provider_error": ("🛑", "Lỗi provider"),
}


def result_is_error(result: Any) -> bool:
    return isinstance(result, dict) and "error" in result


def render_trace(rounds: list[dict[str, Any]]) -> None:
    """Tool trace panel: mỗi round hiển thị tên tool, args, và result/error."""
    if not rounds:
        st.caption("Không có tool call nào ở lượt này.")
        return
    for round_record in rounds:
        calls = round_record.get("tool_calls") or []
        header = f"Round {round_record.get('round')} — " + (
            ", ".join(call.get("name", "?") for call in calls) if calls else "không gọi tool"
        )
        with st.expander(header, expanded=True):
            if round_record.get("assistant_text"):
                st.markdown(f"**Assistant text:** {round_record['assistant_text']}")
            results = round_record.get("tool_results") or []
            if not results:
                st.caption("— không có tool result —")
            for event in results:
                st.markdown(f"**🔧 `{event.get('tool')}`**")
                st.caption("args")
                st.code(json_text(event.get("args", {})), language="json")
                result = event.get("result", {})
                if result_is_error(result):
                    st.caption("error")
                    st.error(json_text(result, max_chars=4000))
                else:
                    st.caption("result")
                    st.code(json_text(result, max_chars=4000), language="json")


def render_turn(turn: dict[str, Any]) -> None:
    with st.chat_message("user"):
        st.markdown(turn["user"])
    with st.chat_message("assistant"):
        if turn.get("status") == "provider_error":
            st.error(turn.get("error", "provider error"))
        else:
            st.markdown(turn.get("assistant_text") or "_(không có nội dung)_")
        icon, label = STATUS_LABEL.get(turn.get("status", ""), ("ℹ️", turn.get("status", "")))
        st.caption(f"{icon} {label}")
        with st.popover("🔎 Tool trace"):
            render_trace(turn.get("rounds") or [])


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
def main() -> None:
    st.set_page_config(page_title="Day04 Research Agent", page_icon="🔎", layout="wide")
    st.title("🔎 Research Agent — Day04 Lab")

    options = available_versions()

    with st.sidebar:
        st.header("⚙️ Cấu hình")
        provider_name = st.selectbox(
            "Provider",
            PROVIDER_CHOICES,
            index=PROVIDER_CHOICES.index("yescale") if "yescale" in PROVIDER_CHOICES else 0,
        )
        version_names = list(options)
        version = st.selectbox("Artifact version", version_names, index=version_names.index(default_version(options)))
        prompt_path, tools_path = options[version]
        model_override = st.text_input("Model (bỏ trống = mặc định của provider)", value="")
        max_tool_rounds = st.slider("Max tool rounds", min_value=1, max_value=8, value=4)
        history_window = st.slider("History window (số cặp lượt giữ lại)", min_value=1, max_value=10, value=5)

        st.divider()
        st.header("📦 Artifact")
        try:
            artifact_version = build_artifact_version(version, prompt_path, tools_path)
            declarations = load_tool_declarations(tools_path)
        except Exception as exc:  # missing/broken artifact must not blank the page
            st.error(f"Không đọc được artifact: {type(exc).__name__}: {exc}")
            st.stop()

        st.code(artifact_version.artifact_version, language="text")
        st.caption(f"prompt: `{prompt_path.relative_to(ROOT)}`")
        st.caption(f"tools: `{tools_path.relative_to(ROOT)}`")
        st.caption(f"prompt_hash: `{artifact_version.prompt_hash[:12]}`")
        st.caption(f"tools_hash: `{artifact_version.tools_hash[:12]}`")

        declared = [item["name"] for item in declarations]
        missing_impl = [name for name in declared if name not in TOOL_FUNCTIONS]
        st.markdown(f"**{len(declared)} tool được khai báo**")
        st.write(", ".join(f"`{name}`" for name in declared))
        if missing_impl:
            st.warning("Chưa có implementation: " + ", ".join(missing_impl))

        with st.expander("Xem system prompt"):
            st.markdown(prompt_path.read_text(encoding="utf-8"))

        st.divider()
        if st.button("🗑️ Xoá hội thoại / bắt đầu transcript mới", use_container_width=True):
            reset_session()
            st.rerun()

    # A change of provider/version starts a fresh transcript so one file never
    # mixes two artifact versions.
    signature = (provider_name, version, model_override)
    if st.session_state.get("signature") != signature:
        reset_session()
        st.session_state["signature"] = signature

    try:
        provider = make_provider(provider_name)
    except Exception as exc:
        st.error(f"Không khởi tạo được provider `{provider_name}`: {exc}")
        st.stop()

    selected_model = model_override.strip() or getattr(provider, "default_model", None)

    if "transcript" not in st.session_state:
        st.session_state["transcript"] = new_transcript(
            version=version,
            provider=provider_name,
            model=selected_model,
            prompt_path=prompt_path,
            tools_path=tools_path,
        )
        st.session_state["transcript_path"] = TRANSCRIPTS_DIR / f"{st.session_state['transcript']['transcript_id']}.transcript.json"
        st.session_state["history"] = []

    transcript: dict[str, Any] = st.session_state["transcript"]
    transcript_path: Path = st.session_state["transcript_path"]

    for turn in transcript["turns"]:
        render_turn(turn)

    user_text = st.chat_input("Hỏi Research Agent... (vd: Tin AI hôm nay có gì?)")
    if not user_text:
        st.caption(f"Transcript: `{transcript_path.name}` — {len(transcript['turns'])} lượt đã lưu.")
        return

    system_prompt = prompt_path.read_text(encoding="utf-8")
    openai_tools = to_openai_tools(declarations)
    history: list[dict[str, str]] = st.session_state["history"]

    messages = [
        {"role": "system", "content": system_prompt},
        *trim_history(history, history_window),
        {"role": "user", "content": user_text},
    ]

    turn_record: dict[str, Any] = {
        "turn_index": len(transcript["turns"]) + 1,
        "started_at": now_iso(),
        "user": user_text,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }

    with st.spinner("Agent đang chọn tool và chạy..."):
        try:
            result = run_model_tool_loop(
                provider=provider,
                messages=messages,
                tools=openai_tools,
                model=model_override.strip() or None,
                max_tool_rounds=max_tool_rounds,
            )
            turn_record.update(result)
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": result["assistant_text"]})
        except Exception as exc:
            turn_record.update({
                "status": "provider_error",
                "error": f"{type(exc).__name__}: {exc}",
            })

    turn_record["ended_at"] = now_iso()
    transcript["turns"].append(turn_record)
    transcript["model"] = selected_model
    write_transcript(transcript_path, transcript)
    st.rerun()


def export_transcript_json(transcript: dict[str, Any]) -> str:
    """Serialize the in-memory transcript exactly like write_transcript does."""
    return json.dumps(transcript, ensure_ascii=False, indent=2, default=str)


# `streamlit run app.py` executes this module as "__main__", so the guard both
# starts the UI under Streamlit and keeps a plain `import app` side-effect free.
if __name__ == "__main__":
    main()
