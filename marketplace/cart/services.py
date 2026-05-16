from __future__ import annotations

import uuid
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.request import Request

from catalog.b2b_client import B2BClient, B2BClientError

from .models import Cart, CartItem

User = get_user_model()


def parse_session_header(request: Request, *, strict: bool = False) -> UUID | None:
    raw = request.headers.get("X-Session-Id")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except (TypeError, ValueError) as exc:
        if strict:
            raise InvalidSessionHeaderError() from exc
        return None  # невалидный заголовок = как будто не передан (только 200/204 на GET/DELETE)


def get_or_create_guest_cart(session_id: UUID) -> Cart:
    cart, created = Cart.objects.get_or_create(session_id=session_id, defaults={"user": None})
    if created:
        cart.save()
    return cart


def get_or_create_user_cart(user) -> Cart:
    cart, _ = Cart.objects.get_or_create(user=user, defaults={"session_id": None})
    return cart


def resolve_cart(request: Request, *, create_guest_session: bool = False) -> Cart:
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return get_or_create_user_cart(user)

    session_id = parse_session_header(request)
    if session_id is None:
        if create_guest_session:
            session_id = uuid.uuid4()
            return get_or_create_guest_cart(session_id)
        raise MissingSessionError()

    return get_or_create_guest_cart(session_id)


def fetch_sku_from_b2b(sku_id: UUID) -> dict:
    client = B2BClient()
    return client.get_public_sku(str(sku_id))


def fetch_product_from_b2b(product_id: UUID) -> dict:
    return B2BClient().get_product(str(product_id))


def _sku_available_quantity(sku_data: dict) -> int:
    raw = sku_data.get("available_quantity")
    if raw is None:
        raw = sku_data.get("active_quantity")
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 0


def _assert_sku_purchasable(*, sku_id: UUID, quantity: int) -> tuple[dict, UUID, int, int]:
    try:
        sku_data = fetch_sku_from_b2b(sku_id)
    except B2BClientError as exc:
        if exc.status_code == 404:
            raise SkuUnavailableError() from exc
        raise

    product_id = UUID(str(sku_data["product_id"]))
    try:
        product = fetch_product_from_b2b(product_id)
    except B2BClientError as exc:
        if exc.status_code == 404:
            raise SkuUnavailableError() from exc
        raise

    if bool(product.get("deleted")):
        raise SkuUnavailableError()
    if (product.get("status") or "").upper() != "MODERATED":
        raise SkuUnavailableError()

    unit_price = int(sku_data.get("price") or 0)
    available_qty = _sku_available_quantity(sku_data)
    if available_qty < quantity:
        raise InsufficientStockError(active_quantity=available_qty)

    return sku_data, product_id, unit_price, available_qty


def add_or_increment_item(cart: Cart, *, sku_id: UUID, quantity: int) -> Cart:
    sku_data, product_id, unit_price, active_qty = _assert_sku_purchasable(
        sku_id=sku_id,
        quantity=quantity,
    )

    with transaction.atomic():
        item = CartItem.objects.filter(cart=cart, sku_id=sku_id).first()
        if item:
            new_qty = item.quantity + quantity
            if active_qty < new_qty:
                raise InsufficientStockError(active_quantity=active_qty)
            item.quantity = new_qty
            item.save(update_fields=["quantity", "updated_at"])
        else:
            CartItem.objects.create(
                cart=cart,
                sku_id=sku_id,
                product_id=product_id,
                quantity=quantity,
                unit_price_at_add=unit_price,
            )
        cart.updated_at = timezone.now()
        cart.save(update_fields=["updated_at"])

    return cart


def set_item_quantity(cart: Cart, *, sku_id: UUID, quantity: int) -> Cart:
    if not CartItem.objects.filter(cart=cart, sku_id=sku_id).exists():
        raise CartItemNotFoundError()

    _, _, _, active_qty = _assert_sku_purchasable(sku_id=sku_id, quantity=quantity)

    with transaction.atomic():
        updated = CartItem.objects.filter(cart=cart, sku_id=sku_id).update(
            quantity=quantity,
            updated_at=timezone.now(),
        )
        if not updated:
            raise CartItemNotFoundError()
        cart.updated_at = timezone.now()
        cart.save(update_fields=["updated_at"])

    return cart


def remove_item(cart: Cart, *, sku_id: UUID) -> Cart:
    CartItem.objects.filter(cart=cart, sku_id=sku_id).delete()
    cart.updated_at = timezone.now()
    cart.save(update_fields=["updated_at"])
    return cart


def clear_cart(cart: Cart) -> None:
    cart.items.all().delete()
    cart.updated_at = timezone.now()
    cart.save(update_fields=["updated_at"])


def merge_guest_into_user(*, guest_session_id: UUID, user) -> Cart:
    user_cart = get_or_create_user_cart(user)
    try:
        guest_cart = Cart.objects.get(session_id=guest_session_id, user__isnull=True)
    except Cart.DoesNotExist:
        return user_cart

    with transaction.atomic():
        guest_items = list(guest_cart.items.all())
        for guest_item in guest_items:
            existing = CartItem.objects.filter(cart=user_cart, sku_id=guest_item.sku_id).first()
            merged_qty = max(guest_item.quantity, existing.quantity if existing else 0)
            if existing:
                existing.quantity = merged_qty
                if existing.unit_price_at_add is None and guest_item.unit_price_at_add is not None:
                    existing.unit_price_at_add = guest_item.unit_price_at_add
                existing.save(update_fields=["quantity", "unit_price_at_add", "updated_at"])
            else:
                CartItem.objects.create(
                    cart=user_cart,
                    sku_id=guest_item.sku_id,
                    product_id=guest_item.product_id,
                    quantity=merged_qty,
                    unit_price_at_add=guest_item.unit_price_at_add,
                )
        guest_cart.items.all().delete()
        guest_cart.delete()
        user_cart.updated_at = timezone.now()
        user_cart.save(update_fields=["updated_at"])

    return user_cart


def _load_products_for_cart(items_qs: list[CartItem]) -> dict[str, dict]:
    product_ids = list({item.product_id for item in items_qs})
    products_by_id: dict[str, dict] = {}
    if not product_ids:
        return products_by_id
    try:
        batch = B2BClient().batch_public_products(product_ids)
        if isinstance(batch, list):
            for product in batch:
                if isinstance(product, dict) and product.get("id"):
                    products_by_id[str(product["id"])] = product
    except B2BClientError:
        pass
    return products_by_id


def build_cart_response(cart: Cart) -> dict:
    items_qs = list(cart.items.all())
    products_by_id = _load_products_for_cart(items_qs)
    items_payload = [
        _enrich_line(row, products_by_id.get(str(row.product_id)))
        for row in items_qs
    ]
    return _assemble_cart_response(cart, items_payload)


def validate_cart(cart: Cart) -> dict:
    items_qs = list(cart.items.all())
    products_by_id = _load_products_for_cart(items_qs)
    issues: list[dict] = []
    items_payload = []
    for row in items_qs:
        product = products_by_id.get(str(row.product_id))
        item_payload = _enrich_line(row, product)
        items_payload.append(item_payload)
        issues.extend(_validation_issues(item_payload, product))

    cart_body = _assemble_cart_response(cart, items_payload)
    return {
        "is_valid": len(issues) == 0,
        "cart": cart_body,
        "issues": issues,
    }


def _assemble_cart_response(cart: Cart, items_payload: list[dict]) -> dict:
    items_count = sum(int(i["quantity"]) for i in items_payload)
    subtotal = sum(int(i["line_total"]) for i in items_payload)
    is_valid = all(i["is_available"] for i in items_payload) if items_payload else True
    cart_public_id = str(cart.session_id) if cart.session_id else str(cart.id)
    return {
        "id": cart_public_id,
        "items": items_payload,
        "items_count": items_count,
        "subtotal": subtotal,
        "is_valid": is_valid,
        "updated_at": cart.updated_at.isoformat().replace("+00:00", "Z"),
    }


def _validation_issues(item: dict, product: dict | None) -> list[dict]:
    sku_id = item["sku_id"]
    issues: list[dict] = []

    if product is None:
        issues.append(
            {
                "sku_id": sku_id,
                "type": "PRODUCT_DELETED",
                "message": "Product is no longer available",
            }
        )
        return issues

    if bool(product.get("deleted")):
        issues.append(
            {
                "sku_id": sku_id,
                "type": "PRODUCT_DELETED",
                "message": "Product is no longer available",
            }
        )
        return issues

    status_value = (product.get("status") or "").upper()
    if status_value != "MODERATED":
        issue_type = "PRODUCT_BLOCKED" if "BLOCKED" in status_value else "PRODUCT_DELETED"
        issues.append(
            {
                "sku_id": sku_id,
                "type": issue_type,
                "message": "Product is not available for purchase",
            }
        )
        return issues

    available = int(item["available_quantity"])
    quantity = int(item["quantity"])
    if available == 0:
        issues.append(
            {
                "sku_id": sku_id,
                "type": "OUT_OF_STOCK",
                "message": "SKU is out of stock",
                "old_value": quantity,
                "new_value": 0,
            }
        )
    elif quantity > available:
        issues.append(
            {
                "sku_id": sku_id,
                "type": "QUANTITY_REDUCED",
                "message": "Quantity exceeds available stock",
                "old_value": quantity,
                "new_value": available,
            }
        )

    unit_price_at_add = item.get("unit_price_at_add")
    unit_price = int(item["unit_price"])
    if unit_price_at_add is not None and int(unit_price_at_add) != unit_price:
        issues.append(
            {
                "sku_id": sku_id,
                "type": "PRICE_CHANGED",
                "message": "Price has changed since item was added",
                "old_value": int(unit_price_at_add),
                "new_value": unit_price,
            }
        )

    return issues


def _enrich_line(row: CartItem, product: dict | None) -> dict:
    placeholder_image = None
    sku_data = None
    product_id = str(row.product_id)
    product_title = ""
    status = ""

    if product:
        product_title = product.get("title") or ""
        status = product.get("status") or ""
        images = product.get("images") or []
        if images and isinstance(images[0], dict):
            placeholder_image = _image_ref(images[0])
        for sku in product.get("skus") or []:
            if str(sku.get("id")) == str(row.sku_id):
                sku_data = sku
                break

    if sku_data:
        sku_name = sku_data.get("name") or ""
        sku_code = sku_data.get("sku_code") or sku_data.get("article") or ""
        unit_price = int(sku_data.get("price") or 0)
        available_quantity = _sku_available_quantity(sku_data)
        sku_images = sku_data.get("images") or []
        image = placeholder_image
        if sku_images and isinstance(sku_images[0], dict):
            image = _image_ref(sku_images[0])
    else:
        sku_name = ""
        sku_code = ""
        unit_price = int(row.unit_price_at_add or 0)
        available_quantity = 0
        image = None

    name = f"{product_title} — {sku_name}".strip(" —") if product_title else sku_name
    line_total = unit_price * row.quantity
    is_available = (
        product is not None
        and not bool(product.get("deleted"))
        and status == "MODERATED"
        and sku_data is not None
        and available_quantity > 0
        and row.quantity <= available_quantity
    )

    payload = {
        "sku_id": str(row.sku_id),
        "product_id": product_id,
        "name": name,
        "sku_code": sku_code,
        "quantity": row.quantity,
        "unit_price": unit_price,
        "unit_price_at_add": row.unit_price_at_add,
        "line_total": line_total,
        "available_quantity": available_quantity,
        "is_available": is_available,
    }
    if image is not None:
        payload["image"] = image
    return payload


def _image_ref(row: dict) -> dict | None:
    url = row.get("url")
    if not url:
        return None
    return {
        "id": str(row.get("id")) if row.get("id") else str(uuid.uuid4()),
        "url": url,
        "ordering": int(row.get("ordering") or 0),
        "alt": row.get("alt"),
        "is_main": bool(row.get("ordering", 0) == 0),
    }


class InsufficientStockError(Exception):
    def __init__(self, *, active_quantity: int):
        self.active_quantity = active_quantity


class CartItemNotFoundError(Exception):
    pass


class SkuNotFoundError(Exception):
    pass


class MissingSessionError(Exception):
    pass


class InvalidSessionHeaderError(Exception):
    pass


class SkuUnavailableError(Exception):
    pass
