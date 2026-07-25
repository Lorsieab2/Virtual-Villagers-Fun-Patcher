# VV1 Origins-exclusive feature research

## Scope and identity

The source was the user-supplied `Virtual Villagers: Origins` Android APK,
version 1.5.0.15. A hashed copy was retained under the ignored research tree;
the APK and its extracted bulk assets are not shipped or committed.

APK SHA-256:
`7BF9D265FAC5C20D1B5E930505FA776AD1C7978DFEF096009085F91883069630`

The desktop target remains the exact supported A New Home executable recorded
in `data/builds.json`. Every desktop hook has an original-byte guard, uses
existing executable or read-only padding, preserves file size, and receives a
new PE checksum through the normal patch pipeline.

## APK behavior recovered

The APK's Tech screen exposes these purchases:

| Purchase | Cost | Recovered effect |
|---|---:|---|
| Time Warp | 50,000 | Advances 3, 6, or 12 hours according to game speed. |
| Island Event | 30,000 | Opens the non-catastrophic Island Event route. |
| Barrel of Babies | 75,000 | Forces the positive-event category with magnitude 10. |
| Bump Max Population | 250,000 | Adds 10 to the mobile cap, repeatable to a 30-point bonus. |
| Grant Youth | 50,000 | Subtracts 700 internal age units, equal to 35 displayed years, with a displayed-age floor of 5. |
| Grant Full Mastery | 100,000 | Writes 90 to each of the five skills. |
| Grant Running | 40,000 | Sets the mobile running upgrade flag. |
| Tech Point Doubler | 500,000 | Doubles positive tech increments. |
| Food Point Doubler | 500,000 | Doubles positive food increments. |

The two doubler hooks run only when their increment is positive. Negative
values retain their original magnitude.

`theNCEventDialog::ProcessNCEventRequest` forces Barrel of Babies into event
cases 12 through 14. `ComposeResult` proves the three possible results:

- case 12 spawns three villagers at internal ages 70 through 89, which are
  young children under VV1's 20-units-per-displayed-year age scale;
- case 13 adds `100 * 10 = 1,000` food;
- case 14 adds `300 * 10 = 3,000` tech points.

## Desktop port

The port adds a stock-styled **Origins Upgrades** control to the desktop Tech
screen's unused button ID 2. A guarded handler displays the nine purchases in
a compact Yes/No/Cancel sequence.

The desktop game's central tech and food award routines implement the
doublers. Consequently, all positive awards routed through those routines are
doubled, including the matching Barrel result, while deductions remain
unchanged. Ownership is stored in `Origins Exclusive Features.ini` beside the
modified executable, so it persists independently of save-slot selection.

Grant Running uses the desktop villager record's otherwise-unused saved dword
at offset `+0x3D4` as its sentinel and reapplies the stock running speed during
normal speed initialization. The game's three like and three dislike slots
remain untouched.

The desktop population modes already make all 256 physical VV1 records
available. Repeating the APK's extra +10 cap purchase would therefore have no
safe effect. The menu retains **Bump Max Population** for feature visibility,
reports the existing 256 maximum, and does not charge tech points.

The APK contains exclusive PVR atlas entries for these upgrades. They are not
inserted into the desktop renderer: the port deliberately uses the game's
stock desktop button and dialog assets, avoiding a new texture decoder or
external runtime dependency.

## Validation boundary

Automated integration tests verify the exact source executable guards, feature
name, two 500,000-point prices, short-output compatibility, PE checksum path,
and combination with every other VV1 patch. The generated payload is
reproducible from `scripts/build_vv1_origins_feature.py`.

This is a native executable modification. Static validation cannot substitute
for player testing of every purchase in a full desktop game folder. Runtime
behavior should therefore be treated as pending until the generated modded
folder has been opened and each menu action has been exercised in-game.
