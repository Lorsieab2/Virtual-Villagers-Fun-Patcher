# Fullscreen Collection playtest runtime evidence

This is a bounded player-observation record, not a broad feature certification.
The observations apply only to the named Collection playtest and to fullscreen
menu interaction:

| Game/playtest | Observation | Scope status |
| --- | --- | --- |
| VV3 Fullscreen Collection Playtest 1 | Fullscreen menus pass. | Menu observation passed; all other runtime behavior pending. |
| VV4 Fullscreen Collection Playtest 1 | Fullscreen menus pass. | Menu observation passed; all other runtime behavior pending. |
| VV5 Fullscreen Collection Playtest 1 | Controls render, but both Tech and Detail clicks produce no menu. | Menu interaction STOP; all other runtime behavior pending. |

No row above certifies Full Mastery, Full Heal/Cure, Running, save/reload,
trophies, or any other gameplay path. Expanded-256 remains fail-closed. The
machine-readable source record is
`data/candidates/fullscreen_playtest_runtime_evidence.json`.

## Individual-villager Buy contract audit

Where a candidate exposes an individual-villager Buy action, the authoritative
contract is: complete dry-run; explicit confirmation; fresh revalidation;
changed-only native mutation; one native charge after successful postverification.
Cancel performs no writes and no charge. A no-change or failure result is
explanatory and includes the exact sentence `No tech points have been
deducted.` This audit does not infer an individual route where the current
candidate is aggregate-only.

- VV3 individual Grant Running (`command 2`, 40,000) has this contract and
  remains runtime/player pending.
- VV5 selected-villager Full Mastery has this contract in its
  `individual_transaction` record and remains runtime/player pending.
- VV1 and VV2 current Full Mastery records are aggregate command-7 routes;
  no separate individual-villager Buy route is certified in their current
  manifests.
- VV4 current Full Heal / Cure All is an aggregate command-5 route; no
  separate individual-villager Buy route is certified in its current manifest.

The absence statements above are coverage boundaries, not claims that a
future individual route is impossible. Any future route must add the same
dry-run/confirm/recheck/mutate/charge and no-charge assertions before it is
enabled or packaged.
