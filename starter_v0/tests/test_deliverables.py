"""Checks on the submitted evidence itself.

version_log.csv, runs/*.json, transcripts/ and REPORT.md must agree with each
other — a report row pointing at a run file that says something else is exactly
the failure mode these tests exist to catch.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
VERSION_LOG = ROOT / "artifacts" / "version_log.csv"
REPORT = ROOT / "artifacts" / "REPORT.md"
TRANSCRIPTS = ROOT / "transcripts"

VERSION_LOG_FIELDS = [
    "version", "author", "changed_artifact", "artifact_version", "prompt_hash", "tools_hash",
    "reason", "hypothesis", "metric_name", "metric_before", "metric_after", "run_file",
]


@pytest.fixture(scope="module")
def log_rows() -> list[dict[str, str]]:
    with VERSION_LOG.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def runs() -> dict[str, dict]:
    return {path.name: json.loads(path.read_text(encoding="utf-8")) for path in sorted(RUNS.glob("*.json"))}


def test_version_log_has_the_required_columns(log_rows: list[dict[str, str]]):
    assert log_rows, "version_log.csv is empty"
    assert list(log_rows[0]) == VERSION_LOG_FIELDS


def test_version_log_covers_v0_through_v3(log_rows: list[dict[str, str]]):
    logged = {row["version"] for row in log_rows}
    assert {"v0", "v1", "v2", "v3"} <= logged


def test_version_log_rows_are_filled_in(log_rows: list[dict[str, str]]):
    for row in log_rows:
        for field in ("author", "changed_artifact", "artifact_version", "reason", "hypothesis", "metric_name"):
            assert row[field].strip(), f"{row['version']}/{row['metric_name']}: {field} is empty"
        assert "<điền" not in row["hypothesis"], "template placeholder left in the log"


def test_every_logged_run_file_exists_and_matches(log_rows: list[dict[str, str]], runs: dict[str, dict]):
    for row in log_rows:
        path = ROOT / row["run_file"]
        assert path.is_file(), f"{row['run_file']} referenced by version_log.csv does not exist"
        run = runs[path.name]
        assert run["version"] == row["version"]
        assert run["artifact_version"] == row["artifact_version"]
        assert run["prompt_hash"].startswith(row["prompt_hash"])
        assert run["tools_hash"].startswith(row["tools_hash"])


def test_logged_metric_after_matches_the_run_summary(log_rows: list[dict[str, str]], runs: dict[str, dict]):
    for row in log_rows:
        run = runs[(ROOT / row["run_file"]).name]
        metric, _, suite = row["metric_name"].partition("@")
        assert run["suite"] == suite, f"{row['run_file']}: suite mismatch"
        assert float(row["metric_after"]) == run["summary"][metric]


def test_logged_metric_before_matches_the_previous_run(log_rows: list[dict[str, str]], runs: dict[str, dict]):
    seen: dict[str, float] = {}
    for row in log_rows:
        run = runs[(ROOT / row["run_file"]).name]
        metric, _, suite = row["metric_name"].partition("@")
        if row["metric_before"].strip():
            assert float(row["metric_before"]) == seen[suite], f"{row['version']}@{suite}: stale metric_before"
        else:
            assert suite not in seen, f"{row['version']}@{suite}: metric_before must only be blank on the first run"
        seen[suite] = run["summary"][metric]


def test_every_run_is_valid_evidence(runs: dict[str, dict]):
    """Lab rule: provider_error_cases must be 0 and every case must be measured."""
    assert runs, "no run files found"
    for name, run in runs.items():
        summary = run["summary"]
        assert summary["provider_error_cases"] == 0, f"{name}: has provider errors"
        assert summary["measured_cases"] == summary["total_cases"], f"{name}: unmeasured cases"


def test_every_run_used_the_yescale_provider(runs: dict[str, dict]):
    for name, run in runs.items():
        assert run["provider"] == "yescale", f"{name}: ran on {run['provider']}"
        assert run["model"], f"{name}: no model recorded"


def test_no_run_ever_sent_a_telegram_message(runs: dict[str, dict]):
    """Lab rule D5: Telegram creds stay unset, so `send` must never report 'sent'."""
    for name, run in runs.items():
        for item in run["results"]:
            for event in item.get("tool_results", []):
                result = event.get("result")
                if isinstance(result, dict):
                    assert result.get("status") != "sent", f"{name}/{item['id']}: a message was actually sent"


def test_the_required_suites_are_perfect_at_v3(runs: dict[str, dict]):
    for name, run in runs.items():
        if run["version"] == "v3" and run["suite"] in {"base", "group"}:
            assert run["summary"]["case_accuracy"] == 1.0, f"{name}: v3 regressed"


def test_v0_baseline_is_genuinely_worse_than_v3(runs: dict[str, dict]):
    """A believable optimisation story needs a baseline that actually failed."""
    by_key = {(run["version"], run["suite"]): run["summary"]["case_accuracy"] for run in runs.values()}
    for suite in ("base", "group"):
        assert by_key[("v0", suite)] < by_key[("v3", suite)], f"{suite}: no measurable improvement"


def test_a_live_transcript_exists_with_three_successful_turns():
    files = sorted(TRANSCRIPTS.glob("*.transcript.json"))
    assert files, "lab requires at least one live chat transcript"
    best = 0
    for path in files:
        transcript = json.loads(path.read_text(encoding="utf-8"))
        best = max(best, sum(1 for turn in transcript["turns"] if turn["status"] != "provider_error"))
    assert best >= 3, f"need >= 3 successful live turns, best transcript had {best}"


def test_transcripts_record_the_artifact_version():
    for path in TRANSCRIPTS.glob("*.transcript.json"):
        transcript = json.loads(path.read_text(encoding="utf-8"))
        assert transcript["artifact_version"]
        assert transcript["provider"]


def test_report_has_no_unfilled_template_placeholders():
    text = REPORT.read_text(encoding="utf-8")
    for placeholder in ("<điền", "| v1 |  |", "|  |  |  |"):
        assert placeholder not in text, f"REPORT.md still contains the placeholder {placeholder!r}"


def test_report_links_the_real_run_files(runs: dict[str, dict]):
    text = REPORT.read_text(encoding="utf-8")
    for version in ("v0", "v1", "v2", "v3"):
        expected = next(name for name, run in runs.items() if run["version"] == version and run["suite"] == "base")
        assert expected in text, f"REPORT.md does not cite the {version} base run"
