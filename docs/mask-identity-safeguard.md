# Mask distribution identity safeguard

A village-wide mask distribution has to decide which villager gets which mask.
If two villagers cannot be told apart, a plan can attach a mask to the wrong
record. This module is the additive guard against that: it fingerprints every
villager from **verified** record fields, refuses any plan it cannot resolve
uniquely, and writes nothing itself.

**Nothing in the shipped patches calls it yet.** It is deliberately inert: the
existing native planners remain the path every game takes at runtime, exactly as
they do today. Wiring a game up to it is a later, separately playtested change.

## Files

| File | What it is |
|---|---|
| `native/shared/mask_identity.h` | The contract: adapter, snapshot, status codes |
| `native/shared/mask_identity.c` | The implementation. Address-free and freestanding |
| `data/mask_identity_adapters.json` | Per-game evidence table -- every offset with its citation |
| `scripts/build_mask_identity_harness.py` | Compiles the C for x64 so tests can call it |
| `tests/test_mask_identity_safeguard.py` | Focused tests, driven through ctypes |

## Why it is address-free

`mask_identity.c` names no game address and no record offset. Everything
build-specific arrives in a caller-supplied `vv_identity_adapter`. That is not
tidiness: it is what lets the tests exercise the **shipped** code. The module
compiles once for the 32-bit game companions and again for x64, where 64-bit
Python can drive it directly through ctypes. The tests are not a Python
re-description of the logic; they run the same source.

## How identity works

Each live villager is hashed over the fields the build actually proves, each
mixed in under its own tag so the *field* a value came from is part of the
identity. A field with no proven offset is simply absent and contributes
nothing -- it is never guessed at from a sibling game.

The fingerprint is **not** assumed unique. Twins happen. The stable native
record index is the tie-breaker:

1. Match the planned villager by fingerprint against the village as it stands.
2. Exactly one match: resolved -- even if the record moved slots, which is what
   a save/reload compaction does.
3. Several matches, and the planned villager is still in its own slot: the
   record key settles it.
4. Several matches and it has moved: **refuse.** There is no evidence left that
   says which twin was meant, so the whole distribution is abandoned and both
   colliding record slots are reported.

## Two-phase, fail-closed

`vv_identity_preflight()` validates everything and writes nothing. It rejects a
plan that would target a slot out of range, an empty slot, an already-masked
villager, a protected villager, or the same record twice. **One bad row rejects
the whole plan**, and the resolved mapping is only handed back on success, so a
rejected plan leaves the caller with nothing it could half-apply. Masks,
sidecars, saves and tech points are untouched on every failure path.

Rules are checked twice: once against the plan-time snapshot and again at the
record the villager actually resolves to. Both matter. A villager masked when
the plan was made lands on a slot whose mask byte is clear if it moved, and a
villager that becomes the chief after planning sits in a slot the snapshot
thought was ordinary.

## Snapshot staleness

`village_signature` covers membership, every tracked identity field, the
protected-villager marker and mask state. Any of them changing tells the caller
to rebuild. Liveness is not hashed separately -- an empty slot contributes
fingerprint 0, so arrivals and departures already move it.

## What is proven, per game

`data/mask_identity_adapters.json` is the authority; it cites the file and
definition establishing every offset. Summary:

| | active | health | age | gender | head | body | skills | preferred | likes | dislikes | nursing | name | protected villager |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VV1 | `0x28` | -- | `0x348` | `0x350` | `0x360` | `0x364` | `0x3BC` | -- | `0x398` | `0x3A8` | -- | -- | Golden Child (ptr `0x48B614`) |
| VV2 | `0x30` | `0x52C` | `0x530` | -- | `0x548` | `0x54C` | `0x7E4` | `0x7F8` | `0x5F0` | `0x6E8` | -- | `0x564` | -- |
| VV3 | `0xF10` | `0xE78` | `0xDC4` | `0xDC8` | `0xDF0` | `0xDF4` | `0xEAC` | `0xEC0` | `0xFB4` | `0xFC0` | `0xE8C` | -- | Tribal Chief (`0xE80`) |
| VV4 | `0x1CC4` | `0x1C40` | `0x1B8C` | `0x1B90` | `0x1BB8` | `0x1BBC` | `0x1C5C` (x5, f32) | `0x1C70` | `0x1E60` | `0x1E6C` | -- | `0x1BC0` | -- |
| VV5 | `0x1CD4` | `0x1C40` | `0x1B8C` | `0x1B90` | `0x1BB8` | `0x1BBC` | `0x1C5C` (x6, f32) | `0x1C74` | -- | -- | -- | -- | Retired Chief (`0x1CFC` == 13) |

A dash means **no proven offset for that build**, not "zero" and not "same as
the game next to it".

### Adapter status

| Game | Enabled | Why |
|---|---|---|
| VV1 | No | No proven health or preferred-skill offset, and the name buffer's start and length are unestablished (`+0x374` is only proven to lie *inside* it) |
| VV2 | No | Fields are well evidenced, but this build carries the unresolved Origins crash; nothing new runs on it until that is settled |
| VV3 | Yes | Richest proven set, including nursing and the Tribal Chief |
| VV4 | Yes | Rich proven set including the name buffer |
| VV5 | Yes | Health, six Float32 skills and the preferred skill are now established, alongside the Retired Chief |

Disabled means the safeguard does not run for that game at all and the native
planner is used unchanged.

### Parentage: requested, and not available

Parentage was asked for on VV2-VV5, defined as the **name, head and body of the
mother and father**, expected inline in each villager's record.

An instruction-level RE audit of all four exact builds found no such fields. The
inheritance path that writes a child's own head/body was identified in each
build -- VV2 `sub_44C600`, VV3 `sub_456120`, VV4 `sub_45EF10`, and VV5's
constructor/pregnancy/delivery/clone/save-load path, all targeting the child's
own head/body offsets above -- but **no instruction stores a parent's name, head
or body into the child record.** Inheritance computes the child's own
appearance; it does not retain the parents'.

No adapter claims parentage, and a test enforces that no field name containing
"mother", "father" or "parent" can appear in the evidence table. Adding it would
require new per-build evidence for a mother/father record reference.

### Fields deliberately not adopted

VV4's companion carries `VV_AGE_OFFSET 0x348`, `VV_SKILL_*_OFFSET
0x3BC..0x3CC`, `VV_LIKES_OFFSET 0x398` and `VV_DISLIKES_OFFSET 0x3A8` --
**VV1's values**, in a file that is a copy of the VV1 source with only some
offsets corrected.

These are **not** unused definitions. `ShowOriginsUpgradeMenu` in
`native/vv4_origins_icons/vv4_origins_icons.c` (lines ~2143-2169) reads them
against VV4's layout, and compares the skills against int `100` rather than
float `100.0` besides. They are, however, **not reachable through the shipped
VV4 patch**: it resolves `ShowOriginsUpgradeMenuState`, a different export that
takes the dialog state from its caller and reads no villager fields.

So this is a latent trap in that companion rather than a live player-facing
fault -- but nothing here treats those values as proven, and they are recorded
in the table's `rejected_fields` with that explanation.

### Floats

VV4 and VV5 store skills as Float32. Those fields are declared `VV_FIELD_I32`
so the raw four bytes go into the fingerprint -- a bit-exact comparison, with no
float arithmetic in a module that has to stay freestanding. The evidence table
records them as type `f32` so the layout stays truthful.

VV5 has **six** skills where VV1-VV4 have five, which is exactly why its
preferred-skill DWORD sits at `+0x1C74` and VV4's at `+0x1C70`. A test pins that
relationship in both games.

### Elderly

No build defines a separately proven elderly flag. Elderly/old rendering is
*derived from age thresholds* -- VV4 and VV5 pick the old frame by age. The
adapters capture the proven age value as `age` and never relabel it.

## Testing

```bash
python -m pytest tests/test_mask_identity_safeguard.py -q
```

The behavioural tests run against a synthetic record layout on purpose -- no
test asserts a real game's offsets, because those belong in the evidence table
with their citations, which a separate test class checks instead.

The suite skips with an explicit reason if no x64 MSVC toolchain is present,
since it compiles the C to run it.

Every guard in `mask_identity.c` has been mutation-tested: breaking it one guard
at a time, each mutation is caught by the suite. Two guards that survived were
found to be genuinely redundant rather than under-tested, and were removed --
an explicit null check the adapter validation already made unreachable, and a
liveness byte in the signature that the zeroed fingerprint already carried.
