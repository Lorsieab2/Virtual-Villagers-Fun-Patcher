"""Every build script that links a DLL makes the same bytes every time (all five games' companions).

The companions' build scripts used to link without /Brepro, so each build stamped the link time and a
fresh debug-record identity into the DLL: two builds of one source were two different files, a
rebuild changed every pinned SHA-256 (the five games' feature files pin one per companion) even when
no code moved, and "does the committed DLL match its source" could only be answered by masking those
fields out.  Every script now links with /Brepro (the timestamp becomes a hash of the image) and no
build option embeds a path or a date (no /DEBUG, no __DATE__ / __TIME__ / __FILE__ in the sources).

This builds each script that links a DLL twice, in two throwaway copies of the project under
different folders (so a folder name in the file shows), and compares every DLL the two builds made
byte for byte; and compares the first build with the committed file of the same relative path for the
scripts whose outputs are committed.  It is skipped where the MSVC toolchain the scripts name is not
installed.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"


def _text(script: Path) -> str:
    return script.read_text(encoding="utf-8")


def dll_scripts() -> list[Path]:
    """Every build script that links a DLL (a harness links an executable and is not shipped)."""
    out = []
    for script in sorted(SCRIPTS_DIR.glob("build_*.ps1")):
        text = _text(script)
        if "harness" in script.name or "$vsTools" not in text:
            continue
        if re.search(r"\.dll\b", text) and re.search(r"/link\b", text):
            out.append(script)
    return out


def toolchain_present(script: Path) -> bool:
    m = re.search(r'\$vsTools = "([^"]+)"', _text(script))
    return bool(m) and (Path(m.group(1)) / "bin" / "Hostx64" / "x86" / "cl.exe").exists()


def native_dirs(script: Path) -> set[str]:
    dirs = set(re.findall(r"native\\\\?([A-Za-z0-9_]+)", _text(script)))
    dirs.add("shared")
    return {d for d in dirs if (ROOT / "native" / d).is_dir()}


def build_copy(script: Path, parent: Path) -> dict[Path, str]:
    """Run `script` in a throwaway copy of the project under `parent`; the SHA-256 of every DLL it
    made, by path relative to the project."""
    project = parent / "project"
    (project / "scripts").mkdir(parents=True)
    shutil.copy2(script, project / "scripts" / script.name)
    for d in native_dirs(script):
        shutil.copytree(ROOT / "native" / d, project / "native" / d)
    # A script may read prebuilt inputs from the project (resources, assets other scripts made).
    for need in re.findall(r'Join-Path \$projectRoot "((?:assets|data|inputs)[^"]*)"', _text(script)):
        source = ROOT / need
        # (never a committed DLL: that is what the build is compared with, not an input of it)
        if source.is_file() and source.suffix.lower() != ".dll":
            (project / need).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, project / need)
        elif source.is_dir() and not (project / need).exists():
            shutil.copytree(source, project / need, ignore=shutil.ignore_patterns("*.dll"))
    # The resource scripts name icons under assets/ ("../../assets/origins/101-time-warp.ico").
    for rc in sorted((project / "native").rglob("*.rc")):
        for icon in re.findall(r'"\.\./\.\./(assets/[^"]+)"', rc.read_text(encoding="utf-8", errors="replace")):
            if (ROOT / icon).is_file() and not (project / icon).exists():
                (project / icon).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / icon, project / icon)
    (project / "data" / "candidates").mkdir(parents=True, exist_ok=True)     # where the candidates are built
    # A script may run a helper of the scripts folder after it compiles (the VV3 companion's sync).
    for helper in re.findall(r'Join-Path \$projectRoot "scripts\\([A-Za-z0-9_]+\.py)"', _text(script)):
        if (SCRIPTS_DIR / helper).is_file():
            shutil.copy2(SCRIPTS_DIR / helper, project / "scripts" / helper)

    def dlls() -> dict[Path, str]:
        return {p.relative_to(project): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(project.rglob("*.dll"))}

    given = dlls()
    run = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                          str(project / "scripts" / script.name)],
                         capture_output=True, text=True, cwd=project, check=False)
    if run.returncode != 0:
        # A script that wrote a first DLL and failed on a later one must not pass on partial output.
        raise RuntimeError(f"{script.name} failed (exit {run.returncode}):\n"
                           f"--- stdout ---\n{run.stdout[-3000:]}\n--- stderr ---\n{run.stderr[-3000:]}")
    return {p: h for p, h in dlls().items() if given.get(p) != h}


class SourceTests(unittest.TestCase):
    def test_every_dll_script_links_with_brepro(self) -> None:
        scripts = dll_scripts()
        self.assertGreater(len(scripts), 25, "the discovery found the companions' scripts")
        for script in scripts:
            with self.subTest(script=script.name):
                self.assertIn("/Brepro", _text(script), "a link without /Brepro stamps the time into the DLL")
                self.assertNotRegex(_text(script), r"/DEBUG|/Zi\b|/Z7\b|/Fd", "no debug record, so no path in the DLL")

    def test_no_source_embeds_a_date_a_time_or_a_path(self) -> None:
        pattern = re.compile(r"__DATE__|__TIME__|__TIMESTAMP__|__FILE__|\bassert\s*\(")
        for path in sorted((ROOT / "native").rglob("*")):
            if path.suffix in {".c", ".h", ".inc"}:
                with self.subTest(file=path.relative_to(ROOT).as_posix()):
                    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", path.read_text(encoding="utf-8"), flags=re.S)
                    self.assertIsNone(pattern.search(code))


class BuildFailureTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("powershell"), "needs PowerShell")
    def test_a_script_that_fails_after_writing_a_dll_is_an_error_not_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "build_fake.ps1"
            script.write_text('Set-Content -Path (Join-Path $PSScriptRoot "..\first.dll") -Value "x"\nthrow "the second DLL failed"\n',
                              encoding="utf-8")
            with self.assertRaises(RuntimeError) as caught:
                build_copy(script, Path(folder) / "out")
            self.assertIn("the second DLL failed", str(caught.exception), "the script's output is shown")


class BuildTwiceTests(unittest.TestCase):
    def test_two_builds_in_different_folders_are_the_same_bytes(self) -> None:
        ran = 0
        for script in dll_scripts():
            if not toolchain_present(script):
                continue
            with self.subTest(script=script.name), tempfile.TemporaryDirectory(prefix="first_") as a, \
                    tempfile.TemporaryDirectory(prefix="second_build_in_a_longer_folder_name_") as b:
                one = build_copy(script, Path(a))
                two = build_copy(script, Path(b))
                self.assertTrue(one, f"{script.name} built nothing")
                self.assertEqual(one, two, f"{script.name}: two builds of one source differ")
                ran += 1
        if not ran:
            self.skipTest("MSVC toolchain not installed")


if __name__ == "__main__":
    unittest.main()
