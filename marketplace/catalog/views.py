import json
from urllib import parse

from django.conf import settings
from django.utils.text import slugify
from django.views.generic import TemplateView
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .b2b_client import B2BClient, B2BClientError

# Поля SKU с B2B, которые нельзя отдавать покупателю (утечка данных продавца).
B2C_FORBIDDEN_SKU_FIELDS = frozenset({"cost_price", "reserved_quantity"})


def _map_b2b_error(exc):
    if exc.status_code == 404:
        return Response({"message": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    if exc.status_code == 400:
        return Response({"message": "Bad request"}, status=status.HTTP_400_BAD_REQUEST)
    if exc.status_code in (401, 403):
        return Response({"message": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
    if exc.status_code == 503:
        return Response(
            {"message": "Catalog service unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response(
        {"message": "Catalog service error"},
        status=status.HTTP_502_BAD_GATEWAY,
    )


def _to_similar_item(product):
    if product.get("min_price") is not None or product.get("cover_image") is not None:
        return {
            "id": product.get("id"),
            "title": product.get("title"),
            "image": product.get("cover_image"),
            "price": product.get("min_price"),
            "in_stock": True,
            "is_in_cart": False,
        }
    skus = product.get("skus") or []
    first_sku = skus[0] if skus else {}
    images = product.get("images") or []
    image = images[0].get("url") if images else None
    qty = first_sku.get("active_quantity")
    if qty is None:
        qty = first_sku.get("activeQuantity", 0)
    return {
        "id": product.get("id"),
        "title": product.get("title"),
        "image": image,
        "price": first_sku.get("price"),
        "in_stock": bool(int(qty or 0) > 0),
        "is_in_cart": False,
    }


def _b2c_product_slug(product: dict) -> str:
    slug = product.get("slug")
    if slug:
        return str(slug)
    title = product.get("title") or "product"
    base = slugify(str(title))[:200] or "product"
    pid = str(product.get("id") or "")
    suffix = pid.replace("-", "")[:8] if pid else "item"
    return f"{base}-{suffix}".strip("-")


def _public_sku_for_card(sku: dict, *, placeholder: str) -> dict:
    """Только публичные поля SKU для B2C (никогда не копируем сырой dict с B2B)."""
    qty = sku.get("active_quantity")
    if qty is None:
        qty = sku.get("activeQuantity", 0)
    qty = int(qty or 0)
    discount = sku.get("discount", 0)
    if discount is None:
        discount = 0
    try:
        discount = int(discount)
    except (TypeError, ValueError):
        discount = 0
    return {
        "id": sku.get("id"),
        "name": sku.get("name"),
        "price": sku.get("price"),
        "discount": discount,
        "image": sku.get("image") or placeholder,
        "active_quantity": qty,
        "in_stock": qty > 0,
        "characteristics": [
            {"name": row.get("name"), "value": row.get("value")}
            for row in (sku.get("characteristics") or [])
        ],
    }


def _strip_forbidden_sku_fields(card: dict) -> dict:
    """Страховка: даже при ошибке в коде не отдаём внутренние поля SKU."""
    for sku in card.get("skus") or []:
        for k in B2C_FORBIDDEN_SKU_FIELDS:
            sku.pop(k, None)
    return card


def _product_category_id(product):
    category_id = product.get("category_id")
    if category_id is not None:
        return category_id
    return (product.get("category") or {}).get("id")


def _to_b2c_card(product, *, category_name=None):
    placeholder = getattr(
        settings,
        "B2C_IMAGE_PLACEHOLDER",
        "https://via.placeholder.com/320x320?text=No+Image",
    )
    skus = [_public_sku_for_card(sku, placeholder=placeholder) for sku in (product.get("skus") or [])]
    category_id = _product_category_id(product)

    return _strip_forbidden_sku_fields(
        {
            "id": product.get("id"),
            "slug": _b2c_product_slug(product),
            "title": product.get("title"),
            "description": product.get("description"),
            "status": product.get("status"),
            "category": {
                "id": category_id,
                "name": category_name or (product.get("category") or {}).get("name") or "",
            },
            "images": [
                {"url": row.get("url"), "ordering": row.get("ordering", 0)}
                for row in (product.get("images") or [])
            ],
            "characteristics": [
                {"name": row.get("name"), "value": row.get("value")}
                for row in (product.get("characteristics") or [])
            ],
            "skus": skus,
        }
    )


def _build_category_tree(rows):
    nodes = {}
    roots = []

    for row in rows:
        node_id = row.get("id")
        if node_id is None:
            continue
        nodes[node_id] = {
            "id": node_id,
            "name": row.get("name"),
            "parent_id": row.get("parent_id"),
            "children": [],
        }

    for node in nodes.values():
        parent_id = node.get("parent_id")
        if parent_id is None:
            roots.append(node)
            continue
        parent = nodes.get(parent_id)
        if not parent:
            roots.append(node)
            continue
        parent["children"].append(node)

    return roots


def _to_filter_slug(name):
    return str(name or "").strip().lower().replace(" ", "_")


def _normalize_value(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if text == "":
        return None
    if text.isdigit():
        return int(text)
    return text


def _build_category_filters(products):
    buckets = {}

    for product in products:
        for row in product.get("characteristics") or []:
            name = row.get("name")
            value = _normalize_value(row.get("value"))
            if not name or value is None:
                continue
            slug = _to_filter_slug(name)
            entry = buckets.setdefault(
                slug, {"slug": slug, "name": name, "type": "list", "value": set()}
            )
            entry["value"].add(value)

        for sku in product.get("skus") or []:
            for row in sku.get("characteristics") or []:
                name = row.get("name")
                value = _normalize_value(row.get("value"))
                if not name or value is None:
                    continue
                slug = _to_filter_slug(name)
                entry = buckets.setdefault(
                    slug, {"slug": slug, "name": name, "type": "list", "value": set()}
                )
                entry["value"].add(value)

    items = []
    for item in buckets.values():
        values = list(item["value"])
        values.sort(key=lambda v: (isinstance(v, str), str(v).lower()))
        items.append(
            {
                "slug": item["slug"],
                "name": item["name"],
                "type": item["type"],
                "value": values,
            }
        )

    items.sort(key=lambda x: x["name"].lower())
    return items


def _product_filter_values(product):
    values = {}

    def _add(name, raw_value):
        slug = _to_filter_slug(name)
        value = _normalize_value(raw_value)
        if not slug or value is None:
            return
        values.setdefault(slug, set()).add(value)

    for row in product.get("characteristics") or []:
        _add(row.get("name"), row.get("value"))

    for sku in product.get("skus") or []:
        for row in sku.get("characteristics") or []:
            _add(row.get("name"), row.get("value"))

    return values


def _parse_filters(raw):
    if not raw:
        return {}
    text = str(raw).strip()
    if not text:
        return {}

    # primary format: JSON string
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except (ValueError, TypeError):
        pass

    # fallback format: querystring-like "brand=Apple&color=Black"
    parsed_qs = parse.parse_qs(text, keep_blank_values=False)
    if not parsed_qs:
        return None
    return {k: v for k, v in parsed_qs.items()}


def _matches_filters(product, filters, skip_slug=None):
    product_values = _product_filter_values(product)

    for key, expected in filters.items():
        slug = _to_filter_slug(key)
        if skip_slug and slug == skip_slug:
            continue

        actual_values = product_values.get(slug, set())
        if not actual_values:
            return False

        if isinstance(expected, dict):
            min_v = expected.get("min")
            max_v = expected.get("max")
            numeric_actual = [v for v in actual_values if isinstance(v, (int, float))]
            if not numeric_actual:
                return False
            if min_v is not None and max(numeric_actual) < min_v:
                return False
            if max_v is not None and min(numeric_actual) > max_v:
                return False
            continue

        if not isinstance(expected, list):
            expected = [expected]

        expected_norm = {_normalize_value(v) for v in expected}
        if not any(v in actual_values for v in expected_norm):
            return False

    return True


class ProductSKUsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, product_id):
        client = B2BClient()
        try:
            skus = client.get_product_skus(product_id)
        except B2BClientError as exc:
            return _map_b2b_error(exc)
        return Response(skus)

    def post(self, request, product_id):
        serializer = CreateSKURequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        body_product_id = str(payload["product_id"])
        if body_product_id != str(product_id):
            return Response(
                {"message": "product_id in body must match product_id in path"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payload["product_id"] = body_product_id

        client = B2BClient()
        try:
            created = client.create_sku(payload)
        except B2BClientError as exc:
            return _map_b2b_error(exc)

        return Response(created, status=status.HTTP_201_CREATED)


class CharacteristicInSerializer(serializers.Serializer):
    name = serializers.CharField()
    value = serializers.CharField()


class CreateSKURequestSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    name = serializers.CharField(max_length=255)
    price = serializers.IntegerField(min_value=0)
    cost_price = serializers.IntegerField(min_value=0)
    discount = serializers.IntegerField(min_value=0, required=False, default=0)
    image = serializers.CharField()
    characteristics = CharacteristicInSerializer(many=True, required=False, default=list)


class ProductImageInSerializer(serializers.Serializer):
    url = serializers.CharField()
    ordering = serializers.IntegerField(min_value=0)


class ProductCharacteristicInSerializer(serializers.Serializer):
    name = serializers.CharField()
    value = serializers.CharField()


class CreateProductRequestSerializer(serializers.Serializer):
    title = serializers.CharField(required=True, allow_blank=False, max_length=255)
    description = serializers.CharField(required=True, allow_blank=False, max_length=5000)
    category_id = serializers.UUIDField(required=True)
    images = ProductImageInSerializer(many=True, required=True)
    characteristics = ProductCharacteristicInSerializer(many=True, required=False, default=list)

    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("title is required")
        if len(value.strip()) > 255:
            raise serializers.ValidationError("title must be 1-255 characters")
        return value.strip()

    def validate_description(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("description is required")
        if len(value.strip()) > 5000:
            raise serializers.ValidationError("description must be 1-5000 characters")
        return value.strip()

    def validate_images(self, value):
        if not value:
            raise serializers.ValidationError("At least one image is required")
        return value


class ProductSKUDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, product_id, sku_id):
        client = B2BClient()
        try:
            sku = client.get_product_sku(product_id, sku_id)
        except B2BClientError as exc:
            return _map_b2b_error(exc)
        return Response(sku)


class ProductsListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", 10))
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return Response(
                {"message": "Invalid pagination parameters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        client = B2BClient()
        try:
            data = client.get_products(
                limit=limit,
                offset=offset,
                category_id=request.query_params.get("category_id"),
                filters=request.query_params.get("filters"),
                sort=request.query_params.get("sort"),
                search=request.query_params.get("search"),
            )
        except B2BClientError as exc:
            return _map_b2b_error(exc)
        return Response(data)

    def post(self, request):
        serializer = CreateProductRequestSerializer(data=request.data)
        if not serializer.is_valid():
            # Приводим ошибки к контракту {"code","message"}
            first_error = next(iter(serializer.errors.values()))
            message = first_error[0] if isinstance(first_error, list) else str(first_error)
            if "category_id" in serializer.errors and "valid UUID" in str(serializer.errors["category_id"]):
                message = "category_id must be a valid UUID"
            return Response(
                {"code": "INVALID_REQUEST", "message": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = serializer.validated_data
        payload["category_id"] = str(payload["category_id"])

        client = B2BClient()
        # Проверка существования категории до create
        try:
            categories = client.get_categories()
        except B2BClientError as exc:
            return _map_b2b_error(exc)
        if not any(str(row.get("id")) == payload["category_id"] for row in categories):
            return Response(
                {"code": "INVALID_REQUEST", "message": "Category not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            created = client.create_product(payload)
        except B2BClientError as exc:
            if exc.status_code == 400:
                return Response(
                    {"code": "INVALID_REQUEST", "message": "Invalid request"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return _map_b2b_error(exc)
        return Response(created, status=status.HTTP_201_CREATED)


class ProductPageView(TemplateView):
    """B2C HTML: полные данные товара подгружаются с GET /api/v1/products/{id} (прокси B2B)."""

    template_name = "product_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["product_id"] = str(kwargs["product_id"])
        ctx["image_placeholder"] = getattr(
            settings,
            "B2C_IMAGE_PLACEHOLDER",
            "https://via.placeholder.com/400x400?text=No+Image",
        )
        return ctx


class CatalogPageView(TemplateView):
    """Витрина: список товаров с карточками, переход на /products/<id>."""

    template_name = "catalog.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["image_placeholder"] = getattr(
            settings,
            "B2C_IMAGE_PLACEHOLDER",
            "https://via.placeholder.com/320x320?text=No+Image",
        )
        return ctx


class ProductDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, product_id):
        client = B2BClient()
        try:
            product = client.get_product(product_id)
        except B2BClientError as exc:
            return _map_b2b_error(exc)

        # Витрина: по умолчанию только MODERATED; для отладки — см. CATALOG_DEV_VISIBILITY в settings.
        if not getattr(settings, "CATALOG_DEV_VISIBILITY", False):
            if product.get("status") != "MODERATED" or bool(product.get("deleted", False)):
                return Response(
                    {"message": "Not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        return Response(_to_b2c_card(product))


class ProductSimilarView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, product_id):
        try:
            limit = int(request.query_params.get("limit", 8))
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return Response(
                {"message": "Invalid pagination parameters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        limit = max(1, min(limit, 50))
        offset = max(0, offset)

        client = B2BClient()
        try:
            pool = client.get_similar_products(product_id, limit=min(50, limit + offset))
        except B2BClientError as exc:
            if exc.status_code == 404:
                return Response(
                    {"message": "Product not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return _map_b2b_error(exc)

        page = pool[offset : offset + limit]
        items = [_to_similar_item(row) for row in page if isinstance(row, dict)]

        return Response(
            {
                "items": items,
                "total_count": len(pool),
                "limit": limit,
                "offset": offset,
            }
        )


class CategoriesTreeView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        client = B2BClient()
        try:
            categories = client.get_categories()
        except B2BClientError as exc:
            return _map_b2b_error(exc)

        return Response({"items": _build_category_tree(categories)})


class CategoryFiltersView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, category_id):
        client = B2BClient()
        try:
            categories = client.get_categories()
        except B2BClientError as exc:
            return _map_b2b_error(exc)

        if not any(str(row.get("id")) == str(category_id) for row in categories):
            return Response(
                {"message": "category not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            listing = client.get_products(limit=1000, offset=0, category_id=str(category_id))
        except B2BClientError as exc:
            return _map_b2b_error(exc)

        pool = listing.get("items", []) if isinstance(listing, dict) else []
        if not pool:
            return Response(
                {"items": []},
                status=status.HTTP_200_OK,
            )

        full_products = []
        for short_item in pool:
            product_id = short_item.get("id")
            if not product_id:
                continue
            try:
                full_products.append(client.get_product(product_id))
            except B2BClientError:
                continue

        return Response({"items": _build_category_filters(full_products)})


class CatalogFacetsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        category_id = request.query_params.get("category_id")
        if not category_id:
            return Response(
                {"message": "category_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filters = _parse_filters(request.query_params.get("filters"))
        if filters is None:
            return Response(
                {"message": "Invalid filters format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = B2BClient()
        try:
            categories = client.get_categories()
        except B2BClientError as exc:
            return _map_b2b_error(exc)

        if not any(str(row.get("id")) == str(category_id) for row in categories):
            return Response(
                {"message": "Category not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            listing = client.get_products(limit=1000, offset=0, category_id=str(category_id))
        except B2BClientError as exc:
            return _map_b2b_error(exc)

        pool = listing.get("items", []) if isinstance(listing, dict) else []

        full_products = []
        for short_item in pool:
            product_id = short_item.get("id")
            if not product_id:
                continue
            try:
                full_products.append(client.get_product(product_id))
            except B2BClientError:
                continue

        all_filters = _build_category_filters(full_products)
        facets = []
        for facet in all_filters:
            slug = facet.get("slug")
            counts = {}
            for product in full_products:
                if not _matches_filters(product, filters, skip_slug=slug):
                    continue
                for value in _product_filter_values(product).get(slug, set()):
                    counts[value] = counts.get(value, 0) + 1

            facet_values = [
                {"value": value, "count": count}
                for value, count in sorted(
                    counts.items(), key=lambda x: (isinstance(x[0], str), str(x[0]).lower())
                )
            ]
            facets.append({"name": slug, "values": facet_values})

        return Response({"category_id": str(category_id), "facets": facets})


class BreadcrumbsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        category_id = request.query_params.get("category_id")
        product_id = request.query_params.get("product_id")

        if bool(category_id) == bool(product_id):
            return Response(
                {
                    "error": "missing_param",
                    "message": "category_id or product_id must be provided",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = B2BClient()
        try:
            categories = client.get_categories()
        except B2BClientError as exc:
            if exc.status_code == 503:
                return Response(
                    {"error": "upstream_error", "message": "catalog api unavailable"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(
                {"error": "upstream_error", "message": "catalog api unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        by_id = {str(row.get("id")): row for row in categories}
        resolved_via = "category_id"
        target_product_id = None

        if product_id:
            try:
                product = client.get_product(product_id)
            except B2BClientError as exc:
                if exc.status_code == 404:
                    return Response(
                        {"error": "product_not_found", "message": "product not found"},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                return Response(
                    {"error": "upstream_error", "message": "catalog api unavailable"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            category_id = str((product.get("category") or {}).get("id"))
            resolved_via = "product_id"
            target_product_id = str(product_id)

        if str(category_id) not in by_id:
            return Response(
                {"error": "category_not_found", "message": "category not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        chain = []
        seen = set()
        current_id = str(category_id)
        while current_id and current_id not in seen:
            seen.add(current_id)
            node = by_id.get(current_id)
            if not node:
                break
            chain.append(node)
            parent_id = node.get("parent_id")
            if parent_id is not None and str(parent_id) not in by_id:
                return Response(
                    {"error": "orphan_node", "message": "category hierarchy is broken"},
                    status=422,
                )
            current_id = str(parent_id) if parent_id is not None else None

        if current_id in seen:
            return Response(
                {"error": "orphan_node", "message": "category hierarchy is broken"},
                status=422,
            )

        chain.reverse()

        segments = []
        data = []
        for idx, node in enumerate(chain):
            name = node.get("name") or ""
            segments.append(slugify(name) or str(node.get("id")))
            data.append(
                {
                    "id": str(node.get("id")),
                    "slug": slugify(name) or str(node.get("id")),
                    "name": name,
                    "url": "/catalog/" + "/".join(segments) + "/",
                    "level": idx,
                    "is_current": idx == len(chain) - 1,
                }
            )

        return Response(
            {
                "data": data,
                "meta": {
                    "resolved_via": resolved_via,
                    "category_id": str(category_id),
                    "product_id": target_product_id,
                },
            }
        )

