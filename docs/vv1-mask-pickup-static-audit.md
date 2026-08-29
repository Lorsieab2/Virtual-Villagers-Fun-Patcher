# VV1 mask pickup/held static audit

This audit is against the exact stock executable copied to
`research/stock-executables/Virtual Villagers - A New Home.exe`:

* size: `581632` bytes (`0x8E000`)
* SHA-256: `1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D`

It is a static binary/source audit. It does not certify player-visible
rendering, save/reload, or acceptance of the patch in a running game.

## Confirmed render topology

The ordinary frame path reaches the central village compositor at
`0x424090 -> call 0x437790` (`0x4240FE`). The compositor has two villager
render loops:

* `sub_437790`: loop 1 begins its per-villager work at `0x437798`.
* `sub_4388E0`: loop 2 begins its per-villager work at `0x438900`.

Both loops resolve a record from the manager's render-order array, read its
position and pose/action fields, and issue the stock draw thunks. The first
loop ends at its `0x4388CE` increment/`0x100` bound; loop 2's last draw call is
`0x4392B1`, before the separate hit-test function beginning at `0x4392D0`.

The exact stock draw-thunk wrappers and every direct callsite in these two
loops are:

| thunk | role in the loop | direct callsites |
| --- | --- | --- |
| `0x409410` | seven-argument scaled draw | `0x437AA8`, `0x437B45`, `0x437BAC`, `0x437C71`, `0x437D17`, `0x437E4D`, `0x437F53`, `0x437FB9`; `0x438A0E`, `0x438B24`, `0x438B9A`, `0x438CE3`, `0x438D3F`, `0x438D86`, `0x438DE2`, `0x438E3D`, `0x438EAA`, `0x438EFC`, `0x439009`, `0x439059`, `0x4390A3`, `0x43918C`, `0x439206`, `0x439256` |
| `0x4093E0` | adult five-argument draw | `0x43808A` |
| `0x4093C0` | alternate child/swim five-argument draw | `0x438150`, `0x438220`, `0x438273`, `0x438296`, `0x4382E9`, `0x438337`, `0x43838D`, `0x4383D5`, `0x43854F`, `0x4385A3`, `0x4385E9`, `0x438733`, `0x438787`, `0x4387CD` |
| `0x4093D0` | alternate non-head five-argument draw | `0x437BFA`, `0x437DDD`, `0x437EE3`, `0x4381CD`, `0x438430`, `0x438483`, `0x4384FA`, `0x438638`, `0x43868B`, `0x4386D8`, `0x438829`, `0x43887C`, `0x4388C9` |
| `0x409420` | second-loop non-head five-argument draw | `0x438FA6`, `0x43912C`, `0x4392B1` |

These are 55 direct wrapper calls in the two central loops. The head-mask
hook's caller gate `0x437790 <= return_address < 0x4392D0` therefore covers
both loops while excluding the Details portrait and unrelated UI/map/effect
draw clusters. The gate's upper bound is conservative: `0x4392D0` is the
next function, not another draw call.

The loop-1 and loop-2 identity stashes at `0x437798` and `0x438900` provide
the current record index to the shared mask hooks. The source hook then
accepts only the native head atlases: the adult head (`0x3E008`) and child
head atlases (`0x3DFF8`/`0x3DFF4`). Action sheets, body atlases, and the other
non-head five-argument draws pass through unchanged. This covers the
branch-specific adult, child, swim/sit, and other pose paths represented by
the head callsites; it does not invent a separate action-sheet mask floor.

The same wrappers are also called by non-villager clusters around
`0x40C4EF..0x40C65B`, `0x41ABA0`, and `0x433B5B..0x434016`. Those callers use
tile/effect/UI objects rather than villager records and are outside the gate.

## Details portrait boundary

`sub_437340` is a separate Details portrait compositor. Its four head draw
calls are at `0x43741B`, `0x4374A4`, `0x437503`, and `0x437556`; the body draws
are at `0x4373D1`, `0x43745A`, `0x4374D5`, and `0x437528`. The existing four
portrait capture caves call the shared portrait helper after the original
head draw. Because these callsites are below `0x437790`, the village hook does
not double-draw the Details portrait. Reopening Details is a distinct runtime
check, not a missing static callsite.

## Pickup/held path

The stock pickup path does not contain a second villager renderer:

1. `0x4392D0` is the hit-test/identity function. It scans up to 256 records,
   checks occupied/status and cursor bounds against the manager scroll object,
   and returns the matching index. Its direct callsite is `0x425226`.
2. `0x439410` is not a draw routine. It converts cursor coordinates to the
   selected record's world position and writes record fields `+0x4` and
   `+0x8`. Its direct drag/update callsites are `0x425937` and `0x423FD1`,
   both passing the selected index and cursor-adjusted coordinates.
3. The per-frame routine at `0x424090` calls the ordinary village compositor
   at `0x437790` after this update path. The central loops subsequently read
   the record position and dispatch the same head/action draw thunks listed
   above.

This is static confirmation that a held villager remains a record in the
ordinary central render loops with cursor-adjusted position data. There is no
separate held-villager draw callsite for the mask patch to hook, and no exact
ABI/preimage evidence authorizes another pickup-specific hook. No pickup hook
was added.

## Save boundary and remaining player trace

Save-slot persistence remains bound to the stock save-builder entry at
`0x402ED0`, whose original first two instructions are
`mov eax,[esp+4]; mov edx,[ecx]`. The guarded six-byte splice replays both
loads in the owned `.vv1mc` cave, captures only validated slots 1 through 5
in `.vv1md`, and resumes at `0x402ED6`. This proves the argument and detour
preimage, not a successful player save/reload cycle.

The remaining minimum player trace is: select a masked adult and child; pick
each up and carry them while changing facing and visible action/pose; verify
the mask follows during the hold and after release; open/reopen Details; save,
reload, and switch slots. Report a held-only failure separately from a normal
village or Details failure. No game was launched for this audit, so those
player-visible and runtime/save results remain unverified.
