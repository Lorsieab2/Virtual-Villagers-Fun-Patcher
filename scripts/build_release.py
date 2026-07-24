from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
VERSION = "v1.23.0"
NAME = f"Virtual-Villagers-Fun-Patcher-{VERSION}.zip"
FILES = [
    "README.md",
    "How to Use.txt",
    "Launch Virtual Villagers Fun Patcher.bat",
    "assets/Island.png",
    "data/builds.json",
    "data/expanded_256.json",
    "docs/max-population-research.md",
    "docs/island-event-population-research.md",
    "docs/experimental-256-cap-research.md",
    "docs/vv2-easier-healing-research.md",
    "docs/vv2-teaching-children-research.md",
    "docs/vv1-school-lessons-research.md",
    "docs/vv1-max-tech-research.md",
    "docs/vv1-f6-clothing-research.md",
    "docs/vv3-nature-honey-research.md",
    "docs/vv4-golden-fish-scales-research.md",
    "docs/vv5-heathen-mommy-research.md",
    "docs/vv5-easier-devotee-research.md",
    "docs/vv5-statue-training-research.md",
    "docs/vv5-nursery-divisor-research.md",
    "src/vv_fun_patcher.py",
    "src/vv_fun_patcher_gui.py",
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
