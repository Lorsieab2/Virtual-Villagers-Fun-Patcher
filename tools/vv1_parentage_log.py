"""Render the small, browser-readable parentage log.

This module is retained under its original development filename so existing
imports continue to work.  ``tools.parentage_log`` is the public all-five-game
entry point.
"""

from __future__ import annotations

import base64
import html
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


SKILL_ORDER = ("Parenting", "Building", "Farming", "Healing", "Research")
HEAD_CELL_HEIGHT = 65
BODY_CELL_HEIGHT = 65
ROW_GUIDE = (
    "head and body values correspond to the rows in the Body and Head pictures "
    "in the Images folder."
)


@dataclass(frozen=True)
class Person:
    name: str
    sex: int
    head: int
    body: int
    likes: tuple[str, ...] = ()
    dislikes: tuple[str, ...] = ()
    skills: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class BirthCard:
    child: Person
    mother: Person
    father: Person


def parentage_log_filename(game_title: str) -> str:
    """Return the stable per-game filename used beside the modified EXE."""

    return f"{game_title} Parentage Log.html"


def parentage_log_path(output_folder: str | Path, game_title: str) -> Path:
    """Return the stable per-game path inside a copied game folder."""

    return Path(output_folder) / parentage_log_filename(game_title)


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _sprite_url(
    image_root: str,
    filename: str,
    image_data: Mapping[str, bytes] | None,
) -> str:
    if image_data is not None and filename in image_data:
        encoded = base64.b64encode(image_data[filename]).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    return f"{image_root.rstrip('/')}/{filename}"


def _person_sex_prefix(person: Person) -> str:
    return "female" if int(person.sex) == 1 else "male"


def _portrait(person: Person, image_root: str, image_data: Mapping[str, bytes] | None) -> str:
    prefix = _person_sex_prefix(person)
    head_url = _sprite_url(image_root, f"{prefix}_heads.png", image_data)
    body_group = int(person.body) // 10
    body_row = int(person.body) % 10
    body_url = _sprite_url(image_root, f"{prefix}_bodies{body_group}0.png", image_data)
    head_y = int(person.head) * HEAD_CELL_HEIGHT
    body_y = body_row * BODY_CELL_HEIGHT
    return (
        '<div class="portrait" aria-label="'
        + _escape(f"{person.name} head {person.head}, body {person.body}")
        + '">'
        f'<span class="head-sprite" style="background-image:url(\'{head_url}\');'
        f'background-position:0 -{head_y}px"></span>'
        f'<span class="body-sprite" style="background-image:url(\'{body_url}\');'
        f'background-position:0 -{body_y}px"></span>'
        "</div>"
    )


def _person_block(
    label: str,
    person: Person,
    image_root: str,
    image_data: Mapping[str, bytes] | None,
    include_details: bool,
) -> str:
    result = [
        '<section class="person">',
        f"<h3>{_escape(label)}</h3>",
        f"<p class=\"name\">{_escape(person.name)}</p>",
        _portrait(person, image_root, image_data),
        f"<p>Head: {_escape(person.head)} &nbsp; Body: {_escape(person.body)}</p>",
    ]
    if include_details:
        likes = ", ".join(_escape(item) for item in person.likes) or "None"
        dislikes = ", ".join(_escape(item) for item in person.dislikes) or "None"
        result.extend(
            [
                f"<p><b>Likes:</b> {likes}</p>",
                f"<p><b>Dislikes:</b> {dislikes}</p>",
                "<p><b>Skills:</b></p>",
                "<ul class=\"skills\">",
            ]
        )
        for skill in SKILL_ORDER:
            result.append(
                f"<li>{_escape(skill)}: {_escape(person.skills.get(skill, 0))}</li>"
            )
        result.append("</ul>")
    result.append("</section>")
    return "\n".join(result)


def render_parentage_html(
    cards: Sequence[BirthCard],
    *,
    game_title: str = "Virtual Villagers - A New Home",
    image_root: str = "Images",
    image_data: Mapping[str, bytes] | None = None,
) -> str:
    """Return a complete HTML document for any number of birth cards."""

    sections: list[str] = []
    for card in cards:
        sections.append(
            "\n".join(
                [
                    '<article class="birth-card">',
                    _person_block("Child", card.child, image_root, image_data, True),
                    '<div class="parents">',
                    _person_block("Mother", card.mother, image_root, image_data, False),
                    _person_block("Father", card.father, image_root, image_data, False),
                    "</div>",
                    "</article>",
                ]
            )
        )
    body = "\n".join(sections) or '<p class="empty">No children recorded yet.</p>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(game_title)} Parentage Log</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; color: #241b12; background: #f7f0e5; }}
h1 {{ margin-bottom: .25rem; }}
.birth-card {{ background: #fffaf2; border: 1px solid #cdbb9f; padding: 1rem; margin: 1rem 0; max-width: 50rem; }}
.person {{ min-width: 10rem; }}
.person h3 {{ margin: 0 0 .25rem; }}
.name {{ font-weight: 700; margin: .25rem 0; }}
.parents {{ display: flex; gap: 2rem; flex-wrap: wrap; margin-top: 1rem; border-top: 1px solid #ddccb5; padding-top: 1rem; }}
.portrait {{ position: relative; width: 80px; height: 130px; image-rendering: auto; }}
.head-sprite, .body-sprite {{ position: absolute; display: block; background-repeat: no-repeat; }}
.head-sprite {{ left: 5px; top: 0; width: 70px; height: 65px; }}
.body-sprite {{ left: 0; top: 65px; width: 80px; height: 65px; }}
.skills {{ margin-top: 0; padding-left: 1.25rem; }}
.empty {{ color: #6b5a47; }}
</style>
</head>
<body>
<h1>{_escape(game_title)} Parentage Log</h1>
<p><b>Head/body row guide:</b> {ROW_GUIDE}</p>
<p>In other words, the head and body numbers are row numbers, starting at row 0. Child records are added when a child becomes an independent villager.</p>
{body}
</body>
</html>
"""


def write_parentage_html(
    destination: str | Path,
    cards: Sequence[BirthCard],
    *,
    game_title: str = "Virtual Villagers - A New Home",
    image_root: str = "Images",
    image_data: Mapping[str, bytes] | None = None,
) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        render_parentage_html(
            cards,
            game_title=game_title,
            image_root=image_root,
            image_data=image_data,
        ),
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)
    return path
