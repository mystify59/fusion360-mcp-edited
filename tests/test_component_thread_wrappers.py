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


def test_thread_schema_exposes_explicit_selection(tools):
    props = tools["fusion_thread"].parameters["properties"]
    assert props["handedness"]["default"] == "right"
    assert props["designation"]["default"] is None
    assert props["thread_class"]["default"] is None
    assert {entry["type"] for entry in props["designation"]["anyOf"]} == {
        "string",
        "null",
    }
    assert {entry["type"] for entry in props["thread_class"]["anyOf"]} == {
        "string",
        "null",
    }


def test_thread_forwards_legacy_defaults(recording_tools):
    tools, calls = recording_tools

    result = tools["fusion_thread"].fn(body=2, face=4)

    assert result == {"recorded": True}
    assert calls == [
        (
            "feature.thread",
            {
                "body": 2,
                "face": 4,
                "internal": False,
                "modeled": True,
                "thread_type": "ISO Metric profile",
                "designation": None,
                "thread_class": None,
                "handedness": "right",
            },
        )
    ]


def test_thread_forwards_explicit_selection(recording_tools):
    tools, calls = recording_tools

    result = tools["fusion_thread"].fn(
        body="Nut",
        face=1,
        internal=True,
        modeled=False,
        thread_type="ISO Metric profile",
        designation="M10x1.5",
        thread_class="6H",
        handedness="left",
    )

    assert result == {"recorded": True}
    assert calls == [
        (
            "feature.thread",
            {
                "body": "Nut",
                "face": 1,
                "internal": True,
                "modeled": False,
                "thread_type": "ISO Metric profile",
                "designation": "M10x1.5",
                "thread_class": "6H",
                "handedness": "left",
            },
        )
    ]
