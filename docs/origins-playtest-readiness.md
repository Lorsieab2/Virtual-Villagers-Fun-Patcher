# Origins static playtest-readiness gate

This document records the patcher's five-game composition matrix for the
current Origins catalog. For each supported game, the test selects every
enabled game-scoped optional patch, resolves prerequisites in dependency-first
order, and renders all four population modes against the exact stock
executable. It verifies every byte guard, feature owner, PE checksum, and
shared Origins companion hash while proving that the stock executable remains
byte-identical.

This is static composition/readiness only. It does not prove player-visible
runtime behavior, and runtime/player confirmation remains pending. The test
never launches a game and does not authorize packaging by itself.

The VV1/VV3/VV4/VV5 doubler new purchases and repurchases remain unavailable
until their exact-build provenance gates are cleared. VV5 native Time Warp,
Island Event, and Barrel rows remain unavailable because their Heathen-safe
target paths are not yet proven.

The matrix is intentionally catalog-driven rather than a hard-coded feature
list, so newly enabled game-scoped patches cannot silently escape the
composition checks. It does not modify manifests, executable payloads, saves,
prices, ownership behavior, or companion DLLs.
