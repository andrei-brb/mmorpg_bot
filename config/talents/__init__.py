"""Talent tree definitions and loaders."""

from config.talents.loader import (
    get_class_foundation,
    get_spec_tree,
    list_class_specs,
    talent_points_for_level,
    total_talent_points_for_level,
)

__all__ = [
    "get_class_foundation",
    "get_spec_tree",
    "list_class_specs",
    "talent_points_for_level",
    "total_talent_points_for_level",
]
