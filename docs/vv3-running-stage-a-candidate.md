# VV3 Running Stage C corrected disabled certification candidate

This is a generated, **disabled** recertification bundle. Neither
`vv3_enable_origins_exclusive_features_running_candidate` nor
`vv3_all_villagers_like_running_candidate` is loaded by the catalog, CLI,
GUI, Select All, or ordinary output rendering. Sol byte certification is
required before any enablement.

Evidence inputs are disassembly commits
`d78db872efe04f98bd19b45c9e098bb5a25d53b8` and
`b9c7a22eb1d7cceae25160ce4d360621e7485625`. Stage C corrects the three
defects certified by Sol at
`f73625582adae714473068c272b90af91a57d945`: the @20 counter arguments now
use a stable base, the dispatcher preserves every nonvolatile register it
uses, and the purchase path is exactly one dry pass followed by the final
unsigned funds recheck, one deduction, and one commit pass. The candidate
remains disabled pending byte recertification. Player-confirmed Like 38 /
Dislike -1 save-and-reload persistence is supporting runtime evidence, not PE
integration proof.

## Deterministic layout

- Base-owned section: `.vvrun`, raw `0xCB000`, length `0x1000`.
- Stock RVA/VA: `0x2DF000` / `0x6DF000`; expanded RVA/VA:
  `0x3B8000` / `0x7B8000`.
- Base dispatcher: page `+0x40`, stock SHA-256
  `6A6CF8281113AE8A0ED9EE03A7811D7D0D76F2B7E791B78218DE76D87C371ABF`, expanded SHA-256
  `97CF6BD9652D10372726ED40E1878CCEECA6624A09872901FA1196A5AF63E2C2`.
- Guarded extension slot: page `+0x100`, file `0xCB100`, length `0x700`;
  entry `+0x20`, walker `+0x240`.
- No-op slot SHA-256: `42FC601B51E8AAC069B70355502C32B6985A2471E26B683A61A68EA3B91BE4E3`.
- Running slot SHA-256: `C1FB2D8C7FE4494AA85BAEB686558B190F10B671710BF72AB1A83E7D88A2318F`.
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
`494D2BE5C7464CC5A59580BFE4C805656FE4F8675A44F7BFED29AFFA45978DDE` with PE checksum
`0x000D8264`. Expanded base+Running render SHA-256 is
`B58119F639B03DEE1743445A8A3025691B0B3083FA5C5E1D159AA38E94D50532` with PE checksum
`0x000DAADA`.

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

Purchase uses exactly two walker passes: one nonmutating dry pass, then—only
after a nonzero grant count and final unsigned 1,000,000-point balance
recheck—one deduction followed by one mutating commit pass and save ownership
bit `0x4`. There is no second dry pass, mutation before charge, or post-commit
no-change branch. A zero-grant or insufficient-race result does not charge.
Removal costs and refunds zero, clears only bit
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
