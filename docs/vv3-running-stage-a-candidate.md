# VV3 Running corrected certified artifact

This generated artifact is enabled for replacement runtime playtesting after
final certification `c62fba9214de7c6092365e99c72bd81a59d3888c`.
`vv3_all_villagers_like_running` is loaded with its base Origins dependency;
commands 7 and 8 remain absent.

Evidence inputs are disassembly commits
`d78db872efe04f98bd19b45c9e098bb5a25d53b8` and
`b9c7a22eb1d7cceae25160ce4d360621e7485625`. Stage C corrects the three
defects certified by Sol at
`f73625582adae714473068c272b90af91a57d945`: the @20 counter arguments now
use a stable base, the dispatcher preserves every nonvolatile register it
uses, and exact repair contract
`0095e605b3b488129c0623efd642e9352d8586c0` replaces the revoked owned-state
transaction. Gameplay validation remains pending.
Player-confirmed Like 38 /
Dislike -1 save-and-reload persistence is supporting runtime evidence, not PE
integration proof.

## Deterministic layout

- Base-owned section: `.vvrun`, raw `0xCB000`, length `0x1000`.
- Stock RVA/VA: `0x2DF000` / `0x6DF000`; expanded RVA/VA:
  `0x3B8000` / `0x7B8000`.
- Base dispatcher: page `+0x40`, stock SHA-256
  `ADBC6F0AEBB33729EFDCC85E86B396A43E2C9AD97F5D8E95EC7676F74FA9F756`, expanded SHA-256
  `371B7280C60F798C85FD3E0CDE5D01C80E2388F2B595C31815AA8340BCE77284`.
- Guarded extension slot: page `+0x100`, file `0xCB100`, length `0x700`;
  entry `+0x20`, walker `+0x240`.
- No-op slot SHA-256: `42FC601B51E8AAC069B70355502C32B6985A2471E26B683A61A68EA3B91BE4E3`.
- Running slot SHA-256: `3F8F3BD7FD6C1BA8D8517539581D96F8D7B14D3BF959C74157FF970E432E5B13`.
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
`D8DD412185559F2B95E1B0544877928D88FC1B6BAF0F539E94DAB6DAB6606A2B` with PE checksum
`0x000D641E`. Expanded base+Running render SHA-256 is
`657D321B2F1E9E6D6C223DB1FF0BBA38C2D761A97A6E7F21B98CE1826531A848` with PE checksum
`0x000D2A32`.

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

Running is a repeatable Buy action and has no ownership or Remove state. A
read-only dry run happens first. Zero grants show exactly
`Everyone already likes running.\r\nNo tech points have been deducted.`
without warning, charge, or writes. Positive grants show the exact universal
permanent-change OK/Cancel warning. Cancel, close, or import failure is inert.
OK repeats the identical read-only dry run, then performs the final unsigned
1,000,000-point balance recheck, one deduction, and one mutating commit.
Command 6 never reads, sets, or clears `0x5824D0 & 0x4`; stale bit 4 is
ignored. Commands 7 and 8 are absent.

The four exact result lines are:

1. `Granted Running to %u villagers`
2. `Skipped over %u villagers. Reason: already likes running`
3. `Skipped over %u villagers. Reason: all like slots are occupied`
4. `Removed running dislike from %u villagers`

Persistent means serialized and restored, not immutable. This candidate must
preserve unrelated fields at its transaction and save roundtrip and must not
intercept native future writers. Native events and other game mechanics may
legitimately change persisted fields later.

## Ownership and uninstall

Base Origins remains the sole owner of hooks `0x6547D` and `0x65640`, the
section header, appended page, and checksum. Running replaces only the exact
guarded slot. Running patch uninstall restores the no-op slot without truncating or
reversing preferences. Base removal is dependency-blocked while Running is
installed; afterward it guards its bytes, restores the stock headers and
hooks, truncates exactly `0x1000`, and recomputes the checksum.
