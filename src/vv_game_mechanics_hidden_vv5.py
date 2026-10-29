"""New Believers (VV5): every hidden key, click, typed code and tip -- the Game Mechanics "Hidden keys, clicks and
cheats" group (src/vv_game_mechanics_hidden.py has the labels and the key path).

Read from the stock exe research/stock-executables/Virtual Villagers - New Believers.exe (its classes named by RTTI):
  * the event pump 0x4047C0; the game's update 0x423AF0 (state at +0x17E1C: 0 the village, theMainScene built by
    0x444630);
  * the screens' input slots: theMainScene 0x443610 (characters 0x443290, keys 0x443540), CCollectionScene /
    CMausoleumScene / CTechScene 0x441390, theHelpScene 0x441BD0, thePuzzlesScene 0x448F50, theSplashScene 0x449C60,
    CAchievementsScene / CAdoptionScene 0x43D3E0, theOverviewScene 0x447C90, theVillagerScene 0x44B530,
    theChangePlayerDlg 0x418AC0, theCreateNickNameDlg / theMessageBoxDlg 0x419B00, ldwTextControlImpl 0x40DC40;
  * the main scene's buttons (0x444630): 0 Menu, 1 Detail, 2 / 3 the villager arrows, 4 Tech, 5 Map, 6 Collections,
    7 Puzzles, 8 Replay Tutorial Instruction, 9 Trophies;
  * the loading screen theLoadingScene 0x441D30 (built by 0x423860), the tip pop-ups 0x44E730, the message bar 0x520F68
    (0x44EF60 by number, 0x44F0B0 by text).
Read only.
"""
from __future__ import annotations

import vv_game_mechanics as gm
import vv_game_mechanics_hidden as hidden
from vv_game_mechanics_hidden import C, CLICK, CODE, KEY, PATCHER, TIP, U, Entry

HIDDEN = "Hidden keys, clicks and cheats"
GAME = 5
PUMP = (0x4047C0, 0x404BD0)
_VILLAGE_CHARS = frozenset(ord(c) for c in " 123456789BCDEFMPTWbcdefgmptw';[]")
KEY_HANDLERS = {
    0x40DC40: (0x40DD30, frozenset({1000, ord("-"), ord("0"), ord("9")})),
    0x418AC0: (0x418AF0, frozenset({1000, 1003})),
    0x419B00: (0x419B40, frozenset({1000, 1003})),
    0x43D3E0: (0x43D410, frozenset({1000})),
    0x441390: (0x4413C0, frozenset({1000, 1018})),
    0x441BD0: (0x441C00, frozenset({1018})),
    0x443610: (0x443670, frozenset()),
    0x443290: (0x443540, _VILLAGE_CHARS),
    0x443540: (0x443600, frozenset({1000, 1025})),
    0x447C90: (0x447CC0, frozenset({1000})),
    0x448F50: (0x448FC0, frozenset({1000, 1018, 1020})),
    0x449C60: (0x449D40, frozenset({1018})),
    0x44B530: (0x44B560, frozenset({1000})),
}
RANDOM_BASE, RANDOM_COUNT = 1121, 50
LOADING_COUNT = 30                       # 0x441D30: rand(30) + 1121
TIP_QUEUE = 0x44E730
STRINGS_FIRST, STRINGS_COUNT = 81, 538   # F8: string 81 + the counter, the counter back to 0 after 537
SPOTS = {1: (-70, 1570), 2: (520, 1570), 3: (1250, 1510), 4: (-100, 827), 5: (800, 790), 6: (1250, 710),
         7: (-205, 200), 8: (340, 130), 9: (1140, 130)}

# The store-like screens' slots, checked for any random draw (the tests read them): (start, end).
RAND = 0x403660
STORE_SLOTS = ((0x441390, 0x4413C0), (0x4415F0, 0x4416F0))

STORY = "vv5_story_cheat_upgrades"
ORIGINS = "vv5_enable_origins_exclusive_features"
DIFFICULTY = "vv5_difficulty_settings"
CLICKABLE_TIPS = "vv5_clickable_tips"
PATCHES = (CLICKABLE_TIPS, DIFFICULTY, ORIGINS, STORY)
DEFAULT_OFF = frozenset({STORY})


def _keys() -> list[Entry]:
    spots = "; ".join(f"{key} {x}, {y}" for key, (x, y) in SPOTS.items())
    return [
        hidden.translator_entry(PUMP[0]),
        Entry(KEY, "Space (village screen)", (
            "pauses: the game's speed value goes up by 999 (0x443290; the speed at state +0x17D7C), which stops the "
            "game's clock. Space again takes the 999 off and the game runs at the speed it had (a value of exactly 999 "
            "comes back as Normal), and clears the message bar"), C),
        Entry(KEY, "1 to 9 (village screen)", (
            "send the view to nine spots laid out like a keypad (7 8 9 along the top, 1 2 3 along the bottom; "
            f"0x443290 -> 0x47B740, kept inside the map): {spots}"), C),
        Entry(KEY, "C, D, M, P and T (village screen)", (
            "the same as clicking the screen's own buttons: C Collections, D Detail, M Map, P Puzzles and T Tech "
            "(0x443290 hands the button's number -- 6, 1, 5, 7 and 4 -- to the screen's button slot 0x4463F0). Capital "
            "and small letters work alike"), C),
        Entry(KEY, "Esc (village screen)", (
            "the same as the Menu button, unless a God Power is armed on the pointer: then Esc only puts the power "
            "down (nothing is cast or spent) and stops the view's glide, and the next Esc opens the Menu (0x443540; "
            "the armed power is 0x51D5A4, the God Powers' +0xDC, -1 for none)"), C, subs=(
                ("No power is armed when the game starts: the game's own start-up sets it to none before anything else "
                 "runs (0x420192, from 0x493D20), so the first Esc opens the Menu. Only these set it: a mouse button's "
                 "release (0x420611: the power whose button was pressed and released there, or none), casting it or clicking its button again (0x423547), and Esc "
                 "(0x44356F).", C),
                ("While a power is armed, a due island event waits; it is tried on the village's next update after "
                 "the power is cast or put down (0x442708).", C))),
        Entry(KEY, "F8 (village screen)", (
            f"shows the game's own text strings one at a time in the message bar, the next one each press: string "
            f"{STRINGS_FIRST} plus a counter that goes up by one a press and starts again after {STRINGS_COUNT} "
            "strings (0x443540; the counter at the screen's +0x104). Nothing else changes: a developer's string "
            "viewer left in the game, with no switch in front of it"), C),
        Entry(KEY, "C then D (village screen)", (
            "C sets the screen's step value (+0x50) to 1 and D with it at 1 sets it to 2, as in The Tree of Life's "
            "cheat, but nothing reads the 2: the only test of the value is D's own (0x4433CC), and F6 and F7 are not "
            "handled at all (0x443540). The cheat itself was removed; C and D only open Collections and Detail"), C,
              dead=True),
        Entry(KEY, "E, F, W, g, B, ' ; [ and ] (village screen)", (
            "tested and do nothing (0x443290): E, F and W (capital or small) are taken as handled, a small g (not a "
            "capital) sets the step value above to 0, and B, ', ;, [ and ] are passed on"), C),
        Entry(KEY, "F1 (help, splash, Puzzles and Milestones, Collections, the Mausoleum, Tech)", (
            "the help pictures, the splash and Puzzles jump straight into the village (game state 0: 0x441BD0, "
            "0x449C60, 0x448F50); on Collections, the Mausoleum and Tech F1 is the same as Esc (0x441390)"), C),
        Entry(KEY, "F3 (Puzzles and Milestones)", (
            "flips one setting of the game's drawing object each press (0x448F50 -> 0x4083A0)"), C, subs=(
                ("What the setting changes on screen is not confirmed.", U),)),
        Entry(KEY, "Esc (Collections, the Mausoleum, Tech, Puzzles, the Map, Villager Detail, Trophies, Adoption)", (
            "the same as the screen's own way back (0x441390, 0x448F50, 0x447C90, 0x44B530, 0x43D3E0)"), C),
        Entry(KEY, "Any typed character (the splash pictures)", (
            "shows the next splash picture, and after the last one moves on to game state 24 (0x449C60). Esc and the "
            "other keys that are not characters do not"), C),
        Entry(KEY, "Enter and Esc (pop-up boxes)", (
            "in a message box or the name box's dialog Enter is the first button and Esc the second (0x419B00); in the "
            "Change Player box either key closes it (0x418AC0)"), C),
        Entry(KEY, "Typing in a name box", (
            "a typed character from 32 to 255 is added (a number box takes only 0 to 9, and \"-\" first), Backspace "
            "takes the last one off, and while the box is active it takes every key but Esc and does nothing with it "
            "(0x40DC40)"), C, subs=(
                ("DEAD (never runs): the box's own ending on a typed Enter or Tab character (13 or 9): the event pump "
                 "never makes those characters (0x4047C0).", C),)),
        Entry(KEY, "Tab, the arrows, Page Up, Page Down, Home, End, Insert, Delete, F2, F4 to F7, F9 and F10", (
            "no screen of New Believers reacts to them (no input slot tests them)"), C),
        Entry(KEY, "Event type 7 (village screen)", (
            "theMainScene passes a type-7 event to 0x443600, which returns at once; nothing makes type-7 events (the "
            "event pump makes characters and keys only)"), C, dead=True),
        Entry(KEY, "Store screens: no redraw or reroll key", (
            "no key or click redraws, refreshes or rerolls what New Believers offers. Its Tech screen (CTechScene) "
            "offers a fixed list at fixed prices; its input and button slots "
            "(0x441390, 0x4415F0) draw no random number (0x403660) and test only Esc and F1 (above)."
            " The screen's mouse slot 0x4413C0 draws random numbers only to scatter 8 sparkles over an icon the player can afford while the pointer moves onto it (rand(70) twice a sparkle); a click there opens that icon's description box; nothing it offers changes."
            " The patcher's Origins Upgrades, Villager Upgrades and Story / Cheat menus are Windows dialogs with "
            "no key handling of their own (native/ has no WM_KEYDOWN, WM_CHAR or key-state code), so only "
            "Windows' own dialog keys work there; their lists are fixed"), C),
    ]


def _codes() -> list[Entry]:
    return [
        Entry(CODE, "Typed codes and name cheats", (
            "none: C then D is left without its cheat (above), and the name boxes only store what is typed "
            "(0x40DC40)"), C, subs=(
                ("The developer-leftover search of 2026-10-11 (static) also found no comparison of a typed name with "
                 "any fixed word, no command-line switch and no date-based event.", U),)),
    ]


def _clicks() -> list[Entry]:
    return [
        Entry(CLICK, "No tip spot in the stock game", (
            "New Believers' village has no spot that shows a random tip: its mouse-down (0x445A60) picks no random "
            "tip, and the loading screen (0x441D30) is the stock game's only random-tip picker; the patcher's "
            "\"Clickable Tips\" adds one (see Patcher)"), C),
        Entry(CLICK, "Clicking villagers in the tutorial (village)", (
            "while the tutorial's steps are armed, clicking a Heathen in a blue, orange or red mask shows that step's "
            "tip about them (0x445A60: tips 678, 680 and 682)"), C),
        Entry(CLICK, "Places that show their state (village)", (
            "the ground click runs 0x443AC0 with the spot, which can write a collection count (\" of \", \"pieces of "
            "lab equipment collected\"); which places and lines it covers was not traced"), U),
    ]


def _tips() -> list[Entry]:
    return [
        Entry(TIP, "Where the tips appear", (
            f"the loading screen shows one of the first {LOADING_COUNT} random tips, picked once when it is built "
            f"(0x441D30: rand({LOADING_COUNT}) + {RANDOM_BASE}, each 1 in {LOADING_COUNT}); the tutorial (eTTip) and "
            "milestone (eTip) pop-ups are asked for by number (0x44E730; whether one is still to show is tested by "
            "0x44E840)"), C, subs=(
                ("The game seeds its random numbers from the computer's clock when it starts (0x402F70 -> srand), so "
                 "the loading screen's tip differs from run to run.", C),
                ("Random tips 31 to 50: no stock code was found asking for them; the patcher's \"Clickable Tips\" "
                 "shows all 50.", U),
                ("Whether each pop-up shows once a village is not traced.", U))),
        Entry(TIP, f"The {RANDOM_COUNT} random tips (eRandomTip1 to 50; the loading screen draws from the first "
                   f"{LOADING_COUNT})", "every one, as the game words it:", C,
              subs=hidden.tip_lines(RANDOM_TIPS, lambda tip: C if tip[0] < RANDOM_BASE + LOADING_COUNT else U,
                                    lambda tip: "" if tip[0] < RANDOM_BASE + LOADING_COUNT
                                    else "not in the loading screen's draw")),
        Entry(TIP, f"The {len(POPUP_TIPS)} tip pop-ups (eTTip tutorial, eTip milestones)", (
            "every one, as the game words it, with its name and the places that ask for it by number (a tip with none "
            "is asked for by a number the game works out, which is not traced, and is labelled as not confirmed)"), C,
              subs=hidden.tip_lines(POPUP_TIPS, lambda tip: C if tip[2] else U,
                                    lambda tip: tip[1] + ("; " + hidden.sites_note(tip[2]) if tip[2] else ""))),
    ]


def _patcher() -> list[Entry]:
    return [
        Entry(PATCHER, "The tip vine (village screen)", (
            "a left click on the village screen on the spot the patch's hook tests in the village's own mouse-down "
            "(0x4463AD: 164 to 194 across, 729 to 757 down, just below the Puzzles button the main scene places at "
            "105, 690 (0x444630)) plays the hou.ogg chime and shows one of all 50 random tips in the message bar "
            "(0x461 + the processor's time-stamp counter modulo 50, each tip about 1 in 50 a click, any tip can come "
            "again; the bar's own timer hides it; the click then goes on to the village as before; "
            "scripts/build_vv5_clickable_tips.py)"), C, feature=CLICKABLE_TIPS,
              subs=(("Across and down are the game's own: the button-down case asks SDL_GetMouseState for x and y "
                     "(0x404A4F) and queues them in that order (0x404A54..0x404A61), and the village scene's slot "
                     "hands them on in that order (0x4463AD..0x4463B7), where the hook tests x for 164 to 194 and y "
                     "for 729 to 757 (emulated in tests/test_vv5_clickable_tips.py).", C),
                    ("Only the village screen: the hook is in the village scene's own input slot (0x446370, named "
                     "only by its vtable 0x49A2F8), which the game's event queue (0x402160) calls only while that "
                     "screen is shown and no pop-up in front has taken the click; the village's buttons hide it "
                     "before another screen opens (Menu 0x443683, Detail 0x443837, Tech 0x44386D, Map 0x4438DD, "
                     "Collections 0x44395D, Trophies 0x4439CD, Puzzles 0x443A3D). Before v1.35.85 the hook sat in "
                     "the game's one event loop (0x404A5C) and the same spot of any screen gave a tip and the "
                     "chime.", C))),
        Entry(PATCHER, "Difficulty (Options dialog)", (
            "puts back the Difficulty choice -- Easy, Normal or Hard -- in the Options dialog, directly above Game "
            "Speed (native/vvfp_difficulty)"), C, feature=DIFFICULTY),
        Entry(PATCHER, "Upgrades buttons (Tech and Villager Detail screens)", (
            "a click opens the Origins Upgrades menu (Tech screen) or the Villager Upgrades menu (Villager Detail)"),
              C, feature=ORIGINS, subs=(("Esc closing these menus is tested only in A New Home.", U),)),
        Entry(PATCHER, "Story / Cheat menus (in the Origins Upgrades menu)", (
            "adds Pick Island Event, Custom Island Event and Choose Time Skip Amount, and makes every Origins Upgrade "
            "cost 0 tech points"), C, feature=STORY),
    ]


def entries() -> list[Entry]:
    return _keys() + _codes() + _clicks() + _tips() + _patcher()


def hidden_facts(village: gm.Village | None = None) -> list[gm.Fact]:
    return hidden.facts(entries(), DEFAULT_OFF, village)


def label(item) -> str:
    return hidden.label(item)

# ---------------------------------------------------------------------------
# The tips, read from the stock exe's string table (tests/island_event_exe.py), whitespace folded: (id, text) and
# (id, the string's name in the table or '', the places that ask for it by number, text).
# ---------------------------------------------------------------------------

RANDOM_TIPS = (
    (1121, 'Relics increase your max energy. Lab gear increases tech points.'),
    (1122, 'One male villager can father many children.'),
    (1123, 'There are many useful spots to which you can drag villagers.'),
    (1124, 'Children can inherit some skill from their parents.'),
    (1125, 'Researching medicine reduces disease and extends longevity.'),
    (1126, 'Children can start working around age 14.'),
    (1127, 'Pause the game if you go away for very long.'),
    (1128, 'If your healer is sick, who is healing your villagers?'),
    (1129, 'Sick or nursing villagers do not work.'),
    (1130, 'Bored villagers tend to hang around the center of the village.'),
    (1131, 'A villager prefers the skill type you set.'),
    (1132, 'Sometimes villagers stubbornly do what they want.'),
    (1133, "Likes and dislikes can affect a villager's behavior."),
    (1134, 'Where is Isola?'),
    (1135, 'You can control whether villagers embrace or not.'),
    (1136, 'Set parenting skill to allow villagers to initiate embracing.'),
    (1137, 'Villagers can die of old age, disease, or starvation.'),
    (1138, 'M displays the map. SPACE toggles pause on and off.'),
    (1139, 'Adult villagers are naturally excellent swimmers.'),
    (1140, "Time passes whether you're playing the game or not."),
    (1141, 'Success at a task may entail meeting key requirements first.'),
    (1142, 'Reaching a milestone can benefit your villagers.'),
    (1143, "Gently selecting villagers doesn't disrupt what they're doing."),
    (1144, 'It can take several tries to teach something to a villager.'),
    (1145, 'Safe and happy villagers attempt new things.'),
    (1146, 'Master scientists produce more tech points than others.'),
    (1147, "A villager's skill preference can be set on the Detail Screen."),
    (1148, 'Your village can grow to a large population.'),
    (1149, 'Building more huts supports a larger population.'),
    (1150, 'Sick villagers tend to hang around the medical area.'),
    (1151, "The 'Learning' tech makes villagers learn new things faster."),
    (1152, 'Devotees generate the most energy.'),
    (1153, 'Watch out for the heathen bully!'),
    (1154, 'Fire assists researchers.'),
    (1155, 'To get more extraordinary powers, get more believers!'),
    (1156, 'Skills can be learned by performing various tasks.'),
    (1157, "Add wood to your fire, so that you don't have to relight it."),
    (1158, 'Duplicate relics turn into energy for you.'),
    (1159, 'Lab collectibles permanently improve research productivity.'),
    (1160, 'Keep a fire burning to reduce disease.'),
    (1161, 'Medicine improves fertility.'),
    (1162, 'Distractions can be a very useful tactic.'),
    (1163, 'Convincing heathens to believe increases devotion skill.'),
    (1164, 'Polishing the statue gives energy and building skill.'),
    (1165, 'You can zip around the island with your numeric keys.'),
    (1166, 'Children will tend to look like their parents.'),
    (1167, 'Older villagers start to slow down.'),
    (1168, 'Highly skilled villagers have more effect on children.'),
    (1169, "Kids can't swim."),
    (1170, 'The more skill your nursery school teacher has, the better.'),
)
POPUP_TIPS = (
    (669, 'eTTipInstruct1\t\t\t\t\t', (0x4428c4,), "Let's explore the area... click and hold the mouse button anywhere on the ground and drag the mouse to move around the village."),  # noqa: E501
    (670, 'eTTipInfo2', (0x442928,), 'Good! This is how you move about the island. Feel free to explore your little village.'),  # noqa: E501
    (671, 'eTTipInstruct3', (), "Let's get to know one of the villagers... Find and click a villager, one without a mask, to select them."),  # noqa: E501
    (672, 'eTTipInfo4', (0x445ba4,), 'Perfect! A white circle shows which villager is selected. See important details about this villager, like their name, at the bottom of the screen.'),  # noqa: E501
    (673, 'eTTipInstruct5', (), "Let's move a villager... click and hold the mouse button on a villager and drag the mouse to move them."),  # noqa: E501
    (674, 'eTTipInfo6', (0x442991,), 'Excellent! Moving villagers influences their behavior. Drag and drop villagers anywhere you like to help them explore useful or interesting places in the village.'),  # noqa: E501
    (675, 'eTTipInstruct7', (), "Your villagers interact with many locations around the map. Let's start by dragging one of them to the green bamboo fence that imprisons them."),  # noqa: E501
    (676, 'eTTipInfo8', (0x438b4c,), 'Your villagers are using the green bamboo to build a bin to store much-needed food. Keep your villagers working on it.'),  # noqa: E501
    (677, 'eTTipInstruct9', (), 'You will notice there are villagers wearing various colorful masks. Find and click a villager wearing a blue mask.'),  # noqa: E501
    (678, 'eTTipInfo10', (0x445c7d,), "You selected a heathen villager. Heathen villagers don't believe in you, so you cannot check their details or interfere with them. Heathens wearing blue masks are not aggressive."),  # noqa: E501
    (679, 'eTTipInstruct11', (), 'Find and click a villager wearing an orange mask.'),
    (680, 'eTTipInfo12', (0x445c3a,), 'You selected a heathen guard. Heathens wearing orange masks are aggressive. If they are approached by believers, they will chase them away.'),  # noqa: E501
    (681, 'eTTipInstruct13', (), 'Find and click a villager wearing a red mask.'),
    (682, 'eTTipInfo14', (0x445bff,), "You selected a senior heathen guard. Heathens wearing red masks are scary. They won't chase believers away, but they are so scary that your villagers will run anyway."),  # noqa: E501
    (683, 'eTTipInstruct15', (), 'Try dropping one of your villagers onto a heathen villager wearing a blue mask.'),
    (684, 'eTTipInfo16', (0x468ee7,), 'Good! Your villager is persuading the heathen villager to believe in you. When the heathen villager faith meter crosses the middle, he or she will convert and join your tribe of believers.'),  # noqa: E501
    (685, 'eTTipInstruct17', (), "Villagers who believe in you increase your Divine Energy. This unlocks God Powers. Let's try a power now and spawn some butterflies. Click the butterfly icon on the top left of the screen, then click somewhere to release them."),  # noqa: E501
    (686, 'eTTipInfo18', (0x422aab,), 'Wow! Butterflies are great for distracting children, both believers and heathens alike. Notice how you used a little bit of your energy. The more believers you have, the faster your energy will replenish.'),  # noqa: E501
    (687, 'eTTipInstruct19', (), "Let's teach one of your villagers to research... Drag an adult villager to the large table at the center of the lab."),  # noqa: E501
    (688, 'eTTipInstruct20', (0x471d06,), 'Oh no! Your villager is being chased away by the heathens! The heathens occupy many areas of the village and have erected totems as a symbol of their ownership. In order to start research and gain tech points, you will need to gain control of each area by dismantling the totems. Once you take over the research area, your tribe can start generating tech points.'),  # noqa: E501
    (689, 'eTTipInstruct21', (), "Let's check out the Technologies screen... click the 'Tech' button on the left side of the screen."),  # noqa: E501
    (690, 'eTTipInfo22', (0x440d24,), "Welcome to the Technologies screen. Use the tech points gained from research to upgrade a variety of different technologies. The right side of the screen shows all the powers you have unlocked, as well as those you have not yet unlocked. They can be unlocked by increasing your divine energy. Click 'Done' to return to the main screen."),  # noqa: E501
    (691, 'eTTipInstruct25', (), 'Children can also contribute to village life. Their keen eyes can spot mushrooms and small collectibles that adults might overlook. Drag a child to this collectible before it disappears.'),  # noqa: E501
    (692, 'eTTipInfo26', (0x414862,), "Ooooh! The child found a relic! Your villagers can collect Isola's small and beautiful treasures, but only when found by a child. Repeat relics are converted into divine energy, while repeat lab gear gets converted into tech points."),  # noqa: E501
    (693, 'eTTipInstruct27', (), "Let's check out the Collections screen. Click the 'Collections' button on the left side of the screen."),  # noqa: E501
    (694, 'eTTipInfo28', (0x43ece7,), "Welcome to the Collections screen. Here you can see which collectibles your village children have gathered. Each relic that you collect permanently increases your maximum divine energy. Each piece of lab gear permanently increases tech point production! Click 'Done' to return to the main screen."),  # noqa: E501
    (695, 'eTTipInstruct29', (), "Let's learn more about a villager... click the 'Detail' button at the bottom of the screen."),  # noqa: E501
    (696, 'eTTipInfo30', (0x44b21d,), "Welcome to the Villager Detail screen. Learn more about each villager, such as faith, health and skills. Check the box to the right of a skill to set a skill preference. Click 'Done' to return to the main screen."),  # noqa: E501
    (697, 'eTTipInstruct31', (), "You can see the status of the game's puzzles on the Puzzles and Milestones screen. Click the 'Puzzles' button on the left side of the screen."),  # noqa: E501
    (698, 'eTTipInfo32', (0x448d6b,), "Welcome to the Puzzles and Milestones screen. The island is full of puzzles and hidden secrets waiting to be discovered. Your goal is to solve Isola's puzzles while helping your tribe survive and make more new believers."),  # noqa: E501
    (699, 'eTTipInstruct37', (), 'Well, as we approach the conclusion of this tutorial, we arrive at the inevitable topic of making babies! Deploy builders on the love shack to provide a romantic place to get together. Take your time... When you manage to get it finished, the final steps of the tutorial will resume.'),  # noqa: E501
    (700, 'eTTipInfo38', (), 'Good! The love shack is a romantic hut and a perfect place for village couples to discuss starting or adding to their families and the tribe!'),  # noqa: E501
    (701, 'eTTipInstruct39', (), "Let's make some babies... Drag an adult male villager onto an adult female villager or vice versa. A villager will not seek a mate on their own unless they are trained and Parenting is set as their preferred skill."),  # noqa: E501
    (702, 'eTTipInfo40', (0x468bf9,), 'Good! They get along and want to go indoors for some privacy. With any luck, the stork may bring a new baby.'),  # noqa: E501
    (703, 'eTTipStandAloneWelcome', (0x4428a0,), 'Welcome to Virtual Villagers: New Believers Oh no! Your villagers have been captured by a faceless tribe of non-believers. They need to establish themselves here in the center of Isola and try to help these heathens regain some hope and faith.'),  # noqa: E501
    (704, 'eTTipStandAloneDragFail', (), 'Almost! Click and hold the mouse button anywhere on the ground and drag the mouse to move around the village.'),  # noqa: E501
    (705, 'eTTipStandAloneBlackberryWait', (), "Good! Let's wait while the villager gathers noni. If they succeed, they will bring some to the food bin near the center of the village."),  # noqa: E501
    (706, 'eTTipStandAloneBlackberryFail', (0x46b3a3,), "Darn! The villager didn't succeed. Sometimes it takes a few tries, so drag the same villager to the noni again."),  # noqa: E501
    (707, 'eTTipStandAloneResearchWait', (), "Good! Let's give the villager a moment to research. If they succeed, you will earn tech points."),  # noqa: E501
    (708, 'eTTipStandAloneResearchFail', (0x46ba10,), 'Oh, well! The villager was unsuccessful at research. Drag the same villager to the table again.'),  # noqa: E501
    (709, 'eTTipStandAloneBreedFail', (0x468b06, 0x46b56f), "Too bad! They didn't get along or aren't in the mood. Try again with the same couple or try a different pair to see if love blossoms."),  # noqa: E501
    (710, 'eTTipStandAloneFirstPreg', (), "Congratulations! The stork brought a baby. Be careful! A mother cares for her child until age two and won't do much else."),  # noqa: E501
    (711, 'eTTipStandAloneHealFail', (0x468d89,), 'Shoot! The villager is still sick. Drag the same villager onto the sick one again.'),  # noqa: E501
    (712, 'eTTipStandAloneEvangelizeFail', (0x468ec8,), 'Hmmm... The villager is not convinced. Drag the same villager onto the heathen again.'),  # noqa: E501
    (713, 'eTTipStandAloneFirstDeath', (0x46ff40,), 'How sad. One of your little villagers is dead. Villagers die of old age, but they can also die from disease and starvation. Buying medicine technology helps your villagers live longer and have fewer diseases.'),  # noqa: E501
    (714, 'eTTipStandAloneMiniMap', (0x447a14,), "Welcome to the Overview Map. Enjoy a bird's-eye view of your village, then click anywhere on the map to zoom in to that spot."),  # noqa: E501
    (715, 'eTTipStandAloneRealTime', (), 'Virtual Villagers is a true real-time game. Your tribe continues to do what they have learned, even when the computer is off or you stop playing, but remember to check back often to care for your little villagers! Have fun!'),  # noqa: E501
    (716, 'eTTipStandAloneFinal', (0x4426da,), 'You have mastered the basics! How you manage your tribe now is up to you! Decide wisely who will do what. Your villagers will slowly learn to do the tasks you show them. Once survival is no longer an issue, you can help them uncover the hidden secrets of Isola!'),  # noqa: E501
    (717, 'eTTipStandAloneConfused', (0x45948f,), 'Hmmm... This villager is confused. Sometimes villagers need more skill or more advanced technology before they understand what to do.'),  # noqa: E501
    (718, 'eTTipStandAloneSkillPref', (0x44b728,), "Great! You set a villager's skill preference. From now on, they prefer this type of work and gain skill the more they practice."),  # noqa: E501
    (719, 'eTTipStandAloneChildrenNoWork', (0x479513,), "Nice try, but children don't work. They love to play and won't do what you ask until they grow up. They can still help out though, as they sometimes find delicious mushrooms or collectibles."),  # noqa: E501
    (720, 'eTTipStandAloneMommiesNoWork', (0x47953d,), "Nursing mothers don't work while they are caring for an infant."),  # noqa: E501
    (721, 'eTTipStandAloneCuttingToolWait', (), "Good. Let's watch this villager make a supply of cutting tools for the tribe."),  # noqa: E501
    (724, 'eTipFirstTrainee', (), 'Congratulations! One of your villagers reached the `Trainee` level in a skill category.'),  # noqa: E501
    (725, 'eTipFirstAdept', (), 'Congratulations! One of your villagers reached the `Adept` level in a skill category.'),  # noqa: E501
    (726, 'eTipFoodOk', (0x41ebcd, 0x46cfbf, 0x46d049, 0x46d0c2, 0x46d143, 0x46d782, 0x46d7bf, 0x46d7fc, 0x46db3f), "Good job! Your villagers aren't worried about food anymore. Now you can focus on research and increasing the population of the village."),  # noqa: E501
    (727, 'eTipFirstAdult', (), 'One of the young children of your tribe is now old enough to work! Your tribe needs every able-bodied person to help out, so find that villager, give them a job and keep everyone productive.'),  # noqa: E501
    (729, 'eTTipOneOffDragHeathen', (0x445f49,), 'You cannot touch heathens because they do not believe in you.'),
    (730, 'eTTipOneOffHeathenDetail', (0x443718,), 'You cannot view details about heathens. They do not believe in you.'),  # noqa: E501
    (731, 'eTTipOneOffFirstConversion', (0x466945,), 'You converted a heathen! Any time you make new believers, through conversion or new babies, you increase your max energy, which can eventually unlock new powers!'),  # noqa: E501
    (732, 'eTTipOneOffFirstTotem', (0x43b072,), 'Some totems will require special powers to help your villagers remove them. If you are stuck, work on increasing population and collecting relics.'),  # noqa: E501
    (733, 'eTTipOneOffFirstRelic', (0x414832,), 'Recovering relics adds to your max energy, which can unlock new, exciting powers!'),  # noqa: E501
    (734, 'eTTipOneOffPolisher', (0x479712,), 'Assigning builders to polish the statue helps them to practice building and gives you a bit of energy each time!'),  # noqa: E501
    (735, 'eTTipOneOffTired', (0x468e83,), 'You can only try to convert each heathen once, then you must wait a while before you can try again. The glowy light above them means they are tired of listening for now!'),  # noqa: E501
    (736, 'eTTipOneOffNewGodPower', (0x422e8c,), 'You have a new power! As you increase the number of people who believe in you, new powers become available.'),  # noqa: E501
    (737, 'eTipFirstMaster', (0x473351,), 'One of your villagers is a master in a skill! This is a great accomplishment. Making any one villager a master in at least three skills grants that villager the prestigious title of Elder.'),  # noqa: E501
    (738, 'eTipPopMilestoneSmall', (0x426246,), 'Congratulations! Your village reached its first population milestone of 15 people!'),  # noqa: E501
    (739, 'eTipPopMilestoneMed', (), 'Congratulations! Your village reached its second population milestone of 25 people!'),  # noqa: E501
    (740, 'eTipPopMilestoneLarge', (), 'Congratulations! Your village reached its third population milestone of 50 people!'),  # noqa: E501
    (741, 'eTipAbsPopCap', (), 'Congratulations! Your village reached its maximum sustainable population!'),
    (742, 'eTipNewRecipe', (), 'Your villagers found an interesting new recipe!'),
    (743, 'eTipYouLose', (0x4261de,), 'Alas, the fates were not kind to your village. There is nobody left who believes in you. The island of Isola remains a myth and its mysteries unsolved.'),  # noqa: E501
    (744, 'eTipPuzzleFenceComplete', (0x43892a,), 'The Prison Break Your villagers have torn down the flimsy bamboo fence and built a food bin from it. Now they have a place to store food.'),  # noqa: E501
    (745, 'eTipPuzzleFoodTotemComplete', (0x4393fa,), 'The Hungry Totem Your villagers have torn down an enemy totem. Now they can add noni fruit to their diet.'),  # noqa: E501
    (746, 'eTipPuzzleClosedEyeTotemComplete', (0x433e6a,), 'The Blind Totem Your villagers have reactivated this peculiar totem. Your vision in this area is restored!'),  # noqa: E501
    (747, 'eTipPuzzleRainbowTotemComplete', (0x43b4aa,), 'The Rainbow Totem Your villagers have torn down an enemy totem. The warm springs are now theirs to enjoy.'),  # noqa: E501
    (748, 'eTipPuzzleChildrensTotemComplete', (0x43367a,), "The Hollow Totem Your village children have broken an enemy totem. The lake is now part of the believers' domain."),  # noqa: E501
    (749, 'eTipPuzzleResearchTotemComplete', (0x43c10a,), 'The Knowing Totem Your villagers have torn down an enemy totem. They have gained access to the lab.'),  # noqa: E501
    (750, 'eTipPuzzleMedicineTotemComplete', (0x43a374,), 'The Pain Totem Your villagers have torn down an enemy totem. They have gained access to a healing area.'),  # noqa: E501
    (751, 'eTipPuzzleBuildingTotemComplete', (0x432eba,), 'The Blocking Totem Your villagers have torn down an enemy totem. They can now dig out the mausoleum safely.'),  # noqa: E501
    (752, 'eTipPuzzleConvertMasterDoctorComplete', (0x437da8,), 'The Sick Heathen Your villagers have cured a sick heathen, who has now joined the believers!'),  # noqa: E501
    (753, 'eTipPuzzleConvertHeathenChiefComplete', (0x4366d8,), 'The Heathen Chief Your villagers have finally convinced the Heathen Chief to join their cause!'),  # noqa: E501
    (754, 'eTipPuzzleConvertLastHeathenComplete', (0x437168,), 'The Last Heathen Your villagers have finally convinced the last of the heathen faction to join their cause!'),  # noqa: E501
    (755, 'eTipPuzzleBelieverIdolComplete', (0x4323f8,), 'The Tribute Statue Your villagers have sculpted a grand statue! This will maximize accumulation of divine energy.'),  # noqa: E501
    (756, 'eTipPuzzleHeathenMommyComplete', (0x4397da,), 'The Heathen Parent Your villagers have converted the heathen parent, who has decided to join the believers!'),  # noqa: E501
    (757, 'eTipPuzzleNurserySchoolComplete', (0x43a7f0,), 'The Nursery School Your villagers have built a nursery school. This will help them raise smarter children.'),  # noqa: E501
    (758, 'eTipPuzzleConvertMasterScientistComplete', (0x437ef8,), 'The Heathen Scientist Your villagers have convinced the heathen scientist to join the believers!'),  # noqa: E501
    (759, 'eTipPuzzleConvertMasterBuilderComplete', (0x437368,), 'The Heathen Builder Your villagers have convinced the heathen builder to join the believers!'),  # noqa: E501
    (760, 'eTipPuzzleHydrofarmComplete', (0x439e20,), 'The Hydroponic Farm Your villagers have restored an advanced hydroponic farm.'),  # noqa: E501
    (761, 'eTipPuzzleHut1Built', (), 'A New Hut! Your villagers have restored one of the broken huts! Your tribe can now support a larger population.'),  # noqa: E501
    (762, 'eTipPuzzleClothingHutBuilt', (), 'The Clothing Hut Your villagers can now spend extra tech points to customize their outfits.'),  # noqa: E501
    (763, 'eTipPuzzleLoveShackBuilt', (0x434e78,), 'The Love Shack Your villagers now have a private, romantic place to which they can retreat.'),  # noqa: E501
    (764, 'eTipPuzzleFireStarted', (), 'Fire! When a fire is burning, your villagers are happier and less vulnerable to disease.'),  # noqa: E501
    (765, 'eTipPuzzleRestoreLakeComplete', (0x43c7ca,), 'The Lake Fish! The lake is full of life once again, and your villagers have a regular source of food.'),  # noqa: E501
    (766, 'eTipPuzzleRestoreMausoleumComplete', (0x43c9b4,), 'The Buried Mausoleum Your villagers have restored the mausoleum, and once again have a place to honor their dead.'),  # noqa: E501
    (767, 'eTipPuzzleRelicCollectionComplete', (), 'Relic Collection Your children collected all of the relics found on Isola! Your maximum village population is increased by 5.'),  # noqa: E501
    (768, 'eTipPuzzleScienceItemCollectionComplete', (), 'Lab Equipment Collection Your children collected all of the science items found on Isola! Your maximum village population is increased by 5.'),  # noqa: E501
    (769, 'eTipPuzzleAllCollectionsComplete', (0x4148d7,), 'All Collections Complete! Well done! Your children completed both of the collections. In addition to keeping the collections, your maximum village population is increased by 5!'),  # noqa: E501
)
