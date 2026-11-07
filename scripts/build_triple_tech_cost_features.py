"""Generate data/vv<N>_triple_tech_cost_feature.json (all five games): Triple Tech Cost, off by default.

The owner (2026-11-06): "Default OFF: "Triple Tech Cost" = triples all technologies so they have 3x the normal cost.
makes the game super hard."  And: "7 should be default off for everything. players who want it must explicitly
choose it": Default Patches, Owner's Defaults and Select All all leave it unticked (src/vv_fun_patcher_gui.py).

WHERE EACH GAME KEEPS ITS PRICES (research/stock-executables, read with capstone, 2026-11-06).

A New Home and The Lost Children write every price as an immediate, in three routines of the Tech screen, each of
which picks the price of the technology's next level by its current level (1 -> level 2's price, 2 -> level 3's):

  * the hover label (VV1 0x434070, VV2 0x441D80): "<cost word> <price> <tech points word>" (format "%s %i %s",
    VV1 0x481A14, VV2 0x48FA00) under the button the mouse is on;
  * the information box (VV1 0x4345E0, VV2 0x4422F0, the "?" click): the level and the price in a message box;
  * the buy handler (VV1 0x435AEF..0x435D6E, VV2 0x4437FF..0x443A2C): `mov edx, price / cmp [points], edx / jb
    refuse / sub [points], edx`, so the same immediate is the refusal threshold ("not enough tech points": message
    0x25 in VV1, 0x3F in VV2, nothing spent) and the amount taken.

Every one of these is a `mov r32, imm32` or `push imm32`, and every immediate equal to a price that is not in these
routines belongs to something else (tests/test_triple_tech_cost.py checks each one).  In the information box two
technologies share one site, each with the same stock price: VV1 Construction and Spirituality level 3 (80,000,
0x434693), VV2 Medicine and Culture level 2 (20,000, 0x4423B1); tripling it is right for both.

The Secret City, The Tree of Life and New Believers read every price from one table through one getter:
price(id) = dword [table + 4 * (3 * id + level + 1)], 0 at the top level (VV3 0x427020 / table 0x4A818C, VV4
0x41E220 / 0x4BC18C, VV5 0x4236D0 / 0x4CA3B4).  The table is initialized data and the getter is its only reader;
the getter has three callers in each game, the same three as above: the hover label, the information box and the
purchase (VV3 0x464C84, 0x464E47, 0x465706; VV4 0x43E57D, 0x43E900, 0x43EA76; VV5 0x440DCA, 0x4412A0, 0x441676),
whose `cmp [points], price / jge` refuses with too few points (VV3 string 0x34, VV4 0x97, VV5 0x88) and whose
`neg / call add-points` (VV3 0x4657C8/0x427130, VV4, VV5 0x44169F/0x4237B0) takes the price.  The Secret City's
two factions (Nature, Magic) are technologies 5 and 6 of the same table, so the faction choice costs 3 times too.

THE CHANGE: each price in place, x 3 -- no code is added, no routine is changed, nothing claims executable space.
The table's zero entries (a level a new village already has) stay 0.  The biggest tripled price is 750,000 (VV1
Medicine level 3): far inside the signed 32-bit range every comparison uses, and at most six digits, as the stock
games' own longest prices (VV1 250,000, VV2 160,000, VV3 150,000).

NOT CHANGED: nothing else reads these prices.  Every other tech-point cost keeps its number, each its own
immediate or table: the clothes (5,000: VV1's F6 change with the patcher, VV3 0x4228A2, and VV4's and VV5's), The
Lost Children's other two 5,000-point checks (0x430357, 0x461C27, not a technology), and the patcher's Origins and
Story / Cheat upgrades (their own price tables); so do island events that grant a level or tech points, and
research.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE_BASE = 0x400000
FACTOR = 3
NAME = "Triple Tech Cost"

# A New Home and The Lost Children: the three routines' (start, end) VAs, each starting on an instruction.
ROUTINES = {
    1: {"hover label": (0x434070, 0x43456E), "information box": (0x4345E0, 0x4347C0), "buy": (0x435AEF, 0x435D6E)},
    2: {"hover label": (0x441D80, 0x4422E8), "information box": (0x4422F0, 0x4424D8), "buy": (0x4437FF, 0x443A2C)},
}
# (level 2, level 3) stock prices, by the technology as each game names it (src/vv_game_mechanics_items_vv<N>.py).
IMMEDIATE_PRICES = {
    1: {"Farming": (6_000, 50_000), "Fertility": (11_000, 240_000), "Science": (12_000, 150_000),
        "Medicine": (15_000, 250_000), "Construction": (2_500, 80_000), "Spirituality": (5_000, 80_000)},
    2: {"Farming": (1_500, 90_000), "Exploration": (10_000, 160_000), "Science": (16_000, 150_000),
        "Medicine": (20_000, 65_000), "Engineering": (5_000, 75_000), "Culture": (20_000, 85_000)},
}
# Each immediate routine's site count: 12 (6 technologies x 2 levels), the information box 11 (one shared site).
SITE_COUNTS = {"hover label": 12, "information box": 11, "buy": 12}

# The Secret City, The Tree of Life and New Believers: (getter, table, technologies in id order).
TABLES = {
    3: (0x427020, 0x4A818C, ("Science", "Medicine", "Alchemy", "Restoration", "Leadership", "Nature", "Magic")),
    4: (0x41E220, 0x4BC18C, ("Science", "Medicine", "Learning", "Construction", "Food Mastery", "Dendrology")),
    5: (0x4236D0, 0x4CA3B4, ("Science", "Medicine", "Learning", "Construction", "Food Mastery", "Spirituality")),
}
GETTER_CALLERS = {3: (0x464C84, 0x464E47, 0x465706), 4: (0x43E57D, 0x43E900, 0x43EA76),
                  5: (0x440DCA, 0x4412A0, 0x441676)}
GAME_NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life",
              5: "New Believers"}


def out_path(game: int) -> Path:
    return ROOT / "data" / f"vv{game}_triple_tech_cost_feature.json"


def stock_path(game: int) -> Path:
    sys.path.insert(0, str(ROOT / "src"))
    import vv_fun_patcher as patcher  # noqa: PLC0415
    build = next(b for b in patcher.load_builds() if b.id == f"vv{game}")
    return ROOT / "research" / "stock-executables" / build.input_name


def _pe(stock: bytes):
    import pefile  # noqa: PLC0415
    return pefile.PE(data=stock, fast_load=True)


def immediate_sites(game: int, stock: bytes) -> list[tuple[str, int, int]]:
    """(routine, file offset of the imm32, stock price) for every price immediate of the three routines."""
    import capstone  # noqa: PLC0415
    pe = _pe(stock)
    prices = {p for pair in IMMEDIATE_PRICES[game].values() for p in pair}
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    out = []
    for routine, (lo, hi) in ROUTINES[game].items():
        start = pe.get_offset_from_rva(lo - IMAGE_BASE)
        found = 0
        for ins in md.disasm(stock[start:start + hi - lo], lo):
            if ins.size != 5 or not (0xB8 <= ins.bytes[0] <= 0xBF or ins.bytes[0] == 0x68):
                continue
            value = struct.unpack_from("<I", ins.bytes, 1)[0]
            if value in prices:
                out.append((routine, pe.get_offset_from_rva(ins.address + 1 - IMAGE_BASE), value))
                found += 1
        if found != SITE_COUNTS[routine]:
            raise SystemExit(f"vv{game} {routine}: {found} price immediates, expected {SITE_COUNTS[routine]}")
    return out


def table_sites(game: int, stock: bytes) -> list[tuple[str, int, int, int]]:
    """(technology, level bought, file offset, stock price) for every non-zero entry of the price table."""
    _, table, techs = TABLES[game]
    pe = _pe(stock)
    out = []
    for tech_id, name in enumerate(techs):
        for level in range(3):                 # the entry read at this level: the price of level + 1
            va = table + 4 * (3 * tech_id + level + 1)
            offset = pe.get_offset_from_rva(va - IMAGE_BASE)
            value = struct.unpack_from("<i", stock, offset)[0]
            if value:
                out.append((name, level + 1, offset, value))
    return out


def description(game: int) -> str:
    if game in IMMEDIATE_PRICES:
        table = IMMEDIATE_PRICES[game]
        listed = "; ".join(f"{name} level 2 {a:,} -> {FACTOR * a:,}, level 3 {b:,} -> {FACTOR * b:,}"
                           for name, (a, b) in table.items())
    else:
        sys.path.insert(0, str(ROOT / "src"))
        stock = stock_path(game).read_bytes()
        rows: dict[str, list[str]] = {}
        for name, level, _, value in table_sites(game, stock):
            rows.setdefault(name, []).append(f"level {level} {value:,} -> {FACTOR * value:,}")
        listed = "; ".join(f"{name} " + ", ".join(levels) for name, levels in rows.items())
    faction = (" The two factions, Nature and Magic, are technologies too: choosing one costs 3 times as much."
               if game == 3 else "")
    return (f"Every technology level on the Tech screen costs 3 times its normal price, in tech points: {listed}. "
            "The Tech screen shows the tripled price, a purchase is refused (and nothing is spent) with fewer tech "
            "points than that, and buying takes exactly that many." + faction + " Research, tech points from "
            "anywhere else, every other tech-point cost (such as clothes) and the patcher's own upgrades are "
            "unchanged. "
            "**Needs no other patch.** Makes the game super hard.")


def feature(game: int, stock: bytes) -> dict:
    patches = []
    if game in IMMEDIATE_PRICES:
        by_price: dict[int, list[str]] = {}
        for name, pair in IMMEDIATE_PRICES[game].items():
            for level, price in zip((2, 3), pair):
                by_price.setdefault(price, []).append(f"{name} {level}")
        for routine, offset, value in immediate_sites(game, stock):
            patches.append({
                "offset": "0x%X" % offset,
                "before": struct.pack("<I", value).hex().upper(),
                "after": struct.pack("<I", FACTOR * value).hex().upper(),
                "purpose": f"the {routine}'s price {value:,} -> {FACTOR * value:,} (a {' or '.join(by_price[value])} "
                           "price immediate; the site is picked by the technology and its level)",
            })
        where = ("the Tech screen's hover label (0x%X), information box (0x%X) and buy handler (0x%X), each a "
                 "price immediate" % tuple(r[0] for r in ROUTINES[game].values()))
        behaviour = [
            f"Every technology price immediate in {where}, x 3: the shown price, the buy handler's refusal threshold "
            "(cmp / jb: too few tech points shows the game's message and spends nothing) and the amount it takes "
            "(sub) are the same tripled number.",
        ]
    else:
        getter, table, _ = TABLES[game]
        for name, level, offset, value in table_sites(game, stock):
            patches.append({
                "offset": "0x%X" % offset,
                "before": struct.pack("<i", value).hex().upper(),
                "after": struct.pack("<i", FACTOR * value).hex().upper(),
                "purpose": f"price table 0x{table:X}: {name} level {level} {value:,} -> {FACTOR * value:,}",
            })
        callers = ", ".join("0x%X" % c for c in GETTER_CALLERS[game])
        behaviour = [
            f"Every non-zero entry of the technology price table 0x{table:X}, x 3. Its only reader is the getter "
            f"0x{getter:X}, called by the Tech screen's hover label, information box and purchase ({callers}): the "
            "shown price, the purchase's refusal threshold and the amount it takes are the same tripled number.",
        ]
    return {
        "id": f"vv{game}_triple_tech_cost",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": description(game),
        "output_tag": NAME,
        "behavior_changes": behaviour,
        "explicit_non_changes": [
            "Each price is changed in place, same length; no code is added and no executable space is claimed.",
            "Research, tech points from island events and duplicate collectibles, every other tech-point cost (such "
            "as 5,000 for clothes) and the patcher's Origins and Story / Cheat upgrades keep their stock numbers.",
        ],
        "companion_files": [],
        "patches": patches,
    }


def main() -> None:
    for game in range(1, 6):
        record = feature(game, stock_path(game).read_bytes())
        out_path(game).write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                                  newline="\n")
        print("wrote", out_path(game), len(record["patches"]), "sites")


if __name__ == "__main__":
    main()
