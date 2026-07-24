# VV1 Magic Fruit mortality and healing patch

## Safe design

The restored **Magic Fruit of Life Alters Mortality** patch does not need
per-villager persistence. It reads the game's existing saved Magic Fruit puzzle
completion byte at global-state offset `+0xA098`. When that byte is nonzero,
the stock mortality routine adds 120 internal age units to its already
calculated threshold. VV1 uses 20 internal units per displayed year, so this is
a fixed six-year shift. Medicine technology is evaluated by the stock formula
before the shift. The same mortality routine is used in ordinary play and
offline time catch-up.

The final cleanup entry in **Enjoying magic fruit** is marked with private
value `126`. The shared cleanup executor preserves its stock call, then sets
the acting villager's confirmed health field at `+836` to `100` and sickness
field at `+852` to `0`. Other cleanup entries follow the displaced stock path
unchanged. Because the marker is on the final queue entry, an interrupted fruit
action does not cure the villager.

Eating the fruit is reusable. It does not add another mortality shift because
longevity depends only on the puzzle's single saved completion flag.

## Retired unsafe experiment

The v1.24.0 experiment tried to save a once-per-villager marker at record byte
`+935`. That premise was wrong: the Detail-screen routine at `0x43BA60` treats
offsets `+920`, `+924`, `+928`, and `+932` as four likes/dislikes pointers, so
`+935` is part of the fourth pointer. The player-observed Detail-screen access
violation at executable offset `0x3BA86` was consistent with that corruption.

The current patch never reads or writes those pointer fields—or any other
villager field for persistence. Its only villager writes are the confirmed
health and sickness values at fruit-action completion.
