# VV2 Easier Healing Mastery - executable evidence

Supported stock executable SHA-256: `46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677`.

## Confirmed control flow

- Villager records have stride `0xE48C`. Skill values are stored at `+0x7E4` Farming, `+0x7E8` Building, `+0x7EC` Research, `+0x7F0` Healing, and `+0x7F4` Parenting. Skill preference is at `+0x7F8`.
- `0x00449C60` selects among the five jobs. Healing is job 3 and is influenced by the Healing value and preference through the stock selection logic.
- `0x0045FBF0` dispatches the chosen job. Healing enters `0x0046045A`, which scans up to 256 villager records for a sick target.
- If no sick target is found, stock code at `0x004604AD` returns false. This is the suppression point changed by the patch.
- Villager work state 9 at `+0x7E0` is the existing persistent plant-study state. `0x00460590` dispatches state 9 to `0x00460686`, checks Healing at `+0x7F0`, selects among available plants, and starts the stock plant-study routines. This state participates in the game's ordinary ongoing-work/catch-up processing.

## Patch

The guarded detour at file offset `0x604AD` replaces the nine-byte no-target return with a jump to unused mapped `.text` padding at file offset `0x73CA0`. The cave sets the selected villager's work state to 9, calls the stock persistent-work dispatcher with its normal 100-unit argument, and returns its success result through the original stack convention.

No plant action, skill-award formula, illness predicate, food value, availability flag, villager count, or record layout is replaced. The executable size is unchanged and the PE checksum is recomputed.
