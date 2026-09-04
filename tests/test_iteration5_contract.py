"""Public tool contracts introduced for the Iteration 5 CAD workflow."""

import importlib.util
from pathlib import Path

import pytest

from fusion_mcp.app import build_app
from fusion_mcp.config import load_config
from fusion_mcp.errors import op_error_message


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


@pytest.mark.parametrize("name", ["fusion_body_info", "fusion_list_edges"])
def test_targeted_query_tools_are_read_only(tools, name):
    """A write annotation on targeted inspection would trigger needless approval."""
    assert name in tools
    assert tools[name].annotations.readOnlyHint is True


def test_list_edges_requires_a_body(tools):
    """Design-wide edge enumeration would reintroduce ambiguous selection."""
    required = tools["fusion_list_edges"].parameters["required"]
    assert required == ["body"]


def test_curve_midpoint_starts_from_parameter_extent():
    """Calling getParameterAtLength without a start parameter drops midpoints."""
    helper_path = (
        Path(__file__).parents[1]
        / "addin/Fusion360MCP/fusion_mcp_addin/ops/_geometry.py"
    )
    spec = importlib.util.spec_from_file_location("fusion_addin_geometry", helper_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Evaluator:
        def getParameterExtents(self):
            return True, 4.0, 10.0

        def getParameterAtLength(self, start, length):
            assert start == 4.0
            assert length == 2.5
            return True, 7.0

        def getPointAtParameter(self, parameter):
            assert parameter == 7.0
            return True, type("Point", (), {"x": 1.0, "y": 2.0, "z": 3.0})()

    edge = type("Edge", (), {"evaluator": Evaluator(), "length": 5.0})()
    assert module.midpoint_mm(edge) == [10.0, 20.0, 30.0]


def test_mutation_evidence_identifies_selection_and_state():
    """Losing selection or before/after state would make a fillet unverifiable."""
    helper_path = (
        Path(__file__).parents[1]
        / "addin/Fusion360MCP/fusion_mcp_addin/bridge/_evidence.py"
    )
    spec = importlib.util.spec_from_file_location("fusion_mutation_evidence", helper_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result = module.mutation_evidence(
        before={"bodies": 1, "timeline": 4, "entities": ["Link"]},
        after={"bodies": 1, "timeline": 5, "entities": ["Link"]},
        requested_edges=[2, 6],
        resolved_edges=[2, 6],
        target={"name": "Link", "operative_id": "token"},
        radius_mm=3.0,
    )
    assert result["selection"] == {
        "requested_edges": [2, 6],
        "resolved_edges": [2, 6],
        "radius_mm": 3.0,
        "edge_resolution": [
            {"requested": 2, "resolved": 2, "status": "resolved"},
            {"requested": 6, "resolved": 6, "status": "resolved"},
        ],
    }
    assert result["rollback"] == "not_required"
    assert result["target_after"]["name"] == "Link"
    assert result["state_before"]["timeline"] == 4
    assert result["state_after"]["timeline"] == 5
    assert result["residual_entities"] == []


def test_physical_properties_documents_material_evidence(tools):
    """Without provenance fields, calculated mass can be mistaken for verified mass."""
    description = tools["fusion_physical_properties"].description.lower()
    assert "material name" in description
    assert "assignment scope" in description


def test_operation_error_preserves_mutation_evidence():
    """Dropping add-in evidence at the server boundary hides failed mutation state."""
    message = op_error_message({
        "code": "not_found",
        "message": "Edge index 99 out of range.",
        "detail": "",
        "rollback": "confirmed",
        "residual_entities": [],
        "state_before": {"bodies": 1, "timeline": 3},
        "state_after": {"bodies": 1, "timeline": 3},
    })
    assert '"rollback": "confirmed"' in message
    assert '"residual_entities": []' in message
