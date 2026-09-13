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

- Village Elders in **A New Home only**. The Lost Children exposes it at
  `+0x2E514`, and the later three games at `+0x1C` of the inherited block, so
  all four already ship the row. A New Home does not have the field: its
  statistics run is `+0x9E20` through `+0x9E48` with every slot accounted for,
  and the slot its successors use for Village Elders holds the saturating
  memorial recount instead -- the layouts diverge there rather than one being
  a superset of the other. The `Elderly` string in that executable is a
  villager health and age status, not a counter, and the remaining matches are
  German and Spanish words containing "elder" by coincidence. Completing this
  needs new storage plus a hook, not a field that is waiting to be read.
- Villagers Died in **A New Home and The Lost Children**. **Closed at
  proportional cost, not blocked on evidence** -- and both are now measured
  rather than one measured and one asserted to match: 19 hooks for A New Home,
  24 for The Lost Children, with no convergence point in either. Both call for
  the same judgement about whether a row is worth that cost.
  The Secret City, The Tree of Life and New Believers ship the counter; see
  "Villagers Died" below for why the other two do not, and what completing
  them needs.
- Total Stews Made in VV2 through VV4. VV2's **Special** Stews Found ships and
  is understood, but the requirements list *Total* Stews Found "with no
  herb-combination restriction" as a **separate** VV2 statistic. The Lost
  Children does not persist such a count anywhere -- established exhaustively
  in "Why The Lost Children has no total stew count" below, which also gives
  the exact mechanism of `+0x2E520` and what a hook satisfying the requirement
  would have to cover. The two must not be conflated.
- Tribal Chiefs Robed in VV3. **This one is different in kind from the others
  above.** See "Tribal Chiefs Robed" below: the mechanism that records a chief
  is a one-shot latch and cannot represent a count, and the game's own accessor
  reads it as a boolean. What is *not* established is that no separate lifetime
  counter exists elsewhere -- see the stated limit at the end of that section.
  The entries above are blocked on finding a writer; this one is blocked on the
  storage the known writer uses, which is a different question and points at a
  decision rather than more of the same search.

Threshold-limited achievement counters are not accepted as substitutes for
these uncapped lifetime totals.

### Tribal Chiefs Robed

**VV3 does not maintain this quantity, and cannot be read for it.** Robing a
chief is a story puzzle, and every puzzle is a saturating progress value behind
a one-way latch.

    sub_435990  AdvancePuzzle(id)              the only incrementing route
        0x435999  call 0x4358D0                ; IsComplete(id)
        0x43599E  test al, al
        0x4359A0  jne  0x4359D0                ; already complete -> no write
        0x4359A2  mov  edx, [edi+esi*8]
        0x4359A5  inc  edx
        0x4359A6  mov  [edi+esi*8], edx

The chief is puzzle id 1, whose threshold is 1. The single advance takes
progress from 0 to 1, which equals the threshold and marks it complete, so
every later robing hits the `jne` and returns. The stored value cannot
represent two: it is not a counter that saturates at one, it is a latch.

The game agrees. Its own accessor is a boolean:

    0x415030  push 1 ; mov ecx, 0x594990 ; call 0x4358D0
    0x41503C  test al, al ; setne al ; ret

`setne` collapses the stored value to 0 or 1, and two of its callers pair it
with `cmp [0x5945E0], 0xA`, the tribe-size influence rule. Nothing in the image
reads a chief quantity.

The advancing site is the robe fitting `sub_431A40`, whose `cmp eax, 0x1F` at
`0x431AB0` forks into the game's own "The robe fits!" and "The robe does not
fit" outcomes; the success branch ends at `0x431B7E push 1 ; call 0x435990`.
That is the only site in `.text` that advances puzzle 1.

`tests/test_vv3_chief_puzzle_is_a_one_shot_latch.py` pins all of the above,
and each of its assertions was validated against a mutated known-bad copy.

**Two dead ends recorded so they are not walked again.** The string route is
closed by design: "The robe fits! The chosen one has been found." at `0x4926BD`
has zero `.text` references because tips are fetched by resource id, so finding
no references says nothing about whether a counter exists. And the table of
handler initialisers at `0x49D298` must not be used to derive puzzle ids -- no
instruction subscripts it, and it holds 25 entries against the 26 in the tables
that *are* subscripted (`[reg*4 + 0x49D230]` and `[reg*4 + 0x4B0D88]`). An
earlier draft of the test above derived the chief's id from an index into it
and reached the right answer for an unsound reason.

Adding the row would therefore mean this project storing its own count, which
is a new counter rather than a repair -- the same situation as Villagers Buried
for VV2 through VV5, and needing the owner's decision rather than more
research.

### What this does NOT establish

The evidence above is about the puzzle slot: it is a latch, and the accessor
reads it as a boolean. **It is not a proof that no separate lifetime counter
exists anywhere in the image.** An earlier revision of this section said the
quantity "does not exist in the game, and no amount of further searching will
find it", which claimed more than was measured.

Every write on the robe fitting's success path targets `[esi+...]`, the puzzle
object's own fields. Its eight callees were then checked for references to the
persisted statistics block -- and that check is **not usable**, because it
failed its own positive control: `sub_4264A0` provably copies the block and the
scan did not flag it. The block arrives there in `ECX` from the caller, so a
callee scanned for the literal address can never match. A method that cannot
find a known-present case says nothing about absence.

Closing the row on "no separate counter exists" therefore needs an argument
this section does not have. What it does have is enough for the decision: the
mechanism the game actually uses cannot hold the number, so shipping the row
means adding storage regardless of whether some other field happens to exist.

### Villagers Died

**Shipped for The Secret City, The Tree of Life and New Believers.** All three
keep health and the cause of death in a small sub-object, and every death
routes through one of two sibling arbiters that write that pair:

| Game | Absolute setter | Delta applier | Sub-object | Health | Cause |
|---|---|---|---|---|---|
| The Secret City | `0x462670` | `0x4626B0` | `+0xE6C` | `+0xE78` | `+0xE7C` |
| The Tree of Life | `0x46AF00` | `0x46AF40` | `+0x1C34` | `+0x1C40` | `+0x1C44` |
| New Believers | `0x4758B0` | `0x4758F0` | `+0x1C34` | `+0x1C40` | `+0x1C44` |

The Tree of Life shares New Believers' field offsets exactly, which looks like
a transcription error and is not: the two are the same engine lineage, and the
usage counts differ (23 references to `+0x1C40` against 40) in independent
binaries; the paragraph below cites the instruction that proves it. Both are
hooked, because a death by cumulative damage reaches zero
only through the delta applier. The hooks sit at
the health-zeroing store in each (`0x46AF0F`, `0x46AF52`), which runs
before the cause write two instructions later -- so the wrapper still sees
the PRIOR cause and counts the transition once. Its counter is at +0x48 of
the live block rather than the +0x40 the other two games use, because
+0x40 is this game's burial marker: the reserve layouts are not parallel
and the offset cannot be ported.

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

**A New Home has now been measured the same way as The Lost Children, and it
lands in the same place.** Until this was done the document asserted parity
between the two games without a count for the first, which read as though both
had been examined to the same depth when only one had.

| | A New Home | The Lost Children |
|---|---|---|
| health field | `record+0x344` | `record+0x52C` |
| sites touching the field | 88 | 130 |
| direct writers (memory as destination) | 9 | 13 |
| of those, storing literal zero | `0x42EF05` | `0x43BDEE` |
| lethal `lea`-mediated sites | **18** | **23** |
| total hooks incl. the old-age store | **19** | **24** |

The instruction families overlap -- both games have the randomiser shape and
the interleaved-pops shape -- but A New Home's damage is enumerated below in
**six** distinct forms against The Lost Children's four, so the games are alike
in *kind* of difficulty and not in the number of guard shapes a hook would need
to argue.

The two shared shapes are the randomiser, where a `call` separates the address
computation from the subtraction (`0x43A5A8`:
`lea ebx,[edx+esi+344h] ; call 0x402F10 ; sub [ebx],eax`), and the one where
pops are interleaved between the load and the store-back (`0x42C2A6`:
`lea ; mov ecx,[eax] ; pop edi ; add ecx,-0Fh ; pop esi ; mov [eax],ecx`).

**The convergence route is closed for A New Home too, and it needed the same
control to close honestly.** Walking flow forward from the 18 sites gives eleven
distinct callees with the most-shared reached from **13 of the 18** -- which
again looks exactly like a shared death handler. It is not one: `0x402F10` is
the bounded RNG helper (`cmp esi,7FFFh ; jg`, then `cdq ; idiv esi`) with **917
callers image-wide**, and the next two, `0x402F70` (92 callers) and `0x43A130`
(31), are the clock helper and a slot-scan loop. Structurally identical to The
Lost Children's `0x4031A0`/`0x403200`/`0x44B2A0` at 1551/137/71.

**A counting note that cost a wrong set.** A first pass also returned 18, but a
*different* 18: it counted `0x448624` as damage on a `cmp dword ptr [esi], 0`,
which only reads through the pointer, and missed `0x43B387`. The totals agreed
while the membership did not, so comparing counts would have confirmed a wrong
answer. Sites are only comparable as **address sets**; a site is lethal only
when the same register the `lea` loaded is the destination of a *reducing*
write.

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

The two games do **not** cost the same to complete, and the sites in the table
above are `sub_43B690`'s alone rather than the game's. Neither game is finished
by hooking them: each also needs its old-age store, which is a separate path.

**The Lost Children is NOT completable at a cost proportional to one row, and
the set is now settled at 23 lethal sites plus the old-age store, 24 hooks in
all.** The table above enumerates `sub_43B690`, and an earlier
revision of this paragraph read it as enumerating the game. It does not: damage
paths with their own death checks sit outside that routine, and every count
offered so far has been revised upward on re-examination.

Four such sites are verified individually and are listed below as **examples
that disprove the three-site claim, not as a complete set**. Two later searches
found families that earlier passes could not see -- one where the damage sits
past a `call` (`0x462990`: `lea ebp,[edx+esi+52Ch] ; call ; sub [ebp],eax`) and
one where pops are interleaved between the load and the store-back
(`0x43909F`: `lea ; mov ecx,[eax] ; pop ; add ecx,-0Fh ; pop ; mov [eax],ecx`).
Both are real reductions; both were dropped silently by classifiers that
recognised only the shapes they had been written for.

So VV2 belongs in **A New Home's category rather than The Secret City's**: the
damage paths are many and the arbiter-shaped design that fits the later three
games does not apply.

The count is now settled. Two sessions rebuilt their classifiers so that every
site lands in a named bucket -- with the unclassified bucket asserted empty
rather than silently discarded -- ran them independently from opposite starting
points, and **diffed the address sets rather than the counts**:

| | |
|---|---:|
| `lea` sites taking the health field's address | 45 |
| of those, sites that **reduce** health | 25 |
| of those, sites that can reach **zero** | **23** |
| distinct instruction forms among them | 4 |

The sets were identical. The 23 are `0x420E16`, `0x421013`, `0x433367`,
`0x4375E7`, `0x43909F`, `0x4392CC`, `0x4393DC`, `0x4394EC`, `0x43BAEB`,
`0x43BB7E`, `0x43BC43`, `0x44EE21`, `0x462990`, `0x462ACD`, `0x462C05`,
`0x462D3C`, `0x462E78`, `0x462F8A`, `0x46308D`, `0x463638`, `0x4638DA`,
`0x46403E` and `0x4641A7`. Twelve share the randomiser shape
`lea ; call 0x4031A0 ; sub [ptr], eax`.

**The convergence route is closed as well**, measured rather than assumed. If
the deaths funnelled through a shared handler, the reads of health followed by
a `<= 0` test would collapse onto a few targets. Two independently written
scanners agree that they do not:

    56 checks, 48 distinct targets, largest cluster 5
    59 checks, 50+ distinct targets, largest cluster 3

Fifty-odd places ask whether a villager is dead, and the most popular
answer-site is reached from five of them. That one is `0x43BD21`, `sub_43B690`'s
own exit -- **a chokepoint does exist, it is simply local to one routine out of
many**, and generalising from it is the error that produced every earlier count.

Immediate targets alone do not settle this, though, since separate blocks can
still converge later or call a common routine. So flow was walked forward from
each of the 23 sites, through unconditional jumps and both edges of
conditionals, recording every `call` reached. Twelve distinct callees turn up
and the most-shared is reached from **16 of the 23** -- which looks exactly like
the shared handler the design wanted.

It is not one. `0x4031A0` is a bounded random-number helper (`test/jle`,
`cmp 0x7FFF/jg`, then `cdq ; idiv esi`) with **1551 callers image-wide**: it is
reached from 16 death sites because it is reached from nearly everything. The
next two, `0x403200` (137 callers) and `0x44B2A0` (71 callers), are a clock
helper and a slot-scan loop, on the same argument. **Caller count is the control
that separates a shared handler from a shared utility**; without it a downstream
trace yields a convincing false positive. No callee is reached from all 23, and
none of the shared ones is death-specific.

Three independent grounds therefore close this row, any one of which would make
it disproportionate: 23 lethal sites across four instruction forms each needing
its own guard, plus the old-age store for 24 hooks in all; no convergence point
to hook instead, neither at the branch targets nor downstream of them; and 35 bytes of worst-case
contiguous free `.text` on the composed image with every VV2 feature selected,
measured on the built output rather than on stock.

| Site | Instruction | Death check |
|---|---|---|
| `0x420E16` | `add dword [eax], -0x14` | `0x420E39` `cmp [eax],ebx ; jge` |
| `0x421013` | `add dword [eax], -0x0A` | `0x421036` `cmp [eax],ebx ; jge` |
| `0x433367` | `sub [eax], ebp` | `0x43337D` `test ecx,ecx ; jge ; mov [eax],0` |
| `0x4375E7` | `sub [eax], ebp` | `0x4375FD` `test ecx,ecx ; jge ; mov [eax],0` |

A hook set built from `sub_43B690` alone misses all four, and misses the two
families named above as well, which is a silent undercount shipped under a
total's name -- the failure this document refuses for A New Home, and worse
here because it would ship looking complete.

Two sites must be **excluded deliberately** rather than omitted, since an
address absent from a list is indistinguishable from one nobody examined:

- `0x46116C` -- `dec ecx ; cmp ecx,3 ; mov [eax],ecx ; jge ; mov [eax],3`
  floors at **three**, so it can never reach a death state. A
  count-the-transition gate never fires there, which makes it harmless *by
  accident*: change that constant and the gate silently starts counting.
- `0x4614DA` -- `edx = -15 - rand() ; add ; cmp eax,3 ; jge ; mov [esi],3`
  reduces health and clamps it to three on the same path, so it is damage
  that cannot kill.

Hooking either would report a death that never happened. **A false positive in
a shipped counter is worse than a missing site, because it looks like data**
and nothing downstream can distinguish it from a real death.

`0x44EE21` was listed here in an earlier revision as "guards on the sign flag
and is not a death path". **That was wrong and it is one of the 23**, and two
independent readings of the same eleven bytes say so.

**From the ordering.** The `jns` sits at `0x44EE2D`, *after* the store at
`0x44EE2B`, so it branches on a result already written rather than preventing
the write. A guard that prevents a death has to come before the store; one that
comes after is an observation of the outcome.

**From the fall-through.** `jns` is taken when the result is non-negative, so
the fall-through is *exactly* the case where health went below zero -- and what
sits there is a repair:

    0044EE2B  89 08   mov [eax], ecx     the reduction, committed
    0044EE2D  0f 89   jns 0x44F448       survived -> leave
    0044EE33  5f 5e 5d                   pop edi ; pop esi ; pop ebp
    0044EE36  89 18   mov [eax], ebx     the clamp
    0044EE38  5b      pop ebx

`ebx` is never assigned anywhere in this routine -- the only instruction naming
it between the `push ebx` prologue at `0x44EDF0` and here is the matching
`pop` -- so the clamp writes back the **caller's** value. Callers pass zero for
a floor.

The two arguments are independent and answer different questions. Ordering
proves the branch is *too late*; the clamp proves **the authors expected the
value to go negative** and wrote code to catch it. Intent rather than sequence,
from a different feature of the same bytes.

The reduction itself, `add ecx, -0x5A`, is unclamped on the path that matters.

Four guard shapes are required, not two: a pre-value in a register (`0x43BAEB`,
`0x43BC43`); the in-place `dec` at `0x43BB7E` whose pre-value must be read
through the pointer first; read-modify-write through a `lea`-ed pointer with the
test *after* (`0x433367`, `0x4375E7`); and the randomiser form, where a `call`
separates the address computation from the subtraction (`0x462990` and eleven
siblings). Plus the old-age store at `0x43BDEE`, which no decrement reaches
and which is therefore **additional to the 23**: a complete death implementation
is 24 hooks, not 23.

A design proposing one wrapper for all sites was withdrawn on this basis. It
rested on every damage site opening with a 7-byte `lea` that leaves the health
pointer in `eax`. That is not a rule with an exception; classifying every `lea`
in `.text` that carries `+0x52C` by its destination register gives:

| Destination | 7-byte SIB form | 6-byte ModRM form |
|---|---:|---:|
| `eax` | 25 combined | |
| `edi` | 12 combined | |
| `ebp` | 5 combined | |
| `esi` | 3 combined | |
| **totals** | **37** | **8** |

Twenty of forty-five target something other than `eax` -- **44 per cent**. A
second session counting only the SIB form arrives at 35 sites and 31 per cent;
the two disagree on the population, not on the finding, and both refute the
premise. `0x462990` is merely the first counter-example encountered, not the
only one, and there the `lea` also sits behind a `call`.

Restricted to the 23 that can actually kill -- the set a hook would target --
the spread is `eax` 12, `edi` 8, `ebp` 3. So the premise fails on **eleven of
the twenty-three sites a counter would have to hook**, not merely somewhere in
the wider population.

A structural claim drawn from an incomplete set is only as complete as the set
-- and verifying it carefully across that set makes it more persuasive without
making it more sound. The withdrawn design had been checked against its seven
sites and held on all seven; what was never asked was whether the seven were
all of them.

**A New Home is not, at a cost proportional to one row.** The same
byte-search-then-classify pass over its health field at `+0x344` finds 31 `lea`
sites, of which **eighteen** are damage, across three regions -- every address
below verified against the stock image.

The 31 was re-measured after the equivalent VV2 figure turned out to be an
undercount: a scan matching only the seven-byte SIB encoding reported 35 where
the true population is 45. VV1's number survives that check -- 28 SIB-form plus
3 ModRM-only is 31 -- so it was already counting both encodings.

The destination spread is the part worth carrying across, because it is nearly
identical to VV2's:

| Game | `eax` | `edi` | `ebx` | `ebp` | `esi` | non-`eax` |
|---|---:|---:|---:|---:|---:|---:|
| A New Home | 17 | 9 | 4 | 0 | 1 | **14 of 31 (45%)** |
| The Lost Children | 25 | 12 | 0 | 5 | 3 | **20 of 45 (44%)** |

So the premise that defeated the single-wrapper design for The Lost Children --
that every damage site leaves the health pointer in `eax` -- fails at the same
rate here. The two games are alike in this, which is why the conclusion below
is a cost judgement rather than a gap in the evidence. The register that takes
up the slack differs (`ebx` in A New Home, `ebp` in The Lost Children), which
is why a wrapper written against either game's spread would not transfer to the
other even if the rate matched.


| Form | Sites |
|---|---|
| `dec ecx` then store | `0x42ECBE`, `0x42ED3E`, `0x42EDAA` |
| `call 0x402F10` then `sub [reg], eax` | `0x43A5A8`, `0x43A787`, `0x43A8AE`, `0x43A9D5`, `0x43AADB`, `0x43AC8F`, `0x43B106` |
| `call 0x402F10`, read, `sub` in a register, store back | `0x43B2C8`, `0x43B387` |
| `sub [reg], ebp` | `0x42AB17` |
| read then `add ecx, -imm` (`-0xF`, `-0x6E`, `-0x46`, `-0x28`) | `0x42C2A6`, `0x42C698`, `0x42C76F`, `0x42C838` |
| `add edx, -0x32` then store | `0x419DAA` |
| old-age store | `0x42EF05` |

**This table read sixteen damage sites until the set was re-derived, and the
two it gained say something about how it missed them.** `0x43B2C8` and
`0x43B387` are the randomiser form -- the same `call 0x402F10` supplying the
amount -- but they subtract in a register and store back
(`call ; mov ecx,[ebx] ; sub ecx,eax ; mov [ebx],ecx`) instead of subtracting
into memory. A classifier looking for `sub [reg], eax` sees the first seven and
not these two, so the miss was a **shape assumption inside a form that had
already been found**, not an unexamined region. The earlier count was a subset
of this one, not a competing measurement: diffing the address sets gives
`{0x43B2C8, 0x43B387}` added and nothing removed.

All nine sites of the randomiser family call the same routine at `0x402F10`,
which supplies the amount. Several forms leave no
register holding the pre-value, so a guard shape has to be argued per site,
and the cave-audit gate would need a register contract for each.

`sub_43B690` having three damage sites was the easy case, not the
representative one -- and those three were that routine's, never the game's.
The Lost Children has since been measured at 23 lethal sites across four
instruction forms, so it belongs in A New Home's category rather than standing
as a contrast to it. Both are recorded as the reason those two games are not
shipped rather than as a recipe to follow: hooks in that quantity and that many
shapes, for one row, is not a maintainable feature, and claiming a completion
path at that cost would be an over-promise of the same kind the document
already refuses elsewhere.

Counting burials instead is exact and already shipped, but it is a different
quantity and should not be relabelled.

**The trampolines have a verified home, and it is not the cave.** Twenty-three
hooks at roughly twenty-five bytes each need about 575 bytes. The statistics
cave has six bytes free of 208, and the largest contiguous executable run in a
fully composed image is 35 bytes, so a cave-resident design is short by more
than an order of magnitude. That is a measurement, not a preference.

The Lost Children already appends an executable page for Origins, and it has
room:

```
append page   file 0xB1000..0xB3000   VA 0x4B3000   8,192 bytes
  .mtab       0xB1000..0xB2000        WRITABLE, not executable
  .vvmk       0xB2000..0xB3000        executable
    occupied  0xB2000..0xB241A        912 bytes of mask-renderer code
    FREE TAIL 0xB241A..0xB3000        3,046 bytes
needed for 23 trampolines                           575 bytes
```

The usable run is the `.vvmk` tail, **not** the 5,146 bytes preceding the
renderer. That prefix is `.mtab` -- a writable data page -- plus the
renderer's own code, so placing trampolines there would put them in
non-executable storage or overwrite the mask code. The layout names the pair
`.mtab/.vvmk` in a single entry, which is exactly the shape that invites
treating two sections as one.

So the mechanism is proven in the shipped build rather than invented, and the
margin is roughly five times what the feature needs. This is also what the
owner's standing rule asks for -- appended pages and DLL-side logic ahead of
cave space -- reached here by measurement rather than by preference.

**The Lost Children's counter storage survives a save, measured against a real
save file rather than inferred.** The doubler persistence defect was a field
written 352 bytes past what the game serialises, so a free slot is not enough
on its own -- it has to be inside the saved extent:

```
VV2 serialised extent        197,488 bytes  (0x30370; the 197,500-byte
                                             file carries 12 bytes of header)
burial counter   +0x2E5D4    189,908   inside, shipped
twins counter    +0x2E5D8    189,912   inside, shipped
deaths counter   +0x2E5DC    189,916   inside, 7,572 bytes of margin
```

The margin is measured against the **serialised extent**, not the file size.
Using the file size overstates it by the header and contradicts the
serialisation arithmetic recorded below, which is the figure the counter
actually depends on.

Both slots are unreferenced by stock code, and **both scans are controlled**,
because a scan that matches nothing looks identical to one that is broken:

```
The Lost Children   +0x2E5DC   0 refs   control +0x2E520 (Special Stews)  4 refs
A New Home          +0x9E90    0 refs   control +0x9E24  (Babies Made)    6 refs
```

The method is a byte search for the little-endian displacement across
`.text`, counting every occurrence. The control is a field of the same shape
in the same block that stock code is known to use, so a non-zero result there
proves the search can find what is present.

**A New Home's eighteen-site set is complete, independently re-derived.** The
same classify-every-`lea` pass used for The Lost Children, run against
`+0x344`:

```
lea sites carrying +0x344   31    (eax 17, edi 9, ebx 4, esi 1)
documented damage sites     18    ALL recovered
remaining sites             13    classified, ZERO damage among them
```

The thirteen are four clamps (`0x41A07A` ceiling, `0x42AB2F` zero, `0x42EDC0`
floor, `0x42EE44` ceiling), one heal (`0x42EE2E`, `inc dword [eax]`), five
reads or branches with no write, and three `lea`-plus-padding sites that touch
only bytes. None mutates health downward.

So unlike The Lost Children -- whose count was revised upward twice before it
settled -- A New Home's list was already complete. That is worth recording
because the two games were treated as equally uncertain and only one of them
was.

Both death counters also have verified storage. `+0x9E90` is free in A New
Home (zero stock references) and sits at 40,592 against a 44,008-byte save,
inside the serialised extent with 3,416 bytes of margin. The doubler
persistence failure -- fields at 44,360, past the extent -- cannot recur.

**The Lost Children's counter storage survives a save, and that was measured
rather than assumed.** A New Home's doubler persistence bug is exactly a field
written past the serialised extent -- real, unused, correctly chosen, and 352
bytes beyond what reaches disk -- so the same question has to be answered
before any new counter is placed:

| | A New Home (broken) | The Lost Children |
|---|---:|---:|
| real save file | 44,008 | **197,500** |
| serialised extent | 0xABE8 | `0x30370` = 197,488 (pushed twice) |
| counter field | 44,360 (`0xAD48`) | 189,916 (`+0x2E5DC`) |
| position | **352 bytes PAST** | **7,572 bytes inside** |

Measured against an actual save file on disk, not inferred from the
allocation. The twelve-byte difference between the file and the allocation is
header overhead.

So the burial, twins and death counters at `+0x2E5D4`..`+0x2E5DC` are already
within the region the game serialises, and a death counter placed beside them
inherits that. The failure that broke the doublers cannot recur here -- but it
was only knowable by looking at a save.

**No convergence point exists below the damage sites either.** Earlier passes
ruled out candidates *at* the sites and left open whether the damage funnels
through a shared callee one frame down. It does not, and the near-miss is
worth recording because it looked convincing:

| Callee | Reached from | Callers image-wide |
|---|---:|---:|
| `0x4031A0` | **15 of 22** damage sites | **1551** |
| `0x441680` | 6 | 795 |
| `0x44B2A0` | 6 | 71 |

`0x4031A0` at 15 of 22 is exactly the shape a convergence point would have,
and it is a generic bounds clamp -- `push esi ; mov esi,[esp+8] ; test esi,esi
; jle ; cmp esi,0x7FFF ; jg` -- called 1551 times across the image. The
reached-from count alone would have endorsed it; the caller count is what
refutes it. **A shared callee is only a convergence point if the sharing is
specific**, and that is a second measurement rather than a stronger reading of
the first.


**A scanning note, because two sessions reached opposite wrong answers here.**
Ground truth for The Lost Children's health field is thirteen *direct* writers
-- instructions with `[reg+0x52C]` as the destination operand -- exactly one of
which writes zero (`0x43BDEE`, the old-age kill). These are a **disjoint
population from the 23 lethal sites** above, which reach the field through a
`lea`-ed pointer instead; `0x43BDEE` is not among the 23 and never was. Two independent method
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

### Why The Lost Children has no total stew count

`+0x2E520` is **not** a count of special stews cooked. It is a count of
**distinct recipes discovered**, and the difference is a per-recipe flag array.

```
004260AF  mov ecx, [esi+0x3044C]              ; the stew RESULT ID
004260B5  mov al, [esi+ecx+0x2EAAC]           ; per-recipe "already found" flag
004260BC  test al, al
004260BE  jne 0x4260E2                        ; already found -> skip the increment
004260C9  call 0x4257A0                       ; (message 0x1C7)
004260CE  mov edx, [esi+0x3044C]
004260D4  mov byte ptr [esi+edx+0x2EAAC], 1   ; mark this recipe found
004260DC  inc dword ptr [esi+0x2E520]         ; increment -- FIRST TIME ONLY
```

Cooking the same stew a second time increments nothing, because `+0x2EAAC`
indexed by result id is already set. This supersedes the earlier description of
a first-cook "undercount by one until the recipe is cooked again": there is no
undercount and no correction on a later cook. The counter is doing exactly what
it was written to do, and it is bounded by the number of recipes.

The result space is 18 outcomes, and **all 18 can eventually count** -- but by
two different routes, selected by a "first stew ever" flag at `+0x2E7A8`:

```
00426017  mov al, [esi+0x2E7A8]     ; has any stew been cooked before?
0042601F  jne 0x4260AF              ; yes -> ROUTE B, the per-recipe gate

          ; ROUTE A, taken once ever, applies three exclusions:
0042602B  cmp eax, 4     je 0x4260E2
00426034  cmp eax, 2     je 0x4260E2
0042603D  cmp eax, 0x12  je 0x4260E2
00426056  mov byte ptr [esi+0x2E7A8], 1    ; set the flag
004260A5  mov byte ptr [esi+eax+0x2EAAC], 1
004260AD  jmp 0x4260DC              ; straight to the increment, past the gate
```

The exclusions therefore apply **only while `+0x2E7A8` is still clear**, and
that flag is set at `0x426056` -- *after* all four early exits, the three id
comparisons and the `[esi+0x205]` test at `0x42604C`. An excluded cook takes
none of them and leaves the flag clear, so the **next** stew takes Route A
again.

The shortfall therefore accumulates. Cook ids `2`, `4` and `0x12` in
succession before anything else and all three go uncounted, because each one
exits before reaching the instruction that would have switched later cooks to
Route B. The count can be as much as three short.

It is not permanent. Those cooks also leave `+0x2EAAC` unset, so once any
non-excluded stew sets the flag, re-cooking a previously excluded recipe
reaches Route B, passes the gate and counts. The ceiling is therefore the
number of recipes rather than 15 -- but the recovery requires a later cook of
that specific recipe, not merely a later cook of anything.

**The absence is exhaustive, not a failed search.** Every 4-byte offset in
`0x2E4C0`-`0x2E560` was byte-searched for its disp32 encoding and each hit
classified by mnemonic -- never by a linear disassembly pass, which
desynchronises and silently omits real stores. Eleven incrementing writers
exist in that range:

| field | writers |
|---|---|
| `+0x2E4FC` | `add` x2 (`0x42629A`, `0x463742`) |
| `+0x2E500` | `inc` x2 (`0x44BA92`, `0x44BAC6`) |
| `+0x2E504` | `add` (`0x4262BA`) |
| `+0x2E508` | `inc` x3 (`0x44DA75`, `0x46477A`, `0x46482D`) |
| `+0x2E514` | `inc` (`0x44D55F`) |
| `+0x2E520` | `inc` (`0x4260DC`) |
| `+0x2E524` | `inc` (`0x44BAD2`) |

Exactly one touches a stew field and it is the gated one. The positive control
for the method is the same table: it recovers the known writers for People
Cured, Village Elders and Triplets Birthed, so a field it reports as having no
unconditional writer genuinely has none.

**What the requirement would need.** The count has to be new persistent state;
no stock field holds it.

**`0x4260AF` is the wrong hook site**, and the reason generalises. Route A
marks the recipe at `0x4260A5` and then `jmp`s from `0x4260AD` directly to
`0x4260DC`, bypassing `0x4260AF` entirely. A counter placed there misses the
first completed cook of every save, and misses an excluded-id first cook twice
over. Hooking the site that *looks* like the top of the block is exactly the
trap: the block has two entries, not one.

**No single site downstream of the split sees every completed cook**, and this
is worth stating because two plausible-looking plans both fail:

| candidate | misses |
|---|---|
| `0x42609F` + `0x4260AF` (both routes) | an excluded id cooked while `+0x2E7A8` is clear -- it exits at `0x42602E`/`0x426037`/`0x426040`, upstream of both |
| `0x4260DC` (the increment) | the above, **and** every repeat, which exits at `0x4260BE` |

`0x4260AF` does observe repeats, because it sits before the gate; that is the
one thing the pair gets right. But the excluded-while-unflagged case reaches
none of the four addresses, so neither plan produces an unrestricted total.

The only site that dominates every route is `0x426017`, the `+0x2E7A8` read,
which every path reaches with the result id already assigned at `+0x3044C`.
It has one escape below it: the `[esi+0x205]` test at `0x42604C`, on Route A
only. A counter placed at `0x426017` therefore counts every completed cook
**plus** any Route A call abandoned by that test.

`[esi+0x205]` has been resolved, and it narrows the gap rather than leaving it
open. Every byte access to that field in `.text` was enumerated by scanning for
the ModRM disp32 forms with any base register:

```
00426046  mov al, [esi+0x205]        read   -- the test at 0x42604C
00426093  mov byte [esi+0x205], 0    clear  -- on the Route A success path
```

**Two accesses. It is read once and cleared once, and nothing in `.text` ever
sets it to a non-zero value.** The scan is trustworthy because the identical
method, run against `+0x2E7A8`, recovers that flag's `set imm8=0x1` at
`0x426056` together with five reads -- so a field it reports as never set is
genuinely never set, not merely missed by the pattern.

That has a consequence for the counter. The test at `0x42604C` is
`je 0x4260E2` when the byte is zero, so on any path where the field still holds
zero the Route A cook is abandoned. Whatever writes it must therefore lie
outside `.text` -- a save-load, an initialiser, or a write through a computed
pointer -- and until that writer is found the frequency of the abandoned case
is unknown.

This is not a small residual. A counter at `0x426017` over-counts by exactly
the abandoned cases, and "abandoned cook" could be anything from a rare failure
to a routine outcome; a nearly-correct lifetime total is the failure this
document refuses everywhere else. The remaining work is to find the writer, and
the search has to look beyond a `.text` disp32 scan because that scan has
already been run and come back with nothing.

The general trap, recorded because it produced three successive wrong answers
in this routine: a hook site must be checked against **every** early exit
above it, not only against the branch that first looks like the gate.

Per the project's standing preference the storage belongs in the companion DLL
rather than a new stock field or cave allocation.

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

## Directing Work at the Hospital (The Secret City)

The requested feature is a Tribal Chief Direct Work action dropped on the
Hospital once Level 2 Medicine is bought, working like the existing
researching and farming Direct Work actions. The mechanism is table-driven,
so none of the strings involved is referenced by address and a search for
them returns nothing:

```
"Directing work"  VA 0x4963D0   .text references: 0
eSayDirectWork    VA 0x4963E0   .text references: 0
```

Both are reached through a 16-byte record table, `{enum_ptr, display_ptr, 0,
id}`, whose neighbours decode cleanly and confirm the layout:

```
0xAE2D4  id 0x219  eSayUsePotion    "Using potion"
0xAE2E4  id 0x21A  eSayDirectWork   "Directing work"
0xAE2F4  id 0x21B  eSaySayRefusing  "Refusing"
```

**Say id `0x21A` is pushed at exactly one site, `0x44BC4D`**, which is the
whole of the existing Direct Work path:

```
0x44BC4D  push 0x21A              "Directing work"
0x44BC52  mov ecx, edi
0x44BC54  call 0x42F190           the say routine
0x44BC59  push 0x27               action 39
0x44BC5B  push eax
0x44BC5C  lea ecx, [esi+0xF28]
0x44BC62  push ecx
0x44BC63  call 0x46F780           the action dispatcher
```

The Level 2 Medicine gate is a separate helper. `sub_4617F0` takes
`(level, tech_id)` and is called with only two distinct pairs in the whole
image, both at level 6:

```
sub_4617F0(6, 0x25F)   1 site
sub_4617F0(6, 0x405)   2 sites   0x452777, 0x4528CE   Medicine
```

`0x405` is `eTechMedicineLabel`'s id, taken from the tech record at
`0xAF1E4`. So the gate the feature needs is `sub_4617F0(6, 0x405)` -- level 6
internally is the Level 2 the player is shown, which is why a search for a
literal 2 finds nothing.

The handler itself is `sub_44A310`, and its prologue names the action a
second time:

```
0x44A310  push esi ; push edi ; push 0x27 ; push 0x482 ; call ...
          called from exactly ONE site, 0x453965
```

So action `0x27` appears both at the handler's entry and at the say site
`0x44BC4D` a little under 0x1940 bytes inside it. A single caller and a single
say site make this the whole of the Direct Work path rather than one branch of
several.

`eObject_Hospital` resolves through a different table shape again -- a dense
pointer array indexed by object id rather than the `{enum, display, 0, id}`
records the say strings use:

```
0xA8FF0  [0]  eObject_None        <- enum base
0xA8FF4  [1]  eObject_Fireplace
0xA8FF8  [2]  eObject_Hut
...
0xA9090  [40] eObject_Hospital    id 0x28
```

The base matters: the array physically starts at `0xA8EF0` with UI strings
(`Select`, `Edit`, `Erase`), so measuring the index from the array start gives
104 rather than 40. `eObject_None` is what anchors the object enum, and using
the wrong anchor produces a plausible id that is wrong by 64.

**The handler tests no object id at all**, which answers the question in the
cheaper direction. Every `cmp reg, imm8` across its 0x193D bytes:

```
cmp reg, 0x01   x3      cmp reg, 0x1E   x1
cmp reg, 0x03   x3      cmp reg, 0x28   x1   <- looks like Hospital
cmp reg, 0x0A   x1      cmp reg, 0x32   x15
cmp reg, 0x14   x8      cmp reg, 0xFF   x18
cmp reg, 0x19   x1
```

The single `0x28` is not an object test. In context it is

```
0x44AAF8  call <rand>
0x44AAFC  cmp eax, 0x28
0x44AAFF  jge
```

a forty-percent probability roll. Reporting it as the Hospital comparison
would have been the easiest mistake available here -- the constant matches the
object id exactly, appears exactly once, and sits in the right routine.
Reading the three bytes before it is what separates the two.

So target selection happens upstream of `sub_44A310`, and the handler accepts
whatever object it is given. That makes the feature a **gate plus target
registration** rather than a change to the handler: the Hospital has to become
a legal drop target for action `0x27`, and the drop has to be refused until
`sub_4617F0(6, 0x405)` reports Level 2 Medicine. Neither of those is in the
handler, which is the good case.

### The Lost Children damage count is 21, not 22

A splice-safety pass over the damage sites turned up an apparent hazard at
`0x44B448` -- a branch from `0x44B4BA` landing at `0x44B450`, one byte inside
what was recorded as a nine-byte `dec dword [eax]` span. Splicing there would
have returned control into the middle of the inserted jump.

The site is not a damage site at all, and the reason is a decoding bug in the
classifier rather than anything in the binary:

```
8d bb 2c050000   lea edi,[ebx+0x52C]    SIX bytes, ModRM form, no SIB
8b ff            mov edi,edi            hot-patch padding
8a 87 04fbffff   mov al,[edi-0x4FC]     a BYTE read at record+0x30
84 c0            test al,al
83 3f 00         cmp dword [edi], 0     reads health, never writes it
```

The classifier assumed every `lea` carrying `+0x52C` was the seven-byte
SIB form and read the mutation at `+7`. At this one site the `lea` is six
bytes, so `+7` lands one byte into `mov edi,edi` and the following `ff` of
`8a 87 04fb**ff**ff` reads as `ff /1`, a `dec dword [eax]` that is not there.

**One site of the twenty-two uses the short form**, which is why the error
appeared exactly once and looked like a genuine hazard rather than a decoding
mistake. It also explains the near-miss: had the branch target not forced a
second look, a hook would have been placed on an instruction that only reads.

So the set is **21 damage sites plus the old-age store at `0x43BDEE`, 22 hooks
in all**, and the splice check is clean for every one of them: zero branch
targets land inside any span once the `lea` length is decoded from its ModRM
byte instead of assumed.

The general form is the one already recorded twice in this document -- a fixed
offset is an assumption about encoding, and x86 does not guarantee it. The
first instance turned six `cmp` sites into phantom writes; this one turned a
read into a phantom `dec`.

### Why VV2's death counter cannot extend the statistics feature

The statistics emitter writes every wrapper into a fixed-size cave buffer at
`cave_va + slot`. The Lost Children's cave is 208 bytes and the built payload
uses 202 of them:

```
vv2 cave payload   208 bytes, 202 used, 6 free
22 trampolines     ~550 bytes
```

So this is a separate append-based feature rather than more `death_hooks`
entries, and the generator work already merged -- the optional cause field and
the transition gate -- applies to A New Home, whose cave is the same size and
whose hook count is lower, only if that game's arithmetic works out. It does
not follow from VV2's.

The home is the appended Origins page, immediately after the parentage
payload, and the space is measured in the built page rather than assumed from
the layout:

```
append page          0xB1000..0xB3000
  .mtab              0xB1000..0xB2000   writable, unusable for code
  .vvmk              0xB2000..0xB3000   executable
    mask renderer    0xB2000..0xB241A   912 bytes
    parentage        0xB241A..0xB24D8   0xBE bytes
    FREE             0xB24D8..0xB3000   2,856 bytes, all zero
```

`build_vv2_parentage_feature.py` is the working model for this shape, and two
of its guardrails are worth carrying rather than rediscovering:

- the payload preimage is read from **the built Origins page**, not from the
  manifest's `append_bytes`, because those carry build-time scaffolding at
  that offset which is replaced before the overlay is applied
- it asserts the payload address is **past the stock end of file**, so a
  mistake that puts it inside the stock image fails loudly instead of
  overwriting real code

The trampoline is a detour rather than a tail here: the stolen bytes are a
`lea` plus a mutation in the middle of a routine, not an epilogue, so each one
has to jump back. That is the rejoin-rel32 class the parentage comment warns
about, and it is why the splice check enumerating branch targets inside every
span had to come first.

### Stolen spans, and why a byte-wise branch scan cannot check them

Every hook needs two facts: how many bytes to steal, and whether anything
branches into the middle of them. Both were derived rather than assumed, and
both assumptions failed first.

**Spans, decoded from ModRM rather than a fixed offset.** The `lea` is six or
seven bytes depending on whether it carries a SIB, and the mutation that
follows is one of five shapes, so the span is found by walking whole
instructions until the field is written:

```
 9 bytes   0x433367 0x4375E7 0x43BB7E
10 bytes   0x420E16 0x421013 0x43BAEB 0x43BC43
12 bytes   0x44EE21
14 bytes   0x462C05 0x462D3C 0x462E78 0x462F8A
15 bytes   0x462990
16 bytes   0x43909F 0x4392CC 0x4393DC 0x4394EC
21 bytes   0x4638DA 0x46403E
23 bytes   0x463638 0x4641A7
 7 bytes   0x43BDEE  (old-age store, no lea)
```

All 21 damage sites resolve, every span is at least nine bytes, and a
five-byte jump fits everywhere.

**The splice check needed a boundary-aware scan.** A byte-wise search for
`E8/E9/EB/7x/0F8x` flagged two sites as unsafe:

```
0x463638  targets at +1 and +17
0x4641A7  targets at +17 and +22
```

Both are phantoms. The bytes that looked like branches are fields inside other
instructions:

```
8b ae d4 74 e5 00   mov ebp,[esi+0xE574D4]   the "74 e5" is disp32
8b 7c 24 1c         mov edi,[esp+0x1C]       the "7c 24" is ModRM+SIB
```

Walking the same region from a verified instruction boundary finds **zero**
real targets inside either span. So all 22 hooks splice cleanly.

This is the third instance of one failure in this feature: `0x44B448` decoded
a byte read as a phantom `dec`, six `cmp` sites once decoded as phantom
writes, and now two phantom branch targets. **Every one came from decoding at
an offset that was not an instruction boundary**, and every one looked like a
real finding -- the phantom hazard is especially convincing, because a branch
landing one byte into a `lea` is exactly what a genuine hazard would look
like.

The rule that survives all three: a scan that starts anywhere except a known
boundary is generating candidates, not facts, and each candidate has to be
re-derived from a boundary before it is believed in either direction.

### The counter is not reachable from every hook site

The shipped VV2 counters are seventeen bytes and need no DLL call:

```
8b 87 d474e500   mov eax, [edi + 0xE574D4]    the manager
ff 80 d8e50200   inc dword [eax + 0x2E5D8]    the counter
e9 rel32         jmp back
```

That template does not transfer to every death site, and the reason is the
manager load rather than the increment. `0xE574D4` is not an address: it sits
far above the image, which ends at `0x4B5000`. It is a displacement against a
base the surrounding code has already established, so the wrapper only works
where such a register is live.

Measured across the twenty-two sites by looking for the same displacement in
each site's own neighbourhood:

```
esi live, manager reachable   12 sites   0x44EE21, 0x462990, 0x462C05,
                                         0x462D3C, 0x462E78, 0x462F8A,
                                         0x463638, 0x4638DA, 0x46403E,
                                         0x4641A7
no base register nearby       10 sites   0x420E16, 0x421013, 0x433367,
                                         0x4375E7, 0x43909F, 0x4392CC,
                                         0x4393DC, 0x4394EC, 0x43BAEB,
                                         0x43BB7E, 0x43BC43, 0x43BDEE
```

Two readings of the displacement were tried and both fail, which is what
establishes that it cannot be made absolute: `mov esi, 0xE57090` appears 61
times, and `0xE57090 + 0xE574D4` is `0x1CAE564`, far outside the image;
treating `0xE574D4` as the address itself puts it outside too. Neither gives a
statically addressable global, so there is nothing to hardcode.

This is a constraint on the design rather than a defect. The ten sites without
a live base need the manager obtained some other way -- recovered from the
villager record they already hold, or the counter kept somewhere reachable
without it -- and that is the next thing to establish. Recording it because
the twins wrapper makes the work look finished: the template is real, it is
simply not universal, and copying it to a site where the base register is dead
would read a pointer out of whatever happened to be in that register.
