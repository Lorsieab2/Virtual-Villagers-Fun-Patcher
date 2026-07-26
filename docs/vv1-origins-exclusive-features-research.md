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
| Barrel of Babies | 75,000 | Opens the native event-12 Barrel of Babies result with magnitude 10, spawning exactly three young children through the stock event path. |
| Bump Max Population | 250,000 | Adds 10 to the mobile cap, repeatable to a 30-point bonus. |
| Grant Youth | 50,000 | Subtracts 700 internal age units, equal to 35 displayed years, with a displayed-age floor of 5. |
| Grant Full Mastery | 100,000 | Writes 90 to each of the five skills. |
| Grant Running | 40,000 | Sets the mobile running upgrade flag. |
| Tech Point Doubler | 500,000 | Doubles positive tech increments. |
| Food Point Doubler | 500,000 | Doubles positive food increments. |

The two doubler hooks run only when their increment is positive. Negative
values retain their original magnitude. The two Island Event result calls that
award tech or food are explicitly excluded, so an Island Event never receives
the doubler bonus.

The desktop implementation now constructs the stock event dialog and marks the
request with a private sentinel. The guarded event selector consumes that
sentinel by calling the game's native event-result routine with event 12 and
magnitude 10. The game's own result handler then displays the Barrel of Babies
event and creates its three young children through the normal event code.

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
The stock message supplies the numeric control ID directly as its second
argument. The Tech handler compares that value with 2; the Villager Detail
handler compares it with 6. Earlier builds incorrectly treated the numeric
values as pointers and dereferenced `ID + 4`. Windows crash records placed the
access violations exactly at those two injected dereferences (module offsets
`0x5690F` and `0x56D9F`). The corrected handlers compare the numeric arguments
without dereferencing them. The constructor reuses the game's existing
`main_wide_button2.png` string at virtual address `0x459340` rather than
supplying a duplicate filename from the injected data block, keeping image
lookup on the same stock path as the game's other wide buttons.

The icon popup is loaded through VV1's actual `LoadLibraryA` import at
`0x457010`. An earlier icon implementation incorrectly called
`GetModuleHandleA` at `0x4570D0` as though it were the loader. That loader issue
and the separate control-ID dereferences are corrected. Player retesting
remains the runtime gate.

A separate stock-styled **Upgrades** control is added to the Villager Detail
screen. It opens one **Villager Upgrades** window containing Grant Youth, Grant
Full Mastery, Grant Running, and Set Age to 18 at the same time. It applies a
purchase only to the villager currently shown on that Detail screen.

Grant Full Mastery preserves an existing checked job preference. When the
villager has no checked preference, the upgrade selects Farming, the first of
the five newly tied mastered skills. This prevents VV1's stock summary-title
chooser from displaying the otherwise incomplete title **Master** after all
five skills are made exactly equal.

Grant Full Mastery itself preserves an existing checked job preference and
chooses Farming when none is checked. The patch does not modify existing save
records during startup; replace saves made by older experimental builds if
they contain persisted movement-speed changes.

The desktop game's central tech and food award routines implement the
doublers. Positive awards routed through those routines are doubled, while
deductions remain unchanged. The Island Event result composer has one central
tech award call (return address `0x428194`) and one central food award call
(return address `0x4281DA`); the detours recognize those exact return addresses
and leave those awards at their stock amounts. Ownership is stored in two
otherwise-unused fields of the active saved game state (`+0xAD48` and
`+0xAD4C`), so one save can own a doubler without changing another save in the
same game folder. No global INI or executable-side ownership file is created.

The experimental desktop sparkle injection was removed after crash records
implicated its renderer path. The stock world sparkle call remains completely
unchanged. Doubler ownership and resource multiplication do not depend on that
cosmetic effect.

Static caller and field-reference verification found seven callers of the
stock positive-tech routine at `0x41D120` and six callers of the stock
positive-food routine at `0x41D140`. Those routines are the positive resource
writers: research, action rewards, event rewards, and food-source awards all
arrive through them, regardless of villager skill or mastery level. The other
positive-looking food writes at `0x41C472` and `0x41C485` initialize a new
village's starting food and are not gameplay gains; costs and negative event
adjustments remain direct deductions. The doubler detours preserve that split:
every positive award is doubled, while starting values, spending, and losses are
unchanged. Island Event awards are also excluded from the doubler.

Grant Running adds trait 38 to an available Like slot on the displayed
villager and removes trait 38 from any of that villager's Dislike slots. If
Running is already a Like, the upgrade can still remove a conflicting Running
Dislike. If all three Like slots are occupied and none is Running, the purchase
refuses without charging or overwriting anything. It does not write movement
speed, movement initialization, or a custom sentinel. The Origins build also
changes the stock movement predicate so the fast branch requires trait 38 in a
Like slot; a villager without the Running Like therefore remains at normal
movement speed.
It also performs no migration or repair of speed values written into a save by
an older experimental build; replacing that affected save is the player's
chosen recovery route.

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
