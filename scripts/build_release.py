from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
VERSION = "v1.34.7-rc11"
NAME = f"Virtual-Villagers-Fun-Patcher-{VERSION}.zip"
FILES = [
    "README.md",
    "How to Use.txt",
    "Launch Virtual Villagers Fun Patcher.bat",
    "assets/Island.png",
    "assets/origins/VVFP Origins Icons.dll",
    "assets/statistics/VVFP Statistics Export.dll",
    "data/builds.json",
    "data/expanded_256.json",
    "data/vv1_origins_feature.json",
    "data/vv2_origins_feature.json",
    "data/vv3_origins_feature.json",
    "data/vv4_origins_feature.json",
    "data/vv5_origins_feature.json",
    "data/vv1_origins_village_wide_upgrades.json",
    "data/vv2_origins_village_wide_upgrades.json",
    "data/vv3_origins_village_wide_upgrades.json",
    "data/vv4_origins_village_wide_upgrades.json",
    "data/vv5_origins_village_wide_upgrades.json",
    "data/statistics_features.json",
    "docs/max-population-research.md",
    "docs/island-event-population-research.md",
    "docs/experimental-256-cap-research.md",
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
    "docs/transparency-log.md",
    "src/vv_fun_patcher.py",
    "src/vv_fun_patcher_gui.py",
    "src/transparency.py",
    "scripts/generate_transparency_docs.py",
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
