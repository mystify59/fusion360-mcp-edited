"""Pure mutation evidence composition for bridge success and error envelopes."""


def mutation_evidence(
    before,
    after,
    requested_edges=None,
    resolved_edges=None,
    target=None,
    radius_mm=None,
    succeeded=True,
):
    before_entities = set((before or {}).get("entities", []))
    after_entities = set((after or {}).get("entities", []))
    residual = sorted(after_entities - before_entities)

    if succeeded:
        rollback = "not_required"
    elif before is None or after is None:
        rollback = "unknown"
    elif before == after:
        rollback = "confirmed"
    else:
        rollback = "incomplete"

    evidence = {
        "state_before": before,
        "state_after": after,
        "residual_entities": residual,
        "rollback": rollback,
    }
    if target is not None:
        evidence["target_after"] = target
    if requested_edges is not None or resolved_edges is not None:
        requested = list(requested_edges or [])
        resolved = list(resolved_edges or [])
        resolved_set = set(resolved)
        evidence["selection"] = {
            "requested_edges": requested,
            "resolved_edges": resolved,
            "edge_resolution": [
                {
                    "requested": edge,
                    "resolved": edge if edge in resolved_set else None,
                    "status": "resolved" if edge in resolved_set else "unresolved",
                }
                for edge in requested
            ],
        }
        if radius_mm is not None:
            evidence["selection"]["radius_mm"] = radius_mm
    return evidence
