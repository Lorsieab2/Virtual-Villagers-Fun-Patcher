from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "src"))
from transparency import PATCHER_VERSION as VERSION  # noqa: E402

NAME = f"Virtual-Villagers-Fun-Patcher-{VERSION}.zip"
FILES = [
    "README.md",
    "How to Use.txt",
    "Launch Virtual Villagers Fun Patcher.bat",
    "assets/Island.png",
    "assets/genealogy/backgrounds/sunset-over-the-sea.png",
    "assets/genealogy/backgrounds/palms-at-sunset.png",
    "assets/genealogy/backgrounds/island-in-the-sea.png",
    "assets/genealogy/backgrounds/city-in-the-mist.png",
    "assets/genealogy/backgrounds/blue-island.png",
    "assets/genealogy/backgrounds/mountains-and-sea.png",
    "assets/genealogy/backgrounds/tree-on-the-rocks.png",
    "assets/genealogy/backgrounds/parchment-in-bamboo.png",
    "assets/genealogy/backgrounds/mausoleum.png",
    "assets/genealogy/backgrounds/green-tree.png",
    "assets/genealogy/backgrounds/starry-night.png",
    "assets/origins/VVFP VV1 Origins Icons.dll",
    "assets/origins/VVFP VV2 Origins Icons.dll",
    "assets/origins/VVFP VV4 Origins Icons.dll",
    "assets/origins/mask_atlas.png",
    "assets/statistics/VVFP Statistics Export.dll",
    "assets/parentage/VVFP Parentage Export.dll",
    "assets/population/VVFP Population Export.dll",
    # The tribe-delete companion. The reset stub in each game resolves it by
    # name at runtime, so it has to be in the package or the sweep never runs.
    "assets/save_reset/VVFP Save Reset.dll",
    "assets/number_keys/VVFP VV1 Number Keys.dll",
    "assets/parentage/VVFP VV1 Parentage.dll",
    "assets/sort_by/VVFP VV1 Sort By.dll",
    "assets/sort_by/vvfp_sort_band.png",
    "assets/sort_by/vvfp_sort_radio.png",
    # Improved Pathfinding: one companion for A New Home and The Lost Children,
    # loaded by each game's Origins companion; no executable bytes.
    "assets/pathfinding/VVFP Improved Pathfinding.dll",
    "assets/watering/VVFP VV1 Watering Builds.dll",
    "assets/fix_huts/VVFP Fix Huts.dll",
    "assets/lesson_cap/VVFP Lesson Cap.dll",
    "assets/healers_study/VVFP Healers Study.dll",
    "assets/work_first/VVFP Work First.dll",
    "assets/golden_mushroom/VVFP Golden Mushroom.dll",
    "assets/golden_mushroom/golden_mushroom.png",
    # Villagers Have Last Names: one companion for all five games, started by
    # VVFP Startup.dll; no executable bytes.
    "assets/last_names/VVFP Last Names.dll",
    # Write Island Events Log: one companion for all five games, started by
    # VVFP Startup.dll; no executable bytes.
    "assets/island_events/VVFP Island Events.dll",
    # Story / Cheat Upgrades: one companion for all five games, loaded by each
    # game's Origins companion; no executable bytes.
    "assets/story_upgrades/VVFP Story Upgrades.dll",
    # Cause of Death: one companion for all five games, loaded by each game's
    # Origins companion; no executable bytes.
    "assets/cause_of_death/VVFP Cause of Death.dll",
    # Loads and arms every companion at game start (any build with a companion DLL).
    "assets/startup/VVFP Startup.dll",
    "data/builds.json",
    "data/vv1_origins_feature.json",
    "data/vv2_origins_feature.json",
    "data/vv3_origins_feature.json",
    "data/candidates/VVFP VV3 Safe Upgrades.dll",
    "data/vv4_origins_feature.json",
    "data/vv5_origins_feature.json",
    "data/candidates/vv5_post_prototype_overlay.json",
    "data/candidates/vv5_task9_native_actions_map.json",
    "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
    "assets/vv5_bighead_masks/bigheads_masks.png",
    "data/vv1_origins_village_wide_upgrades.json",
    "data/vv2_origins_village_wide_upgrades.json",
    "data/vv3_origins_village_wide_upgrades.json",
    "data/vv4_origins_village_wide_upgrades.json",
    "data/vv5_origins_village_wide_upgrades.json",
    "data/statistics_features.json",
    # The Family Tree Maker's traced portrait shapes (scripts/build_tree_shapes.py).
    "data/tree_shapes.json",
    "data/vv1_parentage_feature.json",
    "data/vv2_parentage_feature.json",
    "data/vv3_parentage_feature.json",
    "data/vv4_parentage_feature.json",
    "data/vv5_parentage_feature.json",
    "data/vv1_number_keys_feature.json",
    "data/vv1_show_parents_feature.json",
    "data/vv1_sort_by_feature.json",
    "data/vv1_improved_pathfinding_feature.json",
    "data/vv2_improved_pathfinding_feature.json",
    "data/vv1_watering_trains_building_feature.json",
    "data/vv1_misc_text_fixes_feature.json",
    "data/vv1_restore_missing_island_events_feature.json",
    "data/vv1_builders_fix_huts_feature.json",
    "data/vv2_builders_fix_huts_feature.json",
    "data/vv3_builders_fix_huts_feature.json",
    "data/vv4_builders_fix_huts_feature.json",
    "data/vv5_builders_fix_huts_feature.json",
    "data/vv1_school_lessons_cap_feature.json",
    "data/vv2_teaching_children_cap_feature.json",
    "data/vv3_chief_lessons_cap_feature.json",
    "data/vv1_healers_study_feature.json",
    "data/vv2_healers_study_feature.json",
    "data/vv1_work_first_feature.json",
    "data/vv2_work_first_feature.json",
    "data/vv3_work_first_feature.json",
    "data/vv4_work_first_feature.json",
    "data/vv5_work_first_feature.json",
    "data/vv2_numeric_keys_tip_feature.json",
    "data/vv2_restore_missing_island_events_feature.json",
    "data/vv5_playing_in_the_dirt_feature.json",
    "data/vv5_devoted_soul_epitaph_feature.json",
    "data/vv1_story_cheat_upgrades_feature.json",
    "data/vv2_story_cheat_upgrades_feature.json",
    "data/vv3_story_cheat_upgrades_feature.json",
    "data/vv4_story_cheat_upgrades_feature.json",
    "data/vv5_story_cheat_upgrades_feature.json",
    "data/vv1_story_cheat_upgrades_cost_tech_points_feature.json",
    "data/vv2_story_cheat_upgrades_cost_tech_points_feature.json",
    "data/vv3_story_cheat_upgrades_cost_tech_points_feature.json",
    "data/vv4_story_cheat_upgrades_cost_tech_points_feature.json",
    "data/vv5_story_cheat_upgrades_cost_tech_points_feature.json",
    "data/vv1_cause_of_death_feature.json",
    "data/vv2_cause_of_death_feature.json",
    "data/vv3_cause_of_death_feature.json",
    "data/vv4_cause_of_death_feature.json",
    "data/vv5_cause_of_death_feature.json",
    "data/vv1_last_names_feature.json",
    "data/vv2_last_names_feature.json",
    "data/vv3_last_names_feature.json",
    "data/vv4_last_names_feature.json",
    "data/vv5_last_names_feature.json",
    "data/vv1_island_events_feature.json",
    "data/vv2_island_events_feature.json",
    "data/vv3_island_events_feature.json",
    "data/vv4_island_events_feature.json",
    "data/vv5_island_events_feature.json",
    # 256 Villagers (Experimental): The Secret City, The Tree of Life and
    # New Believers.
    "data/vv3_population_256_feature.json",
    "data/vv4_population_256_feature.json",
    "data/vv5_population_256_feature.json",
    "data/expanded_atomic_writer_integration.json",
    "data/vv5_task9_native_actions.json",
    "docs/game-data-conventions.md",
    "docs/max-population-research.md",
    "docs/island-event-population-research.md",
    "docs/vv2-easier-healing-research.md",
    "docs/vv2-teaching-children-research.md",
    "docs/vv2-hospital-recovery-research.md",
    "docs/vv2-gong-coconuts-research.md",
    "docs/all-games-child-skill-ceilings-research.md",
    "docs/vv1-school-lessons-research.md",
    "docs/vv1-magic-fruit-mortality-research.md",
    "docs/vv1-max-tech-research.md",
    "docs/vv1-f6-clothing-research.md",
    "docs/vv1-builder-action-fixes-research.md",
    "docs/vv3-everyone-tries-on-robe.md",
    "docs/vv1-origins-exclusive-features-research.md",
    "docs/villager-breeding-overhaul-research.md",
    "docs/village-statistics-export-research.md",
    "docs/vv3-origins-exclusive-features-research.md",
    "docs/vv4-origins-exclusive-features-research.md",
    "docs/vv5-origins-exclusive-features-research.md",
    "docs/vv3-nature-honey-research.md",
    "docs/vv3-nature-mortality-research.md",
    "docs/vv4-golden-fish-scales-research.md",
    "docs/vv5-heathen-mommy-research.md",
    "docs/vv5-easier-devotee-research.md",
    "docs/vv5-statue-training-research.md",
    "docs/vv5-nursery-divisor-research.md",
    "docs/doubler-composition-audit.md",
    "docs/origins-village-wide-upgrades.md",
    "docs/origins-playtest-readiness.md",
    "docs/appearance-upgrades-requirements.md",
    "docs/origins-player-runtime-checklist.md",
    # Referenced by README's Barrel of Babies section for the occupancy-vs-
    # population reasoning and the delivery-time recheck. Without it the
    # shipped README links to a file the bundle does not contain -- the same
    # broken-link defect recorded on #55/#57.
    "docs/duplicate-purchase-guards.md",
    # Referenced by README's "known crash" section. A player reading that the
    # VV2 crash is still unconfirmed should be able to reach the measurements
    # behind that claim, including which crash sites also occur on the
    # unmodified executable and therefore cannot be ours.
    "docs/crash-dump-findings.md",
    "docs/transparency-log.md",
    "src/vv_fun_patcher.py",
    "src/vv_fun_patcher_gui.py",
    # The "Virtual Villagers Fun Patcher Files" folder; vv_fun_patcher imports
    # it at the top, so the patcher cannot start without it.
    "src/patcher_files.py",
    # Back Up Saves; the GUI imports it, so the patcher window cannot open
    # without it.
    "src/vv_save_backup.py",
    # Rename Tribe; the GUI imports it too.
    "src/vv_tribe_rename.py",
    # Check Saves & Logs and Repair Saves & Logs; the GUI imports it, and Check Saves & Logs runs
    # the read-only checker in the patcher's own process.
    "src/vv_log_tools.py",
    "src/vv_log_additions.py",
    # The Family Tree Maker and the Village Matchmaker; the GUI imports the window, which
    # imports the rest (vv_tree_editor_tools is the editor's canvas tools).
    "src/vv_genealogy.py",
    "src/vv_family_tree.py",
    "src/vv_gdiplus.py",
    "src/vv_genealogy_window.py",
    "src/vv_tree_editor_tools.py",
    "src/vv_last_names.py",
    "src/vv_number_names.py",
    "src/vv_cut_names.py",
    # The save folder's folder and file names, old and new: the Family Tree Maker finds its edits and
    # writes its reports through it, and Repair Saves & Logs moves older builds' folders with it.
    "src/vv_save_layout.py",
    # The "?" guides beside every feature; the GUI imports the module, and
    # the module reads the data file.
    "src/vv_how_to_use.py",
    "data/how_to_use.json",
    "scripts/vvfp_consistency_check.py",
    # README links to it from the Check Saves & Logs / Repair Saves & Logs section.
    "docs/first-load-cross-check.md",
    "src/transparency.py",
    "src/expanded_atomic_writer.py",
    "src/vv5_full_heal.py",
    "src/vv5_individual_transactions.py",
    "scripts/build_vv1_origins_feature.py",
    "scripts/build_vv1_birth_control_page.py",
    "scripts/build_vv2_origins_feature.py",
    "scripts/build_village_wide_origins_features.py",
    "scripts/generate_transparency_docs.py",
    "scripts/build_vv5_task9_native_actions.py",
    "scripts/build_vv5_appearance_sheets.py",
    "scripts/build_vv5_task9_origins_dll.ps1",
    "native/vv5_task9_origins/vv5_task9_origins.c",
    "native/vv5_task9_origins/vv5_task9_origins.def",
    "native/vv5_task9_origins/vv5_task9_origins.rc",
    "native/vv5_task9_origins/appearance/head_m_young.bmp",
    "native/vv5_task9_origins/appearance/head_m_old.bmp",
    "native/vv5_task9_origins/appearance/head_f_young.bmp",
    "native/vv5_task9_origins/appearance/head_f_old.bmp",
    "native/vv5_task9_origins/appearance/body_m.bmp",
    "native/vv5_task9_origins/appearance/body_f.bmp",
    "native/vv5_task9_origins/appearance/mask_preview.bmp",
    # Fun-patch companion assets (asset-swap patches). Without these the
    # patcher cannot apply the "Optional Text Changes" (VV4) or "Guardians
    # of Isola" (VV5) fun patches, nor restore them on removal.
    # The manifest itself must ship too, or the patch never loads (the loader
    # reads data/vv4_text_changes.json) and it silently never appears.
    "data/vv4_text_changes.json",
    "assets/text-changes/vv4-sm.xml",
    "assets/text-changes/vv4-sm-base.xml",
    # VV4 Heathen-mask assets, pinned by data/vv4_origins_feature.json's
    # companion_files. The render atlas (exact hand-aligned mask art) is
    # SDL-blitted by the DLL onto the render-target surface; the isolated sheet
    # feeds the Change Appearance chooser preview. Both are ADDED files (no
    # stock atlas is swapped), so no restore halves are needed.
    "assets/vv4_masks/vvfp_mask_atlas.png",
    "assets/vv4_masks/vvfp_bighead_mask_atlas.png",
    "assets/vv4_masks/vvfp_mask_preview.png",
    "assets/vv4_masks/vv2_mask_preview.bmp",
    "data/guardians_of_isola/new/Assets/sm.xml",
    "data/guardians_of_isola/base/Assets/sm.xml",
    "data/guardians_of_isola/new/Images/BlinkyEyes.png",
    "data/guardians_of_isola/base/Images/BlinkyEyes.png",
    "data/guardians_of_isola/new/Images/BlinkyEyesSm.png",
    "data/guardians_of_isola/base/Images/BlinkyEyesSm.png",
    "data/guardians_of_isola/new/Images/BuildingTotemStrip.png",
    "data/guardians_of_isola/base/Images/BuildingTotemStrip.png",
    "data/guardians_of_isola/new/Images/ChildrensTotemStrip.png",
    "data/guardians_of_isola/base/Images/ChildrensTotemStrip.png",
    "data/guardians_of_isola/new/Images/FoodTotemStrip.png",
    "data/guardians_of_isola/base/Images/FoodTotemStrip.png",
    "data/guardians_of_isola/new/Images/MedicineTotemStrip.png",
    "data/guardians_of_isola/base/Images/MedicineTotemStrip.png",
    "data/guardians_of_isola/new/Images/RainbowTotemStrip.png",
    "data/guardians_of_isola/base/Images/RainbowTotemStrip.png",
    "data/guardians_of_isola/new/Images/ResearchTotemStrip.png",
    "data/guardians_of_isola/base/Images/ResearchTotemStrip.png",
    "data/guardians_of_isola/new/Images/blinkEyesMaskStrip.png",
    "data/guardians_of_isola/base/Images/blinkEyesMaskStrip.png",
    "data/guardians_of_isola/new/Images/blinkEyesMaskStripSm.png",
    "data/guardians_of_isola/base/Images/blinkEyesMaskStripSm.png",
    "data/guardians_of_isola/new/Images/idol_states.png",
    "data/guardians_of_isola/base/Images/idol_states.png",
    "data/guardians_of_isola/new/Images/mainmenu.jpg",
    "data/guardians_of_isola/base/Images/mainmenu.jpg",
    # VV1 "Visual Mods" fun patch (asset-swap) companion + base-restore images.
    "data/vv1_visual_mods/new/Images/garden_restored.png",
    "data/vv1_visual_mods/base/Images/garden_restored.png",
    "data/vv1_visual_mods/new/Images/lagoon_restored.jpg",
    "data/vv1_visual_mods/base/Images/lagoon_restored.jpg",
    "data/vv1_visual_mods/new/Images/MapX1Y2.jpg",
    "data/vv1_visual_mods/base/Images/MapX1Y2.jpg",
    "data/vv1_visual_mods/new/Images/MapX2Y1.jpg",
    "data/vv1_visual_mods/base/Images/MapX2Y1.jpg",
]


def _assert_no_executable_members(members: list[str]) -> None:
    """Reject executable members before or after assembling the source ZIP."""
    executable_members = [
        member for member in members if member.casefold().endswith(".exe")
    ]
    if executable_members:
        raise RuntimeError(
            "source release archive cannot contain executable members: "
            + ", ".join(executable_members)
        )


SOURCE_NAME = f"Virtual-Villagers-Fun-Patcher-{VERSION}-source.zip"


def _refuse_dirty_tree() -> bool:
    """Raise if a tracked file has uncommitted changes; False if git is absent.

    Both archives depend on this: ``main`` calls it BEFORE writing anything,
    because the patcher ZIP is packed from the working tree. It used to be
    checked only inside ``_build_source_archive``, which ``main`` reaches after
    it has already published the patcher ZIP under its final release name --
    so a dirty tree exited 1 with "refusing to build" while leaving behind a
    release ZIP full of the uncommitted content, which reads as a valid
    artifact.

    Returns True when git reported a clean tree and False when git could not
    be asked (no source archive is possible then, and the patcher ZIP is still
    built, as before).
    """
    try:
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return False
    if dirty:
        raise RuntimeError(
            "refusing to build the release from a dirty tree -- the patcher "
            "archive is built from the working tree and the source archive from HEAD, so they "
            "would not match. Commit or stash first:\n" + dirty
        )
    return True


def _build_source_archive() -> dict | None:
    """Write the full tracked source tree beside the release archive.

    GitHub attaches "Source code (zip/tar.gz)" to a release automatically, but
    only once the tag exists -- a DRAFT release reports ``zipball_url: null``,
    so a draft handed to a playtester carries no source at all. Building it here
    means the source ships with every release regardless of draft state, from
    the exact commit the binaries were built from.

    ``git archive HEAD`` is used rather than walking the working tree, so the
    archive contains what is COMMITTED and nothing else: no build outputs, no
    scratch files, and none of the gitignored ``research/`` stock executables.
    The files force-added under ``research/`` (the mask and skin source art) are
    tracked, so they are included -- they are inputs the patcher's own build
    needs, not third-party binaries.

    A DIRTY tree is refused outright, because the two archives are built from
    different snapshots: ``main`` packs ``FILES`` out of the WORKING TREE while
    this packs HEAD. With an uncommitted tracked change the shipped source would
    not be the shipped binaries' source, and the sharpest case is the one this
    whole feature exists to prevent -- an uncommitted ``PATCHER_VERSION`` bump
    yields a patcher ZIP named for the new version beside a source ZIP whose
    contents are still the old one. Review caught this on #264.

    Only tracked files are consulted (``--untracked-files=no``): untracked
    scratch is invisible to both archives, so it cannot cause a mismatch and
    must not block a release.

    Returns None when git is unavailable rather than failing the release: the
    patcher archive is the deliverable, and a missing source zip should not
    block it.
    """
    if not _refuse_dirty_tree():
        return None
    target = OUTPUTS / SOURCE_NAME
    temp = OUTPUTS / (SOURCE_NAME + ".tmp")
    temp.unlink(missing_ok=True)
    try:
        subprocess.run(
            ["git", "archive", "--format=zip",
             f"--prefix=Virtual-Villagers-Fun-Patcher-{VERSION}-source/",
             "-o", str(temp), "HEAD"],
            cwd=ROOT, check=True, capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        temp.unlink(missing_ok=True)
        return None
    # Validate the TEMP file and only then publish it under the release name.
    # Checking after the replace defeated the gate it exists for: an archive
    # containing a prohibited executable would already be sitting in outputs/
    # under its final release filename when the assert raised, where it reads
    # as a valid artifact. Review caught this on #264. The temp file is removed
    # on rejection so a failed build leaves nothing behind at all.
    try:
        with zipfile.ZipFile(temp) as archive:
            members = archive.namelist()
            # The stock game executables must never ship. They live under the
            # gitignored research/ tree, so a committed-only archive cannot
            # contain them -- but assert it rather than trusting the ignore
            # rule to stay correct.
            _assert_no_executable_members(members)
            bad = archive.testzip()
            if bad:
                raise RuntimeError(f"source archive CRC failure: {bad}")
    except Exception:
        temp.unlink(missing_ok=True)
        # A rejected build must not leave an EARLIER build's archive sitting
        # under the release filename either. It would read as this build's
        # source while corresponding to different code -- the same "looks like a
        # valid artifact" failure the ordering fix above addresses, one build
        # removed.
        target.unlink(missing_ok=True)
        raise
    temp.replace(target)
    return {
        "file": target.name,
        "size": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest().upper(),
        "entries": len(members),
    }


def main() -> int:
    _assert_no_executable_members(FILES)
    # Refuse a dirty tree before anything is written: see _refuse_dirty_tree.
    _refuse_dirty_tree()
    OUTPUTS.mkdir(exist_ok=True)
    target = OUTPUTS / NAME
    temp = OUTPUTS / (NAME + ".tmp")
    # The manifest names this build's ZIP; a failed build must not leave an
    # older one behind describing a ZIP that is no longer there.
    manifest_path = OUTPUTS / f"{target.stem}.manifest.json"
    temp.unlink(missing_ok=True)
    # Validate the TEMP file and publish it only once it has passed, as the
    # source archive does; a rejected build removes both the temp file and any
    # earlier build still sitting under this release name.
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for relative in FILES:
                path = ROOT / relative
                archive.write(path, relative)
        with zipfile.ZipFile(temp) as archive:
            members = archive.namelist()
            _assert_no_executable_members(members)
            if sorted(members) != sorted(FILES):
                raise RuntimeError("release archive manifest mismatch")
            bad = archive.testzip()
            if bad:
                raise RuntimeError(f"release archive CRC failure: {bad}")
    except BaseException:
        temp.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise
    temp.replace(target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest().upper()
    manifest = {"file":target.name,"size":target.stat().st_size,"sha256":digest,"entries":FILES}
    try:
        source = _build_source_archive()
    except BaseException:
        # The tree was clean a moment ago; if it is not now, or the source
        # archive is rejected, do not leave the patcher ZIP looking released.
        target.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise
    if source is not None:
        manifest["source_archive"] = source
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="")
    print(json.dumps(manifest, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
