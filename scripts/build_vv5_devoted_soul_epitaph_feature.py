"""Generate data/vv5_devoted_soul_epitaph_feature.json (New Believers).

THE STOCK PICKER.  The Roster of the Dead writer (0x464C70) fills the grave
entry it has just claimed (0x5C bytes each at 0x5481A8) and, last, its
epitaph: char[0x20] at entry +0x38, terminated at +0x58.  The text is a
string-table entry, chosen by id:

    age under 0x168 (18)              0x310 / 0x311  child, rand(100) < 50 / >= 50
    three or more skills at 88+       0x312 "Esteemed Elder" (0xD3 "Retired
                                      Chief" when flag 0x10 is set and the
                                      villager's +0x1CFC is 0xD)
    otherwise by the grave's job, the index of the villager's highest skill
    (0x4755C0, -1 when every skill is 0) -- the job the grave's skill line
    names:
      0 Farmer     0x306 "Child of the Earth"     / 0x307 "Nature's Friend"
      1 Parent     0x30A "Parent, Teacher, Friend"/ 0x30B "Dedicated to Children"
      2 Doctor     0x30C "Guardian of Health"     / 0x30D "Dedicated to Others"
      3 Scientist  0x308 "Dedicated Student"      / 0x309 "Inspired Inventor"
      4 Builder    0x30E "Inspired Architect"     / 0x30F "Strong Arms, Big Heart"
      5 Devotee    0x305 "Respected Citizen" (eEulogyDefault), always
     -1 no skill   0x305 "Respected Citizen", always

    Every pair is rand(100) through the game's own rand (0x403660): the first
    under 50, the second at 50 or over.  The job is dispatched by
    `cmp eax, 4 / ja 0x464E19` and a five-entry jump table (0x464E5C); the
    Devotee (5) and the unskilled (-1) take the `ja` with ecx still holding
    0x305, the default.  So "Respected Citizen" is shared: the Devotee's and
    the unskilled adult's.

THE CHANGE.  The dispatch and its five cases (0x464D86..0x464E19, 147 bytes)
are recoded in place as one shared case driven by a six-byte table of each
job's first string id (low byte; the second is the next id), so the Devotee
gets a pair like every other job: the first under 50 stays "Respected
Citizen" (0x305), the second, at 50 or over, is "Devoted Soul" -- a string
the patch keeps in the same bytes, copied by the writer's own strncpy at
0x464E28 exactly as a table string is.  The unskilled adult still takes the
`ja` to 0x464E19 with 0x305, as stock.  Jobs 0..4 get the same id for the
same rand value as stock.  No code is added outside the routine and no
executable space is claimed; the rest of the 147 bytes is int3 filler.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "vv5_devoted_soul_epitaph_feature.json"

IMAGE_BASE = 0x400000          # .text is mapped 1:1 (file offset = VA - 0x400000)
START = 0x464D86               # mov eax, [esi+0x28]: the job dispatch
END = 0x464E19                 # push 0x20: the shared string fetch
COPY = 0x464E28                # push eax: the writer's strncpy(entry+0x38, text, 0x20)
RAND = 0x403660
DEVOTEE = 5
DEVOTED_SOUL = b"Devoted Soul\x00"
# Each job's first string id, low byte (0x300 + this); the second is +1.
FIRST_IDS = bytes([0x06, 0x0A, 0x0C, 0x08, 0x0E, 0x05])


def stock_block(exe: bytes) -> bytes:
    return exe[START - IMAGE_BASE:END - IMAGE_BASE]


def build_block() -> bytes:
    """The recoded 147 bytes: code, then the table, then the string."""
    code = bytearray()

    def here() -> int:
        return START + len(code)

    def rel32(target: int, length: int) -> bytes:
        return struct.pack("<i", target - (here() + length))

    code += bytes.fromhex("8B4628")                  # mov eax, [esi+0x28]      the grave's job
    code += bytes.fromhex("83F805")                  # cmp eax, 5
    code += bytes.fromhex("0F87") + rel32(END, 6)    # ja 0x464E19 (rel32)      -1: 0x305, as stock
    table_fix = len(code) + 3
    code += bytes.fromhex("0FB698") + b"\0\0\0\0"    # movzx ebx, byte [eax+table]
    code += bytes.fromhex("6A64")                    # push 0x64
    code += b"\xE8" + rel32(RAND, 5)                 # call rand                eax = 0..99
    code += bytes.fromhex("59")                      # pop ecx                  (the argument)
    code += bytes.fromhex("33C9")                    # xor ecx, ecx
    code += bytes.fromhex("83F832")                  # cmp eax, 0x32
    code += bytes.fromhex("0F9DC1")                  # setge cl                 0 / 1, as stock
    code += bytes.fromhex("83FB") + bytes([DEVOTEE])  # cmp ebx, 5               the Devotee's row
    jne_at = len(code)
    code += bytes.fromhex("7500")                    # jne pick
    jecxz_at = len(code)
    code += bytes.fromhex("E300")                    # jecxz pick               under 50: 0x305
    code += bytes.fromhex("6A20")                    # push 0x20                the strncpy limit
    string_fix = len(code) + 1
    code += b"\xB8\0\0\0\0"                          # mov eax, "Devoted Soul"
    code += b"\xE9" + rel32(COPY, 5)                 # jmp 0x464E28             strncpy(entry+0x38, eax, 0x20)
    pick = len(code)
    code += bytes.fromhex("8D8C1900030000")          # lea ecx, [ecx+ebx+0x300] the id
    code += b"\xE9" + rel32(END, 5)                  # jmp 0x464E19
    code[jne_at + 1] = pick - (jne_at + 2)
    code[jecxz_at + 1] = pick - (jecxz_at + 2)
    table = START + len(code)
    code += FIRST_IDS
    string = START + len(code)
    code += DEVOTED_SOUL
    struct.pack_into("<I", code, table_fix, table)
    struct.pack_into("<I", code, string_fix, string)
    size = END - START
    if len(code) > size:
        raise SystemExit("block overflows the routine: %d > %d" % (len(code), size))
    code += b"\xCC" * (size - len(code))
    return bytes(code)


DESCRIPTION = (
    "When a Devotee dies and is buried, the epitaph New Believers writes on the grave is chosen at random between "
    "\"Respected Citizen\" and \"Devoted Soul\", with equal chances. In the stock game every other job already gets one of "
    "two epitaphs on a coin flip (a Farmer is \"Child of the Earth\" or \"Nature's Friend\", and so on), but a Devotee was "
    "always \"Respected Citizen\", the game's default, which an adult with no skill at all also gets. A villager's job here "
    "is the one the grave names: their highest skill. Only Devotees change: the unskilled adult keeps \"Respected "
    "Citizen\", children and villagers with three or more master skills keep their own epitaphs, and every other job "
    "keeps its pair. The epitaph is stored in the grave like any other, so it is saved with the village, the player can "
    "still edit it, and the Deaths log records it."
)

STOCK_TEXT = "always \"Respected Citizen\""


def feature(block: bytes, before: bytes) -> dict:
    return {
        "id": "vv5_devoted_soul_epitaph",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": "Devoted Soul Epitaph",
        "description": DESCRIPTION,
        "output_tag": "Devoted Soul Epitaph",
        "behavior_changes": [
            "The Roster of the Dead writer (0x464C70) picks a buried Devotee's epitaph (grave job 5, Devotion the highest "
            "skill; an adult not taking the child or Esteemed Elder branch) as rand(100) through the game's own rand "
            "(0x403660): under 50 the stock \"Respected Citizen\" (string 0x305, eEulogyDefault), 50 or over \"Devoted "
            "Soul\" -- the same coin flip, on the same rand, that already gives every other job one of its two epitaphs. "
            "Was " + STOCK_TEXT + ".",
            "\"Devoted Soul\" (12 characters) is copied into the grave entry's epitaph, char[0x20] at entry +0x38, by the "
            "writer's own strncpy at 0x464E28, exactly as a string-table epitaph is; the entry is saved, shown and "
            "editable like any other.",
        ],
        "explicit_non_changes": [
            "The writer's job dispatch and its five cases (0x464D86..0x464E19, 147 bytes) are recoded in place as one "
            "case driven by a table of each job's first string id; the table and the \"Devoted Soul\" text live in the "
            "same bytes and the rest is int3 filler. No code is added outside the routine and no executable space is "
            "claimed; the five-entry jump table at 0x464E5C is left as it was, no longer used.",
            "Farmer, Parent, Doctor, Scientist and Builder get the same string id for the same rand value as stock; an "
            "adult with no skill (job -1) still gets \"Respected Citizen\" without a rand call, as stock; children "
            "(\"Curious and Playful\" / \"Loving and Special\"), three-or-more-master villagers (\"Esteemed Elder\", "
            "\"Retired Chief\") and every other field of the entry are unchanged.",
            "The grave dialog's epitaph editing is unchanged: a typed epitaph replaces the pick as in the stock game. The "
            "game's string table (Assets/sm.xml) is not changed.",
        ],
        "companion_files": [],
        "patches": [
            {
                "offset": "0x%X" % (START - IMAGE_BASE),
                "before": before.hex().upper(),
                "after": block.hex().upper(),
                "purpose": (
                    "the Roster of the Dead writer's epitaph pick by job (0x464D86..0x464E19): mov eax,[esi+0x28] / "
                    "cmp eax,5 / ja 0x464E19 (job -1 keeps 0x305) / movzx ebx, byte [eax+table] / push 0x64 / call rand "
                    "/ pop ecx / xor ecx,ecx / cmp eax,0x32 / setge cl / cmp ebx,5 / jne pick / jecxz pick / push 0x20 / "
                    "mov eax,\"Devoted Soul\" / jmp 0x464E28 (the writer's strncpy) / pick: lea ecx,[ecx+ebx+0x300] / "
                    "jmp 0x464E19; then the table 06 0A 0C 08 0E 05 (Farmer, Parent, Doctor, Scientist, Builder, "
                    "Devotee) and \"Devoted Soul\\0\"; int3 filler"
                ),
            }
        ],
    }


def main() -> None:
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    import vv_fun_patcher as patcher  # noqa: PLC0415
    build = next(b for b in patcher.load_builds() if b.id == "vv5")
    stock = (ROOT / "research" / "stock-executables" / build.input_name).read_bytes()
    record = feature(build_block(), stock_block(stock))
    OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
