"""The Lost Children (VV2): every hidden key, click, typed code and tip -- the Game Mechanics "Hidden keys, clicks and
cheats" group (src/vv_game_mechanics_hidden.py has the labels and the key path).

Read from the stock exe research/stock-executables/Virtual Villagers - The Lost Children.exe:
  * the event pump 0x403C00; the game's update 0x423D70 (state at +0x30470: 1 the village, built by 0x42D2A0);
  * the screens' input slots: the village 0x429E70, Collections 0x418130, the help pictures 0x427C00, the intro pages
    0x427DC0 / 0x428400 / 0x429430, the end screen 0x426E50, Puzzles and Milestones 0x43B100, the splash 0x43F360, the
    Tech screen 0x443770, the Map 0x436200, Villager Detail 0x465AF0, the boxes 0x4144A0 / 0x41AB80, the name boxes
    0x40C810;
  * the village's mouse slot 0x4308D0 (the mask, the places that show their state; 0x42C230 the message line), the
    loading screen 0x429530, the tip pop-ups 0x4257A0.
Read only.
"""
from __future__ import annotations

import vv_game_mechanics as gm
import vv_game_mechanics_hidden as hidden
from vv_game_mechanics_hidden import C, CLICK, CODE, KEY, PATCHER, TIP, U, Entry

HIDDEN = "Hidden keys, clicks and cheats"
GAME = 2
PUMP = (0x403C00, 0x403F90)
KEY_HANDLERS = {
    0x40C810: (0x40C900, frozenset({1000, ord("-"), ord("0"), ord("9")})),
    0x4144A0: (0x4144D0, frozenset({1000, 1003})),
    0x418130: (0x4181B0, frozenset({1000, 1018, 1020})),
    0x41AB80: (0x41ABC0, frozenset({1000, 1003})),
    0x426E50: (0x426E80, frozenset()),
    0x427C00: (0x427C60, frozenset({1018, 1020})),
    0x427DC0: (0x427DF0, frozenset()),
    0x428400: (0x428430, frozenset()),
    0x429430: (0x429490, frozenset({1018, 1020})),
    0x429E70: (0x42A170, frozenset({ord(c) for c in " 123456789CDMPTcdmpt"} | {1000})),
    0x436200: (0x436230, frozenset({1000})),
    0x43B100: (0x43B180, frozenset({1000, 1018, 1020})),
    0x43F360: (0x43F430, frozenset({1018})),
    0x443770: (0x4437C0, frozenset({1000, 1018})),
    0x465AF0: (0x465B20, frozenset({1000})),
}
MASK = (171, 488, 221, 584)              # 0x42D2A0 +0x218..+0x224
RANDOM_BASE, RANDOM_COUNT = 742, 50
LOADING_COUNT = 30                       # 0x429530: rand(30) + 742
TIP_QUEUE = 0x4257A0
# The number keys' spots (0x429E70: the glide target +0x230/+0x234).
SPOTS = {1: (-150, 1200), 2: (300, 1200), 3: (850, 1200), 4: (-150, 500), 5: (300, 570), 6: (850, 500),
         7: (-150, 0), 8: (300, 0), 9: (850, 0)}

# The store-like screens' slots, checked for any random draw (the tests read them): (start, end).
RAND = 0x4031A0
STORE_SLOTS = ((0x441D80, 0x442280), (0x443770, 0x4437C0), (0x4437C0, 0x443AD0))

STORY = "vv2_story_cheat_upgrades"
ORIGINS = "vv2_enable_origins_exclusive_features"
TIP_WORDING = "vv2_numeric_keys_tip_wording"
PATCHES = (TIP_WORDING, ORIGINS, STORY)
DEFAULT_OFF = frozenset({STORY})


def _keys() -> list[Entry]:
    spots = "; ".join(f"{key} {x}, {y}" for key, (x, y) in SPOTS.items())
    return [
        hidden.translator_entry(PUMP[0]),
        Entry(KEY, "Space (village screen)", (
            "pauses: the game's speed value goes up by 999 (0x429E70; the speed at state +0x2EB08), which stops the "
            "game's clock. Space again takes the 999 off and the game runs at the speed it had (a value of exactly 999 "
            "comes back as Normal), and clears the message line"), C),
        Entry(KEY, "1 to 9 (village screen)", (
            "glide the view to nine spots laid out like a keypad (7 8 9 along the top, 1 2 3 along the bottom): the "
            "key sets the glide target (0x429E70) and the village's update moves a tenth of the remaining distance "
            f"each update (0x42F814; native/vv1_number_keys has the trace). The spots: {spots}. Another number "
            "changes course; letting go of a map drag, or a screen button that leaves the village, ends the glide"),
              C),
        Entry(KEY, "C, D, M, P, T and Esc (village screen)", (
            "the same as clicking the screen's own buttons: C Collections, D Detail, M Map, P Puzzles, T Tech and Esc "
            "Menu (0x429E70 hands the button's number -- 9, 4, 6, 7, 5 and 3 -- to the screen's button slot). Capital "
            "and small letters work alike"), C),
        Entry(KEY, "F1 (Collections, the help pictures, the intro pages, Puzzles and Milestones, the splash, Tech)", (
            "jumps straight into the village (game state 1: 0x418130, 0x427C00, 0x429430, 0x43B100, 0x43F360, "
            "0x443770). There is no button for it"), C),
        Entry(KEY, "F3 (Collections, the help pictures, the intro page 0x429430, Puzzles and Milestones)", (
            "flips one setting of the game's drawing object each press (0x408520)"), C, subs=(
                ("What the setting changes on screen is not confirmed.", U),)),
        Entry(KEY, "Esc (Collections, Map, Puzzles and Milestones, Tech, Villager Detail)", (
            "the same as the screen's own way back (0x418130, 0x436200, 0x43B100, 0x443770, 0x465AF0)"), C),
        Entry(KEY, "Any typed character (the splash pictures)", (
            "shows the next splash picture, and after the last one moves on to game state 25 (0x43F360). Esc and the "
            "other keys that are not characters do not"), C),
        Entry(KEY, "Any typed character (the intro pages and the gamewin_bg.jpg screen)", (
            "sets the page's timer to one step past the clock 0x403200 and marks the page done (0x427DC0, 0x428400, "
            "0x426E50)"), C, subs=(("That this turns the page at once is not traced.", U),)),
        Entry(KEY, "Enter and Esc (pop-up boxes)", (
            "in a two-button box Enter is the first button and Esc the second (0x41AB80); in a one-button box either "
            "key closes it (0x4144A0)"), C),
        Entry(KEY, "Typing in a name box", (
            "a typed character from 32 to 255 is added (a number box takes only 0 to 9, and \"-\" first), Backspace "
            "takes the last one off, and while the box is active it takes every key but Esc and does nothing with it "
            "(0x40C810)"), C, subs=(
                ("DEAD (never runs): the box's own ending on a typed Enter or Tab character (13 or 9): the event pump "
                 "never makes those characters (0x403C00).", C),)),
        Entry(KEY, "Tab, the arrows, Page Up, Page Down, Home, End, Insert, Delete, F2, F4, F5 to F10", (
            "no screen of The Lost Children reacts to them (no input slot tests them)"), C),
        Entry(KEY, "Store screens: no redraw or reroll key", (
            "no key or click redraws, refreshes or rerolls what The Lost Children offers. Its Tech screen "
            "offers a fixed list at fixed prices; its input, mouse and button slots "
            "(0x441D80, 0x443770, 0x4437C0) draw no random number (0x4031A0) and test only Esc and F1 (above)."
            ""
            " The patcher's Origins Upgrades, Villager Upgrades and Story / Cheat menus are Windows dialogs with "
            "no key handling of their own (native/ has no WM_KEYDOWN, WM_CHAR or key-state code), so only "
            "Windows' own dialog keys work there; their lists are fixed"), C),
    ]


def _codes() -> list[Entry]:
    return [
        Entry(CODE, "Typed codes and name cheats", (
            "none. Outside the name boxes a typed letter is a single key (above), and the name boxes only store what "
            "is typed (0x40C810)"), C, subs=(
                ("The developer-leftover search of 2026-10-11 (static) also found no comparison of a typed name with "
                 "any fixed word, no command-line switch and no date-based event.", U),)),
    ]


def _clicks() -> list[Entry]:
    x0, y0, x1, y1 = MASK
    return [
        Entry(CLICK, "The mask (village screen)", (
            f"the spot from {x0} to {x1} across and {y0} to {y1} down on the 800 x 600 screen. Each press of the left "
            f"button on it plays a sound (73) and shows one of all {RANDOM_COUNT} random tips (below) in the message "
            f"line: rand({RANDOM_COUNT}) + {RANDOM_BASE}, each tip 1 in {RANDOM_COUNT} a click, any tip can come again, "
            "nothing is remembered (0x4308D0; shown by 0x42C230)"), C, subs=(
                ("Moving the mouse over the mask: each movement has an 11% chance (rand(100) <= 10) of starting two "
                 "of the game's short effects (type 4) at 168, 514 and 193, 505 (0x4308D0); what they look like is "
                 "not confirmed.", C),
                ("The tutorial tip \"Click the mask to see helpful tips at the bottom of the screen.\" (438) is in "
                 "the game; where it is asked for is not traced.", U))),
        Entry(CLICK, "Places that show their state (village)", (
            "a click on the ground (not on a villager) at one of these places writes a line in the message line "
            "(0x4308D0 -> 0x42C230, by the place's map area 0x4181D0)"), C, subs=(
                ("Area 3: \"Coconut resource remaining:\".", C),
                ("Area 6: \"Tech Points\".", C),
                ("Area 9: \"Food available to villagers\".", C),
                ("Areas 10 and 55, 11 and 56, 12 and 57, 13 and 58, 59 and 31, each until its work is done: "
                 "\"Percentage construction completed:\".", C),
                ("Areas 16 and 60, until done: \"Percentage repair completed:\".", C),
                ("Areas 18 and 64, once begun and until done: \"Percentage of thorns cleared:\".", C),
                ("Areas 19 and 61: \"Hours remaining for fire:\".", C),
                ("Areas 20 and 70, once begun and until done: \"Percentage vines removed:\".", C),
                ("Area 49, once crops are growing: \"Crops remaining:\".", C),
                ("Area 65, once begun and until done: \"Percentage restoration completed:\".", C),
                ("Area 21, once the Gong of Wonder is whole (+0x2E7F0): opens the screen of game state 21 (0x426EB0, "
                 "the picture gamewin_bg.jpg).", C),
                ("Areas 24 and 25: a sound (65) and a splash where it was clicked, no line.", C),
                ("Which figure follows each line, and which place on the map each area is, are not traced.", U))),
    ]


def _tips() -> list[Entry]:
    return [
        Entry(TIP, "Where the tips appear", (
            f"the loading screen shows one of the first {LOADING_COUNT} random tips, picked once when it is built "
            f"(0x429530: rand({LOADING_COUNT}) + {RANDOM_BASE}, each 1 in {LOADING_COUNT}); the mask shows any of all "
            f"{RANDOM_COUNT} (above); the tutorial and milestone pop-ups are asked for by number (0x4257A0)"), C, subs=(
                ("So tips 31 to 50, among them \"You can zip around the island with your keypad.\" (786), come only "
                 "from the mask.", C),
                ("A new village asks \"Would you like tutorial tips turned on?\"; how the answer arms the pop-ups, and "
                 "whether each shows once a village, is not traced.", U))),
        Entry(TIP, f"The {RANDOM_COUNT} random tips (the loading screen draws from the first {LOADING_COUNT}, the "
                   "mask from all)", "every one, as the game words it:", C,
              subs=hidden.tip_lines(RANDOM_TIPS, lambda tip: C,
                                    lambda tip: "" if tip[0] < RANDOM_BASE + LOADING_COUNT else "the mask only")),
        Entry(TIP, f"The {len(POPUP_TIPS)} tip pop-ups (tutorial and milestones)", (
            "every one, as the game words it, with the places that ask for it by number (a tip with none is asked for "
            "by a number the game works out, which is not traced: UNCONFIRMED)"), C,
              subs=hidden.tip_lines(POPUP_TIPS, lambda tip: C if tip[2] else U,
                                    lambda tip: hidden.sites_note(tip[2]))),
    ]


def _patcher() -> list[Entry]:
    return [
        Entry(PATCHER, "Tip 786 (the mask)", (
            "rewords \"You can zip around the island with your keypad.\" to \"You can zip around the island with "
            "your numeric keys.\"; the keys themselves are the game's own (above)"), C, feature=TIP_WORDING, subs=(
                ("The patch's description calls it a loading-screen tip; it is tip 45 of 50, which the loading "
                 "screen (1 to 30) never picks, so it comes from the mask.", C),)),
        Entry(PATCHER, "Upgrades buttons (Tech and Villager Detail screens)", (
            "a click opens the Origins Upgrades menu (Tech screen) or the Villager Upgrades menu (Villager Detail)"),
              C, feature=ORIGINS, subs=(("Esc closing these menus is tested only in A New Home.", U),)),
        Entry(PATCHER, "Story / Cheat menus (in the Origins Upgrades menu)", (
            "adds Pick Island Event, Custom Island Event, Pick Gong of Wonder Outcome and Choose Time Skip Amount, and "
            "makes every Origins Upgrade cost 0 tech points"), C, feature=STORY),
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
    (742, 'Certain herbs on the island can be examined.'),
    (743, 'One male villager can father many children.'),
    (744, 'There are many useful spots to which you can drag villagers.'),
    (745, 'Children inherit some skill from their parents.'),
    (746, 'Medicine reduces disease and extends longevity.'),
    (747, 'Children can start working around age 14.'),
    (748, 'Pause the game if you go away for very long.'),
    (749, 'If your healer is sick, who is healing your villagers?'),
    (750, 'Sick or nursing villagers do not work.'),
    (751, 'Bored villagers tend to hang around the center of the village.'),
    (752, 'A villager prefers the skill type you set.'),
    (753, 'Sometimes villagers stubbornly do what they want.'),
    (754, "Likes and dislikes can affect a villager's behavior."),
    (755, 'Isola is pronounced ee-zoh-lah!'),
    (756, 'Who inhabited Isola before your villagers?'),
    (757, 'Unlimited fishing is available in unpolluted waters.'),
    (758, 'Villagers can die of old age, disease, or starvation.'),
    (759, 'M displays the map. SPACE toggles pause on and off.'),
    (760, 'Adult villagers are naturally excellent swimmers.'),
    (761, "Time passes whether you're playing the game or not."),
    (762, 'Success at a task may require meeting key requirements first.'),
    (763, 'Reaching a milestone can benefit your villagers.'),
    (764, "Gently selecting villagers doesn't disrupt what they're doing."),
    (765, 'It can take several tries to teach something to a villager.'),
    (766, 'Safe and happy villagers attempt new things.'),
    (767, 'Master scientists generate more tech points than others.'),
    (768, "A villager's skill preference can be set on the Detail Screen."),
    (769, 'Your village can grow to a large population.'),
    (770, 'Building more huts supports a larger population.'),
    (771, 'Sick villagers tend to hang around the fire.'),
    (772, 'If your hand gets tired, give it a rest!'),
    (773, 'Researching culture helps kids get a head start.'),
    (774, 'Where did the parents go?'),
    (775, 'Fire assists researchers.'),
    (776, 'Research can be hazardous for your villagers.'),
    (777, 'Skills can be trained with various tasks.'),
    (778, "Add wood to your fire so that you don't have to relight it."),
    (779, 'Duplicate collectibles are turned into tech points.'),
    (780, 'Having children pick up collectibles is optional.'),
    (781, 'Keep a fire burning to reduce disease.'),
    (782, 'Medicine improves fertility.'),
    (783, 'Different combinations of herbs make different stews.'),
    (784, 'Different stews have different effects on villagers.'),
    (785, 'Sick villagers tend to hang around the fire.'),
    (786, 'You can zip around the island with your keypad.'),
    (787, 'Children will tend to look like their parents.'),
    (788, 'Older villagers start to slow down.'),
    (789, 'A master in several skills becomes an elder.'),
    (790, "Likes and dislikes can affect a villager's behavior."),
    (791, 'Different combinations of herbs make different stews.'),
)
POPUP_TIPS = (
    (391, '', (0x42f236,), "Let's explore the area... click and hold the mouse button anywhere on the ground and drag the mouse to move around the village."),  # noqa: E501
    (392, '', (0x42f2b0,), 'Good! This is how you move about the island. Feel free to explore your little village.'),
    (393, '', (), "Let's get to know one of the villagers... find and click a villager to select them."),
    (394, '', (0x4310bc,), 'Perfect! A white circle shows which villager is selected. See important details about this villager, like their name, at the bottom of the screen.'),  # noqa: E501
    (395, '', (), "Let's move a villager... click and hold the mouse button on a villager and drag the mouse to move them."),  # noqa: E501
    (396, '', (0x42f333,), 'Excellent! Moving villagers influences their behavior. Drag and drop villagers anywhere you like to help them explore useful or interesting places in the village.'),  # noqa: E501
    (397, '', (), "Let's teach a villager to fish... the children are getting hungry and there isn`t much food. Drag an adult villager to the ocean and drop them in."),  # noqa: E501
    (398, '', (0x44e272,), 'Wow! Your villager caught a fish! This villager improved at fishing and will continue to fish on their own.'),  # noqa: E501
    (399, '', (), "Let's teach a villager to research... drag an adult villager to the large table at the center of the village."),  # noqa: E501
    (400, '', (0x44e7e3,), 'Great! This villager is learning to research. As research skills improve, you gain tech points that can be spent like money on new technologies.'),  # noqa: E501
    (401, '', (), "Let's check out the Technologies screen... click the 'Tech' button on the left side of the screen."),
    (402, '', (0x443718,), "Welcome to the Technologies screen. Use your tech points gained from research to buy any of the six different technologies. Click a '?' to learn more about a technology."),  # noqa: E501
    (403, '', (), "The children could get cold without some heat. Let's teach a villager to build a fire. First, drag an adult villager to this pile of driftwood so they can gather wood."),  # noqa: E501
    (404, '', (0x4624b7,), 'Well done. There is a stack of dry firewood in the fire pit.'),
    (405, '', (), 'Kindling is also needed to start a fire. Now drag your villager to this patch of dry reeds.'),
    (406, '', (0x461f10,), 'Good. Your villager put the kindling in the fire pit.'),
    (407, '', (), 'With dry firewood and kindling, all that`s necessary to start the fire is to drag a villager to the fire pit.'),  # noqa: E501
    (408, '', (0x46257c,), 'Well done! You completed your first puzzle! Your tribe can now enjoy the benefits of a hot, crackling fire on those chilly nights.'),  # noqa: E501
    (409, '', (), "Let's check out the Puzzles and Milestones screen. Click the 'Puzzles' button on the left side of the screen."),  # noqa: E501
    (410, '', (0x43b0a4,), "Welcome to the Puzzles and Milestones screen. The island is full of puzzles and hidden secrets waiting to be discovered. Your goal is to solve Isola's sixteen puzzles while helping your tribe survive."),  # noqa: E501
    (411, '', (), "Let's make some babies... drag an adult male villager onto an adult female villager or vice versa. Note that dragging an adult to a child causes the adult to educate the child."),  # noqa: E501
    (412, '', (0x44f812,), 'Good! They get along and want to go indoors for some privacy. With any luck, the stork may bring a new baby.'),  # noqa: E501
    (413, '', (), "Children can also contribute to village life. Their keen eyes can spot mushrooms and small collectibles that adults might overlook. Drag a child to this shell before it disappears. Don't worry, though, collecting items is optional."),  # noqa: E501
    (414, '', (0x4634a7,), 'Ooooh, the child found a collectible! Your villagers can collect Isola`s small and beautiful treasures, but only when found by a child. The same collectible found more than once is converted into tech points.'),  # noqa: E501
    (415, '', (), "Let's check out the Collections screen. Click the 'Collections' button on the left side of the screen."),  # noqa: E501
    (416, '', (0x417c94,), 'Welcome to the Collections screen. Here you can see which collectibles your village children gathered. You can also check your progress on rebuilding the Gong of Wonder.'),  # noqa: E501
    (417, '', (), "Let's encourage new building skills... drag a builder to the hut they are building."),
    (418, '', (0x430201,), 'Excellent! Dragging a skilled builder to another spot in the village encourages progress. New structures allow a larger population, and many other things.'),  # noqa: E501
    (419, '', (0x43bc09,), "Oh no! One of your little villagers is sick. Let's train a healer. Find the sick villager then drag a second villager onto the sick one."),  # noqa: E501
    (420, '', (0x44da58,), 'Wonderful! The sick villager is better. Your healer also gained healing skill, which is essential for your villagers to lead long and healthy lives.'),  # noqa: E501
    (421, '', (), "Let's learn more about a villager... click the 'Detail' button on the bottom of the screen."),
    (422, '', (0x4676c2,), 'Welcome to the Detail Screen. Learn more about each villager, such as age, health and skills. Check the box to the right of a skill to set a skill preference.'),  # noqa: E501
    (423, '', (0x42f214,), 'Welcome to Virtual Villagers: The Lost Children! After their frightening fall down the waterfall, the two curious villagers find themselves trapped in a new part of Isola. The children here are low on food, scared, and need help to survive. One of them is old enough to help work.'),  # noqa: E501
    (424, '', (), 'Almost! Click and hold the mouse button anywhere on the ground and drag the mouse to move around the village.'),  # noqa: E501
    (425, '', (0x42fba4,), "Good! Let's wait while the villager fishes. If they succeed, they will put the fish in the food bin near the center of the village."),  # noqa: E501
    (426, '', (), "Darn! The villager didn't catch a fish. Sometimes it takes a few tries, so drag the same villager to another spot in the ocean."),  # noqa: E501
    (427, '', (0x4306cb, 0x43070d), "Good! Let's give the villager a moment to research. If they succeed, you earn tech points."),  # noqa: E501
    (428, '', (0x44e741,), 'Oh well! The villager was unsuccessful at research. Drag the same villager to the table again.'),  # noqa: E501
    (429, '', (0x44e3f7, 0x44f951), "Too bad! They didn't get along or aren't in the mood. Try again with the same couple or try a different pair to see if love blossoms."),  # noqa: E501
    (430, '', (0x46190e,), "Congratulations! The stork brought a baby. Be careful! A mother cares for her child until age two and won't do much else."),  # noqa: E501
    (431, '', (0x44daf2,), 'Shoot! The villager is still sick. Drag the same villager onto the sick one again.'),
    (432, '', (0x43b7d9,), "I'm sorry. One of your little villagers is dead. Villagers die of old age, but they can also die from disease and starvation. Buying medicine technology helps your villagers live longer and have fewer diseases."),  # noqa: E501
    (433, '', (0x436a25,), "Welcome to the Overview Map. Enjoy a bird's-eye view of your village, then click anywhere on the map to zoom in to that spot."),  # noqa: E501
    (434, '', (0x42eebe,), 'Virtual Villagers is a true, real-time game. Your tribe continues to do what they have learned even when the computer is off or you stop playing, but remember to check back often to care for your little villagers! Have fun!'),  # noqa: E501
    (435, '', (), 'You have mastered the basics! How you manage your tribe now is up to you! Decide wisely who will do what. Your villagers will slowly learn to do what you show them to do. Once survival is no longer an issue, you can help them uncover the hidden secrets of Isola!'),  # noqa: E501
    (436, '', (0x4545b8,), 'Hmmm... this villager is confused. Sometimes villagers need more skill or more advanced technology before they understand what to do.'),  # noqa: E501
    (437, '', (0x465ced,), "Great! You set a villager's skill preference. From now on, they prefer this type of work and gain skill the more they practice."),  # noqa: E501
    (438, '', (), 'Click the mask to see helpful tips at the bottom of the screen.'),
    (439, '', (0x430e03,), "Nice try, but children don't work. They love to play and won't do what you ask until they grow up. They can still help out though, as they sometimes find delicious mushrooms or collectibles."),  # noqa: E501
    (442, '', (), "Congratulations! One of your villager's reached the `Trainee` level in a skill category."),
    (443, '', (), "Congratulations! One of your villager's reached the `Adept` level in a skill category."),
    (444, '', (0x4631ed, 0x4632a6, 0x46334f, 0x463399, 0x463402), 'Good job! Your villagers aren`t worried about food anymore. Now you can focus on research and increasing the population of the village.'),  # noqa: E501
    (445, '', (0x43c08b,), 'One of the young children of your tribe is now old enough to work! Your tribe needs every able-bodied person to help out, so find that villager and keep everyone productive.'),  # noqa: E501
    (447, '', (0x42ff4d,), 'The Ancient Writings Realizing the markings behind the vines are some kind of writing, and using their advanced cultural knowledge, your villagers translate the symbols written on the wall: "The Gong of Wonder has been dismantled, its pieces hidden or given to the ocean, never again to be whole. They insisted it was an artifact for good only, but we cannot allow it to exist. It must be banished along with the other artifacts." Then written more recently is this: "We are sure now that someone is practicing magic again and even restoring artifacts! We will find them at once. We are leaving the children under the guard of Tofo alone. We leave tomorrow."'),  # noqa: E501
    (448, '', (0x461b87,), "You struck the Gong of Wonder! There's no telling what it might do each time it is sounded. But it takes about a full day before its power is rejuvenated."),  # noqa: E501
    (449, '', (0x43c04d,), 'One of your villagers is a master in a skill! This is a great accomplishment. Remember that making any one villager a master in at least three skills makes that villager a wise villager ELDER.'),  # noqa: E501
    (450, '', (0x44fa07,), 'One of the children remembered something! On the day they disappeared, the adults were hiding pieces of something and then left to find something else. One adult remained behind to watch the children, but what became of that guardian is unclear.'),  # noqa: E501
    (451, '', (0x43c1e7,), 'Congratulations! Your village reached its first population milestone of 15 people!'),
    (452, '', (), 'Congratulations! Your village reached its second population milestone of 25 people!'),
    (453, '', (), 'Congratulations! Your village reached its third population milestone of 50 people!'),
    (454, '', (), 'Congratulations! Your village reached its maximum sustainable population!'),
    (455, '', (0x4260c9,), 'Your villagers found an interesting new recipe!'),
    (456, '', (0x43c21e,), "Oh no! The coconuts are nearly depleted. It's time your villagers think about new food sources. There is a promising patch of soil, but they need to find a way to irrigate it before they can grow food there."),  # noqa: E501
    (457, '', (0x43c110,), 'Alas, the fates were not kind to your village. All of your little villagers died. The island of Isola remains a myth and its mysteries unsolved.'),  # noqa: E501
    (458, '', (0x425af5, 0x43ba67), 'Oh my! Birds found your field and are relentlessly eating the young crops before your villagers can harvest them!'),  # noqa: E501
    (459, '', (0x462b8f,), 'The Lovely Hut Your builders restored and decorated one of the huts built by the previous inhabitants. Its remote location by the shore gives it a special charm.'),  # noqa: E501
    (460, '', (0x462682,), 'Fire A villager discovered how to make fire! Crackling and warm, this foundation of life and progress provides comfort, health, and technological advantage... as long as your villagers can keep it burning.'),  # noqa: E501
    (461, '', (0x46247b,), 'The Scarecrow To ward off the flocks of hungry birds, a farmer fashioned a spooky scarecrow out of some twisted and gnarled sticks. Those pesky birds should keep their distance now!'),  # noqa: E501
    (462, '', (0x44d216,), "The Elder Totem Your villagers erected a handsome totem commemorating the skills mastery of a village Elder. The Elder's wisdom and influence will be remembered for many generations."),  # noqa: E501
    (463, '', (0x46303a,), "The Hospital Your village builders and healers collaborated to build a hospital! Not only is it a place for the infirm, it has also advanced medical research. Your villagers now heal faster and won't get sick as often."),  # noqa: E501
    (464, '', (0x4628a5,), "Herb Mastery After thorough investigation of the local flora, your villagers mastered the use of Isola's indigenous herbs. Not only are healing powers improved, the variety of cooking herbs is increased."),  # noqa: E501
    (465, '', (0x46313d,), 'The Sewing Hut Desperate for new clothes, your researchers developed new clothing materials! Now you can drag a villager to the sewing hut to purchase a new outfit at a cost of 5000 tech points.'),  # noqa: E501
    (466, '', (0x464282,), 'The Dam Your engineers harnessed the power of nature by building a dam and redirecting the overflow of fresh stream water to a patch of fertile soil. As a result, your villagers can farm now! The dam also drained the southeast flats and will prevent further flooding in that area.'),  # noqa: E501
    (467, '', (0x461ff4,), 'The Cutting Tool Your scientists fashioned a new tool! Stout branches combined with naturally sharp stone tips, found by experienced eyes, combine to make an effective tool for cutting down fierce vegetation.'),  # noqa: E501
    (468, '', (0x42609a,), 'The Stew Through mastery of the island herbs and a desire to eat something warm and filling, your villagers learned to make a delicious, hot stew! With different ingredients, maybe they can create different stews...'),  # noqa: E501
    (469, '', (0x464106,), 'The Vine Wall Now that your tribe extensively researched culture, they can read the writing on this ancient wall.'),  # noqa: E501
    (470, '', (0x462a6f,), 'The Ancient Mosaic Being the skilled explorers, engineers, and culturists they are, your villagers expertly restored the ancient mosaic. It was probably the floor of an important building, judging by its intricate beauty.'),  # noqa: E501
    (471, '', (0x463ebe,), 'The Boxed Gong Piece Using their combined ingenuity and skill, your master builders pried open the expertly sealed crate that washed ashore and taunted them since its arrival. After struggling with it for some time, the box yielded to reveal a piece of the Gong of Wonder!'),  # noqa: E501
    (472, '', (0x463b91,), "The Sunken Gong Piece With the aid of a special breathing stew, a villager was able to hold their breath long enough to explore the depths of the lagoon. Long after disappearing, the villager resurfaced with a sunken object seen glinting far below. It's a piece of the Gong of Wonder!"),  # noqa: E501
    (473, '', (0x4639a6,), 'The Overgrown Gong Piece Clearing the briars, your villagers discovered the real purpose of this strange statue... to house a giant gong! The section of gong found in the thorny undergrowth is now positioned in the statue where it seems to belong.'),  # noqa: E501
    (474, '', (0x463d0d,), "The Inlaid Gong Piece Several villagers moved the Elder totem onto the ancient mosaic and discovered that one of the inlaid pieces is not from the original mosaic after all. It's a piece of the Gong of Wonder!"),  # noqa: E501
    (475, '', (0x463a1f, 0x463bf0, 0x463d6c, 0x463f1d), 'The Gong of Wonder Your tribe restored the Gong of Wonder! An artifact of ancient tribes whose purpose remains unclear. Anyone may strike it to initiate the reverberating tone and unleash its unknown potential.'),  # noqa: E501
    (476, '', (0x462789,), 'Sustainable Fishing Your scientists confirmed that over fishing of algae-eating fish caused excessive algae growth in the ocean. By introducing a special fish from the diving pool, your tribe restored the natural balance and clean state of the ocean!'),  # noqa: E501
    (477, '', (0x462cc6, 0x462dec, 0x462f28), 'The Hut Your builders constructed a new hut! Your village can support a larger population now.'),  # noqa: E501
    (478, '', (0x4634e0,), 'Butterfly Collection Your children collected all of the different types of butterflies found on Isola! Your village population maximum is increased by 5.'),  # noqa: E501
    (479, '', (0x46351a,), 'Shell Collection Your children collected all of the different types of shells found on Isola! Your village population maximum is increased by 5.'),  # noqa: E501
    (480, '', (0x463554,), 'Beetle Collection Your children collected all of the different types of beetles found on Isola! Your village population maximum is increased by 5.'),  # noqa: E501
    (481, '', (0x46358e,), 'Pebble Collection Your children collected all of the different types of pebbles found on Isola! Your village population maximum is increased by 5.'),  # noqa: E501
    (482, '', (0x46360e,), 'All Collections Complete! Well done! Your children completed all four of the collections. In addition to keeping the collections, your village population maximum is increased by 10!'),  # noqa: E501
)
