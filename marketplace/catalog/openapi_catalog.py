"""Маппинг B2B ProductPublic → OpenAPI CatalogProductDetail."""

from __future__ import annotations

import uuid

from django.conf import settings

from .openapi import B2C_FORBIDDEN_SKU_FIELDS


def _product_category_id(product):
    category_id = product.get("category_id")
    if category_id is not None:
        return category_id
    return (product.get("category") or {}).get("id")


def _b2c_product_slug(product: dict) -> str:
    from django.utils.text import slugify

    slug = product.get("slug")
    if slug:
        return str(slug)
    title = product.get("title") or product.get("name") or "product"
    base = slugify(str(title))[:200] or "product"
    pid = str(product.get("id") or "")
    suffix = pid.replace("-", "")[:8] if pid else "item"
    return f"{base}-{suffix}".strip("-")

B2C_FORBIDDEN_PRODUCT_FIELDS = frozenset(
    {
        "status",
        "deleted",
        "seller_id",
        "created_at",
        "updated_at",
        "title",
        "characteristics",
        "category_id",
    }
)


def _placeholder_url() -> str:
    return getattr(
        settings,
        "B2C_IMAGE_PLACEHOLDER",
        "https://via.placeholder.com/320x320?text=No+Image",
    )


def _characteristics_to_attributes(rows) -> dict:
    attrs = {}
    for row in rows or []:
        name = row.get("name")
        if not name:
            continue
        attrs[str(name)] = row.get("value")
    return attrs


def _image_id(row: dict, *, seed: str) -> str:
    raw = row.get("id")
    if raw:
        return str(raw)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def _image_ref(row: dict, *, seed: str, default_ordering: int = 0) -> dict:
    ordering = int(row.get("ordering", default_ordering) or 0)
    url = row.get("url") or _placeholder_url()
    payload = {
        "id": _image_id(row, seed=seed),
        "url": url,
        "ordering": ordering,
        "is_main": ordering == 0,
    }
    alt = row.get("alt")
    if alt:
        payload["alt"] = alt
    return payload


def _category_chain(category_id, categories_index: dict) -> list[dict]:
    chain = []
    seen = set()
    current_id = str(category_id)
    while current_id and current_id not in seen:
        seen.add(current_id)
        node = categories_index.get(current_id)
        if not node:
            break
        chain.append(node)
        parent_id = node.get("parent_id")
        current_id = str(parent_id) if parent_id is not None else None
    chain.reverse()
    return chain


def build_category_ref(
    category_id,
    categories_flat,
    *,
    fallback_name: str = "",
) -> dict | None:
    if category_id is None:
        return None
    cid = str(category_id)
    categories_index = {str(row.get("id")): row for row in (categories_flat or []) if row.get("id")}
    chain = _category_chain(cid, categories_index)
    if not chain:
        name = fallback_name or ""
        return {
            "id": cid,
            "name": name,
            "parent_id": None,
            "level": 0,
            "path": [name] if name else [],
        }
    node = chain[-1]
    parent_id = node.get("parent_id")
    return {
        "id": cid,
        "name": node.get("name") or fallback_name or "",
        "parent_id": str(parent_id) if parent_id is not None else None,
        "level": max(0, len(chain) - 1),
        "path": [n.get("name") or "" for n in chain],
    }


def _sku_discount_kopecks(sku: dict) -> int:
    discount = sku.get("discount", 0)
    if discount is None:
        return 0
    try:
        value = int(discount)
    except (TypeError, ValueError):
        return 0
    return max(0, value)


def _sku_available_quantity(sku: dict) -> int:
    raw = sku.get("available_quantity")
    if raw is None:
        raw = sku.get("active_quantity")
    if raw is None:
        raw = sku.get("activeQuantity", 0)
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 0


def _sku_prices(sku: dict) -> tuple[int, int | None]:
    """Текущая цена (коп.) и зачёркнутая old_price при скидке."""
    list_price = int(sku.get("price") or 0)
    discount = _sku_discount_kopecks(sku)
    if discount > 0:
        return max(0, list_price - discount), list_price
    return list_price, None


def _catalog_sku(sku: dict, *, placeholder: str) -> dict:
    sku_id = str(sku.get("id") or "")
    price, old_price = _sku_prices(sku)
    payload = {
        "id": sku_id,
        "name": sku.get("name") or "",
        "sku_code": (sku.get("sku_code") or sku.get("article") or "") or "",
        "price": price,
        "available_quantity": _sku_available_quantity(sku),
        "attributes": _characteristics_to_attributes(sku.get("characteristics")),
        "images": [],
    }
    if old_price is not None:
        payload["old_price"] = old_price

    images = []
    for index, row in enumerate(sku.get("images") or []):
        if isinstance(row, dict):
            images.append(_image_ref(row, seed=f"sku:{sku_id}:img:{index}"))
    if not images and sku.get("image"):
        images.append(
            _image_ref(
                {"url": sku["image"], "ordering": 0},
                seed=f"sku:{sku_id}:legacy",
            )
        )
    if not images:
        images.append(
            _image_ref({"url": placeholder, "ordering": 0}, seed=f"sku:{sku_id}:placeholder")
        )
    payload["images"] = images
    return payload


def _product_images(product: dict) -> list[dict]:
    placeholder = _placeholder_url()
    product_id = str(product.get("id") or "")
    images = []
    for index, row in enumerate(product.get("images") or []):
        if isinstance(row, dict):
            images.append(_image_ref(row, seed=f"product:{product_id}:img:{index}"))
    if not images:
        images.append(
            _image_ref({"url": placeholder, "ordering": 0}, seed=f"product:{product_id}:placeholder")
        )
    return images


def _aggregate_prices(catalog_skus: list[dict]) -> tuple[int, int | None, bool]:
    if not catalog_skus:
        return 0, None, False

    in_stock = [s for s in catalog_skus if s["available_quantity"] > 0]
    has_stock = bool(in_stock)
    pool = in_stock if in_stock else catalog_skus
    min_sku = min(pool, key=lambda s: s["price"])
    min_price = int(min_sku["price"])
    old_price = min_sku.get("old_price")
    return min_price, old_price, has_stock


def to_catalog_product_detail(product: dict, *, categories_flat=None) -> dict:
    placeholder = _placeholder_url()
    catalog_skus = [_catalog_sku(sku, placeholder=placeholder) for sku in (product.get("skus") or [])]
    min_price, old_price, has_stock = _aggregate_prices(catalog_skus)

    category_id = _product_category_id(product)
    fallback_name = (product.get("category") or {}).get("name") or ""
    category = build_category_ref(category_id, categories_flat, fallback_name=fallback_name)

    payload = {
        "id": str(product.get("id") or ""),
        "name": product.get("title") or product.get("name") or "",
        "slug": _b2c_product_slug(product),
        "min_price": min_price,
        "has_stock": has_stock,
        "images": _product_images(product),
        "description": product.get("description") or "",
        "attributes": _characteristics_to_attributes(product.get("characteristics")),
        "skus": catalog_skus,
    }
    if old_price is not None:
        payload["old_price"] = old_price
    if category is not None:
        payload["category"] = category
    return _strip_forbidden(payload)


def _strip_forbidden(card: dict) -> dict:
    for key in B2C_FORBIDDEN_PRODUCT_FIELDS:
        card.pop(key, None)
    for sku in card.get("skus") or []:
        for key in B2C_FORBIDDEN_SKU_FIELDS | {"discount", "active_quantity", "in_stock", "characteristics", "image"}:
            sku.pop(key, None)
    return card


def _card_images(product: dict) -> list[dict]:
    product_id = str(product.get("id") or "")
    cover = product.get("cover_image")
    if cover:
        return [
            _image_ref(
                {"url": cover, "ordering": 0},
                seed=f"product:{product_id}:cover",
            )
        ]
    return _product_images(product)


def to_catalog_product_card(
    product: dict,
    *,
    categories_flat=None,
    has_stock: bool | None = None,
) -> dict:
    """B2B short/full product → OpenAPI CatalogProductCard."""
    if product.get("skus"):
        detail = to_catalog_product_detail(product, categories_flat=categories_flat)
        return {
            "id": detail["id"],
            "name": detail["name"],
            "slug": detail["slug"],
            "min_price": detail["min_price"],
            "has_stock": detail["has_stock"],
            "images": detail["images"],
            **(
                {"old_price": detail["old_price"]}
                if detail.get("old_price") is not None
                else {}
            ),
            **({"category": detail["category"]} if detail.get("category") else {}),
        }

    product_id = str(product.get("id") or "")
    category_id = _product_category_id(product)
    category = build_category_ref(category_id, categories_flat)

    if has_stock is None:
        has_stock = True

    payload = {
        "id": product_id,
        "name": product.get("title") or product.get("name") or "",
        "slug": _b2c_product_slug(product),
        "min_price": int(product.get("min_price") or 0),
        "has_stock": bool(has_stock),
        "images": _card_images(product),
    }
    if category is not None:
        payload["category"] = category
    return _strip_forbidden(payload)


def to_category_tree_nodes(rows) -> list[dict]:
    """Плоский список B2B → OpenAPI CategoryTreeNode[]."""
    categories_flat = rows or []
    nodes = {}
    roots = []

    for row in categories_flat:
        node_id = row.get("id")
        if node_id is None:
            continue
        nodes[str(node_id)] = {
            "id": str(node_id),
            "name": row.get("name"),
            "parent_id": row.get("parent_id"),
            "children": [],
        }

    for node in nodes.values():
        parent_id = node.get("parent_id")
        if parent_id is None:
            roots.append(node)
            continue
        parent = nodes.get(str(parent_id))
        if not parent:
            roots.append(node)
            continue
        parent["children"].append(node)

    def enrich(raw_node: dict) -> dict:
        ref = build_category_ref(
            raw_node["id"],
            categories_flat,
            fallback_name=raw_node.get("name") or "",
        )
        children = [enrich(child) for child in raw_node.get("children") or []]
        return {**ref, "children": children}

    return [enrich(root) for root in roots]


def categories_to_refs(rows) -> list[dict]:
    refs = []
    for row in rows or []:
        if row.get("id") is None:
            continue
        ref = build_category_ref(row.get("id"), rows)
        if ref:
            refs.append(ref)
    return refs
