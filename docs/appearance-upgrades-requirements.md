# Appearance Upgrade Requirements Contract

This document records the requirements and evidence boundary for the proposed
appearance upgrades. It is a requirements contract only: no currently shipped
patch advertises or implements these options.

**Update:** VV1 Change Appearance (both the head field `+0x360` and the body/
clothing field `+0x364`, gated by the villager's gender field `+0x350` --
male villagers have 19 valid values (0-18) for each, everyone else has 20 --
confirmed by decompiling the exact-build villager initializer) is now
implemented as a row in the Villager Details "Upgrades" dialog, superseding
the VV1 "ON HOLD" status recorded below. It costs exactly 5,000 tech points,
charged once and only on a confirmed OK; Cancel or closing the picker
reverts both fields to what they were before it opened; the compiled
picker's gender-dependent range is verified directly against the DLL's own
machine code (`native/vv1_origins_icons/vv1_origins_icons.c`,
`ShowOriginsAppearancePicker`) in `tests/test_vv1_required_fixes.py`. The
STOP boundary below remains current for VV2-VV5, which have not been
implemented.

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
because status 199 uses it. The exact-build audit is STOP, and the requested
Change Outfit and Change Head implementations remain ON HOLD for VV1; all
other games remain subject to their own exact-build gates.

## VV2 exact-build appearance audit (`ed4cedb5a0d41b28319bf62b8d25596baa3e7a2e`)

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
for a new sidecar. The requested Change Outfit and Change Head implementations
remain ON HOLD for VV2; no implementation is authorized from these fields or
bounds.

## VV3 Change Outfit exact-build audit (`a9d3b1ff0e223c0aa5fd8504194845afa4456df1`)

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

Change Outfit remains ON HOLD. Missing proofs are selected-record validation; the
exact outfit field and every writer/copy/clone/save/load path; complete
sex/age/special/invalid catalog classification; world, Detail, and chooser
preview render/refresh behavior; the cost ABI tied to the UI strings; and
collision-free safe placement in both stock and expanded-256 layouts. Do not
infer Change Head status or implementation from these asset strings/resources;
this audit is Outfit-only.

The native transaction is nevertheless bounded: the built-hut entry is
`sub_4227F0`, the completion charge is exactly 5,000 in `sub_458DB0` case 41,
and the chooser is `sub_41C010` with cycle/write routine `sub_41BF00`.
The editable body/outfit DWORD is `record+0xDF4` with stride `0x1F8C`, and
the chooser accepts exactly `0..28`, wrapping in both directions. The special
constructor value `29` is outside the chooser's `0..28` cycle and is not a user
catalog entry. The chooser writes the live record immediately on
initialization/arrows; close is the only exit, with no Accept/OK commit, Cancel
control, rollback, or refund; there is no rollback snapshot. The paid path captures
only a mutable slot index and its later open path does not fully revalidate
occupancy, health, status, or identity. Save/load and clone provenance for
`+0xDF4`, a semantic catalog, stable identity, atomic preview/OK/Cancel
behavior, and collision-free stock/expanded placement remain open.

## VV4 Change Outfit exact-build audit (`23fee766bfbcccc634c565c6bc88f3318e30f244`)

The VV4 audit is **ON HOLD** for the requested atomic custom picker. It applies
to the 929,792-byte build with SHA-256
`6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220`.
The native Clothing Hut transaction uses action 71, charges exactly 5,000,
and opens `sub_419710`; `sub_419590` cycles and immediately writes the DWORD
body/outfit field at `record+0x1BBC` (stride `0x2E3C`) through the `0..28`
domain. The native close path keeps the immediate write; there is no separate
Accept/OK commit, Cancel rollback, or refund. Its pending candidate uses an
index with a `0..149` resolver and the `+0x1CC4/+0x1CC7` predicate, but no
stable identity token is captured and the later chooser path does not provide
the requested atomic revalidation.

World/detail/preview consumers, clone copying, and the `+0x1B8C` save/load span
containing `+0x1BBC` are code-confirmed. The complete semantic catalog and
human-readable row meanings, preview-only working state, OK-time commit,
Cancel rollback, identity guard, and collision-free stock/expanded placement
remain unproved. No custom Change Outfit implementation is authorized.

## VV5 Change Outfit exact-build audit (`313651623d2687d3f53ce5cc30c9f5ad07051a8d`)

The VV5 native chooser facts are documented, but the requested believer-only
atomic/custom expanded-layout contract remains **ON HOLD**. This applies to the
991,232-byte build with SHA-256
`92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D`.
The native action-90 path rechecks and precharges exactly 5,000 at
`0x46CEC7`/`0x46CED1`, then opens `sub_419EC0`;
`sub_419CE0` cycles and immediately writes the DWORD body/outfit field at
`record+0x1BBC` (native stride `0x2F44`) over exactly `0..28`. Accept keeps
the immediate write through button `+0x50`. Cancel button `+0x5C` restores the
original field at `0x419E8E` and refunds exactly 5,000 through
`0x419E94`/`0x419E9E`, for a net-zero cancel outcome.

The native path persists the field through the `+0x1B8C` save/load span and
copies it through clone/summary paths; world, detail, and chooser preview
renderers consume it. The dialog path stores only a mutable slot index. It
does not test current faction `+0x1CEC`, so a code-confirmed believer-only
contract and no-charge current-Heathen refusal are not present in this path.
The numeric `0..28` selector is exact, but complete named/semantic catalog
meaning remains open. Stable identity, preview-only working state, atomic
OK-time commit, Cancel semantics for the requested custom route, complete
eligibility guards, and collision-free stock/expanded placement remain
unproved; no custom Change Outfit implementation is authorized.

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

## Change Head exact-build evidence (all five ON HOLD)

The five independent exact-build audits below record native head storage and
rendering facts only. The requested custom Change Head picker remains ON HOLD
for every game; no UI row, manifest feature, helper, runtime bytes, or output
is authorized from these partial facts.

### VV1 (`ccb5d973909faf222745968cca15109654f767f4`)

For the 581,632-byte VV1 build, the runtime stride is `0x3D8` and the head
sprite index is DWORD `record+0x360`. `sub_43C350` and `sub_41C000` construct
the field with sex-dependent `RNG(19)`/`RNG(20)` domains; status 199 forces
head and body to 19. `sub_43C840` copies the head at `0x43C9D9 -> 0x43C9DF`.
World rendering is `sub_437790`; Detail uses `sub_449140 -> sub_437340` and
selected index `+0xAD34`. The resource constructors prove the male/female
head atlases and numeric creation bounds, not a complete semantic young/old,
gray, sex, special, or invalid catalog.

No complete active/living/status guard, stable identity revalidation,
genetics-warning path, head-specific 5,000 transaction, private preview,
atomic OK commit, Cancel rollback, serializer mapping, vanilla-save contract,
or safe stock/expanded placement was proved. VV1 Change Head remains ON HOLD.

### VV2 (`bfd2ad7f07efa730d962787149c1348f2a6c336b`)

For the 724,992-byte VV2 build, the runtime stride is `0xE48C`; the head-family
DWORD is `record+0x548`, with active `+0x30`, signed health/living `+0x52C`,
and sex `+0x538`. Constructor `sub_44C600` writes inherited or `RNG(30)`
values clamped to `0..29`; additional copy writers include
`0x44D015 -> 0x44D01B` and `0x44D365 -> 0x44D36B`. Separate young/old male
and female resources each declare 30 rows, and world/Detail paths consume the
field.

No native Change Head chooser, head-specific 5,000 transaction, warning,
private preview, OK commit, Cancel rollback/refund, complete writer ledger,
stable identity or open/OK eligibility revalidation, field-specific
save/load/vanilla-save proof, or stock/expanded placement was established.
VV2 Change Head remains ON HOLD.

### VV3 (`cdf50e399360c1eba04449d359b0d477573b7361`)

For the 831,488-byte VV3 build, the runtime stride is `0x1F8C` and the head /
genetics DWORD is `record+0xDF0`; age is `+0xDC4`, sex `+0xDC8`, slot/ID
`+0xEDC`, and active `+0xF10`. `sub_45C540` initializes `RNG(30)` values
`0..29`; `sub_456120` handles inheritance/clamping and the special
sex-branch lists, while `sub_417610` is the bounded event writer. Four atlas
resources provide 30-row young/old male/female selection; world and Detail
renderers consume the raw head row. Clone and compact save/load of the head
field are code-confirmed.

The exact build has no head-specific purchase, insufficient-funds recheck,
warning, chooser, private preview, OK commit, Cancel rollback/refund, stable
identity/eligibility transaction, or collision-free stock/expanded placement.
VV3 Change Head remains ON HOLD.

### VV4 (`9dd368fe6248c55f53be9a620025e2a655854ddd`)

For the 929,792-byte VV4 build, head is DWORD `record+0x1BB8` and body is
`+0x1BBC`. `sub_45EF10` is the bounded constructor writer; clone/save/load
copy the `+0x1B8C..+0x1C33` block (head maps to compact `+0x30`). The `bigheads`,
`male_heads`, and `female_heads` resources are used; age `>=1100` selects the
proven old-frame offset rather than a separate old-head resource. World and
Detail renderers consume the head field, and inheritance/pregnancy paths pass
it onward.

The only native 5,000 purchase is clothing action 71, not head editing. No
head chooser, warning, private preview, atomic OK/Cancel transaction, stable
identity, complete semantic catalog, signed-health/special-status revalidation,
or collision-free stock/expanded placement was proved. VV4 Change Head remains
ON HOLD.

### VV5 (`388bf9a4e3ee400ba7168317526e9511c77a1048`)

For the 991,232-byte VV5 build, the runtime stride is `0x2F44` and head is
DWORD `record+0x1BB8`; active is `+0x1CD4`, transient eligibility `+0x1CE1`,
signed health `+0x1C40`, current faction `+0x1CEC` (`0` believer, nonzero
Heathen), and type/status `+0x1CFC`. Constructor, inheritance, pregnancy/
delivery, clone, save/load, conversion continuity, and world/Detail rendering
of the head field are code-confirmed; age `>=1100` uses the native `+8` row
selection.

The hard eligibility boundary is current faction: no current Heathen may open,
preview, be charged, or be modified by Change Head. A converted former Heathen
is eligible only after native conversion makes `+0x1CEC == 0` and all other
active/living checks pass. The native preview `sub_419D80` reads the live
record and has no private head override. No head-specific transaction,
genetics warning, stable identity, atomic preview/OK/Cancel route, complete
young/old/special catalog, full current-faction revalidation, or
stock/expanded placement was proved. VV5 Change Head remains ON HOLD.

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

## VV5 mask-system exact-build audit (STOP)

The VV5 mask-system audit (disassembly commit `870d236`) applies to the exact
991,232-byte build with SHA-256
`92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D`.
The current faction byte is record `+0x1CEC`; generic selector bytes are
`+0x1CED` and `+0x1CEE`; `+0x1CEF` is a persisted but currently unconsumed
sidecar candidate; and the type dword is `+0x1CFC`. The world mask atlas rows
are blue `0`, orange `1`, red `2`, purple `3`, and Chief `4`. The mask overlay
is gated by current faction. Reset, spawn, conversion, clone, and save/load
behavior are mapped, while the stock Detail portrait has no mask overlay.

`Give Heathen Mask` remains **STOP**: the native chooser/cost and
selected-active-living-current-believer/no-charge-Heathen transaction, safe
manual encoding, Detail overlay/refresh, and collision-free stock+expanded-256
placement are not proved. `Play as the Heathens!` remains **STOP**: complete
all-spawn Play interception, Detail overlay/refresh, and collision-free
stock+expanded-256 placement are not proved. Neither feature is registered or
advertised. This STOP records evidence only; it changes no manifests,
generators, companion DLL, outputs, prices, save behavior, or executable
payloads.

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
