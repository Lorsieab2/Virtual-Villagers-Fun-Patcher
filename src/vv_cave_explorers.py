"""The Cave Explorers: the owner's island event for A New Home (2026-11-12) -- its words and its odds.

The one source of the event's English: scripts/build_more_island_events.py writes it into the companion
(native/vvfp_more_island_events/cave_text.inc) and into the translation template
(data/translations/patcher_strings.json), and the Game Mechanics page reads the odds below.

THE OWNER'S TEXT, as pasted in chat (2026-11-12), unaltered but for what the owner's own notes and the builder's brief
asked for:
  * the notes in parentheses ("(go to A or B)", "(10%)", "(nothing happens)", "(the villagers disappear)", ...) are
    instructions, never shown;
  * the broken placeholders "(name1 and (name2)" and "(name1 and name2)" are "(name1) and (name2)";
  * (name1) / (name2) are the two villagers' names; (He/she), (his/her), (him/her) follow the villager the sentence
    is about (each token below names whose); "(random name between 1 and 2)" is drawn once for each use the text
    gives it (the screamer of A, the finder of B, the one who slips in the chasm), "(other name)" the other one;
    "(name)" in "whatever (name) encountered" is the screamer; "(Other name)" in the argument is name2 (name1 is the
    one stammering);
  * typography the game's font cannot draw is written in the letters it can (A New Home's font holds only A-Z, a-z,
    0-9 and ! " ' , . ? / ` : - and the space -- src/vv_font_glyphs.py): curly quotes as " and ', the dash as -,
    the ellipsis as ...; doubled spaces as one;
  * a pronoun opening a sentence is capitalised ("(he/she) tries to take some" after a full stop);
  * "When they return home" runs on into the ending that follows it ("then either:") with a comma.

Each piece is written in one form per sex of each villager whose pronouns it uses (1, 2 or 4 forms), with the names as
%s in the order they appear and an amount as %d; each form is its own translation row, so a translation never has to
guess a pronoun.

TOKENS:  {a} name1   {b} name2   {s} the screamer (A)   {o} the other one   {r} the finder (B)
         {c} the one who slips into the chasm   {d} the other one
         {he.X} {He.X} {his.X} {him.X}   that villager's pronouns (X one of the letters above)
"""
from __future__ import annotations

import re

STEM = "vvfp.more_island_events/cave_text"
CONTEXT = ("VVFP More Island Events.dll (the island event The Cave Explorers, A New Home: its popups, in the game's own "
           "island-event popup)")

TITLE = "The Cave Explorers"
GAME = 1

# (key, template).  Order is the C table's order (cave_text.inc CAVE_*).
TEXTS: tuple[tuple[str, str], ...] = (
    ("TITLE", TITLE),
    ("INTRO", "{a} has been curious about the cave. {He.a} wonders why the other villagers have not explored it more "
              "thoroughly, and speculates that there must be more to it than meets the eye. {a} is trying to convince "
              "{b}, {his.a} good friend, to come with {him.a}. {b} is also curious, but is not sure whether to sneak "
              "off from work to go spelunking. \"We'll be safer if we're together. Come on, it'll be fun!\", says "
              "{a}. \"So, what do you say?\""),
    ("LABEL_EXPLORE", "Explore the Cave"),
    ("LABEL_DONT", "Don't explore"),
    ("DONT", "\"Sorry, I'm not going,\" says {b}. \"What if we get lost? What if people discover we're gone? We'll get "
             "in trouble. I don't want to risk getting hurt. And neither should you,\" {he.b} says. \"Please "
             "reconsider. Let the tribe handle this and maybe we can tag along later.\" {a} is saddened, but realizes "
             "that {b} is right. After much reflection, {he.a} thanks {him.b} for setting their mind straight. \"I "
             "may not always have my best interests in mind, but I'm glad to have such a good friend looking out for "
             "me!\" {a} and {b} may not always get along, but one thing's for certain: their bond is stronger than "
             "ever."),
    ("EXPLORE_1", "\"Okay, let's go!\" {b} says. {a} and {b} pack up their supplies and steal away to the cave in "
                  "secret. By torchlight, they see intricate drawings depicting the island's history painted on the "
                  "walls, and numerous artifacts scattered around the area. \"Fascinating!\" {b} says. \"I never "
                  "thought I'd see such beautiful things!\""),
    ("EXPLORE_2", "\"Toldja it'd be worth it,\" says {a}, beaming. {He.a} asks {b} if they should head in further to "
                  "see if any more things can be found."),
    ("LABEL_PROCEED", "Proceed Further"),
    ("LABEL_STAY", "Stay Here"),
    ("DEEPER", "The two head in deeper. The place becomes darker and narrower until only a small sliver of light "
               "remains."),
    # B
    ("B_SEARCH", "The two trek on, searching high and low for anything they can find. After a while with no luck, {r} "
                 "finds something buried in the ground. Wow! It's"),
    ("FIND_MAP", "a map! {a} and {b} follow the map to a strange place that was previously unknown by the villagers. "
                 "No one knows where they went, but they left a note saying they were 'alive and well' along with a "
                 "drawing of their whereabouts. 'I hope you'll come and follow us someday,' the note says. 'You'll "
                 "love it here. - {a} and {b}'"),
    ("FIND_COINS", "a sack of gold coins! {a} and {b} haul the heavy sack back home to the delight of the villagers. "
                   "Your village gains %d tech points."),
    ("FIND_TREASURE", "a treasure map! {a} and {b} follow the map to the X marked on the ground, where they dig up a "
                      "large chest full of jewels and gold! They drag the chest all the way back home to the utter "
                      "delight of the villagers. Your villagers gain %d of tech points."),
    ("FIND_FOOD", "a sack of preserved food! {a} and {b} haul the large sack back to the village, to the delight of "
                  "the villagers. Your villagers gain %d food."),
    # A
    ("A_SCREAM", "Suddenly {s} screams. {He.s} tries to run to {o}, but they can't see each other, and their torches "
                 "have all burned out. All they can hear is their voices echoing throughout the chamber, and some "
                 "loud, ominous stomping. \"What's wrong?!\" says {o}."),
    ("WRONG_1", "\"I stepped on something slimy!\""),
    ("WRONG_2", "\"I felt something scratch me!\""),
    ("WRONG_3", "\"I ran into something sticky!\""),
    ("WRONG_4", "\"I heard something growling!\""),
    ("RUN", "\"Quick, run! Something's chasing us!\" {he.s} cries. Unfortunately, they have ventured too deep, and they "
            "are not sure where the exit is. They see two light-streaked tunnels in front of them: one on the left, "
            "and one on the right. Neither of them remembers exactly where they came from, and whatever {s} "
            "encountered seems to be coming closer. Which path should they run down?"),
    ("LABEL_LEFT", "Run towards the left path"),
    ("LABEL_RIGHT", "Run towards the right path"),
    ("RUN_LEFT", "{a} and {b} run down the left path screaming like little children. Things whiz by until the tunnel "
                 "grows brighter and brighter. Suddenly as they reach the end they are blinded by dazzling white "
                 "sunshine."),
    ("RUN_RIGHT", "{a} and {b} run down the right path screaming like little children. Things whiz by until the tunnel "
                  "grows brighter and brighter. Suddenly as they reach the end they are blinded by dazzling white "
                  "sunshine."),
    ("ARGUE", "As they burst out of the cave, they flop onto familiar ground. They pant heavily as their friends, family "
              "and soon the entire village crowds around them in concern. \"W-we w-went in th-the c-cave, and heard "
              "s-something c-chasing us,\" {a} stammers. \"We barely made it out alive!\" {b}, frightened, starts "
              "crying. \"This was YOUR idea! We almost got ourselves killed because of your stupid plan! I should have "
              "never agreed to come along!\" {b} shouts."),
    ("ARGUE_2", "{a} and {b}'s argument lasts for a while until both storm off to their homes. Although thankfully "
                "unhurt, neither of them wants anything to do with each other anymore."),
    ("MAKEUP", "As they burst out of the cave, they flop onto familiar ground. They pant heavily as their friends, "
               "family and soon the entire village crowds around them in concern. \"W-we w-went in th-the c-cave, and "
               "heard s-something c-chasing us,\" {a} stammers. Suddenly, {b} starts crying. \"It was terrifying! If "
               "we hadn't made it out...\" \"I'm so sorry, {b},\" {a} says. \"I should have listened to you. You were "
               "right all along, about everything.\" The two embrace, sobbing for a while as the others help care for "
               "them. They quickly make amends and promise never to let each other do anything like that again."),
    ("CHASM", "As they burst out of the cave, they flop onto what seems to be solid ground. However, {c}'s foot slips "
              "and {he.c} falls down a slippery chasm. Horrified, {d} has no time to react before {he.d}, too tumbles "
              "down the winding waterfall. All that's left of them is their fading screams and a bowl of fresh "
              "berries."),
    # Stay here
    ("STAY", "{b} is too enamored by all the glittering sights and objects and decides to stay put. {He.b} tries to take "
             "some to show the researchers, but {a} stops them. \"Wait. I don't think that's a good idea. What if you "
             "get cursed or something?\" What should {b} say?"),
    ("LABEL_RETURN", "You're right, I'll return them."),
    ("LABEL_KEEP", "Curses schmurses. I'm keeping them."),
    ("RETURN_FOOD", "{b} carefully rearranges the objects exactly where {he.b} found them, and offers a quick prayer of "
                    "apology to the spirits. When the two return home, they find that someone has left a bundle of "
                    "food at their doorsteps. Your villagers gain %d food."),
    ("RETURN_TECH", "{b} carefully rearranges the objects exactly where {he.b} found them, and offers a quick prayer of "
                    "apology to the spirits. When the two return home, they find that someone has left a bundle of "
                    "strange devices at their doorsteps. Your villagers gain %d tech points."),
    ("KEEP", "{b} decides to take some of the objects for further study. \"Surely the researchers will want to come here "
             "now.\" When they return home"),
    ("KEEP_BOTH", "{b} suddenly feels a strange pain in their chest. Over the next few days {he.b} develops a high fever "
                  "and convulsions. No matter what the healers do, {b} becomes weaker and weaker, until {he.b} passes "
                  "away in agony. {a}, in {his.a} guilt, stops eating until {he.a} too, quietly passes away. The "
                  "villagers mourn for them both, and upon discovering the stolen artifacts, perform a complicated "
                  "ritual to appease any angered spirits. Hopefully, this will put them, and poor {a} and {b}, to rest "
                  "in peace."),
    ("KEEP_ONE", "{b} suddenly feels a strange pain in their chest. Over the next few days {he.b} develops a high fever "
                 "and convulsions. No matter what the healers do, {b} becomes weaker and weaker, until {he.b} passes "
                 "away in agony. The villagers mourn for {him.b}, and upon discovering the stolen artifacts, perform a "
                 "complicated ritual to appease any angered spirits. Hopefully, this will put them, and poor {b}, to "
                 "rest in peace."),
    ("KEEP_RESEARCH", "{b} informs the researchers about the objects {a} and {b} found. Intrigued, they start launching "
                      "investigations into the strange artifacts along with the mysterious cave. Their discoveries "
                      "astonish the historians and scientists greatly, yielding much information about the island's "
                      "history and previous inhabitants. Your villagers gain %d tech points."),
)

KEEP_JOIN = ", "            # "When they return home" + ", " + the ending

PRONOUNS = {
    "m": {"he": "he", "He": "He", "his": "his", "him": "him"},
    "f": {"he": "she", "He": "She", "his": "her", "him": "her"},
}
_PRONOUN = re.compile(r"\{(he|He|his|him)\.([a-z])\}")
_NAME = re.compile(r"\{([a-z])\}")


def pronoun_persons(key: str) -> str:
    """The villagers whose pronouns a piece uses, in first-use order ("", "a", "ab", ...)."""
    out = ""
    for m in _PRONOUN.finditer(dict(TEXTS)[key]):
        if m.group(2) not in out:
            out += m.group(2)
    return out


def forms(key: str) -> tuple[str, ...]:
    """A piece's forms: "" (no pronoun), "m"/"f" (one villager's), "mm"/"fm"/"mf"/"ff" (two): the k-th letter is the
    sex of the k-th villager of pronoun_persons.  The C table keeps them at index sum(female_k << k)."""
    n = len(pronoun_persons(key))
    if n == 0:
        return ("",)
    out = []
    for index in range(1 << n):
        out.append("".join("f" if index >> k & 1 else "m" for k in range(n)))
    return tuple(out)


def english(key: str, form: str) -> str:
    """Piece `key` in form `form`, with %s for each name in order (and %d an amount)."""
    persons = pronoun_persons(key)

    def pronoun(m: re.Match) -> str:
        sex = form[persons.index(m.group(2))]
        return PRONOUNS[sex][m.group(1)]
    text = _PRONOUN.sub(pronoun, dict(TEXTS)[key])
    return _NAME.sub("%s", text)


def names_in(key: str) -> tuple[str, ...]:
    """The villagers each %s stands for, in order (the TOKENS letters)."""
    return tuple(_NAME.findall(_PRONOUN.sub("", dict(TEXTS)[key])))


def stem(key: str, form: str) -> str:
    return f"{STEM}.{key}" + (f".{form}" if form else "")


def rows() -> list[tuple[str, str, str, tuple[str, ...]]]:
    """Every (stem, key, English, names) the companion asks the translations for."""
    out = []
    for key, _ in TEXTS:
        for form in forms(key):
            out.append((stem(key, form), key, english(key, form), names_in(key)))
    return out


def fill(key: str, names: dict[str, str], sexes: dict[str, str] | None = None, award: int = 0) -> str:
    """The English of a piece with the names (a letter -> name), the pronouns (a letter -> "m"/"f") and %d put in."""
    sexes = sexes or {}
    form = "".join(sexes.get(p, "m") for p in pronoun_persons(key))
    text = english(key, form)
    for who in names_in(key):
        text = text.replace("%s", names[who], 1)
    return text.replace("%d", str(award))


# ---- The odds (the owner's, 2026-11-12) --------------------------------------------------------------------------

ADULT_YEARS = 18
MAX_AGE_GAP_YEARS = 5
PROCEED_A_PERCENT = 50                               # "Proceed Further": 50% A (the scream), else B (the find)
WRONG = ("WRONG_1", "WRONG_2", "WRONG_3", "WRONG_4")  # equal
A_ENDINGS = {"ARGUE": 10, "MAKEUP": 80, "CHASM": 10}  # percent, after either path
B_FINDS = {"FIND_MAP": 10, "FIND_COINS": 30, "FIND_TREASURE": 30, "FIND_FOOD": 30}   # percent
RETURN_FOOD_PERCENT = 50                             # "You're right": 50% food, else tech points
KEEP_ENDINGS = {"KEEP_RESEARCH": 80, "KEEP_BOTH": 10, "KEEP_ONE": 10}               # percent

# The award each ending gives (kind, size: src/vv_aspiring_adventurer.py AWARD_RANGES / AWARD_SIZES).
AWARDS = {
    "FIND_COINS": ("tech", "normal"), "FIND_TREASURE": ("tech", "huge"), "FIND_FOOD": ("food", "large"),
    "RETURN_FOOD": ("food", "normal"), "RETURN_TECH": ("tech", "normal"), "KEEP_RESEARCH": ("tech", "normal"),
}
# What each ending does (never shown).
EFFECTS = {
    "DONT": "none", "ARGUE": "none", "MAKEUP": "none", "CHASM": "both disappear",
    "FIND_MAP": "both disappear", "FIND_COINS": "award", "FIND_TREASURE": "award", "FIND_FOOD": "award",
    "RETURN_FOOD": "award", "RETURN_TECH": "award", "KEEP_RESEARCH": "award",
    "KEEP_BOTH": "name2 dies, then name1 dies", "KEEP_ONE": "name2 dies",
}
VANISHED = {
    "CHASM": "Disappeared in The Cave Explorers (fell down a chasm)",
    "FIND_MAP": "Disappeared in The Cave Explorers (left for a strange place)",
}


def outcome_chances() -> dict[str, dict[str, float]]:
    """Each ending's chance (percent) out of every time the player picks that answer.  "PROCEED" is out of every
    "Proceed Further" whatever the run answer; "RUN" out of either run answer (the two run the same odds)."""
    proceed: dict[str, float] = {"A": float(PROCEED_A_PERCENT)}
    for find, p in B_FINDS.items():
        proceed[find] = (100 - PROCEED_A_PERCENT) * p / 100
    return {
        "PROCEED": proceed,
        "RUN": {k: float(v) for k, v in A_ENDINGS.items()},
        "RETURN": {"RETURN_FOOD": float(RETURN_FOOD_PERCENT), "RETURN_TECH": float(100 - RETURN_FOOD_PERCENT)},
        "KEEP": {k: float(v) for k, v in KEEP_ENDINGS.items()},
    }
