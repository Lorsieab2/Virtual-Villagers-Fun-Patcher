# Appearance Upgrade Requirements Contract

This document records the requirements and evidence boundary for the proposed
appearance upgrades. It is a requirements contract only: no currently shipped
patch advertises or implements these options.

## Exact supported executable builds

| Game | Executable size | SHA-256 |
| --- | ---: | --- |
| Virtual Villagers - A New Home | 581,632 bytes | `1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D` |
| Virtual Villagers - The Lost Children | 724,992 bytes | `46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677` |
| Virtual Villagers - The Secret City | 831,488 bytes | `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503` |
| Virtual Villagers - The Tree of Life | 929,792 bytes | `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` |
| Virtual Villagers - New Believers | 991,232 bytes | `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D` |

## Change Outfit

Change Outfit belongs in the existing Villager Upgrades window. It must target
only the selected active, living villager. VV5 current Heathens are always
ineligible. Opening the picker never charges tech points and must show the
selected villager's composed current head and body.

Left and right arrows wrap through every valid outfit/body choice proved by the
exact game's native catalog. The non-edited head remains the current head in the
preview. OK must revalidate the selected record, selection identity, eligibility,
funds, and chosen catalog entry, then deduct exactly **5,000 tech points once**
and write only the proven body/outfit field(s). Cancel, close, invalid or stale
selection, insufficient funds, and selecting the unchanged outfit must write
nothing and charge nothing.

## Change Head

Change Head has the same selected active/living eligibility and atomic picker
rules, costs exactly **5,000 tech points**, and writes only the exact proven
genetic-head field. The picker must warn explicitly: **“Warning: This will change
the villager's head genetics.”** VV2–VV5 must expose every exact-build-proved
young and old/gray head choice. If the native representation cannot persistently
select those variants, the feature remains STOP rather than guessing.

## VV5 Give Heathen Mask

Give Heathen Mask is an individual Villager Upgrades option for a selected active,
living believer. Current Heathens are refused without charge and remain
byte-identical. The picker choices, in order, are exactly: Chief's mask, blue
mask, red mask, orange mask, and no mask. The normal cost is **5,000 tech points**;
the cost is exactly **0** only when Play as the Heathens is active. Persistence is
cosmetic only: never write faction, type/tag, conversion, AI, action, puzzle,
health, sickness, skill, genetics, age, or pregnancy/nursing state.

## VV5 Play as the Heathens!

Play as the Heathens! is a separate optional cosmetic patch, not an Origins or
cheat upgrade. Every current believer with no manual mask override defaults to
the blue Heathen mask, including records created by every native spawn,
activation, birth, clone, event, barrel, initialization, and conversion path.
Every current Heathen renders with no mask. A converted former Heathen follows
the current faction immediately. A manual believer mask or explicit no-mask
choice overrides the blue default. The patch must not mutate faction, AI,
puzzles, conversion, body tint, identity, spawn state, or any save/gameplay
field.

## Evidence boundary and STOP conditions

Vanilla base-game save recognition is mandatory. Executable growth is allowed,
but must preserve loading of vanilla saves. Exact per-game fields, catalogs,
render paths, persistence, ABI, and collision-free cave or new-section placement
remain **STOP** until independently proved by exact-build disassembly. The VV1
`+0x364` outfit candidate, ordinary `0..19` range, and F6 research are foundation
evidence only; they do not authorize chooser-preview implementation. No
appearance upgrade may be enabled from cross-game assumptions.

This contract does not change executable manifests, payloads, companion DLLs,
save data, or runtime behavior. Player/runtime confirmation remains pending.
