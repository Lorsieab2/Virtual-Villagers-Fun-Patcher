"""The patcher window's "?" guides (data/how_to_use.json).

The owner: "there should be a little How to Use button for every feature in
the entire patcher. Just a brief, simple to understand guide."  Every public
patch, population mode, button, tool and setting has one short plain guide:
what it does, how to use it, and what to watch out for.

The guides are data, kept in one file that ships with the patcher, keyed by
the same ids the patcher already uses -- a patch by its patch id, a
population mode by its mode id, everything else by a control key.  They are
not put into the patch manifests: many of those are generated or carry
certified hashes, and a guide is presentation text that must never change
what a patch does.  tests/test_how_to_use.py refuses a public patch, mode or
control without a guide, so a new feature cannot ship without one.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES_PATH = ROOT / "data" / "how_to_use.json"

# Guides stay short: the owner asked for "brief, simple to understand".
MAX_LINES = 8
MAX_LINE_CHARS = 180
MAX_GUIDE_CHARS = 900


@dataclass(frozen=True)
class Guide:
    title: str
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n\n".join(self.lines)


def patch_key(patch_id: str) -> str:
    return f"patch:{patch_id}"


def mode_key(mode_id: str) -> str:
    return f"mode:{mode_id}"


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(GUIDES_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def guide_lines() -> dict[str, tuple[str, ...]]:
    """Every guide by key: ``patch:<id>``, ``mode:<id>`` or a control key.

    A patch id listed twice is an error, so two guides can never compete for
    one patch.
    """
    data = _load()
    result: dict[str, tuple[str, ...]] = {}
    for entry in data["patches"]:
        for patch_id in entry["ids"]:
            key = patch_key(patch_id)
            if key in result:
                raise ValueError(f"{patch_id} has more than one guide in {GUIDES_PATH.name}")
            result[key] = tuple(entry["guide"])
    for mode_id, lines in data["modes"].items():
        result[mode_key(mode_id)] = tuple(lines)
    for control, entry in data["controls"].items():
        result[control] = tuple(entry["guide"])
    return result


def control_title(key: str) -> str:
    return _load()["controls"][key]["title"]


def guide(key: str, title: str | None = None) -> Guide:
    """The guide for ``key``; KeyError when there is none.

    ``title`` names the window: a patch or mode passes its own display name,
    a control uses the title stored with its guide.
    """
    lines = guide_lines()[key]
    if title is None:
        title = control_title(key)
    return Guide(title=title, lines=lines)
