"""Generate four new kinds of exe patch rows:

  data/vv{1,2,3,5}_apprentice_graves_feature.json   "Children's Graves Say Apprentice" (default on)
  data/vv5_faith_loss_feature.json                  "Faith Loss is Doubled/Gains Halved" (default off)
  data/vv5_new_heathens_faith_feature.json          "New Heathens Get a Heathen's Faith" (default on)
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

STARVING AND SICK BELIEVERS MOSTLY DIE RATHER THAN LEAVE (part of the same row; the owner, 2026-11-08:
"villagers should preferentially die if their faith decrease-turn heathen is due to starvation or disease ... so
most starving villagers die / most sick people die instead of them all turning heathen"; then: decided once per
villager per crisis, 1 in 10).  A Heathen is skipped by the life tick (0x472CB7): it never eats, starves, falls
ill or loses health, so a believer the drift turns Heathen is out of reach of hunger and sickness.  The rule, per
villager: the first time a believer's Faith would reach 0 or less because of the food roll (under 10, or 10 to
250) or the sickness roll -- the drift's other changes alone would leave Faith above 0 -- it is decided once:
1 in 10 the believer becomes a Heathen as before; 9 in 10 the believer is marked to stay.  While marked, food and
sickness losses never take that believer below Faith 1 (other changes, "too few believers" included, apply as
stock); the mark clears at the first age unit with food above 250 and the believer not sick, so a later crisis
is decided afresh.  The marks are kept by the row's companion, "VVFP Faith Loss.dll" (native/vvfp_faith_loss), in
the save's own folder, by villager identity.

How: the routine keeps a count of the food and sickness losses in ebp, which it does not otherwise use (saved
and zeroed by an entry cave at 0x494F00; the three loss sites `or esi,-1` / `sub esi,1` become `dec esi; inc
ebp` -- esi is 0 at both food sites; the epilogue pops it), and its final FAITH_ADD (0x4681DB) goes through a
cave at 0x494F14 whose first instruction calls the rule (esi the sum, ebp the food and sickness losses, ebx the
record; it returns the sum to apply in esi).  The companion redirects that call to its own rule (the marks); the
call's own target, the cave's fallback at 0x494F28, is used only when the companion is not there: the same
decision made each time instead of once per crisis (1 in 10 converts, else Faith 1).

NEW HEATHENS GET A HEATHEN'S FAITH (the owner, 2026-11-08: "Once they turn heathen, have their faith randomly set
to the typical blue heathen threshold" and "Blue heathen ranges only. NOT CHIEF/ORANGE/RED ETC (READ THE MASK
TYPE!!!)").  The stock setter makes a believer at Faith 0 or less a Heathen (0x4669E0, which sets the role +0x1CFC
to 0) and stores the new Faith as it is -- 0 to -3 from the drift -- so a single preaching (+3 to +5) brings them
back at once, with Faith 55 (0x467FC7).  The mask a Heathen wears is not chosen by Faith: the draw 0x4728C6 takes
the role (+0x1CFC 12, 14-16 purple, 13 the Chief, the table 0x472B60), then the kind bytes +0x1CED (orange) and
+0x1CEE (red), and anything else is blue.  The game sets an ordinary Heathen's Faith once, when it makes them, and
never moves it (the life tick skips Heathens): a new village's Heathens are made at -1 (0x424AC0) and those still
at -1 are set to -38 - rand(30), -38 to -67 (0x471050..0x471099), but five blue ones (red and orange bytes 0,
0x470F01..0x470F11) set to -5, -9, -16, -23 and -30 (0x470F1F..0x471037); Barrel O' Babies! (heathens) -55 (push
-0x37 at 0x4152B0); the Heathen Doctor -14, the Masters -74, the Chief -94.  For the Faith drift's conversions only
(the setter called by FAITH_ADD called by the drift, by their return addresses), the call of 0x4669E0 at 0x467FDF
goes through a cave at 0x494F80 that clears the two kind bytes -- an ordinary blue-mask Heathen -- and draws the
Faith the game's way, -38 - rand(30).  Island events (The Spa, The Cracked Mask: -10) are unchanged.
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
NEW_HEATHEN_ID = "vv5_new_heathens_get_heathen_faith"
NEW_HEATHEN_NAME = "New Heathens Get a Heathen's Faith"
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

# Starving and sick believers mostly die rather than leave (see the top of this file).
DRIFT_ENTRY, DRIFT_TAIL, DRIFT_EPILOGUE = 0x468040, 0x4681DB, 0x4681E3
FAITH_ENTRY_CAVE, FAITH_TAIL_CAVE, FAITH_RULE_CAVE = 0x494F00, 0x494F14, 0x494F28
FAITH_STAY_ROLL, FAITH_STAY_CONVERTS = 10, 1        # decided once a crisis: a Heathen on rand(10) < 1
FAITH_COMPANION = "VVFP Faith Loss.dll"
FAITH_COMPANION_SOURCE = "assets/faith_loss/VVFP Faith Loss.dll"
# The three food and sickness loss sites: (va, stock, patched, purpose).  esi is 0 at both food sites (nothing has
# been added yet), so `dec esi` is the stock `or esi,-1`.
FAITH_LOSS_MARKS = (
    (0x46805E, "83CEFFEB40", "4E4590EB40",
     "food under 10, the roll hit: or esi,-1 -> dec esi; inc ebp (one food loss counted); the jmp is kept"),
    (0x46807E, "83CEFFEB20", "4E4590EB20",
     "food 10..250 (or under 10 when its first roll missed), the roll hit: or esi,-1 -> dec esi; inc ebp"),
    (0x4680BB, "83EE01", "4E4590", "a sick believer, the roll hit: sub esi,1 -> dec esi; inc ebp"),
)


def faith_entry_cave() -> bytes:
    return asm(f"""
        push ebx
        push esi
        push ebp
        xor esi,esi
        xor ebp,ebp
        cmp dword ptr [0x51d34c],0xa
        jmp {DRIFT_ENTRY + 11:#x}
        """, FAITH_ENTRY_CAVE)


def faith_tail_cave() -> bytes:
    """The drift's FAITH_ADD, through the rule: call the rule (the companion redirects this call), then
    FAITH_ADD(esi) and the epilogue."""
    return asm(f"""
        call {FAITH_RULE_CAVE:#x}
        push esi
        mov ecx,ebx
        call 0x468020
        jmp {DRIFT_EPILOGUE:#x}
        """, FAITH_TAIL_CAVE)


def faith_rule_cave() -> bytes:
    """The rule without the companion: a fall to 0 or less that the food or sickness losses (ebp) cause -- the
    other changes alone (esi + ebp) leave Faith above 0 -- is made on rand(10) < 1, else Faith is left at 1."""
    return asm(f"""
        test esi,esi
        jge done
        test ebp,ebp
        je done
        mov eax,dword ptr [ebx+0x1cf0]
        add eax,esi
        test eax,eax
        jg done
        add eax,ebp
        test eax,eax
        jle done
        push {FAITH_STAY_ROLL}
        call 0x403660
        add esp,4
        cmp eax,{FAITH_STAY_CONVERTS}
        jl done
        mov esi,1
        sub esi,dword ptr [ebx+0x1cf0]
    done:
        ret
        """, FAITH_RULE_CAVE)


def faith_stay_patches() -> list[dict]:
    entry, tail, rule = faith_entry_cave(), faith_tail_cave(), faith_rule_cave()
    assert FAITH_ENTRY_CAVE + len(entry) <= FAITH_TAIL_CAVE and FAITH_TAIL_CAVE + len(tail) <= FAITH_RULE_CAVE
    assert FAITH_RULE_CAVE + len(rule) <= NEW_HEATHEN_CAVE
    out = [
        patch(5, DRIFT_ENTRY, asm(f"jmp {FAITH_ENTRY_CAVE:#x}", DRIFT_ENTRY) + b"\x90" * 6,
              "the drift's entry (push ebx; push esi; xor esi,esi; cmp [food],10) -> jmp the entry cave 0x494F00, "
              "which also saves and zeroes ebp, the count of food and sickness losses"),
    ]
    out += [patch(5, va, bytes.fromhex(after), purpose, bytes.fromhex(before))
            for va, before, after, purpose in FAITH_LOSS_MARKS]
    out += [
        patch(5, DRIFT_TAIL, asm(f"jmp {FAITH_TAIL_CAVE:#x}", DRIFT_TAIL) + b"\x90" * 3,
              "the drift's FAITH_ADD (push esi; mov ecx,ebx; call 0x468020) -> jmp the tail cave 0x494F14"),
        patch(5, DRIFT_EPILOGUE, bytes.fromhex("5D5E5BC3"),
              "the drift's epilogue: pop esi; pop ebx; ret -> pop ebp; pop esi; pop ebx; ret (into the int3 "
              "padding after it)", bytes.fromhex("5E5BC3CC")),
        patch(5, FAITH_ENTRY_CAVE, entry,
              "the entry cave: push ebx; push esi; push ebp; esi = 0; ebp = 0; cmp [food],10; jmp back to 0x46804B",
              bytes(len(entry))),
        patch(5, FAITH_TAIL_CAVE, tail,
              "the tail cave: call the rule (0x494F28; VVFP Faith Loss.dll redirects this call to its per-villager "
              "rule), then FAITH_ADD(esi) and the epilogue", bytes(len(tail))),
        patch(5, FAITH_RULE_CAVE, rule,
              "the rule without the companion: a fall (esi < 0) that the food or sickness losses (ebp) take to 0 or "
              "less, the rest alone leaving Faith above 0, is made on rand(10) < 1; otherwise esi = 1 - Faith "
              "(the believer stays at Faith 1)", bytes(len(rule))),
    ]
    return out


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
        "as in the stock game at 0; a rise above 75 is still skipped 70% of the time. Starving and sick believers "
        "mostly die rather than leave: a Heathen never eats, starves or falls ill, so the first time low food or "
        "sickness would take a believer's Faith to 0, it is decided once for that believer: 1 in 10 becomes a "
        "Heathen; the other 9 in 10 stay believers, never pushed below Faith 1 by low food or sickness, and go on "
        "facing hunger and sickness as usual, so they can starve or die of illness. That lasts until the crisis is "
        "over for them (food above 250 and not sick); a later crisis is decided afresh. It is remembered through "
        "saving and loading, by the patch's own file in the save's folder. Too few believers takes Faith as before. "
        "Preaching, Spreading the Word, "
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
            "Starving and sick believers mostly die rather than leave, decided once per villager per crisis: the first "
            "time the drift's food losses (0x46805E, 0x46807E) or sickness loss (0x4680BB) would take a believer to "
            "Faith 0 or less -- its other changes alone leaving Faith above 0 -- VVFP Faith Loss.dll (at the tail "
            "cave's call 0x494F14, before the FAITH_ADD 0x4681DB) makes the fall on rand(10) < 1, else marks the "
            "villager; while marked, food and sickness losses never take them below Faith 1 (FAITH_ADD(1 - Faith) at "
            "most), and the life tick goes on with its hunger and sickness (0x472D66 on) as for any believer. The "
            "mark clears at the first age unit with food above 250 and the villager not sick.",
            "The marks are kept by villager identity (name, likes and dislikes) in <save folder>\\Virtual Villagers "
            "Fun Patcher\\Save <S>\\Data\\Faith Loss\\Believers Kept - Save <S>.dat, written when a mark is made "
            "or cleared and read for the slot the game loads (before its catch-up); only living believers are kept. "
            "Start Over deletes it with the save's folder.",
            "Without the companion the cave's own rule (0x494F28) decides each such fall alone: 1 in 10 converts, "
            "else Faith 1.",
        ],
        "explicit_non_changes": [
            "Thirteen immediates and branches inside the routine, its entry, three loss sites, its last call and its "
            "epilogue; three caves in the .text tail (0x494F00, 0x494F14, 0x494F28). The routine's rolls, their "
            "order and the Faith they move are the stock ones but for the 1-in-10 decision added after them. No "
            "save or villager-record byte is written.",
            "Starting Faith, preaching, Spreading the Word, the Heathen Doctor's cure, The Heathen "
            "Chief, the Hydroponic Farm, the Heathen Mommy's puzzle and island events are unchanged.",
        ],
        "companion_files": [{"source": FAITH_COMPANION_SOURCE, "destination": FAITH_COMPANION,
                             "sha256": file_sha256(ROOT / FAITH_COMPANION_SOURCE)}],
        "patches": [patch(5, va, bytes.fromhex(after), purpose, bytes.fromhex(before))
                    for va, before, after, purpose in FAITH_EDITS] + faith_stay_patches(),
        "runtime_detours": [{
            "va": f"0x{FAITH_TAIL_CAVE:X}",
            "stock_bytes": asm(f"call {FAITH_RULE_CAVE:#x}", FAITH_TAIL_CAVE).hex().upper(),
            "written_bytes": "E8XXXXXXXX",
            "routine": "the Faith drift's tail cave: its call of the rule goes to the companion's per-villager rule "
                       "(the marks)",
            "installed_by": f"{FAITH_COMPANION}, VvfpStartup (started by VVFP Startup.dll, second word)",
        }],
    }


def file_sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


# ---- New Heathens Get a Heathen's Faith ------------------------------------------------------------------------

NEW_HEATHEN_SITE = 0x467FDF                 # the setter's call of 0x4669E0 (to a Heathen)
NEW_HEATHEN_CAVE = 0x494F80
FAITH_ADD_RETURN = 0x468032                 # the setter's return into FAITH_ADD 0x468020
DRIFT_ADD_RETURN = 0x4681E3                 # FAITH_ADD's return into the drift (stock)
# ...and into Faith Loss's tail cave (call rule; push esi; mov ecx,ebx; call 0x468020 -> here).
FAITH_LOSS_ADD_RETURN = FAITH_TAIL_CAVE + 5 + 1 + 2 + 5
BLUE_FAITH_BASE, BLUE_FAITH_SPAN = -38, 30  # a new village's ordinary Heathens: -38 - rand(30) (0x471070..0x471099)
ORANGE, RED = 0x1CED, 0x1CEE                # the mask kind bytes the mask draw reads (0x4728EB, 0x472903)


def new_heathen_cave() -> bytes:
    """Called by the setter in place of 0x4669E0.  Only for the Faith drift's conversion -- the setter called by
    FAITH_ADD (its return 0x468032 at [esp+0xC]) called by the drift (FAITH_ADD's return at [esp+0x18]: 0x4681E3,
    or Faith Loss's tail cave) -- the new Heathen is made an ordinary blue-mask one (0x4669E0 already sets the
    role +0x1CFC to 0; the orange and red bytes are cleared) and the Faith the setter stores (esi) is drawn as the
    game draws an ordinary Heathen's: -38 - rand(30)."""
    return asm(f"""
        call 0x4669e0
        cmp dword ptr [esp+0xc],{FAITH_ADD_RETURN:#x}
        jne keep
        mov eax,dword ptr [esp+0x18]
        cmp eax,{DRIFT_ADD_RETURN:#x}
        je drift
        cmp eax,{FAITH_LOSS_ADD_RETURN:#x}
        jne keep
    drift:
        mov byte ptr [edi+{ORANGE:#x}],0
        mov byte ptr [edi+{RED:#x}],0
        push {BLUE_FAITH_SPAN}
        call 0x403660
        add esp,4
        mov esi,{BLUE_FAITH_BASE}
        sub esi,eax
    keep:
        ret
        """, NEW_HEATHEN_CAVE)


def new_heathen_feature() -> dict:
    cave = new_heathen_cave()
    low, high = BLUE_FAITH_BASE - (BLUE_FAITH_SPAN - 1), BLUE_FAITH_BASE
    description = (
        "In New Believers a believer whose Faith drifts down to 0 (low food, sickness, too few believers) becomes a "
        "Heathen with Faith 0 or just below it, so one preaching brought them straight back. Every ordinary "
        f"blue-mask Heathen the game makes has far less: a new village's get {low} to {high}, Barrel O' Babies' "
        "-55. With this patch a believer the Faith drift turns Heathen (with or without Faith Loss is "
        f"Doubled/Gains Halved) becomes an ordinary blue-mask Heathen with a random Faith from {low} to {high}, "
        "drawn exactly as the game draws a new village's ordinary Heathens, and needs as much preaching as any blue "
        "Heathen to be won back. A Heathen's Faith never moves on its own in New Believers, so this is the Faith "
        "they keep until preached to. The game's own message \"A villager has stopped believing in you!\" is still "
        "shown. Island events that make a Heathen (The Spa, The Cracked Mask, the Custom Island Event) keep their "
        "own Faith (-10).")
    return {
        "id": NEW_HEATHEN_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": NEW_HEATHEN_NAME,
        "description": description,
        "output_tag": "New Heathens Faith",
        "behavior_changes": [
            "The Faith setter 0x467F90: a believer whose new Faith is 0 or less becomes a Heathen (0x4669E0, called "
            "at 0x467FDF, as stock: the role +0x1CFC set to 0 at 0x4669F5, the bottom bar's eSayStoppedBelieving, "
            "string 0x48, at 0x4669EC). When the setter was called by FAITH_ADD 0x468020 for the Faith drift "
            "0x468040 (its return 0x4681E3, or Faith Loss's tail cave 0x494F21), the cave 0x494F80 also clears the "
            "orange and red mask bytes (+0x1CED, +0x1CEE) and sets the Faith to be stored to -38 - rand(30). Stock "
            "stored the drift's Faith as it was (0 to -3).",
            "The mask a Heathen wears is chosen by the game's draw 0x4728C6..0x472919 from the role +0x1CFC (12 and "
            "14-16 the purple Masters' and the Doctor's, 13 the Chief's, through the table 0x472B60) and then the "
            "kind bytes +0x1CED (orange, the chasers) and +0x1CEE (red, the scary ones); anything else is the blue "
            "mask. Faith plays no part in it. So a drift convert is made role 0 (0x4669E0's own) with neither kind "
            "byte: a blue-mask Heathen.",
            f"{low} to {high} is the ordinary Heathens' Faith: the new village's Heathens are made at -1 (the "
            "creator 0x46FD20's last argument at 0x424AC0's calls) and every one still at -1 is then set to -38 - "
            "rand(30) (0x471050..0x471099) -- but five blue ones, set to -5, -9, -16, -23 and -30 (0x470F1F.."
            "0x471037); Barrel O' Babies! (heathens) makes its at -55 (push -0x37 at 0x4152B0, stored by 0x46FC31). "
            "No Heathen's Faith drifts: the life tick skips Heathens (0x472CB7).",
        ],
        "explicit_non_changes": [
            "Only the Faith drift's conversions change. The Spa (0x415D02) and The Cracked Mask (0x416C51) keep "
            "their -10 and their villager's mask; the Custom Island Event's \"Becomes a Heathen\" (which calls "
            "0x4669E0 itself) and every Heathen the game makes are unchanged.",
            "Preaching, Spreading the Word and every conversion back to a believer (0x4668B0, Faith 55 below 5) are "
            "unchanged. One 5-byte call and one cave in the .text tail; no save byte is written.",
        ],
        "companion_files": [],
        "patches": [
            patch(5, NEW_HEATHEN_SITE, asm(f"call {NEW_HEATHEN_CAVE:#x}", NEW_HEATHEN_SITE),
                  "the setter's call of 0x4669E0 (to a Heathen) -> call the cave 0x494F80"),
            patch(5, NEW_HEATHEN_CAVE, cave,
                  "the cave: call 0x4669E0 (as stock); for the Faith drift's conversion (the setter's return "
                  "0x468032, FAITH_ADD's 0x4681E3 or 0x494F21) clear the orange and red mask bytes and set the Faith "
                  "the setter stores (esi) to -38 - rand(30); ret to 0x467FE4 (the clamp and store)",
                  bytes(len(cave))),
        ],
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
    out[ROOT / "data" / "vv5_new_heathens_faith_feature.json"] = new_heathen_feature()
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
