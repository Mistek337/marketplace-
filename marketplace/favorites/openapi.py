"""Контракт OpenAPI (тег Favorites)."""

PAGINATED_CATALOG_REQUIRED = frozenset({"items", "total_count", "limit", "offset"})

ALLOWED_SUBSCRIBE_EVENTS = frozenset({"BACK_IN_STOCK", "PRICE_DROP"})
DEFAULT_SUBSCRIBE_EVENTS = ["BACK_IN_STOCK", "PRICE_DROP"]

ALLOWED_STATUS = {
    "get_favorites": frozenset({200, 401}),
    "put_favorite": frozenset({204, 401, 404}),
    "delete_favorite": frozenset({204, 401}),
    "post_subscribe": frozenset({204, 401, 404}),
    "delete_subscribe": frozenset({204, 401}),
}
