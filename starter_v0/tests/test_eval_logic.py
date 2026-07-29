"""Tests for the scoring logic in run_eval.py.

These are the functions that decide PASS/FAIL, so a silent bug here would make
every metric in the report meaningless.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import run_eval
from run_eval import (
    ALLOWED_CASE_FAILURE_TYPES,
    best_arg_match,
    case_messages,
    compare_subset,
    evaluate_phase_b,
    load_cases,
    normalize_value,
    summarize,
    validate_case_failure_types,
    validate_expected_tools,
)


def case(**overrides: Any) -> dict[str, Any]:
    base = {
        "id": "T01",
        "phase": "B",
        "failure_type": "wrong_tool",
        "expect": {"tool_calls": [{"name": "lookup", "args": {"query": "AI"}}]},
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# normalize_value / compare_subset
# --------------------------------------------------------------------------- #
def test_normalize_is_case_and_whitespace_insensitive_for_strings():
    assert normalize_value("  Sama  ") == normalize_value("sama")


def test_normalize_sorts_lists():
    assert normalize_value(["b", "A"]) == normalize_value(["a", "B"])


def test_normalize_leaves_numbers_and_bools_alone():
    assert normalize_value(10) == 10
    assert normalize_value(True) is True
    assert normalize_value(None) is None


def test_compare_subset_ignores_extra_actual_keys():
    ok, failures, correct, total = compare_subset({"query": "AI"}, {"query": "ai", "topic": "news"})
    assert ok and failures == [] and (correct, total) == (1, 1)


def test_compare_subset_reports_each_mismatch():
    ok, failures, correct, total = compare_subset(
        {"query": "AI", "timeframe": "day"}, {"query": "AI", "timeframe": "week"}
    )
    assert not ok
    assert (correct, total) == (1, 2)
    assert "timeframe" in failures[0]


def test_compare_subset_missing_key_counts_as_wrong():
    ok, failures, correct, total = compare_subset({"limit": 5}, {})
    assert not ok and (correct, total) == (0, 1)


def test_compare_subset_missing_fields_is_a_subset_check():
    assert compare_subset({"missing_fields": ["url"]}, {"missing_fields": ["url", "date"]})[0]
    assert not compare_subset({"missing_fields": ["url"]}, {"missing_fields": ["date"]})[0]


def test_compare_subset_constraints_is_a_normalized_subset_check():
    assert compare_subset({"constraints": ["Top"]}, {"constraints": ["top", "latest"]})[0]


def test_compare_subset_number_types_are_interchangeable():
    assert compare_subset({"amount": 200}, {"amount": 200.0})[0]


# --------------------------------------------------------------------------- #
# best_arg_match
# --------------------------------------------------------------------------- #
def test_best_arg_match_picks_the_closest_of_several_same_name_calls():
    actual = [
        (0, {"name": "lookup", "args": {"query": "robotics", "topic": "general"}}),
        (1, {"name": "lookup", "args": {"query": "robotics", "topic": "news"}}),
    ]
    index, failures, correct, total = best_arg_match({"query": "robotics", "topic": "news"}, actual)
    assert index == 1 and failures == [] and correct == total == 2


def test_best_arg_match_returns_none_without_candidates():
    assert best_arg_match({"query": "x"}, []) is None


# --------------------------------------------------------------------------- #
# evaluate_phase_b
# --------------------------------------------------------------------------- #
def test_no_tool_case_passes_when_no_call_is_made():
    result = evaluate_phase_b(case(expect={"no_tool": True}, failure_type="out_of_scope"), [], "answer")
    assert result["passed"] and result["routing_correct"] and result["args_correct"]
    assert result["failure_type"] is None


def test_no_tool_case_fails_on_any_call():
    result = evaluate_phase_b(
        case(expect={"no_tool": True}, failure_type="out_of_scope"),
        [{"name": "lookup", "args": {}}],
        None,
    )
    assert not result["passed"]
    assert result["observed_mismatch"] == "unexpected_tool_call"
    assert result["failure_type"] == "out_of_scope"


def test_exact_match_passes():
    result = evaluate_phase_b(case(), [{"name": "lookup", "args": {"query": "AI", "topic": "news"}}], None)
    assert result["passed"]


def test_wrong_tool_name_is_missing_tool_call():
    result = evaluate_phase_b(case(), [{"name": "social_search", "args": {"query": "AI"}}], None)
    assert not result["passed"]
    assert not result["routing_correct"]
    assert result["observed_mismatch"] == "missing_tool_call"


def test_right_tool_wrong_arg_keeps_routing_credit():
    result = evaluate_phase_b(case(), [{"name": "lookup", "args": {"query": "robotics"}}], None)
    assert not result["passed"]
    assert result["routing_correct"] is True
    assert result["args_correct"] is False
    assert result["observed_mismatch"] == "wrong_arg_value"


def test_extra_tool_call_fails_the_case():
    result = evaluate_phase_b(
        case(),
        [{"name": "lookup", "args": {"query": "AI"}}, {"name": "format", "args": {}}],
        None,
    )
    assert not result["passed"]
    assert result["observed_mismatch"] == "extra_tool_call"
    assert any("extra tool call format" in item for item in result["failures"])


def test_two_expected_calls_are_order_independent():
    expected = case(expect={"tool_calls": [
        {"name": "lookup", "args": {"query": "AI"}},
        {"name": "social_search", "args": {"query": "AI"}},
    ]})
    actual = [
        {"name": "social_search", "args": {"query": "AI"}},
        {"name": "lookup", "args": {"query": "AI"}},
    ]
    assert evaluate_phase_b(expected, actual, None)["passed"]


def test_duplicate_calls_are_matched_one_to_one():
    expected = case(expect={"tool_calls": [
        {"name": "fetch", "args": {"url": "https://a.com"}},
        {"name": "fetch", "args": {"url": "https://b.com"}},
    ]})
    actual = [
        {"name": "fetch", "args": {"url": "https://b.com"}},
        {"name": "fetch", "args": {"url": "https://a.com"}},
    ]
    assert evaluate_phase_b(expected, actual, None)["passed"]


def test_empty_expected_args_only_checks_routing():
    expected = case(expect={"tool_calls": [{"name": "social_search", "args": {}}]})
    assert evaluate_phase_b(expected, [{"name": "social_search", "args": {"query": "whatever"}}], None)["passed"]


# --------------------------------------------------------------------------- #
# case_messages
# --------------------------------------------------------------------------- #
def test_single_turn_case_uses_query():
    messages = case_messages(case(query="Tin AI hôm nay?"))
    assert messages == [{"role": "user", "content": "Tin AI hôm nay?"}]


def test_input_field_wins_over_query():
    assert case_messages({"input": "A", "query": "B"})[0]["content"] == "A"


def test_multiturn_case_flattens_to_one_message_with_latest_turn_marked():
    messages = case_messages(case(turns=[
        {"role": "user", "content": "turn one"},
        {"role": "user", "content": "turn two"},
        {"role": "user", "content": "turn three"},
    ]))
    assert len(messages) == 1
    content = messages[0]["content"]
    assert "turn one" in content and "turn two" in content
    assert content.rstrip().endswith("turn three")
    assert "Latest user turn to answer now" in content


# --------------------------------------------------------------------------- #
# summarize
# --------------------------------------------------------------------------- #
def item(case_id: str, *, passed: bool, routing: bool = True, args: bool = True,
         multiturn: bool = False, failure_type: str | None = None,
         observed: str | None = None) -> dict[str, Any]:
    return {
        "id": case_id,
        "phase": "B",
        "is_multiturn": multiturn,
        "result": {
            "passed": passed,
            "routing_correct": routing,
            "args_correct": args,
            "failure_type": failure_type,
            "observed_mismatch": observed,
        },
    }


def test_summarize_counts_and_rates():
    summary = summarize([
        item("a", passed=True),
        item("b", passed=False, routing=False, args=False, failure_type="wrong_tool", observed="missing_tool_call"),
        item("c", passed=True, multiturn=True),
        item("d", passed=False, args=False, multiturn=True, failure_type="wrong_arg_value", observed="wrong_arg_value"),
    ])
    assert summary["total_cases"] == 4
    assert summary["measured_cases"] == 4
    assert summary["provider_error_cases"] == 0
    assert summary["passed_cases"] == 2
    assert summary["case_accuracy"] == 0.5
    assert summary["tool_routing_accuracy"] == 0.75
    assert summary["argument_accuracy"] == 0.5
    assert summary["multiturn_accuracy"] == 0.5
    assert summary["failure_counts"] == {"wrong_tool": 1, "wrong_arg_value": 1}
    assert summary["observed_mismatch_counts"] == {"missing_tool_call": 1, "wrong_arg_value": 1}


def test_summarize_excludes_provider_errors_from_accuracy():
    summary = summarize([
        item("a", passed=True),
        item("b", passed=False, failure_type="provider_error"),
    ])
    assert summary["total_cases"] == 2
    assert summary["measured_cases"] == 1
    assert summary["provider_error_cases"] == 1
    assert summary["case_accuracy"] == 1.0


def test_summarize_multiturn_accuracy_is_none_without_multiturn_cases():
    assert summarize([item("a", passed=True)])["multiturn_accuracy"] is None


def test_summarize_handles_an_empty_result_list():
    summary = summarize([])
    assert summary["case_accuracy"] == 0.0
    assert summary["measured_cases"] == 0


# --------------------------------------------------------------------------- #
# validation guards
# --------------------------------------------------------------------------- #
def test_validate_case_failure_types_rejects_unknown_value(tmp_path: Path):
    with pytest.raises(ValueError, match="Invalid failure_type"):
        validate_case_failure_types([case(failure_type="typo_here")], tmp_path / "x.json")


def test_validate_case_failure_types_accepts_every_allowed_value(tmp_path: Path):
    cases = [case(id=name, failure_type=name) for name in ALLOWED_CASE_FAILURE_TYPES]
    validate_case_failure_types(cases, tmp_path / "x.json")


def test_validate_expected_tools_rejects_undeclared_tool(tmp_path: Path):
    with pytest.raises(ValueError, match="not declared"):
        validate_expected_tools([case()], [{"name": "fetch"}], tmp_path / "x.json")


def test_validate_expected_tools_rejects_declared_but_unimplemented_tool(tmp_path: Path):
    assert "ghost" not in run_eval.TOOL_FUNCTIONS
    with pytest.raises(ValueError, match="no implementation"):
        validate_expected_tools(
            [case(expect={"tool_calls": [{"name": "ghost", "args": {}}]})],
            [{"name": "ghost"}],
            tmp_path / "x.json",
        )


def test_load_cases_filters_by_phase(tmp_path: Path):
    path = tmp_path / "cases.json"
    path.write_text(
        '{"cases": [{"id": "a", "phase": "B", "failure_type": "wrong_tool", "expect": {}},'
        ' {"id": "b", "phase": "A", "failure_type": "wrong_tool", "expect": {}}]}',
        encoding="utf-8",
    )
    cases = load_cases(path, "B")
    assert [item["id"] for item in cases] == ["a"]


def test_safe_slug_strips_unsafe_characters():
    assert run_eval.safe_slug("v3 / base?") == "v3_base"
    assert run_eval.safe_slug("   ") == "run"
