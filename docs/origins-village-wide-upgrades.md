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
still under audit and VV1 is not certified.

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

Grant Full Mastery to All Villagers writes only the native five skill fields in VV1–VV4 or six
skill fields in VV5 for eligible active, living villagers. All Villagers are
18 writes only the displayed-age field (360 internal age units). It does not
write nursing timers, pregnancy timers, pregnancy state, movement speed,
movement initialization, unrelated preferences, or other record fields.

New Believers uses the authoritative active predicate, health check, and
believer faction byte. Heathens are excluded from all three operations and are
left byte-for-byte unchanged. Converted records are eligible only when their
current faction byte identifies a believer.

The payloads retain the stock save structures and use the selected mode's
physical record bound. For expanded VV3–VV5 saves, the bound is the patched
256-record marker, so a sparse slot 255 is covered even when the displayed
population is below 150. Runtime/player confirmation remains pending until
the modified games are exercised by the player.
