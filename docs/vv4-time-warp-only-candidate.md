# VV4 Time-Warp-only Expanded-256 candidate

the VV4 Time Warp-only candidate builder (removed; the candidate's bytes are the checked-in manifest) consumes the authenticated
clean Expanded-256 progression base and applies only
`vv4_expanded_256_time_warp`. It deliberately does not use the all-current
Origins render, which contains additional Origins menu rows.

The tech screen exposes the `Upgrades` control. The companion menu state has
only `Time Warp` enabled; the other Origins rows remain unavailable. The
existing `.vv4x` serializer/reader section is retained so the candidate keeps
the reviewed 256-record save extension.

This is a static candidate, not a runtime-safe or publication-ready release.
Runtime save/load/reload, fault tracing, atomic save-writer coverage, and live
player confirmation remain required. The candidate also requires the exact
`data/candidates/VVFP VV5 Task9 Origins Icons.dll` companion copied as
`VVFP Origins Icons.dll`.

Build: **no longer reproducible.** The builder that produced this candidate,
`scripts/build_vv4_time_warp_only_candidate.py`, has been removed along with the
expanded-256 tooling it depended on, and nothing in the tree renders it today.
This document is retained as a record of what was built and verified, not as a
recipe. Reviving it would need a fresh builder written against the current
expanded-256 state, which is itself no longer a selectable patch mode.

The expected executable SHA-256 below still identifies the historical artifact:

`3AD22192212E3D82455EF771AB7B37E841082EE08F3FF10AEB826F2EE5D0AE0F`
