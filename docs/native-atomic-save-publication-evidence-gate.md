# VV3-VV5 native atomic-save publication evidence gate

This additive contract is evidence-only and permanently disabled in its checked-in state. It does not alter the catalog, emit native code, build a package, launch a game, or read or write saves.

Each game is pinned to its exact stock executable. Full-folder fingerprints, native header/body writers, slot-result and late-load-failure ABIs, and exact header/body/record/tail/padding shapes are currently unknown and therefore `null`. Null is STOP, never a wildcard.

Publication requires authenticated proof of a sibling-directory temporary write; checked header, body, flush and close results; reopen and exact validation; an atomic replacement that preserves the prior final file on every failure; directory durability where the platform supports it; explicit slot 0/current/backup outcomes; fatal non-return after a late load failure has mutated state; record-bound, tail and padding correctness; and complete fault-injection, runtime and player receipts.

Stock backup rotation is not atomicity evidence. Serializer arithmetic without the native writer, filesystem protocol, failure boundaries and observed receipts is also nonqualifying. Direct `wb` truncation, ignored rotation results and ignored close results must be established from authenticated native evidence rather than assumed from this contract.

Run `python -B scripts/validate_native_atomic_save_publication_evidence.py`. The checked-in result is intentionally non-zero and reports STOP.

Integration onto C342 is additive: carry the six new files as a single unit. They have no catalog registration or dependency on generated native outputs. Resolve only path conflicts if C342 independently introduces the same contract ID; do not merge evidence rows by assumption or change any false publication flag.
