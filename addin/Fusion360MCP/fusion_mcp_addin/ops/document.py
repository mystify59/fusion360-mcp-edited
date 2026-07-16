"""Document-level operations: create / inspect / save / list."""

import adsk.core

from ._common import op, optional
from ..bridge.protocol import ERR_INTERNAL, OpError


@op(
    "document.new",
    summary="Create a new, empty Fusion design document and make it active.",
    params=[],
)
def new_document(ctx, params):
    doc = ctx.app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    return {"document": doc.name}


@op(
    "document.info",
    summary="Summarize the active document: units and object counts.",
    readonly=True,
)
def info(ctx, params):
    design = ctx.design()
    root = design.rootComponent
    return {
        "document": ctx.app.activeDocument.name if ctx.app.activeDocument else None,
        "units": design.fusionUnitsManager.defaultLengthUnits,
        "bodies": root.bRepBodies.count,
        "components": design.allComponents.count,
        "sketches": root.sketches.count,
        "parameters": design.allParameters.count,
        "is_modified": bool(ctx.app.activeDocument.isModified)
        if ctx.app.activeDocument
        else None,
    }


@op(
    "document.list",
    summary="List the names of all currently open documents.",
    readonly=True,
)
def list_documents(ctx, params):
    return {"documents": [d.name for d in ctx.app.documents]}


@op(
    "document.close_others",
    summary="Close every open document EXCEPT the active one, discarding unsaved changes. Destructive.",
    destructive=True,
)
def close_others(ctx, params):
    app = ctx.app
    active = app.activeDocument
    if active is None:
        return {"closed": 0, "remaining": app.documents.count, "kept": None}

    # Snapshot references up front (the collection re-indexes as we close).
    docs = [app.documents.item(i) for i in range(app.documents.count)]

    # `d is active` is WRONG: app.documents.item(i) hands back a fresh Python
    # wrapper each call, so identity never matches and the active doc gets closed
    # too (this once closed EVERY document). Fusion API objects compare the
    # underlying object with `==`. As a safety net, if nothing matches the active
    # doc — which would mean we're about to close everything — refuse instead.
    to_close = [d for d in docs if not (d == active)]
    if docs and len(to_close) == len(docs):
        raise OpError(
            ERR_INTERNAL,
            "Refusing to close: could not identify the active document, which would "
            "close everything. / 无法识别活动文档，已中止以免全部关闭。",
        )

    closed = 0
    for d in to_close:
        try:
            d.close(False)   # False = do not save changes
            closed += 1
        except Exception:
            pass
    return {"closed": closed, "remaining": app.documents.count, "kept": active.name}


@op(
    "document.save",
    summary="Save the active document (must already have been saved once).",
    idempotent=True,
)
def save(ctx, params):
    description = optional(params, "description", "", types=str)
    doc = ctx.app.activeDocument
    if doc is None:
        return {"saved": False, "reason": "no active document"}
    try:
        doc.save(description or "")
        return {"saved": True, "document": doc.name}
    except Exception as exc:
        # Never-saved docs require an interactive Save As into a data folder.
        return {
            "saved": False,
            "reason": "First save must be done in Fusion (choose a project folder). "
            "/ 首次保存需在 Fusion 中手动选择项目文件夹。",
            "detail": str(exc),
        }
