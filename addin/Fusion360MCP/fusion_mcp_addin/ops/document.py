"""Document-level operations: create / inspect / save / close.

**Workspace discipline.** Every task should run in the document the user already
has open: a pile of stray "Untitled" documents is a mess only the user can clean
up by hand. So building ops target the *active* document (see ``Ctx.target()``
for multi-part-in-one-document), and ``document.new`` is **guarded** — it refuses
while another document is open unless the caller passes ``confirm=true`` (i.e.
the user actually asked for a new project). Disable the guard with the
``guard_new_document`` setting.

**Closing.** ``document.close`` takes an explicit ``save`` flag: save-then-close
or discard-and-close. Saving is done by us *before* closing (never via
``close(True)``) because a never-saved document makes Fusion raise a modal Save
dialog — which the external dialog guard would cancel, and which freezes the
whole bridge while it is up. ``document.save``/``document.close(save=true)``
therefore fall back to ``saveAs`` into a data folder for never-saved documents.
"""

import adsk.core

from ._common import RUNTIME, op, optional, require
from ..bridge.protocol import ERR_INTERNAL, ERR_NOT_ALLOWED, ERR_NOT_FOUND, OpError


# --- helpers -----------------------------------------------------------------
def _active_doc(ctx):
    """The active document, or None (accessing it with nothing open can raise)."""
    try:
        return ctx.app.activeDocument
    except Exception:
        return None


def _open_docs(ctx):
    app = ctx.app
    try:
        return [app.documents.item(i) for i in range(app.documents.count)]
    except Exception:
        return []


def _resolve_doc(ctx, params):
    """The document named by ``params['document']``, else the active one."""
    name = optional(params, "document", None, types=str)
    if not name:
        doc = _active_doc(ctx)
        if doc is None:
            raise OpError(
                ERR_NOT_FOUND,
                "No open document. / 没有打开的文档。",
            )
        return doc
    for d in _open_docs(ctx):
        if d.name == name:
            return d
    raise OpError(
        ERR_NOT_FOUND,
        "No open document named '{}'. List them with document.list. "
        "/ 未找到名为 '{}' 的打开文档，请先用 document.list 查看。".format(name, name),
    )


def _never_saved(doc):
    """True when the document has no cloud DataFile yet (first save pending)."""
    try:
        if doc.isSaved:
            return False
    except Exception:
        pass
    try:
        return doc.dataFile is None
    except Exception:
        return True


# Names Fusion gives the project it creates for a new hub, per UI language.
_DEFAULT_PROJECT_NAMES = ("Default Project", "默认项目", "既定專案", "预设项目")


def _all_projects(ctx):
    try:
        collection = ctx.app.data.dataProjects
        return [collection.item(i) for i in range(collection.count)]
    except Exception:
        return []


def _default_project(ctx):
    """The project to save a never-saved document into.

    ``Data.activeProject`` is the right answer but it raises
    ("InternalValidationError : group") on some accounts, so fall back to the
    project the user's other open documents live in, then to the only / the
    default-named project. Returns None when nothing can be picked.
    """
    try:
        proj = ctx.app.data.activeProject
        if proj is not None:
            return proj
    except Exception:
        pass

    for doc in _open_docs(ctx):
        try:
            data_file = doc.dataFile
            if data_file is not None and data_file.parentProject is not None:
                return data_file.parentProject
        except Exception:
            continue

    projects = _all_projects(ctx)
    if len(projects) == 1:
        return projects[0]
    for proj in projects:
        try:
            if proj.name in _DEFAULT_PROJECT_NAMES:
                return proj
        except Exception:
            continue
    return None


def _data_folder(ctx, project=None):
    """(DataFolder, project_name) to Save As into: a named project or the default one."""
    if project:
        proj = None
        for candidate in _all_projects(ctx):
            if candidate.name == project:
                proj = candidate
                break
        if proj is None:
            raise OpError(
                ERR_NOT_FOUND,
                "No Fusion project named '{}'. List them with document.projects. "
                "/ 未找到名为 '{}' 的项目，可用 document.projects 查看。".format(project, project),
            )
    else:
        proj = _default_project(ctx)
    if proj is None:
        names = []
        for candidate in _all_projects(ctx):
            try:
                names.append(candidate.name)
            except Exception:
                pass
        raise OpError(
            ERR_INTERNAL,
            "Could not pick a project to save into — pass `project` explicitly "
            "(available: {}). / 无法确定要保存到哪个项目，请显式指定 project（可选：{}）。".format(
                ", ".join(names) or "none", ", ".join(names) or "无"
            ),
        )
    return proj.rootFolder, proj.name


def _save_doc(ctx, doc, description="", name=None, project=None, force_save_as=False):
    """Save ``doc``, falling back to Save As for a never-saved document.

    Returns a result dict; raises OpError if nothing could be written (callers
    must NOT close the document in that case — that would lose the user's work).
    """
    description = description or ""
    if not force_save_as and not _never_saved(doc):
        try:
            modified = bool(doc.isModified)
        except Exception:
            modified = True
        if not modified and not name:
            return {"saved": True, "method": "unchanged", "document": doc.name}
        try:
            if doc.save(description):
                return {"saved": True, "method": "save", "document": doc.name}
            detail = "Document.save() returned false"
        except Exception as exc:  # noqa: BLE001
            detail = str(exc)
        raise OpError(
            ERR_INTERNAL,
            "Could not save '{}'. / 保存 '{}' 失败。".format(doc.name, doc.name),
            detail,
        )

    # Never saved (or an explicit Save As): write it into a data folder ourselves
    # so Fusion never has to raise its blocking Save dialog.
    folder, proj_name = _data_folder(ctx, project)
    target_name = name or doc.name
    try:
        done = doc.saveAs(target_name, folder, description, "")
    except Exception as exc:  # noqa: BLE001
        raise OpError(
            ERR_INTERNAL,
            "Save As failed for '{}' into project '{}'. / 另存 '{}' 到项目 '{}' 失败。".format(
                target_name, proj_name, target_name, proj_name
            ),
            str(exc),
        )
    if not done:
        raise OpError(
            ERR_INTERNAL,
            "Fusion refused to save '{}' into project '{}' (name already taken?). "
            "/ Fusion 拒绝把 '{}' 保存到项目 '{}'（可能重名）。".format(
                target_name, proj_name, target_name, proj_name
            ),
        )
    return {
        "saved": True,
        "method": "save_as",
        "document": doc.name,
        "project": proj_name,
    }


def _forget_target_component():
    """Drop the sticky active component: it belonged to the document we just left."""
    RUNTIME.pop("target_component", None)


def _doc_brief(ctx, doc):
    try:
        active = _active_doc(ctx)
        is_active = bool(active is not None and doc == active)
    except Exception:
        is_active = False
    out = {"name": doc.name, "is_active": is_active}
    for key, attr in (("is_modified", "isModified"), ("is_saved", "isSaved")):
        try:
            out[key] = bool(getattr(doc, attr))
        except Exception:
            out[key] = None
    return out


# --- ops ---------------------------------------------------------------------
@op(
    "document.new",
    summary=(
        "Create a NEW empty design document. GUARDED: refuses while another document is "
        "open unless confirm=true — work in the already-open document instead."
    ),
    params=[
        {"name": "confirm", "type": "bool", "required": False,
         "description": "Required (true) when a document is already open."},
    ],
)
def new_document(ctx, params):
    confirm = optional(params, "confirm", False, types=bool)
    from .. import config as _config

    open_docs = _open_docs(ctx)
    guard = bool(_config.get_settings().get("guard_new_document", True))
    if open_docs and guard and not confirm:
        names = ", ".join(d.name for d in open_docs[:5])
        raise OpError(
            ERR_NOT_ALLOWED,
            "A document is already open ({}) — do the work THERE instead of opening "
            "another one. Multi-part models belong in ONE document: give each part its "
            "own component (assembly.create_component). Only pass confirm=true if the "
            "user explicitly asked for a new document/project. "
            "/ 已有打开的文档（{}），请直接在其中工作，不要另开文档。多零件应放在同一文档的"
            "不同组件里（assembly.create_component）。只有用户明确要求新建时才传 confirm=true。".format(
                names, names
            ),
            "open_documents={}".format(len(open_docs)),
        )

    doc = ctx.app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    _forget_target_component()
    return {"document": doc.name, "open_documents": ctx.app.documents.count}


@op(
    "document.info",
    summary="Summarize the active document: units, object counts, and save state.",
    readonly=True,
)
def info(ctx, params):
    design = ctx.design()
    root = design.rootComponent
    doc = _active_doc(ctx)
    out = {
        "document": doc.name if doc else None,
        "units": design.fusionUnitsManager.defaultLengthUnits,
        "bodies": root.bRepBodies.count,
        "components": design.allComponents.count,
        "sketches": root.sketches.count,
        "parameters": design.allParameters.count,
        "is_modified": bool(doc.isModified) if doc else None,
        "open_documents": ctx.app.documents.count,
        "active_component": RUNTIME.get("target_component") or root.name,
    }
    try:
        out["is_saved"] = bool(doc.isSaved) if doc else None
    except Exception:
        out["is_saved"] = None
    return out


@op(
    "document.list",
    summary="List all open documents with their active / modified / saved state.",
    readonly=True,
)
def list_documents(ctx, params):
    docs = [_doc_brief(ctx, d) for d in _open_docs(ctx)]
    return {"documents": docs, "count": len(docs)}


@op(
    "document.projects",
    summary=(
        "List the Fusion projects a document can be saved into, and which one is active "
        "(the default target of document.save / save_as)."
    ),
    readonly=True,
)
def projects(ctx, params):
    data = ctx.app.data
    try:
        collection = data.dataProjects
        names = [collection.item(i).name for i in range(collection.count)]
    except Exception as exc:  # noqa: BLE001
        raise OpError(
            ERR_INTERNAL,
            "Could not list projects (Fusion may be offline / signed out). "
            "/ 无法列出项目（Fusion 可能离线或未登录）。",
            str(exc),
        )
    active, detail = None, None
    try:
        proj = data.activeProject
        active = proj.name if proj else None
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)

    out = {"projects": names, "count": len(names), "active": active}
    if active is None:
        # Fusion raises here on some accounts ("InternalValidationError : group"),
        # so report why and which project a save would actually land in.
        out["active_error"] = detail or "activeProject is None"
    fallback = _default_project(ctx)
    try:
        out["save_target"] = fallback.name if fallback else None
    except Exception:
        out["save_target"] = None
    return out


@op(
    "document.save",
    summary=(
        "Save the active document. A never-saved document is written into the active "
        "Fusion project (no interactive dialog needed)."
    ),
    idempotent=True,
    params=[
        {"name": "description", "type": "str", "required": False},
        {"name": "document", "type": "str", "required": False,
         "description": "Name of an open document; defaults to the active one."},
        {"name": "name", "type": "str", "required": False,
         "description": "File name for a first save / Save As."},
        {"name": "project", "type": "str", "required": False,
         "description": "Fusion project to save into; defaults to the active project."},
    ],
)
def save(ctx, params):
    doc = _resolve_doc(ctx, params)
    return _save_doc(
        ctx,
        doc,
        description=optional(params, "description", "", types=str),
        name=optional(params, "name", None, types=str),
        project=optional(params, "project", None, types=str),
    )


@op(
    "document.save_as",
    summary="Save the active document as a NEW file (name, optionally in a given project).",
    params=[
        {"name": "name", "type": "str", "required": True},
        {"name": "project", "type": "str", "required": False},
        {"name": "description", "type": "str", "required": False},
        {"name": "document", "type": "str", "required": False},
    ],
)
def save_as(ctx, params):
    doc = _resolve_doc(ctx, params)
    return _save_doc(
        ctx,
        doc,
        description=optional(params, "description", "", types=str),
        name=require(params, "name", str),
        project=optional(params, "project", None, types=str),
        force_save_as=True,
    )


@op(
    "document.close",
    summary=(
        "Close a document. save=true saves it first (Save As into the active project if "
        "it was never saved); save=false discards unsaved changes. Destructive."
    ),
    destructive=True,
    params=[
        {"name": "save", "type": "bool", "required": True,
         "description": "true = save then close; false = close WITHOUT saving."},
        {"name": "document", "type": "str", "required": False,
         "description": "Name of an open document; defaults to the active one."},
        {"name": "description", "type": "str", "required": False},
        {"name": "name", "type": "str", "required": False,
         "description": "File name to use if a first save / Save As is needed."},
        {"name": "project", "type": "str", "required": False},
    ],
)
def close(ctx, params):
    save_first = require(params, "save", bool)
    doc = _resolve_doc(ctx, params)
    name = doc.name
    try:
        was_active = bool(doc.isActive)
    except Exception:
        was_active = True

    save_result = None
    if save_first:
        # Raises on failure — we must NOT close an unsaved document then.
        save_result = _save_doc(
            ctx,
            doc,
            description=optional(params, "description", "", types=str),
            name=optional(params, "name", None, types=str),
            project=optional(params, "project", None, types=str),
        )

    try:
        # Always close(False): the save (if any) already happened above, and
        # close(True) on a never-saved document raises a blocking modal.
        doc.close(False)
    except Exception as exc:  # noqa: BLE001
        raise OpError(
            ERR_INTERNAL,
            "Could not close '{}'. / 关闭 '{}' 失败。".format(name, name),
            str(exc),
        )

    if was_active:
        _forget_target_component()
    active = _active_doc(ctx)
    return {
        "closed": name,
        "saved": bool(save_first),
        "save": save_result,
        "remaining": ctx.app.documents.count,
        "active": active.name if active else None,
    }


@op(
    "document.close_others",
    summary=(
        "Close every open document EXCEPT the active one. save=false (default) discards "
        "their unsaved changes. Destructive."
    ),
    destructive=True,
    params=[
        {"name": "save", "type": "bool", "required": False,
         "description": "true = save each document before closing it (default false)."},
    ],
)
def close_others(ctx, params):
    save_first = optional(params, "save", False, types=bool)
    app = ctx.app
    active = _active_doc(ctx)
    if active is None:
        return {"closed": 0, "remaining": app.documents.count, "kept": None}

    # Snapshot references up front (the collection re-indexes as we close).
    docs = _open_docs(ctx)

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

    closed, failed = [], []
    for d in to_close:
        name = d.name
        try:
            if save_first:
                _save_doc(ctx, d)
            d.close(False)   # False = do not save changes
            closed.append(name)
        except Exception as exc:  # noqa: BLE001
            failed.append({"document": name, "detail": str(exc)})
    return {
        "closed": len(closed),
        "documents": closed,
        "failed": failed,
        "saved": bool(save_first),
        "remaining": app.documents.count,
        "kept": active.name,
    }
