# Learning Skills Never Fails: exact-build research

This feature changes only the native work-task skill-success decision. Each
entry below is pinned to the stock executable named by `data/builds.json`.
The patched conditional branch is the decision immediately before the stock
skill-increment path; it is replaced with an unconditional transfer to that
same success path. The stock increment, cap, event, and record-write code is
not replaced.

| Game | Native dispatcher | Skill decisions | Raw branch offsets |
|---|---:|---:|---|
| VV1 A New Home | `0x43D440` | 5 | `0x3D483`, `0x3D5E0`, `0x3D72A`, `0x3D7F8`, `0x3D8AC` |
| VV2 The Lost Children | `0x44E170` | 5 | `0x4E1E2`, `0x4E37B`, `0x4E4E2`, `0x4E5E5`, `0x4E6EA` |
| VV3 The Secret City | `0x45A2C0` | 5 | `0x5A34E`, `0x5A4FD`, `0x5A67F`, `0x5A799`, `0x5A8A3` |
| VV4 The Tree of Life | `0x462A80` | 5 | `0x62B21`, `0x62D9F`, `0x62FAA`, `0x63136`, `0x632AF` |
| VV5 New Believers | `0x46B270` | 6 | `0x6B311`, `0x6B4DD`, `0x6B6C7`, `0x6B853`, `0x6B9CC`, `0x6BB7F` |

VV1--VV4 use the five work skills present in their native records. VV5 has a
sixth native decision for Devotion; the feature is attached to the New
Believers work dispatcher and does not alter heathen behavior.

The exact before/after bytes, including the long-branch relocation padding,
are recorded in the five manifest entries. This is static exact-build
evidence. Runtime/player confirmation is pending.
