"""Reading the stock executables for the island-event catalog tests (tests/test_game_mechanics_events_vv*.py):
each game's own string table, its code and its tables, read only.

String tables (each entry's English text):
  A New Home        the getter 0x433880 walks 0x275 entries of 20 bytes at 0x487208: (id, English, 3 more languages)
  The Lost Children 12-byte entries (id, English, German) around 0x496300
  The Secret City, The Tree of Life, New Believers: 16-byte entries (id, name, text, 0)
The table is walked from a known entry both ways while each entry is well formed."""
from __future__ import annotations

import struct
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
# game: (a known entry's va, entry size, the text's field, the name's field or None)
TABLES = {1: (0x487208, 20, 1, None), 2: (0x498328, 12, 1, None), 3: (0x4B0410, 16, 2, 1),
          4: (0x4C41F8, 16, 2, 1), 5: (0x4D7B80, 16, 2, 1)}

try:
    import pefile
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    HAVE_TOOLS = True
except ImportError:  # pragma: no cover - optional analysis tools
    HAVE_TOOLS = False


def path(game: int) -> Path:
    for folder in (ROOT / "research" / "stock-executables", ROOT / "inputs" / f"vv{game}-stock-copy"):
        candidate = folder / f"Virtual Villagers - {EXE[game]}.exe"
        if candidate.is_file():
            return candidate
    return ROOT / "research" / "stock-executables" / f"Virtual Villagers - {EXE[game]}.exe"


def available(game: int) -> bool:
    return HAVE_TOOLS and path(game).is_file()


class Exe:
    def __init__(self, game: int) -> None:
        self.raw = path(game).read_bytes()
        self.pe = pefile.PE(data=self.raw, fast_load=True)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.game = game

    def off(self, va: int) -> int | None:
        try:
            return self.pe.get_offset_from_rva(va - self.base)
        except Exception:  # noqa: BLE001 -- an address outside the image
            return None

    def u32(self, va: int, count: int = 1) -> tuple[int, ...]:
        return struct.unpack_from(f"<{count}I", self.raw, self.off(va))

    def bytes_at(self, va: int, count: int) -> bytes:
        at = self.off(va)
        return self.raw[at:at + count]

    def cstring(self, va: int) -> str | None:
        if not self.base <= va < self.base + 0x800000:
            return None
        at = self.off(va)
        if at is None or at >= len(self.raw):
            return None
        end = self.raw.find(b"\0", at)
        if end < 0 or end - at > 8000:
            return None
        return self.raw[at:end].decode("latin-1")

    def disasm(self, start: int, end: int) -> list[tuple[int, str, str]]:
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        return [(i.address, i.mnemonic, i.op_str) for i in md.disasm(self.bytes_at(start, end - start), start)]

    def instruction(self, va: int) -> str:
        address, mnemonic, op_str = self.disasm(va, va + 16)[0]
        return f"{mnemonic} {op_str}".strip()

    def strings(self) -> dict[int, str]:
        return _strings(self.game)


@lru_cache(maxsize=None)
def exe(game: int) -> Exe:
    return Exe(game)


@lru_cache(maxsize=None)
def _strings(game: int) -> dict[int, str]:
    e = exe(game)
    va, step, text, _name = TABLES[game]

    def entry(v: int):
        at = e.off(v)
        if at is None or at + step > len(e.raw):
            return None
        fields = struct.unpack_from(f"<{step // 4}I", e.raw, at)
        words = e.cstring(fields[text])
        return (fields[0], words) if fields[0] < 0x10000 and words is not None else None

    start = va
    while entry(start - step):
        start -= step
    out: dict[int, str] = {}
    v = start
    while (found := entry(v)) is not None:
        out.setdefault(found[0], found[1].replace("\r", ""))
        v += step
    return out


def text(game: int, string_id: int) -> str:
    """A string's English text, its layout spaces and line breaks folded to single spaces."""
    return " ".join(_strings(game)[string_id].split())


# The catalogs write the games' name placeholders in words: + is him or her, ^ he or she.
PLACEHOLDERS = (("himself (herself)", "+self"), ("him (her)", "+"), ("he (she)", "^"))
# Quoted words in a catalog that are not buttons: patch names and words the game shows elsewhere.
NOT_BUTTONS = {"Restore Missing Island Events", "Story / Cheat Upgrades", "Fix Vanilla Bugs",
               "Gong of Wonder Coconuts Fix"}


def game_words(button: str) -> str:
    for words, mark in PLACEHOLDERS:
        button = button.replace(words, mark)
    return button


def catalog_texts(module) -> list[str]:
    """Every line a catalog module can show (src/vv_game_mechanics_events_vv<N>.py)."""
    def text_of(item):
        return item if isinstance(item, str) else item.text
    out = [text_of(line) for line in getattr(module, "RULES", ())]
    for event in tuple(getattr(module, "EVENTS", ())) + tuple(getattr(module, "EXTRA", ())):
        out.append(event.text)
        out += [text_of(sub) for sub in event.subs]
        out += [effect for _feature, effect in event.patched]
    return out


def quoted_buttons(module) -> set[str]:
    """The button texts a catalog quotes (each sub-bullet that starts with a quoted choice)."""
    import re
    found = set()
    for event in tuple(getattr(module, "EVENTS", ())) + tuple(getattr(module, "EXTRA", ())):
        for sub in event.subs:
            text = sub if isinstance(sub, str) else sub.text
            match = re.match(r'"([^"]+)":', text)
            if match:
                found.add(match.group(1))
    return found - NOT_BUTTONS


def game_strings(game: int) -> set[str]:
    return {" ".join(words.split()) for words in _strings(game).values()}


def village(game: int, installed=frozenset()):
    """A new, empty village of `game` with the patches `installed` in its exe (vv_game_mechanics.blank_save)."""
    import time
    import vv_game_mechanics as gm
    now = time.time()
    return gm.Village(Path("."), game, 1, Path(f"{game}.ldw"), gm.blank_save(game, now), frozenset(installed), now)


class CatalogChecks:
    """The checks every game's catalog test runs (mixed into a unittest.TestCase with GAME and CATALOG set)."""
    GAME = 0
    CATALOG = None

    def test_every_quoted_button_is_the_games_own(self) -> None:
        if not available(self.GAME):
            self.skipTest("the stock exe or capstone/pefile is absent")
        words = game_strings(self.GAME)
        buttons = quoted_buttons(self.CATALOG)
        self.assertTrue(buttons)
        for button in sorted(buttons):
            with self.subTest(button=button):
                self.assertIn(game_words(button), words)

    def test_every_event_has_a_parent_line(self) -> None:
        import vv_game_mechanics_events as events
        facts = events.facts(village(self.GAME))
        titles = [f.text for f in facts if not f.sub]
        for event in tuple(self.CATALOG.EVENTS) + tuple(getattr(self.CATALOG, "EXTRA", ())):
            heading = event.title + " --"
            with self.subTest(event=event.title):
                if event.only_with:
                    self.assertFalse(any(t.startswith(heading) for t in titles))
                else:
                    self.assertTrue(any(t.startswith(heading) for t in titles))
        self.assertTrue(all(f.group == "Island events" for f in facts))

    def test_the_general_page_keeps_every_line(self) -> None:
        import vv_game_mechanics as gm
        import vv_game_mechanics_events as events
        general = gm.render(gm.general(self.GAME))
        for fact in events.facts(village(self.GAME)):
            with self.subTest(text=fact.text[:60]):
                self.assertTrue(gm.tidy(fact.text) in general, "dropped from the general rules page")

    def test_patches_only_when_in_the_game(self) -> None:
        import vv_game_mechanics as gm
        import vv_game_mechanics_events as events
        stock = gm.render(events.facts(village(self.GAME)))
        self.assertNotIn("With the patcher's", stock)
        self.assertNotIn("(in this game)", stock)

    def test_no_vague_words(self) -> None:
        for text in catalog_texts(self.CATALOG):
            with self.subTest(text=text[:60]):
                self.assertNotRegex(text, r"not (yet )?worked out|etc\.|\bsome\b|\babout\b|\(\)")
