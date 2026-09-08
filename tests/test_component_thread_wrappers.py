"""Public wrappers for selecting the active Fusion component."""

import pytest

from fusion_mcp.app import build_app
from fusion_mcp.config import load_config


@pytest.fixture(scope="module")
def tools():
    mcp, _client = build_app(load_config(mock=True))
    return {tool.name: tool for tool in mcp._tool_manager.list_tools()}


def test_component_target_tools_are_public(tools):
    assert "fusion_set_active_component" in tools
    assert "fusion_get_active_component" in tools
    assert tools["fusion_get_active_component"].annotations.readOnlyHint is True
    create = tools["fusion_create_component"].parameters["properties"]
    assert create["activate"]["default"] is True


def test_component_target_schemas(tools):
    set_schema = tools["fusion_set_active_component"].parameters
    assert set_schema["properties"]["name"]["default"] == "root"
    assert tools["fusion_get_active_component"].parameters.get("required", []) == []
