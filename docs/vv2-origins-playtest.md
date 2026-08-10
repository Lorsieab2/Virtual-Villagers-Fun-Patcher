# VV2 Origins stress-test output

The patcher has an explicit `--playtest-disabled-feature` path for the VV2
Origins record. It does not change the tracked catalog state: the feature
manifest remains `enabled=false`, `catalog_hidden=true`, and
`catalog_enabled=false`.

The option is intentionally narrow. It accepts only
`vv2_enable_origins_exclusive_features`, requires an explicit output root, and
refuses save copying or replacement. The resulting folder is named
`Virtual Villagers - The Lost Children - Modded Playtest` and the executable is
named `Virtual Villagers - The Lost Children - Modded Playtest.exe`.

The output is a player stress-test handoff, not native/runtime certification.
The player should verify launch, Time Warp, Island Event, Barrel of Babies,
both Upgrades menus, normal births, save/reload, and ordinary play before any
publication decision. Do not copy saves into this handoff and do not treat a
successful launch as proof that the underlying native routes are certified.

Every buy-only village upgrade first shows the permanent-change warning. The
Windows prompt's affirmative (OK) choice is the Purchase action; Cancel leaves
the menu and charges nothing. Barrel of Babies performs its native three-child
event only when at least two villager slots remain after the native population
preflight. With fewer than two slots available it shows:

`The village population is already close to its max. No tech points have been deducted.`

and does not deduct tech points. The Barrel event remains the game's native
`The Barrel O' Babies` route; no child records are fabricated by the patch.

The current playtest payload gives command 6 (All villagers like running) its
own bounded loop over 256 active records and all 62 Like/62 Dislike slots. It
does not call the older `ShowOriginsVillageWideResult@20` callback, which had
the wrong result-buffer contract and caused a crash on this route. Commands 7
and 8 are refused without a charge; they are not part of this stress target.
