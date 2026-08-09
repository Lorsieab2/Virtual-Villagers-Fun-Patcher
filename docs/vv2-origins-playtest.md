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
The player should verify launch, Time Warp, both Upgrades menus, normal births,
save/reload, and ordinary play before any publication decision. Do not copy
saves into this handoff and do not treat a successful launch as proof that the
underlying native routes are certified.
