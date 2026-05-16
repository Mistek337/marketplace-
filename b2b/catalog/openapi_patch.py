"""Хелперы PATCH в духе OpenAPI 3 (nullable + partial update)."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

_NOT_PROVIDED = object()


def patch_field_provided(attrs: dict, key: str) -> bool:
    return key in attrs


def pop_patch_value(attrs: dict, key: str, *, default: Any = _NOT_PROVIDED) -> Any:
    """Убрать поле из attrs; вернуть _NOT_PROVIDED, если ключа не было в теле."""
    if key not in attrs:
        return _NOT_PROVIDED
    return attrs.pop(key)


def is_patch_null(value: Any) -> bool:
    return value is None
