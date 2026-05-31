from __future__ import annotations

from .models import Order


def order_to_response(order: Order) -> dict:
    items = []
    for row in order.items.all():
        name = row.product_title
        if row.sku_name:
            name = f"{row.product_title} — {row.sku_name}".strip(" —")
        items.append(
            {
                "sku_id": str(row.sku_id),
                "product_id": str(row.product_id),
                "name": name,
                "sku_code": row.sku_code or None,
                "quantity": row.quantity,
                "unit_price": row.unit_price,
                "line_total": row.line_total,
                "image_url": row.image_url or None,
            }
        )

    return {
        "id": str(order.id),
        "number": order.number,
        "buyer_id": str(order.buyer_id),
        "status": order.status,
        "status_history": order.status_history or [],
        "items": items,
        "subtotal": order.subtotal,
        "delivery_cost": order.delivery_cost,
        "total": order.total,
        "address": order.address_snapshot,
        "payment_method": order.payment_method_snapshot,
        "comment": order.comment or None,
        "cancel_reason": order.cancel_reason or None,
        "created_at": order.created_at.isoformat().replace("+00:00", "Z"),
        "paid_at": order.paid_at.isoformat().replace("+00:00", "Z") if order.paid_at else None,
        "delivered_at": None,
    }
