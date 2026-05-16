"""Контракт OpenAPI (тег Catalog): карточка товара."""

B2C_FORBIDDEN_SKU_FIELDS = frozenset({"cost_price", "reserved_quantity"})

CATALOG_PRODUCT_CARD_REQUIRED = frozenset(
    {"id", "name", "min_price", "has_stock", "images"}
)

CATALOG_PRODUCT_DETAIL_REQUIRED = CATALOG_PRODUCT_CARD_REQUIRED | frozenset(
    {"description", "skus"}
)

CATEGORY_REF_REQUIRED = frozenset({"id", "name", "level", "path"})

IMAGE_REF_REQUIRED = frozenset({"id", "url", "ordering"})

CATALOG_SKU_REQUIRED = frozenset({"id", "price", "available_quantity"})

PAGINATED_CATALOG_REQUIRED = frozenset({"items", "total_count", "limit", "offset"})

ALLOWED_STATUS = {
    "get_product_detail": frozenset({200, 404}),
    "get_products_list": frozenset({200, 400, 422}),
    "get_similar": frozenset({200}),
}
