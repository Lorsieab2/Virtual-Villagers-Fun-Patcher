"""Generate the three "lessons stop at 50" rows.

The owner: "going to school (A New Home) / attending lessons (The Lost
Children) / the Tribal Chief lecturing children (The Secret City) limits
skill gain to exactly 50", picking only among the skills still below 50
(option b) -- and the ordinary lesson rows stay as they are (cap 100), with
these as SEPARATE rows on top of them.  All three live in one companion,
"VVFP Lesson Cap.dll" (native/vvfp_lesson_cap).  How it is reached differs:

  * A New Home, The Lost Children: the lesson rows' callback-127 caves are
    private code with no room left beside them (every free run in the .text
    slack is claimed), so the Origins companion, which already runs every
    frame, loads the DLL by full path and calls VvfpLessonCapInstall(game);
    that verifies the lesson row's own cave head and detours it at run time.
    Those rows patch no executable byte and require the lesson row AND
    Origins.
  * The Secret City: the award is the game's own callback 42, capped by the
    shared 100-cap helper; the game has no per-frame companion, so, exactly
    like Builders Fix Huts, the row carries a small executable-side stub in
    the page Origins appends: the case's first seven bytes (push 5; call
    RNG) jump to the stub, which resolves VvfpLessonCapAward once
    (GetModuleHandleA / LoadLibraryA / GetProcAddress from the stock import
    table, cached in .vv3md), calls it with the case's record, and returns
    through the case's own `pop esi; ret 8`.  With the DLL missing the stub
    replays the displaced bytes and the stock case runs (cap 100).  The stub
    takes the overlay range 0xC00..0x1000 of that page, after the parentage
    (0x400) and fix-huts (0x800) overlays.

The DLL is pinned by SHA-256, so re-run this after every rebuild.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import keystone

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from origins_base_text import ORIGINS_BASE_SENTENCE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "lesson_cap" / "VVFP Lesson Cap.dll"
STOCK_VV3 = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"

RULE = (
    "Each child who finishes {lesson} still gains 7 to 9 points in one random "
    "skill, but only a skill still below 50 can be chosen, and the gain stops at "
    "exactly 50; a skill already at 50 or above is never chosen and never "
    "lowered. When every skill is at 50 the lesson awards nothing. This matches "
    "the Nursery Schools of the later games, which skip any skill at 50. "
)
ROWS = {
    "vv1": {
        "id": "vv1_school_lessons_cap_50",
        "out": "vv1_school_lessons_cap_feature.json",
        "name": "School Lessons Stop at 50",
        "output_tag": "School Stops at 50",
        "lesson_row": "vv1_school_lessons_grant_skill",
        "description": RULE.format(lesson="the Going to school activity") + (
            "**Requires School Lessons Grant Skill** (the lesson it caps). "
            + ORIGINS_BASE_SENTENCE
            + " That base's companion loads this patch's DLL."),
        "va": "0x4566E0", "stock_bytes": "837C24087F753F608BF1",
        "routine": "School Lessons Grant Skill's callback-127 cave (its cmp [esp+8], 7Fh; jne; pushad; mov esi, ecx)",
    },
    "vv2": {
        "id": "vv2_teaching_children_cap_50",
        "out": "vv2_teaching_children_cap_feature.json",
        "name": "Teaching Children Stops at 50",
        "output_tag": "Teaching Stops at 50",
        "lesson_row": "vv2_teaching_children_grants_skill",
        "description": RULE.format(lesson="a Teaching Children lesson (Attending lessons)") + (
            "**Requires Teaching Children Grants Skill** (the lesson it caps). "
            + ORIGINS_BASE_SENTENCE
            + " That base's companion loads this patch's DLL."),
        "va": "0x473D80", "stock_bytes": "837C24087F753F608BF1",
        "routine": "the shared private callback dispatcher cave (Teaching Children's callback 127; Hospital Recovery's callback 126 stays the cave's own)",
    },
}
VV3_ID = "vv3_chief_lessons_cap_50"
VV3_OUT = ROOT / "data" / "vv3_chief_lessons_cap_feature.json"
VV3_DESCRIPTION = (
    "The Tribal Chief's lessons stop at 50. " + RULE.format(lesson="a lesson")
    + "The Secret City has no companion that runs every frame, so this row "
    "diverts the lesson award's first seven bytes into a small stub in the page "
    "Origins appends, which calls \"VVFP Lesson Cap.dll\"; if the DLL cannot "
    "be loaded, the stock lesson runs and trains to 100. " + ORIGINS_BASE_SENTENCE
)

# The callback-42 case (the Leadership-2 Tribal Chief's lesson award).
SITE_VA = 0x458F11
SITE_FILE = SITE_VA - 0x400000
SITE_STOCK = bytes.fromhex("6A05E8B8A3FAFF")        # push 5; call 0x4032D0
RESUME = 0x458F18                                    # add esp, 4; cmp eax, 4; ...
RNG = 0x4032D0
LOAD_LIBRARY_IAT = 0x47C124
GET_MODULE_HANDLE_IAT = 0x47C074
GET_PROC_ADDRESS_IAT = 0x47C128
CACHE_SLOT = 0x6E0FF4          # .vv3md (R/W); fix-huts uses 0x6E0FF8
DLL_NAME = b"VVFP Lesson Cap.dll\0"
EXPORT_NAME = b"VvfpLessonCapAward\0"
NAME_OFFSET = 0x80
EXPORT_OFFSET = 0xA0

# Origins' appended page .vv3mc (R-X) at 0x6DF000 / file 0xCB000: its own
# content ends at 0x3A0; parentage overlays 0x400..0x800, fix-huts
# 0x800..0xC00; this one takes 0xC00..0x1000.
OVERLAY_FILE = 0xCBC00
OVERLAY_VA = 0x6DFC00
OVERLAY_LENGTH = 0x400
ORIGINS_ID = "vv3_enable_origins_exclusive_features"

# The standalone form (never selected: the row depends on Origins), shaped
# like the fix-huts row's: an owned executable section at the stock EOF.
STOCK_FILE_SIZE = 0xCB000
PAGE_FILE = 0xCB000
PAGE_VA = 0x6DF000
PAGE_SIZE = 0x1000
SECTION_NAME = b".vv3lc\0\0"


def assemble(source: str, address: int) -> bytes:
    engine = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    encoding, _ = engine.asm(source, address)
    return bytes(encoding)


def build_page(base_va: int) -> bytes:
    """The stub, re-assembled for the address it will live at."""
    name_va = base_va + NAME_OFFSET
    export_va = base_va + EXPORT_OFFSET
    code = assemble(
        f"""
        pushad
        mov eax, dword ptr [0x{CACHE_SLOT:X}]
        cmp eax, 1
        ja call_it
        je give_up
        push 0x{name_va:X}
        call dword ptr [0x{GET_MODULE_HANDLE_IAT:X}]
        test eax, eax
        jne have_module
        push 0x{name_va:X}
        call dword ptr [0x{LOAD_LIBRARY_IAT:X}]
        test eax, eax
        je mark_failed
    have_module:
        push 0x{export_va:X}
        push eax
        call dword ptr [0x{GET_PROC_ADDRESS_IAT:X}]
        test eax, eax
        je mark_failed
        mov dword ptr [0x{CACHE_SLOT:X}], eax
    call_it:
        push dword ptr [esp + 0x28]
        push 3
        call eax
        add esp, 8
        popad
        pop esi
        ret 8
    mark_failed:
        mov dword ptr [0x{CACHE_SLOT:X}], 1
    give_up:
        popad
        push 5
        call 0x{RNG:X}
        jmp 0x{RESUME:X}
        """,
        base_va,
    )
    if len(code) > NAME_OFFSET:
        raise RuntimeError(f"the VV3 stub is {len(code):#x} bytes, past its string at {NAME_OFFSET:#x}")
    page = bytearray(PAGE_SIZE)
    page[: len(code)] = code
    page[NAME_OFFSET : NAME_OFFSET + len(DLL_NAME)] = DLL_NAME
    page[EXPORT_OFFSET : EXPORT_OFFSET + len(EXPORT_NAME)] = EXPORT_NAME
    if any(page[OVERLAY_LENGTH:]):
        raise RuntimeError("the VV3 stub must fit in the 0x400 overlay")
    return bytes(page)


def site_patch(page_va: int) -> dict:
    entry = b"\xE9" + int(page_va - (SITE_VA + 5)).to_bytes(4, "little", signed=True)
    entry += b"\x90" * (len(SITE_STOCK) - len(entry))
    return {
        "offset": f"0x{SITE_FILE:X}",
        "before": SITE_STOCK.hex().upper(),
        "after": entry.hex().upper(),
        "purpose": (
            "Divert the Tribal Chief lesson award (callback 42's `push 5; call RNG` "
            "at 0x458F11) into the lesson-cap stub, which asks the companion to "
            "award 7 to 9 points to one skill still below 50, stopping at 50, and "
            "returns through the case's own `pop esi; ret 8`; with the companion "
            "missing it replays the displaced bytes and resumes the stock case."
        ),
    }


def section_header() -> bytes:
    header = bytearray(40)
    header[0:8] = SECTION_NAME
    header[8:12] = PAGE_SIZE.to_bytes(4, "little")
    header[12:16] = (PAGE_VA - 0x400000).to_bytes(4, "little")
    header[16:20] = PAGE_SIZE.to_bytes(4, "little")
    header[20:24] = PAGE_FILE.to_bytes(4, "little")
    header[36:40] = (0x60000020).to_bytes(4, "little")
    return bytes(header)


def transaction(stock: bytes) -> tuple[list[dict], dict]:
    if len(stock) != STOCK_FILE_SIZE:
        raise RuntimeError("stock VV3 size changed")
    if stock[SITE_FILE : SITE_FILE + len(SITE_STOCK)] != SITE_STOCK:
        raise RuntimeError("stock bytes at 0x458F11 are not the expected push 5; call RNG")
    page = build_page(PAGE_VA)
    overlay_page = build_page(OVERLAY_VA)
    layout = {
        "original_file_size": f"0x{STOCK_FILE_SIZE:X}",
        "append_offset": f"0x{PAGE_FILE:X}",
        "append_length": PAGE_SIZE,
        "append_bytes": page.hex().upper(),
        "page_virtual_address": f"0x{PAGE_VA:X}",
        "page_sha256": hashlib.sha256(page).hexdigest().upper(),
        "purpose": (
            "append the owned VV3 lesson-cap stub page (the standalone form; the row "
            "depends on Origins, so in practice the stub overlays Origins' page)"
        ),
        "header_patches": [
            {"offset": "0x10E", "before": "0500", "after": "0600",
             "purpose": "add the owned .vv3lc executable section"},
            {"offset": "0x158", "before": "00F02D00", "after": "00002E00",
             "purpose": "extend SizeOfImage for the owned .vv3lc section"},
            {"offset": "0x2C8", "before": "00" * 40, "after": section_header().hex().upper(),
             "purpose": "write the owned .vv3lc section header"},
        ],
    }
    overlay = {
        "base_feature": ORIGINS_ID,
        "overlay_offset": f"0x{OVERLAY_FILE:X}",
        "overlay_length": OVERLAY_LENGTH,
        "page_virtual_address": f"0x{OVERLAY_VA:X}",
        "append_bytes": overlay_page.hex().upper(),
        "page_sha256": hashlib.sha256(overlay_page).hexdigest().upper(),
        "hook_patches": [site_patch(OVERLAY_VA)],
        "overlay_preimage": {
            "kind": "zero_fill",
            "length": OVERLAY_LENGTH,
            "sha256": hashlib.sha256(b"\x00" * OVERLAY_LENGTH).hexdigest().upper(),
        },
        "purpose": (
            "place the VV3 lesson-cap stub in the reserved zero range of the executable "
            "section Origins appends, after the fix-huts overlay"
        ),
    }
    return [site_patch(PAGE_VA)], {
        "layouts": {mode: layout for mode in ("stock", "collection_progression", "immediate_fixed")},
        "composition_overlays": {ORIGINS_ID: overlay},
    }


COMMON_NON_CHANGES = [
    "A skill at or above 50 is never lowered; work-task training past 50 is untouched.",
    "The lesson itself -- who teaches, who attends, its length, its animation and its messages -- is the game's own; only the award at its end changes.",
    "Nothing is written to a villager record beyond the skill the lesson would have written, nor to the save or any file.",
]


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    companion = [{"source": "assets/lesson_cap/VVFP Lesson Cap.dll",
                  "destination": "VVFP Lesson Cap.dll", "sha256": sha}]
    for game, row in ROWS.items():
        manifest = {
            "id": row["id"],
            "enabled": True,
            "catalog_enabled": True,
            "catalog_hidden": False,
            "game_id": game,
            "name": row["name"],
            "description": row["description"],
            "output_tag": row["output_tag"],
            "dependencies": [row["lesson_row"], f"{game}_enable_origins_exclusive_features"],
            "behavior_changes": [
                "When the lesson's completion callback 127 runs, the companion counts the child's skills below 50, asks the game's own RNG for one of them and for the stock 7 to 9 points, adds them and stops at exactly 50. With every skill at 50 or above the lesson awards nothing.",
            ],
            "explicit_non_changes": [
                "This row changes no executable bytes: the Origins companion loads the DLL, which detours the lesson row's own callback cave at run time only after verifying its bytes; the lesson row not applied, or a different build, installs nothing.",
            ] + COMMON_NON_CHANGES,
            "companion_files": list(companion),
            "patches": [],
            "runtime_detours": [{
                "va": row["va"], "stock_bytes": row["stock_bytes"], "routine": row["routine"],
                "installed_by": "VVFP Lesson Cap.dll, VvfpLessonCapInstall"}],
        }
        out = ROOT / "data" / row["out"]
        out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), sha)

    patches, pe_transaction = transaction(STOCK_VV3.read_bytes())
    manifest = {
        "id": VV3_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv3",
        "name": "Tribal Chief Lessons Stop at 50",
        "description": VV3_DESCRIPTION,
        "output_tag": "Lessons Stop at 50",
        "dependencies": [ORIGINS_ID],
        "behavior_changes": [
            "When a child finishes a Tribal Chief lesson (callback 42), the companion counts the skills below 50, asks the game's own RNG for one of them and for the stock 7 to 9 points, adds them and stops at exactly 50. With every skill at 50 or above the lesson awards nothing.",
        ],
        "explicit_non_changes": [
            "This row diverts one seven-byte instruction pair in the lesson award into a stub in the page Origins appends; the stub resolves the companion once and otherwise replays the stock bytes, so with the DLL missing the stock lesson runs (capped at 100).",
        ] + COMMON_NON_CHANGES,
        "companion_files": list(companion),
        "patches": patches,
        "pe_append_transaction": pe_transaction,
    }
    VV3_OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", VV3_OUT.relative_to(ROOT), sha)


if __name__ == "__main__":
    main()
