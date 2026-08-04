# VV3 Origins-Exclusive Features Research

This document records the verified implementation map for **Enable
Origins-Exclusive Features** in the supported desktop build of *Virtual
Villagers - The Secret City*. The feature is implemented by
`scripts/build_vv3_origins_feature.py`; its generated, fingerprint-bound patch
manifest is `data/vv3_origins_feature.json`.

## Supported executable

- File: `Virtual Villagers - The Secret City.exe`
- Size: `831488` bytes
- SHA-256:
  `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`
- Image base: `0x400000`

All addresses below apply only to this exact executable identity.

## Current shipping gate

The doubler audit is **STOP** for this exact build. New purchase and repurchase
are unavailable; existing owned doublers remain removable for zero cost and
zero refund, and ownership is never cleared automatically. Candidate return
sites and ranges below are historical implementation evidence, not exhaustive
provenance proof.

The exact writer inventory is 33 food rows (29 calls and 4 E9 tails) and 16
tech rows (13 calls and 3 E9 tails). The tail sites are food
`0x415EF1`, `0x416983`, `0x416BAB`, and `0x417A3A`, and tech `0x415D44`,
`0x41673E`, and `0x418452`. No Food Mastery-like award transform was found in
the writer, strings, or bounded caller corpus; Food Mastery is therefore
confirmed absent for this exact build.

The collection dispatcher `sub_42DEB0` resolves tech awards through
`0x42DF79` and food awards through `0x42E079`: tech awards are 100 for IDs
52–55, 64–67, 76–79, and 88–91; 250 for 56–59, 68–71, 80–83, and 92–95;
and 1,500 for 60–63, 72–75, 84–87, and 96–99. IDA has no resolved caller to
`sub_42DEB0`, so computed/indirect reachability remains unresolved.

Island Event positive, zero, negative, and bypass paths—including tail calls—
are inventoried, but mixed-source writers carry no source tag. `sub_458DB0`
emits base and bonus components through separate tech-writer calls, so no
single final-delta boundary is proved. There is no safe final-delta/source-aware
hook, transient marker, or certified new section/cave. The requested 500,000
purchase, zero-cost/no-refund removal, and full-price repurchase behavior is a
user contract, not stock-code evidence.

Exact-build audit `4c588ffd36765d750533fe9694f8fda5c8e82736`
enumerates all nine Magic-index reads and finds only one research consumer:
`sub_458DB0` case 26 getter call `0x4593DC`. Magic level 1 or higher adds one
deterministic tech point through a separate writer call. It does not alter
research action/tick frequency, duration, the base award, RNG probability or
amount, or Research-skill gain. Ordinary and special/catch-up routes converge
before Magic. Native calls occur in this order:

`B + (Q ? floor(B/4) : 0) + M + T + G`

Here `M` is the flat Magic `+1`; `G` is the independent `RNG(100) < 10`
addition. Collection duplicates and Island Events are separate producers. A
future Tech Doubler must double the complete eligible positive native research
sum once after all additions, while excluding Island Events. Because case 26
emits those components separately and the shared writer mixes other producers,
the Tech Doubler remains unavailable pending a provenance-safe post-sum hook or
source tag.

## Intended VV2-parity behavior

The current VV2 Origins feature is the behavior baseline:

- Tech Upgrades:
  - Time Warp: 50,000 tech points
  - Island Event: 30,000 tech points
  - Barrel of Babies: 75,000 tech points
  - Tech Point Doubler: 500,000 tech points; removable
  - Food Point Doubler: 500,000 tech points; removable
- Villager Upgrades:
  - Grant Youth: 50,000 tech points; age cannot go below 5
  - Grant Full Mastery: 100,000 tech points
  - Grant Running: 40,000 tech points
  - Set Age to 18: 50,000 tech points
- Doubler ownership belongs only to the current save.
- Island Event awards are not doubled.
- Grant Running uses a normal Like slot, removes Running from Dislikes, does
  not change movement data, and refuses without charging if no Like slot is
  free.
- Barrel of Babies must use VV3's native event and reserve room for all three
  children before charging.
- The reusable menu companion is
  `assets/origins/VVFP Origins Icons.dll`, export
  `ShowOriginsUpgradeMenuState(owner, type, state)`.

## Persisted save-scoped ownership

Verified unused persisted storage:

- Runtime global: `0x5824D0`
- Save-manager mirror: manager `+0x51C`
- Reserved saved region: global `0x5824D0..0x582537`, corresponding to manager
  `+0x51C..+0x583`

The first dword is code-unreferenced in the stock executable, zero-initialized,
and copied by the stock save/load path. Proposed bits:

- Bit 0: Tech Point Doubler
- Bit 1: Food Point Doubler

The save manager is returned by `sub_428B60`; its singleton pointer is
`0x4B309C`, and its object size is `0x12FD4`.

## Central food and tech routes

### Food

- Function: `sub_4263F0`
- Address: `0x4263F0`
- Receiver: pointer to current food
- Argument: signed delta
- Current-food global: `0x582490`
- Positive awards also increment stock lifetime Food Gathered at `0x5824AC`.
- Negative deltas clamp current food to zero and do not increase the lifetime
  total.

### Tech points

- Function: `sub_427130`
- Address: `0x427130`
- Receiver: pointer to current tech points
- Argument: signed delta
- Current-tech global: `0x582644`
- Positive awards also increment stock lifetime Points Earned at `0x5824A4`.
- Negative deltas clamp current tech points to zero and do not increase the
  lifetime total.

A correct doubler hook must double only a positive incoming delta before the
stock function updates both current resources and lifetime statistics.

### Island Event candidate exclusion

The historical candidate Island Event outcome dispatcher occupies
`0x458DB0..0x45943E`. Its food and tech awards use the same central resource
functions. The positive, zero, negative, bypass, and tail-call paths are
inventoried, but mixed-source writers have no source tag and the dispatcher
emits base and bonus components through separate tech-writer calls. This range
is not a final-delta/source-aware exclusion proof and must not be treated as
proof that every Island Event award is excluded.

## Villager Detail selection and record fields

The Villager Detail screen's displayed villager is selected by ID, not by a
screen-owned copy of the record:

1. Read the ID from save manager `+0x12FC0` (decimal `77760`).
2. Validate it with `sub_45EE60(id)` at `0x45EE60`.
3. Resolve the live record with `sub_45C840(id)` at `0x45C840`.

Verified record fields:

| Field | Record offset |
| --- | ---: |
| Current/displayed age | `+0xDC4` |
| Gender | `+0xDC8` |
| Health | `+0xE78` |
| Sick flag | `+0xE89` |
| Pregnancy/baby state | `+0xE8C` |
| Farming skill | `+0xEAC` |
| Building skill | `+0xEB0` |
| Research skill | `+0xEB4` |
| Healing skill | `+0xEB8` |
| Parenting skill | `+0xEBC` |
| Preferred job | `+0xEC0` |
| Three Likes | `+0xFB4` |
| Three Dislikes | `+0xFC0` |

Age uses 20 internal units per displayed year. The five skills are 32-bit
integers. Likes and Dislikes are each exactly three 32-bit entries, with `-1`
representing an empty slot.

The Detail renderer calls `sub_455350(record + 0xFB4)` for Likes and
`sub_4547D0(record + 0xFC0)` for Dislikes. Both helpers traverse exactly three
dwords.

### Grant Running

- Running trait ID: `38`
- If Running is already present in Likes, the upgrade is already satisfied.
- Otherwise, place `38` in the first `-1` Like slot.
- If no Like slot is free, refuse and do not charge.
- Clear every `38` found in the three Dislike slots.
- Do not alter movement speed or any movement-related record field.

`sub_454890` and `sub_454780` demonstrate the stock trait behavior but rely on
implicit current-selection state. Injected code should modify the resolved
record's three-slot arrays directly.

## Native Barrel of Babies event

VV3 already contains the literal native event:

- Title: `Another One of Those Barrels `
- Title string address: `0x48E5E4`
- Description string address: `0x48E450`
- Title localization ID: `0x321` (`801`)
- Description localization ID: `0x322` (`802`)
- Title-ID method: `0x4152F0`
- Description-ID method: `0x415300`
- Vtable: `0x47EA00`
- Registry index: `57`
- Event object pointer: `0x4B3D5C`
- Native result method: vtable `+0x30`, `sub_415320`

The event registry is built by `sub_418630`. Its pointer array begins at
`0x4B3C78`; the Barrel event is the last registered entry, index 57.

`sub_415320` performs the native result:

1. It creates the first child through `sub_45FF50(..., 200)`.
2. It calls `sub_45FE30`.
3. If permitted, it creates the second child through the same native route.
4. It calls `sub_45FE30` again.
5. If permitted, it creates the third child.

The stock event scheduler `sub_419B30` can deliberately select index 57 in its
forced-positive-event branch. Its native presentation path constructs the
event dialog through `sub_4192F0(event_object)`, presents it through
`sub_401AF0(owner, 0)`, and records the event as seen in
`byte_4B3C3C[57]`.

The Origins upgrade must use this native event object and presentation/result
path. It must not directly fabricate three villagers or substitute another
reward.

### Required capacity preflight

The purchase reserves room for all three children before deducting tech
points. The current-population helper is `sub_45E8F0(byte_59E110)`. It counts
each active villager record once and, when that record's baby-reservation flag
is active, adds its stored reserved-baby count. Pregnancies and multiple-birth
reservations therefore already consume capacity in this result.

The stock villager pool begins at `0x59E110` with stride `0x1F8C`. The physical
allocator is `sub_45F0B0`, which scans 150 records in the stock executable and
returns `-1` when none is available. The experimental expansion changes the
same pool bounds to 256.

The runtime discriminator is the dword immediate at `0x42883A`. It is the
immediate operand of `mov edi, 0x96` at `0x428839` in stock VV3; both expanded
modes replace it with `0x100`. The preflight permits the purchase only when
`sub_45E8F0(...) <= 147` in stock mode or `<= 253` in expanded mode.

## Island Event and Time Warp routes

- Island Event scheduler: `sub_4684D0`
- Ordinary event creation pipeline: `sub_419AC0` / `sub_419B30`
- Game-time function: `sub_403330`

The save manager's pause/speed field is at manager `+0x12F20` (decimal
`77600`). Stock code treats values at least `999` as paused and contains normal
branches for speeds `3`, `10`, and the remaining standard case.

Time Warp subtracts `speed * 3600` seconds from the baseline at `0x4A4210`.
The catch-up path divides elapsed seconds by 60 and then by the current speed
before passing the result to the age updater. The age updater adds that value
to the internal age field, and displayed age uses 20 internal units per year.
The result is therefore exactly 60 internal age units, or 3 displayed villager
years, at every active speed:

- half speed (`3`): 3 real hours
- normal speed (`6`): 6 real hours
- double speed (`10`): 10 real hours

Paused values (`>= 999`) are refused without charging.

## UI construction map

### Tech screen

- Constructor: `sub_464F30`
- Constructor address: `0x464F30`
- Vtable: `0x49E834`
- Message handler: `sub_465640(this, message, id)`
- Message-handler address: `0x465640`
- The handler processes command message `8` and stock IDs through `14`.

An Origins button may use an otherwise-unused ID greater than 14 if the
injected handler intercepts it before stock range handling.

The current candidate uses the first free/custom event, command `15`: the
constructor emits event `15`, and the detour accepts exactly `(message=8,
event=15)`. Any other message or event falls through to the stock handler.
This route and the 3,580-byte payload remain byte-identical to the prior
static UI build; the Playtest 9 report that the visible control did not open
the popup is therefore a runtime STOP that is not explained by a source or
emitted-byte mismatch. No new package is authorized until that runtime
discrepancy is independently reproduced and resolved.

### Villager Detail

- Constructor: `sub_46CB50`
- Constructor address: `0x46CB50`
- Vtable: `0x49EAD0`
- Message handler: `sub_46E530(this, message, id)`
- Message-handler address: `0x46E530`

### Shared stock UI helpers

- Button allocator thunk: `0x46EC93`
- Image/resource lookup: `sub_42E8A0`
- Button constructor: `sub_4019F0`
- Child append: `sub_40C1F0`
- Localized `Technologies`: ID `0xF3`
- Localized `Villager Detail`: ID `0x177`
- Localized `Tech Points Available`: ID `0x62`

The Tech constructor's existing button sequence near
`0x465083..0x4650E4` and the Detail constructor's sequence near `0x46CDD9`
are the stock patterns to reproduce.

## Implemented hook and composition map

- Payload cave: file `0xA3180`, VA `0x4A3180`; generated payload uses less than
  the verified `0xE80` zero-filled mapped region.
- Food hook: `0x4263F0`
- Tech hook: `0x427130`
- Tech constructor epilogue: `0x46547D`
- Tech message-handler entry: `0x465640`
- Detail constructor epilogue: `0x46DA2C`
- Detail message-handler entry: `0x46E530`
- The read/write flag is added only to the existing `.rdata` section; section
  layout is unchanged.
- Every hook has an exact stock-byte guard.
- Rendering recomputes a nonzero PE checksum.
- Automated composition covers every current VV3 fun patch in all four
  population modes, including both experimental 256 modes.

The native Barrel presentation mirrors the stock scheduler exactly: it
initializes the registry with `sub_419AC0`, allocates the stock `0x868`-byte
dialog object, constructs it with `sub_4192F0`, checks byte `+76`, presents it
with `sub_401AF0(owner, 0)`, marks event index 57 seen, destroys it with
`sub_418460`, and restores the complete stack allocation.
