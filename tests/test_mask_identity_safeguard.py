"""Focused tests for the village-wide mask distribution identity safeguard.

These drive the SHIPPED C (native/shared/mask_identity.c), compiled for x64 by
scripts/build_mask_identity_harness.py and called through ctypes.  The module is
address-free -- it names no game address and no record offset -- so the object
code exercised here is the same logic that goes into the 32-bit companions.

The behavioural tests use a synthetic record layout on purpose.  Nothing here
asserts a real game's offsets; those live in data/mask_identity_adapters.json
with their evidence, and the last test class checks that table instead.
"""
from __future__ import annotations

import atexit
import ctypes
import importlib.util
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "native" / "shared" / "mask_identity.h"
ADAPTERS = ROOT / "data" / "mask_identity_adapters.json"
BUILDER = ROOT / "scripts" / "build_mask_identity_harness.py"

MAX_SLOTS = 256


def _load_builder():
    spec = importlib.util.spec_from_file_location("mask_identity_harness", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the mask-identity harness builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------- ctypes types

class Field(ctypes.Structure):
    _fields_ = [
        ("present", ctypes.c_int),
        ("offset", ctypes.c_uint),
        ("kind", ctypes.c_int),
        ("count", ctypes.c_int),
    ]


class Special(ctypes.Structure):
    _fields_ = [
        ("kind", ctypes.c_int),
        ("offset", ctypes.c_uint),
        ("value", ctypes.c_int),
        ("pointer", ctypes.POINTER(ctypes.c_ubyte)),
    ]


IDENTITY_FIELDS = (
    "name",
    "health",
    "age",
    "gender",
    "head",
    "body",
    "nursing",
    "skills",
    "preferred_skill",
    "likes",
    "dislikes",
)


class Adapter(ctypes.Structure):
    _fields_ = (
        [
            ("enabled", ctypes.c_int),
            ("base", ctypes.POINTER(ctypes.c_ubyte)),
            ("stride", ctypes.c_uint),
            ("count", ctypes.c_int),
            ("active", Field),
            ("dead", Field),
        ]
        + [(name, Field) for name in IDENTITY_FIELDS]
        + [("special", Special)]
    )


class Entry(ctypes.Structure):
    _fields_ = [
        ("slot", ctypes.c_int),
        ("live", ctypes.c_int),
        ("special", ctypes.c_int),
        ("already_masked", ctypes.c_int),
        ("fingerprint", ctypes.c_uint),
    ]


class Snapshot(ctypes.Structure):
    _fields_ = [
        ("count", ctypes.c_int),
        ("live_count", ctypes.c_int),
        ("candidate_count", ctypes.c_int),
        ("village_signature", ctypes.c_uint),
        ("entries", Entry * MAX_SLOTS),
    ]


# Mirrors of the header enums.  StatusConstantsTests below proves they match.
OK = 0
ADAPTER_DISABLED = 1
BAD_ARGUMENT = 2
TOO_MANY_SLOTS = 3
AMBIGUOUS = 4
PLAN_OUT_OF_RANGE = 5
PLAN_TARGETS_MASKED = 6
PLAN_TARGETS_SPECIAL = 7
PLAN_DUPLICATE_SLOT = 8
PLAN_TARGETS_DEAD = 9
STALE_SNAPSHOT = 10

F_U8, F_I32, F_STR = 0, 1, 2
SPECIAL_NONE, SPECIAL_POINTER, SPECIAL_FLAG, SPECIAL_RANK = 0, 1, 2, 3


# ------------------------------------------------------- synthetic test layout

STRIDE = 0x80
OFF = {
    "active": 0x00,
    "dead": 0x01,
    "head": 0x04,
    "body": 0x08,
    "age": 0x0C,
    "gender": 0x10,
    "health": 0x14,
    "skills": 0x18,           # 5 x i32
    "preferred_skill": 0x2C,
    "likes": 0x30,            # 2 x i32
    "dislikes": 0x38,         # 2 x i32
    "name": 0x40,             # 16-byte buffer
    "nursing": 0x50,
    "chief": 0x51,
    "rank": 0x54,
}


class Village:
    """A block of synthetic villager records plus the adapter describing it."""

    def __init__(self, count: int = 8, *, special=SPECIAL_NONE, enabled: bool = True):
        self.count = count
        self.buffer = (ctypes.c_ubyte * (count * STRIDE))()
        self.masks = (ctypes.c_ubyte * count)()

        adapter = Adapter()
        adapter.enabled = 1 if enabled else 0
        adapter.base = ctypes.cast(self.buffer, ctypes.POINTER(ctypes.c_ubyte))
        adapter.stride = STRIDE
        adapter.count = count
        adapter.active = Field(1, OFF["active"], F_U8, 1)
        adapter.dead = Field(1, OFF["dead"], F_U8, 1)
        adapter.name = Field(1, OFF["name"], F_STR, 16)
        adapter.health = Field(1, OFF["health"], F_I32, 1)
        adapter.age = Field(1, OFF["age"], F_I32, 1)
        adapter.gender = Field(1, OFF["gender"], F_U8, 1)
        adapter.head = Field(1, OFF["head"], F_I32, 1)
        adapter.body = Field(1, OFF["body"], F_I32, 1)
        adapter.nursing = Field(1, OFF["nursing"], F_U8, 1)
        adapter.skills = Field(1, OFF["skills"], F_I32, 5)
        adapter.preferred_skill = Field(1, OFF["preferred_skill"], F_I32, 1)
        adapter.likes = Field(1, OFF["likes"], F_I32, 2)
        adapter.dislikes = Field(1, OFF["dislikes"], F_I32, 2)

        if special == SPECIAL_FLAG:
            adapter.special = Special(SPECIAL_FLAG, OFF["chief"], 0, None)
        elif special == SPECIAL_RANK:
            adapter.special = Special(SPECIAL_RANK, OFF["rank"], 13, None)
        elif special == SPECIAL_POINTER:
            adapter.special = Special(SPECIAL_POINTER, 0, 0, None)
        self.adapter = adapter

    # -- record access ----------------------------------------------------
    def record_address(self, slot: int) -> int:
        return ctypes.addressof(self.buffer) + slot * STRIDE

    def _poke(self, slot: int, offset: int, data: bytes) -> None:
        start = slot * STRIDE + offset
        self.buffer[start:start + len(data)] = tuple(data)

    def set_u8(self, slot: int, key: str, value: int) -> None:
        self._poke(slot, OFF[key], bytes([value & 0xFF]))

    def set_i32(self, slot: int, key: str, value: int, index: int = 0) -> None:
        self._poke(slot, OFF[key] + index * 4,
                   int(value).to_bytes(4, "little", signed=True))

    def set_name(self, slot: int, value: str) -> None:
        raw = value.encode("ascii")[:15]
        self._poke(slot, OFF["name"], raw + b"\0" * (16 - len(raw)))

    def populate(self, slot: int, *, name: str, head: int, body: int,
                 age: int = 100, gender: int = 1, health: int = 50,
                 skill: int = 7, pref: int = 2, like: int = 3,
                 dislike: int = 4, nursing: int = 0) -> None:
        """Fill one slot with a live villager."""
        self.set_u8(slot, "active", 1)
        self.set_u8(slot, "dead", 0)
        self.set_name(slot, name)
        self.set_i32(slot, "head", head)
        self.set_i32(slot, "body", body)
        self.set_i32(slot, "age", age)
        self.set_u8(slot, "gender", gender)
        self.set_i32(slot, "health", health)
        for i in range(5):
            self.set_i32(slot, "skills", skill + i, i)
        self.set_i32(slot, "preferred_skill", pref)
        self.set_i32(slot, "likes", like, 0)
        self.set_i32(slot, "likes", like + 1, 1)
        self.set_i32(slot, "dislikes", dislike, 0)
        self.set_i32(slot, "dislikes", dislike + 1, 1)
        self.set_u8(slot, "nursing", nursing)

    def clone_villager(self, source: int, target: int) -> None:
        """Make `target` byte-identical to `source` -- an indistinguishable twin."""
        start_s, start_t = source * STRIDE, target * STRIDE
        self.buffer[start_t:start_t + STRIDE] = \
            self.buffer[start_s:start_s + STRIDE]

    def move_villager(self, source: int, target: int) -> None:
        """Simulate save/reload compaction moving a record to another slot."""
        self.clone_villager(source, target)
        self.clear(source)

    def clear(self, slot: int) -> None:
        start = slot * STRIDE
        self.buffer[start:start + STRIDE] = tuple(b"\0" * STRIDE)


# --------------------------------------------------------------- test harness

class SafeguardTestCase(unittest.TestCase):
    """Base class that loads the compiled safeguard once."""

    lib = None
    build_dir = None
    build_error = None

    @classmethod
    def setUpClass(cls) -> None:
        if SafeguardTestCase.lib is not None or SafeguardTestCase.build_error:
            return
        try:
            builder = _load_builder()
            SafeguardTestCase.build_dir = Path(
                tempfile.mkdtemp(prefix="vv_mask_identity_")
            )
            dll = builder.build(SafeguardTestCase.build_dir)
            lib = ctypes.CDLL(str(dll))
        except Exception as exc:  # pragma: no cover - toolchain dependent
            SafeguardTestCase.build_error = f"{type(exc).__name__}: {exc}"
            return

        lib.vv_identity_snapshot_build.restype = ctypes.c_int
        lib.vv_identity_snapshot_build.argtypes = [
            ctypes.POINTER(Adapter), ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(Snapshot),
        ]
        lib.vv_identity_snapshot_is_stale.restype = ctypes.c_int
        lib.vv_identity_snapshot_is_stale.argtypes = [
            ctypes.POINTER(Adapter), ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(Snapshot),
        ]
        lib.vv_identity_preflight.restype = ctypes.c_int
        lib.vv_identity_preflight.argtypes = [
            ctypes.POINTER(Adapter), ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(Snapshot), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int,
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.vv_identity_is_candidate.restype = ctypes.c_int
        lib.vv_identity_is_candidate.argtypes = [
            ctypes.POINTER(Snapshot), ctypes.c_int,
        ]
        SafeguardTestCase.lib = lib

        # The DLL stays loaded for the rest of the run, so the build directory
        # can only be removed once every class is done -- not in tearDownClass,
        # which fires after the first class and would strand the others.
        atexit.register(SafeguardTestCase._cleanup)

    @staticmethod
    def _cleanup() -> None:  # pragma: no cover - runs at interpreter shutdown
        if SafeguardTestCase.build_dir:
            shutil.rmtree(SafeguardTestCase.build_dir, ignore_errors=True)

    def setUp(self) -> None:
        if SafeguardTestCase.build_error:
            self.skipTest(
                "x64 MSVC toolchain unavailable, cannot exercise the shipped C: "
                + SafeguardTestCase.build_error
            )

    # -- thin wrappers ----------------------------------------------------
    def snapshot(self, village: Village, masks=True) -> tuple[int, Snapshot]:
        out = Snapshot()
        table = village.masks if masks else None
        status = self.lib.vv_identity_snapshot_build(
            ctypes.byref(village.adapter), table, ctypes.byref(out)
        )
        return status, out

    def is_stale(self, village: Village, snap: Snapshot) -> int:
        return self.lib.vv_identity_snapshot_is_stale(
            ctypes.byref(village.adapter), village.masks, ctypes.byref(snap)
        )

    def preflight(self, village: Village, snap: Snapshot, plan):
        """plan = [(slot, mask), ...] -> (status, resolved, collision pair)"""
        n = len(plan)
        slots = (ctypes.c_int * max(n, 1))(*[p[0] for p in plan])
        masks = (ctypes.c_ubyte * max(n, 1))(*[p[1] for p in plan])
        resolved = (ctypes.c_int * max(n, 1))(*([-99] * max(n, 1)))
        a = ctypes.c_int(-1)
        b = ctypes.c_int(-1)
        status = self.lib.vv_identity_preflight(
            ctypes.byref(village.adapter), village.masks, ctypes.byref(snap),
            slots, masks, n, resolved, ctypes.byref(a), ctypes.byref(b),
        )
        return status, list(resolved)[:n], (a.value, b.value)


# ------------------------------------------------------------ header contract

class StatusConstantsTests(unittest.TestCase):
    """The Python mirrors of the C enums must not drift out of order."""

    def _enum_members(self, name: str) -> list[str]:
        text = HEADER.read_text(encoding="utf-8")
        # `[^}]*` rather than a lazy `.*?`: a lazy match starting at the FIRST
        # `typedef enum {` happily runs through an earlier enum's closing brace
        # and returns both enums' members concatenated.
        match = re.search(
            r"typedef enum \{([^}]*)\}\s*" + re.escape(name) + r"\s*;",
            text, re.S,
        )
        self.assertIsNotNone(match, f"{name} enum not found in the header")
        body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.S)
        members = []
        for chunk in body.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            members.append(chunk.split("=")[0].strip())
        return members

    def test_status_codes_match_the_header_order(self) -> None:
        expected = {
            "VV_IDENTITY_OK": OK,
            "VV_IDENTITY_ADAPTER_DISABLED": ADAPTER_DISABLED,
            "VV_IDENTITY_BAD_ARGUMENT": BAD_ARGUMENT,
            "VV_IDENTITY_TOO_MANY_SLOTS": TOO_MANY_SLOTS,
            "VV_IDENTITY_AMBIGUOUS": AMBIGUOUS,
            "VV_IDENTITY_PLAN_OUT_OF_RANGE": PLAN_OUT_OF_RANGE,
            "VV_IDENTITY_PLAN_TARGETS_MASKED": PLAN_TARGETS_MASKED,
            "VV_IDENTITY_PLAN_TARGETS_SPECIAL": PLAN_TARGETS_SPECIAL,
            "VV_IDENTITY_PLAN_DUPLICATE_SLOT": PLAN_DUPLICATE_SLOT,
            "VV_IDENTITY_PLAN_TARGETS_DEAD": PLAN_TARGETS_DEAD,
            "VV_IDENTITY_STALE_SNAPSHOT": STALE_SNAPSHOT,
        }
        members = self._enum_members("vv_identity_status")
        self.assertEqual(
            members, list(expected),
            "the header's status order changed; the Python mirrors are stale",
        )
        for index, name in enumerate(members):
            self.assertEqual(expected[name], index, f"{name} moved")

    def test_field_and_special_kinds_match_the_header_order(self) -> None:
        self.assertEqual(
            self._enum_members("vv_field_kind"),
            ["VV_FIELD_U8", "VV_FIELD_I32", "VV_FIELD_STR"],
        )
        self.assertEqual(
            self._enum_members("vv_special_kind"),
            ["VV_SPECIAL_NONE", "VV_SPECIAL_RECORD_POINTER",
             "VV_SPECIAL_RECORD_FLAG", "VV_SPECIAL_RECORD_RANK"],
        )


# --------------------------------------------------------------- requirement 1

class SnapshotTests(SafeguardTestCase):
    def _village(self, n=4):
        v = Village(count=8)
        for i in range(n):
            v.populate(i, name=f"V{i}", head=i, body=i + 10)
        return v

    def test_snapshot_counts_only_live_slots(self) -> None:
        v = self._village(3)
        status, snap = self.snapshot(v)
        self.assertEqual(status, OK)
        self.assertEqual(snap.count, 8)
        self.assertEqual(snap.live_count, 3)
        self.assertEqual(snap.candidate_count, 3)

    def test_dead_flag_excludes_a_slot(self) -> None:
        v = self._village(3)
        v.set_u8(1, "dead", 1)
        _, snap = self.snapshot(v)
        self.assertEqual(snap.live_count, 2)
        self.assertFalse(snap.entries[1].live)

    def test_signature_moves_when_a_villager_is_added(self) -> None:
        v = self._village(3)
        _, before = self.snapshot(v)
        self.assertEqual(self.is_stale(v, before), 0)
        v.populate(3, name="new", head=9, body=9)
        self.assertEqual(self.is_stale(v, before), 1)

    def test_signature_moves_when_a_villager_is_removed(self) -> None:
        v = self._village(3)
        _, before = self.snapshot(v)
        v.clear(2)
        self.assertEqual(self.is_stale(v, before), 1)

    def test_signature_moves_when_a_tracked_field_changes(self) -> None:
        """Requirement 1: any tracked identity field, not just membership."""
        for key, setter in (
            ("name", lambda v: v.set_name(0, "renamed")),
            ("health", lambda v: v.set_i32(0, "health", 99)),
            ("age", lambda v: v.set_i32(0, "age", 999)),
            ("gender", lambda v: v.set_u8(0, "gender", 0)),
            ("head", lambda v: v.set_i32(0, "head", 42)),
            ("body", lambda v: v.set_i32(0, "body", 42)),
            ("nursing", lambda v: v.set_u8(0, "nursing", 1)),
            ("skills", lambda v: v.set_i32(0, "skills", 555, 3)),
            ("preferred_skill", lambda v: v.set_i32(0, "preferred_skill", 4)),
            ("likes", lambda v: v.set_i32(0, "likes", 77, 1)),
            ("dislikes", lambda v: v.set_i32(0, "dislikes", 88, 1)),
        ):
            with self.subTest(field=key):
                v = self._village(3)
                _, before = self.snapshot(v)
                self.assertEqual(self.is_stale(v, before), 0)
                setter(v)
                self.assertEqual(
                    self.is_stale(v, before), 1,
                    f"changing {key} did not invalidate the snapshot",
                )

    def test_signature_moves_when_a_mask_is_applied(self) -> None:
        v = self._village(3)
        _, before = self.snapshot(v)
        v.masks[1] = 2
        self.assertEqual(self.is_stale(v, before), 1)

    def test_absent_field_stops_contributing(self) -> None:
        """A field with no proven offset must not be read at all."""
        v = self._village(3)
        v.adapter.name = Field(0, OFF["name"], F_STR, 16)
        _, before = self.snapshot(v)
        v.set_name(0, "totally different")
        self.assertEqual(
            self.is_stale(v, before), 0,
            "an absent field still influenced the fingerprint",
        )


# --------------------------------------------------------------- requirement 3

class AlreadyMaskedTests(SafeguardTestCase):
    def test_masked_villagers_are_not_candidates(self) -> None:
        v = Village()
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        v.masks[2] = 3
        _, snap = self.snapshot(v)
        self.assertEqual(snap.candidate_count, 3)
        self.assertTrue(snap.entries[2].already_masked)
        self.assertEqual(self.lib.vv_identity_is_candidate(ctypes.byref(snap), 2), 0)

    def test_plan_targeting_a_masked_villager_is_refused(self) -> None:
        v = Village()
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        v.masks[2] = 3
        _, snap = self.snapshot(v)
        status, resolved, _ = self.preflight(v, snap, [(2, 5)])
        self.assertEqual(status, PLAN_TARGETS_MASKED)
        self.assertEqual(resolved, [-99], "a refused plan handed back a mapping")

    def test_a_masked_villager_who_moved_is_still_refused(self) -> None:
        """The mask table is slot-indexed, so a masked villager who moves lands
        on a slot whose mask byte is clear.  The plan-time state still governs:
        this villager already has a mask and must not be given another."""
        v = Village()
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        v.masks[2] = 3
        _, snap = self.snapshot(v)
        v.move_villager(2, 6)
        v.masks[2] = 0                      # slot 6's mask byte is clear
        status, resolved, _ = self.preflight(v, snap, [(2, 5)])
        self.assertEqual(status, PLAN_TARGETS_MASKED)
        self.assertEqual(resolved, [-99])

    def test_a_mask_applied_after_planning_is_still_refused(self) -> None:
        """The mask arrived between planning and applying; do not overwrite it."""
        v = Village()
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        _, snap = self.snapshot(v)
        v.masks[1] = 4
        status, _, _ = self.preflight(v, snap, [(1, 5)])
        self.assertEqual(status, PLAN_TARGETS_MASKED)


# --------------------------------------------------------------- requirement 5

class SpecialVillagerTests(SafeguardTestCase):
    def test_record_flag_special_is_protected(self) -> None:
        """VV3 Tribal Chief shape: a non-zero record byte."""
        v = Village(special=SPECIAL_FLAG)
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        v.set_u8(2, "chief", 1)
        _, snap = self.snapshot(v)
        self.assertTrue(snap.entries[2].special)
        self.assertEqual(snap.candidate_count, 3)
        status, _, _ = self.preflight(v, snap, [(2, 5)])
        self.assertEqual(status, PLAN_TARGETS_SPECIAL)

    def test_record_rank_special_is_protected(self) -> None:
        """VV5 Retired Chief shape: a record int equal to a known rank."""
        v = Village(special=SPECIAL_RANK)
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        v.set_i32(3, "rank", 13)
        _, snap = self.snapshot(v)
        self.assertTrue(snap.entries[3].special)
        status, _, _ = self.preflight(v, snap, [(3, 5)])
        self.assertEqual(status, PLAN_TARGETS_SPECIAL)

    def test_record_rank_special_ignores_other_values(self) -> None:
        v = Village(special=SPECIAL_RANK)
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        v.set_i32(3, "rank", 12)
        _, snap = self.snapshot(v)
        self.assertFalse(snap.entries[3].special)

    def test_record_pointer_special_is_protected(self) -> None:
        """VV1 Golden Child shape: a global holding the protected record."""
        v = Village(special=SPECIAL_POINTER)
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        v.adapter.special.pointer = ctypes.cast(
            ctypes.c_void_p(v.record_address(1)), ctypes.POINTER(ctypes.c_ubyte)
        )
        _, snap = self.snapshot(v)
        self.assertTrue(snap.entries[1].special)
        self.assertEqual(snap.candidate_count, 3)
        status, _, _ = self.preflight(v, snap, [(1, 5)])
        self.assertEqual(status, PLAN_TARGETS_SPECIAL)

    def test_null_pointer_special_protects_nobody(self) -> None:
        """"No golden child" must not accidentally match every record."""
        v = Village(special=SPECIAL_POINTER)
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        _, snap = self.snapshot(v)
        self.assertEqual(snap.candidate_count, 4)
        for i in range(4):
            self.assertFalse(snap.entries[i].special)

    def test_a_villager_who_was_special_when_planned_is_refused(self) -> None:
        """Fail closed on the plan-time protection: a plan built while this
        villager was the chief must not be applied just because the flag has
        since moved on."""
        v = Village(special=SPECIAL_FLAG)
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        v.set_u8(2, "chief", 1)
        _, snap = self.snapshot(v)
        v.set_u8(2, "chief", 0)             # no longer special right now
        status, resolved, _ = self.preflight(v, snap, [(2, 5)])
        self.assertEqual(status, PLAN_TARGETS_SPECIAL)
        self.assertEqual(resolved, [-99])

    def test_becoming_special_invalidates_the_snapshot(self) -> None:
        """The chief flag is not an identity field, so only the snapshot's own
        special marker can carry this change."""
        v = Village(special=SPECIAL_FLAG)
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        _, snap = self.snapshot(v)
        self.assertEqual(self.is_stale(v, snap), 0)
        v.set_u8(2, "chief", 1)
        self.assertEqual(self.is_stale(v, snap), 1)

    def test_a_villager_who_becomes_special_after_planning_is_refused(self) -> None:
        v = Village(special=SPECIAL_FLAG)
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        _, snap = self.snapshot(v)
        v.set_u8(1, "chief", 1)
        status, _, _ = self.preflight(v, snap, [(1, 5)])
        self.assertEqual(status, PLAN_TARGETS_SPECIAL)


# ------------------------------------------------------- requirements 2, 6, 7

class ResolutionTests(SafeguardTestCase):
    def _twins(self):
        """Two byte-identical villagers plus two distinct ones."""
        v = Village()
        v.populate(0, name="Alpha", head=1, body=1)
        v.populate(1, name="Twin", head=2, body=2)
        v.clone_villager(1, 2)          # slot 2 is indistinguishable from slot 1
        v.populate(3, name="Delta", head=4, body=4)
        return v

    def test_twins_share_a_fingerprint(self) -> None:
        v = self._twins()
        _, snap = self.snapshot(v)
        self.assertEqual(snap.entries[1].fingerprint, snap.entries[2].fingerprint)
        self.assertNotEqual(snap.entries[0].fingerprint, snap.entries[1].fingerprint)

    def test_duplicate_fingerprints_are_resolved_by_the_record_key(self) -> None:
        """Requirement 10: twins are fine as long as the stable slot separates them."""
        v = self._twins()
        _, snap = self.snapshot(v)
        status, resolved, _ = self.preflight(v, snap, [(1, 5), (2, 6)])
        self.assertEqual(status, OK)
        self.assertEqual(resolved, [1, 2], "the record key failed to separate twins")

    def test_a_moved_villager_is_still_resolved(self) -> None:
        """Save/reload compaction moved the record; identity still finds it."""
        v = Village()
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        _, snap = self.snapshot(v)
        v.move_villager(2, 6)
        status, resolved, _ = self.preflight(v, snap, [(2, 5)])
        self.assertEqual(status, OK)
        self.assertEqual(
            resolved, [6],
            "the mask would have been written to the villager's old slot",
        )

    def test_a_moved_twin_is_refused_rather_than_guessed(self) -> None:
        """Requirement 7: fail closed, and say exactly who collided."""
        v = self._twins()
        _, snap = self.snapshot(v)
        # The planned twin leaves its slot, so the record key can no longer say
        # which of the two remaining identical villagers was meant.
        v.move_villager(1, 5)
        status, resolved, collision = self.preflight(v, snap, [(1, 5)])
        self.assertEqual(status, AMBIGUOUS)
        self.assertEqual(resolved, [-99], "an ambiguous plan handed back a mapping")
        self.assertEqual(
            sorted(collision), [2, 5],
            "the diagnostic did not name both colliding records",
        )

    def test_a_departed_villager_is_reported_as_stale(self) -> None:
        v = Village()
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        _, snap = self.snapshot(v)
        v.clear(2)
        status, _, _ = self.preflight(v, snap, [(2, 5)])
        self.assertEqual(status, STALE_SNAPSHOT)

    def test_identity_depends_on_which_field_a_value_came_from(self) -> None:
        """A value alone is not identity -- the field it sits in counts too.

        This matters because adapters are edited as evidence lands: an adapter
        that starts reading `body` instead of `head` must not produce the same
        fingerprints it did before, or a stale snapshot would look current.
        """
        v = Village()
        v.populate(0, name="Same", head=5, body=5)

        v.adapter.body = Field(0, OFF["body"], F_I32, 1)      # head only
        _, head_only = self.snapshot(v)
        v.adapter.head = Field(0, OFF["head"], F_I32, 1)
        v.adapter.body = Field(1, OFF["body"], F_I32, 1)      # body only
        _, body_only = self.snapshot(v)

        self.assertNotEqual(
            head_only.entries[0].fingerprint,
            body_only.entries[0].fingerprint,
            "the same value in a different field produced the same identity",
        )

    def test_bytes_past_the_name_terminator_are_ignored(self) -> None:
        """Only the name the game shows counts; buffer litter must not."""
        v = Village()
        v.populate(0, name="Ana", head=1, body=1)
        v.clone_villager(0, 1)
        _, before = self.snapshot(v)
        self.assertEqual(before.entries[0].fingerprint,
                         before.entries[1].fingerprint)
        v._poke(1, OFF["name"] + 4, b"junk")   # after the terminator
        _, after = self.snapshot(v)
        self.assertEqual(
            after.entries[0].fingerprint, after.entries[1].fingerprint,
            "litter past the name terminator changed the villager's identity",
        )

    def test_every_captured_field_separates_two_villagers(self) -> None:
        """Requirement 2: each listed field really does contribute to identity."""
        mutations = (
            ("name", lambda v: v.set_name(1, "other")),
            ("health", lambda v: v.set_i32(1, "health", 51)),
            ("age", lambda v: v.set_i32(1, "age", 101)),
            ("gender", lambda v: v.set_u8(1, "gender", 0)),
            ("head", lambda v: v.set_i32(1, "head", 99)),
            ("body", lambda v: v.set_i32(1, "body", 99)),
            ("nursing", lambda v: v.set_u8(1, "nursing", 1)),
            ("skills", lambda v: v.set_i32(1, "skills", 99, 4)),
            ("preferred_skill", lambda v: v.set_i32(1, "preferred_skill", 9)),
            ("likes", lambda v: v.set_i32(1, "likes", 99, 1)),
            ("dislikes", lambda v: v.set_i32(1, "dislikes", 99, 1)),
        )
        for key, mutate in mutations:
            with self.subTest(field=key):
                v = Village()
                v.populate(0, name="Same", head=1, body=1)
                v.clone_villager(0, 1)
                _, snap = self.snapshot(v)
                self.assertEqual(
                    snap.entries[0].fingerprint, snap.entries[1].fingerprint
                )
                mutate(v)
                _, after = self.snapshot(v)
                self.assertNotEqual(
                    after.entries[0].fingerprint, after.entries[1].fingerprint,
                    f"{key} does not contribute to identity",
                )


# --------------------------------------------------------------- requirement 6

class PlanValidationTests(SafeguardTestCase):
    def _village(self):
        v = Village()
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        return v

    def test_out_of_range_slot_is_refused(self) -> None:
        v = self._village()
        _, snap = self.snapshot(v)
        for slot in (-1, 8, 999):
            with self.subTest(slot=slot):
                status, resolved, _ = self.preflight(v, snap, [(slot, 5)])
                self.assertEqual(status, PLAN_OUT_OF_RANGE)
                self.assertEqual(resolved, [-99])

    def test_empty_slot_is_refused(self) -> None:
        v = self._village()
        _, snap = self.snapshot(v)
        status, _, _ = self.preflight(v, snap, [(6, 5)])
        self.assertEqual(status, PLAN_TARGETS_DEAD)

    def test_the_same_villager_twice_is_refused(self) -> None:
        v = self._village()
        _, snap = self.snapshot(v)
        status, resolved, _ = self.preflight(v, snap, [(1, 5), (1, 6)])
        self.assertEqual(status, PLAN_DUPLICATE_SLOT)
        self.assertEqual(resolved, [-99, -99])

    def test_two_plan_rows_resolving_to_one_record_are_refused(self) -> None:
        """Distinct planned slots that collapse onto the same record."""
        v = Village()
        v.populate(0, name="Alpha", head=1, body=1)
        v.populate(1, name="Twin", head=2, body=2)
        v.clone_villager(1, 2)
        _, snap = self.snapshot(v)
        # Both twins vacate their slots into one record: rows 1 and 2 can only
        # resolve to the survivor.
        v.clear(1)
        v.clear(2)
        v.populate(4, name="Twin", head=2, body=2)
        status, resolved, _ = self.preflight(v, snap, [(1, 5), (2, 6)])
        self.assertIn(status, (PLAN_DUPLICATE_SLOT, AMBIGUOUS))
        self.assertEqual(resolved, [-99, -99])

    def test_a_zero_mask_is_refused(self) -> None:
        v = self._village()
        _, snap = self.snapshot(v)
        status, _, _ = self.preflight(v, snap, [(1, 0)])
        self.assertEqual(status, BAD_ARGUMENT)

    def test_an_oversized_plan_is_refused(self) -> None:
        v = self._village()
        _, snap = self.snapshot(v)
        slots = (ctypes.c_int * (MAX_SLOTS + 1))()
        masks = (ctypes.c_ubyte * (MAX_SLOTS + 1))()
        status = self.lib.vv_identity_preflight(
            ctypes.byref(v.adapter), v.masks, ctypes.byref(snap),
            slots, masks, MAX_SLOTS + 1, None, None, None,
        )
        self.assertEqual(status, TOO_MANY_SLOTS)

    def test_an_empty_plan_is_accepted_and_writes_nothing(self) -> None:
        v = self._village()
        _, snap = self.snapshot(v)
        status, resolved, _ = self.preflight(v, snap, [])
        self.assertEqual(status, OK)
        self.assertEqual(resolved, [])

    def test_one_bad_row_rejects_the_whole_plan(self) -> None:
        """Requirement 6: all-or-nothing, no partial mapping handed back."""
        v = self._village()
        v.masks[3] = 1
        _, snap = self.snapshot(v)
        status, resolved, _ = self.preflight(
            v, snap, [(0, 5), (1, 5), (2, 5), (3, 5)]
        )
        self.assertEqual(status, PLAN_TARGETS_MASKED)
        self.assertEqual(
            resolved, [-99] * 4,
            "earlier rows leaked a mapping despite a later row failing",
        )

    def test_preflight_writes_no_game_memory(self) -> None:
        """The safeguard must be read-only over records and the mask table."""
        v = self._village()
        _, snap = self.snapshot(v)
        before_records = bytes(v.buffer)
        before_masks = bytes(v.masks)
        self.preflight(v, snap, [(0, 5), (1, 6), (2, 7)])
        self.assertEqual(bytes(v.buffer), before_records)
        self.assertEqual(bytes(v.masks), before_masks)


# --------------------------------------------------------------- requirement 9

class DisabledAdapterTests(SafeguardTestCase):
    def test_disabled_adapter_refuses_every_entry_point(self) -> None:
        v = Village(enabled=False)
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        status, _ = self.snapshot(v)
        self.assertEqual(status, ADAPTER_DISABLED)
        out = Snapshot()
        status = self.lib.vv_identity_preflight(
            ctypes.byref(v.adapter), v.masks, ctypes.byref(out),
            (ctypes.c_int * 1)(0), (ctypes.c_ubyte * 1)(5), 1, None, None, None,
        )
        self.assertEqual(status, ADAPTER_DISABLED)

    def test_a_disabled_adapter_is_always_stale(self) -> None:
        """So a caller can never keep using a snapshot from a disabled game."""
        v = Village(enabled=False)
        snap = Snapshot()
        self.assertEqual(self.is_stale(v, snap), 1)

    def test_malformed_adapters_are_refused(self) -> None:
        for label, mutate in (
            ("no base", lambda a: setattr(a, "base", None)),
            ("zero stride", lambda a: setattr(a, "stride", 0)),
            ("zero count", lambda a: setattr(a, "count", 0)),
            ("negative count", lambda a: setattr(a, "count", -1)),
        ):
            with self.subTest(case=label):
                v = Village()
                mutate(v.adapter)
                status, _ = self.snapshot(v)
                self.assertEqual(status, BAD_ARGUMENT)

    def test_too_many_slots_is_refused(self) -> None:
        v = Village()
        v.adapter.count = MAX_SLOTS + 1
        status, _ = self.snapshot(v)
        self.assertEqual(status, TOO_MANY_SLOTS)

    def test_an_adapter_without_an_active_field_finds_nobody(self) -> None:
        """Belt and braces: it cannot tell a villager from an empty slot."""
        v = Village()
        for i in range(4):
            v.populate(i, name=f"V{i}", head=i, body=i)
        v.adapter.active = Field(0, 0, F_U8, 1)
        _, snap = self.snapshot(v)
        self.assertEqual(snap.live_count, 0)
        self.assertEqual(snap.candidate_count, 0)


# --------------------------------------------------------------- requirement 8

class AdapterEvidenceTableTests(unittest.TestCase):
    """data/mask_identity_adapters.json is the record of what is PROVEN.

    No offset may appear without a citation, and an adapter may only be enabled
    when the protections its game needs are themselves evidenced.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(ADAPTERS.read_text(encoding="utf-8"))
        cls.games = cls.data["games"]

    def test_all_five_games_are_listed(self) -> None:
        self.assertEqual(sorted(self.games), ["vv1", "vv2", "vv3", "vv4", "vv5"])

    def test_every_offset_carries_evidence(self) -> None:
        for game, entry in self.games.items():
            self.assertIn("evidence", entry["record"], f"{game} record block")
            self.assertTrue(entry["record"]["evidence"].strip())
            for name, field in entry.get("fields", {}).items():
                with self.subTest(game=game, field=name):
                    self.assertIn("offset", field)
                    self.assertRegex(field["offset"], r"^0x[0-9A-Fa-f]+$")
                    self.assertTrue(
                        field.get("evidence", "").strip(),
                        f"{game}.{name} has an offset but no evidence",
                    )

    def test_special_villagers_carry_evidence(self) -> None:
        for game, entry in self.games.items():
            for name, special in entry.get("special_villagers", {}).items():
                with self.subTest(game=game, special=name):
                    self.assertTrue(special.get("evidence", "").strip())
                    self.assertIn(
                        special.get("kind"),
                        {"record_pointer", "record_flag", "record_rank"},
                    )

    def test_absent_fields_say_why(self) -> None:
        for game, entry in self.games.items():
            for name, reason in entry.get("absent_fields", {}).items():
                with self.subTest(game=game, field=name):
                    self.assertTrue(reason.strip())
                    self.assertNotIn(
                        name, entry.get("fields", {}),
                        f"{game}.{name} is listed as both proven and absent",
                    )

    def test_disabled_adapters_state_a_reason(self) -> None:
        for game, entry in self.games.items():
            if not entry["enabled"]:
                with self.subTest(game=game):
                    self.assertTrue(
                        entry.get("disabled_reason", "").strip(),
                        f"{game} is disabled without saying why",
                    )

    def test_enabled_adapters_can_identify_a_villager(self) -> None:
        """An enabled adapter needs liveness plus real identity contributors."""
        for game, entry in self.games.items():
            if not entry["enabled"]:
                continue
            with self.subTest(game=game):
                fields = entry["fields"]
                self.assertIn("active", fields, f"{game} cannot detect liveness")
                contributors = set(fields) - {"active", "dead"}
                self.assertGreaterEqual(
                    len(contributors), 6,
                    f"{game} has too few proven fields to identify a villager",
                )

    def test_enabled_adapters_protect_their_known_special_villager(self) -> None:
        """Requirement 5: if a game has one, it must be evidenced to enable."""
        required = {"vv1": "golden_child", "vv3": "tribal_chief",
                    "vv5": "retired_chief"}
        for game, name in required.items():
            entry = self.games[game]
            if not entry["enabled"]:
                continue
            with self.subTest(game=game):
                self.assertIn(
                    name, entry.get("special_villagers", {}),
                    f"{game} is enabled without protecting its {name}",
                )

    def test_parentage_is_recorded_as_unproven_everywhere(self) -> None:
        """Requirement 8: it was requested, an RE audit found nothing, so no
        adapter may claim it."""
        note = self.data["unproven_fields_global"]["parentage"]
        self.assertTrue(note.strip())
        for game, entry in self.games.items():
            for name in entry.get("fields", {}):
                with self.subTest(game=game, field=name):
                    self.assertNotIn("mother", name.lower())
                    self.assertNotIn("father", name.lower())
                    self.assertNotIn("parent", name.lower())

    def test_rejected_fields_are_kept_out_of_the_proven_set(self) -> None:
        """VV4's source carries VV1-valued offsets; they must not be adopted."""
        for game, entry in self.games.items():
            rejected = entry.get("rejected_fields", {})
            for name, note in rejected.items():
                with self.subTest(game=game, field=name):
                    self.assertTrue(note.strip())
                    self.assertNotIn(name, entry.get("fields", {}))


if __name__ == "__main__":
    unittest.main()
