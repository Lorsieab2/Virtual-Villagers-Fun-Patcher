# VV2 Heathen-mask runtime: deferred, and the constraints it must meet

The VV2 mask runtime exists in the tree but is **not integrated into the shipped
catalog**. `load_fun_patches()` lists no VV2 mask feature, so the production VV2
manifest applies neither the `.mtab`/`.vvmk` sections, nor the render/init/sweep
hooks, nor the atlas. Normal patcher output is unaffected by any of it.

That is a deliberate state, not a half-finished ship. This file records the
constraints review raised against that code, so they are not lost now that the
review threads are closed. Anyone integrating it has to satisfy all of them.

## Blocking, before it can ship

1. **Rebuild and commit the companion.** The shipped
   `assets/origins/VVFP VV2 Origins Icons.dll` still exports the four-argument
   `_ShowVV2AppearanceChooser@16`, lacks ordinal 100, and lacks `Vv2MaskRestore`
   and `Vv2MaskSaveSidecar`. A three-argument bridge resolving the old
   four-argument export will dereference garbage. The companion rebuild is a
   hard prerequisite, not a follow-up.

2. **Namespace persistence by save slot.** Every VV2 save currently shares one
   `vv2_masks.dat`, while the game has slots 1-5. An index-keyed table then
   bleeds between villages: masks assigned in one village are applied to
   unrelated villagers occupying the same record indices in another.

   This is a solved problem elsewhere in this repository — VV1, VV3, VV4 and VV5
   all key the mask sidecar to the active save slot for exactly this reason.
   Copy that, do not re-derive it.

3. **Persist masks cleared by the free-slot sweep.** The sweep clears the
   in-memory table without updating the sidecar, so a restart restores the stale
   nonzero byte. Because a freed slot's seen-alive latch starts at zero, the
   sweep deliberately leaves it intact, and a newborn reusing that slot inherits
   a mask nobody chose. The sidecar has to be written on sweep, not only on
   purchase.

4. **Do not charge when nothing changes.** Change Appearance for All deducts
   450,000 without comparing the selection against the eligible villagers'
   current head/body/mask. Choosing a mask every villager already wears, or
   buying with no active records, charges in full for no effect.

   The shipped village-wide rows already solve this: they report
   `VV2_RES_NO_CHANGE`, return 0, and the executable charges only on a success
   return. Follow that pattern.

5. **Publish the atlas only after a complete write.** A short or failed
   `WriteFile` leaves a truncated `heathen_masks.png`, the init hook asks the
   game to load it, and every later launch skips extraction because the file
   exists. Verify the return value *and* `w == sz`, and delete a short write
   rather than leaving it in place.

6. **Make the atlas builder portable.** `scripts/build_vv2_mask_atlas_exact.py`
   reads absolute `C:/Users/Owner/...` paths and fails on any other machine. The
   source images live under `research/vv2-mask-source`; derive the path from
   `__file__`.

## Already fixed

The module-path handling raised alongside these is done. Both companions reject
a truncated path rather than deriving a save folder from a fragment:

```c
n = GetModuleFileNameA(GetModuleHandleA(NULL), exe, MAX_PATH);
if (n == 0 || n >= MAX_PATH) return 0;   /* empty or truncated -> skip */
```
