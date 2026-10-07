"""Generate the "Story / Cheat Upgrades" rows (all five games) and their tables.

Writes:

* data/vv<N>_story_cheat_upgrades_feature.json -- the five rows;
* native/vvfp_story_upgrades/story_tables.h -- the sites, bytes and island
  events "VVFP Story Upgrades.dll" uses.

Every site is checked against the executable the patcher renders, in all
three population modes, both with only this row (and the Origins upgrades it
requires) and with the whole public catalog: the bytes must be exactly the
ones listed, identical in every render.  A price the Origins payload holds
that is not listed here fails the build (see _price_sites), so a new Origins
row cannot ship with a price this row does not zero.

The row patches no executable byte: "VVFP Story Upgrades.dll" writes the
listed sites at run time, after verifying all of them (see its source).

Run from the repository root:

    python scripts/build_story_cheat_upgrades_features.py
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import story_island_events  # noqa: E402
import story_outcome_tables  # noqa: E402

GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
MODES = ("stock", "collection_progression", "immediate_fixed")
DLL_SOURCE = "assets/story_upgrades/VVFP Story Upgrades.dll"
DLL_NAME = "VVFP Story Upgrades.dll"
HEADER = ROOT / "native" / "vvfp_story_upgrades" / "story_tables.h"

NAME = "Story / Cheat Upgrades"
DESCRIPTION = (
    "Adds optional tools intended for custom stories, experiments, sandbox play, "
    "and cheats. These features deliberately allow the player to bypass normal game "
    "progression and random-event behavior. When enabled, all Origins Upgrades cost "
    "0 Tech Points. Also adds the following Origins Upgrades: Pick Island Event -- "
    "Allows the player to directly choose which stock Island Event occurs instead of "
    "relying on random selection. Opening this upgrade displays a list of the game's "
    "official Island Event titles, each with a brief description. Selecting an event "
    "causes that specific event to occur through the game's Island Event system. "
    "Custom Island Event -- Allows the player to create and trigger a custom Island "
    "Event for storytelling, testing, sandbox play, or cheats. The player may customize "
    "supported event properties, including: Title and description; Food gained or lost; "
    "Tech Points gained or lost; Villagers spawned; Spawned-villager details, including "
    "supported appearance, age, sex, name, likes/dislikes, skills, and other valid "
    "villager attributes; Villager behavior or state changes; Village-state changes; "
    "Puzzle-state changes; Other game-specific values that can be safely and reliably "
    "manipulated. Custom events should appear and behave as closely as practical to "
    "ordinary Island Events, while clearly allowing player-defined outcomes. Only what "
    "this game's own code supports is offered; the rest is shown as not available in "
    "this game. A custom title is kept per save slot in a file beside the saves and is "
    "removed by Start Over. "
    "A custom event can also ask a question with two choices: the player writes the question, "
    "the two button labels and, for each button, one to four outcomes, each with its own chance, "
    "result text and changes (everything the event itself can change); clicking a button rolls "
    "one of its outcomes by those chances and makes only that outcome's changes. **A question "
    "with two choices can be queued only in a game whose own two-button island-event popup the "
    "companion hooks; in any other game the option is shown as not available yet.** "
    "Pick Island Event also lets the player set how the picked event turns out. Each setting "
    "starts at \"Random (original game)\" and offers only what that event's own code can "
    "produce in this game: its result (for a two-choice event, the result of each choice -- the "
    "popup still appears and the player still clicks), every amount it can roll, who a roll it "
    "makes for each villager hits (nobody, everyone, or the villagers chosen), which villager it is "
    "about, and each baby's details; in A New Home and The Lost Children also its strength "
    "(normally a third of the population, 1 to 10). A setting whose condition does not hold right "
    "now can not be bought. An event whose own condition is only a matter of timing or story can "
    "be picked anyway, and developer-dead events proven to work are offered as never happening in "
    "the original game; events that need something the village lacks, or room for new villagers, "
    "stay locked with the reason. "
    "Off by default. **Requires Enable Origins Tech, Details, and Village-Wide "
    "Upgrades: ticking this ticks it, and without it there are no Origins Upgrades "
    "to make free and no Pick Island Event or Custom Island Event.** **A pregnancy a "
    "custom event starts is written to the Births and Conceptions log only with Write "
    "Births and Conceptions Log to Text File ticked.**"
)
# The Lost Children's separate Gong of Wonder upgrade.
VV2_GONG_NOTE = (
    " Also adds Pick Gong of Wonder Outcome (0 Tech Points): the player picks what the next ring "
    "of the Gong of Wonder does -- any result the Gong can give, with its amounts and who falls "
    "sick -- defaulting to \"Random (original game)\"; the choice is used for one ring, in "
    "this save slot, within ten minutes."
)
# A New Home keeps parents only in the Show Parents companion's file.
VV1_PARENTS_NOTE = (
    " **In A New Home a custom event can change a villager's parents only with Show "
    "Parents in Details Screen ticked (its file is where A New Home's parents are kept).**"
)

# What each game's Custom Island Event offers and leaves out, with the reason
# (docs/story-cheat-upgrades.md has the evidence).
CUSTOM_OFFERED = {
    "vv1": ["title and description", "food and tech points (add, subtract, set to 0)",
            "refill: berry bushes, and the crops once the farm produces", "new villagers",
            "dies (leaves a skeleton)", "disappears (no skeleton)", "falls sick",
            "pregnant with a baby, twins or triplets (adults 18+, either sex)",
            "likes and dislikes", "appearance (heads and bodies 0-19)", "skills",
            "parents (with Show Parents in Details Screen)", "custom title", "mask",
            "behaviours: stops what they are doing, dances, goes swimming, relaxes, recovers fully",
            "village: Isola Day celebration, Blessings Day celebration, the beach dirty again "
            "(as The Big Wave leaves it)"],
    "vv2": ["title and description", "food and tech points (add, subtract, set to 0)",
            "refill: coconut trees, and the crops while planted", "new villagers",
            "dies (leaves a skeleton)", "disappears (no skeleton)", "falls sick",
            "pregnant with a baby, twins or triplets (adults 18+, either sex)",
            "likes and dislikes", "appearance (heads and bodies 0-29)", "skills", "parents",
            "custom title", "mask", "becomes an Esteemed Elder (with a totem)",
            "Esteemed Elder's totem type (eight carvings)",
            "behaviours: stops what they are doing, cools off with a swim, celebrates, visits "
            "the graves, sneezes, recovers fully"],
    "vv3": ["title and description", "food and tech points (add, subtract, set to 0)",
            "refill: fruit trees", "new villagers", "dies (leaves a skeleton)",
            "disappears (no skeleton)", "falls sick",
            "pregnant with a baby, twins or triplets (adults 18+, either sex)",
            "likes and dislikes", "appearance (heads and bodies 0-29)", "skills", "parents",
            "custom title", "mask", "behaviours: stops what they are doing, recovers fully"],
    "vv4": ["title and description", "food and tech points (add, subtract, set to 0)",
            "refill: berry bushes", "new villagers", "dies (leaves a skeleton)",
            "disappears (no skeleton)", "falls sick",
            "pregnant with a baby, twins or triplets (adults 18+, either sex)",
            "likes and dislikes", "appearance (heads and bodies 0-29)", "skills", "parents",
            "custom title", "mask", "behaviours: stops what they are doing, recovers fully",
            "village: rain begins, the weather clears"],
    "vv5": ["title and description", "food and tech points (add, subtract, set to 0)",
            "refill: noni bushes, and the crops once the farm is built", "new villagers (believers)",
            "dies (leaves a remains)", "disappears (no skeleton)", "falls sick (believers)",
            "pregnant with a baby, twins or triplets (adult believers, either sex)",
            "likes and dislikes", "appearance (heads and bodies 0-29)", "skills (six)", "parents",
            "custom title", "mask", "becomes a believer / becomes a Heathen",
            "behaviours: stops what they are doing, recovers fully"],
}
CUSTOM_OMITTED = {
    "vv1": [{"option": "Golden Child", "reason": "only the game's own puzzle makes one; the creator's "
             "family 0xC7 forces sex, age and looks, and the puzzle's own state would no longer agree"},
            {"option": "puzzle solved", "reason": "no completion routine that can be called on its own"},
            {"option": "the 47th like word (sleeping)", "reason": "the game never uses it and its "
             "list reader can overrun on it"},
            {"option": "faction, chief, elders, totems", "reason": "A New Home has none"}],
    "vv2": [{"option": "puzzle solved", "reason": "each puzzle is tied to its objects and goal messages; "
             "no completion routine that can be called on its own"},
            {"option": "refill fish and farm soil", "reason": "depleted by design and restored only "
             "by their puzzles"},
            {"option": "Golden Child, chief, faction", "reason": "The Lost Children has none"}],
    "vv3": [{"option": "Tribal Chief", "reason": "only the robe puzzle makes one; a second chief is a "
             "known defect"},
            {"option": "Esteemed Elder", "reason": "worked out from three mastered skills, not stored"},
            {"option": "puzzle solved", "reason": "the puzzles create the objects they need"},
            {"option": "refill the beehive", "reason": "its refill is tied to its puzzle"}],
    "vv4": [{"option": "refill fruit trees and fishing", "reason": "the game has no refill for them"},
            {"option": "special statuses", "reason": "Scholar and Elderly are worked out; Tribal "
             "Chief is never shown"},
            {"option": "other weather", "reason": "the other weather types are not identified"},
            {"option": "puzzle solved", "reason": "only the collections have a completion route"}],
    "vv5": [{"option": "new Heathens", "reason": "the Heathen creator's arguments are not all understood"},
            {"option": "the puzzles' own Heathens' faction", "reason": "their puzzles depend on them"},
            {"option": "sickness or pregnancy for Heathens", "reason": "the game cures Heathens every "
             "moment and Heathens never give birth"},
            {"option": "puzzle solved", "reason": "the completion routine needs world state that is "
             "not proven"}],
}

# Every price the Origins rows charge, in any game.
PRICES = (5000, 30000, 40000, 50000, 75000, 100000, 450000, 500000, 1000000)

# Where each game's Origins payload holds a price: the price tables (VA,
# dword count), the instructions whose 32-bit immediate is a price (VA of the
# IMMEDIATE), and the strings that print a price.  _price_sites proves the
# list complete against every byte the Origins rows write.
PRICE_TABLES = {
    "vv1": [(0x485FC0, 11)],              # tech rows 0-5, Details rows 0-4
    "vv2": [(0x494F90, 10)],              # tech rows 0-5, Details rows 0-3
    "vv3": [(0x4A3F60, 11)],
    "vv4": [(0x489EE7, 11)],
    # New Believers keeps every price in its Task9 page. The base payload's
    # legacy menus and their price tables never ran (0x7B22C0 / 0x7B2600 jump
    # straight into the Task9 page) and are no longer emitted.
    "vv5": [],
}
PRICE_IMMEDIATES = {
    "vv1": [0x456AD9, 0x48D5A3, 0x48D5DB, 0x48D624, 0x48D6F1, 0x48DA86, 0x48DABB,
            0x48DB11, 0x48DB1D, 0x48DD44, 0x48DD96],
    "vv2": [0x494722, 0x494742, 0x49C5F5, 0x49C65B],
    "vv3": [0x47B6AA, 0x47B76F, 0x47BD9E, 0x49EEA6, 0x49EEB2, 0x49EF36, 0x49EF42,
            0x4A35C9, 0x4A35D9],
    "vv4": [0x4896A4, 0x4896AF, 0x4896C9, 0x4896D4, 0x4896F9, 0x489A41, 0x728110,
            0x728789],
    "vv5": [0x7C9989, 0x7C99C1, 0x7C99EA, 0x7C99FB, 0x7C9DD2, 0x7C9E56, 0x7C9F28,
            0x7C9F3A, 0x7CA0E2, 0x7CA102, 0x7CA110,
            0x7CA5D1, 0x7CA638, 0x7CA733, 0x7CA745, 0x7CB2DF, 0x7CB3BB, 0x7CB3CD,
            0x7CC488, 0x7CC4B7, 0x7CC4C2, 0x7CC4D4, 0x7CCC96, 0x7CCCD7, 0x7CCCDE,
            0x7CCCF0, 0x7CCFA3, 0x7CCFE9, 0x7CCFF0, 0x7CD002, 0x7CD38E, 0x7CD41C,
            0x7CD488, 0x7CD49A, 0x7CD612, 0x7CD63F, 0x7CD749, 0x7CD75B, 0x7CD912,
            0x7CD93F, 0x7CDA28, 0x7CDA3A, 0x7CDC2E, 0x7CDC5B, 0x7CDD32, 0x7CDD44,
            0x7CE220, 0x7CE24D, 0x7CE2F7, 0x7CE309, 0x7CE820, 0x7CE84D, 0x7CE8C0,
            0x7CE8D2, 0x7CF012, 0x7CF033, 0x7CF055, 0x7CF212, 0x7CF233, 0x7CF255,
            0x7CF533],
}
# New Believers draws its Time Warp, Island Event and Barrel prompts (and the
# messages for a charge that cannot be verified) from strings in its own page.
PRICE_STRINGS = {
    "vv1": [], "vv2": [], "vv3": [], "vv4": [],
    # The Time Warp prompts the page used to show itself are gone (the
    # companion owns that dialog); their bytes are zero, so nothing to zero.
    "vv5": [0x7D04C1, 0x7D0660, 0x7D06E1, 0x7D072D,
            0x7D09C1, 0x7D0A43],
}

# The Pick Island Event sites: the game's own code at the point where it has
# chosen which event to run (VV3-VV5), or the rand() calls that choose
# (VV1, VV2).  name -> (VA, length).
PICK_SITES = {
    "vv1": {
        "VV1_ROLL_FAMILY_BYTES": (0x423818, 5),
        "VV1_ROLL_ISLAND_OR_CRATE_BYTES": (0x42383A, 5),
        "VV1_ROLL_ISLAND_CASE_BYTES": (0x4284DB, 5),
        "VV1_ROLL_ENCOUNTER_BYTES": (0x418932, 5),
        "VV1_ROLL_CRATE_BYTES": (0x42B03E, 5),
    },
    "vv2": {
        "VV2_ROLL_FAMILY_BYTES": (0x42EF28, 5),
        "VV2_ROLL_C_OR_B_BYTES": (0x42EF4A, 5),
        "VV2_ROLL_CASE_C_BYTES": (0x434607, 5),
        "VV2_ROLL_EVENT_A_BYTES": (0x41F59D, 5),
        "VV2_ROLL_EVENT_B_BYTES": (0x437B0E, 5),
    },
    "vv3": {"VV3_PICK_SITE_BYTES": (0x419BDB, 7)},
    "vv4": {"VV4_PICK_SITE_BYTES": (0x4180F7, 7)},
    "vv5": {"VV5_PICK_SITE_BYTES": (0x41895B, 7)},
}
# Unlocked picks (A New Home / The Lost Children): the check right after
# each family's event roll, passed once for a pick the player unlocked.
UNLOCK_SITES = {
    "vv1": {"VV1_UNLOCK_ISLAND_BYTES": (0x4284EC, 7), "VV1_UNLOCK_ENCOUNTER_BYTES": (0x418941, 7)},
    "vv2": {"VV2_UNLOCK_C_BYTES": (0x434617, 6), "VV2_UNLOCK_A_BYTES": (0x41F5A5, 7)},
}
UNLOCK_SITE_ROUTINES = {
    "VV1_UNLOCK_ISLAND_BYTES": "the island event's condition check after its roll (unlocked picks)",
    "VV1_UNLOCK_ENCOUNTER_BYTES": "the villager encounter's condition check after its roll (unlocked picks)",
    "VV2_UNLOCK_C_BYTES": "the single-result event's condition check after its roll (unlocked picks)",
    "VV2_UNLOCK_A_BYTES": "the two-choice event's condition check after its roll (unlocked picks)",
}

PICK_SITE_ROUTINES = {
    "VV1_ROLL_FAMILY_BYTES": "rand(100) choosing the encounter family",
    "VV1_ROLL_ISLAND_OR_CRATE_BYTES": "rand(100) choosing island event or crate",
    "VV1_ROLL_ISLAND_CASE_BYTES": "rand(15) choosing the island event",
    "VV1_ROLL_ENCOUNTER_BYTES": "rand(16) choosing the villager encounter",
    "VV1_ROLL_CRATE_BYTES": "rand(9) choosing the crate or vial",
    "VV2_ROLL_FAMILY_BYTES": "rand(100) choosing the two-choice family",
    "VV2_ROLL_C_OR_B_BYTES": "rand(100) choosing single-result event or sack",
    "VV2_ROLL_CASE_C_BYTES": "rand(28) choosing the single-result event",
    "VV2_ROLL_EVENT_A_BYTES": "rand(22) choosing the two-choice event",
    "VV2_ROLL_EVENT_B_BYTES": "rand(8) choosing the sack or vial",
    "VV3_PICK_SITE_BYTES": "the island-event selector, after it has chosen",
    "VV4_PICK_SITE_BYTES": "the island-event selector, after it has chosen",
    "VV5_PICK_SITE_BYTES": "the island-event selector, after it has chosen",
}

# The Custom Island Event's own sites (VV3-VV5 deliver at their pick site):
# the island event's chooser call it replaces (VV1, VV2) and the villager
# panel's title (all five).  name -> (VA, length).
CUSTOM_SITES = {
    "vv1": {
        "VV1_CUSTOM_CHOOSE_BYTES": (0x428777, 5),
        "VV1_TITLE_SITE_BYTES": (0x41FD75, 5),
        "VV1_CHOICE_SETUP_BYTES": (0x41A51F, 5),
        "VV1_EVENT_PICK_BYTES": (0x4237DD, 5),
    },
    "vv2": {
        "VV2_CUSTOM_CHOOSE_BYTES": (0x4349B2, 5),
        "VV2_TITLE_SITE_BYTES": (0x429DE3, 5),
        "VV2_CHOICE_SETUP_BYTES": (0x42244A, 5),
        "VV2_EVENT_PICK_BYTES": (0x42EEED, 5),
    },
    "vv3": {"VV3_TITLE_SITE_BYTES": (0x468FC8, 6), "VV3_EVENT_PICK_BYTES": (0x468757, 5)},
    "vv4": {"VV4_TITLE_SITE_BYTES": (0x4404D9, 5), "VV4_EVENT_PICK_BYTES": (0x43FA70, 5)},
    "vv5": {"VV5_TITLE_SITE_BYTES": (0x44319E, 6), "VV5_EVENT_PICK_BYTES": (0x44272F, 5)},
}
CUSTOM_SITE_ROUTINES = {
    "VV1_EVENT_PICK_BYTES": "the event trigger's villager draw 0x43BCD0 (a Custom Island Event arrives within seconds)",
    "VV2_EVENT_PICK_BYTES": "the event trigger's villager draw 0x44BAE0 (a Custom Island Event arrives within seconds)",
    "VV3_EVENT_PICK_BYTES": "the event trigger's villager draw 0x45C9D0 (a Custom Island Event arrives within seconds)",
    "VV4_EVENT_PICK_BYTES": "the event trigger's villager draw 0x4679B0 (a Custom Island Event arrives within seconds)",
    "VV5_EVENT_PICK_BYTES": "the event trigger's villager draw 0x471870 (a Custom Island Event arrives within seconds)",
    "VV1_CUSTOM_CHOOSE_BYTES": "the island event's chooser call 0x428470 (Custom Island Event delivery)",
    "VV1_TITLE_SITE_BYTES": "the villager panel's title, before its label is set (custom titles)",
    "VV2_CUSTOM_CHOOSE_BYTES": "the island event's chooser call 0x434570 (Custom Island Event delivery)",
    "VV2_TITLE_SITE_BYTES": "the villager panel's title label call 0x40C510 (custom titles)",
    "VV1_CHOICE_SETUP_BYTES": "the villager encounter's setup call 0x4189E0 (a Custom Island Event question)",
    "VV2_CHOICE_SETUP_BYTES": "the two-choice event's setup call 0x41F780 (a Custom Island Event question)",
    "VV3_TITLE_SITE_BYTES": "the villager panel's title, before its label is set (custom titles)",
    "VV4_TITLE_SITE_BYTES": "the villager panel's title, before its label is set (custom titles)",
    "VV5_TITLE_SITE_BYTES": "the villager panel's title, before its label is set (custom titles)",
}

# Each game's Parentage row conception hook: the companion logs a custom
# pregnancy's conception only when this site no longer holds the stock bytes
# (the row is ticked).  game -> VA; the stock bytes are read from the stock
# executable and emitted with it.
PARENTAGE_SITES = {"vv1": 0x43BC39, "vv2": 0x44BAD8, "vv3": 0x455BF3, "vv4": 0x45E8E4,
                   "vv5": 0x465F34}

# The Lost Children's Restore Missing Island Events row: the case-4 body
# (scripts/build_vv2_restore_missing_island_events_feature.py) and its
# rand(3) page roll, the site Pick Island Event answers for a picked page.
VV2_LORE_BODY_VA = 0x42F032
VV2_LORE_BODY_LENGTH = 48
VV2_LORE_PAGE_SITE = 0x42F034

# Each game's rand(bound) routine (cdecl): the outcome sites call it.
RAND = {"vv1": 0x402F10, "vv2": 0x4031A0, "vv3": 0x4032D0, "vv4": 0x4036D0, "vv5": 0x403660}

# Addresses the companion reads or calls, per game (emitted as #defines).
CONSTANTS = {
    "VV3_EVENT_TABLE": 0x4B3C78, "VV3_EVENT_GETTER": 0x419AC0,
    "VV3_PICK_SITE": 0x419BDB, "VV3_MANAGER_GLOBAL": 0x4B309C,
    "VV3_QUEUE_ARM_ISLAND": 0x6DF340, "VV3_ISLAND_FLAG": 0x6E0050,
    "VV4_EVENT_TABLE": 0x4CCA28, "VV4_EVENT_GETTER": 0x417F70,
    "VV4_PICK_SITE": 0x4180F7, "VV4_WORLD_GLOBAL": 0x4CB51C,
    "VV4_COUNTDOWN": 0x170E0, "VV4_CLOCK": 0x403750,
    "VV4_ISLAND_TOKEN": 0x728B08, "VV4_ISLAND_STAMP": 0x728B0C,
    "VV4_BARREL_ARMED": 0x728B04,
    "VV5_EVENT_TABLE": 0x4DC850, "VV5_EVENT_GETTER": 0x4187F0,
    "VV5_PICK_SITE": 0x41895B, "VV5_WORLD_GLOBAL": 0x4DACE0,
    "VV5_COUNTDOWN": 0x17D3C, "VV5_PURCHASE_FLAGS": 0x51D388,
}


def _load_patcher():
    import vv_fun_patcher as patcher  # noqa: E402

    return patcher


def _render(patcher, game: str, mode: str, ids: list[str]) -> bytes:
    builds = {b.id: b for b in patcher.load_builds()}
    build = builds[game]
    source = ROOT / "inputs" / f"{game}-stock-copy" / build.input_name
    data, _ = patcher.render_patched_bytes(source, build, mode, ids)
    return bytes(data)


class Image:
    def __init__(self, data: bytes):
        self.data = data
        self.pe = pefile.PE(data=data, fast_load=True)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase

    def offset(self, va: int) -> int:
        return self.pe.get_offset_from_rva(va - self.base)

    def read(self, va: int, n: int) -> bytes:
        o = self.offset(va)
        return self.data[o:o + n]

    def cstring(self, va: int) -> bytes:
        o = self.offset(va)
        return self.data[o:self.data.index(b"\0", o)]


def _instruction_at_immediate(image: Image, imm_va: int) -> tuple[int, bytes]:
    """The instruction whose 32-bit immediate sits at imm_va: (start VA, bytes).

    The immediate is the instruction's last four bytes and one of its
    operands (cmp/sub/add/push/mov imm32).  Exactly one start may decode that
    way, or the build fails: a guessed boundary would make the companion
    verify and rewrite bytes of the wrong instruction."""
    from capstone.x86 import X86_OP_IMM

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    value = struct.unpack("<i", image.read(imm_va, 4))[0]
    if abs(value) not in PRICES:
        raise SystemExit(f"0x{imm_va:X} holds {value}, not a price")
    found = []
    for back in range(1, 8):
        start = imm_va - back
        for ins in md.disasm(image.read(start, 16), start):
            if ins.address != start or ins.address + ins.size != imm_va + 4:
                break
            imms = [op.imm for op in ins.operands if op.type == X86_OP_IMM]
            # No Origins price instruction carries a prefix; a candidate that
            # does has borrowed the previous instruction's last byte (a
            # branch displacement of 0x64 decodes as an fs: prefix).
            if any(ins.prefix):
                break
            if any(((imm + (1 << 31)) % (1 << 32)) - (1 << 31) == value for imm in imms) and \
                    ins.mnemonic in ("cmp", "sub", "add", "push", "mov"):
                found.append((start, bytes(ins.bytes)))
            break
    if len(found) != 1:
        raise SystemExit(f"0x{imm_va:X}: {len(found)} candidate instructions {found}")
    return found[0]


def _price_writes(game: str, image: Image) -> list[dict]:
    writes = []
    for va, count in PRICE_TABLES[game]:
        before = image.read(va, 4 * count)
        values = struct.unpack(f"<{count}I", before)
        if any(v not in PRICES for v in values):
            raise SystemExit(f"{game}: price table at 0x{va:X} holds {values}")
        writes.append({"va": va, "expect": before, "replace": bytes(len(before)),
                       "routine": "the Origins price table (%d prices)" % count})
    for imm in PRICE_IMMEDIATES[game]:
        start, before = _instruction_at_immediate(image, imm)
        k = imm - start
        after = before[:k] + bytes(4) + before[k + 4:]
        price = abs(struct.unpack("<i", before[k:k + 4])[0])
        writes.append({"va": start, "expect": before, "replace": after,
                       "routine": f"an Origins charge, check or refund of {price:,} tech points"})
    for va in PRICE_STRINGS[game]:
        text = image.cstring(va)
        new = re.sub(rb"\d{1,3}(?:,\d{3})+", b"0", text)
        if new == text:
            raise SystemExit(f"{game}: string at 0x{va:X} shows no price: {text!r}")
        writes.append({"va": va, "expect": text, "replace": new + bytes(len(text) - len(new)),
                       "routine": "an Origins prompt that shows the price"})
    return writes


def _origins_owned_ranges(patcher, game: str, mode: str, ids: list[str]) -> list[tuple[int, int]]:
    builds = {b.id: b for b in patcher.load_builds()}
    build = builds[game]
    source = ROOT / "inputs" / f"{game}-stock-copy" / build.input_name
    data, applied = patcher.render_patched_bytes(source, build, mode, ids)
    ranges = []
    for record in applied:
        if "origins" not in record.get("owner", ""):
            continue
        n = len(bytes.fromhex(record["after"])) if record.get("after") else 0
        if n:
            ranges.append((int(record["offset"], 0), int(record["offset"], 0) + n))
    # Sections the rows append (VV5's Task9 page) are owned whole.
    image = pefile.PE(data=bytes(data), fast_load=True)
    stock = pefile.PE(str(source), fast_load=True)
    names = {s.Name for s in stock.sections}
    for section in image.sections:
        if section.Name not in names:
            ranges.append((section.PointerToRawData,
                           section.PointerToRawData + section.SizeOfRawData))
    return ranges


def _price_sites(patcher, game: str, image: Image, ids: list[str], writes: list[dict]) -> None:
    """Fail unless every price the Origins rows hold is one of `writes`."""
    covered = set()
    for w in writes:
        start = image.offset(w["va"])
        covered.update(range(start, start + len(w["expect"])))
    for start, end in _origins_owned_ranges(patcher, game, "collection_progression", ids):
        blob = image.data[start:end]
        for i in range(len(blob) - 3):
            if abs(struct.unpack_from("<i", blob, i)[0]) in PRICES and start + i not in covered:
                raise SystemExit(
                    f"{game}: an Origins byte range holds a price at file 0x{start + i:X} "
                    "that this row does not zero"
                )
        for m in re.finditer(rb"[\x20-\x7e]{6,}", blob):
            if re.search(rb"\d{1,3},\d{3}", m.group()) and start + m.start() not in covered:
                raise SystemExit(f"{game}: an Origins string shows a price: {m.group()!r}")


def _feature_ids(patcher, game: str) -> tuple[list[str], list[str]]:
    public = patcher.load_public_fun_patches()
    minimal = [f"{game}_origins_village_wide_upgrades"]
    # Every other row (this one, and its "cost Tech Points" row that needs it, left out).
    full = [p.id for p in public if p.game_id == game and not p.id.startswith(f"{game}_story_cheat_upgrades")]
    return minimal, full


def _c_bytes(name: str, data: bytes) -> str:
    body = ", ".join(f"0x{b:02X}" for b in data)
    return f"static const unsigned char {name}[{len(data)}] = {{ {body} }};"


def _c_string(text: str) -> str:
    return json.dumps(text, ensure_ascii=True)


def build() -> None:
    patcher = _load_patcher()
    lines = [
        "/* GENERATED by scripts/build_story_cheat_upgrades_features.py -- do not edit. */",
        "#ifndef VVFP_STORY_TABLES_H",
        "#define VVFP_STORY_TABLES_H",
        "",
        "typedef struct { unsigned int va; int length; const unsigned char *expect; "
        "const unsigned char *replace; } story_write;",
        "typedef struct { unsigned int va; int length; const unsigned char *expect; "
        "int is_call; void *stub; } story_detour;",
        "typedef struct { int slot; const char *title; const char *variant; "
        "const char *description; const char *requires; } story_event;",
    ] + story_outcome_tables.C_TYPES + [
        "",
    ]
    for name, value in CONSTANTS.items():
        lines.append(f"#define {name} 0x{value:X}u")
    lines.append("")
    max_events = max(len(story_island_events.EVENTS[g]) for g in GAMES)
    lines.append(f"#define STORY_MAX_EVENTS {max_events}")
    lines.append("")
    manifests = {}
    for game in GAMES:
        minimal, full = _feature_ids(patcher, game)
        renders = [_render(patcher, game, mode, ids) for mode in MODES for ids in (minimal, full)]
        image = Image(renders[0])
        writes = _price_writes(game, image)
        _price_sites(patcher, game, Image(_render(patcher, game, "collection_progression", full)),
                     full, writes)
        stock_image = Image((ROOT / "inputs" / f"{game}-stock-copy" /
                             {b.id: b for b in patcher.load_builds()}[game].input_name).read_bytes())
        sites = {}
        for name, (va, n) in (list(PICK_SITES[game].items()) + list(UNLOCK_SITES.get(game, {}).items())
                              + list(CUSTOM_SITES[game].items())
                              + list(story_outcome_tables.APPLY_SITES.get(game, {}).items())):
            sites[name] = (va, image.read(va, n))
            if stock_image.read(va, n) != sites[name][1]:
                raise SystemExit(f"{game}: {name} at 0x{va:X} is not the stock code")
        parentage_va = PARENTAGE_SITES[game]
        parentage_stock = stock_image.read(parentage_va, 5)
        full_render = Image(_render(patcher, game, "collection_progression", full))
        if full_render.read(parentage_va, 5) == parentage_stock:
            raise SystemExit(f"{game}: the Parentage row's conception hook is not at 0x{parentage_va:X}")
        for data in renders:
            other = Image(data)
            for w in writes:
                if other.read(w["va"], len(w["expect"])) != w["expect"]:
                    raise SystemExit(f"{game}: 0x{w['va']:X} differs between renders")
            for name, (va, expect) in sites.items():
                if other.read(va, len(expect)) != expect:
                    raise SystemExit(f"{game}: {name} differs between renders")
        tag = game.upper()
        entries = []
        for i, w in enumerate(writes):
            lines.append(_c_bytes(f"{tag}_W{i}_E", w["expect"]))
            lines.append(_c_bytes(f"{tag}_W{i}_R", w["replace"]))
            entries.append(f"    {{ 0x{w['va']:X}u, {len(w['expect'])}, {tag}_W{i}_E, {tag}_W{i}_R }},")
        lines.append(f"static const story_write {tag}_WRITES[] = {{")
        lines.extend(entries)
        lines.append("};")
        lines.append(f"#define {tag}_WRITE_COUNT {len(writes)}")
        for name, (va, expect) in sites.items():
            lines.append(_c_bytes(name, expect))
        if game == "vv2":
            # Restore Missing Island Events (its own row): the case-4 lore-page
            # body.  The companion offers the three pages, and answers the
            # body's rand(3) for a picked page, only when exactly these bytes
            # are there.
            lore = full_render.read(VV2_LORE_BODY_VA, VV2_LORE_BODY_LENGTH)
            if lore == stock_image.read(VV2_LORE_BODY_VA, VV2_LORE_BODY_LENGTH):
                raise SystemExit("vv2: the Restore Missing Island Events row's case-4 body is missing")
            if lore[2:7] != bytes([0xE8]) + struct.pack("<i", RAND[game] - (VV2_LORE_PAGE_SITE + 5)):
                raise SystemExit("vv2: the case-4 body does not start with push 3; call rand")
            lines.append(f"#define VV2_LORE_BODY_VA 0x{VV2_LORE_BODY_VA:X}u")
            lines.append(f"#define VV2_LORE_PAGE_SITE 0x{VV2_LORE_PAGE_SITE:X}u")
            lines.append(_c_bytes("VV2_LORE_BODY", lore))
        lines.append(f"#define {tag}_PARENTAGE_SITE 0x{parentage_va:X}u")
        lines.append(_c_bytes(f"{tag}_PARENTAGE_STOCK", parentage_stock))
        events = story_island_events.EVENTS[game]
        outcome_info = story_outcome_tables.collect(game)
        taken = [(w["va"], w["va"] + len(w["expect"])) for w in writes]
        taken += [(va, va + len(expect)) for va, expect in sites.values()]
        outcome_found = story_outcome_tables.check(
            game, outcome_info, RAND[game], stock_image.read,
            [Image(data).read for data in renders], taken)
        lines.extend(story_outcome_tables.emit(game, outcome_info, outcome_found,
                                               [e["slot"] for e in events]))
        lines.append(f"static const story_event {tag}_EVENTS[] = {{")
        for e in events:
            lines.append(
                f"    {{ {e['slot']}, {_c_string(e['title'])}, {_c_string(e['variant'])}, "
                f"{_c_string(e['description'])}, {_c_string(e['requires'])} }},"
            )
        lines.append("};")
        lines.append(f"#define {tag}_EVENT_COUNT {len(events)}")
        lines.append("")
        manifests[game] = (writes, sites, events, outcome_info, outcome_found)
    lines.append("#endif")
    HEADER.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    dll = ROOT / DLL_SOURCE
    dll_sha = hashlib.sha256(dll.read_bytes()).hexdigest().upper() if dll.is_file() else ""
    for game, (writes, sites, events, outcome_info, outcome_found) in manifests.items():
        number = game[2:]
        detours = [
            {
                "va": f"0x{w['va']:X}",
                "stock_bytes": w["expect"].hex().upper(),
                "written_bytes": w["replace"].hex().upper(),
                "routine": w["routine"],
                "installed_by": f"{DLL_NAME}, VvfpStoryInstall",
            }
            for w in writes
        ] + [
            {
                "va": f"0x{va:X}",
                "stock_bytes": expect.hex().upper(),
                "routine": PICK_SITE_ROUTINES[name] + " (Pick Island Event)"
                if name in PICK_SITE_ROUTINES else (
                    story_outcome_tables.APPLY_ROUTINES[name]
                    if name in story_outcome_tables.APPLY_ROUTINES else
                    UNLOCK_SITE_ROUTINES.get(name) or CUSTOM_SITE_ROUTINES[name]),
                "installed_by": f"{DLL_NAME}, VvfpStoryInstall",
            }
            for name, (va, expect) in sites.items()
        ] + story_outcome_tables.manifest_rows(game, outcome_info, outcome_found, DLL_NAME)
        record = {
            "id": f"{game}_story_cheat_upgrades",
            "enabled": True,
            "game_id": game,
            "name": NAME,
            "description": DESCRIPTION + (VV1_PARENTS_NOTE if game == "vv1" else "")
            + (VV2_GONG_NOTE if game == "vv2" else ""),
            "output_tag": "Story Cheat Upgrades",
            "dependencies": [f"{game}_origins_village_wide_upgrades"],
            "behavior_changes": [
                "Every Origins upgrade on the Tech screen and the Villager Details screen costs 0 "
                "tech points: each price the Origins payload compares, deducts, refunds or shows "
                "is set to 0 at run time, and the Origins companion shows and charges 0.",
                "Every existing refusal stays: one pending Island Event or Barrel of Babies at a "
                "time, room for the Barrel's children, and every \"nothing to change\" check.",
                "Adds a Pick Island Event upgrade (0 tech points) to the Origins Tech menu: a "
                "plain Windows list of this game's island events by their official titles, each "
                "with a one-line description.  The pick makes the island event due exactly as "
                "the Island Event upgrade does (the same pending lock), and when the game's own "
                "scheduler fires it, the game's own chooser runs the picked event -- only if that "
                "event's own condition holds -- with its own text, choices, random outcomes and "
                "amounts.",
                f"Offers {len(events)} island events; events that can never run in this game are "
                "not offered.",
                "Adds a Custom Island Event upgrade (0 tech points): plain Windows dialogs build an "
                "event (title, description, village changes, new villagers, per-villager changes "
                "for a list with extended selection and the group toggles All Adult Women, All "
                "Adult Men, All Females, All Males and All Children, plus in New Believers All Heathens "
                "and one toggle for each Heathen type; each villager's row names the role the game "
                "keeps for them, such as the Golden Child or the Tribal Chief).  It is queued exactly as the "
                "Island Event upgrade queues one (the same lock), and when the game's own scheduler "
                "fires it, the game's own island-event popup shows the custom title and description "
                "and the changes are made through the game's own routines.",
                "New villagers and babies are made only while the game's own room predicate says "
                "the village has room, so the population cap of the installed mode is never passed.",
                "Pick Island Event's settings: each offered event can carry its result, every "
                "amount it rolls, who a per-villager roll hits, which villager it is about and each "
                "baby's details (A New Home and The Lost Children: also its strength), each "
                "defaulting to Random (original game).  The companion points the event's own "
                "rand() calls at a stub that answers the chosen value only in that roll's phase "
                "(before the popup, the popup, or the event's apply), for the clicked choice, and "
                "-- in a routine other code shares -- only inside the event's own call to it; the "
                "outcome ends when the event's apply returns, on refusal and on lapse, so no "
                "chosen value reaches a natural event.",
                "Unlocked picks: an event whose own condition is only timing or story (proven by "
                "running its popup and apply with the condition false) can be picked anyway; its "
                "condition is passed for that one delivery only.  Developer-dead events proven to "
                "work are offered as never happening in the original game.",
                "A custom title replaces a villager's title in the villager panel and is printed in "
                "the Village Population and Village History logs; it is kept per save slot in "
                "Virtual Villagers Fun Patcher Data\\Custom Titles\\Custom Titles - Save N.dat and "
                "deleted by Start Over.",
            ],
            "explicit_non_changes": [
                "No executable byte is patched; the companion writes the listed sites at run time "
                "after verifying every one of them, and writes nothing if any differs.",
                "No stock event is emulated: a picked event is created, shown and resolved by the "
                "game's own code; a custom event is shown by the game's own island-event popup.",
                "Pick Island Event adds no tech points and writes nothing to the save; a custom "
                "event changes only what the player chose, through the game's own routines and "
                "fields, and the game saves the village as usual.",
                "No custom title is written into a villager record.",
            ],
            "evidence_status": (
                "static exact-build verification and emulation of the rendered executables and the "
                "companion; runtime/player confirmation pending"
            ),
            "companion_files": [
                {"source": DLL_SOURCE, "destination": DLL_NAME, "sha256": dll_sha},
            ],
            "runtime_detours": detours,
            "island_events": [
                {"slot": e["slot"], "title": e["title"], "variant": e["variant"],
                 "description": e["description"], "requires": e["requires"]}
                for e in events
            ],
            "excluded_island_events": story_island_events.EXCLUDED[game],
            "island_event_settings": story_outcome_tables.manifest_settings(game),
            "custom_island_event": {
                "offered": CUSTOM_OFFERED[game],
                "omitted": CUSTOM_OMITTED[game],
            },
            "patches": [],
        }
        path = ROOT / "data" / f"vv{number}_story_cheat_upgrades_feature.json"
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"{game}: {len(writes)} price sites, {len(sites)} pick sites, {len(events)} events -> {path.name}")
        costs = cost_record(game)
        cost_path = ROOT / "data" / f"vv{number}_story_cheat_upgrades_cost_tech_points_feature.json"
        cost_path.write_text(json.dumps(costs, indent=2) + "\n", encoding="utf-8", newline="\n")


# "Story / Cheat Upgrades cost Tech Points" (the owner, 2026-10-06): "basically
# nullifies the 'everything costs 0 points' when Story/Cheats patch is checked.
# Custom Island Events/Custom Gong of Wonder/Pick Island Event will cost the
# normal 'Island Event' upgrade cost."  Ticked together with Story / Cheat
# Upgrades by default.  No bytes of its own: the patcher sets bit 30 of the
# startup loader's word (STARTUP_LOADER_STORY_CHARGES), and the Story
# companion then leaves every Origins price as it is and charges the Island
# Event upgrade's 30,000 for the story events.
COST_NAME = "Story / Cheat Upgrades cost Tech Points"
ISLAND_EVENT_PRICE = 30000           # the Origins Island Event upgrade, all five games


def cost_record(game: str) -> dict:
    gong = (" and Pick Gong of Wonder Outcome" if game == "vv2" else "")
    return {
        "id": f"{game}_story_cheat_upgrades_cost_tech_points",
        "enabled": True,
        "game_id": game,
        "name": COST_NAME,
        "description": (
            "**Requires Story / Cheat Upgrades.** With this ticked, the Origins upgrades keep their "
            "normal tech-point prices instead of costing 0, and Pick Island Event, Custom Island "
            "Event" + gong + " each cost what the Island Event upgrade costs: "
            f"{ISLAND_EVENT_PRICE:,} tech points, paid when the event is queued. With too few tech "
            "points you are told, and nothing is queued or spent. Untick it to keep every upgrade "
            "free. Ticking Story / Cheat Upgrades ticks this too."
        ),
        "output_tag": "Story Cheat Costs",
        "dependencies": [f"{game}_story_cheat_upgrades"],
        "behavior_changes": [
            "The Story companion verifies its price sites as usual but does not write the zero "
            "prices, so the Origins upgrades show and charge their normal prices.",
            "Pick Island Event, Custom Island Event" + gong + " cost "
            f"{ISLAND_EVENT_PRICE:,} tech points each, taken from the village's tech points when "
            "the event is queued; with fewer, a message says so and nothing is queued.",
        ],
        "explicit_non_changes": [
            "No byte of the executable is changed by this row: the patcher sets bit 30 of the "
            "startup loader's word (the companions' list stays within bits 1-29).",
            "Without Story / Cheat Upgrades this row does nothing (it requires it).",
        ],
        "evidence_status": (
            "emulated: the Story companion's install with the flag set writes no price; the "
            "story events' charge and refusal; runtime/player confirmation pending"
        ),
        "companion_files": [],
        "patches": [],
    }


if __name__ == "__main__":
    build()
