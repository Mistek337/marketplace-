"""Разбор query-параметров Catalog API (OpenAPI) для прокси в B2B."""

from __future__ import annotations

import re

from rest_framework.request import Request

_FILTER_PREFIX = re.compile(r"^filter\[(.+)\]$")
_KNOWN_FILTER_KEYS = frozenset(
    {"category_id", "price_min", "price_max", "seller_id", "attributes"}
)

_OPENAPI_TO_B2B_SORT = {
    "price_asc": "price_asc",
    "price_desc": "price_desc",
    "popularity": "popular",
    "new": "created_desc",
}

MIN_SEARCH_LENGTH = 3
MAX_SEARCH_LENGTH = 200


def parse_catalog_list_params(request: Request):
    """
    Возвращает (params_dict, error_message).
    params_dict: limit, offset, search, sort, category_id, seller_id,
                 min_price, max_price, char_filters.
    """
    qp = request.query_params
    try:
        limit = int(qp.get("limit", 20))
        offset = int(qp.get("offset", 0))
    except (TypeError, ValueError):
        return None, "Invalid pagination parameters"

    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    search = (qp.get("q") or "").strip() or None
    if search is not None:
        if len(search) < MIN_SEARCH_LENGTH:
            return None, (
                f"Search query must be at least {MIN_SEARCH_LENGTH} characters"
            )
        if len(search) > MAX_SEARCH_LENGTH:
            search = search[:MAX_SEARCH_LENGTH]

    sort_raw = qp.get("sort") or "popularity"
    if sort_raw not in _OPENAPI_TO_B2B_SORT:
        return None, (
            "sort must be one of: price_asc, price_desc, popularity, new"
        )
    sort = _OPENAPI_TO_B2B_SORT[sort_raw]

    category_id = qp.get("category_id")
    seller_id = qp.get("seller_id")
    min_price = qp.get("min_price")
    max_price = qp.get("max_price")
    char_filters: dict[str, list[str]] = {}

    for key in qp.keys():
        match = _FILTER_PREFIX.match(key)
        if not match:
            continue
        name = match.group(1)
        values = [v for v in qp.getlist(key) if v is not None and str(v) != ""]
        if not values:
            continue
        if name == "category_id":
            category_id = values[-1]
        elif name == "price_min":
            min_price = values[-1]
        elif name == "price_max":
            max_price = values[-1]
        elif name == "seller_id":
            seller_id = values[-1]
        elif name not in _KNOWN_FILTER_KEYS:
            char_filters[name] = values

    return (
        {
            "limit": limit,
            "offset": offset,
            "search": search,
            "sort": sort,
            "category_id": category_id,
            "seller_id": seller_id,
            "min_price": min_price,
            "max_price": max_price,
            "char_filters": char_filters,
        },
        None,
    )
