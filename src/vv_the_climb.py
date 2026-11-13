"""The Climb: the owner's island event for The Lost Children (2026-11-12) -- its words and its odds.

The one source of the event's English: scripts/build_more_island_events.py writes it into the companion
(native/vvfp_more_island_events/climb_text.inc) and into the translation template
(data/translations/patcher_strings.json), and the Game Mechanics page reads the odds below.

THE OWNER'S TEXT, as pasted in chat (2026-11-12), unaltered but for what the owner's own notes and the builder's brief
asked for:
  * the edits the owner approved: "(name) is certainly setting a name for themselves" -> "... for
    (himself/herself)"; and (2026-11-12) "known for their crazy ...", "makes their way toward the waterfall" and
    "notice their shortcomings" -> (his/her);
  * the notes in parentheses ("(Then 50:50)", "( (name) dies)", "((name) becomes fully mastered in Research ...)",
    "(everyone does Celebrating)", "((name) gains 10-20 points in research skill)") are instructions, never shown; the
    title line's "- any villager at least a Trainee Scientist age 18 or older" is the rule of who may be picked, so the
    title shown is "The Climb";
  * (name) / (Name) is the villager's full name; (he/she), (his/her), (him/her), (himself/herself) follow the villager
    (the same villager throughout); "(award)" is the amount;
  * typography the game's font cannot draw is written in the letters it can (The Lost Children's font holds only A-Z,
    a-z, 0-9 and ! " ' , . ? / ` : - and the space -- src/vv_font_glyphs.py, as A New Home's): the curly apostrophe
    as ', the dash as -, the ellipsis as ...;
  * a pronoun opening a sentence is capitalised ("(he/she) is an avid researcher" after a full stop);
  * the two climbs share their opening ("For several hours, ... Just a little further...", CLIMB), and the fall or the
    summit follows it after a space.

Each piece is written in one form per sex of the villager when it uses a pronoun (else one form), with the name as %s
each time it appears and an amount as %d; each form is its own translation row, so a translation never has to guess a
pronoun.

TOKENS:  {n} the villager's name   {he} {He} {his} {His} {him} {himself}  the villager's pronouns
"""
from __future__ import annotations

import re

STEM = "vvfp.more_island_events/climb_text"
CONTEXT = ("VVFP More Island Events.dll (the island event The Climb, The Lost Children: its popups, in the game's own "
           "island-event popup)")

TITLE = "The Climb"
GAME = 2

# (key, template).  Order is the C table's order (climb_text.inc CLIMB_*).
TEXTS: tuple[tuple[str, str], ...] = (
    ("TITLE", TITLE),
    ("INTRO", "{n} is known for {his} crazy, spontaneous, yet sometimes genius ideas. {He} is an avid researcher and "
              "has been studying the tribe's history for a long time. {He} believes that two of the tribe's founders "
              "fell down the Great Falls, but nothing definitive is known about their origins. {n} proposes trying "
              "to retrace their steps by climbing the waterfall and offers to devise a plan. The others are skeptical "
              "about {his} claims and warn {him} not to take matters into {his} own hands without further proof. {n} "
              "knows that the plan could be dangerous, but what if {he} is right? Should {he} go through with {his} "
              "plan, or follow the other researchers' advice?"),
    ("LABEL_PLAN", "Go with the plan"),
    ("LABEL_ADVICE", "Follow the scientists' advice"),
    ("PLAN", "{n} revises {his} plan until {he} believes it is practically foolproof. At dawn the next morning, {he} "
             "sneaks out of the hut before anyone else has woken up and makes {his} way toward the waterfall. Setting "
             "up {his} climbing gear, {he} makes the perilous ascent up the falls."),
    ("CLIMB", "For several hours, {he} carefully scales the jagged rocks until {he} can almost see over the edge of the "
              "falls. Just a little further..."),
    ("FALL", "Oops! {n}'s hand loses its grip and {he} falls many dozens of meters to the hard, unforgiving ground. "
             "When the villagers wake up, they discover {n}'s body and weep bitterly for their fallen colleague. {He} "
             "will be remembered as a passionate dreamer that dared to do the impossible."),
    ("SUMMIT", "With one last stretch, {n} climbs onto the final rock and stands in victory. From this height, {he} can "
               "see over the entire village and jungle canopy. {He} thinks {he} can even see other settlements from "
               "up here! Behind {him}, {he} hears the rushing of the falls echoing through a large cave mouth leading "
               "to somewhere unknown. Checking {his} notes and doing some quick calculations, {he} is almost certain "
               "the cave tunnel must lead somewhere close to the Southern Shore of Isola. {n} fervently writes down "
               "{his} deductions and makes a detailed sketch of the area before making the careful descent back home. "
               "That day, {he} presents {his} findings to the others, who work together to perfect {his} plan. Over "
               "several months they send an expedition team to the perilous peak, and confirm that {n} was right "
               "about everything. They name {n} a Distinguished Scientist, and recognize {his} achievements in a "
               "grand ceremony. {n} is certainly setting a name for {himself} throughout the entire scientific "
               "community! Your village gains %d tech points."),
    ("ADVICE", "{n} admits that {his} plan still needs some refining. {He} goes back to the drawing board to "
               "double-check it. After scrutinizing it thoroughly, even {he} sees glaring flaws in its execution, and "
               "writes a report detailing all {his} mistakes. The next day {he} consults {his} senior colleagues to "
               "help {him} work out the kinks in {his} plan, and over time {n} learns many things from their strict "
               "guidance. It turns out {he} had much to learn, but was too blinded by ambition to notice {his} "
               "shortcomings. {n} promises to be more humble and learn from {his} elders before stubbornly taking "
               "matters into {his} own hands."),
)

CLIMB_JOIN = " "            # CLIMB + " " + FALL / SUMMIT

PRONOUNS = {
    "m": {"he": "he", "He": "He", "his": "his", "His": "His", "him": "him", "himself": "himself"},
    "f": {"he": "she", "He": "She", "his": "her", "His": "Her", "him": "her", "himself": "herself"},
}
_PRONOUN = re.compile(r"\{(he|He|his|His|him|himself)\}")


def forms(key: str) -> tuple[str, ...]:
    """The forms a piece has: ("",) when it holds no pronoun, else ("m", "f")."""
    return ("m", "f") if _PRONOUN.search(dict(TEXTS)[key]) else ("",)


def english(key: str, form: str) -> str:
    """Piece `key` in form `form` ("m", "f" or ""), with %s for each name (and %d an amount)."""
    words = dict(PRONOUNS.get(form, PRONOUNS["m"]))
    words["n"] = "%s"
    return re.sub(r"\{(\w+)\}", lambda m: words[m.group(1)], dict(TEXTS)[key])


def names_in(key: str) -> tuple[str, ...]:
    """The names a piece's %s stand for, in order (always "n", the villager)."""
    return tuple(re.findall(r"\{(n)\}", dict(TEXTS)[key]))


def stem(key: str, form: str) -> str:
    return f"{STEM}.{key}" + (f".{form}" if form else "")


def rows() -> list[tuple[str, str, str, tuple[str, ...]]]:
    """Every (stem, key, English, names) the companion asks the translations for."""
    out = []
    for key, _ in TEXTS:
        for form in forms(key):
            out.append((stem(key, form), key, english(key, form), names_in(key)))
    return out


def fill(key: str, form: str, name: str, award: int = 0) -> str:
    """The English of a piece with the name (and %d) put in, as the companion fills it."""
    text = english(key, form if forms(key) != ("",) else "")
    return text.replace("%s", name).replace("%d", str(award))


# ---- Who and the odds (the owner, 2026-11-12) ---------------------------------------------------------------------

ADULT_YEARS = 18                 # 360 age units (20 a year)
RESEARCH_TRAINEE = 20            # The Lost Children's own "Trainee" level: below 20 is "Untrained" (0x429C3D)
RESEARCH_MAX = 100               # the game's own cap on a skill (0x4212F4: cmp [rec+0x7F4], 0x64 / mov 0x64)
FALL_PERCENT = 50                # "Go with the plan": 50% the fall, else the summit
SUMMIT_AWARD = ("tech", "large")  # twice a normal tech award (src/vv_aspiring_adventurer.py AWARD_SIZES)
ADVICE_GAIN = (10, 20)           # "Follow the scientists' advice": + this much Research, inclusive, at most RESEARCH_MAX
CELEBRATION_PLACE = 0x18         # the village celebration 0x45D7D0's place, as Old Friends calls it (0x4344AE)

EFFECTS = {
    "FALL": "dies (the game's own death: health 0, a body and a grave, \"Unknown causes\")",
    "SUMMIT": "Research set to the game's maximum, a large tech award, the village celebrates",
    "ADVICE": "+10 to 20 Research, at most the game's maximum",
}


def outcome_chances() -> dict[str, dict[str, float]]:
    """Each ending's chance (percent) out of every time the player picks that answer."""
    return {"PLAN": {"FALL": float(FALL_PERCENT), "SUMMIT": float(100 - FALL_PERCENT)},
            "ADVICE": {"ADVICE": 100.0}}
