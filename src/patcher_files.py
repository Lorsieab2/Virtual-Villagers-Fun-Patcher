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

from pathlib import PurePosixPath, PureWindowsPath

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
    # The Super-Secret Golden Mushroom (A New Home, The Secret City, The Tree
    # of Life, New Believers): the game's sprite constructor is handed
    # "golden_mushroom.png" (vvfp_golden_mushroom.c).
    "Images/golden_mushroom.png": _GAME_IMAGE,
    # The Tree of Life's Origins mask atlases: the game's sprite constructor
    # formats "vvfp_mask_atlas%d%d.png" / "vvfp_bighead_mask_atlas%d%d.png"
    # and opens them from Images (vv4_origins_icons.c).
    "Images/vvfp_mask_atlas00.png": _GAME_IMAGE,
    "Images/vvfp_bighead_mask_atlas00.png": _GAME_IMAGE,
    # New Believers' big-head mask sheet: the game's own sprite table names it
    # (the Task9 page points the sheet's name at it).
    "Images/bigheads_masks.png": _GAME_IMAGE,
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
})

_IN_PLACE = {key.casefold() for key in GAME_READS_IN_PLACE}
_PATCHER_READS = {key.casefold() for key in PATCHER_READS}

PATCH_LOG_SUFFIX = ".patch-log.json"
TRANSPARENCY_FILENAME = "VVFP Transparency Log.txt"
TRANSPARENCY_RELATIVE_PATH = PurePosixPath(PATCHER_FILES_FOLDER) / TRANSPARENCY_FILENAME

# Windows' classic path limit. A companion the game cannot open by a path this
# long would never load, so the patcher refuses such an output folder rather
# than publish a build whose add-ons silently do not start.
MAX_PATH = 260


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


def patch_log_name(executable_name: str) -> str:
    """The patch log's file name for the executable named `executable_name`."""
    name = PurePosixPath(executable_name.replace("\\", "/")).name
    stem = name[:-4] if name.lower().endswith(".exe") else name
    return stem + PATCH_LOG_SUFFIX


def patch_log_relative_path(executable_name: str) -> PurePosixPath:
    """The patch log of the executable named `executable_name`."""
    return PurePosixPath(PATCHER_FILES_FOLDER) / patch_log_name(executable_name)
