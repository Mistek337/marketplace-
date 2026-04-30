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
        raw = getattr(settings, "B2B_API_PREFIX", "/api") or "/api"
        raw = str(raw).strip()
        if not raw.startswith("/"):
            raw = "/" + raw
        self.api_prefix = raw.rstrip("/") or "/api"

    def _api_path(self, *parts):
        tail = "/".join(str(p).strip("/") for p in parts if p)
        return f"{self.api_prefix}/{tail}" if tail else self.api_prefix

    def _build_url(self, path, query=None):
        url = f"{self.base_url}{path}"
        if not query:
            return url
        query_string = parse.urlencode(
            {k: v for k, v in query.items() if v is not None and v != ""}
        )
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

    def get_products(self, *, limit, offset, category_id=None, filters=None, sort=None, search=None):
        # B2B (Desktop): GET /api/products/?category=<uuid>&… — параметр категории называется category.
        data = self._get(
            self._api_path("products"),
            query={
                "limit": limit,
                "offset": offset,
                "category": category_id,
                "filters": filters,
                "sort": sort,
                "search": search,
            },
        )
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

    def get_product(self, product_id):
        return self._get(self._api_path("products", str(product_id)))

    def get_product_skus(self, product_id):
        product = self.get_product(product_id)
        return product.get("skus", []) if isinstance(product, dict) else []

    def get_product_sku(self, product_id, sku_id):
        skus = self.get_product_skus(product_id)
        for sku in skus:
            if str(sku.get("id")) == str(sku_id):
                return sku
        raise B2BClientError(404, "SKU not found")

    def get_categories(self):
        data = self._get(self._api_path("categories"))
        return data if isinstance(data, list) else []
