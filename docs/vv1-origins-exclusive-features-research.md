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
| Barrel of Babies | 75,000 | Forces event 12 with magnitude 10, spawning exactly three young children. |
| Bump Max Population | 250,000 | Adds 10 to the mobile cap, repeatable to a 30-point bonus. |
| Grant Youth | 50,000 | Subtracts 700 internal age units, equal to 35 displayed years, with a displayed-age floor of 5. |
| Grant Full Mastery | 100,000 | Writes 90 to each of the five skills. |
| Grant Running | 40,000 | Sets the mobile running upgrade flag. |
| Tech Point Doubler | 500,000 | Doubles positive tech increments. |
| Food Point Doubler | 500,000 | Doubles positive food increments. |

The two doubler hooks run only when their increment is positive. Negative
values retain their original magnitude.

`theNCEventDialog::ProcessNCEventRequest` forces Barrel of Babies to event 12.
The ARM instructions set the random bound to 1 and the event base to 12, so
`GetRandom(1) + 12` can only produce 12. `ComposeResult` then spawns three
villagers at internal ages 70 through 89, which are young children under VV1's
20-units-per-displayed-year age scale.

Cases 13 and 14 are neighboring positive Island Event results for food and
tech points, but the Barrel purchase's bound of 1 makes them unreachable.

## Desktop port

The port adds a stock-styled **Upgrades** control to the desktop Tech screen's
unused button ID 2. It opens one **Origins Upgrades** window containing Time
Warp, Island Event, Barrel of Babies, Tech Point Doubler, and Food Point
Doubler at the same time. Each row contains the recovered mobile icon, name,
cost, and its own Buy button, with one Cancel button for the window. An owned
doubler's button changes to Remove and removing it does not charge tech points.
The popup overlays the APK's exact green `tech_checkmark.png` art on completed
villager upgrades and owned doublers. A completed villager-upgrade button reads
**Done**; an unavailable Running upgrade with three occupied non-Running Like
slots reads **Unavailable** without showing a completion checkmark.
The stock message supplies a pointer to the button object. The handler reads
the numeric control ID at object offset `+4` and compares it with 2. The constructor
reuses the game's existing
`main_wide_button2.png` string at virtual address `0x459340` rather than
supplying a duplicate filename from the injected data block, keeping image
lookup on the same stock path as the game's other wide buttons.

The icon popup is loaded through VV1's actual `LoadLibraryA` import at
`0x457010`. The earlier icon implementation incorrectly called
`GetModuleHandleA` at `0x4570D0` as though it were the loader; that shared
invocation path was corrected while addressing the player's report that both
Upgrades buttons crashed in v1.34.4. Player retesting remains the runtime gate.

A separate stock-styled **Upgrades** control is added to the Villager Detail
screen. It opens one **Villager Upgrades** window containing Grant Youth, Grant
Full Mastery, Grant Running, and Set Age to 18 at the same time. It applies a
purchase only to the villager currently shown on that Detail screen.

Grant Full Mastery preserves an existing checked job preference. When the
villager has no checked preference, the upgrade selects Farming, the first of
the five newly tied mastered skills. This prevents VV1's stock summary-title
chooser from displaying the otherwise incomplete title **Master** after all
five skills are made exactly equal.

Corrected builds also perform a deliberately narrow compatibility repair while
VV1 initializes its villager records: a villager whose five skills are all
exactly 90 and whose preference is still zero is assigned Farming. No other
skill combination or existing preference is changed. The injected check
preserves the stock `EAX` and `ECX` values before returning to the initializer;
v1.34.3 failed to preserve `ECX` and was withdrawn after a player-confirmed
startup crash.

The desktop game's central tech and food award routines implement the
doublers. Consequently, all positive awards routed through those routines are
doubled, while deductions remain unchanged. Ownership is stored in
`Origins Exclusive Features.ini` beside the
modified executable, so it persists independently of save-slot selection.

Grant Running only adds trait 38 to an available Like slot on the displayed
villager. If Running is already a Like or all three Like slots are occupied,
the purchase refuses without charging or overwriting anything. It neither
reads nor writes dislikes and does not touch movement speed, movement
initialization, or a custom sentinel. Any movement caused by the resulting
Like is entirely VV1's unmodified base-game behavior.

Set Age to 18 costs 50,000 tech points, matching Grant Youth. It writes 360
internal age units to the displayed and current-age fields. If the selected
villager has an active pregnancy or nursing-relative timestamp, the associated
field is adjusted with the same age change instead of leaving it inconsistent.

The desktop port deliberately omits **Bump Max Population** from its menu. The
patcher's population modes already target VV1's physical 256-record capacity,
so the mobile upgrade is neither displayed nor offered for purchase.

Before charging for Barrel of Babies, the desktop port computes the current
population and applies the stock housing thresholds of 15, 25, and 50 before
the patched 256 maximum. The purchase proceeds only when three spaces remain.
Otherwise it charges nothing and reports **The village population is already
at maximum capacity.**

The APK contains exclusive PVR atlas entries for these upgrades. The eight
required entries were decoded losslessly into local PNG/ICO assets and embedded
as native resources in the bundled 32-bit `VVFP Origins Icons.dll`. The patcher
copies that hash-verified companion into the user's new modded game folder; it
does not depend on the original APK or any files outside the patcher.

## Validation boundary

Automated integration tests verify the exact source executable guards, feature
name, two 500,000-point prices, short-output compatibility, PE checksum path,
the direct control-ID handler, the mastery tie repair, the companion DLL hash
and copied location, and combination with every other VV1 patch. The generated
payload is reproducible from
`scripts/build_vv1_origins_feature.py`.

This is a native executable modification. Static validation cannot substitute
for player testing of every purchase in a full desktop game folder. Runtime
behavior should therefore be treated as pending until the generated modded
folder has been opened and each menu action has been exercised in-game.
