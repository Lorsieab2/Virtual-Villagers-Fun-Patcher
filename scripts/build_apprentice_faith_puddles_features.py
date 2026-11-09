"""Generate three new kinds of exe patch rows:

  data/vv{1,2,3,5}_apprentice_graves_feature.json   "Children's Graves Say Apprentice" (default on)
  data/vv5_faith_loss_feature.json                  "Faith Loss is Doubled/Gains Halved" (default off)
  data/vv5_puddles_by_the_lake_feature.json         "Puddle Play Moves to the Lake Shore" (default on)

Each is a few guarded byte edits of the stock exe, assembled here (keystone) from the stock bytes
(research/stock-executables).  Run after any change and re-run the touched tests.

CHILDREN'S GRAVES SAY APPRENTICE.  The owner: "Children who are at least trainees in any skill will say for
example "Apprentice Farmer, scientist, parent etc"" and "Apprentice on graves SHOULD BE FOR ALL GAMES THAT DON'T
ALREADY HAVE THEM".  The Tree of Life's grave dialog does it (0x41BE43: a grave whose age at death is under 280
age units, 14 years, and whose best skill is 20 or more says string 0xD6 "Apprentice " instead of the rank);
the other four games' grave skill lines never do.  Each game builds the line the same way: the best skill
under 20 (or no job) prints "Untrained"; otherwise the rank's string -- "Trainee " under 50, "Adept " under
the master value, "Master " -- into the line buffer, then the job's word is appended.  The block that picks
the rank's string id is recoded in place, same length, as

    best skill < 20                   -> Untrained (as stock)
    age at death < 280                -> the game's own "Apprentice " string
    else < 50 / < master / otherwise  -> Trainee / Adept / Master (as stock)

and the one outside jump into the block (job none -> Untrained) is re-aimed at the recoded Untrained.  The
game's own string ("Apprentice ", eSayApprentice in the later games; the string the Villager Detail panel
gives a child in A New Home and The Lost Children) is used, so it is in the game's language.

  A New Home        popup 0x436516..0x436565 (strings 0x54 Untrained, 0x56 Apprentice, 0x57 Trainee,
                    master 90); grave = manager + slot * 0x2C, best skill +0xA338, age +0xA340
  The Lost Children panel 0x44456A..0x4445CB (0x81, 0x83, 0x84, master 88); best skill +0x2EB78, age +0x2EB80
  The Secret City   dialog 0x41E941..0x41E996 (0x90, 0x92, 0x93); roster entry esi, age +0x1C
  New Believers     dialog 0x41C680..0x41C6D5 (0xC4, 0xC6, 0xC7); roster entry esi, age +0x1C

The Cause of Death companion (native/vvfp_cause_of_death) writes the same skill line into the Deaths log and,
in A New Home and The Lost Children, used to put "Apprentice" on the popup itself; it now does both only when
this row's bytes are in the exe (cod_apprentice_patched), so one rule decides the grave and the log.

FAITH LOSS IS DOUBLED/GAINS HALVED.  The owner: "I feel like VV5 should be even harder. there should be a patch
to make Believers lose Faith easier, so they can become heathens easier" -- then: double every loss roll's
chance, halve every gain roll's chance, drop the "below 5 a fall is skipped half the time" protection, keep the
"above 75 a rise is skipped 70%" rule.  The per-age-unit drift 0x468040 (every believer, live and catching up):

    food under 10        -1 on rand(100) < 30, else the 10..250 roll       -> < 60
    food 10..250         -1 on rand(100) < 10                               -> < 20
    food 8,000+          +1 on rand(100) < 20                               -> < 10
    sick                 -1 on rand(100) < 15                               -> < 30
    Tribute Statue done  +1 on rand(100) < 30 (stage 2: < 20, stage 1: < 10) -> < 15 (< 10, < 5)
    Spirituality 1/2/3   +1 on rand(100) < 10 / 20 / 30                     -> < 5 / 10 / 15
    believers < 12       -1 on rand(100) < 12 - n                           -> < 2 * (12 - n)
    believers >= 12      +1 on rand(100) < n / 5                            -> < n / 10
    sum < 0, Faith < 5   skipped on rand(100) < 50                          -> never skipped
    sum > 0, Faith > 75  skipped on rand(100) < 70                          -> unchanged

A believer at 0 or less becomes a Heathen in the setter 0x467F90, as in the stock game.

PUDDLE PLAY MOVES TO THE LAKE SHORE.  The owner: children "Playing in puddles" in the dry lake bed; "once the
lake bed is full of water that action is disabled (because they can't swim)", and asked for them to play "at this
edge of the lake" (the north-west sandy shore, marked on a screenshot).  The owner (2026-11-07): "PLAYING IN
PUDDLES IS PLAYING IN PUDDLES NOT ANYTHING ELSE" -- not "Excited about the puddles" (0xEB) nor "Chasing fish"
(0xEA), which stay exactly as stock.  "Playing in puddles" is behaviour 0x5E (routine 0x45FFF0, string 0x229,
registered at 0x4643A6): five walks to a random point of lake-bed area 0x6A (0x4744C0 at 0x46003B), each with
gestures.  Its one chooser, 0x46E4F7, starts it when the rain level [0x718EB8] is 50 or more, rand(100) < 75, it is
raining (0x477040) and the lake holds no water (0x43C5D0: project 10's progress above 0, when the full lake is
drawn).  The patch drops "the lake holds no water" (test al,al / jne at 0x46E527 -> nops; the start flag is bl,
untouched), and 0x5E's walk (0x46003B) calls a cave at 0x494E00: with water in the lake, a walk to a random point
of the shore line (SHORE_* below); without, the stock walk into the lake bed.  The spots are lcmap.dat cells (8 x
8 world pixels) on that sandy strip: walkable, not lake (areas 0x69 / 0x6A), every neighbour walkable, connected
to the village; the owner's screenshot matched the map art at 1.5x, top-left world (1345, 1870).  Behaviour 0x5F
(0x4600D0, the waterfall pool; started only by The Missing Kids island event, 0x4161AA) is unchanged.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pefile
from keystone import KS_ARCH_X86, KS_MODE_32, Ks

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
EXE = {1: "Virtual Villagers - A New Home.exe", 2: "Virtual Villagers - The Lost Children.exe",
       3: "Virtual Villagers - The Secret City.exe", 5: "Virtual Villagers - New Believers.exe"}
GAME_NAME = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 5: "New Believers"}
KS = Ks(KS_ARCH_X86, KS_MODE_32)
CHILD_AGE = 0x118           # 280 age units, 14 years: The Tree of Life's own boundary (0x41BE43)

APPRENTICE_NAME = "Children's Graves Say Apprentice"
FAITH_ID = "vv5_faith_loss_doubled_gains_halved"
FAITH_NAME = "Faith Loss is Doubled/Gains Halved"
PUDDLES_ID = "vv5_puddles_by_the_lake"
PUDDLES_NAME = "Puddle Play Moves to the Lake Shore"


def apprentice_id(game: int) -> str:
    return f"vv{game}_apprentice_graves"


def asm(src: str, va: int) -> bytes:
    return bytes(KS.asm(src, va)[0])


_exes: dict[int, tuple] = {}


def stock(game: int, va: int, n: int) -> bytes:
    if game not in _exes:
        path = STOCK / EXE[game]
        _exes[game] = (pefile.PE(str(path), fast_load=True), path.read_bytes())
    pe, data = _exes[game]
    off = pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)
    return data[off:off + n]


def patch(game: int, va: int, after: bytes, purpose: str, before: bytes | None = None) -> dict:
    before = stock(game, va, len(after)) if before is None else before
    assert len(before) == len(after)
    return {"offset": "0x%X" % (va - 0x400000), "before": before.hex().upper(), "after": after.hex().upper(),
            "purpose": purpose}


# ---- Children's Graves Say Apprentice ------------------------------------------------------------------------

# game: block start, the instruction after the copy call, the outside je, Untrained / Apprentice / Trainee ids,
# master value, the best skill's operand (None: already in eax), the age's operand, the string-table load,
# the string routine, the line buffer's offset from esp after that call (before the string's push: New Believers'
# own code pushes the string first and then takes [esp+0x38], the same buffer), the copy routine.
GRAVES = {
    1: (0x436516, 0x436565, 0x436514, 0x54, 0x56, 0x57, 90, "dword ptr [eax+0xa338]", "dword ptr [eax+0xa340]",
        "mov ecx,dword ptr [ebx+0x7c]", 0x433970, 0x14, 0x44B23D),
    2: (0x44456A, 0x4445CB, 0x444568, 0x81, 0x83, 0x84, 88, "dword ptr [eax+0x2eb78]", "dword ptr [eax+0x2eb80]",
        "mov ecx,dword ptr [ebp+0x80]", 0x441680, 0x14, 0x4682BD),
    3: (0x41E941, 0x41E996, 0x41E939, 0x90, 0x92, 0x93, 88, None, "dword ptr [esi+0x1c]",
        "mov ecx,dword ptr [ebp+0x5c]", 0x42F190, 0x30, 0x46EFCD),
    5: (0x41C680, 0x41C6D5, 0x41C67B, 0xC4, 0xC6, 0xC7, 88, None, "dword ptr [esi+0x1c]",
        "mov ecx,dword ptr [ebp+0x5c]", 0x4506D0, 0x34, 0x47C046),
}


def grave_block(game: int) -> tuple[bytes, bytes, int]:
    """The recoded block, the re-aimed je, and the Untrained label's address."""
    lo, hi, je, untrained, apprentice, trainee, master, value, age, table, string, buf, copy = GRAVES[game]
    if value:   # A New Home / The Lost Children: eax is the grave; test the skill and age, then load the skill
        head = (f"cmp {value},0x14\n jl untr\n mov edx,{apprentice:#x}\n cmp {age},{CHILD_AGE:#x}\n jl done\n"
                f" mov eax,{value}\n")
    else:       # The Secret City / New Believers: eax is already the best skill
        head = f"cmp eax,0x14\n jl untr\n mov edx,{apprentice:#x}\n cmp {age},{CHILD_AGE:#x}\n jl done\n"
    src = (head + f" mov dl,{trainee:#x}\n cmp eax,0x32\n jl done\n inc edx\n cmp eax,{master:#x}\n jl done\n"
           f" inc edx\n jmp done\nuntr:\n mov edx,{untrained:#x}\ndone:\n {table}\n push edx\n call {string:#x}\n"
           f" lea ecx,[esp+{buf:#x}]\n push eax\n push ecx\n")
    code = asm(src, lo)
    # The Untrained label: the only `mov edx, <untrained>` (BA imm32) in the block.
    untr = lo + code.index(b"\xBA" + struct.pack("<I", untrained))
    call_at = hi - 5
    assert lo + len(code) <= call_at, game
    code += b"\x90" * (call_at - lo - len(code)) + asm(f"call {copy:#x}", call_at)
    assert len(code) == hi - lo
    assert stock(game, call_at, 5) == code[-5:], "the copy call stays where it was"
    return code, asm(f"je {untr:#x}", je), untr


# The owner (2026-11-07): "A New Home's Golden Child gets no grave title at all. In case he ever dies due to an
# island event or something, his job should be "Golden Child" and his epitaph should be either of the default
# child ones."  One VV1 grave Job rule, this row's: the Golden Child's grave says the game's own "Golden Child"
# (string 0x5F, the Villager Detail panel's for family 199, 0x41FBDC).  The grave keeps no family number (the
# burial 0x448F8D..0x448FF1 copies only the name, the age, the best skill and its job), so the Cause of Death
# companion marks his grave at the burial and draws the line (cod_vv12.inc vv1_job_line, 0x43667C) -- only while
# these bytes are in the exe.  This row's bytes are unchanged.
GOLDEN_DESCRIPTION = (
    " **With Show Cause of Death and Age at Death on Graves ticked too,** the Golden Child's grave says \"Golden "
    "Child\" under Job (the game's own words, as his villager panel shows them) instead of a skill, and his "
    "Deaths log record says the same; that patch also gives him a child's epitaph. It knows his grave from his "
    "burial; for a Golden Child buried before both patches were installed, Repair Saves & Logs marks his "
    "grave from his Deaths log record (when its name and age at death match exactly one grave) and puts "
    "\"Golden Child\" in that record.")
GOLDEN_CHANGE = (
    "With the Cause of Death companion installed, the Golden Child's grave (family 199 at the burial, marked in that "
    "companion's Graves file) shows the game's own string 0x5F (\"Golden Child\") as its whole skill line, put in the "
    "line's buffer right before the popup draws it (0x43667C); his Death record's Grave line says \"Golden Child\".")


def apprentice_feature(game: int) -> dict:
    lo, hi, je, untrained, apprentice, trainee, master = GRAVES[game][:7]
    code, jump, untr = grave_block(game)
    name = GAME_NAME[game]
    description = (
        "A child's grave names the child's job as an \"Apprentice\", the way The Tree of Life does: a villager who "
        "died under 14 years old whose best skill was 20 or more (Trainee or better) shows \"Apprentice Farmer\", "
        "\"Apprentice Scientist\", \"Apprentice Parent\" and so on, instead of \"Trainee\", \"Adept\" or "
        "\"Master\"; below 20 it is \"Untrained\" as before. Adults' graves are unchanged. The word is the game's "
        "own \"Apprentice\" text, so it follows the game's language. Graves are read when shown, so graves made "
        "before you ticked this change too. With Show Cause of Death and Age at Death on Graves, the Deaths log "
        "writes the same line.")
    if game == 1:
        description += GOLDEN_DESCRIPTION
    stock_line = f"\"Trainee\" under 50, \"Adept\" under {master}, \"Master\" from {master}, at any age"
    return {
        "id": apprentice_id(game),
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": APPRENTICE_NAME,
        "description": description,
        "output_tag": "Apprentice Graves",
        "behavior_changes": [
            f"{name}'s grave skill line (0x{lo:X}..0x{hi:X}): a grave whose age at death is under 280 age units "
            f"(14 years) and whose best skill is 20 or more prints the game's own string 0x{apprentice:X} "
            f"(\"Apprentice \") before the job's word. Was {stock_line}.",
            "The Cause of Death companion writes the same line into the Deaths log only while these bytes are in the "
            "executable (cod_apprentice_patched), so the grave and its Death record agree.",
        ] + ([GOLDEN_CHANGE] if game == 1 else []),
        "explicit_non_changes": [
            f"The block is recoded in place, same length; the copy call at 0x{hi - 5:X} and everything after it are "
            "unchanged, and no executable space is claimed.",
            "A best skill under 20 (or no job) is still \"Untrained\"; adults keep Trainee / Adept / Master at the "
            "game's own values; the job's word, the cause, the age and the epitaph are untouched. Nothing is written "
            "to the save: the line is built each time the grave is shown.",
        ],
        "companion_files": [],
        "patches": [
            patch(game, je, jump, f"the grave dialog's no-job branch: je 0x{untr:X} (the recoded Untrained)"),
            patch(game, lo, code,
                  f"the rank pick: best skill < 20 -> 0x{untrained:X} Untrained; age < 0x118 -> 0x{apprentice:X} "
                  f"Apprentice; < 50 -> 0x{trainee:X} Trainee; < {master} -> 0x{trainee + 1:X} Adept; else "
                  f"0x{trainee + 2:X} Master; then the stock string fetch and copy"),
        ],
    }


# ---- Faith Loss is Doubled/Gains Halved ----------------------------------------------------------------------

FAITH_EDITS = (
    (0x46805B, "1E", "3C", "food under 10: -1 on rand(100) < 30 -> < 60"),
    (0x46807B, "0A", "14", "food 10..250 (and food under 10 when its first roll missed): -1 on rand(100) < 10 -> < 20"),
    (0x46809B, "14", "0A", "food 8,000 or more: +1 on rand(100) < 20 -> < 10"),
    (0x4680B8, "0F", "1E", "a sick believer: -1 on rand(100) < 15 -> < 30"),
    (0x4680DA, "1E", "0F", "the Tribute Statue solved: +1 on rand(100) < 30 -> < 15"),
    (0x4680FD, "14", "0A", "the statue's second stage: +1 on rand(100) < 20 -> < 10"),
    (0x46810C, "0A", "05", "the statue's first stage: +1 on rand(100) < 10 -> < 5"),
    (0x468139, "1E", "0F", "Spirituality 3: +1 on rand(100) < 30 -> < 15"),
    (0x468148, "14", "0A", "Spirituality 2: +1 on rand(100) < 20 -> < 10"),
    (0x468157, "0A", "05", "Spirituality 1: +1 on rand(100) < 10 -> < 5"),
    (0x468179, "B90C0000002BCF3BC1", "6BCFFE83C1183BC190",
     "fewer than 12 believers: -1 on rand(100) < 12 - n -> imul ecx,edi,-2 / add ecx,24 / cmp eax,ecx: < 2 * (12 - n)"),
    (0x468192, "D1FA8BC2C1E81F03C2", "C1FA028BC290909090",
     "12 or more believers: +1 on rand(100) < n / 5 -> sar edx,2: < n / 10 (n is positive here, so the sign fix-up "
     "is not needed)"),
    (0x4681AE, "7D", "EB", "a fall with Faith under 5 was skipped on rand(100) < 50: jge -> jmp, never skipped"),
)


def faith_feature() -> dict:
    description = (
        "Every believer's Faith moves each age unit by a few small rolls (New Believers' own Faith drift). This "
        "doubles the chance of every roll that takes Faith away and halves the chance of every roll that gives it: "
        "food under 10 loses 1 Faith 60% of the time (was 30%), and when that misses, 20% (was 10%); food 10 to 250 "
        "loses 1 Faith 20% of the time (was 10%); a sick believer loses 1 more 30% of the time (was 15%); fewer than "
        "12 believers loses 1 with a chance of 2 x (12 - believers) in 100 (was 12 - believers). Food 8,000 or more "
        "gains 1 Faith 10% of the time (was 20%); the Tribute Statue solved 15% (was 30%; its first and second "
        "stages 5% and 10%, were 10% and 20%); Spirituality 1, 2 or 3 gains 5%, 10% or 15% (was 10%, 20% or 30%); "
        "12 or more believers gains 1 with a chance of believers / 10 in 100 (was believers / 5). A fall is no longer "
        "skipped half the time when Faith is below 5, so a believer can fall all the way to 0 and become a Heathen, "
        "as in the stock game at 0; a rise above 75 is still skipped 70% of the time. Preaching, Spreading the Word, "
        "island events and every other Faith change are unchanged. Adds a real chance of your "
        "villagers becoming heathens. Makes the game that much harder. Good Luck!")
    return {
        "id": FAITH_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": FAITH_NAME,
        "description": description,
        "output_tag": "Faith Loss Doubled",
        "behavior_changes": [
            "The Faith drift 0x468040 (each believer, once per age unit, live and while catching up; Heathens skipped "
            "at 0x472CB7): every loss roll's rand(100) threshold doubled, every gain roll's halved, and the 50% skip of "
            "a fall below Faith 5 (0x4681A7) removed. The rise skip above 75 (70%) is unchanged.",
            "A believer whose Faith reaches 0 or less becomes a Heathen in the setter 0x467F90, exactly as in the stock "
            "game.",
        ],
        "explicit_non_changes": [
            "Thirteen immediates and branches inside the routine; no code is added and no executable space is claimed.",
            "Starting Faith, preaching, Spreading the Word, the Heathen Doctor's cure, The Heathen "
            "Chief, the Hydroponic Farm, the Heathen Mommy's puzzle and island events are unchanged.",
        ],
        "companion_files": [],
        "patches": [patch(5, va, bytes.fromhex(after), purpose, bytes.fromhex(before))
                    for va, before, after, purpose in FAITH_EDITS],
    }


# ---- Puddle Play Moves to the Lake Shore -----------------------------------------------------------------------

CAVE = 0x494E00
WALK_SITE = 0x46003B                     # 0x5E "Playing in puddles": call 0x4744C0 (area 0x6A)
GATE = (0x46E527, "84C0751E")            # its chooser 0x46E4F7: test al,al / jne (the lake holds water)
# The north-west sandy shore the owner marked: a random point on the line from world (1348, 2116) to (1599, 2050),
# the feet's point -- x = 1348 + r, y = 2116 - (17r >> 6), r = rand(252).  Every one of the 252 points is an
# lcmap.dat cell that is walkable, not lake (areas 0x69 / 0x6A), with every neighbour walkable, connected to the
# village (tests/test_apprentice_faith_puddles.py); the owner's screenshot matched the map art at 1.5x, top-left
# world (1345, 1870).  Pure code, no data: the cave lies in the .text tail whose every byte must be reached
# (tests/test_vv5_origins_dead_code_removed.py).
SHORE_X, SHORE_Y, SHORE_SPAN, SHORE_SLOPE = 1348, 2116, 252, (17, 6)


def shore_point(r: int) -> tuple[int, int]:
    return SHORE_X + r, SHORE_Y - ((r * SHORE_SLOPE[0]) >> SHORE_SLOPE[1])


def puddle_cave() -> bytes:
    return asm(f"""
        push ecx
        call 0x43c5d0
        pop ecx
        test al,al
        je stock
        push ecx
        push {SHORE_SPAN}
        call 0x403660
        pop edx
        pop ecx
        push dword ptr [esp+0xc]
        push dword ptr [esp+0xc]
        mov edx,eax
        imul edx,edx,{SHORE_SLOPE[0]}
        sar edx,{SHORE_SLOPE[1]}
        neg edx
        add edx,{SHORE_Y}
        push edx
        add eax,{SHORE_X}
        push eax
        call 0x4745a0
        ret 0xc
    stock:
        jmp 0x4744c0
        """, CAVE)


# "Playing in the dirt" (the routine 0x45ED40, say-event 504) moves to the same shore, always (the owner,
# 2026-11-08: before and after The Lake has water; "Those specific actions only and NOT ANY OTHERS!!!").  The
# routine queues six go-tos (0x4745A0 at 0x45ED99, ecx the villager, arguments x, y, speed 0x64, flag 0) to points
# it picks in its own strip; the call is re-aimed at a cave that puts a random point of the puddles' shore line in
# place of the x and y and jumps on to 0x4745A0, so the routine's steps, speed, gestures and say-event stay its own.
# Move the "Playing in the dirt" Spot (vv5_playing_in_the_dirt_spot) moves the same walk to the flower patch: the
# two name each other in "conflicts", and ticking one unticks the other (UNTICKING_CONFLICT_IDS).
DIRT_SITE = 0x45ED99                     # "Playing in the dirt": call 0x4745A0, six times in its loop
DIRT_SPOT_ID = "vv5_playing_in_the_dirt_spot"


def dirt_cave(at: int) -> bytes:
    return asm(f"""
        push ecx
        push {SHORE_SPAN}
        call 0x403660
        pop edx
        pop ecx
        mov edx,eax
        imul edx,edx,{SHORE_SLOPE[0]}
        sar edx,{SHORE_SLOPE[1]}
        neg edx
        add edx,{SHORE_Y}
        add eax,{SHORE_X}
        mov dword ptr [esp+4],eax
        mov dword ptr [esp+8],edx
        jmp 0x4745a0
        """, at)


def dirt_cave_at() -> int:
    """Right after the puddles' cave (the .text tail's every byte must be reached)."""
    return CAVE + len(puddle_cave())


def puddles_feature() -> dict:
    cave = puddle_cave()
    dirt_at = dirt_cave_at()
    dirt = dirt_cave(dirt_at)
    assert dirt_at + len(dirt) <= 0x494E80, "the Fix Vanilla Bugs picker cave starts at 0x494E80"
    description = (
        "When it rains, children in New Believers go \"Playing in puddles\" in the dry lake bed. Once The Lake holds "
        "water the game never starts that action again, because they cannot swim. With this patch, after The Lake "
        "has water, children still go \"Playing in puddles\" when it rains, on the north-west sandy shore of the "
        "lake (between the lake's west tip and the rocks with the red flower), never in the water: each of the "
        "action's five walks goes to a random point along that shore. Before The Lake has water nothing changes. "
        "Children \"Playing in the dirt\" play on that same sandy shore, always, before and after The Lake has "
        "water: each of the action's six steps goes to a random point along it. The actions, their text and their "
        "length are the game's own; \"Excited about the puddles\", \"Chasing fish\" and every other action are "
        "not changed. **Cannot be used with Move the \"Playing in the dirt\" Spot, which moves \"Playing in the "
        "dirt\" to the flower patch instead (ticking one unticks the other).**")
    return {
        "id": PUDDLES_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": PUDDLES_NAME,
        "description": description,
        "output_tag": "Puddles By The Lake",
        "conflicts": [DIRT_SPOT_ID],
        "behavior_changes": [
            "The chooser of \"Playing in puddles\" (behaviour 0x5E, routine 0x45FFF0), 0x46E4F7, starts it when the "
            "rain level [0x718EB8] is 50 or more, rand(100) < 75 and it is raining (0x477040), as stock; stock also "
            "needed the lake to hold no water (0x43C5D0).",
            "0x5E's walk (0x46003B, five times): with water in the lake (0x43C5D0), a walk (0x4745A0) to a random point "
            "of the north-west sandy shore, x = 1348 + r, y = 2116 - (17r >> 6), r = rand(252) (world pixels, the "
            "feet's point: 1348..1599 by 2116..2050); without, the stock walk to a random point of the lake bed "
            "(area 0x6A, 0x4744C0).",
            "\"Playing in the dirt\" (routine 0x45ED40, say-event 504), with the lake dry or full: each of its six "
            f"go-tos (0x4745A0 at 0x45ED99) goes to a random point of the same shore line, x = 1348 + r, y = 2116 - "
            f"(17r >> 6), r = rand(252) (the cave 0x{dirt_at:X} replaces the routine's own x and y and jumps on to "
            "0x4745A0); stock: 236..453 by 442..475, a strip from the rainbow totem's side across the river.",
        ],
        "explicit_non_changes": [
            "Before the lake holds water \"Playing in puddles\" is as stock. Its text (string 0x229), its gestures, "
            "speed and length are unchanged; so are \"Playing in the dirt\"'s text, sound, six steps, speed and "
            "gestures (only the points it walks to change).",
            "\"Excited about the puddles\" (0xEB, 0x454200) and \"Chasing fish\" (0xEA) and their choosers "
            "(0x469E4B, 0x46EFB2) are exactly as stock. Behaviour 0x5F (0x4600D0, the waterfall pool), started only "
            "by The Missing Kids island event (0x4161AA), is unchanged. No save or villager-record byte is written.",
        ],
        "companion_files": [],
        "patches": [
            patch(5, GATE[0], bytes.fromhex("90909090"),
                  "\"Playing in puddles\" chooser 0x46E4F7: the lake-holds-water test no longer skips it: "
                  "test al,al / jne -> nops (the start flag is bl, unchanged)", bytes.fromhex(GATE[1])),
            patch(5, WALK_SITE, asm(f"call {CAVE:#x}", WALK_SITE),
                  "0x5E's walk: call 0x4744C0 (area 0x6A) -> call the shore cave 0x494E00"),
            patch(5, CAVE, cave,
                  "the shore cave: lake holds water (0x43C5D0)? r = rand(252); a walk 0x4745A0 to (1348 + r, 2116 - "
                  "(17r >> 6)) with the caller's speed and flag, ret 0xC; else jmp 0x4744C0 (stock)",
                  bytes(len(cave))),
            patch(5, DIRT_SITE, asm(f"call {dirt_at:#x}", DIRT_SITE),
                  f"\"Playing in the dirt\" (0x45ED40)'s go-to: call 0x4745A0 -> call the dirt shore cave 0x{dirt_at:X}"),
            patch(5, dirt_at, dirt,
                  "the dirt shore cave: r = rand(252); the go-to's x and y become (1348 + r, 2116 - (17r >> 6)); "
                  "jmp 0x4745A0 with the routine's own speed and flag", bytes(len(dirt))),
        ],
    }


# ---- Fix Vanilla Bugs (New Believers): the lake bed's puddle spots use the whole lake bed -----------------------
#
# The area-point picker 0x477B90 (called by the walk-to-area 0x4744C0 and 67 other places) collects the cells of
# the area it is asked for -- walkable, in row order -- into two 1,024-entry arrays and picks one with
# rand(count).  Past 1,024 cells it stops collecting (`cmp ebp, 0x400 / jge` at 0x477C63), so an area larger than
# that only ever gives points in its first 1,024 cells.  "Playing in puddles" (0x5E) walks to area 0x6A (1,479
# walkable cells), so it only ever used the first 1,024 of them.  The owner approved fixing it for the dry lake
# bed's puddle play, "Playing in puddles" (2026-11-07: not "Excited about the puddles", which stays stock).  Only two areas of lcmap.dat
# have more than 1,024 cells: 0x69 (the lake) and 0x6A (its deep middle, 1,479).  Spreading every caller would
# also send fishers (0x463B50, area 0x69) and the children chasing fish (0x454198, area 0x6A) to points in the
# middle of a filled lake, where the stock game never puts anyone, so the fix is for the puddle play's walk only:
# the picker's caller is 0x4744C0 (return 0x4744EB at [esp+0x2028] at the collecting step) and its caller
# "Playing in puddles"' walk (return 0x460040 at [esp+0x20AC]; with the shore patch its cave tail-jumps to
# 0x4744C0, so the return address is the same).  For that walk the picker keeps a uniform sample of every
# cell (reservoir sampling: the first 1,024 stored, then cell k replaces a random entry with chance 1024 / (k + 1),
# rand(k + 1) < 1024), counts every cell, and draws from min(count, 1024) -- so each cell of the area is equally
# likely.  Every other caller collects exactly as before (the cap moves after the cell checks, which have no side
# effect), and draws as before (its count never passes 1,024).

PICKER_CAVE = 0x494E80
PICKER_FROM_WALK, PICKER_FROM_PUDDLES = 0x4744EB, 0x460040


def picker_fix_patches() -> list[dict]:
    store, skip = 0x477C91, 0x477C9F
    cave = asm(f"""
        cmp dword ptr [esp+0x2028],{PICKER_FROM_WALK:#x}
        jne cap
        cmp dword ptr [esp+0x20ac],{PICKER_FROM_PUDDLES:#x}
        jne cap
        cmp ebp,0x400
        jl keep
        push edx
        lea eax,[ebp+1]
        push eax
        call 0x403660
        pop ecx
        pop edx
        cmp eax,0x400
        jge next
        mov dword ptr [esp+eax*4+0x1028],edi
        mov dword ptr [esp+eax*4+0x28],edx
        jmp next
    cap:
        cmp ebp,0x400
        jge {skip:#x}
    keep:
        mov dword ptr [esp+ebp*4+0x1028],edi
        mov dword ptr [esp+ebp*4+0x28],edx
    next:
        add ebp,1
        jmp {skip:#x}
        """, PICKER_CAVE)
    draw = PICKER_CAVE + len(cave)          # no filler: every byte of the .text tail must be reached
    cave += asm("""
        pop ecx
        mov eax,ebp
        cmp eax,0x400
        jle k
        mov eax,0x400
    k:
        push eax
        push ecx
        jmp 0x403660
        """, draw)
    jump = asm(f"jmp {PICKER_CAVE:#x}", store)
    return [
        patch(5, 0x477C63, bytes.fromhex("EB06") + b"\xCC" * 6,
              "Lake bed puddle spots (0x477C63): the area-point picker's 1,024-cell cap `cmp ebp,0x400 / jge` -> "
              "jmp to the cell checks; the cap is applied in the picker cave at 0x494E80, after them"),
        patch(5, store, jump + b"\xCC" * (14 - len(jump)),
              "Lake bed puddle spots (0x477C91): the picker's store of a cell -> jmp 0x494E80"),
        patch(5, 0x477CDF, asm(f"call {draw:#x}", 0x477CDF) + b"\x90",
              f"Lake bed puddle spots (0x477CDF): the draw `push ebp / call rand` -> call 0x{draw:X}: "
              "rand(min(count, 1024)) with the same stack"),
        patch(5, PICKER_CAVE, cave,
              "Lake bed puddle spots, the picker cave 0x494E80: for \"Playing in puddles\"' walk (0x4744C0 called "
              "from 0x46003B) a uniform sample of every cell of the area (reservoir: cell k replaces entry rand(k + 1) "
              "when that is under 1,024) and a count of every cell; every other caller stores the first 1,024 as "
              "stock; then the draw helper", bytes(len(cave))),
    ]


PICKER_DESCRIPTION = (
    " Children \"Playing in puddles\" in the dry lake bed use all of their part of it: the game picks a spot of an "
    "area from its first 1,024 map cells only, so of the puddles' 1,479 cells only the first 1,024 were ever used; "
    "now every spot is equally likely for that action. Every other walk to an area, fishing and \"Excited about "
    "the puddles\" included, picks exactly as before.")
PICKER_CHANGE = (
    "The area-point picker 0x477B90, for \"Playing in puddles\"' walk only (0x4744C0 called from 0x46003B, "
    "behaviour 0x5E, area 0x6A): every cell of the area is collected into a uniform 1,024-entry sample "
    "(reservoir sampling) and counted, and the draw is rand(min(count, 1024)), so each cell is equally likely; stock "
    "kept the first 1,024 of its 1,479 cells. Every other caller is unchanged, \"Excited about the puddles\" "
    "(0x45423B) included (fishing at the lake 0x463B50 and chasing fish 0x454198 would otherwise stand in the middle "
    "of a filled lake).")


def add_picker_fix() -> None:
    path = ROOT / "data" / "builds.json"
    builds = json.loads(path.read_text(encoding="utf-8"))
    row = next(p for p in builds["fun_patches"] if p["id"] == "vv5_fix_vanilla_bugs")
    mine = {p["offset"]: p for p in picker_fix_patches()}
    # First in the row's list: the other sub-fixes' tests read theirs from the end.
    row["patches"] = list(mine.values()) + [p for p in row["patches"] if p["offset"] not in mine]
    desc = row["description"]
    for old in (" Children playing in the puddles of the dry lake bed", " Children \"Playing in puddles\" in the dry"):
        if old in desc:
            at = desc.index(old)
            stop = desc.index("picks exactly as before.", at) + len("picks exactly as before.")
            desc = desc[:at] + desc[stop:]
    if PICKER_DESCRIPTION not in desc:
        tail = " **Needs no other patch.**"
        assert desc.endswith(tail)
        desc = desc[:-len(tail)] + PICKER_DESCRIPTION + tail
    row["description"] = desc
    row["behavior_changes"] = [c for c in row["behavior_changes"]
                               if not c.startswith("The area-point picker 0x477B90, for ")] + [PICKER_CHANGE]
    path.write_text(json.dumps(builds, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("updated data/builds.json (vv5_fix_vanilla_bugs)")


def main() -> None:
    add_picker_fix()
    out = {}
    for game in GRAVES:
        out[ROOT / "data" / f"vv{game}_apprentice_graves_feature.json"] = apprentice_feature(game)
    out[ROOT / "data" / "vv5_faith_loss_feature.json"] = faith_feature()
    out[ROOT / "data" / "vv5_puddles_by_the_lake_feature.json"] = puddles_feature()
    for path, record in out.items():
        for p in record["patches"]:
            va = int(p["offset"], 16) + 0x400000
            game = int(record["game_id"][2])
            assert stock(game, va, len(p["before"]) // 2).hex().upper() == p["before"], (path.name, p["offset"])
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    sys.exit(main())
