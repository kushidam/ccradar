"""カテゴリ定義モジュール。"""

from enum import StrEnum


class Category(StrEnum):
    """Gemini が分類する全カテゴリ。"""
    FEATURE = "Feature"
    IMPROVEMENT = "Improvement"
    BUGFIX = "Bugfix"
    CHANGE = "Change"
    BREAKING = "Breaking"


# 通知対象カテゴリ（Bugfix を除く）
NOTIFY_CATEGORIES: frozenset[Category] = frozenset(Category) - {Category.BUGFIX}
