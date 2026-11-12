"""Where the patcher's own files go in a patched game folder.

THE ONE RULE (owner, 2026-10-04): "can we put all the patcher dlls and files
into a folder 'Virtual Villagers Fun Patcher Files' to clean up the game
folders a bit? all 5 games". Every file the patcher adds -- every companion
DLL, "VVFP Startup.dll", the images and data only the companions read, the
patch log and the transparency log -- lives in

    <game folder>\\Virtual Villagers Fun Patcher Files\\

in all five games, every build (Modded, 256, Playtest) and every population
mode.

The only files that stay where they always were are the ones the GAME
ENGINE itself opens by its own path: a stock file the patcher replaces, and
a new image the game's own sprite loader reads from its Images folder by
name. Each is listed, with its reason, in GAME_READS_IN_PLACE. Every other
non-DLL file must be listed in PATCHER_READS, so a new asset is never placed
by accident: installed_relative_path refuses an unclassified one.

This module is the single Python source of that rule; vv_fun_patcher.py
(install, removal, overwrite ownership, the startup loader's path),
transparency.py (the two logs) and the GUI use it. The native companions use
native/shared/patcher_files.h, which holds the same folder name and loads
every companion by its full path with the wide API.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath

PATCHER_FILES_FOLDER = "Virtual Villagers Fun Patcher Files"

_GAME_IMAGE = "a new image the game's own sprite loader opens by name from its Images folder"
_REPLACED_IMAGE = "replaces a stock image, which the game opens from its Images folder"

# Files the game engine opens itself, so they stay where it reads them.
# Keyed by the manifest destination, forward slashes, compared casefolded.
GAME_READS_IN_PLACE: dict[str, str] = {
    # A New Home's Visual Mods: stock images replaced in place.
    "Images/garden_restored.png": _REPLACED_IMAGE,
    "Images/lagoon_restored.jpg": _REPLACED_IMAGE,
    "Images/MapX1Y2.jpg": _REPLACED_IMAGE,
    "Images/MapX2Y1.jpg": _REPLACED_IMAGE,
    # A New Home's Origins mask atlas: the game's sprite constructor is
    # handed the bare name "mask_atlas.png" (vv1_origins_icons.c).
    "Images/mask_atlas.png": _GAME_IMAGE,
    # A New Home's Sort By art: built through the game's sprite constructor
    # by bare name (vv1_sort_by.c).
    "Images/vvfp_sort_band.png": _GAME_IMAGE,
    "Images/vvfp_sort_radio.png": _GAME_IMAGE,
    # Scrolling Popups (A New Home, The Lost Children): The Secret City's
    # scrollbar pictures, built through the game's frame-strip constructor by
    # bare name (native/shared/scroll_popup.h, SP_BORROWED_ART).
    "Images/vvfp_scroll_up.png": _GAME_IMAGE,
    "Images/vvfp_scroll_down.png": _GAME_IMAGE,
    "Images/vvfp_scroll_track.png": _GAME_IMAGE,
    "Images/vvfp_scroll_knob.png": _GAME_IMAGE,
    # The Super-Secret Golden Mushroom (A New Home, The Secret City, The Tree
    # of Life, New Believers): the game's sprite constructor is handed
    # "golden_mushroom.png" (vvfp_golden_mushroom.c).
    "Images/golden_mushroom.png": _GAME_IMAGE,
    # A New Home's Grey Hair at 55: the game's sprite constructor is handed
    # "vvfp_grey_male_heads.png" / "vvfp_grey_female_heads.png" (vv1_grey_hair.c).
    "Images/vvfp_grey_male_heads.png": _GAME_IMAGE,
    "Images/vvfp_grey_female_heads.png": _GAME_IMAGE,
    # The Tree of Life's Origins mask atlases: the game's sprite constructor
    # formats "vvfp_mask_atlas%d%d.png" / "vvfp_bighead_mask_atlas%d%d.png"
    # and opens them from Images (vv4_origins_icons.c).
    "Images/vvfp_mask_atlas00.png": _GAME_IMAGE,
    "Images/vvfp_bighead_mask_atlas00.png": _GAME_IMAGE,
    # New Believers' big-head mask sheet: the game's own sprite table names it
    # (the Task9 page points the sheet's name at it).
    "Images/bigheads_masks.png": _GAME_IMAGE,
    # The Secret City's Fix Vanilla Bugs: the owner's hospital sheet with the
    # tables' legs fixed; the game's own sprite table names it (the row
    # renames the stock name "map_hospitalStates.png" in place).
    "Images/vvfp_hospitalFixed.png": _GAME_IMAGE,
    # New Believers' Fix Vanilla Bugs: the owner's redrawn Last Heathen hovel
    # cover; the game's own image table names it (the row renames the stock
    # name "hovel_cover.png" in place).
    "Images/vvfp_hovel.png": _GAME_IMAGE,
    # New Believers' Shrine to the Ancestors: the owner's cover with graves and
    # flowers; the game's own image table names it (the row points entry 0x1B's name at it).
    "Images/vvfp_respectful_hovel.png": _GAME_IMAGE,
    # The Tree of Life's Yellow Fruit Trees are No Longer Unlimited: the fruit
    # trees running out; the game's sprite constructor is handed
    # "vvfp_fruit_tree_0.png" .. "_5.png" (vvfp_vv4_fruit_supply.c).
    "Images/vvfp_fruit_tree_0.png": _GAME_IMAGE,
    "Images/vvfp_fruit_tree_1.png": _GAME_IMAGE,
    "Images/vvfp_fruit_tree_2.png": _GAME_IMAGE,
    "Images/vvfp_fruit_tree_3.png": _GAME_IMAGE,
    "Images/vvfp_fruit_tree_4.png": _GAME_IMAGE,
    "Images/vvfp_fruit_tree_5.png": _GAME_IMAGE,
    # The Tree of Life / New Believers text: the game's own string table.
    "Assets/sm.xml": "replaces the game's own string table, which the game opens from Assets\\",
    # New Believers' Guardians of Isola rewrite: stock art replaced in place.
    "Images/BlinkyEyes.png": _REPLACED_IMAGE,
    "Images/BlinkyEyesSm.png": _REPLACED_IMAGE,
    "Images/BuildingTotemStrip.png": _REPLACED_IMAGE,
    "Images/ChildrensTotemStrip.png": _REPLACED_IMAGE,
    "Images/FoodTotemStrip.png": _REPLACED_IMAGE,
    "Images/MedicineTotemStrip.png": _REPLACED_IMAGE,
    "Images/RainbowTotemStrip.png": _REPLACED_IMAGE,
    "Images/ResearchTotemStrip.png": _REPLACED_IMAGE,
    "Images/blinkEyesMaskStrip.png": _REPLACED_IMAGE,
    "Images/blinkEyesMaskStripSm.png": _REPLACED_IMAGE,
    "Images/idol_states.png": _REPLACED_IMAGE,
    "Images/mainmenu.jpg": _REPLACED_IMAGE,
}

# Files a COMPANION writes into the game folder at run time (never in a patch
# log or the catalog). Each is read by the game engine, so it is written
# where the game reads it; listed here so the documentation and the tests
# name every file the patcher can put outside its folder.
RUNTIME_GAME_FILES: dict[str, str] = {
    "Images/heathen_masks.png": (
        "The Lost Children's and The Secret City's Origins companions write the "
        "Heathen mask atlas there from their own resources; the game's sprite "
        "loader reads it from Images"
    ),
}

# Non-DLL files only the patcher's companions read: they go in the patcher's
# folder with the DLLs, opened by full path from the executable's own path.
PATCHER_READS: frozenset[str] = frozenset({
    # The Tree of Life's Change Appearance mask preview, drawn by the Origins
    # companion through GDI+ (vv4_origins_icons.c).
    "Images/vvfp_mask_preview.png",
    # The Tree of Life's Yellow Breadfruit Refills Partially Every Time: a flag file whose presence beside the
    # companions tells "VVFP VV4 Fruit Supply.dll" to refill at The Secret City's pace (vvfp_vv4_fruit_supply.c).
    "VVFP VV4 Fruit Partial Refill.txt",
    # Island Events Scale With Stored Food and Tech Points (A New Home, The Tree of Life, New Believers): a flag file
    # whose presence beside the companions tells "VVFP Island Events Scale.dll" to scale by the stored food and tech
    # points instead of the population (vvfp_island_events_scale.c).
    "VVFP Island Events Scale Stored.txt",
}) | frozenset(
    # The Unicode companions' bundled open fonts (assets/unicode_fonts), their licence texts and sources: loaded
    # privately by "VVFP Unicode Text.dll" / "VVFP Unicode Font.dll" from "Unicode Fonts\\" beside them.
    f"Unicode Fonts/{name}" for name in (
        "NotoSansCuneiform-Regular.otf", "NotoSerifTangut-Regular.otf", "unifont-18.0.01.otf",
        "unifont_upper-18.0.01.otf", "LastResortHE-Regular.ttf", "NotoSansCuneiform-OFL-1.1.txt",
        "NotoSerifTangut-OFL-1.1.txt", "Unifont-OFL-1.1.txt", "Unifont-GPL-2.0-COPYING.txt",
        "LastResort-OFL-1.1.txt", "SOURCES.json",
    )
) | frozenset(
    # The shared ICU word lists (assets/word_lists) and ICU's licence: read by the same companions from
    # "Word Lists\\" beside them where Windows has no icu.dll.
    f"Word Lists/{name}" for name in (
        "thaidict.txt", "laodict.txt", "khmerdict.txt", "burmesedict.txt", "ICU-LICENSE.txt",
    )
)

_IN_PLACE = {key.casefold() for key in GAME_READS_IN_PLACE}
_PATCHER_READS = {key.casefold() for key in PATCHER_READS}

# The patch log. Its name is short and the same in every build (the owner,
# 2026-11-09: "fix the path too long bug when trying to patch games"): the
# older name, "<executable name>.patch-log.json", repeated the long game
# title ("...\Virtual Villagers - The Tree of Life - Modded 256\Virtual
# Villagers Fun Patcher Files\Virtual Villagers - The Tree of Life - Modded
# 256.patch-log.json") and was the longest path in the build. Every reader
# also finds a log under the older name; a re-patch replaces it.
PATCH_LOG_FILENAME = "VVFP Patch Log.json"
PATCH_LOG_SUFFIX = ".patch-log.json"   # the older name's ending
TRANSPARENCY_FILENAME = "VVFP Transparency Log.txt"
TRANSPARENCY_RELATIVE_PATH = PurePosixPath(PATCHER_FILES_FOLDER) / TRANSPARENCY_FILENAME

# Windows' classic path limit: a path of at most MAX_PATH - 1 characters. The
# games are 32-bit programs that are not long-path aware, so Windows will not
# let them open a longer path even where long paths are switched on: a
# companion past it would never load, and a game file past it would never be
# read. The patcher refuses an output folder only for those files (the game's
# own); the files only the patcher reads and writes -- the two logs, the
# hidden staging, backup and recovery folders -- go through long_path, so
# their length never stops a patch.
MAX_PATH = 260

_LONG_PREFIX = "\\\\?\\"
_LONG_UNC_PREFIX = "\\\\?\\UNC\\"


def long_path(path: "str | os.PathLike[str]") -> Path:
    """`path` as Windows opens it at any length: absolute, with the "\\\\?\\"
    prefix ("\\\\?\\UNC\\server\\share\\..." for a network path). For the
    patcher's own reads and writes only -- never a path handed to a game or
    written into a log. Unchanged when already prefixed, and on other systems."""
    if os.name != "nt":
        return Path(path)
    text = os.fspath(path)
    if text.startswith(_LONG_PREFIX) or text.startswith("\\\\.\\"):
        return Path(text)
    text = os.path.abspath(text)
    if text.startswith("\\\\"):
        return Path(_LONG_UNC_PREFIX + text[2:])
    return Path(_LONG_PREFIX + text)


def plain_path(path: "str | os.PathLike[str]") -> Path:
    """`path` without long_path's prefix: the form shown to the player and
    written into the logs."""
    text = os.fspath(path)
    if text.startswith(_LONG_UNC_PREFIX):
        return Path("\\\\" + text[len(_LONG_UNC_PREFIX):])
    if text.startswith(_LONG_PREFIX):
        return Path(text[len(_LONG_PREFIX):])
    return Path(text)


def windows_length(path: "str | os.PathLike[str]") -> int:
    """The length Windows counts: UTF-16 units, so a character outside the
    BMP (an emoji) takes two where Python's len() counts one."""
    return len(os.fspath(path).encode("utf-16-le", "surrogatepass")) // 2


def normalized_destination(destination: str) -> str:
    """A manifest destination as forward-slash text, refusing escapes."""
    if not isinstance(destination, str) or not destination.strip():
        raise ValueError(f"Companion destination is empty: {destination!r}")
    text = destination.replace("\\", "/")
    windows = PureWindowsPath(destination)
    if windows.is_absolute() or windows.drive or text.startswith("/"):
        raise ValueError(f"Companion destination must be relative: {destination}")
    if any(part in ("", ".", "..") for part in text.split("/")):
        raise ValueError(f"Companion destination is not a plain relative path: {destination}")
    return text


def stays_in_place(destination: str) -> bool:
    """True for a file the game engine itself opens by its own path."""
    return normalized_destination(destination).casefold() in _IN_PLACE


def installed_relative_path(destination: str) -> PurePosixPath:
    """Where a companion item is written, relative to the game folder.

    Raises ValueError for a non-DLL file nobody has classified: a new asset
    must be placed deliberately, in the patcher's folder (a companion reads
    it) or in place (the game engine reads it).
    """
    text = normalized_destination(destination)
    key = text.casefold()
    if key in _IN_PLACE:
        return PurePosixPath(text)
    if key.endswith(".dll") or key in _PATCHER_READS:
        return PurePosixPath(PATCHER_FILES_FOLDER) / text
    raise ValueError(
        f"Companion file {destination} is not classified: add it to "
        "patcher_files.GAME_READS_IN_PLACE (the game opens it) or "
        "patcher_files.PATCHER_READS (a companion opens it)."
    )


def legacy_relative_path(destination: str) -> PurePosixPath:
    """Where a v1.35.58-or-earlier patcher wrote the same item: loose in the
    game folder, at the manifest destination itself."""
    return PurePosixPath(normalized_destination(destination))


def patch_log_name(executable_name: str = "") -> str:
    """The patch log's file name: the same in every build (PATCH_LOG_FILENAME)."""
    return PATCH_LOG_FILENAME


def legacy_patch_log_name(executable_name: str) -> str:
    """The name an older patcher gave the patch log of the executable named
    `executable_name`: "<executable name>.patch-log.json"."""
    name = PurePosixPath(executable_name.replace("\\", "/")).name
    stem = name[:-4] if name.lower().endswith(".exe") else name
    return stem + PATCH_LOG_SUFFIX


def patch_log_relative_path(executable_name: str = "") -> PurePosixPath:
    """The patch log, relative to the game folder."""
    return PurePosixPath(PATCHER_FILES_FOLDER) / PATCH_LOG_FILENAME


def is_patch_log_name(name: str) -> bool:
    """A file named as a patch log, by this patcher or an older one."""
    folded = name.casefold()
    return folded == PATCH_LOG_FILENAME.casefold() or folded.endswith(PATCH_LOG_SUFFIX)


def patch_log_candidates(executable: "str | os.PathLike[str]") -> list[Path]:
    """Where the patch log of `executable` may be, newest name first: the
    patcher's folder beside it, under this name and the older one."""
    exe = Path(executable)
    files = exe.parent / PATCHER_FILES_FOLDER
    return [files / PATCH_LOG_FILENAME, files / legacy_patch_log_name(exe.name)]
