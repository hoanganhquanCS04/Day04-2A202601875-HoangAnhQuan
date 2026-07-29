"""The registry contract: tools.yaml <-> TOOL_FUNCTIONS <-> tools/<name>/ folders.

A rename that is only half-applied is the classic way this lab breaks, so these
tests check every artifact version snapshot, not just the live one.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml

from tools import TOOL_FUNCTIONS, load_tool_declarations, to_openai_tools


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
VERSIONS = ARTIFACTS / "versions"

# Two generations of team-written tools: the active set the model sees from v5
# on, and the first set that only the frozen v0..v4 snapshots declare.
TEAM_TOOLS = ["wikipedia", "hackernews", "crossref"]
LEGACY_TEAM_TOOLS = ["weather", "currency", "crypto"]
CORE_TOOLS = ["clarify", "timeline", "social_search", "lookup", "fetch", "format"]

FROZEN_VERSIONS = ("v0", "v1", "v2", "v3", "v4")
CURRENT_VERSION = "v5"

ALL_TOOLS_YAML = [ARTIFACTS / "tools.yaml"] + sorted(VERSIONS.glob("v*/tools.yaml"))


def yaml_ids(paths: list[Path]) -> list[str]:
    return [str(path.relative_to(ROOT)) for path in paths]


def test_version_snapshots_exist():
    for version in (*FROZEN_VERSIONS, CURRENT_VERSION):
        assert (VERSIONS / version / "system_prompt.md").is_file(), f"{version} prompt snapshot missing"
        assert (VERSIONS / version / "tools.yaml").is_file(), f"{version} tools snapshot missing"


@pytest.mark.parametrize("tools_path", ALL_TOOLS_YAML, ids=yaml_ids(ALL_TOOLS_YAML))
def test_every_declared_tool_has_an_implementation(tools_path: Path):
    for declaration in load_tool_declarations(tools_path):
        assert declaration["name"] in TOOL_FUNCTIONS, (
            f"{declaration['name']} declared in {tools_path.name} but missing from TOOL_FUNCTIONS"
        )


@pytest.mark.parametrize("tools_path", ALL_TOOLS_YAML, ids=yaml_ids(ALL_TOOLS_YAML))
def test_declaration_names_are_unique(tools_path: Path):
    names = [item["name"] for item in load_tool_declarations(tools_path)]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("tools_path", ALL_TOOLS_YAML, ids=yaml_ids(ALL_TOOLS_YAML))
def test_declaration_schema_is_well_formed(tools_path: Path):
    for declaration in load_tool_declarations(tools_path):
        name = declaration["name"]
        assert declaration.get("description", "").strip(), f"{name}: empty description"
        params = declaration["parameters"]
        assert params["type"] == "object", f"{name}: parameters must be an object schema"
        properties = params["properties"]
        for required in params.get("required", []):
            assert required in properties, f"{name}: required arg {required!r} is not in properties"
        for arg_name, spec in properties.items():
            assert "type" in spec, f"{name}.{arg_name}: missing type"
            if "enum" in spec and "default" in spec:
                assert spec["default"] in spec["enum"], f"{name}.{arg_name}: default not in enum"


@pytest.mark.parametrize("tools_path", ALL_TOOLS_YAML, ids=yaml_ids(ALL_TOOLS_YAML))
def test_declared_args_match_the_python_signature(tools_path: Path):
    """Every declared property must be a real keyword of the implementation.

    The agent calls `func(**call.args)`, so a property the function does not accept
    becomes a TypeError at runtime instead of a routing failure.
    """
    for declaration in load_tool_declarations(tools_path):
        func = TOOL_FUNCTIONS[declaration["name"]]
        signature = inspect.signature(func)
        accepts_kwargs = any(p.kind is p.VAR_KEYWORD for p in signature.parameters.values())
        if accepts_kwargs:
            continue
        for arg_name in declaration["parameters"]["properties"]:
            assert arg_name in signature.parameters, (
                f"{declaration['name']}: declares {arg_name!r} but {func.__name__}() does not accept it"
            )


@pytest.mark.parametrize("tools_path", ALL_TOOLS_YAML, ids=yaml_ids(ALL_TOOLS_YAML))
def test_required_args_have_no_python_side_surprise(tools_path: Path):
    """Required args must exist as parameters; optional ones must have defaults."""
    for declaration in load_tool_declarations(tools_path):
        func = TOOL_FUNCTIONS[declaration["name"]]
        signature = inspect.signature(func)
        for name, parameter in signature.parameters.items():
            if parameter.kind in (parameter.VAR_KEYWORD, parameter.VAR_POSITIONAL):
                continue
            assert parameter.default is not inspect.Parameter.empty, (
                f"{declaration['name']}.{name} has no default; a missing arg would raise TypeError"
            )


@pytest.mark.parametrize("name", TEAM_TOOLS + LEGACY_TEAM_TOOLS)
def test_team_tool_is_registered_and_documented(name: str):
    assert name in TOOL_FUNCTIONS
    folder = ROOT / "tools" / name
    assert (folder / "tool.py").is_file()
    tool_md = folder / "TOOL.md"
    assert tool_md.is_file()

    text = tool_md.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{name}/TOOL.md must start with YAML frontmatter"
    frontmatter = yaml.safe_load(text.split("---")[1])
    assert frontmatter["name"] == name
    for field in ("track", "kind", "requires_env", "inputs", "outputs", "side_effect"):
        assert field in frontmatter, f"{name}/TOOL.md missing frontmatter field {field}"
    assert frontmatter["requires_env"] == [], f"{name} must stay key-free so any teammate can run it"


@pytest.mark.parametrize("name", TEAM_TOOLS)
def test_active_team_tool_is_declared_in_the_live_artifact(name: str):
    declared = {item["name"] for item in load_tool_declarations(ARTIFACTS / "tools.yaml")}
    assert name in declared


@pytest.mark.parametrize("name", LEGACY_TEAM_TOOLS)
def test_legacy_team_tool_is_retired_from_the_live_artifact(name: str):
    """weather/currency/crypto had no research use and were dropped at v5.

    The implementation stays so every frozen v0..v4 snapshot still loads, but the
    model must no longer see them.
    """
    declared = {item["name"] for item in load_tool_declarations(ARTIFACTS / "tools.yaml")}
    assert name not in declared, f"{name} should not be declared any more"
    assert name in TOOL_FUNCTIONS, f"{name} implementation must stay for v0..v4 reproducibility"


@pytest.mark.parametrize("name", LEGACY_TEAM_TOOLS)
def test_legacy_team_tool_is_still_declared_in_the_frozen_snapshots(name: str):
    for version in FROZEN_VERSIONS:
        declared = {item["name"] for item in load_tool_declarations(VERSIONS / version / "tools.yaml")}
        assert name in declared, f"{version} snapshot was modified; it must stay frozen"


@pytest.mark.parametrize("name", CORE_TOOLS + TEAM_TOOLS)
def test_lab_requires_these_tools_to_be_live(name: str):
    declared = {item["name"] for item in load_tool_declarations(ARTIFACTS / "tools.yaml")}
    assert name in declared and name in TOOL_FUNCTIONS


def test_at_least_five_tools_are_declared():
    assert len(load_tool_declarations(ARTIFACTS / "tools.yaml")) >= 5


def test_tool_inventory_is_identical_across_the_frozen_versions():
    """v0..v4 must expose the same tools, so those eval deltas measure wording only."""
    inventories = {
        version: sorted(item["name"] for item in load_tool_declarations(VERSIONS / version / "tools.yaml"))
        for version in FROZEN_VERSIONS
    }
    reference = inventories["v0"]
    for version, names in inventories.items():
        assert names == reference, f"{version} tool inventory drifted from v0"


def test_v5_swaps_exactly_the_three_team_tools():
    """v5 is a new tool generation: same core/bonus set, team tools replaced."""
    frozen = {item["name"] for item in load_tool_declarations(VERSIONS / "v0" / "tools.yaml")}
    current = {item["name"] for item in load_tool_declarations(VERSIONS / "v5" / "tools.yaml")}

    assert frozen - current == set(LEGACY_TEAM_TOOLS)
    assert current - frozen == set(TEAM_TOOLS)
    assert len(frozen) == len(current), "the tool count should not change"


def test_to_openai_tools_shape():
    tools = to_openai_tools(load_tool_declarations(ARTIFACTS / "tools.yaml"))
    assert tools, "no tools converted"
    for tool in tools:
        assert tool["type"] == "function"
        function = tool["function"]
        assert set(function) == {"name", "description", "parameters"}
        assert function["name"] in TOOL_FUNCTIONS
        assert isinstance(function["parameters"], dict)


def test_to_openai_tools_defaults_for_minimal_declaration():
    converted = to_openai_tools([{"name": "bare"}])[0]["function"]
    assert converted["description"] == ""
    assert converted["parameters"] == {"type": "object", "properties": {}}


def test_live_artifacts_match_the_current_snapshot():
    """artifacts/ is the promoted deliverable; it must equal the v5 snapshot byte for byte."""
    for filename in ("system_prompt.md", "tools.yaml"):
        assert (ARTIFACTS / filename).read_bytes() == (VERSIONS / CURRENT_VERSION / filename).read_bytes(), (
            f"artifacts/{filename} differs from artifacts/versions/{CURRENT_VERSION}/{filename}"
        )
