"""Compare every game's Tech and Details dialog shell against VV2's.

VV2 is the reference implementation.  This reports differences in the visible
shell -- dialog caption, row labels, cost text, button text, the ESC hint and
the Cancel control -- so a divergence is a listed finding rather than something
noticed in a screenshot.

It deliberately does NOT compare which upgrades exist, their costs, or their
icons: those differ per game by design.  Only the wording and the surrounding
chrome are compared.

Run directly for a report; tests/test_upgrade_menu_shell_text_parity.py asserts
that the reported differences stay inside the reviewed allowances.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RESOURCES = {
    "vv1": ROOT / "native/vv1_origins_icons/vv1_origins_icons.rc",
    "vv2": ROOT / "native/vv2_origins_icons/vv2_origins_icons.rc",
    "vv3": ROOT / "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.rc",
    "vv4": ROOT / "native/vv4_origins_icons/vv4_origins_icons.rc",
    "vv5": ROOT / "native/vv5_task9_origins/vv5_task9_origins.rc",
}

# Dialog ids that carry the public Tech and Details menus per game.
DIALOGS = {
    "vv1": {"tech": 201, "details": 202},
    "vv2": {"tech": 211, "details": 212},
    "vv3": {"tech": 201, "details": 202},
    "vv4": {"tech": 201, "details": 202},
    "vv5": {"tech": 201, "details": 202},
}

REFERENCE = "vv2"

DIALOG_RE = re.compile(
    r"^(?P<id>\d+)\s+DIALOG(?:EX)?\b(?P<rest>.*?)^BEGIN$(?P<body>.*?)^END$",
    re.MULTILINE | re.DOTALL,
)
CAPTION_RE = re.compile(r'^\s*CAPTION\s+"(?P<caption>(?:[^"]|"")*)"', re.MULTILINE)
TEXT_RE = re.compile(
    r'^\s*(?P<kind>LTEXT|RTEXT|CTEXT|PUSHBUTTON|DEFPUSHBUTTON|CONTROL)\s+'
    r'"(?P<text>(?:[^"]|"")*)"',
    re.MULTILINE,
)

# Badge (checkmark) controls, ICON 109 with ids 1100+row.  The dialog proc
# shows one when the corresponding "satisfied" bit is set in the state word.
#
# Every game's exe builds the TECH state word with only two of those bits --
# the Tech Point Doubler and Food Point Doubler ownership flags.  Nothing sets
# a satisfied bit above 4, so a badge control for any other row can never light
# up.  That is why a checkmark is only ever seen on those two rows, and why they
# are the two rows whose button also flips to "Remove".
#
# VV3, VV4 and VV5 nevertheless declare badge controls for all 14 Tech rows.
# The extra five (1109..1113) are inert.  They are recorded so the difference is
# a known, reviewed fact rather than a surprise, and so a future change that
# starts setting higher bits has to come back through this audit.
BADGE_RE = re.compile(r"^\s*ICON\s+\d+,\s*(?P<id>11\d\d),", re.MULTILINE)
SATISFIED_BITS_SET_BY_EXE = {3, 4}   # Tech Point Doubler, Food Point Doubler

# The Tech dialog is opened with `push <accumulator>; push 0; call`, where the
# 0 is villager_menu false.
TECH_DIALOG_CALL = re.compile(
    r"push\s+(?P<reg>eax|edi)\s*\n\s*push\s+0\s*\n\s*call", re.MULTILINE
)
# Accepts hex as well as decimal: these blocks use both, and a decimal-only
# pattern would silently skip a flag added as `or eax, 0x20`.
OR_BIT = re.compile(
    r"or\s+e(?:ax|bx|cx|dx|si|di|bp),\s*(?P<value>0[xX][0-9a-fA-F]+|\d+)\b"
)
# `1 << (8 + row)` markers meaning "this row is unavailable", not satisfied
# bits.  They sit in the same block, so they are excluded explicitly.
UNAVAILABLE_MASK_VALUES = {0x800, 0x1000, 0x1800}

GENERATORS = {
    game: ROOT / f"scripts/build_{game}_origins_feature.py"
    for game in ("vv1", "vv2", "vv3", "vv4", "vv5")
}


def parse_dialogs(path: Path) -> dict[int, dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out: dict[int, dict] = {}
    for match in DIALOG_RE.finditer(text):
        dialog_id = int(match.group("id"))
        body = match.group("body")
        caption = CAPTION_RE.search(match.group("rest") + body)
        strings = [
            (m.group("kind"), m.group("text"))
            for m in TEXT_RE.finditer(body)
            if m.group("text").strip()
        ]
        out[dialog_id] = {
            "caption": caption.group("caption") if caption else None,
            "strings": strings,
        }
    return out


COST_RE = re.compile(r"^[\d,]+ tech points$")
CHROME = {"Cancel", "Press ESC to exit this menu."}


def rows_of(dialog: dict) -> list[dict]:
    """Group a dialog's strings into one record per upgrade row.

    A row is a label, then its cost, then its button.  Grouping matters because
    a set of all strings hides deletions: removing one `Buy` leaves the set
    unchanged, and removing a cost line produces no new text either.  Comparing
    row by row makes a missing control visible.
    """
    rows: list[dict] = []
    current: dict | None = None
    for kind, text in dialog["strings"]:
        if text in CHROME:
            continue
        if kind == "LTEXT" and COST_RE.match(text):
            if current is not None:
                current["cost"] = text
            continue
        if kind in ("PUSHBUTTON", "DEFPUSHBUTTON"):
            if current is not None:
                current["button"] = text
            continue
        if kind == "LTEXT":
            current = {"label": text, "cost": None, "button": None}
            rows.append(current)
    return rows


def shell_of(dialog: dict) -> dict:
    texts = [text for _, text in dialog["strings"]]
    return {
        "caption": dialog["caption"],
        "cancel": "Cancel" in texts,
        "escape_hint": "Press ESC to exit this menu." in texts,
        "escape_hint_count": texts.count("Press ESC to exit this menu."),
        # The row text itself, so the standalone report catches a reworded
        # label, cost string or button -- not only the surrounding chrome.
        "texts": set(texts),
        # ...and the per-row grouping, so it also catches a MISSING one.
        "rows": rows_of(dialog),
    }


def badge_ids(path: Path, dialog_id: int) -> list[int]:
    """Badge control ids declared inside one dialog.

    Reuses DIALOG_RE, the same matcher the shell comparison relies on.  An
    independent copy of that pattern silently matched nothing and reported
    "0 controls" for every game.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    for match in DIALOG_RE.finditer(text):
        if int(match.group("id")) != dialog_id:
            continue
        return sorted(
            int(m.group("id")) for m in BADGE_RE.finditer(match.group("body"))
        )
    return []


def badge_coverage() -> dict:
    """(rows, badge controls) per game and screen."""
    out: dict = {}
    for game, path in RESOURCES.items():
        if not path.is_file():
            continue
        parsed = parse_dialogs(path)
        for screen in ("tech", "details"):
            dialog = parsed.get(DIALOGS[game][screen])
            if dialog is None:
                continue
            rows = [
                text
                for kind, text in dialog["strings"]
                if kind == "LTEXT"
                and "tech points" not in text
                and "ESC" not in text
            ]
            out[(game, screen)] = (
                len(rows),
                len(badge_ids(path, DIALOGS[game][screen])),
            )
    return out


def tech_state_bits(generator: Path) -> set[int]:
    """Bit values the TECH menu's state builder sets.

    Bounded exactly rather than by scanning the whole generator: the Details
    menu builds its own state word and also contains `or edi, 8`, so a
    file-wide search would report the Tech behaviour as intact even if the Tech
    path stopped setting that bit.

    The block runs from the `xor <reg>, <reg>` that clears the accumulator to
    the `push <reg>; push 0; call` that opens the Tech dialog.
    """
    text = generator.read_text(encoding="utf-8")
    call = TECH_DIALOG_CALL.search(text)
    if call is None:
        raise RuntimeError(f"{generator.name}: no Tech dialog invocation found")
    register = call.group("reg")
    zero = re.compile(rf"xor\s+{register},\s*{register}\b")
    starts = [m.start() for m in zero.finditer(text) if m.start() < call.start()]
    if not starts:
        raise RuntimeError(
            f"{generator.name}: the Tech state accumulator is never cleared"
        )
    block = text[starts[-1] : call.end()]
    values = {int(m.group("value"), 0) for m in OR_BIT.finditer(block)}
    # Drop the unavailable markers so only satisfied bits are reported.
    return values - UNAVAILABLE_MASK_VALUES


def audit_badges(verbose: bool = True) -> list[str]:
    """Report badge-control coverage and which Tech rows can light up.

    Only the TECH menu's doubler bits are established here.  The Details state
    word is computed per selected villager and is deliberately NOT
    characterised, so no claim is made about which of its rows light up.
    """
    problems: list[str] = []
    coverage = badge_coverage()
    if verbose:
        print("\nbadge (checkmark) control coverage:")
        for (game, screen), (rows, badges) in sorted(coverage.items()):
            note = ""
            if screen == "tech":
                inert = max(0, badges - len(SATISFIED_BITS_SET_BY_EXE))
                note = (
                    f"  (only rows {sorted(SATISFIED_BITS_SET_BY_EXE)} can show"
                    f"; {inert} inert)"
                )
            print(f"  {game}/{screen:<8} rows={rows:>2} badges={badges:>2}{note}")
    return problems


def audit(verbose: bool = True) -> list[str]:
    problems: list[str] = []
    parsed = {}
    for game, path in RESOURCES.items():
        if not path.is_file():
            problems.append(f"{game}: resource {path} is missing")
            continue
        parsed[game] = parse_dialogs(path)

    if REFERENCE not in parsed:
        return problems + [f"reference {REFERENCE} resource unavailable"]

    for screen in ("tech", "details"):
        ref_id = DIALOGS[REFERENCE][screen]
        if ref_id not in parsed[REFERENCE]:
            problems.append(f"{REFERENCE}: dialog {ref_id} ({screen}) not found")
            continue
        reference = shell_of(parsed[REFERENCE][ref_id])
        if verbose:
            print(f"\n{screen}: reference {REFERENCE} dialog {ref_id}")
            print(f"  caption      : {reference['caption']!r}")
            print(f"  rows/strings : {len(reference['texts'])}")
            print(f"  Cancel       : {reference['cancel']}")
            print(
                f"  ESC hint     : {reference['escape_hint']} "
                f"(x{reference['escape_hint_count']})"
            )

        for game in RESOURCES:
            if game == REFERENCE or game not in parsed:
                continue
            dialog_id = DIALOGS[game][screen]
            if dialog_id not in parsed[game]:
                problems.append(f"{game}: dialog {dialog_id} ({screen}) not found")
                continue
            actual = shell_of(parsed[game][dialog_id])
            if verbose:
                print(
                    f"  {game} d{dialog_id}: caption={actual['caption']!r} "
                    f"strings={len(actual['texts'])} cancel={actual['cancel']} "
                    f"esc={actual['escape_hint']}(x{actual['escape_hint_count']})"
                )
            if actual["caption"] != reference["caption"]:
                problems.append(
                    f"{game}/{screen}: caption {actual['caption']!r} != "
                    f"{REFERENCE} {reference['caption']!r}"
                )
            if actual["cancel"] != reference["cancel"]:
                problems.append(
                    f"{game}/{screen}: Cancel button present={actual['cancel']}, "
                    f"{REFERENCE}={reference['cancel']}"
                )
            if actual["escape_hint"] != reference["escape_hint"]:
                problems.append(
                    f"{game}/{screen}: ESC hint present={actual['escape_hint']}, "
                    f"{REFERENCE}={reference['escape_hint']}"
                )
            if reference["escape_hint"] and actual["escape_hint_count"] != 1:
                problems.append(
                    f"{game}/{screen}: ESC hint appears "
                    f"{actual['escape_hint_count']} times, expected exactly 1"
                )
            # A game may OMIT an upgrade it does not have -- VV1 has no
            # Collections rows -- but it may never reword one it does show.
            for text in sorted(actual["texts"] - reference["texts"]):
                problems.append(
                    f"{game}/{screen}: shows wording {REFERENCE} does not: {text!r}"
                )
            # Every row this game DOES show must carry the same cost text and
            # button as VV2's row of the same name.  A plain set difference
            # cannot see a deleted cost line or a deleted Buy button, because
            # removing one repeated string leaves the set unchanged.
            expected_rows = {row["label"]: row for row in reference["rows"]}
            for row in actual["rows"]:
                expected = expected_rows.get(row["label"])
                if expected is None:
                    continue  # already reported above as unknown wording
                for field in ("cost", "button"):
                    if row[field] != expected[field]:
                        problems.append(
                            f"{game}/{screen}: row {row['label']!r} has "
                            f"{field}={row[field]!r}, {REFERENCE} has "
                            f"{expected[field]!r}"
                        )
    return problems


def main() -> int:
    print("Upgrade-menu shell parity (reference: VV2)")
    problems = audit()
    problems.extend(audit_badges())
    print()
    if problems:
        print("DIFFERENCES:")
        for problem in problems:
            print("  -", problem)
        return 1
    print("OK: every game's Tech and Details shell matches VV2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
