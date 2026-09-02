# Duplicate purchase guards

Buying Time Warp, Island Event or Barrel of Babies more than once charges for
each purchase while only the first takes effect. This records what the cause
is, where the guard has landed, and why it has not landed everywhere — so the
next attempt starts from measurements rather than rediscovering them.

## The cause

Every game queues an Island Event by **zeroing a countdown field**:

| Game | Countdown |
| --- | --- |
| VV1 | `player + 0xA300` |
| VV2 | `player + 0x2EAE0` |
| VV3 | `manager + 0x12EF4` |
| VV4 | `manager + 0x170E0` (via the getter at `0x41FE70`) |
| VV5 | `manager + 0x17D3C` |

Zeroing an already-zero field does nothing, so a second purchase while one is
pending is a no-op the player still pays for. The guard is therefore: if the
countdown is already zero, refuse and charge nothing.

The guard must sit **after** `jb insufficient`. Its compares overwrite the
flags that branch reads — the same mistake the paused Time Warp guard made,
which was caught as a P1 on three games.

## Where it has landed

**VV3 only.** The refusal message is DLL result code 10 rather than an
executable string, because VV3's string block is full and the companion DLL
has no such limit. It costs the executable nothing.

## Why not the other four

Each was written and backed out. The blockers are measured, not assumed:

| Game | Blocker |
| --- | --- |
| VV1 | string block 764 bytes over budget; then code overlap at `0x456C04` (payload `0x5B` bytes) |
| VV2 | string block `0x29C` against a `0x278` budget; then code overlap at `0x4948A8` (`0x2AE`) |
| VV4 | overruns the native UI factory cave |
| VV5 | assembles, but shifts payload offsets that a fail-closed validator pins by exact byte position (`payload[0x4E:0x59]`, `[0x10E:0x119]`, `[0x55:0x59]`, `[0x115:0x119]`) |

Growing the payload blocks is not available either. Free zero bytes
immediately after each block in the stock image:

| Game | Free bytes after the payload |
| --- | ---: |
| VV2 | 4 |
| VV4 | 0 |
| VV5 | 8 |

They butt against other content, so the VV3 robe trick — extending the owned
range into following zeros — does not apply.

## The zero-cost idea, and why it does not work

The companion DLL owns the Tech dialog and returns the clicked row; the
executable simply returns whatever the DLL hands back. So the DLL could refuse
the click itself, and the executable would need **no new bytes at all**.

It cannot, because it has no way to read the countdown:

* `ShowVV2UpgradeMenuState(villager_menu, dialog_state)` is never passed the
  player object.
* There is no global to fetch it from. The record array *is* reachable that
  way — `0x44F4E0` dereferences a singleton at `0x499F24` — but a scan for a
  global feeding the tech-balance/countdown accesses found none.
* VV1's DLL does cache a pointer at its scratch page `+0x98`, which looked
  promising. It is the **villager-records container, not the player object**:
  read live with a village loaded, its `+0xA2FC` (tech points), `+0xA300`
  (countdown) and `+0xA318` (game speed) all read 0, while the first twelve
  `0x3D8` strides from it are populated records.

Passing the pointer in from the executable is the remaining option, and the
cheapest hook still costs roughly 20 bytes plus an export name — against the
budgets above.

## What would unblock it

Reclaiming space inside the payload blocks: auditing what is in each string
and code region and evicting anything dead. That is surgery on pinned layouts
and deserves its own branch and review, rather than being folded into an
unrelated change.
