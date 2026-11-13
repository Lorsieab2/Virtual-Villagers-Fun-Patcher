"""The Aspiring Adventurer: the owner's island event (2026-11-12), all five games -- its words and its odds.

The one source of the event's English: scripts/build_more_island_events.py writes it into the companion
(native/vvfp_more_island_events/adv_text.inc) and into the translation template
(data/translations/patcher_strings.json), and the Game Mechanics pages read the odds below.

The owner's text, with only the pronoun fixes the owner was shown: (he/she), (his/her), (him/her), (He/she) follow
the adventurer's sex; in endings A4 and A6 the stranger's (man/woman) and (his/her) follow the stranger's own sex,
drawn at random.  (Name) is the adventurer, (Name2) the friend of ending A8.  Game effects (the owner's bracketed
notes) are never shown.

Each piece is written in two forms, one for a male and one for a female adventurer (the stranger's sentence: one
for a male and one for a female stranger), with the names as %s, in the order they appear; each form is its own
translation row, so a translation never has to guess a pronoun.

TOKENS in TEXTS:  {n} the adventurer's name   {f} the friend's name
                  {he} {He} {his} {His} {him}  the adventurer's pronouns ({she} forms are made from these)
                  {man} {shis}                 the stranger's word and pronoun (STRANGER only)
"""
from __future__ import annotations

import re

STEM = "vvfp.more_island_events/adv_text"
CONTEXT = "VVFP More Island Events.dll (the island event The Aspiring Adventurer: its popups, in the game's own island-event popup)"

TITLE = "The Aspiring Adventurer"

# (key, template).  Order is the C table's order (adv_text.inc ADV_*).
TEXTS: tuple[tuple[str, str], ...] = (
    ("TITLE", TITLE),
    ("INTRO_1", "{n} is an aspiring adventurer. Every morning {he} goes off in the jungle to scavenge for useful "
                "things. Although {n} has an eye for treasure, sometimes {his} ambition gets the best of {him}. {n} "
                "has managed to escape from sticky situations so far, but the others have cautioned {him} "
                "repeatedly about exploring alone."),
    ("INTRO_2", "During {his} travels, {he} sees something glinting in the corner of {his} eye. {n} feels "
                "compelled to see what it is, but is unsure whether to leave the known-safe path in order to "
                "investigate."),
    ("LABEL_A", "Go investigate!"),
    ("LABEL_B", "Stay on the safe path"),
    ("A_OPEN", "Against {his} better judgement, {n} leaves the beaten path to check out the strange sight. As {he} "
               "pushes through the foliage, the area gets noticeably darker and colder. The hairs on {n}'s neck "
               "stand on end as {he} gets closer to the spot. When {n} approaches, {he} finds..."),
    ("FIND_1", "nothing but a pile of dirt."),
    ("FIND_2", "a large stack of meat, sitting perfectly on a cloth! {n}'s stomach growls upon seeing the bounty, "
               "and {he} hastily grabs as much as {he} can and starts stuffing it in {his} knapsack."),
    ("FIND_3", "a large golden chest full of artifacts! {n}'s eyes widen at the sight, and {he} stuffs as much "
               "treasure as {he} can fit in {his} knapsack."),
    ("A1", "{n} waits for a while, and seeing no one else around, concludes that {he} can get away safely. {He} "
           "triumphantly goes back to the village and raves about {his} latest discovery, to the joy of the "
           "villagers."),
    ("TRAP", "As {n} turns to leave, {he} unexpectedly steps into a trap! Now panicking, {he} struggles with all "
             "{his} might to break free, causing a big ruckus. {He} hears something coming, and braces for the "
             "worst..."),
    ("BEAST", "The last thing {n} sees is the wide toothy grin of a large beast, and the terror of {his} face "
              "reflected in its eyes."),
    ("A2_END", "Later on, some hunters come to check on the trap, and see the unfortunate aftermath. They manage to "
               "recover {n}'s remains and return them to the village. The villagers mourn for {n} greatly and "
               "lament that things had to turn out this way."),
    ("A3_END", "Later on, some hunters come to check on the trap, and see the unfortunate aftermath. They try to "
               "recover {n}'s remains, but are unsuccessful. They bring the sad news to the village along with "
               "their condolences. The villagers mourn for {n} greatly and lament that things had to turn out this "
               "way."),
    ("STRANGER", "The last thing {n} sees is a strange {man} brandishing a knife with a wide grin on {shis} face..."),
    ("A4_END", "After several days, the villagers get worried about {n} and send out a search party. Eventually, "
               "they find the grisly scene, and manage to recover {his} remains. For 3 days the village mourns "
               "{n}'s death as they lay {him} to rest. They vow never to let something like this happen again."),
    ("A5_END", "Miraculously, {n} manages to escape the trap, and quickly runs back to the safety of the village. "
               "Heart pounding, {he} frantically warns others about {his} misadventure, to the relief of all the "
               "villagers. {n} vows to never do something like that EVER again!"),
    ("A6_END", "After several days, the villagers get worried about {n} and send out a search party. Although they "
               "try their hardest, they cannot find any trace of {him}. For 3 days the village mourns {n}'s "
               "disappearance and vow to never let something like this happen again."),
    ("A7", "{n} is disappointed that {he} wasted {his} time, and manages to make it back to the village safely."),
    ("A9", "{n} laughs at the pitiable sight and walks back to the village with a smile. {He} will definitely have a "
           "funny story to tell over dinner."),
    ("A8_END", "Luckily, it's just one of {his} old friends! Apparently, they got worried, and brought extra "
               "supplies to help {n} out... Together {n} and {f} return to the safety of the village, to the "
               "relief of all the villagers. {n} thanks {f} for saving {his} life and vows to never do something "
               "like that EVER again!"),
    ("AWARD_FOOD", "Your villagers gain %d food."),
    ("AWARD_TECH", "Your villagers gain %d tech points."),
    ("B_OPEN", "{n} decides it's far too dangerous to leave the safety of the path..."),
    ("B_HOME", "And manages to make it home safely."),
    ("B_LOST", "And starts heading home. Unfortunately, something goes horribly wrong and {he} gets hopelessly "
               "lost in the jungle. Days pass with no sign of {n}..."),
    ("L1", "...until a scout spots {n} wandering disoriented. {He} is heavily injured, and is quickly brought to "
           "the healers..."),
    ("H1", "Although they try everything in their power to save {n}, {he} quietly passes away, to the grief of all "
           "the villagers. In the end, they can only speculate about what happened to poor {n}, and forbid anyone "
           "from ever going out in the jungle alone again."),
    ("H2", "After many medical procedures, {n} eventually makes a full recovery. {n} recounts {his} harrowing "
           "misadventure to the worried villagers, and {he} vows never to make that mistake again. The villagers "
           "are relieved that {n} has managed to survive {his} ordeal and embrace {him} tightly."),
    ("H3", "After many medical procedures, {n} manages to recover, although is left permanently disabled. {n} "
           "recounts {his} harrowing misadventure to the worried villagers, and {he} vows never to make that "
           "mistake again. The villagers are relieved that {n} has managed to survive {his} ordeal and embrace "
           "{him} tightly."),
    ("L2_OTHER", "...until a scout spots {n} walking about. {n} seems to have joined another tribe. {He} seems no "
                 "worse for the wear, so the scout goes back to report their findings to the tribe."),
    ("L2_HEATHENS", "...until a scout spots {n} walking about. {n} is seen wearing a mask and seems to have joined "
                    "the heathens' tribe. {He} seems no worse for the wear, so the scout goes back to report their "
                    "findings to the tribe."),
    ("L2_ISOLANS", "...until a scout spots {n} walking about. {n} is seen wearing a mask and seems to have joined "
                   "the Isolans' tribe. {He} seems no worse for the wear, so the scout goes back to report their "
                   "findings to the tribe."),
    ("L3", "...until a scout spots {n} walking about. {n} notices the scout and returns home with them, to the "
           "great relief of the villagers. {He} recounts {his} misadventure to the worried villagers, who learn that "
           "{he} got lost in the dark. Luckily, {n} was prepared and managed to survive. {n} is proving to be a "
           "great survivalist, and now teaches others the art of bushcraft!"),
    ("L4", "...until a scout spots {n}'s remains under a fallen tree. In the end, the villagers can only speculate "
           "about what happened to poor {n}, and forbid anyone from ever going out in the jungle alone again."),
    ("L5", "...until a scout spots {n}'s remains at the bottom of a stony cliff. In the end, the villagers can only "
           "speculate about what happened to poor {n}, and forbid anyone from ever going out in the jungle alone "
           "again."),
    ("L6", "...and {he} is never seen again. In the end, the villagers can only speculate about what happened to "
           "poor {n}, and forbid anyone from ever going out in the jungle alone again."),
)

PRONOUNS = {
    "m": {"he": "he", "He": "He", "his": "his", "His": "His", "him": "him"},
    "f": {"he": "she", "He": "She", "his": "her", "His": "Her", "him": "her"},
}
STRANGER = {"m": {"man": "man", "shis": "his"}, "f": {"man": "woman", "shis": "her"}}


def forms(key: str) -> tuple[str, ...]:
    """The forms a piece has: ("",) when it holds no pronoun, else ("m", "f")."""
    template = dict(TEXTS)[key]
    return ("m", "f") if re.search(r"\{(he|He|his|His|him|man|shis)\}", template) else ("",)


def english(key: str, form: str) -> str:
    """Piece `key` in form `form` ("m", "f" or ""), with %s for each name in order."""
    template = dict(TEXTS)[key]
    words = dict(STRANGER[form]) if key == "STRANGER" and form else dict(PRONOUNS.get(form, PRONOUNS["m"]))
    words["n"] = "%s"
    words["f"] = "%s"
    return re.sub(r"\{(\w+)\}", lambda m: words[m.group(1)], template)


def names_in(key: str) -> tuple[str, ...]:
    """The names a piece's %s stand for, in order: "n" the adventurer, "f" the friend."""
    return tuple(re.findall(r"\{(n|f)\}", dict(TEXTS)[key]))


def stem(key: str, form: str) -> str:
    return f"{STEM}.{key}" + (f".{form}" if form else "")


def rows() -> list[tuple[str, str, str, tuple[str, ...]]]:
    """Every (stem, key, English, names) the companion asks the translations for."""
    out = []
    for key, _ in TEXTS:
        for form in forms(key):
            out.append((stem(key, form), key, english(key, form), names_in(key)))
    return out


def fill(key: str, form: str, name: str, friend: str = "", award: int = 0) -> str:
    """The English of a piece with the names (and %d) put in, as the companion fills it."""
    text = english(key, form)
    for who in names_in(key):
        text = text.replace("%s", name if who == "n" else friend, 1)
    return text.replace("%d", str(award))


# ---- The odds (the owner's, 2026-11-12) --------------------------------------------------------------------------

FIND_ODDS = {"nothing": 50, "meat": 25, "chest": 25}                 # percent, Choice A's find
SURVIVE_PERCENT = 50                                                  # Choice A: a surviving ending, else a deadly one
SURVIVING_WITH_FIND = ("A1", "A5", "A8")                              # equal; A8 needs a friend (else A5)
SURVIVING_NOTHING = ("A7", "A9")                                      # equal
DEADLY = ("A2", "A3", "A4", "A6")                                     # equal
LOST_PERCENT = 10                                                     # Choice B: lost, else home safe
LOST_ENDINGS = ("L1", "L2", "L3", "L4", "L5", "L6")                   # equal
HEALERS = ("H1", "H2", "H3")                                          # equal, after L1
INJURED_HEALTH = (10, 50)                                             # inclusive
SKILL_GAIN = (20, 30)                                                 # inclusive (the owner, 2026-11-12)
ADULT_YEARS = 14

# ---- The reward (the owner, 2026-11-12: "a random tech and food point award, scaling") --------------------------
#
# A NORMAL award is a random amount, each equally likely, from the smallest to the largest food (or tech-point) gain
# the game's own stock island events give, taken at the game's own base amount (A New Home's strength n, The Lost
# Children's k and The Secret City's m all at 1): the game's own scaling -- or "Island Events Scale" when ticked --
# is then applied to it exactly as before (adv_game.award_amount).  A LARGE award is twice a normal one, a HUGE award
# three times (The Cave Explorers).  The Aspiring Adventurer's meat and chest give a normal award in every game.
# Patch-added events (Restore Missing Island Events) and the Gong of Wonder (no island event) are left out.  Read from
# the Game Mechanics island-event catalogs (src/vv_game_mechanics_events_vvN.py, each read from the stock executable)
# and the Island Events Scale site table (scripts/build_island_events_scale_features.py); the companion has the same
# numbers (adv_vv1.inc, adv_vv2.inc, adv_vv345.inc: each adv_game's food / tech range):
AWARD_RANGES: dict[int, dict[str, tuple[int, int]]] = {
    # A New Home: food 200 The Greedy Little Monkey (200 x n) .. 1,500 the wooden crate at strength 3; tech 500 the
    # badly weathered crate at strength 1 .. 4,999 The Brass Compass (rand(3000) + 2000, 0x41A367).
    1: {"food": (200, 1500), "tech": (500, 4999)},
    # The Lost Children: food 100 For The Birds (100 x k) .. 1,500 the thick, plastic sack at strength 3; tech 500
    # the somewhat compromised sack at strength 1 .. 3,000 The Spyglass and the carefully sealed sack at strength 3.
    2: {"food": (100, 1500), "tech": (500, 3000)},
    # The Secret City: food 200 The Bitter Brown Beans' taste, The Mango and the Papaya's mango, The Shooting Star
    # (m x 200) .. 600 the beans' brew; tech 1,000 the beans' taste and The Return of Biggles .. 2,000 The
    # Mysterious Fog and the beans' brew.
    3: {"food": (200, 600), "tech": (1000, 2000)},
    # The Tree of Life: food 300 The Mysterious Footprints and The Arc of Brilliant Colors (its only food gains);
    # tech 500 The Mosquito Larvae (0x415A74) .. 5,000 The Sealed Box (0x415D7F).
    4: {"food": (300, 300), "tech": (500, 5000)},
    # New Believers: food 50 Mushroom Day! (rand(50) + 50, 0x415110) .. 300 The Mysterious Footprints; tech 500
    # You're Doing It Wrong! (0x4160A5) .. 3,000 Trick Or Trade (0x416692).
    5: {"food": (50, 300), "tech": (500, 3000)},
}
AWARD_SIZES = {"normal": 1, "large": 2, "huge": 3}


def award_range(game: int, kind: str, size: str = "normal") -> tuple[int, int]:
    """The base amounts an award can be (inclusive), before the game's own scaling / Island Events Scale."""
    lo, hi = AWARD_RANGES[game][kind]
    return lo * AWARD_SIZES[size], hi * AWARD_SIZES[size]


def award_words(game: int, kind: str, size: str = "normal") -> str:
    """'200 to 1,500 food' / '300 food' -- the base amounts in plain words."""
    lo, hi = award_range(game, kind, size)
    unit = "food" if kind == "food" else "tech points"
    return f"{lo:,} {unit}" if lo == hi else f"{lo:,} to {hi:,} {unit}"


# What each ending does (never shown).
EFFECTS = {
    "A1": "award", "A5": "award", "A8": "award", "A7": "none", "A9": "none",
    "A2": "dies", "A4": "dies", "A3": "disappears", "A6": "disappears",
    "HOME": "none", "H1": "dies", "H2": "none", "H3": "injured", "L2": "joins", "L3": "skill",
    "L4": "dies", "L5": "dies", "L6": "disappears",
}


def outcome_chances(friend: bool = True) -> dict[str, dict[str, float]]:
    """Each ending's chance (percent), out of every time the player picks that choice."""
    a: dict[str, float] = {}
    for find, p in FIND_ODDS.items():
        surviving = SURVIVING_NOTHING if find == "nothing" else SURVIVING_WITH_FIND
        for e in surviving:
            share = p * SURVIVE_PERCENT / 100 / len(surviving)
            if e == "A8" and not friend:
                e = "A5"
            a[e] = a.get(e, 0.0) + share
        for e in DEADLY:
            a[e] = a.get(e, 0.0) + p * (100 - SURVIVE_PERCENT) / 100 / len(DEADLY)
    b: dict[str, float] = {"HOME": 100.0 - LOST_PERCENT}
    for e in LOST_ENDINGS:
        share = LOST_PERCENT / len(LOST_ENDINGS)
        if e == "L1":
            for h in HEALERS:
                b[h] = share / len(HEALERS)
        else:
            b[e] = share
    return {"A": a, "B": b}
