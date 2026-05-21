from uuid import UUID

from catalog.b2b_client import B2BClientError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_errors import error_body
from .request_utils import reject_client_identity_override
from .services import (
    CartItemNotFoundError,
    InsufficientStockError,
    InvalidSessionHeaderError,
    MissingSessionError,
    SkuUnavailableError,
    add_or_increment_item,
    build_cart_response,
    clear_cart,
    merge_guest_into_user,
    parse_session_header,
    remove_item,
    resolve_cart,
    set_item_quantity,
    validate_cart,
)


def _bad_request(message: str, *, details=None) -> Response:
    return Response(
        error_body(code="VALIDATION_ERROR", message=message, details=details),
        status=status.HTTP_400_BAD_REQUEST,
    )


def _not_found(message: str) -> Response:
    return Response(
        error_body(code="NOT_FOUND", message=message),
        status=status.HTTP_404_NOT_FOUND,
    )


def _conflict(*, message: str, available_quantity: int | None = None) -> Response:
    details = {"available_quantity": available_quantity} if available_quantity is not None else None
    return Response(
        error_body(code="CONFLICT", message=message, details=details),
        status=status.HTTP_409_CONFLICT,
    )


def _resolve_cart_lenient(request, *, create_guest_session: bool = False):
    """Без 400: невалидный X-Session-Id трактуется как отсутствие заголовка."""
    try:
        return resolve_cart(request, create_guest_session=create_guest_session)
    except MissingSessionError:
        if create_guest_session:
            return resolve_cart(request, create_guest_session=True)
        return None


class CartAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        # OpenAPI: только 200
        cart = _resolve_cart_lenient(request, create_guest_session=True)
        return Response(build_cart_response(cart), status=status.HTTP_200_OK)

    def delete(self, request):
        # OpenAPI: только 204
        cart = _resolve_cart_lenient(request, create_guest_session=False)
        if cart is not None:
            clear_cart(cart)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemsAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # OpenAPI: 200, 400, 404, 409
        if rejected := reject_client_identity_override(request):
            return rejected

        sku_id_raw = request.data.get("sku_id")
        quantity = request.data.get("quantity")
        if not sku_id_raw or quantity is None:
            return _bad_request("sku_id and quantity are required")
        try:
            quantity = int(quantity)
            if quantity < 1:
                raise ValueError
            sku_id = UUID(str(sku_id_raw))
        except (TypeError, ValueError):
            return _bad_request("Invalid sku_id or quantity")

        try:
            cart = resolve_cart(request, create_guest_session=False)
        except MissingSessionError:
            return _bad_request("X-Session-Id header is required for guest cart operations")

        try:
            cart = add_or_increment_item(cart, sku_id=sku_id, quantity=quantity)
        except SkuUnavailableError:
            return _not_found("SKU not found or unavailable")
        except B2BClientError as exc:
            if exc.status_code == 404:
                return _not_found("SKU not found or unavailable")
            return _bad_request("Catalog service unavailable")
        except InsufficientStockError as exc:
            return _conflict(message="Insufficient stock", available_quantity=exc.active_quantity)

        return Response(build_cart_response(cart), status=status.HTTP_200_OK)


class CartValidateAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # OpenAPI: только 200
        cart = _resolve_cart_lenient(request, create_guest_session=False)
        if cart is None:
            cart = resolve_cart(request, create_guest_session=True)
        return Response(validate_cart(cart), status=status.HTTP_200_OK)


class CartItemDetailAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def patch(self, request, sku_id):
        # OpenAPI: только 200 и 409
        try:
            quantity = int(request.data.get("quantity"))
            if quantity < 1:
                raise ValueError
            sku_uuid = UUID(str(sku_id))
        except (TypeError, ValueError):
            return _conflict(message="Invalid quantity")

        cart = _resolve_cart_lenient(request, create_guest_session=False)
        if cart is None:
            return _conflict(message="Insufficient stock", available_quantity=0)

        try:
            cart = set_item_quantity(cart, sku_id=sku_uuid, quantity=quantity)
        except CartItemNotFoundError:
            return Response(build_cart_response(cart), status=status.HTTP_200_OK)
        except SkuUnavailableError:
            return _conflict(message="Insufficient stock", available_quantity=0)
        except B2BClientError as exc:
            if exc.status_code == 404:
                return _conflict(message="Insufficient stock", available_quantity=0)
            return Response(build_cart_response(cart), status=status.HTTP_200_OK)
        except InsufficientStockError as exc:
            return _conflict(message="Insufficient stock", available_quantity=exc.active_quantity)

        return Response(build_cart_response(cart), status=status.HTTP_200_OK)

    def delete(self, request, sku_id):
        # OpenAPI: только 200
        try:
            sku_uuid = UUID(str(sku_id))
        except (TypeError, ValueError):
            cart = _resolve_cart_lenient(request, create_guest_session=False)
            if cart is None:
                cart = resolve_cart(request, create_guest_session=True)
            return Response(build_cart_response(cart), status=status.HTTP_200_OK)

        cart = _resolve_cart_lenient(request, create_guest_session=False)
        if cart is None:
            cart = resolve_cart(request, create_guest_session=True)

        remove_item(cart, sku_id=sku_uuid)
        return Response(build_cart_response(cart), status=status.HTTP_200_OK)


class CartMergeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            session_id = parse_session_header(request, strict=True)
        except InvalidSessionHeaderError:
            return _bad_request("Invalid X-Session-Id header")
        if session_id is None:
            return _bad_request("X-Session-Id header is required")
        cart = merge_guest_into_user(guest_session_id=session_id, user=request.user)
        return Response(build_cart_response(cart), status=status.HTTP_200_OK)
