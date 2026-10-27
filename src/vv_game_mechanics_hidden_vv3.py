"""The Secret City (VV3): every hidden key, click, typed code and tip -- the Game Mechanics "Hidden keys, clicks and
cheats" group (src/vv_game_mechanics_hidden.py has the labels and the key path).

Read from the stock exe research/stock-executables/Virtual Villagers - The Secret City.exe:
  * the event pump 0x404220; the game's update 0x427720 (state at +0x12FB8: 0 the village, built by 0x4676F0);
  * the screens' input slots: the village 0x4665E0 (characters 0x4662F0, keys 0x4665B0), the slot three screens share
    0x464D60 (vtables 0x49E790, 0x49E7D4, 0x49E834), the help pictures 0x465C90, the Map 0x46B950, the splash 0x46C910,
    Villager Detail 0x46CAF0, the boxes 0x41AC90 / 0x41C310, the name boxes 0x40D4A0;
  * the developer's editors that never run: the behaviour-script editor (object 0x58C548, vtable 0x481B58), the content
    map editor (0x58ED24, vtable 0x4826F0) and the waypoint editor (0x58ED9C, vtable 0x4828E4);
  * the village's mouse slot 0x46A630 -> 0x46A3D0 (the spot, the places that show their state 0x469A60; 0x42E0F0 the
    message bar), the loading screen 0x465E30, the tip pop-ups 0x436E60.
Read only.
"""
from __future__ import annotations

import vv_game_mechanics as gm
import vv_game_mechanics_hidden as hidden
from vv_game_mechanics_hidden import C, CLICK, CODE, KEY, O, PATCHER, TIP, U, Entry

HIDDEN = "Hidden keys, clicks and cheats"
GAME = 3
PUMP = (0x404220, 0x4045B0)
_VILLAGE_CHARS = frozenset(ord(c) for c in " 123456789CDFMPTWcdfmptw';[]")
KEY_HANDLERS = {
    0x40D4A0: (0x40D590, frozenset({1000, ord("-"), ord("0"), ord("9")})),
    0x41AC90: (0x41ACC0, frozenset({1000, 1003})),
    0x41C310: (0x41C350, frozenset({1000, 1003})),
    0x464D60: (0x464D90, frozenset({1000, 1018})),
    0x465C90: (0x465CC0, frozenset({1018})),
    0x4665E0: (0x466640, frozenset()),
    0x4662F0: (0x4665B0, _VILLAGE_CHARS),
    0x4665B0: (0x4665E0, frozenset({1000})),
    0x46B950: (0x46B980, frozenset({1000})),
    0x46C910: (0x46C9F0, frozenset({1018})),
    0x46CAF0: (0x46CB20, frozenset({1000})),
}
# The developer's editors (DEAD): their input slots and the keys each one tests.
DEAD_HANDLERS = {
    0x42A120: (0x42A570, frozenset(ord(c) for c in "-0=G[]abcdeghipst")),
    0x42A570: (0x42A590, frozenset({1002})),
    0x42BD60: (0x42BE70, frozenset({ord("B"), 1002, 1006, 1007, 1012, 1013, 1021})),
    0x42BEB0: (0x42C000, frozenset(ord(c) for c in ")+-4Gbhmor")),
    0x42C000: (0x42C120, frozenset({1002, 1012, 1013, 1021, 1022, 1023, 1024, 1025, 1026})),
    0x42C120: (0x42C140, frozenset({1002})),
    0x42CAB0: (0x42CAD0, frozenset({1021})),
}
SPOT = (171, 488, 221, 584)              # 0x4676F0 +0x7C..+0x88
RANDOM_BASE, RANDOM_COUNT = 1050, 50
LOADING_COUNT = 30                       # 0x465E30: rand(30) + 1050
TIP_QUEUE = 0x436E60
SPOTS = {1: (-70, 1570), 2: (520, 1570), 3: (1250, 1510), 4: (-100, 827), 5: (420, 720), 6: (1250, 710),
         7: (-205, 200), 8: (340, 130), 9: (1140, 130)}

# The store-like screens' slots, checked for any random draw (the tests read them): (start, end).
RAND = 0x4032D0
STORE_SLOTS = ((0x462A70, 0x462C80), (0x4633A0, 0x4633F0), (0x463770, 0x4639C0), (0x464230, 0x464290), (0x464D60, 0x464D90), (0x464D90, 0x464F30), (0x465640, 0x465820))

STORY = "vv3_story_cheat_upgrades"
ORIGINS = "vv3_enable_origins_exclusive_features"
FACTIONS = "vv3_both_factions"
PATCHES = (FACTIONS, ORIGINS, STORY)
DEFAULT_OFF = frozenset({STORY})


def _keys() -> list[Entry]:
    spots = "; ".join(f"{key} {x}, {y}" for key, (x, y) in SPOTS.items())
    return [
        hidden.translator_entry(PUMP[0]),
        Entry(KEY, "Space (village screen)", (
            "pauses: the game's speed value goes up by 999 (0x4662F0; the speed at state +0x12F20), which stops the "
            "game's clock. Space again takes the 999 off and the game runs at the speed it had, and clears the message "
            "bar"), C),
        Entry(KEY, "1 to 9 (village screen)", (
            "send the view to nine spots laid out like a keypad (7 8 9 along the top, 1 2 3 along the bottom; "
            f"0x4662F0 -> 0x423870, kept inside the map): {spots}"), C),
        Entry(KEY, "C, D, M, P, T and Esc (village screen)", (
            "the same as clicking the screen's own buttons: C Collections, D Detail, M Map, P Puzzles, T Tech and Esc "
            "Menu (0x4662F0 and 0x4665B0 hand the button's number -- 4, 1, 3, 5, 2 and 0 -- to the screen's button "
            "slot). Capital and small letters work alike"), C),
        Entry(KEY, "F then W (village screen)", (
            "no effect was found. F flips a value of the village screen (+0x40) between 0 and 1, W with it at 1 sets "
            "it to 2, and any other unlisted character sets it back to 0 (0x4662F0); no code of the village screen "
            "was found reading the value"), U, subs=(
                ("Seen by the owner (2026-10-11): F then W, then the F keys, did nothing visible.", O),)),
        Entry(KEY, "' ; [ and ] (village screen)", (
            "the village screen tests them and does nothing with them (0x4662F0); unlike other characters they leave "
            "the F then W value alone"), C),
        Entry(KEY, "F1 (the help pictures, the splash, the three screens of the shared slot)", (
            "the help pictures and the splash jump straight into the village (game state 0: 0x465C90, 0x46C910); on the "
            "three screens of the shared slot (0x464D60) F1 is the same as Esc"), C),
        Entry(KEY, "Esc (the shared slot's three screens, Map, Villager Detail)", (
            "the same as the screen's own way back (0x464D60, 0x46B950, 0x46CAF0)"), C, subs=(
                ("Which three screens share 0x464D60 is not read here; in The Tree of Life and New Believers that slot "
                 "serves Collections, the Mausoleum and Tech.", U),)),
        Entry(KEY, "Any typed character (the splash pictures)", (
            "shows the next splash picture, and after the last one moves on to game state 20 (0x46C910). Esc and the "
            "other keys that are not characters do not"), C),
        Entry(KEY, "Enter and Esc (pop-up boxes)", (
            "in a two-button box Enter is the first button and Esc the second (0x41C310); in a one-button box either "
            "key closes it (0x41AC90)"), C),
        Entry(KEY, "Typing in a name box", (
            "a typed character from 32 to 255 is added (a number box takes only 0 to 9, and \"-\" first), Backspace "
            "takes the last one off, and while the box is active it takes every key but Esc and does nothing with it "
            "(0x40D4A0)"), C, subs=(
                ("DEAD (never runs): the box's own ending on a typed Enter or Tab character (13 or 9): the event pump "
                 "never makes those characters (0x404220).", C),)),
        Entry(KEY, "F3 and the keys not listed", (
            "no live screen of The Secret City tests F3, Tab, the arrows, Page Up, Page Down, Home, End, Insert, "
            "Delete, F2 or F4 to F10 (only the dead editors below do)"), C),
        Entry(KEY, "The developer's three editors (behaviour scripts, the content map, waypoints)", (
            "their keys -- the behaviour-script editor's - 0 = G [ ] a b c d e g h i p s t and Tab (0x42A120, "
            "0x42A570), the content map editor's + - ) 4 G b h m o r, B, Tab, Up, Down, Insert, Delete and F4 (0x42BEB0, "
            "0x42BD60), the waypoint editor's Tab, Insert, Delete and F4 to F9 (0x42C000, 0x42C120, 0x42CAB0) -- never "
            "reach them: the three editor objects (0x58C548, 0x58ED24, 0x58ED9C) are touched only by their static "
            "constructors (0x47AEA0, 0x47AEB0, 0x47AEE0), by their own code and by 0x42CA60, which nothing calls; no "
            "screen hands them input"), C, dead=True),
        Entry(KEY, "Event type 7 (village screen)", (
            "the village screen passes a type-7 event to 0x42CAD0, which returns at once; nothing makes type-7 events "
            "(the event pump makes characters and keys only)"), C, dead=True),
        Entry(KEY, "Store screens: no redraw or reroll key", (
            "no key or click redraws, refreshes or rerolls what The Secret City offers. Its Tech screen and the two screens that share its input slot each "
            "offers a fixed list at fixed prices; its input, mouse and button slots "
            "(0x462A70, 0x4633A0, 0x463770, 0x464230, 0x464D60, 0x464D90, 0x465640) draw no random number (0x4032D0) and test only Esc and F1 (above)."
            ""
            " The patcher's Origins Upgrades, Villager Upgrades and Story / Cheat menus are Windows dialogs with "
            "no key handling of their own (native/ has no WM_KEYDOWN, WM_CHAR or key-state code), so only "
            "Windows' own dialog keys work there; their lists are fixed"), C),
    ]


def _codes() -> list[Entry]:
    return [
        Entry(CODE, "Typed codes and name cheats", (
            "none in play. Outside the name boxes a typed letter is a single key (above), and the name boxes only "
            "store what is typed (0x40D4A0)"), C, subs=(
                ("The developer-leftover search of 2026-10-11 (static) also found no comparison of a typed name with "
                 "any fixed word, no command-line switch and no date-based event.", U),)),
    ]


_PLACE_LINES = ("Time remaining for fire:", "The bath needs some repair.", "Percentage repair completed:",
                "The bath is repaired.", "The machine is broken.", "It's a primitive lift!",
                "This potion will evaporate in %dm %02ds", "There is no potion ready!", "Still need %d additional herbs!",
                "The herbs are ready to make a potion", "The alchemy lab is in ruins!", "Food available to villagers:",
                "There is not enough to harvest.", "Honey remaining in hive:", "It's a beautiful princess!",
                "Time Until Repaired:", "The statue looks too splendid to leave broken.", "Tech Points Available:",
                "Percentage construction completed:", "Time Until Mature:", "Fruit on tree:",
                "There is a cave entrance here.", "Percentage of rubble removed:", "Percentage of leaves removed:",
                "The chalkboard could be used for drawing plans.", "The chalkboard contains detailed plans.")


def _clicks() -> list[Entry]:
    x0, y0, x1, y1 = SPOT
    return [
        Entry(CLICK, "The tip spot (village screen)", (
            f"the spot from {x0} to {x1} across and {y0} to {y1} down on the 800 x 600 screen (A New Home's mask spot). "
            f"Each press of the left button on it plays a sound (95) and shows one of all {RANDOM_COUNT} random tips "
            f"(below) in the message bar: rand({RANDOM_COUNT}) + {RANDOM_BASE}, each tip 1 in {RANDOM_COUNT} a click, "
            "any tip can come again, nothing is remembered (0x46A3D0)"), C, subs=(
                ("What is drawn on that spot was not checked.", U),)),
        Entry(CLICK, "Places that show their state (village)", (
            "a click on the ground (not on a villager, nor on something to pick up) writes one of these lines in the "
            "message bar, chosen by the place clicked and its state (0x46A3D0 -> 0x46A350 -> 0x469A60); the %d marks "
            "are the game's figures"), C,
              subs=tuple((f"\"{line}\"", C) for line in _PLACE_LINES) + (
                  ("Which place gives which line, and the conditions, are in 0x469A60 and not written out here.", U),
                  ("One place (area 34), when its condition holds, plays a sound (133) and opens a pop-up instead "
                   "(0x469A60); what the pop-up is was not identified.", U))),
    ]


def _tips() -> list[Entry]:
    return [
        Entry(TIP, "Where the tips appear", (
            f"the loading screen shows one of the first {LOADING_COUNT} random tips, picked once when it is built "
            f"(0x465E30: rand({LOADING_COUNT}) + {RANDOM_BASE}, each 1 in {LOADING_COUNT}); the tip spot shows any of "
            f"all {RANDOM_COUNT} (above); the tutorial (eTTip) and milestone (eTip) pop-ups are asked for by number "
            "(0x436E60)"), C, subs=(
                ("Whether each pop-up shows once a village, and how the tutorial question arms them, is not traced.",
                 U),)),
        Entry(TIP, f"The {RANDOM_COUNT} random tips (eRandomTip1 to 50; the loading screen draws from the first "
                   f"{LOADING_COUNT}, the tip spot from all)", "every one, as the game words it:", C,
              subs=hidden.tip_lines(RANDOM_TIPS, lambda tip: C,
                                    lambda tip: "" if tip[0] < RANDOM_BASE + LOADING_COUNT else "the tip spot only")),
        Entry(TIP, f"The {len(POPUP_TIPS)} tip pop-ups (eTTip tutorial, eTip milestones)", (
            "every one, as the game words it, with its name and the places that ask for it by number (a tip with none "
            "is asked for by a number the game works out, which is not traced: UNCONFIRMED)"), C,
              subs=hidden.tip_lines(POPUP_TIPS, lambda tip: C if tip[2] else U,
                                    lambda tip: tip[1] + ("; " + hidden.sites_note(tip[2]) if tip[2] else ""))),
    ]


def _patcher() -> list[Entry]:
    return [
        Entry(PATCHER, "The second faction (Tech screen)", (
            "clicking the other faction after buying one buys it too, instead of \"You have already chosen your "
            "faction!\" (native/vvfp_vv3_both_factions)"), C, feature=FACTIONS),
        Entry(PATCHER, "Upgrades buttons (Tech and Villager Detail screens)", (
            "a click opens the Origins Upgrades menu (Tech screen) or the Villager Upgrades menu (Villager Detail)"),
              C, feature=ORIGINS, subs=(("Esc closing these menus is tested only in A New Home.", U),)),
        Entry(PATCHER, "Story / Cheat menus (in the Origins Upgrades menu)", (
            "adds Pick Island Event, Custom Island Event, Choose Time Skip Amount and Recharge Chief Powers, and makes "
            "every Origins Upgrade cost 0 tech points"), C, feature=STORY),
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
    (1050, 'Certain herbs on the island can be used in alchemy.'),
    (1051, 'One male villager can father many children.'),
    (1052, 'There are many useful spots to which you can drag villagers.'),
    (1053, 'Children can inherit some skill from their parents.'),
    (1054, 'Researching medicine reduces disease and extends longevity.'),
    (1055, 'Children can start working around age 14.'),
    (1056, 'Pause the game if you go away for very long.'),
    (1057, 'If your healer is sick, who is healing your villagers?'),
    (1058, 'Sick or nursing villagers do not work.'),
    (1059, 'Bored villagers tend to hang around the center of the village.'),
    (1060, 'A villager prefers the skill type you set.'),
    (1061, 'Sometimes villagers stubbornly do what they want.'),
    (1062, "Likes and dislikes can affect a villager's behavior."),
    (1063, 'Where is Isola?'),
    (1064, 'The chief has some powers that can be used only once a day.'),
    (1065, 'The bigger the tribe, the more influence your chief has.'),
    (1066, 'Villagers can die of old age, disease, or starvation.'),
    (1067, 'M displays the map. SPACE toggles pause on and off.'),
    (1068, 'Adult villagers are naturally excellent swimmers.'),
    (1069, "Time passes whether you're playing the game or not."),
    (1070, 'Success at a task may entail meeting key requirements first.'),
    (1071, 'Reaching a milestone can benefit your villagers.'),
    (1072, "Gently selecting villagers doesn't disrupt what they're doing."),
    (1073, 'It can take several tries to teach something to a villager.'),
    (1074, 'Safe and happy villagers attempt new things.'),
    (1075, 'Master scientists produce more tech points than others.'),
    (1076, "A villager's skill preference can be set on the Detail Screen."),
    (1077, 'Your village can grow to a large population.'),
    (1078, 'Building more huts supports a larger population.'),
    (1079, 'Sick villagers tend to hang around the medical area.'),
    (1080, 'If your hand gets tired, give it a rest!'),
    (1081, 'Empty the pot by dropping a villager on a table full of herbs.'),
    (1082, 'What happened to the city?'),
    (1083, 'Fire assists researchers.'),
    (1084, 'Alchemy can be hazardous to your villagers.'),
    (1085, 'Skills can be learned by performing various tasks.'),
    (1086, "Add wood to your fire, so that you don't have to relight it."),
    (1087, 'Duplicate collectibles are turned into tech points.'),
    (1088, 'Having children pick up collectibles is optional.'),
    (1089, 'Keep a fire burning to reduce disease.'),
    (1090, 'Medicine improves fertility.'),
    (1091, 'Different combinations of herbs make different potions.'),
    (1092, 'Different potions have different effects on villagers.'),
    (1093, 'Children can gather herbs to bring to the lab.'),
    (1094, 'You can zip around the island with your numeric keys.'),
    (1095, 'Children will tend to look like their parents.'),
    (1096, 'Older villagers start to slow down.'),
    (1097, 'A chief does not work, but enhances the work of others.'),
    (1098, "Kids can't swim."),
    (1099, 'Different herbs have different properties in potions.'),
)
POPUP_TIPS = (
    (634, 'eTTipInstruct1\t\t\t\t\t', (0x468947,), "Let's explore the area... click and hold the mouse button anywhere on the ground and drag the mouse to move around the village."),  # noqa: E501
    (635, 'eTTipInfo2', (0x4689b4,), 'Good! This is how you move about the island. Feel free to explore your little village.'),  # noqa: E501
    (636, 'eTTipInstruct3', (), "Let's get to know one of the villagers... find and click a villager to select them."),
    (637, 'eTTipInfo4', (0x46a4c2,), 'Perfect! A white circle shows which villager is selected. See important details about this villager, like their name, at the bottom of the screen.'),  # noqa: E501
    (638, 'eTTipInstruct5', (), "Let's move a villager... click and hold the mouse button on a villager and drag the mouse to move them."),  # noqa: E501
    (639, 'eTTipInfo6', (0x468a21,), 'Excellent! Moving villagers influences their behavior. Drag and drop villagers anywhere you like to help them explore useful or interesting places in the village.'),  # noqa: E501
    (640, 'eTTipInstruct7', (), "Your villagers interact with many locations around the map. Let's start by dragging one of them to this hut that needs some repair."),  # noqa: E501
    (641, 'eTTipInfo8', (0x42266f,), 'Excellent! Dragging a villager to this broken structure in the village encourages progress. New structures allow a larger population and many other things.'),  # noqa: E501
    (642, 'eTTipInstruct9', (), 'Your villagers would benefit from a warm and cozy fire. First, drag an adult villager to this pile of driftwood, so they can gather wood.'),  # noqa: E501
    (643, 'eTTipInfo10', (0x433ac0,), 'Well done. There is a stack of dry firewood in the fire pit.'),
    (644, 'eTTipInstruct11', (), 'Kindling is also needed to start a fire. Drag your villager to this patch of dry grass.'),  # noqa: E501
    (645, 'eTTipInfo12', (0x433b5c,), 'Good. Your villager put an armful of dry grass into the fire pit.'),
    (646, 'eTTipInstruct13', (), "With dry firewood and kindling, all that's necessary to start the fire is to drag a villager to the fire pit."),  # noqa: E501
    (647, 'eTTipInfo14', (0x433a61,), 'Well done! Your tribe can now enjoy the benefits of a hot, crackling fire on those chilly nights.'),  # noqa: E501
    (648, 'eTTipInstruct15', (), 'Your little villagers must be hungry. There must be some delicious honey up in the beehive. Drag a villager to the dark stick on the ground... maybe there is a way to take care of those angry bees.'),  # noqa: E501
    (649, 'eTTipInfo16', (0x43162e,), 'Wonderful! Your villager calmed the bees using smoke, and the bees are no longer a problem.'),  # noqa: E501
    (650, 'eTTipInstruct17', (), "Now that you've calmed the bees, you can safely drag a villager to the hive to gather honey."),  # noqa: E501
    (651, 'eTTipInfo18', (0x45a433,), 'Great! Your villagers now have a source of food. They will discover more sources of food later.'),  # noqa: E501
    (652, 'eTTipInstruct19', (), "Let's teach a villager to research... drag an adult villager to the large table at the center of the big structure."),  # noqa: E501
    (653, 'eTTipInfo20', (0x45a9b2,), 'Great! This villager is learning to research. As research skills improve, you gain tech points that can be spent like money on new technologies.'),  # noqa: E501
    (654, 'eTTipInstruct21', (), "Let's check out the Technologies screen... click the 'Tech' button on the left side of the screen."),  # noqa: E501
    (655, 'eTTipInfo22', (0x465550,), "Welcome to the Technologies screen. Use the tech points gained from research to upgrade a variety of different technologies. Click a '?' to learn more about a technology."),  # noqa: E501
    (656, 'eTTipInstruct23', (), "Let's make some babies... drag an adult male villager onto an adult female villager or vice versa. Note that dragging an adult to a child causes the adult to entertain the child with a story."),  # noqa: E501
    (657, 'eTTipInfo24', (0x45872a,), 'Good! They get along and want to go indoors for some privacy. With any luck, the stork may bring a new baby.'),  # noqa: E501
    (658, 'eTTipInstruct25', (), "Children can also contribute to village life. Their keen eyes can spot mushrooms and small collectibles that adults might overlook. Drag a child to this collectible before it disappears. Don't worry, though, collecting items is optional."),  # noqa: E501
    (659, 'eTTipInfo26', (0x42df95,), "Ooooh, the child found a collectible! Your villagers can collect Isola's small and beautiful treasures, but only when found by a child. The same collectible found more than once is converted into tech points."),  # noqa: E501
    (660, 'eTTipInstruct27', (), "Let's check out the Collections screen. Click the 'Collections' button on the left side of the screen."),  # noqa: E501
    (661, 'eTTipInfo28', (0x46294b,), 'Welcome to the Collections screen. Here you can see which collectibles your village children gathered. You can also check your progress on finding the keys that open the mysterious door.'),  # noqa: E501
    (662, 'eTTipInstruct29', (0x460176,), "Oh no! One of your little villagers is sick. Let's train a healer. Find the sick villager, then drag a second villager onto the sick one."),  # noqa: E501
    (663, 'eTTipInfo30', (0x4573f7,), 'Wonderful! The sick villager is better. Your healer also gained healing skill, which is essential for your villagers to lead long and healthy lives.'),  # noqa: E501
    (664, 'eTTipInstruct31', (), "Let's learn more about a villager... click the 'Detail' button at the bottom of the screen."),  # noqa: E501
    (665, 'eTTipInfo32', (0x46dcac,), "Welcome to the Detail screen. Learn more about each villager, such as age, health and skills. Check the box to the right of a skill to set a skill preference. Click 'Done' to return to the main screen."),  # noqa: E501
    (666, 'eTTipInstruct33', (), "Finally, let's check out the Puzzles and Milestones screen. Click the 'Puzzles' button on the left side of the screen."),  # noqa: E501
    (667, 'eTTipInfo34', (0x463521,), "Welcome to the Puzzles and Milestones screen. The island is full of puzzles and hidden secrets waiting to be discovered. Your goal is to solve Isola's sixteen puzzles while helping your tribe survive."),  # noqa: E501
    (668, 'eTTipStandAloneWelcome', (0x468920,), 'Welcome to Virtual Villagers: The Secret City! After their perilous, storm-tossed journey on a tiny raft, this small band of villagers gazes in amazement at what appears to be the ruins of what must have once been a wonderful city. They sense something, or someone, beckoning them . . .'),  # noqa: E501
    (669, 'eTTipStandAloneDragFail', (), 'Almost! Click and hold the mouse button anywhere on the ground and drag the mouse to move around the village.'),  # noqa: E501
    (670, 'eTTipStandAloneHoneyWait', (), "Good! Let's wait while the villager gathers honey. If they succeed, they will bring the honey to the food bin near the center of the village."),  # noqa: E501
    (671, 'eTTipStandAloneHoneyFail', (0x45a3f6,), "Darn! The villager didn't succeed. Sometimes it takes a few tries, so drag the same villager to the bee hive again."),  # noqa: E501
    (672, 'eTTipStandAloneResearchWait', (), "Good! Let's give the villager a moment to research. If they succeed, you will earn tech points."),  # noqa: E501
    (673, 'eTTipStandAloneResearchFail', (0x45a91b,), 'Oh, well! The villager was unsuccessful at research. Drag the same villager to the table again.'),  # noqa: E501
    (674, 'eTTipStandAloneBreedFail', (0x458607, 0x45a5a8), "Too bad! They didn't get along or aren't in the mood. Try again with the same couple or try a different pair to see if love blossoms."),  # noqa: E501
    (675, 'eTTipStandAloneFirstPreg', (), "Congratulations! The stork brought a baby. Be careful! A mother cares for her child until age two and won't do much else."),  # noqa: E501
    (676, 'eTTipStandAloneHealFail', (0x457455,), 'Shoot! The villager is still sick. Drag the same villager onto the sick one again.'),  # noqa: E501
    (677, 'eTTipStandAloneFirstDeath', (0x45f48b,), "I'm sorry. One of your little villagers is dead. Villagers die of old age, but they can also die from disease and starvation. Buying medicine technology helps your villagers live longer and have fewer diseases."),  # noqa: E501
    (678, 'eTTipStandAloneMiniMap', (0x46c0b7,), "Welcome to the Overview Map. Enjoy a bird's-eye view of your village, then click anywhere on the map to zoom in to that spot."),  # noqa: E501
    (679, 'eTTipStandAloneRealTime', (), 'Virtual Villagers is a true real-time game. Your tribe continues to do what they have learned, even when the computer is off or you stop playing, but remember to check back often to care for your little villagers! Have fun!'),  # noqa: E501
    (680, 'eTTipStandAloneFinal', (0x468722,), 'You have mastered the basics! How you manage your tribe now is up to you! Decide wisely who will do what. Your villagers will slowly learn to do the tasks you show them. Once survival is no longer an issue, you can help them uncover the hidden secrets of Isola!'),  # noqa: E501
    (681, 'eTTipStandAloneConfused', (0x447bef,), 'Hmmm... this villager is confused. Sometimes villagers need more skill or more advanced technology before they understand what to do.'),  # noqa: E501
    (682, 'eTTipStandAloneSkillPref', (0x46e0db,), "Great! You set a villager's skill preference. From now on, they prefer this type of work and gain skill the more they practice."),  # noqa: E501
    (683, 'eTTipStandAloneChildrenNoWork', (0x4666fb,), "Nice try, but children don't work. They love to play and won't do what you ask until they grow up. They can still help out though, as they sometimes find delicious mushrooms or collectibles."),  # noqa: E501
    (684, 'eTTipStandAloneMommiesNoWork', (0x466739,), "Nursing mothers don't work while they are caring for an infant."),  # noqa: E501
    (687, 'eTipFirstTrainee', (), "Congratulations! One of your villager's reached the `Trainee` level in a skill category."),  # noqa: E501
    (688, 'eTipFirstAdept', (), "Congratulations! One of your villager's reached the `Adept` level in a skill category."),  # noqa: E501
    (689, 'eTipFoodOk', (0x42641d, 0x458f08, 0x459000, 0x459087), "Good job! Your villagers aren't worried about food anymore. Now you can focus on research and increasing the population of the village."),  # noqa: E501
    (690, 'eTipFirstAdult', (), 'One of the young children of your tribe is now old enough to work! Your tribe needs every able-bodied person to help out, so find that villager and keep everyone productive.'),  # noqa: E501
    (692, 'eTipFirstMaster', (0x4605ae,), 'One of your villagers is a master in a skill! This is a great accomplishment. Making any one villager a master in at least three skills grants that villager the prestigious title of Elder.'),  # noqa: E501
    (693, 'eTipFirstAlchemyFailure', (0x430c81,), 'A potion blew up while it was being brewed! This kind of dangerous accident becomes less common if you research alchemy tech.'),  # noqa: E501
    (694, 'eTipPopMilestoneSmall', (0x428d7a,), 'Congratulations! Your village reached its first population milestone of 15 people!'),  # noqa: E501
    (695, 'eTipPopMilestoneMed', (), 'Congratulations! Your village reached its second population milestone of 25 people!'),  # noqa: E501
    (696, 'eTipPopMilestoneLarge', (), 'Congratulations! Your village reached its third population milestone of 50 people!'),  # noqa: E501
    (697, 'eTipAbsPopCap', (), 'Congratulations! Your village reached its maximum sustainable population!'),
    (698, 'eTipNewRecipe', (), 'Your villagers found an interesting new recipe!'),
    (699, 'eTipYouLose', (0x428ced,), 'Alas, the fates were not kind to your village. All of your little villagers died. The island of Isola remains a myth and its mysteries unsolved.'),  # noqa: E501
    (700, 'eTipPuzzleBeehiveCleared', (0x431641,), 'The Bee Hive Your villagers have cleverly calmed the bees with smoke, so now they will be enjoying delicious honey!'),  # noqa: E501
    (701, 'eTipPuzzleAlchemyLabRestored', (0x42fb6e,), 'The Alchemy Lab Recovering all the scattered pieces, your villagers have restored what appears to have once been some kind of alchemy lab. By finding hidden herbs, they can now start creating interesting and potent potions!'),  # noqa: E501
    (702, 'eTipPuzzleRainLiftRestored', (0x435bd3,), 'The Lift Your villagers have succeeded in setting upright an ancient lift from the pre- cursors of this city. It is clearly designed to let them reach the tree high above on the cliff.'),  # noqa: E501
    (703, 'eTipPuzzleChiefCreated', (0x432009,), 'The First Chief The robe fits! The chosen one has been found. Your tribal chief does not actually work, but when set to a task, others nearby are more effective. The chief also has other powers, yet to be discovered.'),  # noqa: E501
    (704, 'eTipPuzzlePotionsMade', (), 'Potion Made need teeeeext Potion Made'),
    (705, 'eTipPuzzleAncientBathsRestored', (0x4315c6,), 'The Ancient Bath Your village builders have repaired an ancient bath, and the clean rains have filled it! What a wonderful place to meet, swim, and stay clean and fit!'),  # noqa: E501
    (706, 'eTipPuzzleOrchardStarted', (0x433fce,), 'The Orchard It must have been many years since the orchard has thrived and prospered on this part of the island. It will produce much food for the tribe.'),  # noqa: E501
    (707, 'eTipPuzzleRainDanceMastered', (0x436b8e,), 'Weather Dancing With your chief leading, your villagers have discovered that they can influence the weather.'),  # noqa: E501
    (708, 'eTipPuzzleDigRestored', (0x43641e,), 'The Ruins By digging and clearing, your builders have found a collapsed building and a concealed room. It seems to be an archiving room and, hopefully, will shed some light on the history of this mysterious island.'),  # noqa: E501
    (709, 'eTipPuzzlePrincessRestored', (0x435401,), 'The Statue This tremendous statue was too beautiful to leave broken, and your builders know no task too great. It appears to be in honor of a princess...'),  # noqa: E501
    (710, 'eTipPuzzleSharksCleared', (0x43651e,), 'The Sharks With a masterful mix of herbs, and the skill of your great alchemists, a way has been found to deal with the sharks, so that they will no longer bother your villagers. Let the fishing begin!'),  # noqa: E501
    (711, 'eTipPuzzleRosterDeadCleared', (0x43606e,), 'The Roster of the Dead Hidden behind vines and growth, your villagers have found a great plaque for recording the lives of those who have passed on.'),  # noqa: E501
    (712, 'eTipPuzzleTreeKeyFound', (), 'The Cliff Key Your villagers have found one of the keys to the strange door at the end of the cliff path.'),  # noqa: E501
    (713, 'eTipPuzzleAshKeyFound', (0x433426,), 'The Ash Key Your villagers have found one of the keys to the strange door amid the ashes of the fire.'),  # noqa: E501
    (714, 'eTipPuzzleClamKeyFound', (), 'The Clam Key Your villagers have found one of the keys to the strange door in the big clam in the ocean.'),  # noqa: E501
    (715, 'eTipPuzzleSundiskMastered', (0x4367de,), 'The Chief and the Princess Using the strange machine in the hidden antechamber, your villagers have somehow enabled communication with some of the original inhabitants of this part of the island! This is a great achievement, and your tribe stands in awe and wonder!'),  # noqa: E501
    (716, 'eTipPuzzleAromatherapyMastered', (0x4311fe,), 'Aromatherapy Your villagers have mastered aromatherapy, which reduces the chance of disease.'),  # noqa: E501
    (717, 'eTipPuzzleHut1Built', (), 'A New Hut! Your villagers have restored one of the broken huts! Your tribe can now support a larger population.'),  # noqa: E501
    (718, 'eTipPuzzleClothingHutBuilt', (0x432853,), 'The Clothing Hut Your villagers can now spend extra tech points to customize their outfits.'),  # noqa: E501
    (719, 'eTipPuzzleFireStarted', (), 'Fire! When a fire is burning, your villagers are happier and less vulnerable to disease.'),  # noqa: E501
    (720, 'eTipPuzzleTurtleShellCollectionComplete', (), 'Turtle Shell Collection Your children collected all of the different types of turtle shells found on Isola! Your village population maximum is increased by 5.'),  # noqa: E501
    (721, 'eTipPuzzleCoralCollectionComplete', (), 'Coral Collection Your children collected all of the different types of coral found on Isola! Your village population maximum is increased by 5.'),  # noqa: E501
    (722, 'eTipPuzzleTabletCollectionComplete', (), 'Tablet Collection Your children collected all of the different tablet pieces found on Isola! Your village population maximum is increased by 5.'),  # noqa: E501
    (723, 'eTipPuzzleFeatherCollectionComplete', (), 'Feather Collection Your children collected all of the different types of feathers found on Isola! Your village population maximum is increased by 5.'),  # noqa: E501
    (724, 'eTipPuzzleAllCollectionsComplete', (0x42e056,), 'All Collections Complete! Well done! Your children completed all four of the collections. In addition to keeping the collections, your village population maximum is increased by 5!'),  # noqa: E501
)
