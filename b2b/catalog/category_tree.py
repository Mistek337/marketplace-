"""Хелперы дерева категорий для OpenAPI CategoryResponse (level, path)."""

from __future__ import annotations

from .models import Category


def build_categories_index(
    categories: list[Category] | None = None,
) -> dict[str, Category]:
    if categories is None:
        categories = list(Category.objects.all())
    return {str(category.id): category for category in categories}


def category_ancestry(
    category: Category,
    *,
    categories_index: dict[str, Category],
) -> list[Category]:
    chain: list[Category] = []
    current: Category | None = category
    seen: set[str] = set()

    while current is not None:
        current_id = str(current.id)
        if current_id in seen:
            break
        seen.add(current_id)
        chain.insert(0, current)
        if not current.parent_id:
            break
        current = categories_index.get(str(current.parent_id))

    return chain


def category_level(category: Category, *, categories_index: dict[str, Category]) -> int:
    return max(0, len(category_ancestry(category, categories_index=categories_index)) - 1)


def category_path(category: Category, *, categories_index: dict[str, Category]) -> list[str]:
    return [node.name for node in category_ancestry(category, categories_index=categories_index)]
