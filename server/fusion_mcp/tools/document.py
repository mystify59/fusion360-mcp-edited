"""Document tools: create / inspect / save / close.

Work in the document the user already has open — see ``fusion_new_document``.
"""

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno())
    def fusion_new_document(confirm: bool = False) -> dict:
        """Create a NEW empty Fusion design document.

        Prefer NOT calling this. If a document is already open, build in THAT one —
        several parts belong in ONE document as separate components
        (fusion_create_component). Stray documents pile up and only the user can
        close them by hand.

        Set confirm=true only when the user explicitly asked for a new
        document/project, or when nothing is open at all (then it is a no-op flag).
        Without confirm the call is refused while any document is open.
        """
        return client.call("document.new", {"confirm": confirm})

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_document_info() -> dict:
        """Summarize the active document: display units, counts of bodies,
        components, sketches and parameters, save state, and the active component."""
        return client.call("document.info")

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_list_documents() -> dict:
        """List all open Fusion documents with their active / modified / saved state."""
        return client.call("document.list")

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_list_projects() -> dict:
        """List the Fusion projects a document can be saved into, and which one is
        active (where fusion_save_document / _as put a never-saved document)."""
        return client.call("document.projects")

    @mcp.tool(annotations=anno(idempotent=True))
    def fusion_save_document(
        description: str = "",
        document: str = "",
        name: str = "",
        project: str = "",
    ) -> dict:
        """Save a document (the active one unless `document` names another open one).

        A never-saved document is saved into the active Fusion project automatically
        (optionally under `name` / into `project`), so no interactive dialog is needed.
        """
        payload = {"description": description}
        if document:
            payload["document"] = document
        if name:
            payload["name"] = name
        if project:
            payload["project"] = project
        return client.call("document.save", payload)

    @mcp.tool(annotations=anno())
    def fusion_save_document_as(
        name: str,
        project: str = "",
        description: str = "",
        document: str = "",
    ) -> dict:
        """Save a document as a NEW file called `name` (in `project`, else the active
        project). Use this to keep the original untouched."""
        payload = {"name": name, "description": description}
        if project:
            payload["project"] = project
        if document:
            payload["document"] = document
        return client.call("document.save_as", payload)

    @mcp.tool(annotations=anno(destructive=True))
    def fusion_close_document(
        save: bool,
        document: str = "",
        name: str = "",
        project: str = "",
        description: str = "",
    ) -> dict:
        """Close a document — save=true saves it first, save=false discards unsaved
        changes.

        Closes the active document unless `document` names another open one. With
        save=true a never-saved document is written into the active Fusion project
        first (use `name` / `project` to choose where); if that save fails the
        document is left open rather than losing the work.
        """
        payload = {"save": save, "description": description}
        if document:
            payload["document"] = document
        if name:
            payload["name"] = name
        if project:
            payload["project"] = project
        return client.call("document.close", payload)

    @mcp.tool(annotations=anno(destructive=True))
    def fusion_close_other_documents(save: bool = False) -> dict:
        """Close every open document EXCEPT the active one — handy for tidying up
        after stray documents accumulated. save=false discards their unsaved changes."""
        return client.call("document.close_others", {"save": save})
