"""Every villager-record layout the companions and the test fixtures declare agrees with one reference.

The reference is the Cause of Death companion's REC table (native/vvfp_cause_of_death/vvfp_cause_of_death.c): per
game the table (and whether it is a pointer to it), the first record's offset, the stride, the slot count and the
fields present / health / age / name (+ capacity) / sex / pregnant / head / body.  A DLL and a test fixture once agreed
on a wrong field (A New Home / The Lost Children's woman read as 0 instead of 2), so each layout below is compared
with the reference, not with its own test:

* the structured tables: shared/sex_change.h VV_SEX_LAYOUT, the Translations companion's GAMES, the Story / Cheat
  Upgrades adapters (C<N>_STRIDE, the record base, C<N>_PROBE, C<N>_BIRTH), the villager-table readers
  (shared/vv<N>_villager_table.h: the stock manager and 256 Villagers (Experimental)'s 0x800000);
* every game-tagged layout macro in a native source (`#define VV3_STRIDE`, `VV5_OFF_SEX`, `NB_NAME`, ...);
* the fixtures: tests/story_custom_fixtures.py LAYOUTS, tests/head_look_emulation.py GAMES, the Translations runtime
  test's RECORDS / REC345 and the 256 harnesses' strides and record bases.

Static: no game, no executable, no emulator.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
TESTS = ROOT / "tests"

FIELDS = ("table", "table_is_pointer", "record_base", "stride", "slots", "present", "health", "age", "name",
          "name_capacity", "sex", "pregnant", "litter", "heathen", "snapshot_lo", "snapshot_hi", "head", "body")
# Each game's sex values: (man, woman).  A New Home and The Lost Children: 1 and 2; the later games 0 and 1.
SEXES = {1: (1, 2), 2: (1, 2), 3: (0, 1), 4: (0, 1), 5: (0, 1)}
MANAGER_256 = 0x800000
SLOTS_256 = 256


def _int(token: str) -> int:
    return int(token.strip().rstrip("uU"), 0)


def _strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def reference() -> dict[int, dict[str, int]]:
    text = _strip_comments((NATIVE / "vvfp_cause_of_death" / "vvfp_cause_of_death.c").read_text(encoding="utf-8"))
    body = text[text.index("static struct game_records REC[6] = {"):]
    body = body[body.index("{") + 1:body.index("};")]
    rows = re.findall(r"\{([^{}]*)\}", body)
    assert len(rows) == 6, rows
    out = {}
    for game, row in enumerate(rows):
        if game == 0:
            continue
        values = [_int(v) for v in row.split(",") if v.strip()]
        assert len(values) == len(FIELDS), (game, values)
        out[game] = dict(zip(FIELDS, values))
    return out


REC = reference()


def first_record(game: int) -> int | None:
    """The first record's address in the stock build (None: behind a pointer)."""
    r = REC[game]
    return None if r["table_is_pointer"] else r["table"] + r["record_base"]


class ReferenceSanity(unittest.TestCase):
    def test_the_reference_is_the_games_own(self):
        self.assertEqual([REC[g]["stride"] for g in range(1, 6)], [0x3D8, 0xE48C, 0x1F8C, 0x2E3C, 0x2F44])
        self.assertEqual([REC[g]["slots"] for g in range(1, 6)], [256, 256, 150, 150, 150])
        self.assertEqual([REC[g]["table"] for g in (3, 4, 5)], [0x59E110, 0x50E568, 0x554148])


class StructuredTables(unittest.TestCase):
    def test_sex_change_layout(self):
        text = _strip_comments((NATIVE / "shared" / "sex_change.h").read_text(encoding="utf-8"))
        body = text[text.index("VV_SEX_LAYOUT[6] = {"):]
        body = body[:body.index("};")]
        rows = re.findall(r"\{([^{}]*)\}", body)[1:]
        self.assertEqual(len(rows), 5)
        for game, row in enumerate(rows, 1):
            stride, name, name_bytes, sex, male, female, pregnant, head, body_ = (_int(v) for v in row.split(","))
            r = REC[game]
            with self.subTest(game=game):
                self.assertEqual((stride, name, name_bytes, sex, pregnant, head, body_),
                                 (r["stride"], r["name"], r["name_capacity"], r["sex"], r["pregnant"], r["head"],
                                  r["body"]))
                self.assertEqual((male, female), SEXES[game])

    def test_translations_games(self):
        text = _strip_comments((NATIVE / "vvfp_translations" / "vvfp_translations.c").read_text(encoding="utf-8"))
        body = text[text.index("static const tr_game GAMES[6] = {"):]
        body = body[:body.index("};")]
        rows = re.findall(r"\{ (\"[^\"]*\",[^{}]*)\}", body)
        self.assertEqual(len(rows), 5)
        for game, row in enumerate(rows, 1):
            tokens = [t.strip() for t in row.split(",")]
            # title, table, rows, stride, max_id, sm, sm_count, loader, loader_site, singleton, output,
            # output_args4, pool_global, rec_stride, rec_present, rec_name, rec_name_bytes, rec_sex, male_value
            pool, stride, present, name, name_bytes, sex, male = (_int(t) for t in tokens[12:19])
            r = REC[game]
            with self.subTest(game=game):
                self.assertEqual((stride, present, name, name_bytes, sex),
                                 (r["stride"], r["present"], r["name"], r["name_capacity"], r["sex"]))
                self.assertEqual(male, SEXES[game][0])
                if game <= 2:
                    self.assertEqual(pool, REC[game]["table"])
        # How a sex value is read by name (tr_sex_of_name): A New Home / The Lost Children, then the later games.
        reads = re.findall(r"value == (\d) \? 'm' : \(value == (\d) \? 'f' : 'o'\)", text)
        self.assertEqual([tuple(map(int, r)) for r in reads], [SEXES[1], SEXES[3]])

    def test_story_adapters(self):
        for game in (3, 4, 5):
            text = _strip_comments((NATIVE / "vvfp_story_upgrades" / f"story_c{game}.inc").read_text(encoding="utf-8"))
            r = REC[game]
            with self.subTest(game=game):
                self.assertEqual(_int(re.search(rf"#define C{game}_STRIDE (0x[0-9A-F]+u)", text).group(1)),
                                 r["stride"])
                base = re.search(rf"#define C{game}_RECORDS \(c{game}_\w+\(\) \+ (0x[0-9A-F]+u)\)", text).group(1)
                self.assertEqual(_int(base), r["record_base"])
                probe = re.search(rf"C{game}_PROBE\[\] = \{{(.*?)\}};", text, re.S).group(1)
                fields = [tuple(_int(v) for v in f.split(",")) for f in re.findall(r"\{([^{}]*)\}", probe)]
                self.assertEqual([f[0] for f in fields[:4]], [r["present"], r["health"], fields[2][0], r["pregnant"]])
                birth = re.search(rf"C{game}_BIRTH = \{{ (0x[0-9A-F]+u), (0x[0-9A-F]+u), (0x[0-9A-F]+u), "
                                  rf"(0x[0-9A-F]+u), c{game}_catch_up \}};", text)
                age, _processed, pregnant, health = (_int(birth.group(i)) for i in range(1, 5))
                self.assertEqual((age, pregnant, health), (r["age"], r["pregnant"], r["health"]))
        for game in (1, 2):
            text = _strip_comments((NATIVE / "vvfp_story_upgrades" / f"story_c{game}.inc").read_text(encoding="utf-8"))
            birth = re.search(rf"C{game}_BIRTH = \{{ (0x[0-9A-F]+u), (0x[0-9A-F]+u), (0x[0-9A-F]+u), "
                              rf"(0x[0-9A-F]+u), c{game}_catch_up \}};", text)
            age, _processed, pregnant, health = (_int(birth.group(i)) for i in range(1, 5))
            with self.subTest(game=game):
                self.assertEqual((age, pregnant, health), (REC[game]["age"], REC[game]["pregnant"],
                                                           REC[game]["health"]))

    def test_villager_table_readers_128_and_256(self):
        for game in (3, 4, 5):
            text = (NATIVE / "shared" / f"vv{game}_villager_table.h").read_text(encoding="utf-8")
            stock = _int(re.search(rf"#define VV{game}_STOCK_MANAGER_RVA (0x[0-9A-F]+u)", text).group(1))
            moved = _int(re.search(rf"#define VV{game}_256_MANAGER\s+(0x[0-9A-F]+u)", text).group(1))
            with self.subTest(game=game):
                self.assertEqual(0x400000 + stock, REC[game]["table"])
                self.assertEqual(moved, MANAGER_256)
                self.assertIn(f"*slots = {REC[game]['slots']}u;", text)
                self.assertIn(f"*slots = {SLOTS_256}u;", text)
            builder = (ROOT / "scripts" / f"build_vv{game}_population_256_feature.py").read_text(encoding="utf-8")
            low = builder.lower()
            with self.subTest(game=game, what="the 256 builder"):
                self.assertIn(f"0x{REC[game]['table']:x}", low)          # the manager it moves...
                self.assertIn(f"0x{MANAGER_256:x}", low)                  # ...to 0x800000
                self.assertIn(f"0x{REC[game]['stride']:x}", low)


# `#define <game tag>_<field>` and the reference field it names.
MACRO = re.compile(r"^#define\s+(?:VV([1-5])|C([1-5])|(NB))_(?:OFF_|REC_|RECORD_)?"
                   r"(STRIDE|SEX|AGE|HEALTH|NAME|ACTIVE|PRESENT|OCCUPIED|PREGNANT)(?:_OFFSET)?"
                   r"\s+\(?(0x[0-9A-Fa-f]+|\d+)u?\)?\s*(?:/\*.*|//.*)?$", re.M)
MACRO_FIELD = {"STRIDE": "stride", "SEX": "sex", "AGE": "age", "HEALTH": "health", "NAME": "name",
               "ACTIVE": "present", "PRESENT": "present", "OCCUPIED": "present", "PREGNANT": "pregnant"}


class LayoutMacros(unittest.TestCase):
    def test_every_game_tagged_layout_macro_matches(self):
        seen = 0
        for path in sorted(NATIVE.rglob("*")):
            if path.suffix not in (".c", ".h", ".inc"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in MACRO.finditer(text):
                game = int(m.group(1) or m.group(2) or 5)          # NB_: New Believers
                field = MACRO_FIELD[m.group(4)]
                seen += 1
                with self.subTest(file=str(path.relative_to(ROOT)), macro=m.group(0).split()[1]):
                    self.assertEqual(int(m.group(5), 0), REC[game][field])
        self.assertGreater(seen, 40)


def _literal_dict(path: Path, name: str):
    """The dict literal assigned to `name` at module level in `path` (read, never imported)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(_fold(node.value))
    raise AssertionError(f"{name} not in {path.name}")


def _fold(node):
    """`0x59E110 + 0x14` -> the number; dict(...) calls -> dict literals; everything else as written."""
    class Fold(ast.NodeTransformer):
        def visit_BinOp(self, n):
            self.generic_visit(n)
            if isinstance(n.left, ast.Constant) and isinstance(n.right, ast.Constant) and isinstance(n.op, ast.Add):
                return ast.copy_location(ast.Constant(n.left.value + n.right.value), n)
            return n

        def visit_Call(self, n):
            self.generic_visit(n)
            if isinstance(n.func, ast.Name) and n.func.id == "dict" and not n.args:
                return ast.copy_location(ast.Dict(keys=[ast.Constant(k.arg) for k in n.keywords],
                                                  values=[k.value for k in n.keywords]), n)
            return n
    return Fold().visit(node)


class Fixtures(unittest.TestCase):
    def test_story_custom_fixtures(self):
        layouts = _literal_dict(TESTS / "story_custom_fixtures.py", "LAYOUTS")
        for key, L in layouts.items():
            game = int(key[2])
            r = REC[game]
            with self.subTest(game=game):
                self.assertEqual((L["stride"], L["active"], L["health"], L["age"], L["name"], L["name_cap"],
                                  L["sex"][0], L["pregnant"], L["head"], L["body"], L["count"]),
                                 (r["stride"], r["present"], r["health"], r["age"], r["name"], r["name_capacity"],
                                  r["sex"], r["pregnant"], r["head"], r["body"], r["slots"]))
                self.assertEqual(tuple(L["sex"][1:]), SEXES[game])
                if "base" in L:
                    self.assertEqual(L["base"], first_record(game))

    def test_head_look_emulation_games(self):
        games = _literal_dict(TESTS / "head_look_emulation.py", "GAMES")
        for game, G in games.items():
            r = REC[game]
            with self.subTest(game=game):
                self.assertEqual((G["stride"], G["count"], G["present"], G["name"], G["sex"], G["age"], G["head"]),
                                 (r["stride"], r["slots"], r["present"], r["name"], r["sex"], r["age"], r["head"]))
                if "records" in G:
                    self.assertEqual(G["records"], first_record(game))
                    self.assertEqual(G["table"][2], r["record_base"])
                else:
                    self.assertEqual(G["pool_global"], r["table"])

    def test_translations_runtime_fixtures(self):
        path = TESTS / "test_translations_runtime.py"
        for game, R in _literal_dict(path, "RECORDS").items():
            r = REC[game]
            with self.subTest(game=game, table="RECORDS"):
                self.assertEqual((R["pool"], R["stride"], R["present"], R["name"], R["sex"], R["male"]),
                                 (r["table"], r["stride"], r["present"], r["name"], r["sex"], SEXES[game][0]))
        for game, R in _literal_dict(path, "REC345").items():
            r = REC[game]
            with self.subTest(game=game, table="REC345"):
                self.assertEqual((R["records"], R["stride"], R["present"], R["name"], R["sex"]),
                                 (first_record(game), r["stride"], r["present"], r["name"], r["sex"]))

    def test_population_256_harnesses(self):
        for game in (3, 4, 5):
            text = (TESTS / f"vv{game}_population_256_harness.py").read_text(encoding="utf-8")
            with self.subTest(game=game):
                self.assertEqual(_int(re.search(r"^STRIDE = (0x[0-9A-F]+)$", text, re.M).group(1)),
                                 REC[game]["stride"])
                base = re.search(r"^RECORD_BASE = (0x[0-9A-F]+)$", text, re.M)
                if base:
                    self.assertEqual(_int(base.group(1)), REC[game]["record_base"])
                else:
                    self.assertIn(f"self.manager + 0x{REC[game]['record_base']:X} + index * STRIDE", text)


if __name__ == "__main__":
    unittest.main()
