"""Shared parentage-log renderer used by all five Virtual Villagers games.

The data model is deliberately game-neutral.  A game-specific birth hook only
needs to provide a :class:`Person` snapshot and a :class:`BirthCard`; the
HTML writer and the Images-folder row mapping stay identical for VV1 through
VV5.
"""

from .vv1_parentage_log import (
    BODY_CELL_HEIGHT,
    HEAD_CELL_HEIGHT,
    SKILL_ORDER,
    BirthCard,
    Person,
    parentage_log_filename,
    parentage_log_path,
    render_parentage_html,
    write_parentage_html,
)

__all__ = [
    "BODY_CELL_HEIGHT",
    "HEAD_CELL_HEIGHT",
    "SKILL_ORDER",
    "BirthCard",
    "Person",
    "parentage_log_filename",
    "parentage_log_path",
    "render_parentage_html",
    "write_parentage_html",
]
