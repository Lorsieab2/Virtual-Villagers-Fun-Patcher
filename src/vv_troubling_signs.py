"""The Troubling Signs: the owner's island event for The Secret City (2026-11-13) -- its words and its rules.

The one source of the event's English: scripts/build_more_island_events.py writes it into the companion
(native/vvfp_more_island_events/troubling_text.inc) and into the translation template
(data/translations/patcher_strings.json), and the Game Mechanics page reads the rules below.

THE OWNER'S TEXT, as pasted in chat (2026-11-13), unaltered but for what the owner approved and the brief asked for:
  * the grammar fixes the owner approved ("fix any obvious grammatical mistakes"): the closing and reopening quote marks
    around "(random name) says" in the four advisor speeches; "either our connection" -> "Either our connection" (a new
    sentence inside the quote); "O Kalahuna" -> "O (tribe name)", the player's own tribe name;
  * the notes in parentheses ("(four choices)", "(5 villagers age 18 and up disappear)", "(if Magicians were asked)",
    the title line's requirements) are instructions, never shown;
  * (Name) / (name) is the Tribal Chief's full name, (his/her) / (he/she) the chief's pronouns; (random name) is the
    advisor of the group the chief asked (the owner, 2026-11-13: one advisor per group, the same four kept for the
    whole event); (tribe name) the tribe's name the player typed when the village was started; (award) the amount;
  * typography the game's font cannot draw is written in the letters it can (The Secret City's ldwBurweed27 has no
    curly quotes: src/vv_font_glyphs.py missing("vv3", "ldwBurweed27") lists U+2018/2019/201C/201D): the curly quotes
    and apostrophes as " and '.  The text has no dash or ellipsis;
  * a pronoun opening a sentence is capitalised ("For the past 9 months, (he/she) has heard" stays lower case).

Each piece is written in one form per sex of the chief when it uses a pronoun (else one form), with each name as %s
and an amount as %d; each form is its own translation row, so a translation never has to guess a pronoun.

TOKENS:  {c} the chief's name   {a} the asked group's advisor   {t} the tribe's name
         {he} {He} {his} {His} {him}  the chief's pronouns
"""
from __future__ import annotations

import re

STEM = "vvfp.more_island_events/troubling_text"
CONTEXT = ("VVFP More Island Events.dll (the island event The Troubling Signs, The Secret City: its popups, in the "
           "game's own island-event popup with four answers)")

TITLE = "The Troubling Signs"
GAME = 3

# The four advisor groups, in the order of the popup's buttons (top to bottom).
GROUPS = ("SPIRITUAL", "MAGICIANS", "NATURALISTS", "SCIENTISTS")

_DECREE_SPEECH_2 = ("Look amongst yourselves, all who are eligible to work, and from you pick five to represent our "
                    "tribe. You alone will travel to find the cause of our suffering, and heal it, for the sake of us "
                    "all. Now go forth, and discuss your plans with my advisors. They will guide you on your sacred "
                    "mission. May Isola help us all.\"")


def _decree_1(who: str) -> str:
    return (f"\"I have consulted with {who}, and have heard your cries for help. There is much we know, and much we "
            "don't know about the strange misfortunes befalling our village. But I believe we have a plan to fix "
            "them!")


_DEPART = "On the day of departure, {c} meets personally with the chosen representatives and wishes them well on their "

# (key, template).  Order is the C table's order (troubling_text.inc TS_*).
TEXTS: tuple[tuple[str, str], ...] = (
    ("TITLE", TITLE),
    ("INTRO_1", "{c}, the tribal chief, has been noticing something troubling. For the past 9 months, {he} has heard "
                "reports of fish floating dead on the water. Crop harvests have been failing, and birds have been "
                "falling out of the sky. Even the villagers have started to feel weak and tired, almost to the point "
                "of being unable to work. The scientists and healers have been trying to investigate but have not "
                "found a definite explanation for these occurrences."),
    ("INTRO_2", "With so little information to go on, and the problems mounting further, {c} must make a decision "
                "quickly for the sake of the village. But, who should {c} go to for advice?"),
    ("LABEL_SPIRITUAL", "Consult the spiritual leaders"),
    ("LABEL_MAGICIANS", "Ask the magicians for advice"),
    ("LABEL_NATURALISTS", "Call the naturalists to a discussion"),
    ("LABEL_SCIENTISTS", "Talk with the scientists and healers"),
    ("ADVICE_SPIRITUAL", "The spiritual leaders believe that the village should pray and offer gifts. Surely these "
                         "unfortunate occurrences must stem from transgressions the villagers have made towards the "
                         "things that guide their fate. \"Make haste. The spirits are patient and kind, but such "
                         "transgressions are not easily forgiven,\" {a} says. \"One must be pure of heart, mind and "
                         "body to right what is wrong. It will take time. Time which grows ever shorter.\" Chief {c} "
                         "thanks the spiritual leaders for their wise counsel and makes {his} decree."),
    ("ADVICE_MAGICIANS", "The magicians think that the factions are in imbalance, and believe that the magical forces "
                         "that strengthen Isola have been weakened. \"The magic that flows within all things is "
                         "waning,\" {a} says. \"Either our connection, or its source. We must figure out which is "
                         "true, and remedy it.\" Chief {c} thanks the magicians for their wise counsel, and makes {his} "
                         "decree."),
    ("ADVICE_NATURALISTS", "The naturalists believe that the factions are in imbalance, and that the natural forces "
                           "that keep Isola healthy have been disrupted. \"The natural cycle of rebirth and renewal is "
                           "fading,\" {a} says. \"Soon enough, all of Isola will perish if nothing is done. We must "
                           "figure out what is destroying it and stop it.\" Chief {c} thanks the naturalists for their "
                           "wise counsel, and makes {his} decree."),
    ("ADVICE_SCIENTISTS", "The scientists and healers believe that some organic phenomenon is causing the animals and "
                          "plants to wither and die. \"Perhaps they are being poisoned,\" {a} says. \"Or, something in "
                          "their environment is adversely affecting their health. Whatever it is, we must do some "
                          "in-depth experimentation to get to the bottom of this disaster.\" Chief {c} thanks the "
                          "scientists and healers for their wise counsel, and makes {his} decree."),
    ("HEAR", "\"Hear me, O {t}! Your Chief speaks!\" {c} calls from on high. A crowd gathers in the amphitheater to "
             "listen to {his} words."),
    ("DECREE_SPIRITUAL", _decree_1("the spiritual leaders")),
    ("DECREE_MAGICIANS", _decree_1("the magicians")),
    ("DECREE_NATURALISTS", _decree_1("the naturalists")),
    ("DECREE_SCIENTISTS", _decree_1("the scientists and healers")),
    ("DECREE_2", _DECREE_SPEECH_2),
    ("DEPART_SPIRITUAL", _DEPART + "journey. As they leave, the tribe prays for a whole week, offering gifts of food to "
                                   "the spirits in hopes of granting them salvation. Your village loses %d food."),
    ("DEPART_MAGICIANS", _DEPART + "journey. As they leave, the tribe spends a whole week focusing their mental and "
                                   "physical energies towards honing their innate potential. Gradually, they gain "
                                   "strength as well as dexterity and clarity. This newfound strength pushes the "
                                   "villagers to accomplish extraordinary things that temporarily improve their living "
                                   "conditions. Your villagers gain %d tech points."),
    ("DEPART_NATURALISTS", _DEPART + "journey. As they leave, the tribe spends a whole week fortifying the earth and "
                                     "environment. The care and nourishment given by the villagers temporarily boosts "
                                     "the village's food production. Your villagers gain %d food."),
    ("DEPART_SCIENTISTS", _DEPART + "journey. As they leave, the tribe spends a whole week taking samples of everything "
                                    "into small containers. The scientists and healers suspend other projects to run "
                                    "tests on the abiotic and biotic samples, which yield some inconsistent results."),
    ("LOSS_SCIENTISTS", "Your village loses %d tech points."),
)

PRONOUNS = {
    "m": {"he": "he", "He": "He", "his": "his", "His": "His", "him": "him"},
    "f": {"he": "she", "He": "She", "his": "her", "His": "Her", "him": "her"},
}
_PRONOUN = re.compile(r"\{(he|He|his|His|him)\}")
_NAME = re.compile(r"\{(c|a|t)\}")


def forms(key: str) -> tuple[str, ...]:
    """The forms a piece has: ("",) when it holds no pronoun, else ("m", "f") -- the chief's sex."""
    return ("m", "f") if _PRONOUN.search(dict(TEXTS)[key]) else ("",)


def english(key: str, form: str) -> str:
    """Piece `key` in form `form` ("m", "f" or ""), with %s for each name (and %d an amount)."""
    words = dict(PRONOUNS.get(form, PRONOUNS["m"]))
    words.update({"c": "%s", "a": "%s", "t": "%s"})
    return re.sub(r"\{(\w+)\}", lambda m: words[m.group(1)], dict(TEXTS)[key])


def names_in(key: str) -> tuple[str, ...]:
    """The names a piece's %s stand for, in order: c the chief, a the advisor, t the tribe."""
    return tuple(_NAME.findall(dict(TEXTS)[key]))


def stem(key: str, form: str) -> str:
    return f"{STEM}.{key}" + (f".{form}" if form else "")


def rows() -> list[tuple[str, str, str, tuple[str, ...]]]:
    """Every (stem, key, English, names) the companion asks the translations for."""
    out = []
    for key, _ in TEXTS:
        for form in forms(key):
            out.append((stem(key, form), key, english(key, form), names_in(key)))
    return out


def fill(key: str, form: str, chief: str = "", advisor: str = "", tribe: str = "", award: int = 0) -> str:
    """The English of a piece with the names (and %d) put in, as the companion fills it."""
    text = english(key, form if forms(key) != ("",) else "")
    values = {"c": chief, "a": advisor, "t": tribe}
    for who in names_in(key):
        text = text.replace("%s", values[who], 1)
    return text.replace("%d", str(award))


def pages_of(group: str) -> tuple[tuple[str, ...], ...]:
    """The popups an answer shows, each a tuple of its paragraphs' keys: the advice, the "Hear me" page, the decree."""
    depart = ("DEPART_" + group,) + (("LOSS_SCIENTISTS",) if group == "SCIENTISTS" else ())
    return (("ADVICE_" + group,), ("HEAR",), ("DECREE_" + group, "DECREE_2") + depart)


# ---- Who and the effects (the owner, 2026-11-13) ------------------------------------------------------------------

ADULT_YEARS = 18                 # 360 age units (20 a year): the travellers and the advisors
TRAVELLERS = 5                   # leave the village for good (no bodies, no graves)
ADVISORS = 4                     # one per group; they speak and stay
POPULATION_AT_LEAST = 61         # The Lost Children's "A Dangerous Mission": a population of more than 60 (0x425860)
CHIEF_ROBE_BODY = 29             # the robe: The Secret City's robing 0x45FBC0 writes body +0xDF4 = 29 (0x45FBDE)

# Each answer's award: (kind, sign).  A normal award (src/vv_aspiring_adventurer.py AWARD_SIZES "normal"): a random
# amount, each equally likely, in The Secret City's stock range (food 200-600, tech 1,000-2,000), then the game's own
# factor for its two-choice events (x (villagers / 20 + 1), its picker 0x45D460).  A loss takes at most what is stored.
AWARDS = {"SPIRITUAL": ("food", -1), "MAGICIANS": ("tech", +1), "NATURALISTS": ("food", +1),
          "SCIENTISTS": ("tech", -1)}

EFFECTS = {
    "SPIRITUAL": "the village loses food (a normal award; never below 0)",
    "MAGICIANS": "the village gains tech points (a normal award)",
    "NATURALISTS": "the village gains food (a normal award)",
    "SCIENTISTS": "the village loses tech points (a normal award; never below 0)",
}
