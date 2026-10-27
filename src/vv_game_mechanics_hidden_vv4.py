"""The Tree of Life (VV4): every hidden key, click, typed code and tip -- the Game Mechanics "Hidden keys, clicks and
cheats" group (src/vv_game_mechanics_hidden.py has the labels and the key path).

Read from the stock exe research/stock-executables/Virtual Villagers - The Tree of Life.exe (its classes named by RTTI):
  * the event pump 0x404830; the game's update 0x41E640 (state at +0x171A8: 0 the village, theMainScene built by
    0x441450);
  * the screens' input slots: theMainScene 0x4409E0 (characters 0x440550, keys 0x440840), CCollectionScene /
    CMausoleumScene / CTechScene 0x43C7D0, theHelpScene 0x43F020, thePuzzlesScene 0x445D10, theSplashScene 0x4469A0,
    CAchievementsScene / CAdoptionScene 0x43AAF0, theOverviewScene 0x444B40, theVillagerScene 0x447F70,
    theChangePlayerDlg 0x418390, theCreateNickNameDlg / theMessageBoxDlg 0x419D70, ldwTextControlImpl 0x40D750;
  * the developer's cheat (the IDebugger interface of theMainScene): the step value +0x50, F6 / F7 / F8 in 0x440840;
  * the village's mouse-down 0x442650 (the tip spot, the collection displays 0x440A70), the loading screen 0x43F180,
    the tip pop-ups 0x44B890.
Read only.
"""
from __future__ import annotations

import vv_game_mechanics as gm
import vv_game_mechanics_hidden as hidden
from vv_game_mechanics_hidden import C, CLICK, CODE, KEY, O, PATCHER, TIP, U, Entry

HIDDEN = "Hidden keys, clicks and cheats"
GAME = 4
PUMP = (0x404830, 0x404C40)
_VILLAGE_CHARS = frozenset(ord(c) for c in " 123456789BCDFMPTWbcdfmptw';[]")
KEY_HANDLERS = {
    0x40D750: (0x40D840, frozenset({1000, ord("-"), ord("0"), ord("9")})),
    0x418390: (0x4183C0, frozenset({1000, 1003})),
    0x419D70: (0x419DB0, frozenset({1000, 1003})),
    0x43AAF0: (0x43AB20, frozenset({1000})),
    0x43C7D0: (0x43C800, frozenset({1000, 1018})),
    0x43F020: (0x43F050, frozenset({1018})),
    0x4409E0: (0x440A40, frozenset()),
    0x440550: (0x440840, _VILLAGE_CHARS),
    0x440840: (0x4409D0, frozenset({1000, 1023, 1024, 1025})),
    0x444B40: (0x444B70, frozenset({1000})),
    0x445D10: (0x445D80, frozenset({1000, 1018, 1020})),
    0x4469A0: (0x446A80, frozenset({1018})),
    0x447F70: (0x447FA0, frozenset({1000})),
}
SPOT = (171, 488, 221, 584)              # 0x441450 +0x8C..+0x98
RANDOM_BASE, RANDOM_COUNT = 1025, 50
LOADING_COUNT = 50                       # 0x43F180: rand(50) + 1025
TIP_QUEUE = 0x44B890
SPOTS = {1: (-70, 1570), 2: (520, 1570), 3: (1250, 1510), 4: (-100, 827), 5: (420, 720), 6: (1250, 710),
         7: (-205, 200), 8: (340, 130), 9: (1140, 130)}

# The store-like screens' slots, checked for any random draw (the tests read them): (start, end).
RAND = 0x4036D0
STORE_SLOTS = ((0x43C7D0, 0x43C800), (0x43E9F0, 0x43EB50))

STORY = "vv4_story_cheat_upgrades"
ORIGINS = "vv4_enable_origins_exclusive_features"
DIFFICULTY = "vv4_difficulty_settings"
PATCHES = (DIFFICULTY, ORIGINS, STORY)
DEFAULT_OFF = frozenset({STORY})

ARMING = ("press C (it opens Collections; come back with Esc) and then D (it opens Detail; come back with Esc), or F "
          "and then D, in the village: C sets the screen's step value (+0x50) to 1, F flips it between 0 and 1, D with "
          "it at 1 sets it to 2, a character the village screen does not handle sets it back to 0, and once it is 2 any "
          "typed character at all sets it back to 0 (0x440550). F6, F7 and F8 are keys, not characters, so they leave "
          "it at 2 and can be pressed again")


def _keys() -> list[Entry]:
    spots = "; ".join(f"{key} {x}, {y}" for key, (x, y) in SPOTS.items())
    return [
        hidden.translator_entry(PUMP[0]),
        Entry(KEY, "Space (village screen)", (
            "pauses: the game's speed value goes up by 999 (0x440550; the speed at state +0x17110), which stops the "
            "game's clock. Space again takes the 999 off and the game runs at the speed it had (a value of exactly 999 "
            "comes back as Normal), and clears the message bar"), C),
        Entry(KEY, "1 to 9 (village screen)", (
            "send the view to nine spots laid out like a keypad (7 8 9 along the top, 1 2 3 along the bottom; "
            f"0x440550 -> 0x4707A0, kept inside the map): {spots}"), C),
        Entry(KEY, "C, D, M, P, T and Esc (village screen)", (
            "the same as clicking the screen's own buttons: C Collections, D Detail, M Map, P Puzzles, T Tech and Esc "
            "Menu (0x440550 and 0x440840 hand the button's number -- 6, 1, 5, 7, 4 and 0 -- to the screen's button "
            "slot). Capital and small letters work alike. C, F and D also step the developer's cheat (below)"), C),
        Entry(KEY, "The developer's cheat: C then D (or F then D), then F6, F7 or F8 (village screen)", (
            f"to arm it, {ARMING}. Once armed: F6 adds 80,000 tech points (0x41E300) and 5,000 food (0x41D920); F7 "
            "makes six new villagers (0x467D10 six times, kinds 0, 4, 4, 3, 1 and 2, each with 100 + rand(400)); F8 "
            "fires the island events one after another (0x417FF0, then 0x4182B0 runs the 49 event slots through "
            "0x418190). Unarmed, F6, F7 and F8 do nothing (0x440840)"), C, subs=(
                ("Seen by the owner (2026-10-11): C, Esc, D, Esc, then F6 on a fresh village took Tech Points from 99 to "
                 "80,099 and Food from 60 to 5,060.", O),
                ("Seen by the owner (2026-10-11): F7 makes villagers (six a press; the population reached 53 after "
                 "repeated presses).", O),
                ("Seen by the owner (2026-10-11): F8 fires every island event in turn, the first shown being \"The "
                 "Creeping Mold\".", O),
                ("How the patcher's logs record villagers made by F7 is not settled.", U))),
        Entry(KEY, "B (village screen)", (
            "when the fire burns and puzzle 2 is solved, the game asks a yes / no question of the stew pot (0x42DD20) "
            "and does nothing with the answer (0x440550); no effect was found"), U),
        Entry(KEY, "W, ' ; [ and ] (village screen)", (
            "tested and do nothing (0x440550); W is taken as handled, the others are passed on"), C),
        Entry(KEY, "F1 (help, splash, Puzzles and Milestones, Collections, the Mausoleum, Tech)", (
            "the help pictures, the splash and Puzzles jump straight into the village (game state 0: 0x43F020, "
            "0x4469A0, 0x445D10); on Collections, the Mausoleum and Tech F1 is the same as Esc (0x43C7D0)"), C),
        Entry(KEY, "F3 (Puzzles and Milestones)", (
            "flips one setting of the game's drawing object each press (0x445D10 -> 0x4083D0)"), C, subs=(
                ("What the setting changes on screen is not confirmed.", U),)),
        Entry(KEY, "Esc (Collections, the Mausoleum, Tech, Puzzles, the Map, Villager Detail, Trophies, Adoption)", (
            "the same as the screen's own way back (0x43C7D0, 0x445D10, 0x444B40, 0x447F70, 0x43AAF0)"), C),
        Entry(KEY, "Any typed character (the splash pictures)", (
            "shows the next splash picture, and after the last one moves on to game state 24 (0x4469A0). Esc and the "
            "other keys that are not characters do not"), C),
        Entry(KEY, "Enter and Esc (pop-up boxes)", (
            "in a message box or the name box's dialog Enter is the first button and Esc the second (0x419D70); in the "
            "Change Player box either key closes it (0x418390)"), C),
        Entry(KEY, "Typing in a name box", (
            "a typed character from 32 to 255 is added (a number box takes only 0 to 9, and \"-\" first), Backspace "
            "takes the last one off, and while the box is active it takes every key but Esc and does nothing with it "
            "(0x40D750)"), C, subs=(
                ("DEAD (never runs): the box's own ending on a typed Enter or Tab character (13 or 9): the event pump "
                 "never makes those characters (0x404830).", C),)),
        Entry(KEY, "Tab, the arrows, Page Up, Page Down, Home, End, Insert, Delete, F2, F4, F5, F9 and F10", (
            "no screen of The Tree of Life reacts to them (no input slot tests them)"), C),
        Entry(KEY, "Event type 7 (village screen)", (
            "theMainScene passes a type-7 event to 0x4409D0, which returns at once; nothing makes type-7 events (the "
            "event pump makes characters and keys only)"), C, dead=True),
        Entry(KEY, "Store screens: no redraw or reroll key", (
            "no key or click redraws, refreshes or rerolls what The Tree of Life offers. Its Tech screen (CTechScene) "
            "offers a fixed list at fixed prices; its input, mouse and button slots "
            "(0x43C7D0, 0x43E9F0) draw no random number (0x4036D0) and test only Esc and F1 (above)."
            ""
            " The patcher's Origins Upgrades, Villager Upgrades and Story / Cheat menus are Windows dialogs with "
            "no key handling of their own (native/ has no WM_KEYDOWN, WM_CHAR or key-state code), so only "
            "Windows' own dialog keys work there; their lists are fixed"), C),
    ]


def _codes() -> list[Entry]:
    return [
        Entry(CODE, "Typed codes and name cheats", (
            "the only typed sequence is the developer's C then D (or F then D) above. The name boxes only store what is "
            "typed (0x40D750)"), C, subs=(
                ("The developer-leftover search of 2026-10-11 (static) also found no comparison of a typed name with "
                 "any fixed word, no command-line switch and no date-based event.", U),)),
    ]


def _clicks() -> list[Entry]:
    x0, y0, x1, y1 = SPOT
    return [
        Entry(CLICK, "The tip spot (village screen)", (
            f"the spot from {x0} to {x1} across and {y0} to {y1} down on the 800 x 600 screen (A New Home's mask spot). "
            f"Each press of the left button on it plays a sound (95) and shows one of all {RANDOM_COUNT} random tips "
            f"(below) in the message bar: rand({RANDOM_COUNT}) + {RANDOM_BASE}, each tip 1 in {RANDOM_COUNT} a click, "
            "any tip can come again, nothing is remembered (0x442650)"), C, subs=(
                ("What is drawn on that spot was not checked.", U),)),
        Entry(CLICK, "The collection displays (village)", (
            "a click on the ground at one of four places shows how much of a collection is found (0x442650 -> "
            "0x440A70, map areas 77 to 80): \"<n> of 12 mausoleum mural pieces collected\", \"<n> of 12 fish scales "
            "collected\", \"<n> of 12 flutes collected\" and \"<n> of 12 pieces of lab equipment collected\""), C, subs=(
                ("The condition before it (the area at the click, 0x46C3D0, and 0x41DBC0) is not traced.",
                 U),)),
        Entry(CLICK, "Other places (village)", (
            "the ground click also runs 0x46E510 with the spot; what lines it can show was not traced"), U),
    ]


def _tips() -> list[Entry]:
    return [
        Entry(TIP, "Where the tips appear", (
            f"the loading screen shows one of all {RANDOM_COUNT} random tips, picked once when it is built (0x43F180: "
            f"rand({LOADING_COUNT}) + {RANDOM_BASE}, each 1 in {LOADING_COUNT}); the tip spot shows any of them too "
            "(above); the tutorial (eTTip) and milestone (eTip) pop-ups are asked for by number (0x44B890; whether one "
            "is still to show is tested by 0x44B9A0)"), C, subs=(
                ("Whether each pop-up shows once a village, and how \"Do you need help getting started?\" arms them, "
                 "is not traced.", U),
                ("The game seeds its random numbers from the computer's clock when it starts (0x402FE0 -> srand), so "
                 "the loading screen's tip differs from run to run.", C))),
        Entry(TIP, f"The {RANDOM_COUNT} random tips (eRandomTip1 to 50)", "every one, as the game words it:", C,
              subs=hidden.tip_lines(RANDOM_TIPS, lambda tip: C, lambda tip: "")),
        Entry(TIP, f"The {len(POPUP_TIPS)} tip pop-ups (eTTip tutorial, eTip milestones)", (
            "every one, as the game words it, with its name and the places that ask for it by number (a tip with none "
            "is asked for by a number the game works out, which is not traced, and is labelled as not confirmed)"), C,
              subs=hidden.tip_lines(POPUP_TIPS, lambda tip: C if tip[2] else U,
                                    lambda tip: tip[1] + ("; " + hidden.sites_note(tip[2]) if tip[2] else ""))),
    ]


def _patcher() -> list[Entry]:
    return [
        Entry(PATCHER, "Difficulty (Options dialog)", (
            "puts back the Difficulty choice -- Easy, Normal or Hard -- in the Options dialog "
            "(native/vvfp_difficulty)"), C, feature=DIFFICULTY),
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
    (1025, 'Certain herbs on the island can be used in cooking.'),
    (1026, 'One male villager can father many children.'),
    (1027, 'There are many useful spots to which you can drag villagers.'),
    (1028, 'Children can inherit some skill from their parents.'),
    (1029, 'Researching medicine reduces disease and extends longevity.'),
    (1030, 'Children can start working around age 14.'),
    (1031, 'Pause the game if you go away for very long.'),
    (1032, 'If your healer is sick, who is healing your villagers?'),
    (1033, 'Sick or nursing villagers do not work.'),
    (1034, 'Bored villagers tend to hang around the center of the village.'),
    (1035, 'A villager prefers the skill type you set.'),
    (1036, 'Sometimes villagers stubbornly do what they want.'),
    (1037, "Likes and dislikes can affect a villager's behavior."),
    (1038, 'Where is Isola?'),
    (1039, 'You can control whether villagers embrace or not.'),
    (1040, 'Set parenting skill to allow villagers to initiate embracing.'),
    (1041, 'Villagers can die of old age, disease, or starvation.'),
    (1042, 'M displays the map. SPACE toggles pause on and off.'),
    (1043, 'Adult villagers are naturally excellent swimmers.'),
    (1044, "Time passes whether you're playing the game or not."),
    (1045, 'Success at a task may entail meeting key requirements first.'),
    (1046, 'Reaching a milestone can benefit your villagers.'),
    (1047, "Gently selecting villagers doesn't disrupt what they're doing."),
    (1048, 'It can take several tries to teach something to a villager.'),
    (1049, 'Safe and happy villagers attempt new things.'),
    (1050, 'Master scientists produce more tech points than others.'),
    (1051, "A villager's skill preference can be set on the Detail Screen."),
    (1052, 'Your village can grow to a large population.'),
    (1053, 'Building more huts supports a larger population.'),
    (1054, 'Sick villagers tend to hang around the medical area.'),
    (1055, "The 'Learning' tech makes villagers learn new things faster."),
    (1056, 'Empty the pot by dropping a villager on the nearby grating.'),
    (1057, 'What happened to the tree?'),
    (1058, 'Fire assists researchers.'),
    (1059, 'Cooking stews can benefit your villagers.'),
    (1060, 'Skills can be learned by performing various tasks.'),
    (1061, "Add wood to your fire, so that you don't have to relight it."),
    (1062, 'Duplicate collectibles are turned into tech points.'),
    (1063, 'Lab collectibles permanently improve research productivity.'),
    (1064, 'Keep a fire burning to reduce disease.'),
    (1065, 'Medicine improves fertility.'),
    (1066, 'Different combinations of herbs make different stews.'),
    (1067, 'Only fresh water stews are edible.'),
    (1068, 'Children can gather herbs to bring to the lab.'),
    (1069, 'You can zip around the island with your numeric keys.'),
    (1070, 'Children will tend to look like their parents.'),
    (1071, 'Older villagers start to slow down.'),
    (1072, 'Highly skilled villagers have more effect on children.'),
    (1073, "Kids can't swim."),
    (1074, 'The more skill your nursery school teacher has, the better.'),
)
POPUP_TIPS = (
    (683, 'eTTipInstruct1\t\t\t\t\t', (0x43fc73,), "Let's explore the area... click and hold the mouse button anywhere on the ground and drag the mouse to move around the village."),  # noqa: E501
    (684, 'eTTipInfo2', (0x43fcd4,), 'Good! This is how you move about the island. Feel free to explore your little village.'),  # noqa: E501
    (685, 'eTTipInstruct3', (), "Let's get to know one of the villagers... find and click a villager to select them."),
    (686, 'eTTipInfo4', (0x442757,), 'Perfect! A white circle shows which villager is selected. See important details about this villager, like their name, at the bottom of the screen.'),  # noqa: E501
    (687, 'eTTipInstruct5', (), "Let's move a villager... click and hold the mouse button on a villager and drag the mouse to move them."),  # noqa: E501
    (688, 'eTTipInfo6', (0x43fd3d,), 'Excellent! Moving villagers influences their behavior. Drag and drop villagers anywhere you like to help them explore useful or interesting places in the village.'),  # noqa: E501
    (689, 'eTTipInstruct7', (), 'Your little villagers must be hungry, after their long expedition. Fortunately, there are some blackberries available. Just drag someone to the blackberry bush and they will attempt to gather some berries.'),  # noqa: E501
    (690, 'eTTipInfo8', (0x462c42,), 'Great job! Your villagers can survive on these blackberries until they find a more sustainable source of food.'),  # noqa: E501
    (691, 'eTTipInstruct9', (), 'Your villagers would benefit from a warm and cozy fire. First, drag an adult villager to this pile of driftwood, so they can gather wood.'),  # noqa: E501
    (692, 'eTTipInfo10', (0x432895,), 'Well done. There is a pile of dry firewood in the fire pit.'),
    (693, 'eTTipInstruct11', (), 'Kindling is also needed to start a fire. Drag your villager to this patch of dry grass.'),  # noqa: E501
    (694, 'eTTipInfo12', (0x4328fe,), 'Good. Your villager put an armful of dry grass into the fire pit.'),
    (695, 'eTTipInstruct13', (), "With dry firewood and kindling, all that's necessary to start the fire is to drag a villager to the fire pit."),  # noqa: E501
    (696, 'eTTipInfo14', (0x43282e,), 'Well done! Your tribe can now enjoy the benefits of a hot, crackling fire on those chilly nights.'),  # noqa: E501
    (697, 'eTTipInstruct15', (), "Your villagers interact with many locations around the map. Let's start by dragging one of them to this hut that needs some repair."),  # noqa: E501
    (698, 'eTTipInfo16', (0x46f5d1,), "Excellent! This hut is the love shack and is needed for villagers to 'discuss' having a baby. Keep working on it -- this hut will be built much faster than other huts. By the way, any hut that has not been worked on yet can be relocated by dragging it around the map. Release it anywhere when its footprint is green ."),  # noqa: E501
    (699, 'eTTipInstruct17', (), "Let's teach a villager to research... drag an adult villager to the large table at the center of the big structure."),  # noqa: E501
    (700, 'eTTipInfo18', (0x4633c2,), 'Great! This villager is learning to research. As research skills improve, you gain tech points that can be spent like money on new technologies.'),  # noqa: E501
    (701, 'eTTipInstruct21', (), "Let's check out the Technologies screen... click the 'Tech' button on the left side of the screen."),  # noqa: E501
    (702, 'eTTipInfo22', (0x43e442,), "Welcome to the Technologies screen. Use the tech points gained from research to upgrade a variety of different technologies. Click a '?' to learn more about a technology."),  # noqa: E501
    (703, 'eTTipInstruct25', (), 'Children can also contribute to village life. Their keen eyes can spot mushrooms and small collectibles that adults might overlook. Drag a child to this collectible before it disappears.'),  # noqa: E501
    (704, 'eTTipInfo26', (0x414506,), "Ooooh, the child found a collectible! Your villagers can collect Isola's small and beautiful treasures, but only when found by a child. The same collectible found more than once is converted into tech points."),  # noqa: E501
    (705, 'eTTipInstruct27', (), "Let's check out the Collections screen. Click the 'Collections' button on the left side of the screen."),  # noqa: E501
    (706, 'eTTipInfo28', (0x43c537,), 'Welcome to the Collections screen. Here you can see which collectibles your village children have gathered. Each set of collectibles benefits your tribe in some way. For example, each time you find a new piece of lab equipment, the researchers are permanently more productive!'),  # noqa: E501
    (707, 'eTTipInstruct29', (0x4685d0,), "Oh no! One of your little villagers is sick. Let's train a healer. Find the sick villager, then drag a second villager onto the sick one."),  # noqa: E501
    (708, 'eTTipInfo30', (0x45fe69,), 'Wonderful! The sick villager is better. Your healer also gained healing skill, which is essential for your villagers to lead long and healthy lives.'),  # noqa: E501
    (709, 'eTTipInstruct31', (), "Let's learn more about a villager... click the 'Detail' button at the bottom of the screen."),  # noqa: E501
    (710, 'eTTipInfo32', (0x447cfd,), "Welcome to the Detail screen. Learn more about each villager, such as age, health and skills. Check the box to the right of a skill to set a skill preference. Click 'Done' to return to the main screen."),  # noqa: E501
    (711, 'eTTipInstruct33', (), "Some of the mysteries of the island will require that other puzzles are solved first, or that certain supplies have been made available. Let's help your villagers with an easy one-- making a supply of cutting tools. Drop someone on this giant fish skeleton on the beach."),  # noqa: E501
    (712, 'eTTipInfo34', (0x43144a,), 'Excellent! Your villagers have 3 cutting tools available now. They can make more any time they need them-- all you have to do is drop another villager on the giant fish skeleton again.'),  # noqa: E501
    (713, 'eTTipInstruct35', (), "You can see the status of the game's puzzles on the Puzzles and Milestones screen. Click the 'Puzzles' button on the left side of the screen."),  # noqa: E501
    (714, 'eTTipInfo36', (0x445bbb,), "Welcome to the Puzzles and Milestones screen. The island is full of puzzles and hidden secrets waiting to be discovered. Your goal is to solve Isola's sixteen puzzles while helping your tribe survive."),  # noqa: E501
    (715, 'eTTipInstruct37', (), 'Well, as we approach the conclusion of this tutorial, we are really going to need that love shack finished. Keep deploying villagers (especially ones with building skill) on it until construction is complete.'),  # noqa: E501
    (716, 'eTTipInfo38', (), 'Good! The love shack is a romantic hut and a perfect place for village couples to discuss starting or adding to their families and the tribe!'),  # noqa: E501
    (717, 'eTTipInstruct39', (), "Let's make some babies... drag an adult male villager onto an adult female villager or vice versa. A villager will not seek a mate on their own unless they are trained, and Parenting is set as their preferred skill."),  # noqa: E501
    (718, 'eTTipInfo40', (0x460e9c,), 'Good! They get along and want to go indoors for some privacy. With any luck, the stork may bring a new baby.'),  # noqa: E501
    (719, 'eTTipStandAloneWelcome', (0x43fc4f,), 'Welcome to Virtual Villagers: The Tree Of Life Relief replaces panic as the villagers realize that they have been granted success in their quest for answers. They are certain that they have been led to this forsaken, dying tree. As they pray for continued guidance, they begin to seek a way to save it . . . and all of Isola!'),  # noqa: E501
    (720, 'eTTipStandAloneDragFail', (), 'Almost! Click and hold the mouse button anywhere on the ground and drag the mouse to move around the village.'),  # noqa: E501
    (721, 'eTTipStandAloneBlackberryWait', (), "Good! Let's wait while the villager gathers blackberries. If they succeed, they will bring some to the food bin near the center of the village."),  # noqa: E501
    (722, 'eTTipStandAloneBlackberryFail', (0x462bf0,), "Darn! The villager didn't succeed. Sometimes it takes a few tries, so drag the same villager to the blackberries again."),  # noqa: E501
    (723, 'eTTipStandAloneResearchWait', (), "Good! Let's give the villager a moment to research. If they succeed, you will earn tech points."),  # noqa: E501
    (724, 'eTTipStandAloneResearchFail', (0x463330,), 'Oh, well! The villager was unsuccessful at research. Drag the same villager to the table again.'),  # noqa: E501
    (725, 'eTTipStandAloneBreedFail', (0x460da3, 0x462e81), "Too bad! They didn't get along or aren't in the mood. Try again with the same couple or try a different pair to see if love blossoms."),  # noqa: E501
    (726, 'eTTipStandAloneFirstPreg', (), "Congratulations! The stork brought a baby. Be careful! A mother cares for her child until age two and won't do much else."),  # noqa: E501
    (727, 'eTTipStandAloneHealFail', (0x45feb3,), 'Shoot! The villager is still sick. Drag the same villager onto the sick one again.'),  # noqa: E501
    (728, 'eTTipStandAloneFirstDeath', (0x466508,), "I'm sorry. One of your little villagers is dead. Villagers die of old age, but they can also die from disease and starvation. Buying medicine technology helps your villagers live longer and have fewer diseases."),  # noqa: E501
    (729, 'eTTipStandAloneMiniMap', (0x4448c4,), "Welcome to the Overview Map. Enjoy a bird's-eye view of your village, then click anywhere on the map to zoom in to that spot."),  # noqa: E501
    (730, 'eTTipStandAloneRealTime', (), 'Virtual Villagers is a true real-time game. Your tribe continues to do what they have learned, even when the computer is off or you stop playing, but remember to check back often to care for your little villagers! Have fun!'),  # noqa: E501
    (731, 'eTTipStandAloneFinal', (0x43fa2d,), 'You have mastered the basics! How you manage your tribe now is up to you! Decide wisely who will do what. Your villagers will slowly learn to do the tasks you show them. Once survival is no longer an issue, you can help them uncover the hidden secrets of Isola! Remember that the game continues to run, even when it is off, so keep a close eye on your tribe!'),  # noqa: E501
    (732, 'eTTipStandAloneConfused', (0x452cbf,), 'Hmmm... this villager is confused. Sometimes villagers need more skill or more advanced technology before they understand what to do.'),  # noqa: E501
    (733, 'eTTipStandAloneSkillPref', (0x448121,), "Great! You set a villager's skill preference. From now on, they prefer this type of work and gain skill the more they practice."),  # noqa: E501
    (734, 'eTTipStandAloneChildrenNoWork', (0x46e4bd,), "Nice try, but children don't work. They love to play and won't do what you ask until they grow up. They can still help out though, as they sometimes find delicious mushrooms or collectibles."),  # noqa: E501
    (735, 'eTTipStandAloneMommiesNoWork', (0x46e4e7,), "Nursing mothers don't work while they are caring for an infant."),  # noqa: E501
    (736, 'eTTipStandAloneCuttingToolWait', (0x431670,), "Good. Let's watch this villager make a supply of cutting tools for the tribe."),  # noqa: E501
    (739, 'eTipFirstTrainee', (), "Congratulations! One of your villager's reached the `Trainee` level in a skill category."),  # noqa: E501
    (740, 'eTipFirstAdept', (), "Congratulations! One of your villager's reached the `Adept` level in a skill category."),  # noqa: E501
    (741, 'eTipFoodOk', (0x41d9ad, 0x464456, 0x4644e0, 0x464559, 0x464596, 0x4645d3, 0x46461e, 0x464a65), "Good job! Your villagers aren't worried about food anymore. Now you can focus on research and increasing the population of the village."),  # noqa: E501
    (742, 'eTipFirstAdult', (), 'One of the young children of your tribe is now old enough to work! Your tribe needs every able-bodied person to help out, so find that villager and keep everyone productive.'),  # noqa: E501
    (744, 'eTipFirstMaster', (0x468af0,), 'One of your villagers is a master in a skill! This is a great accomplishment. Making any one villager a master in all five skills grants that villager the prestigious title of Scholar.'),  # noqa: E501
    (745, 'eTipAbsPopCap', (0x42065d,), 'Congratulations! Your village reached its maximum sustainable population!'),
    (746, 'eTipNewRecipe', (), 'Your villagers found an interesting new recipe!'),
    (747, 'eTipYouLose', (0x420625,), 'Alas, the fates were not kind to your village. All of your little villagers died. The island of Isola remains a myth and its mysteries unsolved.'),  # noqa: E501
    (748, 'eTipPuzzlePotionsMade', (), 'The potions made Potion Made'),
    (749, 'eTipPuzzleStreamRestored', (0x439774,), 'The Stream Your villagers have restored the normal life-giving flow of the stream.'),  # noqa: E501
    (750, 'eTipPuzzleFruitwellsRestored', (0x433f94,), 'The Cooking Pit Your villagers have restored the fruit cooking pit back to functional condition.'),  # noqa: E501
    (751, 'eTipPuzzleButterfliesRestored', (0x438c97,), 'The Butterflies Your villagers have made the Tree of Life attractive to butterflies again.'),  # noqa: E501
    (752, 'eTipPuzzleCuttingToolsComplete', (0x4314fa,), 'The Cutting Tool Your villagers have discovered a method for the manufacture of cutting tools.'),  # noqa: E501
    (753, 'eTipPuzzleFrogRescueComplete', (0x4336ba,), 'The Frog Rescue Your villagers have rescued some frogs. Good for them!'),  # noqa: E501
    (754, 'eTipPuzzleMakingClothComplete', (0x4369ea,), 'Cloth Invented Your villagers have discovered a method for the manufacture of cloth.'),  # noqa: E501
    (755, 'eTipPuzzleFishingComplete', (0x433044,), 'Fishing Nets Your villagers have repaired the fish traps. Now they can add fish to their diet.'),  # noqa: E501
    (756, 'eTipPuzzleSoapInvented', (0x43a3aa,), 'Soap Invented Your villagers have invented soap! Now they can wash behind their ears.'),  # noqa: E501
    (757, 'eTipPuzzleBoilingWater', (0x42f62a,), 'Boiling Water Your villagers figured out how to boil water. Good for them!'),  # noqa: E501
    (758, 'eTipPuzzleMossyRocks', (0x436efa,), 'The Mossy Rocks A story seems to be carved in the rocks!'),
    (759, 'eTipPuzzleGrandFeast', (0x42eef6,), 'The Grand Feast The villagers have put together a marvelous feast!'),
    (760, 'eTipPuzzleNurserySchoolComplete', (0x43748a,), 'The Nursery School Your villagers have built a nursery school. This will help them raise smarter children.'),  # noqa: E501
    (761, 'eTipPuzzleHonorTreeComplete', (0x436775,), 'Honoring the Tree Your villagers have honored the tree.'),
    (762, 'eTipPuzzlePruningPuzzle', (0x437abf,), 'Pruning the Tree Your villagers have successfully treated the damaged tree limb.'),  # noqa: E501
    (763, 'eTipPuzzleTreeDecorated', (0x4319cf,), 'Decorating the Tree Your villagers have successfully decorated the tree.'),  # noqa: E501
    (764, 'eTipPuzzleHut1Built', (), 'A New Hut! Your villagers have restored one of the broken huts! Your tribe can now support a larger population.'),  # noqa: E501
    (765, 'eTipPuzzleClothingHutBuilt', (), 'The Clothing Hut Your villagers can now spend extra tech points to customize their outfits.'),  # noqa: E501
    (766, 'eTipPuzzleLoveShackBuilt', (0x43034b,), 'The Love Shack Your villagers now have a private, romantic place to which they can retreat.'),  # noqa: E501
    (767, 'eTipPuzzleFireStarted', (), 'Fire! When a fire is burning, your villagers are happier and less vulnerable to disease.'),  # noqa: E501
    (768, 'eTipPuzzlePurifyTree', (0x437eaf,), 'Purify Tree! The tree has been purified.'),
    (769, 'eTipPuzzleDecorateTree', (), 'Decorate Tree! The tree has been adorned with ceremonial ornaments.'),
    (770, 'eTipPuzzleFishScaleCollectionComplete', (), 'Fish Scale Collection Your children collected all of the different fish scales found on Isola! Your maximum village population is increased by 5.'),  # noqa: E501
    (771, 'eTipPuzzleLabPieceCollectionComplete', (), 'Lab Equipment Collection Your children collected all of the different types of lab equipment found on Isola! Your maximum village population is increased by 5.'),  # noqa: E501
    (772, 'eTipPuzzleMausoleumCollectionComplete', (), 'Mausoleum Mural Collection Your children collected all of the different mausoleum mural pieces found on Isola! Your maximum village population is increased by 5.'),  # noqa: E501
    (773, 'eTipPuzzleWindFluteCollectionComplete', (), 'Wind Flute Collection Your children collected all of the different types of wind flutes found on Isola! Your maximum village population is increased by 5.'),  # noqa: E501
    (774, 'eTipPuzzleAllCollectionsComplete', (0x4145d1,), 'All Collections Complete! Well done! Your children completed all four of the collections. In addition to keeping the collections, your maximum village population is increased by 5!'),  # noqa: E501
)
