"""Generate the five "Builders Fix Huts When Idle" rows.

The owner: "When no building projects are present/available to be worked on
AND not all population huts are complete, then builders will fix huts to
increase their skill (just makes it able to be autonomously chosen; applies
during catch-up time and live playing)."

The behaviour lives in one companion, "VVFP Fix Huts.dll"
(native/vvfp_fix_huts), which detours each game's Building dispatcher at its
"nothing available" point -- see the source for the five sites.  How the
companion gets loaded differs:

  * A New Home, The Lost Children, The Tree of Life, New Believers: a
    companion that already runs every frame in that game (the Origins
    companion; New Believers' Task 9 companion) loads it by full path and
    calls VvfpFixHutsInstall(game), which verifies the stock bytes and writes
    the detour at run time.  Those rows patch no executable byte.
  * The Secret City has no such companion (its shared Origins DLL is not
    rebuilt from source), so its row carries a small executable-side stub:
    the dispatcher's empty-list test jumps to the stub, which resolves the
    companion's VvfpFixHutsDecide once (GetModuleHandleA / LoadLibraryA /
    GetProcAddress from the stock import table, the same shape the VV3
    parentage trampoline uses) and calls it; the stub lives in the reserved
    zero range of the page Origins appends (a composition overlay at
    0x6DF800, after the parentage overlay at 0x6DF400), with a standalone
    appended-section form that is never used because the row depends on
    Origins.

The DLL is pinned by SHA-256, so re-run this after every rebuild.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import keystone

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "fix_huts" / "VVFP Fix Huts.dll"
STOCK_VV3 = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"

DESCRIPTION = (
    "Builders fix huts when no building projects are present. When no building "
    "project is available to be worked on and not all population huts are "
    "complete, a builder with nothing to do examines and fixes one of the huts "
    "that already stands, the game's own \"Examining hut\" / \"Fixing hut\" job, "
    "which trains Building. It only makes that job able to be chosen "
    "autonomously; the job itself, its chance of a repair and its skill roll are "
    "the game's own. While not every population hut is built, a builder also "
    "does this regardless of the food supply: plentiful food no longer skips "
    "the builder's work attempt (A New Home, The Lost Children), and scarce "
    "food no longer sends the builder to farm or gather first (The Secret City, "
    "The Tree of Life, New Believers). Applies in live play and during catch-up. "
    "**Requires Enable Origins-Exclusive Features**, whose companion loads this "
    "one; without it the stock scheduler runs unchanged."
)

# The idle scheduler's food gates (see "Regardless of the food supply" in
# native/vvfp_fix_huts/vvfp_fix_huts.c).  VV3's is executable-side.
FOOD_RUNTIME = {
    "vv1": {"va": "0x448336", "stock_bytes": "81BDECA2000090010000" "7D2D",
            "routine": "the idle scheduler's 400-food gate (0x448220); installs only while Builder Action Fixes, which owns the same bytes, is off"},
    "vv2": {"va": "0x4619E9", "stock_bytes": "81B9A4EA02002C010000" "7D2D",
            "routine": "the idle scheduler's 300-food gate (0x461850)"},
    "vv4": {"va": "0x4659B0", "stock_bytes": "8B8E881B0000",
            "routine": "the idle scheduler's low-food path, after the pick (0x465840)"},
    "vv5": {"va": "0x46F271", "stock_bytes": "8B8E881B0000",
            "routine": "the idle scheduler's low-food path, after the pick (0x46F070)"},
}
FOOD_BEHAVIOR = (
    "While not every population hut is complete, a builder's work attempt no "
    "longer depends on the food supply: {how}. Every other villager, and every "
    "village whose huts are all built, keeps the stock food behaviour."
)
FOOD_HOW = {
    "vv1": "at 400 food or more a villager whose selected job is Building still gets the preferred-job attempt the stock game gives below 400",
    "vv2": "at 300 food or more a villager whose selected job is Building still gets the preferred-job attempt the stock game gives below 300",
    "vv3": "at 250 food or less a picked Building job is dispatched at once instead of waiting behind a farming attempt and a 50% swap for a food action",
    "vv4": "at 250 food or less a picked Building job is dispatched at once instead of waiting behind a farming attempt and a 50% swap for a food action",
    "vv5": "at 250 food or less a picked Building job is dispatched at once instead of waiting behind a farming attempt and a 50% swap for a food action",
}

RUNTIME = {
    "vv1": {"va": "0x447724", "stock_bytes": "6A64E8E5B7FBFF83C404",
            "routine": "the Building dispatcher's skip roll before the random hut (0x4472C0)"},
    "vv2": {"va": "0x46029D", "stock_bytes": "6A64E8FC2EFAFF83C404",
            "routine": "the Building dispatcher's skip roll before the random hut (0x45FBF0)"},
    "vv4": {"va": "0x463F8A", "stock_bytes": "3BFB0F8469010000",
            "routine": "the Building dispatcher's empty-option-list test (0x4639B0)"},
    "vv5": {"va": "0x46CADA", "stock_bytes": "3BFB0F8415030000",
            "routine": "the Building dispatcher's empty-option-list test (0x46C540)"},
}

# ---- The Secret City ------------------------------------------------------
VV3_SITE_VA = 0x45B39E
VV3_SITE_FILE = VV3_SITE_VA - 0x400000
VV3_SITE_STOCK = bytes.fromhex("3BFB0F849C030000")   # cmp edi, ebx; je 0x45B742
VV3_NOTHING = 0x45B742
VV3_RESUME = 0x45B3A6
VV3_STARTED = 0x45B5F0
VV3_LOAD_LIBRARY_IAT = 0x47C124
VV3_GET_MODULE_HANDLE_IAT = 0x47C074
VV3_GET_PROC_ADDRESS_IAT = 0x47C128
VV3_CACHE_SLOT = 0x6E0FF8          # .vv3md (R/W), unused by Origins and parentage
VV3_DLL_NAME = b"VVFP Fix Huts.dll\0"
VV3_EXPORT_NAME = b"VvfpFixHutsDecide\0"
VV3_NAME_OFFSET = 0x80
VV3_EXPORT_OFFSET = 0xA0

# "Regardless of the food supply": at 250 food or less The Secret City's idle
# scheduler makes the pick (ebx) wait behind a farming attempt and then,
# half the time, swaps it for a food action.  The farming test at 0x45C229
# (cmp [esi+0xEAC], 20; jl 0x45C244) jumps to a second stub, which asks the
# companion's VvfpFixHutsBuilderFirst(3, pick): a builder while not every
# population hut is complete goes straight to the stock dispatch-with-pick at
# 0x45C271; anything else replays the test.  With the DLL missing the stock
# test runs.
VV3_FOOD_SITE_VA = 0x45C229
VV3_FOOD_SITE_FILE = VV3_FOOD_SITE_VA - 0x400000
VV3_FOOD_SITE_STOCK = bytes.fromhex("83BEAC0E0000147C12")   # cmp [esi+0xEAC], 0x14; jl 0x45C244
VV3_FOOD_FARM = 0x45C232          # the jl not taken: try farming
VV3_FOOD_SKIP = 0x45C244          # the jl taken: skill below 20
VV3_FOOD_DISPATCH = 0x45C271      # push ebx; push esi; mov ecx, edi; call dispatcher
VV3_FOOD_CACHE_SLOT = 0x6E0FFC    # .vv3md; fix-huts 0x6E0FF8, lesson-cap 0x6E0FF4
VV3_FOOD_EXPORT_NAME = b"VvfpFixHutsBuilderFirst\0"
VV3_FOOD_EXPORT_OFFSET = 0xC0
VV3_FOOD_CODE_OFFSET = 0x100

# Origins' appended pages: .vv3mc (R-X) at 0x6DF000 / file 0xCB000, whose own
# content ends at 0x3A0; the parentage overlay takes 0x400..0x800; this one
# takes 0x800..0xC00.
VV3_OVERLAY_FILE = 0xCB800
VV3_OVERLAY_VA = 0x6DF800
VV3_OVERLAY_LENGTH = 0x400
VV3_ORIGINS_ID = "vv3_enable_origins_exclusive_features"

# The standalone form (never selected: the row depends on Origins), shaped like
# the parentage row's: an owned executable section at the stock EOF.
VV3_STOCK_FILE_SIZE = 0xCB000
VV3_PAGE_FILE = 0xCB000
VV3_PAGE_VA = 0x6DF000
VV3_PAGE_SIZE = 0x1000
VV3_SECTION_NAME = b".vv3fh\0\0"


def assemble(source: str, address: int) -> bytes:
    engine = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    encoding, _ = engine.asm(source, address)
    return bytes(encoding)


def vv3_build_page(base_va: int) -> bytes:
    """The stub, re-assembled for the address it will live at."""
    name_va = base_va + VV3_NAME_OFFSET
    export_va = base_va + VV3_EXPORT_OFFSET
    code = assemble(
        f"""
        cmp edi, ebx
        jne 0x{VV3_RESUME:X}
        pushad
        mov eax, dword ptr [0x{VV3_CACHE_SLOT:X}]
        cmp eax, 1
        ja call_it
        je give_up
        push 0x{name_va:X}
        call dword ptr [0x{VV3_GET_MODULE_HANDLE_IAT:X}]
        test eax, eax
        jne have_module
        push 0x{name_va:X}
        call dword ptr [0x{VV3_LOAD_LIBRARY_IAT:X}]
        test eax, eax
        je mark_failed
    have_module:
        push 0x{export_va:X}
        push eax
        call dword ptr [0x{VV3_GET_PROC_ADDRESS_IAT:X}]
        test eax, eax
        je mark_failed
        mov dword ptr [0x{VV3_CACHE_SLOT:X}], eax
    call_it:
        push esi
        push 3
        call eax
        add esp, 8
        test eax, eax
        popad
        je 0x{VV3_NOTHING:X}
        jmp 0x{VV3_STARTED:X}
    mark_failed:
        mov dword ptr [0x{VV3_CACHE_SLOT:X}], 1
    give_up:
        popad
        jmp 0x{VV3_NOTHING:X}
        """,
        base_va,
    )
    if len(code) > VV3_NAME_OFFSET:
        raise RuntimeError(f"the VV3 stub is {len(code):#x} bytes, past its string at {VV3_NAME_OFFSET:#x}")
    page = bytearray(VV3_PAGE_SIZE)
    page[: len(code)] = code
    page[VV3_NAME_OFFSET : VV3_NAME_OFFSET + len(VV3_DLL_NAME)] = VV3_DLL_NAME
    page[VV3_EXPORT_OFFSET : VV3_EXPORT_OFFSET + len(VV3_EXPORT_NAME)] = VV3_EXPORT_NAME
    food_va = base_va + VV3_FOOD_CODE_OFFSET
    food = assemble(
        f"""
        pushad
        mov eax, dword ptr [0x{VV3_FOOD_CACHE_SLOT:X}]
        cmp eax, 1
        ja call_it
        je give_up
        push 0x{name_va:X}
        call dword ptr [0x{VV3_GET_MODULE_HANDLE_IAT:X}]
        test eax, eax
        jne have_module
        push 0x{name_va:X}
        call dword ptr [0x{VV3_LOAD_LIBRARY_IAT:X}]
        test eax, eax
        je mark_failed
    have_module:
        push 0x{base_va + VV3_FOOD_EXPORT_OFFSET:X}
        push eax
        call dword ptr [0x{VV3_GET_PROC_ADDRESS_IAT:X}]
        test eax, eax
        je mark_failed
        mov dword ptr [0x{VV3_FOOD_CACHE_SLOT:X}], eax
    call_it:
        push ebx
        push 3
        call eax
        add esp, 8
        test eax, eax
        popad
        jne 0x{VV3_FOOD_DISPATCH:X}
        jmp stock
    mark_failed:
        mov dword ptr [0x{VV3_FOOD_CACHE_SLOT:X}], 1
    give_up:
        popad
    stock:
        cmp dword ptr [esi + 0xEAC], 0x14
        jl 0x{VV3_FOOD_SKIP:X}
        jmp 0x{VV3_FOOD_FARM:X}
        """,
        food_va,
    )
    page[VV3_FOOD_EXPORT_OFFSET : VV3_FOOD_EXPORT_OFFSET + len(VV3_FOOD_EXPORT_NAME)] = VV3_FOOD_EXPORT_NAME
    if VV3_FOOD_EXPORT_OFFSET + len(VV3_FOOD_EXPORT_NAME) > VV3_FOOD_CODE_OFFSET:
        raise RuntimeError("the food export name runs into the food stub")
    page[VV3_FOOD_CODE_OFFSET : VV3_FOOD_CODE_OFFSET + len(food)] = food
    if any(page[VV3_OVERLAY_LENGTH:]):
        raise RuntimeError("the VV3 stub must fit in the 0x400 overlay")
    return bytes(page)


def vv3_site_patch(page_va: int) -> dict:
    entry = b"\xE9" + int(page_va - (VV3_SITE_VA + 5)).to_bytes(4, "little", signed=True)
    entry += b"\x90" * (len(VV3_SITE_STOCK) - len(entry))
    return {
        "offset": f"0x{VV3_SITE_FILE:X}",
        "before": VV3_SITE_STOCK.hex().upper(),
        "after": entry.hex().upper(),
        "purpose": (
            "Divert the Building dispatcher's empty-option-list test (cmp edi, ebx; "
            "je nothing at 0x45B39E) into the fix-huts stub, which replays the test, "
            "asks the companion whether to fix a hut, and resumes at the stock "
            "'job started' or 'nothing' path."
        ),
    }


def vv3_food_site_patch(page_va: int) -> dict:
    target = page_va + VV3_FOOD_CODE_OFFSET
    entry = b"\xE9" + int(target - (VV3_FOOD_SITE_VA + 5)).to_bytes(4, "little", signed=True)
    entry += b"\x90" * (len(VV3_FOOD_SITE_STOCK) - len(entry))
    return {
        "offset": f"0x{VV3_FOOD_SITE_FILE:X}",
        "before": VV3_FOOD_SITE_STOCK.hex().upper(),
        "after": entry.hex().upper(),
        "purpose": (
            "Divert the idle scheduler's low-food farming test (cmp [esi+0xEAC], 20; "
            "jl at 0x45C229) into the food stub, which sends a builder straight to the "
            "stock dispatch-with-pick while not every population hut is complete, and "
            "otherwise replays the test."
        ),
    }


def vv3_section_header() -> bytes:
    header = bytearray(40)
    header[0:8] = VV3_SECTION_NAME
    header[8:12] = VV3_PAGE_SIZE.to_bytes(4, "little")
    header[12:16] = (VV3_PAGE_VA - 0x400000).to_bytes(4, "little")
    header[16:20] = VV3_PAGE_SIZE.to_bytes(4, "little")
    header[20:24] = VV3_PAGE_FILE.to_bytes(4, "little")
    header[36:40] = (0x60000020).to_bytes(4, "little")
    return bytes(header)


def vv3_transaction(stock: bytes) -> tuple[list[dict], dict, list[dict]]:
    if len(stock) != VV3_STOCK_FILE_SIZE:
        raise RuntimeError("stock VV3 size changed")
    if stock[VV3_SITE_FILE : VV3_SITE_FILE + len(VV3_SITE_STOCK)] != VV3_SITE_STOCK:
        raise RuntimeError("stock bytes at 0x45B39E are not the expected test")
    page = vv3_build_page(VV3_PAGE_VA)
    overlay_page = vv3_build_page(VV3_OVERLAY_VA)
    if stock[VV3_FOOD_SITE_FILE : VV3_FOOD_SITE_FILE + len(VV3_FOOD_SITE_STOCK)] != VV3_FOOD_SITE_STOCK:
        raise RuntimeError("stock bytes at 0x45C229 are not the expected farming test")
    patches = [vv3_site_patch(VV3_PAGE_VA), vv3_food_site_patch(VV3_PAGE_VA)]
    overlay_patches = [vv3_site_patch(VV3_OVERLAY_VA), vv3_food_site_patch(VV3_OVERLAY_VA)]
    layout = {
        "original_file_size": f"0x{VV3_STOCK_FILE_SIZE:X}",
        "append_offset": f"0x{VV3_PAGE_FILE:X}",
        "append_length": VV3_PAGE_SIZE,
        "append_bytes": page.hex().upper(),
        "page_virtual_address": f"0x{VV3_PAGE_VA:X}",
        "page_sha256": hashlib.sha256(page).hexdigest().upper(),
        "purpose": (
            "append the owned VV3 fix-huts stub page (the standalone form; the row "
            "depends on Origins, so in practice the stub overlays Origins' page)"
        ),
        "header_patches": [
            {"offset": "0x10E", "before": "0500", "after": "0600",
             "purpose": "add the owned .vv3fh executable section"},
            {"offset": "0x158", "before": "00F02D00", "after": "00002E00",
             "purpose": "extend SizeOfImage for the owned .vv3fh section"},
            {"offset": "0x2C8", "before": "00" * 40, "after": vv3_section_header().hex().upper(),
             "purpose": "write the owned .vv3fh section header"},
        ],
    }
    overlay = {
        "base_feature": VV3_ORIGINS_ID,
        "overlay_offset": f"0x{VV3_OVERLAY_FILE:X}",
        "overlay_length": VV3_OVERLAY_LENGTH,
        "page_virtual_address": f"0x{VV3_OVERLAY_VA:X}",
        "append_bytes": overlay_page.hex().upper(),
        "page_sha256": hashlib.sha256(overlay_page).hexdigest().upper(),
        "hook_patches": overlay_patches,
        "overlay_preimage": {
            "kind": "zero_fill",
            "length": VV3_OVERLAY_LENGTH,
            "sha256": hashlib.sha256(b"\x00" * VV3_OVERLAY_LENGTH).hexdigest().upper(),
        },
        "purpose": (
            "place the VV3 fix-huts stub in the reserved zero range of the executable "
            "section Origins appends, after the parentage overlay"
        ),
    }
    transaction = {
        "layouts": {mode: layout for mode in ("stock", "collection_progression", "immediate_fixed")},
        "composition_overlays": {VV3_ORIGINS_ID: overlay},
    }
    return patches, transaction, overlay_patches


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    common_non_changes = [
        "Nothing about the examine/fix job itself changes: its route, its 30% repair chance, its Building practice roll and its messages are the game's own.",
        "A builder with a project available still takes the project; in a village where every population hut is complete, or none is, the Building dispatcher's hut choice is the stock one (no hut to fix, or the stock fix-a-hut option). The food bypass applies whenever any population hut is unbuilt, and a village with every hut complete keeps the stock food behaviour.",
        "Nothing is written to a villager record, the save or any file.",
    ]
    for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
        manifest = {
            "id": f"{game}_builders_fix_huts",
            "enabled": True,
            "catalog_enabled": True,
            "catalog_hidden": False,
            "game_id": game,
            "name": "Builders Fix Huts When Idle",
            "description": DESCRIPTION,
            "output_tag": "Fix Huts",
            "dependencies": [f"{game}_enable_origins_exclusive_features"],
            "behavior_changes": [
                "When the Building dispatcher finds no project to work on (every project check has failed) and at least one population hut is complete while another is not, the companion picks a random complete hut and starts the game's own 'Examining hut' job for it, in live play and in catch-up alike.",
                FOOD_BEHAVIOR.format(how=FOOD_HOW[game]),
            ],
            "explicit_non_changes": list(common_non_changes),
            "companion_files": [
                {"source": "assets/fix_huts/VVFP Fix Huts.dll",
                 "destination": "VVFP Fix Huts.dll", "sha256": sha},
            ],
            "patches": [],
        }
        if game in RUNTIME:
            manifest["explicit_non_changes"].insert(0,
                "This row changes no executable bytes: a companion that already runs every frame loads the DLL, which detours the dispatcher at run time only after verifying the stock bytes; a different build of the game installs nothing.")
            manifest["runtime_detours"] = [
                {**RUNTIME[game], "installed_by": "VVFP Fix Huts.dll, VvfpFixHutsInstall"},
                {**FOOD_RUNTIME[game], "installed_by": "VVFP Fix Huts.dll, VvfpFixHutsInstall"},
            ]
        else:
            patches, transaction, _overlay_patches = vv3_transaction(STOCK_VV3.read_bytes())
            manifest["explicit_non_changes"].insert(0,
                "The Secret City's row diverts one eight-byte test in the Building dispatcher and one nine-byte test in the idle scheduler's low-food path into two stubs in the page Origins appends; each resolves the companion once and otherwise replays the stock test, so with the DLL missing the stock scheduler runs.")
            manifest["patches"] = patches
            manifest["pe_append_transaction"] = transaction
        out = ROOT / "data" / f"{game}_builders_fix_huts_feature.json"
        out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), sha)


if __name__ == "__main__":
    main()
