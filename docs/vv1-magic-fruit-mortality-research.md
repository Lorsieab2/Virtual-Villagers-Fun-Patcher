# VV1 Magic Fruit of Life Alters Mortality

## Supported executable

| Size | SHA-256 |
|---:|---|
| 581,632 bytes | `1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D` |

## Stock mechanics

The completed Magic Plant flag changes action 27 from **Studying fruitless plant** to `sub_443150`, **Enjoying magic fruit**. The stock action queues two fruit-effect and animation sequences but writes no age, health, sickness, Medicine, or mortality state.

VV1 checks old-age mortality only on processed birthdays in `sub_42E900`. Its internal-age threshold is:

`940 + 160 × Medicine level`

That produces displayed thresholds 55, 63, and 71 for Medicine levels 1, 2, and 3. Above the threshold, the annual conditional death chance rises by ten percentage points per year until it reaches 100%.

The same `sub_42E900` processed-age loop runs during live simulation and offline catch-up.

## Persistent once-only storage

Every villager record is 984 bytes. The generated name occupies a fixed buffer beginning at `+880`; likes/dislikes begin at `+936`. The patch uses the otherwise unreferenced final byte at `+935` for the Magic Fruit extension.

Only values 3 through 9 are valid. Zero and every value outside that range are treated as “not yet rewarded,” avoiding accidental activation from unrelated pre-patch data. The villager-creation routine explicitly clears `+935`, including when a dead record slot is reused.

The byte is part of the saved villager record, so it persists across closing, reopening, and offline catch-up. It is outside the null-terminated visible name and does not change the displayed name.

## Completion award

The second stock opcode-19 effect-cleanup entry in `sub_443150` is marked with private value 126. The opcode-19 executor preserves ordinary cleanup for every action, then checks that marker.

For marker 126:

1. the visual effect is cleared normally;
2. an existing valid 3-to-9 value receives no second award;
3. otherwise stock `RNG(7)+3` selects 3 through 9 with equal odds;
4. the selected value is written to the villager's saved `+935` byte.

Because the award is attached to the second and final fruit-animation cleanup, an interrupted first visit that never reaches that step receives nothing.

## Mortality shift

Immediately after the stock Medicine threshold is calculated, the mortality detour validates `+935`, multiplies it by 20 internal age units per displayed year, and adds it to the threshold. The shifted threshold remains in the same register used by both the eligibility comparison and subsequent probability calculation.

Consequently, the entire curve moves later without changing the villager's displayed or processed age:

| Medicine | Stock threshold | Patched possible threshold |
|---:|---:|---:|
| 1 | 55 | 58–64 |
| 2 | 63 | 66–72 |
| 3 | 71 | 74–80 |

The 10%, 20%, through 100% annual sequence is unchanged; only its starting age moves. Because this is the ordinary processed-birthday code, the extension applies identically during time catch-up.

## Repeat-attempt message

At assignment time, a valid saved extension bypasses the fruit sequence and returns a private result code to the ordinary villager-drop handler. The handler recognizes only that private result and writes the external full sentence into the same temporary message widget used for notices such as **This villager improved at farming**:

`This villager has already extended their lifespan.`

The patch then sets the widget's ordinary one-tick visibility timer and returns through the stock drop-handler epilogue. Every ordinary result continues through the original handler. The villager's current-action text and action queue are not changed, and no new random roll occurs.

## Boundaries

- The award never stacks.
- The patch does not lower either age counter or make the villager appear younger.
- Health, sickness, Medicine Technology, fertility, skills, and food are unchanged.
- The Golden Child remains governed by its separate stock age-reset exemption.
- The original executable is never modified; the patcher writes a separately named copy with a recalculated PE checksum.
