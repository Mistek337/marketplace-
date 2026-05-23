"""Расчёт фасетов каталога по данным B2B (прокси + агрегация на стороне B2C)."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from django.utils.text import slugify

from .b2b_client import B2BClient


def _attr_key(name: str) -> str:
    return slugify(name, allow_unicode=True) or name.strip().lower()


def _list_products_for_facets(client: B2BClient, params: dict) -> tuple[list[dict], int]:
    """Берём до 100 карточек с текущими фильтрами (кроме пагинации листинга)."""
    data = client.get_products(
        limit=100,
        offset=0,
        category_id=params.get("category_id"),
        seller_id=params.get("seller_id"),
        min_price=params.get("min_price"),
        max_price=params.get("max_price"),
        char_filters=params.get("char_filters"),
        sort=params.get("sort"),
        search=params.get("search"),
    )
    items = data.get("items", []) if isinstance(data, dict) else []
    total = int(data.get("total_count", len(items))) if isinstance(data, dict) else 0
    return [row for row in items if isinstance(row, dict)], total


def _enrich_with_characteristics(client: B2BClient, product_ids: list[str]) -> list[dict]:
    if not product_ids:
        return []
    batch = client.batch_public_products(product_ids)
    return batch if isinstance(batch, list) else []


def build_catalog_facets(client: B2BClient, params: dict) -> dict[str, Any]:
    """
    Фасеты по выборке, согласованной с текущими фильтрами листинга.
    category_id и динамические attributes — подсчёты по видимым товарам.
    """
    items, total_count = _list_products_for_facets(client, params)
    product_ids = [str(row["id"]) for row in items if row.get("id")]
    full_products = _enrich_with_characteristics(client, product_ids)
    by_id = {str(p["id"]): p for p in full_products if isinstance(p, dict) and p.get("id")}

    category_counts: Counter[str] = Counter()
    attribute_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for row in items:
        pid = str(row.get("id", ""))
        product = by_id.get(pid, row)
        category_id = product.get("category_id") or row.get("category_id")
        if category_id:
            category_counts[str(category_id)] += 1

        for ch in product.get("characteristics") or []:
            if not isinstance(ch, dict):
                continue
            key = _attr_key(str(ch.get("name") or ""))
            value = str(ch.get("value") or "").strip()
            if key and value:
                attribute_counts[key][value] += 1

    facets: dict[str, Any] = {
        "total_count": total_count,
        "category_id": [
            {"value": value, "count": count}
            for value, count in sorted(category_counts.items(), key=lambda x: (-x[1], x[0]))
        ],
        "attributes": {
            name: [
                {"value": value, "count": count}
                for value, count in sorted(counter.items(), key=lambda x: (-x[1], x[0]))
            ]
            for name, counter in sorted(attribute_counts.items())
        },
    }
    return facets
