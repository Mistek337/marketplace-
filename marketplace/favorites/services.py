from django.conf import settings

from catalog.b2b_client import B2BClient, B2BClientError
from catalog.api_errors import catalog_not_found
from catalog.openapi_catalog import to_catalog_product_card

from .openapi import ALLOWED_SUBSCRIBE_EVENTS, DEFAULT_SUBSCRIBE_EVENTS


def parse_pagination(request):
    try:
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))
    except (TypeError, ValueError):
        limit, offset = 20, 0
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    return limit, offset


def is_visible_product(product: dict) -> bool:
    if getattr(settings, "CATALOG_DEV_VISIBILITY", False):
        return not bool(product.get("deleted", False))
    return product.get("status") == "MODERATED" and not bool(product.get("deleted", False))


def parse_subscribe_events(request):
    """OpenAPI: default [BACK_IN_STOCK, PRICE_DROP]; только допустимые enum."""
    raw = request.data.get("events") if hasattr(request, "data") else None
    if not raw:
        return list(DEFAULT_SUBSCRIBE_EVENTS)
    if not isinstance(raw, list):
        return list(DEFAULT_SUBSCRIBE_EVENTS)
    events = []
    for item in raw:
        if item in ALLOWED_SUBSCRIBE_EVENTS and item not in events:
            events.append(item)
    return events or list(DEFAULT_SUBSCRIBE_EVENTS)


def fetch_visible_product(product_id):
    client = B2BClient()
    try:
        product = client.get_product(product_id)
    except B2BClientError:
        return None, catalog_not_found()
    if not is_visible_product(product):
        return None, catalog_not_found()
    return product, None


def _load_categories(client: B2BClient):
    try:
        return client.get_categories()
    except B2BClientError:
        return []


def visible_cards_by_product_id(product_ids: list[str]) -> dict[str, dict]:
    """Batch B2B → видимые CatalogProductCard по product_id."""
    if not product_ids:
        return {}

    client = B2BClient()
    try:
        pool = client.batch_public_products(product_ids)
    except B2BClientError:
        pool = []

    categories = _load_categories(client)
    cards = {}
    for row in pool if isinstance(pool, list) else []:
        if not isinstance(row, dict) or not is_visible_product(row):
            continue
        product_id = str(row.get("id") or "")
        if product_id:
            cards[product_id] = to_catalog_product_card(row, categories_flat=categories)
    return cards


def build_favorites_list_response(user, *, limit: int, offset: int) -> dict:
    """
    PaginatedCatalogProducts:
    - items — карточки видимых товаров на странице (порядок избранного);
    - total_count — только товары, доступные в B2B (MODERATED, не deleted).
    """
    all_ids = [str(pid) for pid in user.favorites.values_list("product_id", flat=True)]
    visible_cards = visible_cards_by_product_id(all_ids)
    total_count = len(visible_cards)

    page_rows = list(user.favorites.all()[offset : offset + limit])
    items = []
    for row in page_rows:
        card = visible_cards.get(str(row.product_id))
        if card is not None:
            items.append(card)

    return {
        "items": items,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
    }
