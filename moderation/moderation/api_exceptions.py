"""DRF → NeoMarket OpenAPI Error: {code, message, details?}."""

from __future__ import annotations

from django.http import Http404
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated, NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from events.api_errors import (
    FORBIDDEN,
    NOT_FOUND,
    UNAUTHORIZED,
    VALIDATION_ERROR,
    drf_validation_error,
    error_body,
)


def _detail_message(detail) -> str:
    if isinstance(detail, list) and detail:
        return str(detail[0])
    if isinstance(detail, dict):
        if "message" in detail:
            return str(detail["message"])
        if "detail" in detail:
            return _detail_message(detail["detail"])
        first = next(iter(detail.values()), None)
        if first is not None:
            return _detail_message(first)
    return str(detail) if detail is not None else "Request failed"


def moderation_exception_handler(exc, context):
    if isinstance(exc, AuthenticationFailed):
        return Response(
            error_body(code=UNAUTHORIZED, message=_detail_message(exc.detail)),
            status=401,
        )
    if isinstance(exc, NotAuthenticated):
        return Response(
            error_body(code=UNAUTHORIZED, message="Authentication required"),
            status=401,
        )
    if isinstance(exc, PermissionDenied):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            return Response(detail, status=403)
        return Response(
            error_body(code=FORBIDDEN, message=_detail_message(detail)),
            status=403,
        )
    if isinstance(exc, (Http404, NotFound)):
        return Response(
            error_body(code=NOT_FOUND, message="Not found"),
            status=404,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    if isinstance(data, dict) and "code" in data and "message" in data:
        return response

    status_code = response.status_code
    if status_code == 401:
        message = _detail_message(data)
        if message not in ("Invalid token", "Invalid credentials", "Invalid refresh token"):
            message = "Authentication required"
        response.data = error_body(code=UNAUTHORIZED, message=message)
        return response

    if status_code in (400, 422) and isinstance(data, dict):
        if "detail" in data and isinstance(data["detail"], list):
            loc_errors: dict = {}
            for item in data["detail"]:
                if not isinstance(item, dict):
                    continue
                loc = item.get("loc") or []
                field = ".".join(str(part) for part in loc if part != "body") or "non_field_errors"
                loc_errors[field] = item.get("msg", "Validation failed")
            response.data = drf_validation_error(loc_errors)
            return response
        response.data = drf_validation_error(data)
        return response

    message = _detail_message(data)
    code_by_status = {
        400: VALIDATION_ERROR,
        403: FORBIDDEN,
        404: NOT_FOUND,
        409: "CONFLICT",
        503: "SERVICE_UNAVAILABLE",
    }
    response.data = error_body(
        code=code_by_status.get(status_code, "ERROR"),
        message=message,
    )
    return response
