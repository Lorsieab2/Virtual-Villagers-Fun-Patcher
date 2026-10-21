"""Each Villager Changes action, run through the stock game's own code, shows what its label says.

The owner (2026-10-21): "add all villager actions/behaviors to the Villager Changes section in the
Custom Island Event.  Especially 'Celebrating'" -- then "literally anything villagers can do, on
everyone regardless".  tests/cie_behaviour_catalog.json is the table every adapter declares
(tests/test_cie_behaviour_labels.py pins it against the source).  Here every row is started the way
the adapter starts it -- A New Home / The Lost Children: the starter routine on the villager
array with the villager's index (and its place); the later games: the do-action routine on the
record with the action id and an argument block of zeros, dispatched through the game's own
handler table -- in an emulated stock executable, for an adult, a child and (New Believers) a
Heathen, and afterwards the villager's Details text is what the label names, and in the later
games the action code is the row's id.

Only the string lookup is answered by the test (the game's own English text for the id it asks
for; the language manager is not built in an emulated process).  A run may stop later on world
state the emulated village lacks (an object list, a path); the Details text and the action code
are set first, and they are what is checked.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
EXE = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
CATALOG = json.loads((Path(__file__).resolve().parent / "cie_behaviour_catalog.json").read_text(encoding="utf-8"))

LOOKUPS = {1: (0x433970, 0x433880), 2: (0x441680, 0x4415A0), 3: (0x42F190,), 4: (0x44D3D0,), 5: (0x4506D0,)}
MANAGERS = {3: 0x42F740, 4: 0x44DA20, 5: 0x450D40}         # the language manager's getter (cdecl)
STRING_COPY = {1: 0x44B23D, 2: 0x4682BD, 3: 0x46F780, 4: 0x4724E0, 5: 0x47D7C0}  # into the record
INDIRECT_TEXT = {5: (0x41F100,)}                         # a helper that looks a text up itself
DO_ACTION = {3: 0x455570, 4: 0x45DEC0, 5: 0x465580}
HANDLER_TABLE = {3: 0x596970, 4: 0x501B30, 5: 0x5475C8}   # 8 bytes per id: handler, takes-arguments
TEXT = {1: 0x314, 2: 0x4FC, 3: 0xF28, 4: 0x1CE4, 5: 0x1D14}
CODE = {3: 0xF24, 4: 0x1CE0, 5: 0x1D10}
MARK = b"(before)\0"
NO_CODE = 0xFFFFFFFF


def _stock_or_skip(game):
    path = STOCK / f"Virtual Villagers - {EXE[game]}.exe"
    if not path.is_file():
        pytest.skip(f"stock executable not available: {path.name}")
    pytest.importorskip("unicorn")
    pytest.importorskip("capstone")
    return path


def _texts(game, path):
    import pefile
    import capstone
    import test_cie_behaviour_labels as labels

    pe = pefile.PE(str(path))
    base = pe.OPTIONAL_HEADER.ImageBase
    if game == 1:
        out = {}
        for i in range(0x275):
            sid, p0, *_ = struct.unpack("<5I", pe.get_data(0x487208 - base + i * 20, 20))
            out[sid] = labels._cstr(pe, base, p0, 400)
        return out, None
    if game == 2:
        out = {}
        for i in range(0x36C):
            sid, p0, _p1 = struct.unpack("<III", pe.get_data(0x496300 - base + i * 12, 12))
            out[sid] = labels._cstr(pe, base, p0, 400)
        return out, None
    texts, _ = labels._later_games_tables(pe, base, capstone, game)
    return {sid: text for sid, (_name, text) in texts.items()}, labels.registrations(pe, base, capstone, game)


class Game:
    """One stock executable in the emulator, its village and the game's own starters.

    The starter's own code runs instruction by instruction.  The routines it calls are not run,
    except the string lookup (answered with the game's text for the id), the string copy into
    the villager's record and, in the later games, the do-action routine and its dispatch: a
    helper (the world's object lists, sounds, the step queue) is skipped as if it returned a
    valid pointer, so the starter takes the branch it takes when what it asks for is there."""

    def __init__(self, game):
        import capstone
        from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ_UNMAPPED, UC_HOOK_MEM_WRITE_UNMAPPED
        from story_custom_fixtures import Village
        from story_emulator import Process

        path = _stock_or_skip(game)
        self.game = game
        self.proc = Process(path.read_bytes())
        self.pe = self.proc._exe_pe
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        self.village = Village(self.proc, f"vv{game}")
        self.texts, self.handlers = _texts(game, path)
        self.strings = {}
        self.looked_up = []
        for va in LOOKUPS[game]:
            self.proc.stub(va, self._lookup)
        if game in MANAGERS:
            manager = self.proc.alloc(0x100)
            self.proc.stub(MANAGERS[game], lambda p: (manager, 0))
        if self.handlers is not None:
            for aid, (handler, takes_arguments) in self.handlers.items():
                self.proc.put32(HANDLER_TABLE[game] + aid * 8, handler)
                self.proc.write(HANDLER_TABLE[game] + aid * 8 + 4, bytes([takes_arguments]))
        self.dummy = self.proc.alloc(0x4000)       # what a skipped helper "returns"
        self.zeros = self.proc.alloc(0x40)
        # ...and the do-action itself: a chooser starts the action it picks through it.
        self.allowed = (set(LOOKUPS[game]) | {STRING_COPY[game]} | set(INDIRECT_TEXT.get(game, ()))
                        | ({DO_ACTION[game]} if game in DO_ACTION else set()))

        self.bodies = {}        # starter -> {call site: (next instruction, target or None, pop)}
        self.active = {}
        self.pops = {}

        def _map_on_use(mu, _access, address, _size, _value, _user):
            page = address & ~0xFFF
            if page < 0x10000 or page >= 0xC0000000:
                return False
            mu.mem_map(page, 0x1000)
            return True
        self.proc.mu.hook_add(UC_HOOK_MEM_READ_UNMAPPED | UC_HOOK_MEM_WRITE_UNMAPPED, _map_on_use)
        self.proc.mu.hook_add(UC_HOOK_CODE, self._skip_helpers)
        self.subjects = {
            "adult": self.village.put(2, sex="f", years=30, name="Adult"),
            "child": self.village.put(3, sex="m", years=4, name="Child"),
        }
        if game == 5:
            self.subjects["heathen"] = self.village.put(4, sex="m", years=30, name="Heathen", faction=1)
        self.index = {"adult": 2, "child": 3, "heathen": 4}
        # A body awaiting burial, for the actions that need one.
        self.body = 6
        self.village.put(6, sex="m", years=50, name="Body", health=0)

    # ---- the starter's own code ---------------------------------------------------------------
    def _pop(self, target):
        """Bytes of arguments `target` pops (its first `ret N`)."""
        if target not in self.pops:
            pop = 0
            try:
                data = self.pe.get_data(target - self.pe.OPTIONAL_HEADER.ImageBase, 6000)
                for i in self.md.disasm(data, target):
                    if i.mnemonic == "ret":
                        pop = int(i.op_str, 0) if i.op_str else 0
                        break
            except Exception:
                pop = 0
            self.pops[target] = pop
        return self.pops[target]

    def _body(self, start):
        """The call sites of the routine at `start` (its own code, to its last ret)."""
        if start not in self.bodies:
            base = self.pe.OPTIONAL_HEADER.ImageBase
            data = self.pe.get_data(start - base, 12000)
            sites = {}
            pushes = 0
            ins = list(self.md.disasm(data, start))
            end = start
            for k, i in enumerate(ins):
                if i.mnemonic == "ret":
                    end = i.address
                    nxt = ins[k + 1] if k + 1 < len(ins) else None
                    if nxt is None or nxt.mnemonic in ("nop", "int3") or data[nxt.address - start] in (0x90, 0xCC):
                        if not any(j.address > i.address for j in ins[:k] if j.mnemonic.startswith("j")
                                   and j.op_str.startswith("0x") and int(j.op_str, 16) > i.address):
                            break
                if i.mnemonic == "push":
                    pushes += 1
                if i.mnemonic == "call":
                    target = int(i.op_str, 16) if i.op_str.startswith("0x") else None
                    pop = self._pop(target) if target is not None else 4 * pushes
                    sites[i.address] = (i.address + i.size, target, pop)
                    pushes = 0
                if i.mnemonic == "add" and i.op_str.startswith("esp"):
                    pushes = 0
            self.bodies[start] = (sites, end)
        return self.bodies[start]

    def _skip_helpers(self, mu, address, _size, _user):
        for start, (sites, end) in self.active.items():
            site = sites.get(address)
            if site is None:
                continue
            nxt, target, pop = site
            if target in self.allowed:
                return
            if target is not None and target in self.starters:
                return
            p = self.proc
            p.set_reg("esp", p.reg("esp") + pop)
            p.set_reg("eax", self.answer)
            p.set_reg("eip", nxt)
            return

    def _lookup(self, p):
        sid = p.arg(0)
        self.looked_up.append(sid)
        if sid not in self.strings:
            text = (self.texts.get(sid) or "").encode("latin-1")
            self.strings[sid] = self.proc.alloc(len(text) + 1)
            self.proc.write(self.strings[sid], text + b"\0")
        return self.strings[sid], 4

    def start(self, row, who):
        """Start `row` for `who` as the adapter does; (Details text, action code).  The skipped
        helpers answer "there" (a valid pointer, nonzero in every byte tested) first; a starter that then sets no text
        (it stops early: "nothing to do") is run again with them answering "not there" (0)."""
        for self.answer in (self.dummy + 0x41, 0):
            text, code = self._start(row, who)
            if text != MARK.rstrip(b"\0").decode() or row["mode"] == "effect":
                break
        return text, code

    def _start(self, row, who):
        record = self.subjects[who]
        self.proc.write(record + TEXT[self.game], MARK)
        if self.game in CODE:
            self.proc.put32(record + CODE[self.game], NO_CODE)
        # The argument block (VV3-VV5) or the starter's argument (VV1 / VV2) as the adapter sends
        # them: the row's own, with what it needs found in the village (the body awaiting burial).
        block = list(row["args"] or [0] * 8)
        argument = row["arg"]
        supply = row["supply"]
        if supply:
            value = self.body if supply["what"] == "BODY" else self.body
            if supply["slot"] == -1:
                argument = value
            elif supply["slot"] >= 0:
                block[supply["slot"]] = value
            if supply["store"]:
                self.proc.put32(supply["store"], value)
        self.proc.write(self.zeros, struct.pack("<8i", *block))
        self.proc.write(self.dummy, bytes(0x4000))
        self.looked_up = []
        kind = row["kind"]
        if kind == "ACT_DROP" or self.game <= 2:
            starter = row["routine"]
        else:
            starter = self.handlers[row["arg"]][0]
        self.starters = {starter}
        self.active = {starter: self._body(starter)}
        self.result = None
        try:
            if kind == "ACT_DROP":
                self.result = self.proc.call(starter, [record], ecx=row["arg"], limit=200_000) & 0xFF
            elif kind == "ACT_CALL_RAW":
                self.proc.call(starter, row["args"][:row["arg"]], ecx=self.village.base, limit=200_000)
            elif self.game <= 2:
                index = self.index[who]
                args = [index] + ([argument] if kind == "ACT_CALL_ARG" else
                                  [argument, 0] if kind == "ACT_CALL_ARG2" else [])
                self.proc.call(starter, args, ecx=self.village.base, limit=200_000)
            else:
                self.proc.call(DO_ACTION[self.game], [row["arg"], self.zeros], ecx=record, limit=200_000)
        except Exception:                       # world state the emulated village lacks, later on
            pass
        text = self.proc.read(record + TEXT[self.game], 0x40).split(b"\0")[0].decode("latin-1").strip()
        code = self.proc.u32(record + CODE[self.game]) if self.game in CODE else None
        return text, code


_GAMES = {}


def _game(game):
    """One game at a time (each emulated process maps the whole executable and village)."""
    if game not in _GAMES:
        _GAMES.clear()
        _GAMES[game] = Game(game)
    return _GAMES[game]


# Starters whose first step depends on world state an emulated village does not have (other
# idle children, food in the stores, a lift puzzle part way, a fixed spot free of rocks); their
# text is proved statically (tests/test_cie_behaviour_labels.py) and their (Unsafe) reason or
# label says what they need.
NEEDS_THE_WORLD = {
    (2, "Playing tag (Unsafe)"): "other idle children to play with",
    (2, "Going to village center (then picks something to do there) (Unsafe)"): "a free spot and a roll",
    (2, "Starting to prepare a stew (Unsafe)"): "food in the stores and the cauldron",
    (4, "Curious about the hole in the ground"): "the hole, uncovered in the world",
}


def _names_alternatives(label):
    """A label that names the other texts its starter can show ("A / B", "A (or B)")."""
    return " / " in label or "(or " in label


def _rows(game):
    return [r for r in CATALOG[str(game)] if r["kind"] not in ("ACT_STOP", "ACT_RECOVER")]


@pytest.mark.parametrize("game", [1, 2, 3, 4, 5])
def test_every_action_shows_the_text_its_label_names_for_anyone(game):
    g = _game(game)
    problems = []
    for row in _rows(game):
        for who in g.subjects:
            text, code = g.start(row, who)
            label = row["label"]
            before = MARK.rstrip(b"\0").decode()
            if (game, label) in NEEDS_THE_WORLD and text == before:
                continue
            if row["kind"] == "ACT_DROP":
                # Nothing lies where they stand in the emulated village: the game's own drop finds
                # nothing and starts nothing -- the change is refused, the villager untouched.
                if g.result != 0 or text != before:
                    problems.append(f"{label} [{who}]: the drop on nothing gave {g.result}, shows {text!r}")
                continue
            if row["mode"] == "chooser":
                if text != before and text not in label and not _names_alternatives(label):
                    problems.append(f"{label} [{who}]: picked {text!r}, which the label does not name")
                continue
            if row["mode"] == "argtext":
                want = row["text"] or ""
                if text != want or (code is not None and code != row["arg"]):
                    problems.append(f"{label} [{who}]: shows {text!r} / {code}, not {want!r}")
                continue
            if "an adult just stops" in label and who != "child":
                if text != MARK.rstrip(b"\0").decode():
                    problems.append(f"{label} [{who}]: an adult was expected to just stop, shows {text!r}")
                continue
            if code is not None and code != row["arg"]:
                problems.append(f"{label} [{who}]: action code {code}, not {row['arg']}")
            if row["mode"] == "effect":
                if text != MARK.rstrip(b"\0").decode():
                    problems.append(f"{label} [{who}]: an effect set the text {text!r}")
            elif row["mode"] in ("direct", "literal") and not _names_alternatives(label):
                if text != row["text"]:
                    problems.append(f"{label} [{who}]: shows {text!r}, not {row['text']!r}")
            elif not text or text == MARK.rstrip(b"\0").decode() or text not in label:
                problems.append(f"{label} [{who}]: shows {text!r}, which the label does not name")
    assert not problems, f"VV{game}: {len(problems)} problems:\n" + "\n".join(problems)


CELEBRATING = {1: ("ACT_CALL_ARG", 0x443FA0, 9), 2: ("ACT_CALL_ARG2", 0x459B60, 1), 3: ("ACT_DO", 0, 82),
               4: ("ACT_DO", 0, 42), 5: ("ACT_DO", 0, 49)}


@pytest.mark.parametrize("game", [1, 2, 3, 4, 5])
def test_a_celebrating_starts_the_games_own_celebration(game):
    """The owner's "Especially 'Celebrating'": the Details screen then says "Celebrating"."""
    g = _game(game)
    kind, routine, arg = CELEBRATING[game]
    row = next(r for r in CATALOG[str(game)]
               if (r["kind"], r["routine"] if game <= 2 else 0, r["arg"]) == (kind, routine, arg))
    assert row["label"].startswith("Celebrating") and row["unsafe"] is None, row["label"]
    for who in g.subjects:
        text, code = g.start(row, who)
        assert text == "Celebrating", (who, text)
        if code is not None:
            assert code == arg
    every = [r for r in CATALOG[str(game)] if r["label"].startswith("Celebrating") and r["text"] == "Celebrating"]
    for r in every:
        assert g.start(r, "adult")[0] == "Celebrating", r["label"]
