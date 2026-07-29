"""Build the FastMCP application and wire in the tools."""

import logging
import sys

from mcp.server.fastmcp import FastMCP

from .client import AddinClient
from .config import ServerConfig
from .tools import register_all

INSTRUCTIONS = """Drive Autodesk Fusion 360 through natural language.

Workspace discipline (important):
- Work in the document the user ALREADY has open. Do NOT open a new document per
  part or per task: stray documents pile up and only the user can close them by
  hand. fusion_new_document refuses while a document is open unless you pass
  confirm=true, which you should only do when the user explicitly asked for a new
  document/project.
- Several parts belong in ONE document, each as its own component
  (fusion_create_component + fusion_set_active_component). Before adding a part,
  check what is already there (fusion_summary, fusion_list_bodies,
  fusion_bounding_box) and place the new one clear of the existing geometry — never
  modify or delete the user's existing bodies unless asked.
- To finish up: fusion_save_document (or fusion_save_document_as to keep the
  original untouched), fusion_close_document(save=true/false) to save-and-close or
  discard-and-close, fusion_close_other_documents to tidy up leftovers.

Conventions:
- ALL distances are millimetres (mm); angles are degrees. Pass values literally.
- You do NOT need a document open: with nothing open, build tools (fusion_box/
  cylinder/sphere, fusion_create_sketch, fusion_sketch_*) auto-create one.
- For simple solids prefer the one-call primitives: fusion_box, fusion_cylinder,
  fusion_sphere. For custom shapes: sketch (fusion_sketch_*) -> fusion_extrude/
  revolve/sweep/loft -> modify (fusion_fillet/chamfer/shell/pattern/combine).
- Reference bodies/sketches by index or name — inspect with fusion_summary,
  fusion_list_bodies, fusion_list_sketches. Name important bodies (fusion_rename_body).
- Mutating tools return a `_delta` (bodies_before/after/added) so you can confirm
  an op took effect without a screenshot.
- Prefer parameters (fusion_create_parameter / fusion_set_parameter) for any
  dimension you might revise; it makes later edits robust.
- After building, verify visually with fusion_screenshot — CAD precision matters
  (a 0.1 mm error breaks a fit).
"""


def setup_logging(config: ServerConfig):
    # IMPORTANT: stdio transport uses stdout for the JSON-RPC stream, so every
    # log line MUST go to stderr or it corrupts the protocol.
    level = getattr(logging, str(config.log_level).upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        stream=sys.stderr,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


def build_app(config: ServerConfig):
    """Return (FastMCP app, AddinClient)."""
    setup_logging(config)
    mcp = FastMCP(
        "Fusion360 MCP",
        instructions=INSTRUCTIONS,
        host=config.http_host,
        port=config.http_port,
    )
    client = AddinClient(config)
    register_all(mcp, client, config)
    logging.getLogger("fusion_mcp").info(
        "Server ready (transport=%s, addin=%s, mock=%s, arbitrary_code=%s)",
        config.transport,
        config.addin_url,
        config.mock,
        config.allow_arbitrary_code,
    )
    return mcp, client
