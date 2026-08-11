# VV4 Time-Warp-only Expanded-256 candidate

`scripts/build_vv4_time_warp_only_candidate.py` consumes the authenticated
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

Build:

```powershell
$env:PYTHONPATH = "src;scripts"
python scripts/build_vv4_time_warp_only_candidate.py `
  outputs/expanded-256-audit/vv4-renders/vv4-experimental_expanded_256_progression-base.exe `
  outputs/vv4-time-warp-only-candidate/VV4-Expanded-256-Time-Warp-Only.exe
```

Expected executable SHA-256:

`3AD22192212E3D82455EF771AB7B37E841082EE08F3FF10AEB826F2EE5D0AE0F`
