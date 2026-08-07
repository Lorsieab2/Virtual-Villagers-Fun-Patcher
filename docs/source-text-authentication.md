# Authenticated source-text hashing

Tracked text artifacts authenticated by the patcher use
`vvfp.source-text.v1`. The algorithm decodes UTF-8 with an optional BOM,
normalizes CRLF and lone CR to LF, removes the BOM by decoding, re-encodes as
UTF-8 without a BOM, and computes uppercase SHA-256. Invalid UTF-8 fails closed.

The authoritative inventory is `data/source-text-authentication.json`. It
contains every tracked JSON artifact whose complete source text is pinned by
the production loader. Binary DLL, executable, page, helper, image, and patch-
byte hashes remain raw-byte SHA-256 and are not affected.

This migration replaces checkout-dependent raw hashes; it does not accept a
semantic change. JSON identity, enabled/hidden/catalog flags, dependency,
fingerprint, ABI, range, and transaction validation continue independently.
No candidate was enabled or published.

The migration specifically closes observed Windows `core.autocrlf=true` drift
for VV3 Full Heal, VV2 Full Mastery, VV4 Full Heal, and VV5 legacy Running. It
also moves the other complete-text pins in the same loader (VV3 Running, Full
Mastery, individual Running, and individual Full Mastery) to the same policy so
archive and checkout behavior cannot diverge later.

Regression tests compare each digest against both the Windows worktree bytes
and the corresponding clean Git blob, then exercise LF, CRLF, lone-CR, BOM,
semantic mutation, and invalid-UTF-8 cases.
