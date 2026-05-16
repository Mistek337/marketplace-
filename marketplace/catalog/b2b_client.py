import json
from urllib import error, parse, request

from django.conf import settings


class B2BClientError(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class B2BClient:
    def __init__(self):
        self.base_url = settings.B2B_BASE_URL.rstrip("/")
        self.timeout = settings.B2B_TIMEOUT
        raw = getattr(settings, "B2B_API_PREFIX", "/api/v1") or "/api/v1"
        raw = str(raw).strip()
        if not raw.startswith("/"):
            raw = "/" + raw
        self.api_prefix = raw.rstrip("/") or "/api/v1"

    def _api_path(self, *parts):
        tail = "/".join(str(p).strip("/") for p in parts if p)
        return f"{self.api_prefix}/{tail}" if tail else self.api_prefix

    def _build_url(self, path, query=None):
        url = f"{self.base_url}{path}"
        if not query:
            return url
        pairs = []
        for key, value in query.items():
            if value is None or value == "":
                continue
            if isinstance(value, (list, tuple)):
                for item in value:
                    if item is not None and item != "":
                        pairs.append((key, item))
            else:
                pairs.append((key, value))
        query_string = parse.urlencode(pairs)
        return f"{url}?{query_string}" if query_string else url

    def _single_get(self, path, query=None):
        req = request.Request(self._build_url(path, query=query), method="GET")
        token = getattr(settings, "B2B_SERVICE_TOKEN", "")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        service_key = getattr(settings, "B2B_SERVICE_KEY", "") or ""
        if service_key:
            req.add_header("X-Service-Key", service_key)
        req.add_header("Accept", "application/json")

        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8") if resp.length != 0 else ""
                return json.loads(body) if body else {}
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise B2BClientError(exc.code, detail or "B2B HTTP error") from exc
        except error.URLError as exc:
            raise B2BClientError(503, f"B2B unavailable: {exc}") from exc

    def _get(self, path, query=None):
        """
        GET к B2B. При 404 повторяет тот же путь с/без завершающего слэша —
        у разных бэкендов (Django APPEND_SLASH, FastAPI) принят один из вариантов.
        """
        try:
            return self._single_get(path, query)
        except B2BClientError as first:
            if first.status_code != 404:
                raise
            alt = path.rstrip("/") + "/" if not path.endswith("/") else path.rstrip("/")
            if alt == path:
                raise
            try:
                return self._single_get(alt, query)
            except B2BClientError:
                raise first

    def get_products(
        self,
        *,
        limit,
        offset,
        category_id=None,
        seller_id=None,
        min_price=None,
        max_price=None,
        char_filters=None,
        filters=None,
        sort=None,
        search=None,
        ids=None,
    ):
        query = {
            "limit": limit,
            "offset": offset,
            "category_id": category_id,
            "seller_id": seller_id,
            "min_price": min_price,
            "max_price": max_price,
            "sort": sort,
            "search": search,
        }
        if filters:
            query["filters"] = filters
        for name, values in (char_filters or {}).items():
            key = f"filters[{name}]"
            query[key] = list(values) if isinstance(values, (list, tuple)) else [values]

        data = self._get(self._api_path("public", "products"), query=query)
        if isinstance(data, dict) and "items" in data:
            return data
        if isinstance(data, list):
            return {
                "total_count": len(data),
                "limit": limit,
                "offset": offset,
                "items": data[offset : offset + limit],
            }
        return {"total_count": 0, "limit": limit, "offset": offset, "items": []}

    def batch_public_products(self, product_ids):
        return self._post_json(
            self._api_path("public", "products", "batch"),
            {"product_ids": [str(pid) for pid in product_ids]},
        )

    def _post_json(self, path, payload):
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self._build_url(path),
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        token = getattr(settings, "B2B_SERVICE_TOKEN", "")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        service_key = getattr(settings, "B2B_SERVICE_KEY", "") or ""
        if service_key:
            req.add_header("X-Service-Key", service_key)
        req.add_header("Accept", "application/json")

        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8") if resp.length != 0 else ""
                return json.loads(raw) if raw else []
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise B2BClientError(exc.code, detail or "B2B HTTP error") from exc
        except error.URLError as exc:
            raise B2BClientError(503, f"B2B unavailable: {exc}") from exc

    def get_product(self, product_id):
        return self._get(self._api_path("public", "products", str(product_id)))

    def get_similar_products(self, product_id, *, limit=10):
        data = self._get(
            self._api_path("public", "products", str(product_id), "similar"),
            query={"limit": limit},
        )
        return data if isinstance(data, list) else []

    def get_public_sku(self, sku_id):
        return self._get(self._api_path("public", "skus", str(sku_id)))

    def get_product_skus(self, product_id):
        product = self.get_product(product_id)
        return product.get("skus", []) if isinstance(product, dict) else []

    def get_product_sku(self, product_id, sku_id):
        del product_id
        return self.get_public_sku(sku_id)

    def get_categories(self):
        data = self._get(self._api_path("categories"))
        return data if isinstance(data, list) else []
