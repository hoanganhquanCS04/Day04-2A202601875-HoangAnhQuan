"""Structural checks on the eval datasets.

data/eval_group.json must hold exactly 10 team-written cases (5 single-turn +
5 multi-turn) and every case must be scoreable by run_eval.evaluate_phase_b.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from run_eval import ALLOWED_CASE_FAILURE_TYPES, case_messages, load_cases, validate_expected_tools
from tools import TOOL_FUNCTIONS, load_tool_declarations


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
GROUP_PATH = DATA / "eval_group.json"
BASE_PATH = DATA / "eval_base.json"
EXTENSION_PATH = DATA / "eval_research_extension.json"
LIVE_TOOLS = ROOT / "artifacts" / "tools.yaml"

REQUIRED_SINGLE = 5
REQUIRED_MULTI = 5


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def group_cases() -> list[dict[str, Any]]:
    return load(GROUP_PATH)["cases"]


def test_group_file_is_valid_json_with_metadata():
    data = load(GROUP_PATH)
    assert data["dataset_id"]
    assert data["dataset_role"] == "group"
    assert data["description"].strip()
    assert set(data["allowed_failure_types"]) == ALLOWED_CASE_FAILURE_TYPES


def test_group_has_exactly_ten_cases(group_cases: list[dict[str, Any]]):
    assert len(group_cases) == 10


def test_group_split_is_five_single_and_five_multi(group_cases: list[dict[str, Any]]):
    single = [c for c in group_cases if "query" in c and "turns" not in c]
    multi = [c for c in group_cases if "turns" in c]
    assert len(single) == REQUIRED_SINGLE
    assert len(multi) == REQUIRED_MULTI
    assert len(single) + len(multi) == len(group_cases)


def test_group_case_ids_are_unique(group_cases: list[dict[str, Any]]):
    ids = [c["id"] for c in group_cases]
    assert len(ids) == len(set(ids))


def test_group_cases_have_the_required_fields(group_cases: list[dict[str, Any]]):
    for c in group_cases:
        assert c["phase"] == "B", f"{c['id']}: phase must be 'B'"
        assert c["failure_type"] in ALLOWED_CASE_FAILURE_TYPES, f"{c['id']}: bad failure_type"
        assert c["expect"], f"{c['id']}: empty expect"
        assert c["metadata"]["what_it_tests"].strip(), f"{c['id']}: metadata.what_it_tests is required"


def test_group_expectations_are_either_no_tool_or_tool_calls(group_cases: list[dict[str, Any]]):
    for c in group_cases:
        expect = c["expect"]
        has_no_tool = bool(expect.get("no_tool"))
        has_calls = bool(expect.get("tool_calls"))
        assert has_no_tool != has_calls, f"{c['id']}: expect must set exactly one of no_tool / tool_calls"
        for call in expect.get("tool_calls", []):
            assert call["name"] in TOOL_FUNCTIONS, f"{c['id']}: {call['name']} has no implementation"
            assert isinstance(call.get("args", {}), dict)


def test_group_multiturn_cases_have_at_least_two_turns(group_cases: list[dict[str, Any]]):
    for c in group_cases:
        if "turns" in c:
            assert len(c["turns"]) >= 2, f"{c['id']}: a multi-turn case needs 2+ turns"
            for turn in c["turns"]:
                assert turn["role"] == "user"
                assert turn["content"].strip()


def test_group_expected_tools_are_declared_in_the_live_artifact():
    cases = load_cases(GROUP_PATH, "B")
    validate_expected_tools(cases, load_tool_declarations(LIVE_TOOLS), GROUP_PATH)


def test_group_exercises_the_team_written_tools(group_cases: list[dict[str, Any]]):
    used = {call["name"] for c in group_cases for call in c["expect"].get("tool_calls", [])}
    assert {"wikipedia", "hackernews", "crossref"} <= used, "group eval must cover the new tools"


def test_group_does_not_reference_retired_tools(group_cases: list[dict[str, Any]]):
    """weather/currency/crypto were dropped at v5; the model no longer sees them."""
    used = {call["name"] for c in group_cases for call in c["expect"].get("tool_calls", [])}
    assert not ({"weather", "currency", "crypto"} & used)


def test_group_covers_a_spread_of_failure_types(group_cases: list[dict[str, Any]]):
    kinds = {c["failure_type"] for c in group_cases}
    assert len(kinds) >= 4, f"only {kinds} covered; the suite should probe several failure modes"


def test_every_group_case_produces_a_usable_prompt(group_cases: list[dict[str, Any]]):
    for c in group_cases:
        messages = case_messages(c)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"].strip()


def test_load_cases_accepts_the_group_file():
    assert len(load_cases(GROUP_PATH, "B")) == 10


# --------------------------------------------------------------------------- #
# The fixed datasets must not be edited (lab rule D2)
# --------------------------------------------------------------------------- #
def test_base_dataset_is_unchanged_in_shape():
    cases = load(BASE_PATH)["cases"]
    assert len(cases) == 20
    assert {c["id"] for c in cases} >= {"R01_user_tweets_routing", "M06_switch_tool"}


@pytest.mark.parametrize("path", [BASE_PATH, EXTENSION_PATH, GROUP_PATH])
def test_all_datasets_reference_only_implemented_tools(path: Path):
    validate_expected_tools(load_cases(path, "B"), load_tool_declarations(LIVE_TOOLS), path)


# --------------------------------------------------------------------------- #
# The archived first-generation team eval
# --------------------------------------------------------------------------- #
GEN1_PATH = DATA / "eval_group_gen1.json"
V0_TOOLS = ROOT / "artifacts" / "versions" / "v0" / "tools.yaml"


def test_archived_group_eval_still_exists():
    """The v0..v4 group runs were measured against this file; keep it readable."""
    assert GEN1_PATH.is_file()
    data = load(GEN1_PATH)
    assert data["dataset_role"] == "group_archive"
    assert len(data["cases"]) == 10


def test_archived_group_eval_validates_against_the_v0_snapshot():
    validate_expected_tools(load_cases(GEN1_PATH, "B"), load_tool_declarations(V0_TOOLS), GEN1_PATH)


def test_archived_group_eval_matches_the_recorded_group_runs():
    """Its case ids must line up with what runs/*_group_*.json actually measured."""
    archived = {case["id"] for case in load(GEN1_PATH)["cases"]}
    for path in sorted((ROOT / "runs").glob("*_group_*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        measured = {item["id"] for item in run["results"]}
        assert measured == archived, f"{path.name} does not match the archived dataset"


def test_current_and_archived_group_evals_are_different_generations():
    current = {case["id"] for case in load(GROUP_PATH)["cases"]}
    archived = {case["id"] for case in load(GEN1_PATH)["cases"]}
    assert current != archived
