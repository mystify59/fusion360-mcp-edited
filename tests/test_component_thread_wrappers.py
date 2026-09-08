"""Public wrappers for selecting the active Fusion component."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from fusion_mcp.app import build_app
from fusion_mcp.config import load_config


ADDIN_FEATURE = (
    Path(__file__).resolve().parents[1]
    / "addin"
    / "Fusion360MCP"
    / "fusion_mcp_addin"
    / "ops"
    / "feature.py"
)


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


def test_list_threads_is_read_only(tools):
    tool = tools["fusion_list_threads"]
    assert tool.annotations.readOnlyHint is True
    assert "component" in tool.parameters["properties"]


def test_thread_inspection_contract_is_explicit():
    text = ADDIN_FEATURE.read_text(encoding="utf-8")
    for field in [
        "thread_type",
        "designation",
        "thread_class",
        "internal",
        "modeled",
        "handedness",
        "full_length",
        "capability_notes",
    ]:
        assert '"{}"'.format(field) in text


@pytest.fixture
def addin_thread_inspector(monkeypatch):
    """Load the real add-in operation against a narrow fake Fusion boundary."""
    package = "_thread_inspector_test_addin"
    for name in (package, package + ".ops", package + ".bridge"):
        module = ModuleType(name)
        module.__path__ = []
        monkeypatch.setitem(sys.modules, name, module)

    class OpError(Exception):
        pass

    protocol = ModuleType(package + ".bridge.protocol")
    protocol.ERR_INVALID_PARAMS = "invalid_params"
    protocol.ERR_NOT_FOUND = "not_found"
    protocol.OpError = OpError
    monkeypatch.setitem(sys.modules, protocol.__name__, protocol)

    def op(*_args, **_kwargs):
        return lambda fn: fn

    def optional(params, key, default=None, types=None):
        value = params.get(key, default)
        if value is None:
            return default
        if types is not None and not isinstance(value, types):
            raise OpError("bad type")
        return value

    common = ModuleType(package + ".ops._common")
    common.op = op
    common.optional = optional
    common.require = lambda params, key, types=None: params[key]
    common._find_component = lambda design, name: design.components.get(name)
    monkeypatch.setitem(sys.modules, common.__name__, common)

    adsk = ModuleType("adsk")
    adsk_fusion = ModuleType("adsk.fusion")
    adsk.fusion = adsk_fusion
    monkeypatch.setitem(sys.modules, "adsk", adsk)
    monkeypatch.setitem(sys.modules, "adsk.fusion", adsk_fusion)

    spec = importlib.util.spec_from_file_location(package + ".ops.feature", ADDIN_FEATURE)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_list_threads_reads_thread_properties_without_mutating_target(addin_thread_inspector):
    thread_info = SimpleNamespace(
        threadType="ISO Metric profile",
        threadDesignation="M10x1.5",
        threadClass="6g",
        isInternal=False,
        isRightHanded=False,
    )
    feature = SimpleNamespace(
        name="Thread1",
        threadInfo=thread_info,
        isModeled=True,
        isFullLength=False,
    )
    component = SimpleNamespace(
        name="Active",
        features=SimpleNamespace(threadFeatures=SimpleNamespace(count=1, item=lambda index: feature)),
    )
    calls = []
    ctx = SimpleNamespace(
        target=lambda: calls.append("target") or component,
        design=lambda: calls.append("design") or SimpleNamespace(components={}),
    )

    result = addin_thread_inspector.list_threads(ctx, {})

    assert calls == ["target"]
    assert result == {
        "component": "Active",
        "count": 1,
        "threads": [
            {
                "index": 0,
                "name": "Thread1",
                "thread_type": "ISO Metric profile",
                "designation": "M10x1.5",
                "thread_class": "6g",
                "internal": False,
                "modeled": True,
                "handedness": "left",
                "full_length": False,
                "capability_notes": [],
            }
        ],
    }


def test_list_threads_uses_null_and_notes_when_fusion_properties_are_unavailable(
    addin_thread_inspector,
):
    feature = SimpleNamespace(
        name="Left-looking thread",
        threadInfo=SimpleNamespace(threadType="ISO Metric profile"),
    )
    component = SimpleNamespace(
        name="Active",
        features=SimpleNamespace(threadFeatures=SimpleNamespace(count=1, item=lambda index: feature)),
    )
    ctx = SimpleNamespace(target=lambda: component)

    result = addin_thread_inspector.list_threads(ctx, {})

    thread = result["threads"][0]
    assert thread["thread_type"] == "ISO Metric profile"
    assert thread["designation"] is None
    assert thread["thread_class"] is None
    assert thread["internal"] is None
    assert thread["modeled"] is None
    assert thread["handedness"] is None
    assert thread["full_length"] is None
    assert "handedness unavailable: threadInfo.isRightHanded is not exposed by this Fusion API." in thread["capability_notes"]
    assert all("left" not in note.lower() for note in thread["capability_notes"])


def test_list_threads_records_a_capability_note_when_a_property_read_raises(
    addin_thread_inspector,
):
    class Feature:
        name = "Thread1"
        threadInfo = SimpleNamespace(
            threadType="ISO Metric profile",
            threadDesignation="M10x1.5",
            threadClass="6g",
            isInternal=False,
            isRightHanded=True,
        )
        isFullLength = True

        @property
        def isModeled(self):
            raise RuntimeError("unsupported in this Fusion release")

    component = SimpleNamespace(
        name="Active",
        features=SimpleNamespace(threadFeatures=SimpleNamespace(count=1, item=lambda index: Feature())),
    )

    result = addin_thread_inspector.list_threads(SimpleNamespace(target=lambda: component), {})

    thread = result["threads"][0]
    assert thread["modeled"] is None
    assert "modeled unavailable: isModeled could not be read from this Fusion API." in thread[
        "capability_notes"
    ]


def test_list_threads_resolves_a_named_component_without_changing_target(
    addin_thread_inspector,
):
    selected = SimpleNamespace(
        name="Selected",
        features=SimpleNamespace(threadFeatures=SimpleNamespace(count=0, item=None)),
    )
    ctx = SimpleNamespace(
        target=lambda: pytest.fail("named inspection must not use or change the active target"),
        design=lambda: SimpleNamespace(components={"Selected": selected}),
    )

    result = addin_thread_inspector.list_threads(ctx, {"component": "Selected"})

    assert result == {"component": "Selected", "count": 0, "threads": []}
