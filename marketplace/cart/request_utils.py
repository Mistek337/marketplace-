from __future__ import annotations

from rest_framework.request import Request

from .api_errors import error_body

FORBIDDEN_IDENTITY_KEYS = frozenset(
    {
        "user_id",
        "userid",
        "session_id",
        "sessionid",
        "x_session_id",
        "x-session-id",
    }
)


def reject_client_identity_override(request: Request):
    """OpenAPI: идентичность только JWT / X-Session-Id, не из query/body."""
    found: list[str] = []

    for key in request.query_params:
        if key.lower().replace("-", "_") in FORBIDDEN_IDENTITY_KEYS or key.lower() in FORBIDDEN_IDENTITY_KEYS:
            found.append(key)

    if isinstance(request.data, dict):
        for key in request.data:
            normalized = str(key).lower().replace("-", "_")
            if normalized in FORBIDDEN_IDENTITY_KEYS:
                found.append(str(key))

    if found:
        from rest_framework.response import Response
        from rest_framework import status

        return Response(
            error_body(
                code="VALIDATION_ERROR",
                message="user_id and session_id must not be sent in query or body",
                details={"fields": sorted(set(found))},
            ),
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None
