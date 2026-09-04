"""Pure geometry formatting helpers shared by Fusion query operations."""


def point_mm(point):
    return [point.x * 10.0, point.y * 10.0, point.z * 10.0]


def midpoint_mm(edge):
    evaluator = edge.evaluator
    ok, start_parameter, _end_parameter = evaluator.getParameterExtents()
    if not ok:
        return None
    ok, parameter = evaluator.getParameterAtLength(start_parameter, edge.length / 2.0)
    if not ok:
        return None
    ok, point = evaluator.getPointAtParameter(parameter)
    return point_mm(point) if ok else None
