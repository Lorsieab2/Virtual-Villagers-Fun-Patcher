# VV3 Running Stage A disabled certification candidate

This is a generated, **disabled** artifact bundle. Neither
`vv3_enable_origins_exclusive_features_running_candidate` nor
`vv3_all_villagers_like_running_candidate` is loaded by the catalog, CLI,
GUI, Select All, or ordinary output rendering. Sol byte certification is
required before any enablement.

Evidence inputs are disassembly commits
`d78db872efe04f98bd19b45c9e098bb5a25d53b8` and
`b9c7a22eb1d7cceae25160ce4d360621e7485625`. Player-confirmed Like 38 /
Dislike -1 save-and-reload persistence is supporting runtime evidence, not PE
integration proof.

## Deterministic layout

- Base-owned section: `.vvrun`, raw `0xCB000`, length `0x1000`.
- Stock RVA/VA: `0x2DF000` / `0x6DF000`; expanded RVA/VA:
  `0x3B8000` / `0x7B8000`.
- Base dispatcher: page `+0x40`, stock SHA-256
  `489F714C74C88EA5183BE01BDD82649F4B31F690BCE4679AA5C29FFD10F64880`, expanded SHA-256
  `C042D4E32F0975DF11CE3498DE10E9DCADCC84635A418E057698E329DD7D4B7E`.
- Guarded extension slot: page `+0x100`, file `0xCB100`, length `0x700`;
  entry `+0x20`, walker `+0x240`.
- No-op slot SHA-256: `42FC601B51E8AAC069B70355502C32B6985A2471E26B683A61A68EA3B91BE4E3`.
- Running slot SHA-256: `156C6C200D73BEC18B719D54F82E74A5ED6B2B1BF3CE18117A32F33FF38BBA98`.
- Stock base payload SHA-256:
  `289D4C7A72A46713CAD2217753E696F891C273EB749CF1E68011CD740F14AAE0`.
- Expanded base payload SHA-256:
  `0593E81A897BAAC47243EBACD70B01EC7ECA929627D8C3E4B0805FF826D914EF`.
- Companion DLL SHA-256: `2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9`;
  `ShowOriginsVillageWideResult@20` is ordinal
  `4`,
  RVA `0x11B0`,
  stdcall five arguments with a 256-byte result buffer.

Stock base+Running render SHA-256 is
`9E343BD485773D4CAF9C2F49BD894E5CB6D4F59B2831D1A7ECCFE2D365E10521` with PE checksum
`0x000D2AEB`. Expanded base+Running render SHA-256 is
`48FF88457CD52300A187C7F2B7712CFD86C53AC4A656C152AFFE0287178E5CCA` with PE checksum
`0x000D5361`.

The machine-readable complete map, payload deltas, page hashes, per-mode
checksums, ABI, and export map are in
`data/candidates/vv3_running_candidate_map.json`.

## Closed transaction and record contract

The candidate uses only active `+0xF10 != 0` and signed health
`+0xE78 > 0`; dormant `+0xE94` is not read. It scans exactly three Likes
`+0xFB4..+0xFBC` and three Dislikes `+0xFC0..+0xFC8`, with sentinel `-1`
and independently confirmed Running ID 38. Already-like records are skipped
without mutation. Otherwise the first empty Like is preflighted before any
Running dislike is removed; full Likes cause no mutation. All Running
dislikes are cleared, unrelated slots and order are preserved, and 38 is
written to the first empty Like.

Purchase uses an unsigned 1,000,000-point two-pass dry-run, final balance
recheck, one deduction, commit, and save ownership bit `0x4`. A zero-grant
result does not charge. Removal costs and refunds zero, clears only bit
`0x4`, does not reverse preference edits, and permits full-price repurchase.
Commands 7 and 8 are absent.

The four exact result lines are:

1. `Granted Running to %u villagers`
2. `Skipped over %u villagers. Reason: already likes running`
3. `Skipped over %u villagers. Reason: all like slots are occupied`
4. `Removed running dislike from %u villagers`

Persistent means serialized and restored, not immutable. This candidate must
preserve unrelated fields at its transaction and save roundtrip and must not
intercept native future writers. Native events and other game mechanics may
legitimately change persisted fields later.

## Ownership and removal

Base Origins remains the sole owner of hooks `0x6547D` and `0x65640`, the
section header, appended page, and checksum. Running replaces only the exact
guarded slot. Running removal restores the no-op slot without truncating or
reversing preferences. Base removal is dependency-blocked while Running is
installed; afterward it guards its bytes, restores the stock headers and
hooks, truncates exactly `0x1000`, and recomputes the checksum.
