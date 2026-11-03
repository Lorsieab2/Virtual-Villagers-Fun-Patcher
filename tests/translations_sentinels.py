"""The sentinel proof for tests/test_translations_sentinels.py and scripts/audit_translation_keys.py.

Every patch text of a game (data/translations/patcher_strings.json, as the "Make a translation" template offers it:
vv_translations.template_rows) is translated to a UNIQUE sentinel ("Z0042", keeping the English's placeholders),
a Translation.txt of those is put in an emulated game (tests/translations_emulation.py: the stock executable with
the real "VVFP Translations.dll" mapped), and each text is then asked for the way its route asks for it:

  key      VvfpTranslateKey / VvfpTranslateKeyText with the row's stem and English (what vvfp_tr / vvfp_trf /
           ce_tr_printf in the companion do);
  patch    the English written at the patch's address, then VvfpStartup: the text read back at that address;
  content  VvfpTranslateText with the English as the game or a dialog shows it (what the Unicode Text draw hooks
           and the dialog hook call).

A row is PROVEN when the sentinel that comes back is its own.  Anything else is listed with its reason.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import scan_patch_text as scan  # noqa: E402
import vv_translation_format as fmt  # noqa: E402
import vv_translations as vt  # noqa: E402

CONV = re.compile(r"%[-+ #0]*(?:\d+|\*)?(?:\.\d+)?(?:hh|h|ll|l)?[diouxXsc]")
PLAIN = re.compile(r"%[sdiu]")
START_LIMIT = 3_000_000_000
CAP = 3900


def sentinel_for(index: int, english: str) -> str:
    """Unique, short (an exe patch's text is replaced in place within its own bytes), ASCII, with the English's
    placeholders and named variables kept in order."""
    parts = [f"Z{index:04d}"]
    parts += fmt.printf_conversions(english)
    parts += ["{%s}" % name for name in fmt.named_variables(english)]
    return " ".join(parts)


def fill(text: str) -> str:
    """The text as the game shows it after printf: a number for %d %i %u, a name for %s, %% as %."""
    text = PLAIN.sub(lambda m: "Zed" if m.group(0) == "%s" else "7", re.sub(r"%%", "\x00", text))
    return text.replace("\x00", "%")


def is_pattern(english: str) -> bool:
    found = fmt.printf_conversions(english)
    return bool(found) and all(PLAIN.fullmatch(c) for c in found)


def same_shown(got: str, want: str) -> bool:
    """Two adjacent conversions ("%s%s") split what the game printed between them either way: compare the
    letters, not where the pieces are separated."""
    return got == want or re.sub(r"\s+", "", got) == re.sub(r"\s+", "", want)


@dataclass
class Result:
    stem: str
    route: str
    english: str
    sentinel: str
    status: str            # "proven" or "unproven"
    why: str = ""
    got: str = ""


@dataclass
class GameRun:
    game: int
    rows: list = field(default_factory=list)       # the template's patcher rows (dicts), in order
    results: list = field(default_factory=list)
    dropped: list = field(default_factory=list)    # rows the template leaves out (shadowed by an English)
    active: int = 0

    def unproven(self) -> list:
        return [r for r in self.results if r.status != "proven"]


def patcher_rows_of_template(game: int, stock_english: set[str] | None = None) -> tuple[list, list]:
    """(offered, dropped): the game's patcher rows as vv_translations.template_rows offers them (the same
    filter, vv_translations.content_shadowed), the stock English counted as taken."""
    taken = set(stock_english or ())
    offered, dropped = [], []
    for entry in vt.load_patcher_strings():
        if f"vv{game}" not in entry.get("games", ()):
            continue
        (dropped if vt.content_shadowed(entry, taken) else offered).append(entry)
    return offered, dropped


def va_of(stem: str) -> int | None:
    m = re.match(r"^patch/0x([0-9a-f]+)(?:\.v\d+)?$", stem)
    return int(m.group(1), 16) if m else None


def patch_group(entry: dict) -> str:
    """The patch file a row's text comes from (its context names it): two files that rewrite the same bytes (the
    Expanded Time Warp build and the Origins patch of The Tree of Life) are never in one game."""
    return entry.get("context", "").split(" (")[0]


def prove(game: int, exe: bytes, stock_texts: set[str]) -> GameRun:
    """Build the sentinel file for `game`, run the DLL over it in the emulated game and ask for every row."""
    from translations_emulation import Game, TITLES   # noqa: PLC0415 (needs unicorn)

    keys = scan.key_call_stems()
    offered, dropped = patcher_rows_of_template(game, stock_texts)
    run = GameRun(game=game, rows=offered, dropped=dropped)
    rows, meta = [], []
    for index, entry in enumerate(offered):
        source, _slash, ident = entry["stem"].partition("/")
        english = entry["english"]
        s = sentinel_for(index, english)
        route = scan.route_of(entry["stem"], keys)
        problems = [i.message for i in fmt.check_row(english, s, vt._rules_for(entry)) if i.severity == "error"]
        if source == "patch" and len(s.encode()) > len(english.encode("cp1252", errors="replace")):
            problems.append("the sentinel is longer than the patch's own bytes")
        if problems:
            run.results.append(Result(entry["stem"], route, english, s, "unproven", "sentinel rejected: " + problems[0]))
            continue
        rows.append(fmt.Row(fmt.make_key(source, ident, english), english, s, entry.get("notes", "")))
        meta.append((entry, route, s))
    tf = fmt.template_file(rows, TITLES[game], "Sentinel", "zz")
    for prepared, source_row in zip(tf.rows, rows):
        prepared.translation = source_row.translation
    data = b"\xef\xbb\xbf" + fmt.dumps(tf).encode("utf-8")

    groups = [""]
    for entry, route, _s in meta:
        if route == "patch" and patch_group(entry) not in groups:
            groups.append(patch_group(entry))
    done_stems: set[str] = set()
    for group in groups:
        g = Game(game, exe, data)
        patch_sites: dict[int, tuple] = {}
        for entry, route, s in meta:
            va = va_of(entry["stem"])
            if route != "patch" or patch_group(entry) != group or va is None or va in patch_sites:
                continue
            if g.p.mapped(va, 4):
                patch_sites[va] = (entry, s)
                g.p.write(va, entry["english"].encode("cp1252", errors="replace") + bytes([0]))
        g.p.call(g.p.exports["VvfpStartup"], [game, 0], limit=START_LIMIT)
        run.active = g.active()

        def cstr(text: bytes) -> int:
            at = g.p.alloc(len(text) + 1)
            g.p.write(at, text + bytes([0]))
            return at

        for entry, route, s in meta:
            stem, english = entry["stem"], entry["english"]
            if stem in done_stems:
                continue
            if route == "patch" and patch_group(entry) != group:
                continue
            if route != "patch" and group != "":
                continue
            done_stems.add(stem)
            try:
                raw_english = english.encode("cp1252")
            except UnicodeEncodeError:
                run.results.append(Result(stem, route, english, s, "unproven", "English is not Windows-1252"))
                continue
            shown = fill(english) if is_pattern(english) else english
            want = fill(s) if is_pattern(english) else s
            if route == "patch":
                va = va_of(stem)
                if va not in patch_sites or patch_sites[va][0] is not entry:
                    run.results.append(Result(stem, route, english, s, "unproven",
                                              "the address is not in the stock image" if va not in patch_sites
                                              else "another patch row of its file shares this address"))
                    continue
                got = g.raw(va).decode("cp1252", errors="replace")
                want = s                           # in place: the format as written, nothing filled in
            elif route == "key":
                if is_pattern(english):
                    out = g.p.alloc(CAP + 1)
                    done = g.p.export("VvfpTranslateKeyText", cstr(stem.encode()), cstr(raw_english),
                                      cstr(shown.encode("cp1252")), out, CAP)
                    got = g.raw(out).decode("cp1252", errors="replace") if done else english
                else:
                    got = g.raw(g.p.export("VvfpTranslateKey", cstr(stem.encode()), cstr(raw_english), CAP)).decode(
                        "cp1252", errors="replace")
            else:
                got = g.translate(shown.encode("cp1252")).decode("cp1252", errors="replace")
            ok = same_shown(got, want)
            run.results.append(Result(stem, route, english, s, "proven" if ok else "unproven",
                                      "" if ok else "the sentinel did not come back", got))
        del g
    return run
