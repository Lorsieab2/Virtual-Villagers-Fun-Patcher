"""A New Home (VV1): every hidden key, click, typed code and tip -- the Game Mechanics "Hidden keys, clicks and cheats"
group (src/vv_game_mechanics_hidden.py has the labels and the key path).

Read from the stock exe research/stock-executables/Virtual Villagers - A New Home.exe (the tests read the same file):
  * the event pump 0x403970 (Esc 1000 ... F10 1027, typed characters as characters; Alt+F4 sets the quit flag +0x1D);
  * the screens' input slots (vtable +8): the village 0x41FDF0 (vtable 0x4598B0, built by 0x4224A0, state 1 of the
    game's update 0x41B350), the help pictures 0x41E410, the Start / "?" screen 0x41F480, the Map 0x429B70, Puzzles and
    Milestones 0x42E420, the splash 0x431700, the Tech screen 0x435A60, the Villager Detail screen 0x449630, the Yes / No
    boxes 0x415400, the one-button boxes 0x4317E0, the name boxes 0x40BE30;
  * the village's mouse slot 0x424EF0 (the mask, the school drum, the places that show their state, 0x421B40 the
    message line), the tip queue 0x41C960 and the tutorial's next step 0x41C9A0.
KEY_HANDLERS gives each input slot's span and the keys it tests (the tests read them from the code); RANDOM_TIPS and
POPUP_TIPS quote every tip exactly (whitespace folded), each with the places that ask for it by number.
Read only: nothing here writes anything.
"""
from __future__ import annotations

import vv_game_mechanics as gm
import vv_game_mechanics_hidden as hidden
from vv_game_mechanics_hidden import C, CLICK, CODE, E, KEY, O, PATCHER, TIP, U, Entry

HIDDEN = "Hidden keys, clicks and cheats"
GAME = 1
PUMP = (0x403970, 0x403D00)
# Every input slot: start -> (end, the keys it tests: command numbers and typed characters).
KEY_HANDLERS = {
    0x40BE30: (0x40BF20, frozenset({1000, ord("-"), ord("0"), ord("9")})),
    0x415400: (0x415440, frozenset({1000, 1003})),
    0x41E410: (0x41E470, frozenset({1018, 1020})),
    0x41F480: (0x41F4E0, frozenset({1018, 1020})),
    0x41FDF0: (0x420060, frozenset({ord(c) for c in " DMPTdmpt"} | {1000, 1024, 1025})),
    0x429B70: (0x429BA0, frozenset({1000})),
    0x42E420: (0x42E4A0, frozenset({1000, 1018, 1020})),
    0x431700: (0x431730, frozenset({1018})),
    0x4317E0: (0x431810, frozenset({1000, 1003})),
    0x435A60: (0x435AB0, frozenset({1000, 1018})),
    0x449630: (0x449660, frozenset({1000})),
}
MASK = (171, 488, 221, 584)              # the village's mask: x from, y from, x to, y to (0x4224A0 +0x2C8..+0x2D4)
RANDOM_BASE, RANDOM_COUNT = 519, 30      # 0x424EF0: rand(30) + 519 (0x4256B0 push 0x1E)
TIP_QUEUE = 0x41C960
CHAINED = frozenset(range(264, 287, 2))  # queued by 0x41C9A0 as the tutorial's next step

# The store-like screens' slots, checked for any random draw (the tests read them): (start, end).
RAND = 0x402F10
STORE_SLOTS = ((0x434070, 0x434570), (0x435A60, 0x435AB0), (0x435AB0, 0x435E10))

STORY = "vv1_story_cheat_upgrades"
ORIGINS = "vv1_enable_origins_exclusive_features"
NUMBER_KEYS = "vv1_number_keys"
F6 = "vv1_f6_clothing_change_cheat"
SORT_BY = "vv1_sort_by"
PATCHES = (NUMBER_KEYS, F6, SORT_BY, ORIGINS, STORY)
DEFAULT_OFF = frozenset({STORY})


def _keys() -> list[Entry]:
    return [
        hidden.translator_entry(PUMP[0]),
        Entry(KEY, "Space (village screen)", (
            "pauses: the game's speed value goes up by 999 (0x41FDF0; the speed at state +0xA318), which stops the "
            "game's clock. Space again takes the 999 off and the game runs at the speed it had (a value of exactly 999 "
            "comes back as Normal), and clears the message line at the bottom of the screen"), C),
        Entry(KEY, "D, M, P, T and Esc (village screen)", (
            "the same as clicking the screen's own buttons: D the Detail button, M Map, P Puzzles, T Tech and Esc Menu "
            "(0x41FDF0 hands the button's number -- 4, 6, 7, 5 and 3 -- to the screen's button slot, as a click does). "
            "Capital and small letters work alike"), C),
        Entry(KEY, "F7 and F8 (village screen)", (
            "move the message line at the bottom of the screen (the text box at 496, 575) up by one pixel (F7) or down "
            "by one pixel (F8) a press, and nothing else (0x41FDF0 -> 0x40C420): a developer's layout key left in "
            "the game"), C),
        Entry(KEY, "F1 (the splash, the help pictures, the Start / \"?\" screen, Puzzles and Milestones, Tech)", (
            "jumps straight into the village (game state 1: 0x431700, 0x41E410, 0x41F480, 0x42E420, 0x435A60). There "
            "is no button for it. On the Start / \"?\" screen of a new village it also skips setting the village's "
            "start time (docs/known-behaviours-and-non-bugs.md, G10)"), C, subs=(
                ("Seen by the owner (2026-10-11): F1 pressed on the \"Lost at sea\" picture did nothing. Which "
                 "screen that picture belongs to was not settled, so the code and this observation are both kept.",
                 O),)),
        Entry(KEY, "F3 (the help pictures, the Start / \"?\" screen, Puzzles and Milestones)", (
            "flips one setting of the game's drawing object (its byte +0x1F, 0x408290) each press"), C, subs=(
                ("What the setting changes on screen (read on 2026-10-11 as the game's own pointer against the "
                 "Windows pointer) is not confirmed.", U),)),
        Entry(KEY, "Esc (Map, Puzzles and Milestones, Tech, Villager Detail)", (
            "the same as the screen's own way back (0x429B70, 0x42E420, 0x435A60, 0x449630)"), C),
        Entry(KEY, "Enter and Esc (pop-up boxes)", (
            "in a Yes / No box Enter is Yes and Esc is No (0x415400); in a one-button box either key closes it "
            "(0x4317E0)"), C),
        Entry(KEY, "Typing in a name box", (
            "a typed character from 32 to 255 is added (a number box takes only 0 to 9, and \"-\" as the first "
            "character), Backspace takes the last one off, and while the box is active it takes every key but Esc "
            "and does nothing with it (0x40BE30)"), C, subs=(
                ("DEAD (never runs): the box's own ending on a typed Enter or Tab character (13 or 9, 0x40B910): the "
                 "event pump never makes those characters, it hands Enter and Tab on as keys (0x403970).", C),)),
        Entry(KEY, "Tab, the arrows, Page Up, Page Down, Home, End, Insert, Delete, F2, F4, F5, F6, F9 and F10", (
            "no screen of A New Home reacts to them (no input slot tests them; the patcher's \"Reenable F6 Clothing "
            "Change Cheat\" adds F6, below)"), C),
        Entry(KEY, "Store screens: no redraw or reroll key", (
            "no key or click redraws, refreshes or rerolls what A New Home offers. Its Tech screen "
            "offers a fixed list at fixed prices; its input, mouse and button slots "
            "(0x434070, 0x435A60, 0x435AB0) draw no random number (0x402F10) and test only Esc and F1 (above)."
            ""
            " The patcher's Origins Upgrades, Villager Upgrades and Story / Cheat menus are Windows dialogs with "
            "no key handling of their own (native/ has no WM_KEYDOWN, WM_CHAR or key-state code), so only "
            "Windows' own dialog keys work there; their lists are fixed"), C),
    ]


def _codes() -> list[Entry]:
    return [
        Entry(CODE, "Typed codes and name cheats", (
            "none. Outside the name boxes a typed letter is a single key (above), and the name boxes only store what "
            "is typed (0x40BE30)"), C, subs=(
                ("The developer-leftover search of 2026-10-11 (static) also found no comparison of a typed name with "
                 "any fixed word, no command-line switch and no date-based event.", U),)),
    ]


def _clicks() -> list[Entry]:
    x0, y0, x1, y1 = MASK
    return [
        Entry(CLICK, "The mask (village screen)", (
            f"the spot from {x0} to {x1} across and {y0} to {y1} down on the 800 x 600 screen. Each press of the left "
            "button on it shows one of the 30 random tips (below) in the message line at the bottom of the screen: "
            f"rand(30) + {RANDOM_BASE}, each tip 1 in 30 a click, any tip can come again, nothing is remembered "
            "(0x424EF0, 0x4256B0; shown by 0x421B40). The first click in a village also queues the tutorial tip \"Click "
            "the mask to see helpful tips at the bottom of the screen.\" while it is still armed (+0x161, tip 304); "
            "after that each click also plays a sound (67)"), C, subs=(
                ("The message line's timer is set 5 real-life seconds on, in real time at every speed and also while "
                 "paused (0x421B40 sets +0x284 to 0x402F70 + 5; 0x402F70 counts real-life seconds since the program "
                 "started); that the line is cleared then is not traced.", U),
                ("Moving the mouse over the mask: each movement has an 11% chance (rand(100) <= 10) of starting two "
                 "of the game's short effects (type 4) at 168, 514 and 193, 505 (0x424EF0); what they look like is "
                 "not confirmed.", C),
                ("The patcher's \"Numeric Keys: Zip Around the Island\" adds a 31st tip to this mask (see Patcher).",
                 C))),
        Entry(CLICK, "The school drum (village)", (
            "once The School puzzle is complete (+0xA050), a click on the map spot 729 to 757 across and 888 to 936 down "
            "plays a sound (73) and sends every living child under 14 villager years to school (the drum lesson "
            "0x444AA0, sole caller 0x425505; docs/vv1-school-lessons-research.md)"), C),
        Entry(CLICK, "Places that show their state (village)", (
            "a click on the ground (not on a villager) at one of these places writes a line in the message line at "
            "the bottom of the screen (0x424EF0 -> 0x421B40, by the place's map area 0x414200)"), C, subs=(
                ("Area 3: \"Berries remaining:\" and the count (+0xA2F4).", C),
                ("Areas 4 and 16, while that work has begun and is not finished (+0x9FAC, +0x9FB0): \"Percentage of "
                 "blockage cleared:\" and its progress x 100 / 350.", C),
                ("Areas 5 and 21, the same way (+0x9FD4, +0x9FD8): \"Percentage carving progress:\" and its progress "
                 "x 100 / 1,350.", C),
                ("Area 6: \"Tech Points : \" and the tech points (+0xA2FC).", C),
                ("Area 11: \"Food available to villagers.: \" and the food (+0xA2EC).", C),
                ("Area 34, once its crops have been planted twice or more (+0xA2E4): \"Crops remaining:\" and the "
                 "crops, or with none left \"Minutes until new crops:\" and the real-life minutes to the next crop.",
                 C),
                ("Area 35, while it is being built (+0x9FDC, +0x9FE0): \"Percentage construction completed:\" and its "
                 "progress x 100 / 1,000; areas 39, 40 and 41: the same words, progress x 100 / 250, / 400 and / "
                 "600.", C),
                ("Area 15, where a dropped child shows \"Children can't swim!\": a sound (59) and a splash where it "
                 "was clicked, no line.", C),
                ("Which place on the map each area is was not drawn out; the messages name the work.", U))),
        Entry(CLICK, "The grid at the map spot 1,233 to 1,533 across and 200 to 350 down (village)", (
            "a click on a filled square of the 10-wide grid there plays a sound (72) and opens a box with a \"Done\" "
            "button (0x420060); what the grid is was not identified"), U),
    ]


def _tips() -> list[Entry]:
    return [
        Entry(TIP, "Where the tips appear", (
            "A New Home has two kinds: the 30 random tips, shown only by clicking the mask (above; there is no "
            "loading-screen tip: nothing else picks from them), and the tip pop-ups -- the tutorial and the milestone "
            "pop-ups -- which the game queues by number (0x41C960) and shows one at a time; up to 10 wait, and a tip "
            "asked for with the queue full is armed again for a later time (+0x31 + its number)"), C, subs=(
                ("A new village arms the tutorial tips (0x41C755); answering the help question \"Would you like HELP "
                 "the first time?\" one way switches them off (0x41ECB6; which button does it is not observed).", U),
                ("Each tutorial step's instruction is queued by 0x41C9A0 when the step before it is shown, while "
                 "that step is still armed: the tutorial runs in order, each tip once a village.", C))),
        Entry(TIP, f"The {RANDOM_COUNT} random tips (the mask)", "every one, as the game words it:", C,
              subs=hidden.tip_lines(RANDOM_TIPS, lambda tip: C, lambda tip: "")),
        Entry(TIP, f"The {len(POPUP_TIPS)} tip pop-ups (tutorial and milestones)", (
            "every one, as the game words it, with the places that ask for it by number (a tip with none is asked for "
            "by a number the game works out, which is not traced, and is labelled as not confirmed)"), C,
              subs=hidden.tip_lines(POPUP_TIPS, _popup_label, _popup_note)),
    ]


def _popup_label(tip) -> bool | str:
    return C if tip[2] or tip[0] in CHAINED else U


def _popup_note(tip) -> str:
    if tip[2]:
        return hidden.sites_note(tip[2])
    if tip[0] in CHAINED:
        return "queued by 0x41C9A0 as the tutorial's next step"
    return ""


def _patcher() -> list[Entry]:
    return [
        Entry(PATCHER, "Number keys 1 to 9 (village screen)", (
            "glide the view to nine spots laid out like a keypad (7 8 9 along the top, 4 5 6 in the middle, 1 2 3 "
            "along the bottom), a tenth of the remaining distance each update; another number changes course, "
            "dragging the map pulls against the glide while the button is held, letting go of the button (or any "
            "click) ends it, and opening another screen ends it. The top-row digits and, with Num Lock on, the keypad "
            "work (native/vv1_number_keys). It also adds the tip \"You can zip around the island with your numeric "
            "keys.\" as tip 549, and the mask then draws from 31 tips (0x4256B0: push 0x1E becomes push 0x1F)"), C,
              feature=NUMBER_KEYS, subs=(
                ("The tip comes only from the mask: A New Home's only random-tip picker is the mask click (0x4256B0 "
                 "is in the village's mouse slot 0x424EF0), and its loading screen (built by 0x41F650) shows only "
                 "\"Loading...\".", C),)),
        Entry(PATCHER, "F6 (village screen)", (
            "with a living villager selected, spends 5,000 tech points and puts that villager in the next outfit (0 to "
            "19, then 0 again); with fewer than 5,000 tech points or nobody selected nothing happens and nothing is "
            "charged (docs/vv1-f6-clothing-research.md)"), C, feature=F6),
        Entry(PATCHER, "Sort By (Villager Detail screen)", (
            "adds a Sort By band under the Age and Gender boxes with Age, Skill and Health; clicking one makes the left "
            "and right arrows walk the villagers in that order (Age is the default; native/vv1_sort_by)"), C,
              feature=SORT_BY),
        Entry(PATCHER, "Upgrades buttons (Tech and Villager Detail screens)", (
            "a click opens the Origins Upgrades menu (Tech screen) or the Villager Upgrades menu (Villager Detail); "
            "Esc closes either menu the same way as Cancel"), C, feature=ORIGINS, subs=(
                ("Esc closing both menus was run for real against the compiled menus "
                 "(tests/manual/runtime_test_vv1_esc_closes_upgrade_menus.c).", E),)),
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
    (519, 'Certain herbs on the island can be examined.'),
    (520, 'One male villager can father many children.'),
    (521, 'There are many useful spots to which you can drag villagers.'),
    (522, 'Children inherit some skill from their parents.'),
    (523, 'Medicine reduces disease and extends longevity.'),
    (524, 'Children can start working around age 14.'),
    (525, 'Pause the game if you go away for very long.'),
    (526, 'If your healer is sick, who is healing your villagers?'),
    (527, 'Sick or nursing villagers do not work.'),
    (528, 'Bored villagers tend to hang around the center of the village.'),
    (529, 'A villager prefers the skill preference you set.'),
    (530, 'Sometimes villagers stubbornly do what they want.'),
    (531, "Likes and dislikes can affect a villager's behavior."),
    (532, 'Isola is pronounced ee-zoh-lah!'),
    (533, 'Who inhabited Isola before your villagers?'),
    (534, 'Fish are the only unlimited food source.'),
    (535, 'Villagers can die of old age, disease or starvation.'),
    (536, 'M will go to the map. SPACE will toggle pause.'),
    (537, 'Adult villagers are naturally excellent swimmers.'),
    (538, "Time passes whether you're playing the game or not."),
    (539, 'Success at a task may require meeting key requirements first.'),
    (540, 'Reaching a milestone can benefit your villagers.'),
    (541, "Gently selecting villagers doesn't disrupt what they're doing."),
    (542, 'It can take several tries to teach something to a villager.'),
    (543, 'Safe and happy villagers attempt new things.'),
    (544, 'Master researchers generate more tech points than others.'),
    (545, "A villager's skill preference can be set on the Detail Screen."),
    (546, 'Your village can grow to a huge population.'),
    (547, 'Building more huts supports a larger population.'),
    (548, 'Sick villagers tend to hang around the well.'),
)
POPUP_TIPS = (
    (262, '', (0x423afb,), "Let's explore the island... Click and hold the mouse button anywhere on the ground and drag the mouse to move around the village."),  # noqa: E501
    (263, '', (0x423b75,), 'Good! This is how you move about the island. Feel free to explore your little village.'),
    (264, '', (), "Let's get to know one of the villagers... Find and click a villager to select them."),
    (265, '', (0x425412,), 'Perfect! A white circle shows which villager is selected. See important details about this villager, like their name, at the bottom of the screen.'),  # noqa: E501
    (266, '', (), "Let's move a villager... Click and hold the mouse button on a villager and drag the mouse to move them."),  # noqa: E501
    (267, '', (0x423bf8,), 'Excellent! Moving villagers influences their behavior. Drag and drop villagers anywhere you like to help them explore useful or interesting places in the village.'),  # noqa: E501
    (268, '', (), "Let's teach a villager to forage... Drag a villager to the large berry bush and drop them on it."),
    (269, '', (0x43d512,), 'Wow! Your villager gathered a bowl of fresh berries. They also improved at foraging and will continue to forage on their own.'),  # noqa: E501
    (270, '', (), "Let's teach a villager to research... Drag a little villager to the large table at the center of the village."),  # noqa: E501
    (271, '', (0x43d987,), 'Great! This villager is learning to research. As research skills improve, you gain tech points that can be spent like money on new technologies.'),  # noqa: E501
    (272, '', (), "Let's check out the Technologies screen... Click the 'Tech' button on the left side of the screen."),
    (273, '', (0x435a08,), "Welcome to the Technologies screen. Use your tech points gained from research to buy any of the six different technologies. Click a '?' to learn more about a technology."),  # noqa: E501
    (274, '', (), "Let's encourage the villagers to clean the well. Find a villager who has building skills and drag them to the well."),  # noqa: E501
    (275, '', (), "Congratulations! You solved the island's first puzzle! Your villagers now have plenty of clean water and want to celebrate this achievement!"),  # noqa: E501
    (276, '', (), "Let's check out the Puzzles and Milestones screen. Click the 'Puzzles' button on the left side of the screen."),  # noqa: E501
    (277, '', (0x42e3d4,), "Welcome to the Puzzles and Milestones screen. The island is full of puzzles and hidden secrets waiting to be discovered. Your goal is to solve Isola's sixteen puzzles while helping your tribe survive."),  # noqa: E501
    (278, '', (), "Let's make some babies... Drag a male villager onto a female villager or vice versa."),
    (279, '', (0x43dca1,), 'Good! They get along and want to go indoors for some privacy. With any luck, the stork may bring a new baby.'),  # noqa: E501
    (280, '', (0x42ed70,), "Oh no! One of your little villagers is sick. Let's train a healer. Find the sick villager then drag a second villager onto the sick one."),  # noqa: E501
    (281, '', (0x43cf28,), 'Wonderful! The sick villager is better. Your healer also gained healing skill, which is essential for your villagers to lead long and healthy lives.'),  # noqa: E501
    (282, '', (), "Let's learn more about a villager... Click the 'Detail' button on the bottom of the screen."),
    (283, '', (0x44a69d,), 'Welcome to the Detail screen. Learn more about each villager, such as age, health, and skills. Check the box to the right of a skill to set a skill preference.'),  # noqa: E501
    (284, '', (), "Let's encourage new building skills... Drag a builder to the hut they are building."),
    (285, '', (0x4247f3, 0x424866, 0x424ccc), 'Excellent! Dragging a skilled builder to another spot in the village encourages progress. New structures allow a larger population, and many other things.'),  # noqa: E501
    (286, '', (), 'Children can actually help out the village. Their keen eyes can spot rare mushrooms that others might miss. Drag a child to this mushroom. Hurry, though, because mushrooms wilt quickly!'),  # noqa: E501
    (287, '', (0x4251bd,), 'The child has recovered a rare and delicious mushroom and is sharing it with the tribe! It is just another way for you to help your tribe to thrive.'),  # noqa: E501
    (288, '', (0x423ad9,), 'Welcome to Virtual Villagers! Your little villagers landed on the shores of a beautiful and mysterious island called Isola. Some basic structures, most likely built by previous islanders, already exist. Your villagers are scared and disoriented, so they need your help and guidance to survive and thrive in their new home.'),  # noqa: E501
    (289, '', (), 'Almost! Click and hold the mouse button anywhere on the ground and drag the mouse to move around the village.'),  # noqa: E501
    (290, '', (0x42471f, 0x42477d), "Good! Let's wait while the villager tries to forage. If they succeed they will gather some berries."),  # noqa: E501
    (291, '', (0x43d4e5,), "Darn! The villager didn't gather any berries. Sometimes it takes a few tries, so drag the same villager to the berry bush again."),  # noqa: E501
    (292, '', (0x424b09,), "Good! Let's give the villager a moment to research. If they succeed, you earn tech points."),  # noqa: E501
    (293, '', (0x43d8ff,), 'Oh well! The villager was unsuccessful at research. Drag the same villager to the table again.'),  # noqa: E501
    (294, '', (0x424d84,), 'Yuck! The well is still dirty. A trainee builder is more likely to succeed. Let me help you find a builder with this skill level.'),  # noqa: E501
    (295, '', (0x43d648, 0x43ddb5), "Too bad! They didn't get along or aren't in the mood. Try again with the same couple or try a different pair to see if love blossoms."),  # noqa: E501
    (296, '', (0x4482da,), "Congratulations! The stork brought a baby. But be careful! A mother cares for her child until age two and won't do much else."),  # noqa: E501
    (297, '', (0x43cfc2,), 'Shoot! The villager is still sick. Drag the same villager onto the sick one again.'),
    (298, '', (0x42ea05,), "I'm sorry. One of your little villagers is dead. Villagers die of old age, but they can also die from disease and starvation. Buying medicine technology helps your villagers live longer and have fewer diseases."),  # noqa: E501
    (299, '', (0x42a395,), "Welcome to the Overview Map. Enjoy a bird's-eye view of your village, then click anywhere on the map to zoom in to that spot."),  # noqa: E501
    (300, '', (0x4237ae,), 'Virtual Villagers is a true, real-time game. Your tribe continues to do what they have learned even when the computer is off or you stop playing, but remember to check back often to care for your little villagers!'),  # noqa: E501
    (301, '', (), 'You have mastered the basics! How you manage your tribe now is up to you! Decide wisely who will do what. Your villagers will slowly learn to do what you show them to do. Once survival is no longer a problem, you can help them to uncover the hidden secrets of Isola!'),  # noqa: E501
    (302, '', (0x440068,), 'Hmmm... this villager is confused. Sometimes villagers need more skill or more advanced technology before they understand what to do.'),  # noqa: E501
    (303, '', (0x44981d,), "Great! You set a villager's skill preference. From now on, they prefer this type of work and gain skill the more they practice."),  # noqa: E501
    (304, '', (0x42569f,), 'Click the mask to see helpful tips at the bottom of the screen.'),
    (305, '', (0x4251f5,), "Nice try, but children don't work. They love to play and won't do what you ask until they grow up. They can still help out though, as they sometimes find delicious mushrooms."),  # noqa: E501
    (308, '', (), "Congratulations! One of your villager's reached the `Trainee` level in a skill category."),
    (309, '', (), "Congratulations! One of your villager's reached the `Adept` level in a skill category."),
    (310, '', (), "Congratulations! One of your villager's reached the `Master` level in a skill category."),
    (311, '', (0x43ade2, 0x43af03, 0x43af7a, 0x43afc4, 0x43b02d), 'Good job! Your villagers aren`t worried about food anymore. Now you can focus on research and increasing the population of the village.'),  # noqa: E501
    (312, '', (0x42f28b,), 'Congratulations! Your village reached its first population milestone of 15 people!'),
    (313, '', (), 'Congratulations! Your village reached its second population milestone of 25 people!'),
    (314, '', (), 'Congratulations! Your village reached its third population milestone of 50 people!'),
    (315, '', (), 'Congratulations! Your village reached its maximum sustainable population!'),
    (316, '', (0x42f2b8,), 'Oh no! The berry bush is nearly depleted. It`s time your villagers think about new food sources.'),  # noqa: E501
    (317, '', (0x42f1c6,), 'Alas, the fates were not kind to your village. All of your little villagers died. The island of Isola remains a myth and its mysteries unsolved.'),  # noqa: E501
    (318, '', (0x43ac4f,), "The Cave The magical Golden Child moved the giant boulder and opened the cave! Maybe more clues about Isola's mysteries are waiting to be found inside..."),  # noqa: E501
    (319, '', (0x43a355,), 'The Magic Fish of Fertility Your master fisherman found a strange, sparkling fish deep in the lagoon. This delicious and rare fish is the Fish of Fertility. Your tribe now enjoys greater success at breeding!'),  # noqa: E501
    (320, '', (0x4132ca,), 'The Magic Plant of Life The butterflies pollinated the strange and rare plant of life, which now bears fruit! Your villagers live longer than ever now!'),  # noqa: E501
    (321, '', (0x43b1bd,), 'The Lagoon Your builders removed the creek blockage! The water now flows freely providing a pristine, pure stream. The waters of this lagoon may be the key to more than one mystery for your villagers.'),  # noqa: E501
    (322, '', (0x43abab,), 'The Beach Your builders cleared away the debris and smashed boat pieces from the beach. The ocean is much more accessible now.'),  # noqa: E501
    (323, '', (0x43b282,), 'The Garden The pure creek waters restored the magical garden! Your villagers are astounded by its beauty. The stunning beauty of these flowers is uplifting to all of your villagers!'),  # noqa: E501
    (324, '', (), 'The Treasure Using advanced building techniques and scientific methods of detection, one of your villagers uncovered a buried treasure!'),  # noqa: E501
    (325, '', (0x43a680,), 'The Idol Through divine inspiration, your builders carved a large idol out of the sparkling, strange rock. It`s as if the idol was always there, just waiting to be revealed.'),  # noqa: E501
    (326, '', (0x43a426,), "Herb Mastery After thoroughly investigating Isola's indigenous herbs, your villagers have mastered their healing powers. Your healers are more effective than ever!"),  # noqa: E501
    (327, '', (0x43b44a,), 'The Temple Inspired by their spirituality, your builders successfully restored the ancient ruins that have mystified them since their arrival. They`re certain this is how the stone temple once looked in the distant past...'),  # noqa: E501
    (328, '', (0x43a848, 0x43a959, 0x43aa8c), 'The Hut Your builders constructed a new hut! Your village can support a larger population now.'),  # noqa: E501
    (329, '', (0x424596,), 'The Cemetery Using their enhanced spirituality, your villagers designed an appropriate resting place for elders and others who have passed on to the next life.'),  # noqa: E501
    (330, '', (0x4242e3,), 'The Golden Child A miracle! One of your villagers gave birth to a special, golden child! No one can doubt or deny his powers! Behold the Golden Child!'),  # noqa: E501
    (331, '', (0x43a740,), 'The School One of your master scientists founded a school! Children will now be born with more skills.'),  # noqa: E501
    (332, '', (0x43a56c,), 'The Butterflies The Golden Child called forth a group of beautiful butterflies to grace the new garden!'),  # noqa: E501
    (333, '', (0x43ae9c,), 'The Well Your builder removed the cover from the well and now your tribe has fresh, clean water!'),  # noqa: E501
)
