# VV3 full-256 serializer static candidate

This metadata-only model is strictly disabled. It does not emit `.vv3sv`, patch either hook, modify the catalog, build a package, launch the game, or access saves.

Both exact post-Origins+Running parents are bound: Immediate `657D321B...6531A848` and Progression `3A35745C...9015B211`, each size `0xCC000`. The collision-free section plan is `.vv3sv`, header `0x2F0`, raw `0xCC000–0xCD000`, RVA `0x3B9000`, VA `0x7B9000`, RX. Header, section, wrapper, hook-emission, final bytes, checksums, and result hashes remain null.

The planned sole-callsite guards are raw `0x27D57` (stock serializer `0x45EF80`, `E824720300` to `E8A4123900`, serializer wrapper at `0x7B9000`) and raw `0x28A4C` (stock deserializer `0x45C860`, `E80F3E0300` to `E8AF073900`, deserializer wrapper at `0x7B9200`). They are reference expectations only and are not written.

D353 establishes that compact state is obtained from `0x428B60()+0x786C`, not the formal wrapper argument. The model binds the five native helper bounds/hashes and requires logical records 0–255 only, padding 256–259 excluded, a terminator only below count 256, reader success at exactly 256 without a tail read, and strict stack/nonvolatile-register preservation.

Native emission is blocked because singleton allocation can return null. Load orchestration already tests deserializer `AL`; save orchestration ignores serializer `AL`. No exact guarded caller branch that checks `AL` and dominates the writer is available. Returning `AL=0` would therefore not prevent a save write. The builder refuses to invent that branch and keeps `native_output=false` and all runtime/player/publication gates false.

D354 adds a disabled atomic-writer plan at VA `0x7B9400` / raw `0xCC400` around stock writer `0x403530`. D356 authenticates the four callsite preimages against both exact post-Running parents: actions/null-manager raw `0x27C7D`, VA `0x427C7D`, `E8AEB8FDFF` to expected `E87E173900`; config-village/null-manager raw `0x27C92`, VA `0x427C92`, `E899B8FDFF` to `E869173900`; actions/non-null-manager raw `0x27D6C`, VA `0x427D6C`, `E8BFB7FDFF` to `E88F163900`; and config-village/non-null-manager raw `0x27D81`, VA `0x427D81`, `E8AAB7FDFF` to `E87A163900`. These remain evidence-only expectations and are not emitted. The transaction requires a non-numeric sibling temporary path, create-new/write-through, exact write, flush/close/reopen verification, `ReplaceFileA` flags 0 for an existing final, and `MoveFileExA` write-through without replace-existing for an absent final. Dynamic resolver bytes, imports, wrapper bytes, failure/caller propagation, page-state proof, and uninstall proof remain blockers. Failure is modeled as fatal/non-returning until every caller is proven to check a result.

Run `python scripts/build_vv3_full256_serializer_candidate.py --check` to verify deterministic checked-in metadata.
