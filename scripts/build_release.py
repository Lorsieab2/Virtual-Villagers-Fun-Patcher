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
    "assets/origins/VVFP Origins Icons.dll",
    "assets/origins/VVFP VV1 Origins Icons.dll",
    "assets/origins/VVFP VV2 Origins Icons.dll",
    "assets/origins/VVFP VV4 Origins Icons.dll",
    "assets/origins/m1.png",
    "assets/origins/m2.png",
    "assets/origins/m3.png",
    "assets/origins/m4.png",
    "assets/origins/m5.png",
    "assets/origins/mask_atlas.png",
    "assets/statistics/VVFP Statistics Export.dll",
    "assets/parentage/VVFP Parentage Export.dll",
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
    "data/vv1_parentage_feature.json",
    "data/vv2_parentage_feature.json",
    "data/vv3_parentage_feature.json",
    "data/vv4_parentage_feature.json",
    "data/vv5_parentage_feature.json",
    "data/expanded_atomic_writer_integration.json",
    "data/vv5_task9_native_actions.json",
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
    "scripts/build_vv5_task9_origins_dll.ps1",
    "native/vv5_task9_origins/vv5_task9_origins.c",
    "native/vv5_task9_origins/vv5_task9_origins.def",
    "native/vv5_task9_origins/vv5_task9_origins.rc",
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
    try:
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if dirty:
        raise RuntimeError(
            "refusing to build a source archive from a dirty tree -- the patcher "
            "archive is built from the working tree and this from HEAD, so they "
            "would not match. Commit or stash first:\n" + dirty
        )
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
    OUTPUTS.mkdir(exist_ok=True)
    target = OUTPUTS / NAME
    temp = OUTPUTS / (NAME + ".tmp")
    temp.unlink(missing_ok=True)
    with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in FILES:
            path = ROOT / relative
            archive.write(path, relative)
    temp.replace(target)
    with zipfile.ZipFile(target) as archive:
        members = archive.namelist()
        _assert_no_executable_members(members)
        if sorted(members) != sorted(FILES):
            raise RuntimeError("release archive manifest mismatch")
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"release archive CRC failure: {bad}")
    digest = hashlib.sha256(target.read_bytes()).hexdigest().upper()
    manifest = {"file":target.name,"size":target.stat().st_size,"sha256":digest,"entries":FILES}
    source = _build_source_archive()
    if source is not None:
        manifest["source_archive"] = source
    (OUTPUTS / f"{target.stem}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="")
    print(json.dumps(manifest, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
