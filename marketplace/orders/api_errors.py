from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.response import Response


def error_body(*, code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return body


def service_unavailable(message: str = "Catalog service unavailable") -> Response:
    return Response(
        error_body(code="SERVICE_UNAVAILABLE", message=message),
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
