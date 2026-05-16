"""Ошибки API в формате NeoMarket OpenAPI: {code, message, details?}."""

from __future__ import annotations

from typing import Any

VALIDATION_ERROR = "VALIDATION_ERROR"
FORBIDDEN = "FORBIDDEN"
NOT_FOUND = "NOT_FOUND"
SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


def error_body(*, code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    return body


def _flatten_errors(errors: Any, prefix: str = "") -> dict[str, str]:
    details: dict[str, str] = {}
    if isinstance(errors, dict):
        for key, value in errors.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key == "non_field_errors":
                details[prefix or "non_field_errors"] = (
                    value[0] if isinstance(value, list) else str(value)
                )
            else:
                details.update(_flatten_errors(value, path))
    elif isinstance(errors, list):
        if errors and isinstance(errors[0], dict):
            for index, nested in enumerate(errors):
                path = f"{prefix}[{index}]" if prefix else f"[{index}]"
                details.update(_flatten_errors(nested, path))
        else:
            msg = errors[0] if errors else "Validation failed"
            details[prefix or "non_field_errors"] = str(msg)
    else:
        details[prefix or "non_field_errors"] = str(errors)
    return details


def drf_validation_error(errors: dict | list) -> dict[str, Any]:
    details = _flatten_errors(errors)
    message = next(iter(details.values()), "Validation failed")
    return error_body(code=VALIDATION_ERROR, message=message, details=details)
