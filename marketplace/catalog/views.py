from django.conf import settings
from django.views.generic import TemplateView
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_errors import catalog_not_found as _catalog_not_found
from .api_errors import map_b2b_error as _map_b2b_error
from .b2b_client import B2BClient, B2BClientError
from .openapi_catalog import to_catalog_product_detail


class ProductPageView(TemplateView):
    """HTML-карточка: данные с GET /api/v1/catalog/products/{id}."""

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
    """HTML-каталог: список с GET /api/v1/catalog/products."""

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

        if not getattr(settings, "CATALOG_DEV_VISIBILITY", False):
            if product.get("status") != "MODERATED" or bool(product.get("deleted", False)):
                return _catalog_not_found()

        categories = []
        try:
            categories = client.get_categories()
        except B2BClientError:
            pass

        return Response(to_catalog_product_detail(product, categories_flat=categories))
