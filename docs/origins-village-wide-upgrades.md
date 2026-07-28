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

New Believers uses the authoritative active predicate, health check, and
believer faction byte. Heathens are excluded from all three operations and are
left byte-for-byte unchanged. Converted records are eligible only when their
current faction byte identifies a believer.

The payloads retain the stock save structures and use the selected mode's
physical record bound. For expanded VV3–VV5 saves, the bound is the patched
256-record marker, so a sparse slot 255 is covered even when the displayed
population is below 150. Runtime/player confirmation remains pending until
the modified games are exercised by the player.
