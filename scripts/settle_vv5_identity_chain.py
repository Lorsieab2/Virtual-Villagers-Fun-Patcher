"""Recompute VV5's identity chain in dependency order, then verify it.

VV5 pins itself at seven layers, each over the output of the one before, so a
change to the Origins payload or the companion invalidates all of them and they
have to be recomputed IN ORDER. Recomputing out of order silently re-invalidates
an earlier layer, which reads as "the suite is still red" long after the real
work is done.

Order:

    companion DLL
      -> Origins payload            (data/vv5_origins_feature.json)
      -> Task9 manifest + map       (regenerated from the above)
      -> Task9 PAGE hashes          (per mode, plus the expanded builder's pin)
      -> patcher identity pins      (manifest/map/companion sha + size, page length)
      -> expanded-time-warp builder (companion sha + size)
      -> expanded artefacts + builder source pins

Run it from the repository root AFTER building the companion and the Origins
payload:

    powershell scripts/build_vv5_task9_origins_dll.ps1
    python scripts/build_vv5_origins_feature.py
    python scripts/settle_vv5_identity_chain.py

The Task9 page carries twelve byte-pattern assertions (entry thunks, the two
trampolines, push counts, the withdrawn-gate absence). This refuses to touch the
page-length guard unless all twelve still hold, so the length is never widened
to make a red suite go green.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))
from vv_fun_patcher import (  # noqa: E402
    _pe_export_names,
    source_text_sha256,
)

# Every export the shipping build resolves at runtime. Time Warp reaches
# ShowVv5TimeWarp through GetProcAddress, so a companion missing it
# disables the row silently -- and settlement is the wrong place to find
# that out afterwards.
REQUIRED_EXPORTS = {
    b"BeginOriginsOwner",
    b"GetOriginsOwner",
    b"EndOriginsOwner",
    b"ShowOriginsUpgradeMenuState",
    b"ConfirmVV5Task9Action",
    b"ShowVV5Task9Result",
    b"ShowVv5TimeWarp",
}

DLL = "data/candidates/VVFP VV5 Task9 Origins Icons.dll"
ACTIVE = "data/vv5_origins_feature.json"
GENERATOR = "scripts/build_vv5_task9_native_actions.py"
EXPANDED = "scripts/build_expanded_time_warp.py"
PATCHER = Path("src/vv_fun_patcher.py")


def raw(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def txt(path: str) -> str:
    return source_text_sha256(Path(path).read_bytes())


def run(script: str) -> None:
    result = subprocess.run([sys.executable, script], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            f"{script} failed:\n{result.stdout[-1500:]}{result.stderr[-1500:]}"
        )


def swap(path: str, old: str, new: str, label: str,
         within: str | None = None) -> None:
    r"""Replace `old` with `new`, optionally only inside a named block.

    `within` is a regex selecting the enclosing constant (for example
    ``VV5_TASK9_PAGE_SHA256 = \{.*?\n\}``). Pass it whenever the value being
    replaced is a bare digest, because the same digest can legitimately appear
    in an unrelated pin -- a global replace once retargeted
    VV3_RUNNING_CERTIFIED_SHA256["map"] to the VV5 Task9 map hash, corrupting a
    certification that had not been touched.

    Without `within` the replacement is global, which is only safe for values
    that are unique by construction (a full assignment line, say).
    """
    if old == new:
        return
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    if within is None:
        if old not in s:
            raise SystemExit(f"{label}: {old[:16]}... not found in {path}")
        p.write_text(s.replace(old, new), encoding="utf-8")
    else:
        m = re.search(within, s, re.S)
        if m is None:
            raise SystemExit(f"{label}: block {within!r} not found in {path}")
        block = m.group(0)
        if old not in block:
            raise SystemExit(f"{label}: {old[:16]}... not in the {label} block")
        s = s[: m.start()] + block.replace(old, new) + s[m.end():]
        p.write_text(s, encoding="utf-8")
    print(f"  {label} -> {new[:12]}")


def pinned(path: str, pattern: str) -> str | None:
    m = re.search(pattern, Path(path).read_text(encoding="utf-8"))
    return m.group(1) if m else None


def main() -> None:
    # 0 -- refuse to certify a companion that does not export what the
    #      shipping build resolves. Settlement repins the DLL and then
    #      recomputes six further layers over it, so a broken binary
    #      caught only by the patcher afterwards has already had the whole
    #      chain rebuilt around it.
    missing = sorted(
        name.decode()
        for name in REQUIRED_EXPORTS - _pe_export_names(Path(DLL).read_bytes())
    )
    if missing:
        raise SystemExit(
            "REFUSING to settle: the companion does not export "
            + ", ".join(missing)
            + "\nRebuild it before settling; repinning it here would\n"
            "certify a build whose Time Warp row is dead."
        )
    print(f"  companion exports {len(REQUIRED_EXPORTS)}/{len(REQUIRED_EXPORTS)} present")

    # 1 -- the Origins payload the caller just built.
    swap(GENERATOR, pinned(GENERATOR, r'ACTIVE_SHA256 = "([0-9A-F]{64})"'),
         raw(ACTIVE), "generator ACTIVE_SHA256")
    before = pinned(GENERATOR, r'ACTIVE_SOURCE_TEXT_SHA256 = "([0-9A-F]{64})"')
    swap(GENERATOR, before, txt(ACTIVE), "generator ACTIVE_SOURCE_TEXT")
    if before != txt(ACTIVE):
        swap(str(PATCHER), before, txt(ACTIVE), "patcher ACTIVE_SOURCE_TEXT")

    # 2 -- Task9 artefacts.
    run(GENERATOR)
    print("  task9 manifest + map regenerated")

    block = re.search(r"VV5_TASK9_SOURCE_TEXT_SHA256 = \{(.*?)\}",
                      PATCHER.read_text(encoding="utf-8"), re.S).group(1)
    for key, path in (("manifest", "data/vv5_task9_native_actions.json"),
                      ("map", "data/candidates/vv5_task9_native_actions_map.json")):
        current = re.search(rf'"{key}": "([0-9A-F]{{64}})"', block).group(1)
        swap(str(PATCHER), current, txt(path), f"patcher {key} identity",
             within=r"VV5_TASK9_SOURCE_TEXT_SHA256 = \{.*?\}")

    swap(str(PATCHER), pinned(str(PATCHER), r'VV5_TASK9_DLL_SHA256 = "([0-9A-F]{64})"'),
         raw(DLL), "patcher companion sha")

    # Only the sizes that sit beside the SYMBOLIC companion pin. A size next to
    # a literal historical hash belongs to a frozen archival binding and must
    # keep its historical value -- updating it there silently desynchronises the
    # pair and trips "Expanded Time Warp emitted bytes drifted".
    size = os.path.getsize(DLL)
    s = PATCHER.read_text(encoding="utf-8")
    updated = re.sub(
        r'("sha256": VV5_TASK9_DLL_SHA256,\s+"size": )\d+',
        lambda m: m.group(1) + str(size),
        s,
    )
    if updated != s:
        PATCHER.write_text(updated, encoding="utf-8")
        print(f"  patcher companion size -> {size}")

    # 3 -- the Task9 PAGE hashes, above the manifest/map layer.
    spec = importlib.util.spec_from_file_location("task9gen", GENERATOR)
    task9 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(task9)
    stock_sha = hashlib.sha256(task9.build_page(0x7C9000)[0]).hexdigest().upper()
    expanded_sha = hashlib.sha256(task9.build_page(0x904000)[0]).hexdigest().upper()

    current = pinned(EXPANDED, r'if sha\(stock_page\) != "([0-9A-F]{64})"')
    if current:
        swap(EXPANDED, current, stock_sha, "expanded builder stock page")
    for mode in ("collection_progression", "immediate_fixed",
                 "experimental_expanded_256", "experimental_expanded_256_progression"):
        # Re-read each time. The two stock modes share a hash, so settling one
        # settles the other, and a block captured before the loop then sends
        # the next iteration hunting for a value that is already gone.
        page_block = re.search(r"VV5_TASK9_PAGE_SHA256 = \{(.*?)\n\}",
                               PATCHER.read_text(encoding="utf-8"), re.S).group(1)
        m = re.search(rf'"{mode}": "([0-9A-F]{{64}})"', page_block)
        if not m:
            continue
        want = expanded_sha if "expanded" in mode else stock_sha
        if m.group(1) != want:
            swap(str(PATCHER), m.group(1), want, f"patcher page {mode}",
                 within=r"VV5_TASK9_PAGE_SHA256 = \{.*?\n\}")

    # 4 -- the page-length guard, only once every byte assertion still holds.
    manifest = json.loads(
        Path("data/vv5_task9_native_actions.json").read_text(encoding="utf-8"))
    payload = None
    for section in [manifest] + [v for v in manifest.values() if isinstance(v, dict)]:
        for row in section.get("patches", []):
            if row["offset"] == "0xDB000":
                payload = bytes.fromhex(row["after"])
    if payload is None:
        raise SystemExit("Task9 payload row 0xDB000 not found")

    checks = {
        "no 89F96A6A in 0x40:0x180": bytes.fromhex("89F96A6A") not in payload[0x40:0x180],
        "0x4E entry thunk": payload[0x4E:0x59].hex().upper() == "97E8EC6F0100E8C7D9C9FF",
        "0x10E entry thunk": payload[0x10E:0x119].hex().upper() == "97E82C6F0100E807D9C9FF",
        "0x55 tail": payload[0x55:0x59].hex().upper() == "C7D9C9FF",
        "0x115 tail": payload[0x115:0x119].hex().upper() == "07D9C9FF",
        "push 2 count lo": payload[0x40:0xC0].count(bytes.fromhex("6802000000")) == 1,
        "push 2 count hi": payload[0x100:0x180].count(bytes.fromhex("6802000000")) == 1,
        "push 0x89 count lo": payload[0x40:0xC0].count(bytes.fromhex("6889000000")) == 1,
        "push 0x89 count hi": payload[0x100:0x180].count(bytes.fromhex("6889000000")) == 1,
        "0x2C0 trampoline": payload[0x2C0:0x2C7].hex().upper() == "B800917C00FFE0",
        "0x600 trampoline": payload[0x600:0x607].hex().upper() == "B820917C00FFE0",
        "withdrawn gate absent": bytes.fromhex("E11C0000") not in payload,
    }
    broken = [name for name, ok in checks.items() if not ok]
    if broken:
        raise SystemExit(
            "REFUSING to touch the page-length guard -- these no longer hold: "
            + ", ".join(broken)
            + "\nSomething real moved; investigate before re-pinning."
        )
    print(f"  task9 page 0x{len(payload):X}, all {len(checks)} byte guards hold")
    current = pinned(str(PATCHER), r"len\(payload\) != (0x[0-9A-F]+)")
    swap(str(PATCHER), f"len(payload) != {current}",
         f"len(payload) != 0x{len(payload):X}", "patcher page length")

    # 5 -- expanded time warp: builder pins, regenerate, then artefact pins.
    swap(EXPANDED, pinned(EXPANDED, r'COMPANION_SHA256 = "([0-9A-F]{64})"'),
         raw(DLL), "expanded companion sha")
    swap(EXPANDED, "COMPANION_SIZE = " + pinned(EXPANDED, r"COMPANION_SIZE = ([0-9]+)"),
         f"COMPANION_SIZE = {size}", "expanded companion size")
    run(EXPANDED)
    print("  expanded artefacts regenerated")

    for game, key, path in (
        ("vv3", "manifest", "data/vv3_expanded_time_warp.json"),
        ("vv3", "map", "data/candidates/vv3_expanded_time_warp_map.json"),
        ("vv5", "manifest", "data/vv5_expanded_time_warp.json"),
        ("vv5", "map", "data/candidates/vv5_expanded_time_warp_map.json"),
    ):
        artefacts = re.search(r"EXPANDED_TIME_WARP_ARTIFACT_SHA256 = \{(.*?)\n\}",
                              PATCHER.read_text(encoding="utf-8"), re.S).group(1)
        segment = re.search(rf'"{game}": \{{(.*?)\}}', artefacts, re.S).group(1)
        m = re.search(rf'"{key}": "([0-9A-F]{{64}})"', segment)
        if m and Path(path).is_file():
            swap(str(PATCHER), m.group(1), txt(path), f"expanded {game} {key}",
                 within=r"EXPANDED_TIME_WARP_ARTIFACT_SHA256 = \{.*?\n\}")

    # 6 -- the builder SOURCE pins, which move whenever either builder is edited.
    for pin, script in (("builder", EXPANDED), ("task9_builder", GENERATOR)):
        m = re.search(rf'"{pin}": "([0-9A-F]{{64}})"',
                      PATCHER.read_text(encoding="utf-8"))
        if m:
            swap(str(PATCHER), m.group(1), txt(script), f"expanded {pin} source",
                 within=r"EXPANDED_TIME_WARP_SOURCE_TEXT_SHA256 = \{.*?\n\}")

    run("scripts/generate_transparency_docs.py")
    print("settled")


if __name__ == "__main__":
    main()
