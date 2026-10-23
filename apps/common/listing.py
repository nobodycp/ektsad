def _positive_int(value, default):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def paginate(queryset, params):
    page = _positive_int(params.get("page"), 1)
    page_size = min(_positive_int(params.get("page_size"), 20), 100)
    ordering = params.get("ordering")
    if ordering:
        queryset = queryset.order_by(ordering)
    count = queryset.count()
    start = (page - 1) * page_size
    return {
        "count": count,
        "page": page,
        "page_size": page_size,
        "results": list(queryset[start : start + page_size]),
    }
