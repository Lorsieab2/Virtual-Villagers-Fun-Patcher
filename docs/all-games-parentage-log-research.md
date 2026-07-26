# All-five-game parentage log: implementation boundary

This note records what is safe to share between the five games and what still
requires a build-specific native hook.  It is intentionally conservative: a
file-format renderer is not described as an executable patch.

## Shared behavior

- The output is one ordinary HTML file beside the modified executable:
  `<game title> Parentage Log.html`.
- The format accepts any number of cards, so 256 or more records do not need a
  larger in-game table.
- A card is emitted only after the newborn materialization path has created the
  child record.  Conception/pregnancy state alone is not a birth card.
- The visible fields are the child name, Likes, Dislikes, numeric skills, and
  head/body row numbers, followed by the mother and father name and
  head/body row numbers.
- The row guide is printed at the beginning of every file.  Row 0 is the first
  row in the corresponding `Images` sheet.

## Game-specific evidence boundary

| Game | Confirmed birth/materialization path | Confirmed pending-state evidence | Remaining hook work |
|---|---|---|---|
| VV1 | `sub_42E900` creates the first child through `sub_43C350` and clones through `sub_43C840` | mother `+856/+860/+908/+912/+916`; child head/body are `+864/+868` | cache the father snapshot at conception and fingerprint the post-constructor callback before writing the EXE patch |
| VV2 | `sub_43B690` reaches `sub_44F5C0`, which calls `sub_44C600`; clones use `sub_44CEC0` | record stride `0xE48C`; parent-name strings `+1405/+1430`; cached appearance `+1500/+1504`; child Likes/Dislikes and skills are directly addressed | bind the callback to the exact supported executable and preserve the stock return path |
| VV3 | `sub_45FFE0` reaches `sub_45FF90`/`sub_456120`; clones use `sub_45F1D0` | marker/count are `+3724/+3728` in the villager pointer; partner/name/appearance payload begins at `+3652` | recover the exact display-name and parent-appearance offsets before native serialization |
| VV4 | `sub_467D50`/`sub_466270` reaches `sub_45EF10`; clones use `sub_466310`/`sub_45D9B0` | marker/count `+7244/+7248`; parent/name/appearance payload begins at `+7180` (`+0x1C0C`) | verify the four copied lineage fields and exact display-name storage in the supported build |
| VV5 | `sub_471E60`/`sub_46FAD0` reaches `sub_4681F0`; clones use `sub_46FD70`/`sub_4687F0` | marker/count `+7244/+7248`; parent/name lineage `+7104/+7129`; appearance payload `+7156..+7168` | verify string encoding and the two parent head/body values before native serialization |

The reports and exact stock-executable fingerprints are the source of these
addresses.  The parentage patch must not enlarge a villager record or alter a
save stride.  Logging failure must be fail-open: the original birth must still
complete.

Until those per-build callbacks and name/appearance reads are guarded in the
manifest, the patcher must not offer an “active” parentage checkbox.  The
shared renderer and the player-facing artifact notice are complete, but this
research boundary prevents a guessed pointer or guessed string layout from
being shipped as a birth log.
