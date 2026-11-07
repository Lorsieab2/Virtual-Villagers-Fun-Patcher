"""Small fixtures for tests/test_preferred_job_repair.py: a save with graves and a villager table, a Deaths log,
and a game folder whose patcher log lists the rows."""
from __future__ import annotations

import hashlib
import json
import struct
import tempfile
from pathlib import Path

import vv_game_mechanics as gm
import vv_graves
import vv_last_names as ln
import vv_log_tools as tools

LOGS = "Virtual Villagers Fun Patcher Logs"
FOLDER = {1: "Virtual Villagers - A New Home - Modded", 2: "Virtual Villagers - The Lost Children - Modded",
          3: "Virtual Villagers - The Secret City - Modded", 4: "Virtual Villagers - The Tree of Life - Modded",
          5: "Virtual Villagers - New Believers - Modded"}

# Skills in record order.  Highest: Building 95.  Checked preference: Farming 60.
SKILLS = {1: [10, 95, 60, 5, 30], 2: [10, 95, 60, 5, 30], 3: [60, 10, 5, 30, 95],
          4: [60.5, 10.0, 5.0, 30.0, 95.5], 5: [60.5, 10.0, 5.0, 30.0, 95.5, 0.0]}
FARMING = {1: 1, 2: 1, 3: 0, 4: 0, 5: 0}
BUILDER = {1: 4, 2: 5, 3: 4, 4: 4, 5: 4}
NONE = {1: 0, 2: 0, 3: -1, 4: -1, 5: -1}
BUILDING = {1: 1, 2: 1, 3: 4, 4: 4, 5: 4}            # the Building skill's place in SKILLS

# Table entry fields, from the name: stride, age, health, head, body, skills, preference, present (offset, width).
ENTRY = {2: (0x2E0, -0x34, -0x38, -0x1C, -0x18, 0x280, 0x294, (0x29C, 1)),
         3: (0x11C, -0x10, 0xA4, 0x1C, 0x20, 0xD8, 0xEC, (-0x14, 4)),
         4: (0x104, -0x10, 0xA4, 0x1C, 0x20, 0xC0, 0xD4, (-0x14, 4)),
         5: (0x118, -0x10, 0xA4, 0x1C, 0x20, 0xC0, 0xD8, (-0x20, 1))}
TABLE = {2: 0x31000, 3: 0x8000, 4: 0xC000, 5: 0xC000}
SIZE = {1: 0x10000, 2: 0x60000, 3: 0x10000, 4: 0x14000, 5: 0x14000}


def put(buf: bytearray, at: int, value) -> None:
    struct.pack_into("<f" if isinstance(value, float) else "<i", buf, at, value)


def entry_at(game: int, k: int) -> int:
    """The name offset of table entry k."""
    if game == 1:
        checker = tools.load_checker()
        return checker.VV1_BLOCK0 + k * checker.VV1_STRIDE + 0x370 - checker.VV1_BASE
    return TABLE[game] + 0x40 + k * ENTRY[game][0]


def write_entry(buf: bytearray, game: int, k: int, name: str, age: int, health: int, pref: int,
                present: bool, skills: list | None = None) -> None:
    at = entry_at(game, k)
    skills = SKILLS[game] if skills is None else skills
    buf[at:at + len(name) + 1] = name.encode() + b"\0"
    if game == 1:
        put(buf, at - 0x28, age)
        put(buf, at - 0x2C, health)
        put(buf, at - 0x20, 1)
        for i, s in enumerate(skills):
            put(buf, at + 0x4C + 4 * i, s)
        put(buf, at + 0x60, pref)
        buf[at + 0x64] = 1 if present else 0
        return
    _stride, age_at, health_at, head, body, skills_at, pref_at, (flag, width) = ENTRY[game]
    put(buf, at + age_at, age)
    put(buf, at + health_at, health)
    put(buf, at + head, 1)
    put(buf, at + body, 1)
    for i, s in enumerate(skills):
        put(buf, at + skills_at + 4 * i, s)
    put(buf, at + pref_at, pref)
    buf[at + flag:at + flag + width] = (1 if present else 0).to_bytes(width, "little")


def write_grave(buf: bytearray, game: int, place: int, name: str, age: int, job: int, value: int,
                epitaph: str = "") -> None:
    lay = vv_graves.LAYOUTS[game]
    at = lay.base + place * lay.stride
    buf[at:at + len(name) + 1] = name.encode() + b"\0"
    put(buf, at + lay.age, age)
    put(buf, at + lay.job, job)
    put(buf, at + lay.value, value)
    if lay.epitaph and epitaph:
        buf[at + lay.epitaph[0]:at + lay.epitaph[0] + len(epitaph) + 1] = epitaph.encode() + b"\0"


class Village:
    """One village: graves (name, age, job, value, epitaph) and table entries; a Deaths log; the exe's rows."""

    def __init__(self, game: int):
        self.game = game
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = self.root / "LDW" / FOLDER[game]
        self.folder.mkdir(parents=True)
        self.buf = bytearray(SIZE[game])
        if game == 3:                                     # no gravestones
            for k in range(50):
                put(self.buf, vv_graves.VV3_STONES[0] + k * vv_graves.VV3_STONES[2], -1)
        self.log_text = "Village: Test Tribe (Save 1)\n"
        self.game_folders: list[Path] = []

    def save(self) -> Path:
        stem = tools.load_checker().SAVE_STEMS[self.game]
        path = self.folder / f"{stem}1.ldw"
        path.write_bytes(bytes(self.buf))
        return path

    def death(self, n: int, name: str, age: int, grave: str, epitaph: str) -> None:
        self.log_text += (f"Death {n}\n  Name: {name}\n  Age at death: {age}\n  Sex: Female\n"
                          f"  Cause of death: Old age\n  Grave: {grave}\n  Epitaph: {epitaph}\n\n")

    def log(self) -> Path:
        logs = self.folder / LOGS / "Deaths and Disappearances"
        logs.mkdir(parents=True, exist_ok=True)
        path = logs / f"Virtual Villagers {self.game} Deaths Log 1.txt"
        path.write_bytes(self.log_text.encode("cp1252"))
        return path

    def rows(self, rows: list[str]) -> None:
        built = self.root / "Games" / FOLDER[self.game]
        files = built / "Virtual Villagers Fun Patcher Files"
        files.mkdir(parents=True)
        exe = built / f"{FOLDER[self.game]}.exe"
        exe.write_bytes(b"MZ test exe " + bytes([self.game]))
        digest = hashlib.sha256(exe.read_bytes()).hexdigest()
        (files / (exe.stem + gm.PATCH_LOG_SUFFIX)).write_text(json.dumps({
            "patcher": gm.PATCHER_SIGNATURE, "output_sha256": digest, "fun_patches": rows,
            "created_utc": "2026-11-07T00:00:00"}), encoding="utf-8")
        self.game_folders = [built]

    def close(self) -> None:
        self.tmp.cleanup()


def sidecar_vv1(v: Village, place: int, name: str, age: int, epitaph: str) -> Path:
    """A New Home's Graves file with one entry: the grave's epitaph."""
    fp = ln.grave_fingerprint(name.encode().ljust(0x1C, b"\0"), ln.GRAVE_PRINT_CAP[1], age)
    e = bytearray(44)
    struct.pack_into("<HHIb", e, 0, 0, place, fp, 2)
    e[9] = vv_graves.EPITAPHS.index(epitaph)
    path = vv_graves.graves_file(v.folder, 1, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<4sIII", b"VCD1", 1, 1, 1) + bytes(e))
    return path
