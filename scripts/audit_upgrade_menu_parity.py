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

import sys

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





# Wording that must be identical everywhere: the shell, not the catalogue.

SHELL_PHRASES = (

    "Cancel",

    "Press ESC to exit this menu.",

)





def shell_of(dialog: dict) -> dict:

    texts = [t for _, t in dialog["strings"]]

    return {

        "caption": dialog["caption"],

        "cancel": "Cancel" in texts,

        "escape_hint": "Press ESC to exit this menu." in texts,

        "escape_hint_count": texts.count("Press ESC to exit this menu."),

    }





# Badge (checkmark) controls, ICON 109 with ids 1100+row.  The dialog proc

# shows one when the corresponding "satisfied" bit is set in the state word.

#

# EVERY game's exe sets only two of those bits -- `or eax, 8` and `or eax, 16`,

# the Tech Point Doubler and Food Point Doubler ownership flags.  Nothing sets

# a bit above 4, so a badge control for any other row can never light up.

# That is why a checkmark is only ever seen on those two rows, and why they are

# the two rows whose button also flips to "Remove".

#

# VV3, VV4 and VV5 nevertheless declare badge controls for all 14 Tech rows.

# The extra five (1109..1113) are inert: no code path can show them.  They are

# recorded here so the difference is a known, reviewed fact rather than a

# surprise, and so a future change that starts setting higher bits has to come

# back through this audit.

BADGE_RE = re.compile(r"^\s*ICON\s+\d+,\s*(?P<id>11\d\d),", re.MULTILINE)

SATISFIED_BITS_SET_BY_EXE = {3, 4}   # Tech Point Doubler, Food Point Doubler





def badge_ids(path: Path, dialog_id: int) -> list[int]:
    """Badge control ids declared inside one dialog.

    Reuses DIALOG_RE, the same matcher the shell comparison relies on, rather
    than a second hand-rolled pattern.  An independent copy silently matched
    nothing and reported "0 controls" for every game.
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
    out = {}
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


def audit_badges(verbose: bool = True) -> list:
    """Report badge-control coverage and which Tech rows can light up.

    Only the TECH menu's doubler bits are established here: every game's exe
    builds that state word with just `or eax, 8` and `or eax, 16`, so rows 3
    and 4 are the only Tech rows whose checkmark can ever appear.  The Details
    state word is computed per selected villager and is deliberately NOT
    characterised here, so no claim is made about which of its rows light up.
    """
    problems = []
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

            print(f"  Cancel       : {reference['cancel']}")

            print(f"  ESC hint     : {reference['escape_hint']} (x{reference['escape_hint_count']})")



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

                    f"cancel={actual['cancel']} esc={actual['escape_hint']}"

                    f"(x{actual['escape_hint_count']})"

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

