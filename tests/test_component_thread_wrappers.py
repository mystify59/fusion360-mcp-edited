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


@pytest.fixture
def recording_tools():
    mcp, client = build_app(load_config(mock=True))
    calls = []

    def record_call(op, params=None):
        calls.append((op, params))
        return {"recorded": True}

    client.call = record_call
    return {tool.name: tool for tool in mcp._tool_manager.list_tools()}, calls


def test_create_component_forwards_name_and_activate(recording_tools):
    tools, calls = recording_tools

    result = tools["fusion_create_component"].fn(name="Part", activate=False)

    assert result == {"recorded": True}
    assert calls == [("assembly.create_component", {"name": "Part", "activate": False})]


def test_set_active_component_forwards_name(recording_tools):
    tools, calls = recording_tools

    tools["fusion_set_active_component"].fn(name="Part")

    assert calls == [("assembly.activate_component", {"name": "Part"})]


def test_get_active_component_does_not_send_a_payload(recording_tools):
    tools, calls = recording_tools

    tools["fusion_get_active_component"].fn()

    assert calls == [("assembly.active_component", None)]
