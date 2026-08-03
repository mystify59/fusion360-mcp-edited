"""Body-level operations: rename, visibility, delete, move, rotate."""

import math

import adsk.core

from ..bridge.protocol import ERR_INVALID_PARAMS, OpError
from ._common import op, optional, require


@op("body.rename", summary="Rename a body.", idempotent=True)
def rename(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    new_name = require(params, "name", str)
    body.name = new_name
    return {"name": body.name}


@op("body.set_visible", summary="Show or hide a body.", idempotent=True)
def set_visible(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    visible = bool(require(params, "visible", bool))
    body.isVisible = visible
    return {"name": body.name, "is_visible": body.isVisible}


@op("body.delete", summary="Delete a body.", destructive=True)
def delete(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    name = body.name
    body.deleteMe()
    return {"deleted": name, "remaining_bodies": ctx.target().bRepBodies.count}


@op("body.move", summary="Translate a body by (dx,dy,dz) millimetres.")
def move(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    dx = float(optional(params, "dx", 0.0, types=(int, float)))
    dy = float(optional(params, "dy", 0.0, types=(int, float)))
    dz = float(optional(params, "dz", 0.0, types=(int, float)))
    entities = ctx.collection([body])
    transform = adsk.core.Matrix3D.create()
    transform.translation = adsk.core.Vector3D.create(
        ctx.mm2cm(dx), ctx.mm2cm(dy), ctx.mm2cm(dz)
    )
    move_feats = ctx.target().features.moveFeatures
    move_input = move_feats.createInput(entities, transform)
    move_feats.add(move_input)
    return {"name": body.name, "moved_mm": [dx, dy, dz]}


_AXIS_VECTORS = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}


@op(
    "body.rotate",
    summary=(
        "Rotate a body by angle degrees about an axis ('x'/'y'/'z' or a free "
        "[i,j,k] vector) passing through origin=[x,y,z] mm. Right-hand rule."
    ),
)
def rotate(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    angle = float(require(params, "angle", (int, float)))

    axis_ref = optional(params, "axis", "z", types=(str, list))
    if isinstance(axis_ref, str):
        vec = _AXIS_VECTORS.get(axis_ref.strip().lower())
        if vec is None:
            raise OpError(
                ERR_INVALID_PARAMS, "axis must be 'x', 'y', 'z' or a [i,j,k] vector."
            )
    else:
        if len(axis_ref) != 3 or not all(isinstance(t, (int, float)) for t in axis_ref):
            raise OpError(ERR_INVALID_PARAMS, "axis vector must be [i,j,k] numbers.")
        vec = tuple(float(t) for t in axis_ref)
    if math.sqrt(sum(t * t for t in vec)) < 1e-9:
        raise OpError(ERR_INVALID_PARAMS, "axis vector must not be zero-length.")

    origin = optional(params, "origin", [0.0, 0.0, 0.0], types=list)
    if len(origin) != 3 or not all(isinstance(t, (int, float)) for t in origin):
        raise OpError(ERR_INVALID_PARAMS, "origin must be [x,y,z] millimetres.")

    transform = adsk.core.Matrix3D.create()
    transform.setToRotation(
        math.radians(angle),
        adsk.core.Vector3D.create(*vec),
        # origin is in mm at the API boundary; Fusion's database unit is cm.
        adsk.core.Point3D.create(*[ctx.mm2cm(float(t)) for t in origin]),
    )
    move_feats = ctx.target().features.moveFeatures
    move_feats.add(move_feats.createInput(ctx.collection([body]), transform))
    return {
        "name": body.name,
        "rotated_deg": angle,
        "axis": list(vec),
        "origin_mm": [float(t) for t in origin],
    }


@op("body.combine", summary="Boolean combine a target body with tool body/bodies (join/cut/intersect).", destructive=True)
def combine(ctx, params):
    target = ctx.get_body(require(params, "target", (int, str)))
    tools_ref = require(params, "tools", (int, str, list))
    refs = tools_ref if isinstance(tools_ref, list) else [tools_ref]
    tool_bodies = [ctx.get_body(r) for r in refs]
    op_name = optional(params, "operation", "join", types=str)
    operation = ctx.feature_operation(op_name)
    keep_tools = bool(optional(params, "keep_tools", False, types=bool))

    combines = ctx.target().features.combineFeatures
    combine_input = combines.createInput(target, ctx.collection(tool_bodies))
    combine_input.operation = operation
    combine_input.isKeepToolBodies = keep_tools
    combines.add(combine_input)
    return {
        "feature": "combine",
        "operation": op_name,
        "target": target.name,
        "remaining_bodies": ctx.target().bRepBodies.count,
    }
