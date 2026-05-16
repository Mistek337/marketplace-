"""Контракт OpenAPI (тег Cart): схемы и допустимые HTTP-коды."""

CART_RESPONSE_REQUIRED = frozenset({"items", "items_count", "subtotal", "is_valid"})

CART_ITEM_REQUIRED = frozenset(
    {
        "sku_id",
        "product_id",
        "name",
        "quantity",
        "unit_price",
        "line_total",
        "available_quantity",
        "is_available",
    }
)

CART_VALIDATION_ISSUE_TYPES = frozenset(
    {
        "PRICE_CHANGED",
        "OUT_OF_STOCK",
        "QUANTITY_REDUCED",
        "PRODUCT_BLOCKED",
        "PRODUCT_DELETED",
    }
)

CART_VALIDATION_RESPONSE_REQUIRED = frozenset({"is_valid", "cart", "issues"})

# Только коды, перечисленные в paths.*.responses для Cart
ALLOWED_STATUS = {
    "get_cart": frozenset({200}),
    "delete_cart": frozenset({204}),
    "post_items": frozenset({200, 400, 404, 409}),
    "patch_item": frozenset({200, 409}),
    "delete_item": frozenset({200}),
    "post_validate": frozenset({200}),
    "post_merge": frozenset({200, 401}),
}
