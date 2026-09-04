# VV2 Heathen-mask runtime: shipped, and the invariants it satisfies

The VV2 mask runtime **ships as part of `vv2_enable_origins_exclusive_features`**.
It is not a separate catalog entry, which makes it easy to look for a
"vv2 mask" feature id, find nothing, and wrongly conclude it is unintegrated.
That mistake was made in an earlier revision of this file and is the reason the
file now leads with the correction.

Evidence, from the shipping artefacts rather than from source:

- `data/vv2_origins_feature.json` contains the `.mtab` and `.vvmk` section
  entries.
- The shipped `assets/origins/VVFP VV2 Origins Icons.dll` exports
  `Vv2MaskRestore`, `Vv2MaskSaveSidecar`, `Vv2ExtractAtlas`, and the
  three-argument `_ShowVV2AppearanceChooser@12`.

So a normal catalog selection of VV2 Origins applies this runtime, and any
review finding against it is a finding about shipped behaviour.

## Invariants this runtime already satisfies

These were once open review findings. They are now implemented, and are recorded
here as invariants to preserve rather than as work to do — presenting them as
blockers would send an integrator toward rework that is already done.

1. **The companion exports match the bridge.** The shipped DLL provides ordinal
   100, `_ShowVV2AppearanceChooser@12`, `Vv2MaskRestore` and
   `Vv2MaskSaveSidecar`, so the three-argument bridge resolves the function it
   expects.

2. **Persistence is namespaced by save slot.** `build_vv2_mask_stage2.py`
   tracks the slot explicitly — the save-path builder publishes it, the
   per-frame sweep reloads the sidecar when it changes, and the DLL reads
   `SLOT_VA` to choose `vv2_masks_<slot>.dat`. Village 2 can therefore neither
   show nor overwrite village 1's masks.

3. **The sweep persists what it clears.** Slot capture and the post-sweep save
   are wired, so a freed slot does not resurrect a stale nibble on restart.

4. **Appearance for All compares before charging.** The companion materialises
   the target head/body/mask values and compares them against the eligible
   villagers, so a selection that changes nothing does not deduct 450,000.

5. **The atlas is published atomically.** Extraction writes
   `heathen_masks.png.tmp` and only then promotes it, and the path-length check
   reserves room for the staging suffix — so a short or failed write cannot
   leave a truncated PNG that every later launch skips re-extracting.

6. **The atlas builder is portable.** `build_vv2_mask_atlas_exact.py` derives
   its root from `Path(__file__).resolve().parents[1]` rather than an absolute
   author-only path.

Module-path handling is likewise done: both companions reject a truncated path
rather than deriving a save folder from a fragment.

```c
n = GetModuleFileNameA(GetModuleHandleA(NULL), exe, MAX_PATH);
if (n == 0 || n >= MAX_PATH) return 0;   /* empty or truncated -> skip */
```

## The lesson worth keeping

Absence of a feature id is not absence of a feature. The VV2 mask runtime is
bundled into the Origins feature, so `load_fun_patches()` never lists it
separately. Check the manifest sections and the companion's export table before
concluding that anything is unshipped — and never use "it does not reach a user"
to close a review thread without that check.
