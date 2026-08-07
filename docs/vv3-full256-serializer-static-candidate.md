# VV3 full-256 serializer static candidate

This metadata-only model is strictly disabled. It does not emit `.vv3sv`, patch either hook, modify the catalog, build a package, launch the game, or access saves.

Both exact post-Origins+Running parents are bound: Immediate `657D321B...6531A848` and Progression `3A35745C...9015B211`, each size `0xCC000`. The collision-free section plan is `.vv3sv`, header `0x2F0`, raw `0xCC000–0xCD000`, RVA `0x3B9000`, VA `0x7B9000`, RX. Header, section, wrapper, hook-emission, final bytes, checksums, and result hashes remain null.

The planned sole-callsite guards are raw `0x27D57` (`E824720300` to `E8A4123900`, reader at `0x7B9000`) and raw `0x28A4C` (`E80F3E0300` to `E8AF073900`, serializer at `0x7B9200`). They are reference expectations only and are not written.

D353 establishes that compact state is obtained from `0x428B60()+0x786C`, not the formal wrapper argument. The model binds the five native helper bounds/hashes and requires logical records 0–255 only, padding 256–259 excluded, a terminator only below count 256, reader success at exactly 256 without a tail read, and strict stack/nonvolatile-register preservation.

Native emission is blocked because singleton allocation can return null. Load orchestration already tests deserializer `AL`; save orchestration ignores serializer `AL`. No exact guarded caller branch that checks `AL` and dominates the writer is available. Returning `AL=0` would therefore not prevent a save write. The builder refuses to invent that branch and keeps `native_output=false` and all runtime/player/publication gates false.

Run `python scripts/build_vv3_full256_serializer_candidate.py --check` to verify deterministic checked-in metadata.
