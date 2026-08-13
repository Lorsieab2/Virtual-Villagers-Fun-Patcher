# Tech-screen Upgrades crash hotfix

This hotfix addresses the Tech-screen Upgrades crash paths found in the current
all-five Origins upgrade implementation. No game was launched and no save file
was opened or changed during this work.

## Windows crash evidence

| Game | Faulting module | Exception | Fault offset |
| --- | --- | --- | --- |
| VV1 Modded | game executable | `0xC0000005` | `0x0000ABDE` (two events) |
| VV1 Modded | game executable | `0xC0000005` | `0x0008B530` |
| VV2 Modded | game executable | `0xC0000005` | `0x0009C5CF` |
| VV5 Modded | game executable | `0xC0000005` | `0x00094843` |

## Confirmed defects repaired

- All five base generators left an export-name pointer on the stack before
  `LoadLibraryA` in both village-wide helpers. The helpers now retain the
  reviewed relocation operand without pushing it, so their saved-register and
  return stacks remain balanced.
- VV1 assembled `.shr` helpers using raw file offsets as runtime addresses.
  Runtime addresses now use the mapped RVA, the full helper reserve is mapped
  executable, and raw `0x8B004` emits the correct `E9 27 05 00 00` jump.
- VV1 Cure's result dialog now passes all three arguments in the established
  order.
- VV1 now resolves the state-based dialog export for the Tech screen and the
  legacy villager-pointer export for Villager Details. The false unavailable
  bits that disabled both unowned doubler rows were removed.
- VV1's deferred Barrel result now uses the stock scalar-deleting destructor,
  so the allocated event object is both destructed and freed.
- VV2 Cure and village-wide scans now resolve the certified manager and use its
  `+0x52C` villager pool instead of a Tech-screen object field. The faulting
  `0x9C5CF` instruction was inside the former invalid-pool scan.
- The VV5 `0x94843` event maps to the optional Statue selector, not the Task9
  Tech page. Two stock call sites entered selectors before loading the villager
  pointer; dedicated adapters now materialize that pointer. The selector result
  arithmetic is also corrected and covered by emitted-byte tests.

## Containment applied across Tech menus

After any result in the five public base Tech routes and the active VV5 Task9
route, the custom menu now returns to the stock screen instead of immediately
reopening another external modal. This removes the shared custom-control/modal
lifetime backedge associated with the VV1 `0xABDE` child-detach fault, but the
available WER record does not contain a stack or register trace proving that
exact caller. Hidden Expanded Time Warp modes remain outside this public-route
claim.

## Evidence boundary

Generator, manifest, PE, disassembly, render, and test results are static
evidence. Player runtime confirmation remains pending and is the only basis for
the final gameplay interpretation.
