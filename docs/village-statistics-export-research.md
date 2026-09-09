# Village Statistics text-export research

## Cross-game Villagers Buried and Oldest Villager boundary

Exact-build audit `7fe0a047706693d69c9b504f7a7b0b014280dee3`
supersedes the earlier burial-hook interpretation below.

In all five games, stock **Oldest Villager** exports the persisted lifetime
maximum. It does not rescan living villagers, dead or skeleton records,
graves, mausoleums, the VV3 Roster of the Dead, or another current memorial
collection. Stock-layout export is proved; expanded-256 walker coverage
remains ON HOLD.

The future **Villagers Buried** counter must increment exactly once at the
earliest successful skeleton pickup, regardless of later graveyard or
mausoleum capacity, completion, occupancy, or burial success. Known delayed
grave/removal/record-retirement sites are downstream and insufficient.

The former VV3/VV4/VV5 burial detours at raw `0x5F45B`, `0x664DC`, and
`0x6FF12` are withdrawn and absent from the statistics generators and
manifests. Those exact stock guard bytes are preserved; no wrapper or payload
owns them. Memorial migration and any replacement burial hook remain **ON
HOLD** until an earliest-successful-pickup route and atomic save migration are
proved. Oldest Villager exporters and unrelated food/conversion hooks remain
active where independently certified.

A retroactive retained-memorial count may initialize a one-time lower-bound
baseline only with a dedicated, atomic, save-scoped initialized marker.
Initialization stores the baseline and marker together; later successful
pickups increment the saved counter. Export must never repeatedly add current
memorial counts. VV2 `state+0x2E514` is **Village Elders** and is forbidden
for buried migration, ownership, or initialization state. Exact pickup hooks
and safe migration storage remain ON HOLD.

## Confirmed local lifetime statistics

### A New Home

VV1's reachable local Statistics screen is `sub_431B30`. Its persisted manager
fields are:

| Statistic | Manager offset |
|---|---:|
| Points Earned | `+0x9E20` |
| Babies Made | `+0x9E24` |
| Food Gathered | `+0x9E28` |
| People Cured | `+0x9E2C` |
| Mushrooms Found | `+0x9E30` |
| Maximum Population | `+0x9E34` |
| ~~Villagers Buried~~ | ~~`+0x9E38`~~ **NOT a lifetime total and no longer exported.** It is a live recount that saturates at the 50-slot memorial; see the correction below. The exported row reads the patch-added counter at `+0x9E84` instead. |
| Oldest Villager | `+0x9E3C` |
| Island Events Seen | `+0x9E40` |
| Twins Birthed | `+0x9E44` |
| Triplets Birthed | `+0x9E48` |

Real Hours Played is calculated by `sub_41D0E0(manager)`. Puzzles Solved is
calculated from the sixteen persisted puzzle flags.

The block at `+0x9EEC` through `+0x9F1C` belongs to the separate Internet
statistics display and is not a substitute for the local values.

### The Lost Children

VV2 retains the corresponding local lifetime counters:

| Statistic | Manager offset |
|---|---:|
| Points Earned | `+0x2E4FC` |
| Babies Made | `+0x2E500` |
| Food Gathered | `+0x2E504` |
| People Cured | `+0x2E508` |
| Mushrooms Found | `+0x2E50C` |
| Highest Population | `+0x2E510` |
| Village Elders | `+0x2E514` |
| Oldest Villager | `+0x2E518` |
| Island Events Seen | `+0x2E51C` |
| Special Stews Found | `+0x2E520` |
| Triplets Birthed | `+0x2E524` |

Real Hours Played is calculated by `sub_425A90(manager)`. Puzzles Solved is
calculated from the sixteen persisted completion bytes at `+0x2E768`,
`+0x2E770`, `+0x2E778`, `+0x2E780`, `+0x2E788`, `+0x2E790`, `+0x2E798`,
`+0x2E7A0`, `+0x2E7A8`, `+0x2E7B0`, `+0x2E7B8`, `+0x2E7C0`, `+0x2E7C8`,
`+0x2E7D8`, `+0x2E7E0`, and `+0x2E7E8`.

## The later games retain the inherited lifetime block

The initial UI-led inspection was incomplete. VV3 through VV5 do not expose the
old local Statistics screen, but all three still initialize, serialize, and
restore its inherited `0x98`-byte per-save block:

| Game | Runtime block | Saved manager copy |
|---|---:|---:|
| The Secret City | `0x5824A0` | `+0x4EC` |
| The Tree of Life | `0x4D6DE0` | `+0x850` |
| New Believers | `0x51D358` | `+0x7B4` |

The common layout is:

| Offset | Statistic |
|---:|---|
| `+0x00` | save/session creation-time anchor |
| `+0x04` | Points Earned |
| `+0x08` | Babies Made |
| `+0x0C` | Food Gathered |
| `+0x10` | People Cured |
| `+0x14` | Mushrooms Found in VV3/VV5; Collectibles Found in VV4 |
| `+0x18` | Highest Population |
| `+0x1C` | Village Elders |
| `+0x20` | Oldest Villager |
| `+0x24` | Island Events Seen |
| `+0x28` | **Twins Birthed** (the exporter printed "Special Stews Found" here until the correction below) |
| `+0x2C` | Triplets Birthed |

`+0x1C` was previously documented here as Villagers Buried, inherited from VV1's
layout. That was wrong, and the correction matters because it changes what has
to be built rather than merely what a row is called.

Each executable carries its own statistics table pairing an internal enum name
with the string it draws, and the enum names were kept across sequels while the
displayed statistic changed:

    eTotemsMade      -> "Village Elders"        (not Villagers Buried)

VV2's `+0x2E514` is confirmed **Village Elders**, and confirmed from the game's
own UI rather than from the enum name: the statistics screen builder
`sub_43F860` pushes label string id `0x368` at `0x4407EF` and reads the field at
`0x44082A` seven instructions later. Id `0x368` is literally `"Village Elders"`
(EN pointer `0x48F378`), sitting between `0x367` "Highest Population" and
`0x369` "Oldest Villager". So the row-to-field pairing is read off the builder,
not inferred.

So VV2 through VV5 do not have an unmaintained Villagers Buried slot waiting to
be populated -- they have no such counter at all. VV1 is the only game whose own
table lists Villagers Buried.

**Villagers Buried for VV2-VV5 is therefore a NEW counter** that must be built
and stored by this project, not a stock field to be repaired. The mutation-site
analysis below still applies to building it, but its premise that the
destination slot already exists does not.

### Correction: `+0x28` is Twins Birthed, and the enum name was right

An earlier revision of this section recorded

    eTwinsBirthed    -> "Special Stews Found"   (not Twins Birthed)

on the reasoning that the displayed string was authoritative and the enum name
was stale inheritance. **That was backwards.** The disassembly shows `+0x28` is
incremented inside the childbirth routine, on the twins branch:

    VV3  0x455BE7  inc dword_5824C8      in sub_455AB0, after `mov [litter], 2`
    VV4  0x45E8DD  add dword_4D6E08, 1   in sub_45E7B0, after `mov [litter], 2`

Both are mutually exclusive with the `+0x2C` write, which follows
`mov [litter], 3`. At most one fires per conception: the litter field is
initialised to 1 (VV3 `0x455B7C`, VV4 `0x45E87D`), and the multiple-birth
guards (VV4 `0x45E88F`, `0x45E89E`) branch past both increments, so a
singleton conception writes neither counter. Exactly one fires when the
litter is twins or triplets, and neither otherwise.

That distinction is worth stating explicitly because **the singleton birth
path is this codebase's reliable odd-one-out**. It has now been the case a
claim failed to cover three separate times: a conception hook placed only on
the multiple-birth tails silently dropped singleton births; a `cave_va`
reassignment broke only the singleton trampoline, while a check covering the
two tail trampolines passed; and the "exactly one fires per conception"
claim above was true for multiples and false for singletons. For any
*exactly one* / *always* / *never* claim about the birth path, enumerate the
cases the model does not name -- the default path and the empty case -- and
check those first rather than last.

The alignment does not rest on `+0x28` alone. Every neighbouring label was
matched to the shape of the code that writes it, and only `+0x28` fails to fit:

| Offset | Label | Code shape | Fits |
|---|---|---|---|
| `+0x08` | Babies Made | `add ..., ecx` -- adds the *litter size* | yes |
| `+0x14` | Mushrooms / Collectibles | `cmp ..., 1F4h` (500 cap) | yes |
| `+0x18` | Highest Population | load / max / store | yes |
| `+0x20` | Oldest Villager | load / max / store | yes |
| `+0x24` | Island Events Seen | plain increment | yes |
| `+0x28` | "Special Stews Found" | `inc` on the twins branch of childbirth | **no** |

Two games, two different encodings (`inc` vs `add ,1`), the same answer.

**The generalisable lesson:** this project's rule is that *a counter's name is
not evidence of its trigger*. A displayed string is a name too. The earlier
revision applied the rule to the enum name and exempted the display string; the
rule applies to both, and only the write site is evidence.

**Consequence for the shipped exporter, now corrected:** VV3/VV4/VV5 printed
the twins-birth count under a "Special Stews Found" label. Both later-game
writers now print **Twins Birthed**, which is what the requirements ask for in
all five games; The Lost Children keeps its own Special Stews Found row, whose
value comes from a different field entirely (`manager+0x2E520`, the
unique-recipe gate). The companion DLL was rebuilt and
`data/statistics_features.json` regenerated so the shipped binary carries the
corrected string, and `tests/test_statistics_offsets_match_the_research.py`
pins both writers against a regression to the stale enum-name mapping.

**Consequence for planned work:** VV3/VV4/VV5 twins totals already exist *and
already persist*, so no new counter, field, or hook is needed for them. Only
VV2 lacks a twins counter -- its twins branch at `0x44BA82` sets litter size 2
and increments nothing.

### The block is persisted, and how that was missed

The statistics block is copied wholesale between a live global and the saved
manager copy:

    VV3  save  sub_4264A0: dest = manager+0x4EC, src = dword_5824A0, `rep movsd`, ecx = 0x26
         load  sub_426480: dest = dword_5824A0,  src = manager+0x4EC, same
    VV4  live block dword_4D6DE0, same shape

38 dwords (152 bytes) flat in both directions. An earlier analysis concluded
these counters were "never read, so session-scoped, resetting each launch",
because a per-address xref scan found exactly one reference to each -- the
write. **That was a scanning artifact, not a fact about the game:** a bulk
`rep movsd` over the whole block is invisible to per-address xref scans. Any
future claim that a block field is unread must account for bulk copies.

The block range `+0x30..+0x97` has no direct stock code references in any of the
three games. It is still zeroed, serialized, and restored, but the current
implementation uses one proven field in that reserve for VV5:

- `runtime 0x51D38C`, statistics `+0x34`, saved manager `+0x7E8` stores the
  patch-added **Heathens Converted** lifetime total.
- The exact successful-conversion entry is `sub_4668B0`. Its original first
  six bytes are `83 EC 10 56 8B F1`.
- At function entry, the original Heathen tag is still present at villager
  record `+0x1CFC`. Tag `17` is the Heathen Mommy, so that conversion adds two;
  every other successful conversion adds one. Stock subsequently clears most
  tags, so the test must happen before the original conversion body resumes.
- The first reserve dword at runtime `0x51D388` remains exclusively owned by
  the Origins feature's saved bit flags. The conversion total uses the next
  dword and does not overlap it.
- Existing saves begin this new total at zero. The counter is not retroactive.

VV4 and VV5's threshold-limited achievement trackers are not used as
substitutes for these uncapped lifetime totals.

### Historical proposed writers and current status

| Game | Statistic | Exact stock route patched |
|---|---|---|
| VV3 | Villagers Buried | **insufficient downstream site**: delayed corpse-record retirement at `0x45F45B`, not the required successful-pickup hook |
| VV4 | Food Gathered | final central food delta at `0x41D987`; guard `01 37 8B 07 79 0B` |
| VV4 | Villagers Buried | **insufficient downstream site**: delayed corpse-record release at `0x4664DC`, not the required successful-pickup hook |
| VV5 | Food Gathered | final central food delta at `0x41EBA7`; guard `01 37 8B 07 79 0B` |
| VV5 | Villagers Buried | **insufficient downstream site**: delayed corpse-record release at `0x46FF12`, not the required successful-pickup hook |
| VV5 | Heathens Converted | successful conversion entry at `0x4668B0`; guard `83 EC 10 56 8B F1`; tag 17 adds two and all other tags add one |

The food detours count only positive final deltas and reproduce the stock
negative-underflow branch. Historical burial detours run at delayed
record-release/retirement sites and cannot satisfy the required
earliest-successful-skeleton-pickup contract.

### Later-game puzzle counts

- VV3 stores the sixteen story-puzzle progress values at
  `manager+0x11ED8+8*id`, IDs 0 through 15. The thresholds at RVA `0x9D230`
  are `1, 1, 5, 700, 1, 1, 1800, 1400, 2, 1, 1, 6, 1, 1, 1, 1`.
- VV4 calls predicate RVA `0x38960` with puzzle manager RVA `0xD8BF8`, IDs
  0 through 15.
- VV5 stores progress at `manager+0x16D20+8*id`, with thresholds at RVA
  `0x11DF30`. Stock counts IDs 1 through 16. When the Heathen Parent patch
  marker at RVA `0x8F16` is active, the exporter counts ID 17 and reports a
  denominator of 17.

## Safe update points

The text file should be refreshed after each successful full-save call. This
includes a normal close-time save without depending on an unproven
process-termination route, and it avoids exporting state from a failed or
partially normalized save.

| Game | Full-save wrapper | Wrapped call | Resume |
|---|---:|---:|---:|
| The Secret City | `sub_427C60` | `sub_403530(this, this+8, 77596, slot)` | after successful call |
| The Tree of Life | `sub_41F030` | call at `0x41F13A` to `sub_4039B0` | `0x41F13F` |
| New Believers | `sub_4244F0` | call at `0x4245FA` to `sub_403940` | `0x4245FF` |

For VV4 and VV5, a detour must replace the five-byte full-save call itself and
return to the existing post-call instruction. The wrapper must preserve the
writer's Boolean result and export only after success. Slot-zero uses a
separate path and must not trigger a village-statistics export.

## Fields still blocked on exact evidence

The following requested totals were not added in this pass because no exact,
uncapped lifetime storage field and mutation route have yet been proven:

- Village Elders where the inherited statistics block does not already expose
  it.
- Villagers Died in **A New Home, The Lost Children and The Tree of Life**.
  Only The Secret City and New Believers ship the counter; see "Villagers
  Died" below for why the others do not, and what completing them needs.
- Total Stews Made in VV2 through VV4. VV2's **Special** Stews Found ships and
  is understood (see below, including the first-cook case where it undercounts
  by one until the recipe is cooked again), but the requirements list *Total*
  Stews Found "with no herb-combination restriction" as a **separate** VV2
  statistic, and no writer that increments for every stew has been found. The
  two must not be conflated.
- Tribal Chiefs Robed in VV3.

Threshold-limited achievement counters are not accepted as substitutes for
these uncapped lifetime totals.

### Villagers Died

**Shipped for The Secret City and New Believers.** Both keep health and the
cause of death in a small sub-object, and every death routes through one of
two sibling arbiters that write that pair:

| Game | Absolute setter | Delta applier | Sub-object | Health | Cause |
|---|---|---|---|---|---|
| The Secret City | `0x462670` | `0x4626B0` | `+0xE6C` | `+0xE78` | `+0xE7C` |
| New Believers | `0x4758B0` | `0x4758F0` | `+0x1C34` | `+0x1C40` | `+0x1C44` |

The Tree of Life has the same shape and is **not yet shipped**; another
session holds that work. Its arbiters are `0x46AF00` (absolute,
`mov [ecx+0x0C], eax`) and `0x46AF40` (delta, `add [ecx+0x0C], eax`), verified
from the stock bytes along with the kill guards `C7410C00000000` at `0x46AF0F`
and `0x46AF52` -- byte-identical to the two shipped games -- and the alive
paths `mov [ecx+0x10], -1` at `0x46AF28` and `0x46AF6B`. The cause write
follows the hook site at both (`0x46AF16`, `0x46AF59`), which is what lets a
`cause == -1` gate read the prior value; that ordering reads as incidental and
is the whole reason the gate counts anything.

**Its record offsets are `+0x1C34` / `+0x1C40` / `+0x1C44` -- identical to New
Believers, and genuinely so.** This looks exactly like a row copied from the
game above, and was checked on that suspicion: The Tree of Life really does
carry `lea ecx, [esi+1C34h]` and `cmp dword ptr [esi+1C40h], 0` in its own
callers. Two games of the same engine lineage share the layout. The usage
counts differ (23 references to `+0x1C40` against New Believers' 40), which is
what distinguishes a shared layout from a transcription error.

Both entry points are hooked in each game. They are not alternatives: the
delta form does `add [ecx+0x0C], eax` before testing, so a death by
accumulated damage passes only through it, and hooking the setter alone would
miss starvation and illness entirely.

What proves these are the *sole* arbiter, rather than one route into death
among several, is that the **alive** path explicitly writes `-1` to the cause
field. Every exit of both functions writes that field, so a death cannot slip
past.

That same fact supplies the idempotency gate. The branch above each site tests
the **resulting** health, not the prior, so calling either function again on an
already-dead villager re-enters the death path and would count twice. The
wrapper tests the cause field for `-1` instead: a living villager reads `-1`
and is counted, a corpse reads a real cause id and is skipped. This works only
because the hook precedes the cause write -- at hook time the field still holds
the prior value. A hook placed after that write would read the new cause and
count nothing at all.

Testing the cause rather than the prior health also avoids a per-game
difference: New Believers' delta form adds in place and destroys the prior
value, so a prior-health test would need different code in each game.

**Not shipped for A New Home or The Lost Children, and the reason is coverage
rather than reachability.** Both have a health field and both do kill through
it:

| Game | Health | Cause field | Old-age kill |
|---|---|---|---|
| A New Home | `record+0x344` | none | `0x42EF05` |
| The Lost Children | `record+0x52C` | none | `0x43BDEE` |

Both kill sites share one shape -- the divide-by-ten age arithmetic
(`mov eax, 66666667h`, `imul`, `sar edx, 3`), a `cmp`/`jge`, then the health
store. But that store is only the **old-age** path. Starvation and disease
reach zero health by *decrement* through register-computed pointers inside the
same tick routine, so a hook on the store would report old-age deaths under a
total's name: authoritative-looking and quietly wrong. Neither game has a cause
field to gate on either, so the idempotency trick above does not transfer.

The damage that reaches zero is applied **through a pointer**, which is why no
displacement search finds it and why the image contains no `sub [mem]` for
this field at all. In The Lost Children, inside `sub_43B690`:

    0043BAE4  mov ecx, [eax+edi+52Ch]   read health
    0043BAEB  lea eax, [eax+edi+52Ch]   take its ADDRESS
    0043BAF2  dec ecx
    0043BAF3  mov [eax], ecx            store back -- NO displacement

That routine takes the field's address at seven separate `lea` sites, so the
decrement is only ever reachable behind a register. **Seven address-taking
sites are not seven damage paths**, and hooking all of them would count
healing as death:

| Site | Instruction after the `lea` | Effect |
|---|---|---|
| `0x43BAEB` | `dec ecx` ; `mov [eax], ecx` | damage |
| `0x43BB7E` | `dec dword ptr [eax]` | damage, in place |
| `0x43BBD7` | `inc ecx` ; `mov [eax], ecx` | heal |
| `0x43BC43` | `dec ecx` ; `mov [eax], ecx` | damage |
| `0x43BC59` | `cmp ecx,ebx` ; `jge` ; `mov [eax], ebx` | floor clamp, only raises |
| `0x43BD02` | `inc ecx` ; `mov [eax], ecx` | heal |
| `0x43BD0F` | `cmp [eax],64h` ; `jle` ; `mov [eax],64h` | ceiling clamp |

`0x43BC59` deserves the explicit note because it reads as an ordinary store:
it fires only when health is *below* `ebx` and raises it to that floor, so it
can never lower health. And `0x43BB7E` is a **third** instruction form for
writing this field -- an in-place `dec` with no separate store and no register
holding the value. A guard that reads the pre-value out of `ECX` works at
`0x43BAEB` and `0x43BC43` but has nothing to read at `0x43BB7E`, which must be
read through the pointer before the `dec`. Two guard shapes, not one.

Immediate store, register store-back, in-place `dec`: three forms for one
field, which is the same lesson as the scanning note below arriving a third
time. Image-wide, `0x52C` appears as a displacement 135 times in `.text`, of
which 45 are `lea` sites -- counting them needs both the SIB and ModRM-only
encodings, since assuming one form returns 1. It is the routine boundary that
makes these seven meaningful, not the displacement.

Completing these two games means hooking the zero-crossing at the three damage
sites, with the same count-the-transition-not-the-state reasoning the later
games needed. Counting
burials instead is exact and already shipped, but it is a different quantity
and should not be relabelled.

**A scanning note, because two sessions reached opposite wrong answers here.**
Ground truth for The Lost Children's health field is thirteen writers, exactly
one of which writes zero (`0x43BDEE`, the old-age kill). Two independent method
failures produced confident wrong lists:

- A **linear disassembly pass over the section** desynchronised on embedded
  data and never enumerated `0x43BDEE` at all, while enumerating another store
  in the same section. Nothing about the result looks incomplete.
- Classifying by **operand position rather than mnemonic** turned six
  `cmp dword ptr [reg+0x52C], reg` sites into phantom "writes", because the
  memory operand renders first.

Either alone is enough to close the question wrongly, and the two overlapped
enough to look like a disagreement about a single site rather than two broken
enumerations. The method that survives: **search the bytes for the
displacement, disassemble at each hit, and classify on the mnemonic.** A
positive control pairing the zero write with the `0x64` writes catches the
missing-instruction failure but not the phantom one, so the control is
necessary and not sufficient.

### What The Secret City actually has instead of stews

Worth recording so the search is not repeated. VV3 has no stews: it has an
**Alchemy Lab**, seven herbs (`eObject_Herb1` .. `Herb7` at `0x482294` and
below), and the tip string `"Different combinations of herbs make different
potions."` at `0x490D84`.

The one string implying a unique-combination total is
`"You have concocted 50 unique alchemy recipes"` at `0x49C528`, whose enum
name `eAlchemyRUsDesc` is id `0x4A9` in the `.data` string table at
`0x4ABDB0`; the achievement itself is `eAlchemyRUs`, id `0x4A8`, at
`0x4ABDA0`. Both ids appear at exactly one site each, `0x463EBB` and
`0x463F0B` in `sub_4639C0`, and that function is the achievements *display*
builder: it writes ten consecutive title/description id pairs into a stack
frame. Nothing there evaluates a condition.

Searching for the threshold directly also comes up empty. Thirteen
`cmp <memory>, 0x32` sites exist image-wide and none is an alchemy counter
-- they are unrelated fields at `+0xEAC`, `+0xEB4`, `+0xEB8`, `+0xEBC` and
the global `dword_4B86D8`.

So the achievement text exists while the quantity behind it does not appear
to, which matches the earlier controlled result that neither VV3 nor VV4
carries a discovered-recipe set, a recipe-identity resolver, or a discovery
gate, and that `eTipNewRecipe`'s string id is never referenced by any
instruction in either game. Delivering "Stews Found, including every herb
combination" for these two therefore means inventing the recipe identity and
its storage rather than reading one, which is a different task from every
other counter in this document.

### Corrections to the list above

**VV1's `+0x9E38` is a live recount, not a lifetime total, and is no longer
exported.** It was listed above under confirmed local statistics as *Villagers
Buried* and the exporter emitted it under that label. It has only two writers
image-wide and both are stores rather than increments:

    0x41C3DF  mov [ebp+9E38h], ebx   zero-init
    0x42F191  mov [edx+9E38h], eax   stores sub_41CF10's return value

`sub_41CF10` is an unrolled 5x10 walk that **recounts currently-occupied grave
slots** (base `manager+0xA340`, stride `0x2C`) and returns the total. So the
value saturates at the 50-slot capacity and would fall if a slot were ever
released. It reports present occupancy, not lifetime burials.

**Resolved.** The row now reads the patch-added lifetime counter at
`manager+0x9E84`, which the cave wrapper on the skeleton-pickup latch clear at
`0x448F65` advances, and which is seeded once per save from the memorial so an
existing village does not start from zero. The row keeps its name because the
name was never the problem -- the field behind it was. Every game is now the
same shape: seed once from occupied graves, then count pickups past the
memorial's capacity.

**The later-game "buried" counters decrement.** They were described here as
incrementing when a corpse record is retired, which reads as a usable lifetime
total that merely lags. It is not one. Enumerating every instruction touching
each displacement:

    VV4  +0xBB80   0x45D3F3 cmp ...,1   0x45D450 add ...,-1   0x45D627 add ...,1
    VV3  +0x6810   0x454A35 mov ...,0   0x454E33 cmp ...,1    0x454E85 dec
                   0x4551C7 / 0x4551D1  load / store

Both increment *and* decrement, both are guarded by a `cmp` against 1, and VV3
additionally has an explicit zeroing reset. They are live occupancy counts --
the same disqualification as VV1's `+0x9E38` recount, reached by a different
route. VV5's `+0xBB80` is the population of a **55-slot visible-marker array**
(`0xB3B0`, bound `mov ebp, 37h` at `0x464C05`), which is a different structure
from the 500-slot grave array. So no game has an existing lifetime burial
total, and any such counter must be newly built.

**VV2's SPECIAL Stews Found is solved -- but that is not the Total.** The
requirements list two separate VV2 statistics: *Special Stews Found*, and
*Total Stews Found* "with no herb-combination restriction". What follows
establishes the **first** only. No writer incrementing on every stew has been
found, so *Total* Stews Found stays blocked.

The earlier verdict was recorded against *Total Stews Made* as a **counter**,
and no uncapped counter exists. Re-running the search for a **set** rather than
a counter found the unique-recipe storage:
`manager+0x2EAAC`, 19 bytes, indexed directly by recipe id (ids 1..18, index 0
unused), cleared to exactly 19 bytes by the initializer at `0x425114`. The
"...found an interesting new recipe!" string (id `0x1C7`) sits between the
test and the mark, which is what establishes the array's meaning rather than
its shape.

The counter at `+0x2E520` and that set cannot diverge: on both paths the mark
and the increment are gated together.

    normal path  0x4260B5 test set[id] / 0x4260BE jne exit
                 0x4260D4 mark set[id] / 0x4260DC inc [+0x2E520]
    first cook   0x4260A5 mark set[id] / 0x4260AD jmp -> 0x4260DC inc

So `popcount(+0x2EAAC) == [+0x2E520]` at all times: the counter and the set
never disagree with each other. The row reports unique recipes rather than
stews cooked, so it does not answer "every stew cooked", which is the separate
Total.

It is **not** exact in one case. On the first-cook path only, ids 2, 4 and
`0x12` branch to `0x4260E2` -- the **function tail**, the same target the
"already known" branch uses -- so they skip the mark and the increment
together, leaving the recipe absent from both. Two consequences follow, and
the second is easy to miss:

- The one-time flag at `0x426056` is set *after* the three comparisons, so a
  skipped cook never sets it and the **next** stew takes the first-cook path
  as well.
- The undercount therefore **accumulates**. Every excluded recipe cooked
  before any non-excluded one is skipped in turn, so all three of ids 2, 4
  and `0x12` can be missed in sequence and the row can be short by up to
  three. It is not a single-recipe edge case.
- Recovery is **not automatic**. A skipped recipe is only recorded if it is
  cooked again *after* some non-excluded stew has set the flag, which is what
  finally routes cooking through the normal path at `0x4260AF`. Until then
  `0x4260B5` is never reached for it at all.

So Special Stews Found is exact for any save whose first stew is not one of
those three recipes, and otherwise undercounts by up to three until each
missed recipe is recooked past the flag being set. Worth stating at that size
rather than as a one-off, and it matters before printing a denominator such
as "of 18".

An earlier revision of this section called the undercount "by one" and
"self-correcting on any later cook". Both were wrong, and wrong in the same
direction: they assumed the flag was set on the skipped path, so that only a
single cook could ever be lost and any recook would recover it. The flag is
set past the comparisons, not before them.

**A verdict must name the shape it searched for.** "No counter found" and "no
set found" are different claims, and recording the first as though it were the
second is what kept VV2 blocked. Two further traps cost real time here and are
worth stating:

- *A conditional jump's meaning is its destination, not its position.* Reading
  `cmp` / `jz` before an increment as "skips the increment" was wrong; the
  target was the function exit, so it skipped the mark as well. Resolve the
  target before inferring intent.
- *Matching geometry is not evidence.* A VV4 array with the right record count
  and stride turned out to be the active potion-effect buffer, identified by
  two sites that clear its byte on expiry. Structure can mislead exactly as a
  label can; what the code does with the field is the evidence.

## The memorial arrays, and what a count of them can honestly claim

Each later game keeps its dead in a flat array behind a small bounds-checked
accessor, and each accessor states the whole layout in a handful of
instructions.

| Game | Accessor | Base | Slots | Stride | Occupied when |
|---|---|---|---|---:|---|
| The Secret City | `0x454AD0` | `0x597D64` | 500 | `0x30` | `record+0x1C != 0` |
| The Tree of Life | `0x45D650` | `0x5025C8` | 500 | `0x5C` | `record+0x1C != 0` |
| New Believers | `0x464E70` | `0x5481A8` | 500 | `0x5C` | `record+0x1C != 0` |

VV4's and VV5's accessors are instruction-for-instruction identical. VV3
computes the record with `lea`/`shl` instead of `imul`:

    0x454ADF  lea edx, [eax+eax*2+99h]   ; 3i + 0x99
    0x454AE6  shl edx, 4                 ;   x16 = 48i + 0x990
    0x454AE9  cmp dword ptr [edx+ecx], 0 ; occupancy
    0x454AF5  lea eax, [eax+ecx+974h]    ; base = container 0x5973F0 + 0x974

so a scan shaped on VV4's `imul` cannot find it. VV3 was reached from the Roster
Of The Dead string table instead, and confirmed by three other functions that
walk the same array: the burial writer `0x454FF0`, the clear `0x4549F0` and the
copy `0x454930`, each stepping `0x30` for `0x1F4` records.

The burial writers fill the FIRST record whose `+0x1C` is zero — VV4 `0x45D470`,
VV3 `0x454FF0` — copying the villager's name and their age at death.

### What the count means, and what it does not

`+0x1C` holds the age at death AND serves as the occupancy test. Because the
writer takes the first free slot, a slot is reusable once something clears it.
Nothing has been found that clears one, but that is an absence of evidence, and
a 500-slot array cannot hold an uncapped lifetime total in any case.

The export therefore reports **graves currently held**, not villagers buried and
not a lifetime death count. Those quantities genuinely diverge: a villager can
die without being buried, and the array is bounded while deaths are not. This
does **not** satisfy the Villagers Buried contract stated at the top of this
document, which requires an increment at the earliest successful skeleton
pickup; nothing here changes that item's status.

A villager buried at age zero would leave its record reading free, and the next
burial would overwrite it. The repository owner confirms that state is
unreachable in ordinary play and requires external memory editing to produce —
age forced to zero, then health to zero. The executable agrees: VV4 compares
`+0x1B8C` against `0x118` and `0x168` at nine sites as a maturity threshold, so
it is an age that grows before any death path is reached.

### Method note

Every address above was established with a positive control: the same method was
run first against VV4, where the site was already proven, and required to find it
before any result elsewhere was believed. That discipline earned its keep — the
VV3 scan passed its VV4 control and still returned a false negative on VV3, which
is how the null was recognised as a fact about the scan rather than about the
game.
