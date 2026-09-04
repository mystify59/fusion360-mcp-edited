"""Body tools."""

from typing import Optional, Union

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno(idempotent=True))
    def fusion_rename_body(body: Union[int, str], name: str) -> dict:
        """Rename a body."""
        return client.call("body.rename", {"body": body, "name": name})

    @mcp.tool(annotations=anno(idempotent=True))
    def fusion_set_body_visible(body: Union[int, str], visible: bool) -> dict:
        """Show or hide a body."""
        return client.call("body.set_visible", {"body": body, "visible": visible})

    @mcp.tool(annotations=anno(destructive=True))
    def fusion_delete_body(body: Union[int, str]) -> dict:
        """Delete exactly one body and verify the resulting model state. Destructive.
        This does not delete sketches, features, or construction geometry."""
        return client.call("body.delete", {"body": body})

    @mcp.tool(annotations=anno())
    def fusion_move_body(
        body: Union[int, str], dx: float = 0.0, dy: float = 0.0, dz: float = 0.0
    ) -> dict:
        """Translate a body by (dx, dy, dz) millimetres."""
        return client.call("body.move", {"body": body, "dx": dx, "dy": dy, "dz": dz})

    @mcp.tool(annotations=anno())
    def fusion_rotate_body(
        body: Union[int, str],
        angle: float,
        axis: Union[str, list] = "z",
        origin: Optional[list] = None,
    ) -> dict:
        """Rotate a body by `angle` degrees (right-hand rule) about an axis through
        a point. axis: "x"/"y"/"z" or a free direction vector [i, j, k].
        origin: [x, y, z] in millimetres, defaults to the world origin. Use this to
        build inclined geometry that revolve/extrude alone cannot produce."""
        return client.call(
            "body.rotate",
            {
                "body": body,
                "angle": angle,
                "axis": axis,
                "origin": origin if origin is not None else [0.0, 0.0, 0.0],
            },
        )

    @mcp.tool(annotations=anno(destructive=True))
    def fusion_combine(
        target: Union[int, str],
        tools: Union[int, str, list],
        operation: str = "join",
        keep_tools: bool = False,
    ) -> dict:
        """Boolean-combine a target body with one or more tool bodies (by index or
        name). operation: join (union), cut (subtract tools from target), or
        intersect. Set keep_tools=true to preserve the tool bodies."""
        return client.call(
            "body.combine",
            {"target": target, "tools": tools, "operation": operation, "keep_tools": keep_tools},
        )
