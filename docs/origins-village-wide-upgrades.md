# Origins village-wide upgrades

## Current atomic-payload safety containment

All five `vvN_origins_village_wide_upgrades` records are fail-closed and are
not offered by the catalog, GUI, CLI, or Select All. Commands 6, 7, and 8 share
one atomic payload, so the complete feature remains unavailable until each
game receives a full-payload GO gate. The VV4 audit
`628e0d9217b92b9cd695655842b09d74689a0238` proves that command 7's direct
`90.0` mastery stores bypass eight native mutations. The VV5 audit
`02581c8f518e27ebd5fc7d2972db5597ab08ed35` records unresolved native-counter,
eligibility, no-change, inheritance, and expanded-layout requirements. VV3 is
ON HOLD under exact-build audit
`089957227c0db6a4c3128045519ffa27b201a00e`; VV1 is not certified.

The manifests below remain as disabled diagnostic evidence; their payload
bytes are not applied. Containment does not clear or rewrite existing save
fields, issue a refund, or copy a companion DLL. Base Origins remains
independently selectable for VV1, VV3, VV4, and VV5; VV2's complete Origins
pair remains separately contained after its reported crashes.

The five historical features are separate, game-scoped manifests:

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
Running from Dislikes and writes Running only to a free normal Like slot. A
villager with all three normal Like slots occupied is skipped without changing
an unrelated Like. After processing, the result dialog uses these exact CRLF
lines (with actual counts): `Skipped over X villagers. Reason: Already 3
likes.` then `skipped over Y villagers. Reason: already likes running`; when
any Running dislike was removed it adds `Removed running dislike from Z
villagers` without a period. A villager who already Likes Running is not counted
as a full-Like skip. The charge is one million tech points for the
village-wide purchase, not per villager. The implementation is tailored to each
supported executable: it independently reads the numeric Running ID certified
in that game's exact stock preference table. All five current tables happen to
resolve Running to ID 38, but that is not a blanket cross-game assumption. The
certified preference-table evidence offsets are VV1 `0x7B260`, VV2 `0x8B808`,
VV3 `0x97488`, VV4 `0xA0CD8`, and VV5 `0xAEF60`; each manifest also records its
exact Likes/Dislikes offsets and physical record stride.

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

Disassembly commit `cee9a195faed187c847672bf36d46935a9f67ad3`
applies to the exact 831,488-byte executable with SHA-256
`8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`.
It confirms signed target/display age `+0xDC4`, 20 units per year, and age 18
value 360. Native elapsed updater `sub_45F3E0` calls increment routine
`sub_45C640` at `0x45F5C6`, then updates the oldest-villager statistic.
Life catch-up `sub_45FFE0` separately advances processed simulation cursor
`+0xE74` one unit at a time while running native life simulation.

The disabled command-8 helper scans stride `0x1F8C` over a supplied 150/256
bound, accepts active `+0xF10 != 0` with positive signed health `+0xE78`, and
performs only `+0xDC4 = 360`. It does not synchronize `+0xE74`, so moving a
younger target forward or an older target backward leaves the dual ages
inconsistent. Its active/health checks are not a complete ordinary/status
predicate.

The selected-age candidate is not a safe precedent: it changes `+0xE74` and
also changes nonzero nursing/pregnancy marker `+0xE8C`. That conflicts with
the mandatory requirement that nursing timer and state never change. Neither
raw policy is semantically approved.

The transaction compares unsigned Technology Points at `0x582644`, directly
subtracts 1,000,000, dispatches command 8, and reports `Purchased.`. It charges
no-qualifier and all-already-18 cases, returns zero result counts, and has no
recheck or rollback. VV3 age 18 remains ON HOLD pending dual-age policy,
native transitions/statistics, ordinary eligibility, future Event/birth/clone
exclusions, and complete guarded stock-plus-expanded placement/composition.

New Believers uses the authoritative active predicate, health check, and
believer faction byte. Heathens are excluded from all three operations and are
left byte-for-byte unchanged. Converted records are eligible only when their
current faction byte identifies a believer.

The payloads retain the stock save structures and use the selected mode's
physical record bound. For expanded VV3–VV5 saves, the bound is the patched
256-record marker, so a sparse slot 255 is covered even when the displayed
population is below 150. Runtime/player confirmation remains pending until
the modified games are exercised by the player.
