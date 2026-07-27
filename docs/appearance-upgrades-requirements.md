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

## VV1 exact-build appearance audit

The VV1 audit (disassembly commit `8888682`) is an independent **STOP** for
both Change Outfit and Change Head. It applies to the 581,632-byte build with
SHA-256 `1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D`.

The body/outfit candidate is the DWORD at record `+0x364`; the genetic-head
candidate is the DWORD at record `+0x360`. Native random construction uses
RNG(19), values `0..18`, for one sex and RNG(20), values `0..19`, for the other.
Status/action 199 forces both fields to 19, and the clone path copies both
fields. The world renderer is `sub_437790`; the selected portrait path is
`sub_449140 -> sub_437340`; selected-index state is `+0xAD34`. Strange Berries
contains non-UI writes to `+0x360`.

The audit does not prove complete usable catalogs or special-row meaning,
exact save/load serializer mapping, custom chooser/preview and OK-time
revalidation ABI, native 5,000-tech deduction/persistence integration,
refresh/invalidation, or safe composable cave/new-section placement. The
absence of a stock chooser is not a claim that custom UI is impossible. Do not
infer young/old catalogs from constructor RNG bounds or expose row 19 merely
because status 199 uses it. Change Outfit and Change Head therefore remain
STOP for VV1 and all other games remain subject to their own exact-build gates.

## VV2 exact-build appearance audit

The VV2 audit is an independent **STOP** for both Change Outfit and Change
Head. It applies to the 724,992-byte build with SHA-256
`46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677`.

For Change Outfit, the traced record stride is `0xE48C`; the body/outfit DWORD
candidate is record `+0x54C`. Native action 69 costs exactly **5,000 tech points**.
The native chooser is `sub_4229D0`, and its cycle writer is
`sub_422890` with a native range of `0..29`. World and Detail render paths,
clone writers, and the whole-state save/load size of **197,488 bytes** were
traced. The `0..29` cycle bound is not a final user catalog: complete per-sex,
age, and special-row classification is missing.

For Change Head, the head/genetics DWORD candidate is record `+0x548`. Sex/age
atlas rendering, creation/clone/event writers, and both old/young resources
were confirmed. A native/custom head chooser, 5,000-tech purchase callback,
genetics-warning callback, complete selectable young/old catalog, OK-time
revalidation, preview/refresh and persistence ABI, and safe placement remain
unproved. The `head feels strange` string has no direct caller xref and is not
an implementation hook. Whole-state save/load evidence does not independently
prove the requested editable transaction semantics or vanilla-save compatibility
for a new sidecar. Change Outfit and Change Head therefore remain
STOP for VV2; no implementation is authorized from these fields or bounds.

## VV3 Change Outfit exact-build audit

The VV3 Change Outfit audit is an independent **STOP**. It applies to the
831,488-byte build with SHA-256
`8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`.

The exact build contains the Clothing Hut strings `The Clothing Hut`, `Choose
an outfit for your villager!`, `Do you want to spend 5000 tech points to change
this villager's clothes?`, `Getting new clothes!`, and `Not enough tech points
to make new clothes!`. Male/female body resources and young/old head assets are
present, and `sub_4227F0` and `sub_4228F0` are bounded in the disassembly export.

The literal `0x1388` (5,000) at VA/file `0x004228A2`/`0x228A2` writes manager
state `[eax+0x12FB0]`. This does **not** prove a clothing purchase, cost
deduction, selected-villager identity, or outfit-field write.

Change Outfit remains STOP. Missing proofs are selected-record validation; the
exact outfit field and every writer/copy/clone/save/load path; complete
sex/age/special/invalid catalog classification; world, Detail, and chooser
preview render/refresh behavior; the cost ABI tied to the UI strings; and
collision-free safe placement in both stock and expanded-256 layouts. Do not
infer Change Head status or implementation from these asset strings/resources;
this audit is Outfit-only.

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
