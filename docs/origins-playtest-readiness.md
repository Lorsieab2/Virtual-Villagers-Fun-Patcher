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

VV1, VV3, and VV4 doubler new purchases and repurchases remain unavailable
until their exact-build provenance gates are cleared. VV5 stock-layout Tech and
Food Doublers support purchase, zero-cost/no-refund Remove, and full-price
repurchase. In VV5 expanded-256 modes, both writer hooks are restored to native
bytes and new doubler purchases remain unavailable; owned Remove remains
available. Expanded composition is ON HOLD: the 75-row relocation ledger covers
32 rows and leaves 43 references (36 cross-section rel32 and 7 external
absolute `.shr` pointers) outside the certified set, per disassembly commit
`8dfccbd1b31e55f5168bb1c5ff23890bb98d9fdb`. VV5 native Time Warp, Island Event,
and Barrel rows remain unavailable because their Heathen-safe target paths are
not yet proven.

The matrix is intentionally catalog-driven rather than a hard-coded feature
list, so newly enabled game-scoped patches cannot silently escape the
composition checks. It does not modify manifests, executable payloads, saves,
prices, ownership behavior, or companion DLLs.
