"""Преобразование ошибок DRF в формат OpenAPI 422 (как FastAPI)."""

from __future__ import annotations

from typing import Any


def _infer_error_type(message: str) -> str:
    text = message.lower()
    if "required" in text or "may not be blank" in text or "may not be null" in text:
        return "value_error.missing"
    if "valid uuid" in text:
        return "type_error.uuid"
    if "not found" in text or "does not exist" in text:
        return "value_error.not_found"
    if "at least one" in text:
        return "value_error"
    return "value_error"


def _resolve_input(data: Any, loc: list) -> Any:
    """Достаёт значение из тела запроса по цепочке loc (после префикса body)."""
    if not isinstance(data, dict):
        return None
    path = loc[1:] if loc and loc[0] == "body" else loc
    current: Any = data
    for part in path:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and isinstance(part, int) and 0 <= part < len(current):
            current = current[part]
        else:
            return None
    return current


def _append_detail(
    detail: list[dict],
    *,
    loc: list,
    message: str,
    request_data: Any = None,
) -> None:
    raw_input = _resolve_input(request_data, loc) if request_data is not None else None
    if raw_input is None:
        input_value: Any = ""
    elif isinstance(raw_input, (dict, list)):
        input_value = raw_input
    else:
        input_value = str(raw_input)

    detail.append(
        {
            "loc": loc,
            "msg": message,
            "type": _infer_error_type(message),
            "input": input_value,
            "ctx": {},
        }
    )


def drf_errors_to_detail(
    errors: dict | list,
    *,
    loc_prefix: tuple[str, ...] = ("body",),
    request_data: Any = None,
) -> dict[str, list[dict]]:
    detail: list[dict] = []

    def walk(errs: Any, loc: list[str | int]) -> None:
        if isinstance(errs, dict):
            for key, value in errs.items():
                if key == "non_field_errors":
                    items = value if isinstance(value, list) else [value]
                    for item in items:
                        msg = item if isinstance(item, str) else str(item)
                        _append_detail(detail, loc=list(loc), message=msg, request_data=request_data)
                else:
                    next_loc: list[str | int] = [*loc, key if isinstance(key, str) else key]
                    walk(value, next_loc)
        elif isinstance(errs, list):
            if errs and isinstance(errs[0], dict):
                for index, nested in enumerate(errs):
                    walk(nested, [*loc, index])
            else:
                for item in errs:
                    msg = item if isinstance(item, str) else str(item)
                    _append_detail(detail, loc=list(loc), message=msg, request_data=request_data)
        else:
            _append_detail(
                detail,
                loc=list(loc),
                message=str(errs),
                request_data=request_data,
            )

    walk(errors, list(loc_prefix))
    return {"detail": detail}


def validation_error_response(
    errors: dict | list,
    *,
    request_data: Any = None,
) -> dict[str, list[dict]]:
    return drf_errors_to_detail(errors, request_data=request_data)
