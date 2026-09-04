"""Public tool contracts introduced for the Iteration 5 CAD workflow."""

import pytest

from fusion_mcp.app import build_app
from fusion_mcp.config import load_config


@pytest.fixture(scope="module")
def tools():
    mcp, _client = build_app(load_config(mock=True, allow_arbitrary_code=True))
    return {tool.name: tool for tool in mcp._tool_manager.list_tools()}


def test_create_sketch_accepts_construction_plane_index(tools):
    """Removing integer plane support would break offset-plane sketch chains."""
    schema = tools["fusion_create_sketch"].parameters["properties"]["plane"]
    assert {entry["type"] for entry in schema["anyOf"]} >= {"string", "integer"}


def test_extrude_operation_exposes_actual_values(tools):
    """An unconstrained operation schema permits values rejected by Fusion."""
    operation = tools["fusion_extrude"].parameters["properties"]["operation"]
    assert operation["enum"] == ["new", "join", "cut", "intersect"]
