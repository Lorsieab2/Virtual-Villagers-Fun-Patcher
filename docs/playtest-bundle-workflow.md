# Guarded playtest bundles

`scripts/build_playtest_bundle.py` creates a player-facing bundle only after a
feature is already certified for public playtesting. It is not an enablement
tool and cannot promote an evidence-only candidate.

The tool refuses every feature unless its resolved catalog record has all of
the following exact states:

- `enabled: true`, `catalog_enabled: true`, and `catalog_hidden: false`;
- `native_output: true`; and
- explicit runtime and player verification (`runtime_verified` and
  `player_verified`, or an equivalent non-pending certified status).

Consequently, the Reset Collectibles and Complete All Collectibles records
remain unpackageable while they are disabled, catalog-hidden, native-output
false, or runtime/player pending.

## Dry run

Dry run performs source-folder and feature preflight only. It does not create
an output directory, invoke the patcher, launch a game, or inspect saves:

```text
python -B scripts/build_playtest_bundle.py dry-run `
  --game vv2 `
  --source-folder "Vanilla Games\Virtual Villagers - The Lost Children" `
  --output-root outputs\playtest-bundles\vv2 `
  --patch-mode collection_progression `
  --fun-patch <certified-feature-id>
```

## Build and package

After a feature reaches the required state, build one game at a time into a
new ignored output root. `--package` creates a ZIP only after the patched game
tree passes the same no-follow and save exclusion checks:

```text
python -B scripts/build_playtest_bundle.py build `
  --game vv2 `
  --source-folder "Vanilla Games\Virtual Villagers - The Lost Children" `
  --output-root outputs\playtest-bundles\vv2 `
  --patch-mode collection_progression `
  --fun-patch <certified-feature-id> `
  --package
```

Use the analogous `vv3`, `vv4`, and `vv5` source folders. The stock executable
must match the repository fingerprint for that game. Source and output trees
must be separate, contain no reparse points, and contain no `.ldw`, `.sav`,
`.save`, or save-directory paths.

To package an already-built, certified folder without rebuilding it:

```text
python -B scripts/build_playtest_bundle.py package `
  --game vv2 `
  --game-folder "outputs\playtest-bundles\vv2\Virtual Villagers - The Lost Children - Modded" `
  --output-root outputs\playtest-bundles\vv2 `
  --patch-mode collection_progression `
  --fun-patch <certified-feature-id>
```

The ZIP contains the complete modded game tree plus an internal
`PLAYTEST-BUNDLE-MANIFEST.json`. A sibling manifest records the ZIP SHA-256,
entry count, output inventory, stock fingerprint, selected IDs, and the
explicit `launch: false`, `save_access: false`, and runtime-status fields.
ZIP CRCs and the exact entry list are verified before success. Saves are never
included; the player supplies a separately backed-up save only when a later
runtime test is authorized.

The current Reset Collectibles and Complete All Collectibles contracts are
evidence-only and therefore intentionally fail this tool's preflight.
