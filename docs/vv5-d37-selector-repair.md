# VV5 D37 selector repair evidence

Status: **candidate-only; Full Mastery records remain disabled and catalog-hidden**.

This records the bounded startup/stability correction for the VV5 Origins
selector. It does not enable, package, launch, or authorize save access.

## Provenance

The supplied visual references are copied byte-for-byte under
`assets/candidates/vv5_full_mastery/provenance/`:

| File | SHA-256 |
| --- | --- |
| `VV5Mockup.jpg` | `4EF2DFC0DAE6C733C452CCB4BEA4023C0E2601EEF2396A1A38D75A4DCD57B00F` |
| `VV5Mockup2.jpg` | `104B1BE5873B1660EE4BC2E02A886C6EBB99B06CB6F0D723D20638C2B0949144` |

The mockups are provenance only. They do not alter the existing VV5 UI
geometry/art contract or introduce a runtime image dependency.

## Exact selector repair

The exact stock executable fingerprint is 991,232 bytes,
`92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D`.

At file `0x1890F` / VA `0x41890F`, the guarded stock hook is
`8B7484146A64E8` and the repaired candidate hook is
`E96C9839009090`. The owned body at file `0xDB180` / VA `0x7B2180` is
replaced with the exact 40-byte sequence:

```text
8B748414F70588D3510004000000740C832588D35100FBBE1E000000
6A64E8BD14C5FFE97267C6FF
```

The body calls native `0x403660` on both paths and jumps only to the valid
continuation `0x41891A`, where the caller's native `add esp,8` remains in
control. Branch targets `0x418916..0x418919` are forbidden. Body SHA-256:
`17DF82FD97BFED39146705143D005F20A6893ECEBA99964A14EE380C49B9E1CF`.

Install requires the exact executable fingerprint, the stock hook, a zero
40-byte body preimage, and the `.shr` raw range `0xDB000..0xDBFFF` with the
expected section header. The candidate `.shr` executable-characteristics
change is guarded by `0x400000D0 -> 0x400000F0`. Uninstall restores the stock
hook, zero body, section flags, headers, and file layout. Any guard mismatch
fails atomically without partial output mutation.

Expanded-256 remains ON HOLD; no expanded selector enablement is implied.
