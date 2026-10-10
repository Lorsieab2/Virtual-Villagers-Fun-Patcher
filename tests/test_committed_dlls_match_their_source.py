"""Every committed companion DLL and its test build match the current source.

The behaviour companions ship a DLL without test hooks and commit a separate
test build (tests/test_dlls/*.test.dll) that the emulator tests drive. Both
are prebuilt binaries: editing the C source changes nothing until the build
script is re-run and both outputs are committed. Nothing else in the suite
notices when one of them is stale -- a merge that keeps the older binary
silently ships (or tests) code the source no longer contains.

This re-runs each build script in a throwaway copy of the project (its native
source folders, native/shared and the script itself), so nothing in this
checkout is written, and compares every DLL the script produces with the
committed file of the same relative path: the code, data and relocation
sections byte for byte, and read-only data with only the link timestamps and
debug-record identities masked (these builds are not /Brepro, so those change
on every link).

It is skipped where the MSVC toolchain the scripts name is not installed.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    "build_vv1_number_keys.ps1",
    "build_vv1_parentage_dll.ps1",
    "build_vv1_sort_by_dll.ps1",
    "build_vv1_watering_builds.ps1",
    "build_vvfp_fix_huts.ps1",
    "build_vvfp_golden_mushroom.ps1",
    "build_vvfp_healers_study.ps1",
    "build_vvfp_lesson_cap.ps1",
    "build_vvfp_pathfinding.ps1",
    "build_vvfp_startup.ps1",
    "build_vvfp_story_upgrades.ps1",
    "build_vvfp_storytelling.ps1",
    "build_vvfp_work_first.ps1",
)


def _toolchain_present(script: str) -> bool:
    text = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    m = re.search(r'\$vsTools = "([^"]+)"', text)
    return bool(m) and (Path(m.group(1)) / "bin" / "Hostx64" / "x86" / "cl.exe").exists()


def _native_dirs(script: str) -> set[str]:
    text = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    dirs = set(re.findall(r'native\\\\?([A-Za-z0-9_]+)', text))
    dirs.add("shared")
    return {d for d in dirs if (ROOT / "native" / d).is_dir()}


def _comparable(path: Path) -> dict[str, bytes]:
    data = path.read_bytes()         # not pefile.PE(path): that keeps the file mapped
    pe = pefile.PE(data=data)
    image = bytearray(data)

    def mask(offset: int, size: int) -> None:
        image[offset:offset + size] = b"\0" * size

    if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        mask(pe.DIRECTORY_ENTRY_EXPORT.struct.get_file_offset() + 4, 4)      # TimeDateStamp
    for entry in getattr(pe, "DIRECTORY_ENTRY_DEBUG", []):
        mask(entry.struct.get_file_offset() + 4, 4)                           # TimeDateStamp
        if entry.struct.PointerToRawData and entry.struct.SizeOfData:
            mask(entry.struct.PointerToRawData, entry.struct.SizeOfData)      # CodeView/POGO identity
    sections = {}
    for s in pe.sections:
        name = s.Name.rstrip(b"\0").decode("ascii", "replace")
        sections[name] = bytes(image[s.PointerToRawData:s.PointerToRawData + s.SizeOfRawData])
    return sections


class CommittedDllsMatchTheirSourceTests(unittest.TestCase):
    def test_each_build_script_reproduces_its_committed_dlls(self) -> None:
        ran = 0
        for script in SCRIPTS:
            if not _toolchain_present(script):
                continue
            with self.subTest(script=script), tempfile.TemporaryDirectory() as temp:
                project = Path(temp) / "project"
                (project / "scripts").mkdir(parents=True)
                shutil.copy2(ROOT / "scripts" / script, project / "scripts" / script)
                for d in _native_dirs(script):
                    shutil.copytree(ROOT / "native" / d, project / "native" / d)
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                     str(project / "scripts" / script)],
                    capture_output=True, text=True, cwd=project,
                )
                built = sorted(p for p in project.rglob("*.dll") if "native" not in p.parts)
                self.assertTrue(built, f"{script} built nothing: {result.stdout[-1500:]} {result.stderr[-1500:]}")
                for dll in built:
                    relative = dll.relative_to(project)
                    committed = ROOT / relative
                    self.assertTrue(committed.exists(), f"{relative} is built but not committed")
                    fresh, kept = _comparable(dll), _comparable(committed)
                    self.assertEqual(sorted(fresh), sorted(kept), f"{relative}: section list differs")
                    for name in fresh:
                        self.assertTrue(fresh[name] == kept[name],
                                         f"{relative}: section {name} differs from a fresh build of the "
                                         f"current source -- rebuild with scripts/{script} and commit it")
                ran += 1
        if not ran:
            self.skipTest("MSVC toolchain not installed")


if __name__ == "__main__":
    unittest.main()
