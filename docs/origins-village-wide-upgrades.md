# Origins village-wide upgrades

## Current atomic-payload safety containment

All five legacy `vvN_origins_village_wide_upgrades` records are fail-closed and are
not offered by the catalog, GUI, CLI, or Select All. Commands 6, 7, and 8 share
one atomic payload, so the complete feature remains unavailable until each
game receives a full-payload GO gate. VV3's independent certified command-6
feature is now available without commands 7/8. The VV4 audit
`628e0d9217b92b9cd695655842b09d74689a0238` proves that command 7's direct
`90.0` mastery stores bypass eight native mutations. The VV5 audit
`02581c8f518e27ebd5fc7d2972db5597ab08ed35` records unresolved native-counter,
eligibility, no-change, inheritance, and expanded-layout requirements. VV3 is
ON HOLD under exact-build audit
`089957227c0db6a4c3128045519ffa27b201a00e`; VV1 is not certified.

The legacy manifests below remain as disabled diagnostic evidence; their payload
bytes are not applied. Containment does not clear or rewrite existing save
fields, issue a refund, or copy a companion DLL. Base Origins remains
independently selectable for VV1, VV3, VV4, and VV5; VV2's complete Origins
pair remains separately contained after its reported crashes.

The five historical bundled features are separate, game-scoped manifests:

* `vv1_origins_village_wide_upgrades`
* `vv2_origins_village_wide_upgrades`
* `vv3_origins_village_wide_upgrades`
* `vv4_origins_village_wide_upgrades`
* `vv5_origins_village_wide_upgrades`

Each depends on its matching `vvN_enable_origins_exclusive_features` feature.
The base Origins payload remains the owner of the six normal rows and the
shared companion DLL. The optional manifest owns only its exact-build,
zero-filled extension reserve and its signed ABI header/payload; it does not
rewrite base Origins payload bytes or copy another companion DLL.

The VV2 record is additionally covered by the complete VV2 Origins
containment after player-reported crashes in Time Warp and Food Point Doubler.
Its historical payload remains in the data file for diagnosis, but it is not
applied or copied; unrelated VV2 features remain available.

The optional ABI exposes three commands to the dormant base-payload extension
hook. The base passes `EAX=6/7/8`, `ECX=first physical record pointer`, and
`EDX=physical record bound`. Running returns full-Like skips in `EAX`,
already-running villagers in `EDX`, and villagers whose Running dislike was
removed in `ECX`; commands 7/8 return zero counts and invalid commands return
`EAX=-1`, `EDX=0`, `ECX=0`. All helpers preserve `EBX`, `ESI`, `EDI`, `EBP`,
and `ESP`.

| Row | Label | Cost |
| --- | --- | --- |
| 6 | All Villagers Like Running | 1,000,000 tech points |
| 7 | Grant Full Mastery to All Villagers | 1,000,000 tech points |
| 8 | All Villagers are 18 | 1,000,000 tech points |

These selected upgrades are inspired by the exclusive upgrades in the Virtual
Villagers 1 mobile port. They are current-save-only purchases. Running removes
Running from Dislikes and writes Running only to a free normal Like slot. The
historical helper/result wording is retained only as rejected diagnostic
evidence; the exact future atomic contract is specified below. The charge
contract is one million tech points for the village-wide purchase, not per
villager. VV3 command 6 is currently available; every other command remains
unavailable. The implementation is tailored to each
supported executable: it independently reads the numeric Running ID certified
in that game's exact stock preference table. All five current tables happen to
resolve Running to ID 38, but that is not a blanket cross-game assumption. The
certified preference-table evidence offsets are VV1 `0x7B260`, VV2 `0x8B808`,
VV3 `0x97488`, VV4 `0xA0CD8`, and VV5 `0xAEF60`; each manifest also records its
exact Likes/Dislikes offsets and physical record stride.

### All Villagers Like Running exact-build boundary

Cross-game audit `0311443fbd078e3adcabaf7e693199989ddb9db8`, with
evidence-hierarchy clarification
`a67e05247dc822306e1d5a514524cba388ab4d69`, places command 6 independently
ON HOLD for VV1, VV2, VV4, and VV5. VV3 is separately certified below:

| Game | Exact supported fingerprint | Persisted Like/Dislike model |
| --- | --- | --- |
| VV1 | 581,632 bytes; `1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D` | 4 Likes + 4 Dislikes, signed DWORDs |
| VV2 | 724,992 bytes; `46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677` | 62 Likes + 62 Dislikes, signed DWORDs |
| VV3 | 831,488 bytes; `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503` | 3 Likes + 3 Dislikes, signed DWORDs |
| VV4 | 929,792 bytes; `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` | 3 Likes + 3 Dislikes, signed DWORDs |
| VV5 | 991,232 bytes; `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D` | 3 Likes + 3 Dislikes, signed DWORDs |

Every empty slot uses signed DWORD sentinel `-1`; construction, membership,
copy, and persistence paths were traced for each complete array. Running ID
38 was code-confirmed independently in every exact executable, rather than
assumed across games.

VV3 Stage C certification `79b122bf0850f18a101db9fb86b40407dd2db573`
approves the exact command-6-only artifact generated at patcher commit
`4876f30609e2b9c5ea04188000b16be65e1175b1`. It is exposed as
`vv3_all_villagers_like_running`, depends on
`vv3_enable_origins_exclusive_features`, and retains the certified page,
slot, hashes, ownership, and uninstall guards unchanged. Commands 7 and 8 are
absent. Player runtime confirmation remains pending.

The future operation must be atomic per villager. An already-Running Like
skips the entire villager. Otherwise, the helper must scan the complete Like
array and prove an empty slot exists before removing any Running Dislike. Full
Likes means no mutation. Only after successful preflight may it add Running
and clear all matching Running Dislikes, without reordering or replacing any
unrelated slot. The dormant helpers violate this ordering, and the VV1/VV2
helpers additionally inspect too few slots.

VV5 must reject current faction `+0x1CEC != 0` before any preference read,
write, or result count. The additional `+0x1CE1` candidate gate is unsafe and
unproved. Shared blockers are a bounded four-counter dialog/result ABI, a
final unsigned no-op/no-charge transaction with funds recheck and rollback,
complete ordinary/status eligibility, and collision-free stock plus expanded
composition.

Two required future result lines are exactly:

```text
Skipped over X villagers. Reason: already likes running
Removed running dislike from X villagers
```

The proposed full-slot line remains future-only until complete capacity and
result-ABI proof; it does not describe current available behavior.

Cheat Engine evidence is subordinate to the executable evidence. The main
`Official LDW Cheat Tables` folder is the current authoritative vanilla-table
set. `Official LDW Cheat Tables  (Backup!!)` is a backup snapshot of that same
vanilla set and is used for recovery/version comparison.
`Official LDW Cheat Tables - Copy` is strong player-confirmed runtime evidence
used repeatedly with renamed/copied base-game executables whose filenames
contain `- Copy` or a variation. Translating its addresses still requires
fingerprinting the underlying executable and accounting for any
process/module-name-dependent Cheat Engine script. Exact-build executable
evidence controls every claim.

#### VV3 resolution-pass boundary

VV3 resolution commits `531b0aca8d5bf051f87773e67d48b61c0ba02833`
and `1d9a39da078806aa940e4774a9068956e88347bc` close the preference
operation, but not the executable architecture. The exact
831,488-byte/SHA-256
`8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`
build has Running ID 38, three Like DWORDs `+0xFB4..+0xFBC`, three Dislike
DWORDs `+0xFC0..+0xFC8`, sentinel `-1`, stride `0x1F8C`, and a supplied
150/256 physical bound. Persistence of all six slots is traced. The complete
atomic algorithm may write only `+0xFB4..+0xFC8`: scan all Likes, skip the
whole record if Running is present, require an empty Like, then add Running,
clear matching Dislikes, and count `granted`, `already`, `removed`, and
`full`.

The finalized VV3 future result lines are:

```text
Granted Running to %u villagers
Skipped over %u villagers. Reason: already likes running
Skipped over %u villagers. Reason: all like slots are occupied
Removed running dislike from %u villagers
```

The transaction must dry-run, refuse and charge nothing when `granted == 0`,
perform a final unsigned funds recheck immediately before commit, apply only
the proved deterministic stores, and deduct exactly once.

VV3 remains ON HOLD, but `+0xE94` is no longer an unresolved eligibility
field. Commands 6/7/8 share one 944-byte atomic payload at file `0x7B820` and entry
file/VA `0x7B840/0x47B840`. The existing path precharges at `0x582644`;
header check `0x7B7A0` proves only signature/result-export presence. Its
three-counter 128-byte result ABI cannot return `granted`. Base hooks
`0x6547D`/`0x65640` and payload `0xA3180` mix unrelated Origins mechanics;
there are no command-6-only UI guards. No complete appended-section
relocation, uninstall, absolute-reference, or all-patch stock/expanded ledger
is certified.

Second resolution commit `d1cdeb67362487c1d577e3abae03c9424fd04fb9`
specifies every remaining architecture item except the first semantic gate,
the naturally nonzero meaning of `record+0xE94`. Its exhaustive direct scan
found exactly eight readers:

`0x455993/0x55993`, `0x4568A3/0x568A3`, `0x45C9AA/0x5C9AA`,
`0x468D4C/0x68D4C`, `0x469081/0x69081`, `0x46915C/0x6915C`,
`0x4692C8/0x692C8`, and `0x4697EF/0x697EF`.

The sole direct writer is retirement/reset
`0x45F2B1/0x5F2B1`, which writes zero. Constructor clearing, save/load/copy,
and wholesale copies preserve the byte; no direct nonzero writer was found.
Main, Backup, and Copy Cheat Engine tables strongly corroborate the preference
and Chief fields but do not label `+0xE94`; the separately exposed Chief DWORD
proves it is not that field.

The specified command-6-only design retains hooks `0x6547D` and `0x65640` but
uses a distinct Running-only seven-row state, defensive maximum ID 1006, and
exact `command == 6` dispatch; any `command >= 6` range is forbidden. It
returns a 16-byte four-counter structure
`{granted, already_like, full_like, removed_dislike}`. At bound 256, the four
lines plus three CRLF sequences and NUL require at most 201 bytes, so the
bounded result buffer is `char[256]`.

An unowned purchase unsigned-checks 1,000,000, dry-runs, refuses without
charge when `granted == 0`, performs a final unsigned recheck, deducts exactly
once, commits the identical deterministic plan, and sets ownership only after
a nonzero commit. Removal costs 0, refunds 0, clears only ownership/UI state,
does not reverse preferences, and permits repurchase.

Stock PE facts are ImageBase `0x400000`, SectionAlignment/FileAlignment
`0x1000/0x1000`, five sections, SizeOfHeaders `0x1000`, SizeOfImage
`0x2DF000`, checksum zero, and a final `.rsrc` at RVA `0x2C9000`, raw
`0xB5000`, size `0x16000`, ending at raw `0xCB000`; one 40-byte section-header
slot remains. Expanded mode moves `.shr` to RVA `0x3A1000`, `.rsrc` to
`0x3A2000`, sets SizeOfImage `0x3B8000`, and applies 1,263 guarded patches.
A stock appended section begins no earlier than RVA `0x2DF000`; expanded no
earlier than `0x3B8000`. Deterministic injection bytes and dual-layout section
manifests remain deliberately withheld pending a collision-certified
command-6-only implementation.

Semantic-closure audit `b9c7a22eb1d7cceae25160ce4d360621e7485625`
identifies `+0xE94` as a dormant retained per-villager totem-render selector,
not a live eligibility discriminator. At reader `0x468D4C/0x68D4C`, nonzero
selects localization ID 573, exact suffix **`'s totem`**; zero with signed
health `<= 0` selects ID 574, **`'s remains`**. The same eight readers and
sole direct zero writer remain exhaustive. Save/load/copy preserves the byte,
but constructors, new villagers, clones, Events, puzzles, and templates expose
no nonzero producer. A corrected readable save corpus contained 64 active
records, all zero; a read-only live scan found 125 active of 150 physical
records, also all zero. Strong player-confirmed Cheat Engine tables corroborate
the surrounding fields but contain no `+0xE94` label.

The Running walker therefore removes `+0xE94` and uses only active byte
`+0xF10 != 0` plus signed health DWORD `+0xE78 > 0`. VV2's `+0x558`
memorial marker and VV5's Heathen totems are separate game-specific mechanics,
not substitutes for this VV3 field.

Stage C has now generated a corrected disabled command-6-only recertification bundle under
`data/candidates/`, with the exact base-owned `.vvrun` page, guarded no-op
slot, dependent Running replacement, stock and both-expanded layouts,
append/truncate guards, four-counter `char[256]` ABI, and rebuilt
`ShowOriginsVillageWideResult@20` companion export. It remains absent from the
catalog and ordinary outputs until Sol certifies those emitted bytes. The
existing 944-byte commands 6/7/8 payload remains forbidden because it
precharges, exposes commands 7/8, lacks the granted count, and uses the wrong
callback ABI.

Persistence here means serialization and restoration, not immutability.
Certification requires preservation of unrelated fields at the Running
transaction, correct save roundtrip, and no interception of later native
writers. Native Events and other ordinary game mechanics may legitimately
change persisted Likes, Dislikes, health, age, or other fields afterward.

The disabled Full Mastery candidate contains direct stores to the native five
skill fields in VV1–VV4 or six skill fields in VV5. Those stores are retained
as diagnostic evidence, not approved behavior. All Villagers are 18 writes only
the displayed-age field (360 internal age units). It does not write nursing
timers, pregnancy timers, pregnancy state, movement speed, movement
initialization, unrelated preferences, or other record fields.

### VV3 Full Mastery exact-build boundary

Disassembly commit `089957227c0db6a4c3128045519ffa27b201a00e`
confirms five signed DWORD skill fields at record offsets `+0xEAC`,
`+0xEB0`, `+0xEB4`, `+0xEB8`, and `+0xEBC`. Native mastery begins at 88,
the native maximum is 100, and stock code performs an all-five evaluation
whose award identifier is 4. The contained command-7 candidate writes 90
directly. That is neither full 100 mastery nor native-equivalent: its direct
stores bypass the post-write all-five evaluation.

VV3 remains ON HOLD. A future implementation must resolve the exact target
value and native evaluation/counter policy, define a zero-change/no-charge
result, prove creation and inheritance behavior, and provide safe composable
placement. None of those open items is inferred from the disabled payload.

### VV2 Full Mastery exact-build boundary

Disassembly commit `60f649bf90b55dea3a6856d949e123bd79808782`
confirms five contiguous signed DWORD skills: Farming `+0x7E4`, Building
`+0x7E8`, Research `+0x7EC`, Healing `+0x7F0`, and Parenting `+0x7F4`.
The following DWORD `+0x7F8` is job preference, not a sixth skill. Native
consumers use thresholds 20, 50, and 88; Detail displays Master at 88 or
higher, while native award paths cap skills at 100. Save/load persists the
five skills and preference across 256 physical records at stride `0xE48C`.

The disabled candidate iterates the supplied physical bound, including sparse
records, and requires active byte `+0x30 != 0` and signed health DWORD
`+0x52C > 0`. It writes 90 to all five fields, returns zero counts, and cannot
distinguish changed records or already-mastered villagers. Its transaction
checks `state+0x2EADC`, subtracts 1,000,000 once, then uses `Purchased.`; it has
no zero-change/no-charge result, recheck, or rollback.

VV2 remains ON HOLD. Candidate 90 is Master-ranked but is not full native 100;
no complete native all-five side-effect route is proved. Creation starts from
zero with an optional one-skill seed, copying/cloning copies all five, and
pregnancy, event-child, inheritance, Silver Mirror, and Gong closure remains
incomplete. The withdrawn VV2 Origins transport also retains its `.shr`
raw-offset/virtual-address defect. Gong and every Island Event path—including
their selection, RNG, messages, statistics, and skill writes—must remain
entirely native and cannot be intercepted by this command.

### VV1 Full Mastery exact-build boundary

Disassembly commit `e0bed87ce17dca5331afed1abc2d753ec3d8f0aa`
confirms five contiguous signed DWORD skills: Farming `+0x3BC`, Building
`+0x3C0`, Research `+0x3C4`, Healing `+0x3C8`, and Parenting `+0x3CC`.
The following DWORD `+0x3D0` is job preference. Master rank begins at 90,
while ordinary native award paths cap at 100. Save pack scans 32 physical
records at stride `0x3D8` and persists the skills and preference.

The disabled candidate iterates its supplied physical bound and requires
occupied byte `+0x28 != 0` and signed health DWORD `+0x344 > 0`. It writes 90
to all five skills, leaves preference unchanged, preserves nonvolatile
registers, and returns zero counts. Its dispatcher checks Technology Points at
`state+0xA2FC`, subtracts 1,000,000 once, and has no commit recheck,
changed-record preflight, no-charge no-op result, or rollback.

VV1 remains ON HOLD. Full Mastery still requires a decision between Master
threshold 90 and native maximum 100, and the mass candidate's unchanged
preference conflicts with the separate selected-villager candidate that sets
an empty preference to Farming. Native skill side effects are distributed; no
complete all-five route is proved. Creation initializes skills/preference
independently while copy/clone copies the five skills, leaving future-record
policy unresolved. Golden Child and every Island Event route—including
eligibility, RNG, selection, messages, statistics, births, skills, and record
writes—must remain entirely native. Exact guarded placement and all-patch
composition are also unproved.

### VV5 All Villagers are 18 exact-build boundary

Disassembly commit `aaddf71797c28f37b0cc1f5728e567c0601a05aa`
confirms the signed displayed-age DWORD at `+0x1B8C`. VV5 uses 20 internal
units per displayed year, so age 18 is 360 (`0x168`). Detail refresh divides
that field by 20; native adult, child, and older-head consumers compare it with
360, 280, and 1100. Constructor/copy operate on its `0xA8`-byte age/identity
object, and save/restore persist that object.

Native ordinary/offline aging reaches primitive increment writer `0x46F7F0`
through loop `0x46FE90` and then updates the oldest-villager lifetime statistic
when applicable. The disabled command-8 candidate instead performs only
`record+0x1B8C = 360`; it bypasses that native increment/statistic/transition
route. Its instruction stream does not write catch-up companion `+0x1C3C`,
nursing/pregnancy companion `+0x1C4C`, or pending-baby count `+0x1C50`.
However, the selected-villager age candidate adjusts `+0x1C3C` and nonzero
`+0x1C4C` by the age delta, so the village-wide asymmetry is unresolved.
The mandatory contract remains that nursing timer and nursing/pregnancy state
must never change; the raw store is not proof that the helper satisfies that
semantic requirement.

The candidate iterates stride `0x2F44` and tests active `+0x1CD4`, positive
signed health `+0x1C40`, extra byte `+0x1CE1 == 0`, and proven current-believer
faction `+0x1CEC == 0`. The faction test correctly excludes current Heathens
and includes converted believers, but the extra `+0x1CE1` exclusion is not
proved. Its transaction checks `0x51D5F8`, submits `-1000000` to native tech
writer `0x4237B0`, dispatches command 8, and reports `Purchased.`. It performs
no changed-record preflight, charges zero-change/already-18 cases, returns zero
result counts, and has no tied recheck or rollback.

VV5 age 18 remains ON HOLD. The shared expanded transport also retains 43
uncertified relocated references: 36 cross-section `rel32` operands and seven
external absolute `.shr` pointers. No helper availability or safety is claimed
from this diagnostic loop.

### VV4 All Villagers are 18 exact-build boundary

Disassembly commit `ab404b0c5e80cab4d327de9a51069e6e3529df27`
applies to the exact 929,792-byte executable with SHA-256
`6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220`.
It confirms signed displayed-age DWORD `+0x1B8C`, 20 internal units per year,
and age 18 value 360. Detail refresh is `sub_43BA80`; native increment is
`sub_465F10`. Offline updater `sub_466450` calls it at `0x46663B`, then updates
oldest-villager statistic `dword_4D6E00`. Save/restore routines
`sub_45DB30`/`sub_45DBE0` persist the `0xA8` age object.

The disabled helper scans stride `0x2E3C` using a supplied 150/256 bound and
requires active `+0x1CC4 != 0`, status `+0x1CC7 == 0`, and positive signed
health `+0x1C40`. It performs only raw store `+0x1B8C = 360`, bypassing the
native oldest-stat/transition route. The selected-age candidate also uses a
raw store, which is not native proof. Status `+0x1CC7` lifecycle semantics
remain incomplete.

The transaction compares unsigned Technology Points at `0x4D6F88` with
1,000,000, deducts through `sub_41E300`, dispatches command 8, and reports
`Purchased.`. It charges when no record changes or all eligible villagers are
already 18, returns zero result counts, and has no rollback.

VV4 age 18 remains ON HOLD. Processed age `+0x1C3C`, nursing/pregnancy
companion `+0x1C4C`, pending baby count `+0x1C50`, and all unrelated fields
must never change. Although the candidate instruction stream does not directly
write them, that is not proof of complete semantics. Future births, clones,
and Event-created villagers must remain native, and complete guarded
stock-plus-expanded placement/composition is not certified.

### VV3 All Villagers are 18 exact-build boundary

Corrective audit `295b5d1e228c501d0e14b1f869f11b0caa3a07bd`
applies to the exact 831,488-byte executable with SHA-256
`8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`.
It confirms signed target/display age `+0xDC4`, 20 units per year, and age 18
value 360. Native elapsed updater `sub_45F3E0` calls increment routine
`sub_45C640` at `0x45F5C6` with `+0xDC4`, then updates the
oldest-villager statistic.

Player-confirmed live evidence changed `+0xDC4` from 372 to 360, immediately
displayed age 18, survived save/reload, and then advanced natively to 361.
`+0xE74` remained 372 and `+0xE8C` remained zero. `+0xE74` is the
player-confirmed nursing/conception-age/lifecycle timestamp and must never be
synchronized by this patch.

The remaining consequence is neutral but material: `sub_45FFE0` runs hidden
food, health, mortality, and reproduction life steps only while `+0xE74 <
+0xDC4`. Lowering `+0xDC4` below the unchanged timestamp pauses those steps
until target age advances beyond it. This does not make a target-only write
inherently invalid, and it is not a final GO.

VV3 age 18 remains ON HOLD because exact command-8 transaction/result bytes
and collision-certified stock plus both-expanded PE manifests have not been
generated. The stale dual-age desynchronization objection is retracted.

### VV2 All Villagers are 18 exact-build boundary

Disassembly commit `bd6ce555a9a197450aab7133c0a87b36fbfc6899`
applies to the exact 724,992-byte executable with SHA-256
`46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677`.
It confirms signed target/display age `+0x530`, processed simulation age
`+0x534`, 20 units per year, and age 18 value 360. Native life updater
`sub_43B690` advances target age at `0x43B8FD`, updates the oldest statistic,
runs full life catch-up, and increments `+0x534` at `0x43C09A`.

The disabled command-8 candidate scans stride `0xE48C` over 256 supplied slots,
tests active `+0x30` and positive signed health `+0x52C`, but omits native
special/esteemed exclusion `+0x558`. It writes only `+0x530 = 360`, leaving
the dual ages desynchronized.

Pregnancy writer `sub_44B980` stores processed age into marker `+0x540`, and
delivery requires `marker + 40 < processed age`. The selected-age candidate
instead writes `+0x530 = 360`, `+0x534 = 360`, and nonzero `+0x540 = 318`.
That violates the mandatory requirement that nursing timer/state remain
byte-for-byte unchanged. Neither candidate route is semantically safe.

The transaction at `state+0x2EADC` precharges 1,000,000, returns zero counts,
and has no no-op refusal, affordability recheck, or rollback. Love Note
`0x422006`, Gong pregnancy `0x44EB3E`, and Silver Mirror clone `0x4217F9`
remain separate native paths, without claiming complete origin classification.
VV2 remains ON HOLD, independently blocked by the withdrawn `.shr` transport:
its encoded VAs are `0x2000` below the actual mapping and the section is not
executable.

### Future Full Mastery value contract

Any future certified Full Mastery implementation must set every native skill
to the true native maximum 100: five skills in VV1–VV4 and six in VV5. A
Master-rank threshold such as 88, 90, or a candidate value of 90 is not Full
Mastery. This requirement does not authorize any contained command or raw
store; native side effects, eligibility, transaction, and placement still need
independent per-game GO proof.

New Believers uses the authoritative active predicate, health check, and
believer faction byte. Heathens are excluded from all three operations and are
left byte-for-byte unchanged. Converted records are eligible only when their
current faction byte identifies a believer.

The payloads retain the stock save structures and use the selected mode's
physical record bound. For expanded VV3–VV5 saves, the bound is the patched
256-record marker, so a sparse slot 255 is covered even when the displayed
population is below 150. Runtime/player confirmation remains pending until
the modified games are exercised by the player.
