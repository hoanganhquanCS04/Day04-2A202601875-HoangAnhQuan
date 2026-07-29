"""Tests for versioning, .env loading, console encoding and the run-log parser."""
from __future__ import annotations

import csv
import io
import json
import os
import sys
from pathlib import Path

import pytest

from console import enable_utf8_io, safe_text
from env_loader import load_dotenv, load_lab_env
from scripts import parse_runs
from versioning import artifact_version_dict, build_artifact_version, file_hash, short_hash


ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# versioning
# --------------------------------------------------------------------------- #
def test_artifact_version_encodes_both_hashes(tmp_path: Path):
    prompt = tmp_path / "system_prompt.md"
    tools = tmp_path / "tools.yaml"
    prompt.write_text("prompt", encoding="utf-8")
    tools.write_text("tools", encoding="utf-8")

    version = build_artifact_version("v3", prompt, tools)
    assert version.version == "v3"
    assert version.artifact_version == f"v3+p{version.prompt_hash[:12]}+t{version.tools_hash[:12]}"
    assert len(version.prompt_hash) == 64


def test_artifact_version_changes_when_the_prompt_changes(tmp_path: Path):
    prompt = tmp_path / "p.md"
    tools = tmp_path / "t.yaml"
    tools.write_text("tools", encoding="utf-8")

    prompt.write_text("one", encoding="utf-8")
    first = build_artifact_version("v1", prompt, tools).artifact_version
    prompt.write_text("two", encoding="utf-8")
    second = build_artifact_version("v1", prompt, tools).artifact_version

    assert first != second


def test_artifact_version_is_stable_for_identical_content(tmp_path: Path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text("same", encoding="utf-8")
    b.write_text("same", encoding="utf-8")
    assert file_hash(a) == file_hash(b)


def test_short_hash_length():
    assert short_hash("abcdef1234567890") == "abcdef123456"
    assert len(short_hash("abcdef1234567890", 4)) == 4


def test_artifact_version_dict_has_the_run_log_fields(tmp_path: Path):
    prompt, tools = tmp_path / "p", tmp_path / "t"
    prompt.write_text("p", encoding="utf-8")
    tools.write_text("t", encoding="utf-8")
    payload = artifact_version_dict(build_artifact_version("v0", prompt, tools))
    assert set(payload) == {"version", "artifact_version", "prompt_hash", "tools_hash"}


def test_each_delivered_version_has_a_distinct_artifact_version():
    versions = {}
    for name in ("v0", "v1", "v2", "v3"):
        folder = ROOT / "artifacts" / "versions" / name
        versions[name] = build_artifact_version(name, folder / "system_prompt.md", folder / "tools.yaml")

    assert versions["v0"].prompt_hash != versions["v1"].prompt_hash, "v1 must actually change the prompt"
    assert versions["v1"].tools_hash != versions["v2"].tools_hash, "v2 must actually change tools.yaml"
    assert versions["v1"].prompt_hash == versions["v2"].prompt_hash, "v2 changes tools only"
    assert versions["v2"].prompt_hash != versions["v3"].prompt_hash, "v3 fine-tunes the prompt"
    assert versions["v2"].tools_hash != versions["v3"].tools_hash, "v3 fine-tunes the declarations"
    assert len({v.artifact_version for v in versions.values()}) == 4


# --------------------------------------------------------------------------- #
# env_loader
# --------------------------------------------------------------------------- #
def test_load_dotenv_parses_pairs_and_skips_noise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join([
            "# a comment",
            "",
            "YESCALE_API_KEY=sk-123",
            'QUOTED="quoted-value"',
            "SINGLE='single-value'",
            "SPACED  =  padded  ",
            "URL=https://api.yescale.io/v1?a=b",
            "no_equals_sign",
        ]),
        encoding="utf-8",
    )
    for name in ("YESCALE_API_KEY", "QUOTED", "SINGLE", "SPACED", "URL"):
        monkeypatch.delenv(name, raising=False)

    load_dotenv(env_file)

    assert os.environ["YESCALE_API_KEY"] == "sk-123"
    assert os.environ["QUOTED"] == "quoted-value"
    assert os.environ["SINGLE"] == "single-value"
    assert os.environ["SPACED"] == "padded"
    assert os.environ["URL"] == "https://api.yescale.io/v1?a=b", "values containing '=' must survive"

    for name in ("YESCALE_API_KEY", "QUOTED", "SINGLE", "SPACED", "URL"):
        monkeypatch.delenv(name, raising=False)


def test_load_dotenv_override_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_file = tmp_path / ".env"
    env_file.write_text("YESCALE_API_KEY=from-file", encoding="utf-8")

    monkeypatch.setenv("YESCALE_API_KEY", "from-shell")
    load_dotenv(env_file, override=False)
    assert os.environ["YESCALE_API_KEY"] == "from-shell"

    load_dotenv(env_file, override=True)
    assert os.environ["YESCALE_API_KEY"] == "from-file"


def test_load_dotenv_missing_file_is_a_no_op(tmp_path: Path):
    load_dotenv(tmp_path / "nope.env")  # must not raise


def test_load_lab_env_prefers_the_external_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    external = tmp_path / "external.env"
    external.write_text("YESCALE_API_KEY=external", encoding="utf-8")
    monkeypatch.setenv("DAY04_ENV_FILE", str(external))
    monkeypatch.delenv("YESCALE_API_KEY", raising=False)

    load_lab_env(tmp_path)
    assert os.environ["YESCALE_API_KEY"] == "external"
    monkeypatch.delenv("YESCALE_API_KEY", raising=False)


def test_env_example_documents_the_yescale_key():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "YESCALE_API_KEY=" in text
    assert "https://api.yescale.io/v1" in text


def test_env_example_never_ships_a_real_secret():
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip().endswith(("_KEY", "_TOKEN")):
            assert value.strip() == "", f"{key} must be blank in .env.example"


def test_env_is_gitignored():
    ignore_files = [ROOT / ".gitignore", ROOT.parent / ".gitignore"]
    patterns = "\n".join(path.read_text(encoding="utf-8") for path in ignore_files if path.is_file())
    assert ".env" in patterns


# --------------------------------------------------------------------------- #
# console
# --------------------------------------------------------------------------- #
def test_enable_utf8_io_makes_streams_utf8(capsys: pytest.CaptureFixture[str]):
    enable_utf8_io()
    print("Thời tiết Hà Nội — 25°C ✅")  # would raise on a cp1252 console
    assert "Thời tiết" in capsys.readouterr().out


def test_enable_utf8_io_survives_a_stream_without_reconfigure(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    enable_utf8_io()  # StringIO has no .reconfigure; must not raise


def test_enable_utf8_io_also_reconfigures_stdin(monkeypatch: pytest.MonkeyPatch):
    """Piped Vietnamese input decoded as cp1252 turns into lone surrogates."""
    seen: list[dict] = []

    class Recorder:
        def reconfigure(self, **kwargs):
            seen.append(kwargs)

    monkeypatch.setattr(sys, "stdin", Recorder())
    monkeypatch.setattr(sys, "stdout", Recorder())
    monkeypatch.setattr(sys, "stderr", Recorder())
    enable_utf8_io()

    assert len(seen) == 3, "stdin, stdout and stderr must all be reconfigured"
    assert all(kwargs == {"encoding": "utf-8", "errors": "replace"} for kwargs in seen)


def test_safe_text_strips_unpaired_surrogates():
    mangled = "Hà N\udc9di"
    assert safe_text(mangled).encode("utf-8")  # must not raise
    assert "\udc9d" not in safe_text(mangled)


def test_safe_text_leaves_valid_text_alone():
    assert safe_text("Thời tiết Hà Nội 25°C") == "Thời tiết Hà Nội 25°C"


# --------------------------------------------------------------------------- #
# scripts/parse_runs.py
# --------------------------------------------------------------------------- #
def sample_run() -> dict:
    return {
        "run_id": "v3_B_base_yescale_1",
        "version": "v3",
        "artifact_version": "v3+pabc+tdef",
        "suite": "base",
        "results": [
            {
                "id": "R01",
                "is_multiturn": False,
                "expect": {"tool_calls": [{"name": "timeline", "args": {"screenname": "sama"}}]},
                "result": {
                    "passed": True, "routing_correct": True, "args_correct": True,
                    "case_failure_type": "wrong_tool", "observed_mismatch": None,
                    "actual_tool_calls": [{"name": "timeline", "args": {}}], "failures": [],
                },
            },
            {
                "id": "R08",
                "is_multiturn": False,
                "expect": {"no_tool": True},
                "result": {
                    "passed": False, "routing_correct": False, "args_correct": False,
                    "case_failure_type": "out_of_scope", "observed_mismatch": "unexpected_tool_call",
                    "actual_tool_calls": [{"name": "lookup", "args": {}}], "failures": ["expected no tool call"],
                },
            },
        ],
    }


def test_parse_runs_row_mapping():
    run = sample_run()
    row = parse_runs.row_for(run, run["results"][1])
    assert row["case_id"] == "R08"
    assert row["expected_tool"] == "no_tool"
    assert row["actual_tool"] == "lookup"
    assert row["passed"] is False
    assert row["failures"] == "expected no tool call"


def test_parse_runs_joins_multiple_expected_tools():
    expect = {"tool_calls": [{"name": "lookup"}, {"name": "social_search"}]}
    assert parse_runs.first_expected_tool(expect) == "lookup|social_search"


def test_parse_runs_empty_expect_is_blank():
    assert parse_runs.first_expected_tool({}) == ""


def test_parse_runs_writes_a_csv_for_a_directory(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "run1.json").write_text(json.dumps(sample_run()), encoding="utf-8")
    out = tmp_path / "analysis" / "out.csv"

    files = parse_runs.iter_run_files([runs_dir])
    rows = []
    for path in files:
        run = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(parse_runs.row_for(run, item) for item in run["results"])

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    assert len(rows) == 2
    assert "R01" in out.read_text(encoding="utf-8")
