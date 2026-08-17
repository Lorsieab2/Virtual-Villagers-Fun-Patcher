from __future__ import annotations

import hashlib
import json
import shutil
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
    "assets/statistics/VVFP Statistics Export.dll",
    "data/builds.json",
    "data/expanded_256.json",
    "data/vv1_origins_feature.json",
    "data/vv2_origins_feature.json",
    "data/vv3_origins_feature.json",
    "data/candidates/VVFP VV3 Safe Upgrades.dll",
    "data/vv4_origins_feature.json",
    "data/vv5_origins_feature.json",
    "data/candidates/vv5_post_prototype_overlay.json",
    "data/candidates/vv5_task9_native_actions_map.json",
    "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
    "data/vv1_origins_village_wide_upgrades.json",
    "data/vv2_origins_village_wide_upgrades.json",
    "data/vv3_origins_village_wide_upgrades.json",
    "data/vv4_origins_village_wide_upgrades.json",
    "data/vv5_origins_village_wide_upgrades.json",
    "data/statistics_features.json",
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

def main() -> int:
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
        if sorted(archive.namelist()) != sorted(FILES):
            raise RuntimeError("release archive manifest mismatch")
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"release archive CRC failure: {bad}")
    digest = hashlib.sha256(target.read_bytes()).hexdigest().upper()
    manifest = {"file":target.name,"size":target.stat().st_size,"sha256":digest,"entries":FILES}
    (OUTPUTS / f"{target.stem}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
