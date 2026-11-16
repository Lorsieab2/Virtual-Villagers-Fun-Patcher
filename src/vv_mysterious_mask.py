"""The Mysterious Mask: the owner's island event for The Tree of Life (2026-11-13) -- its words and its rules.

The one source of the event's English: scripts/build_more_island_events.py writes it into the companion
(native/vvfp_more_island_events/mask_text.inc) and into the translation template
(data/translations/patcher_strings.json), and the Game Mechanics page reads the rules below.

THE OWNER'S TEXT, as pasted in chat (2026-11-13), unaltered but for the fixes the owner asked for ("fix grammar
mistakes"): "Little (mask)" and the plain "(name)" -> (name1), the finder; "where she got it from" -> "where (he/she)
got it from"; "hold back their tears" -> "hold back (his/her) tears"; the missing closing quote marks; "The parents of
(name1, name2) and the other kids" -> "The parents of (name1), (name2) and the other kids"; and the owner's edited
"rescued" speech.
  * the notes in parentheses or after "--" ("(then A or B, 50% each)", "(captured)") are instructions, never shown;
  * (name1) is the child who finds the mask, (name2) another child of the group; (he/she), (his/her), (him/her) are
    (name1)'s;
  * a sentence that runs on into the next piece ("The other children follow behind (him/her), and" + "they
    eventually make it back ...") is one paragraph: the pieces are joined with a space;
  * typography the game's font cannot draw is written in the letters it can (The Tree of Life's ldwBurweed27 has no
    curly quotes: src/vv_font_glyphs.py missing("vv4", "ldwBurweed27")): the curly quotes and apostrophes as " and '.

Each piece is written in one form per sex of (name1) when it uses a pronoun (else one form), with each name as %s;
each form is its own translation row.

TOKENS:  {a} (name1), the finder   {b} (name2)   {he} {He} {his} {His} {him}  (name1)'s pronouns
"""
from __future__ import annotations

import re

STEM = "vvfp.more_island_events/mask_text"
CONTEXT = ("VVFP More Island Events.dll (the island event The Mysterious Mask, The Tree of Life: its popups, in the "
           "game's own island-event popup with four answers)")

TITLE = "The Mysterious Mask"
GAME = 4

# (key, template).  Order is the C table's order (mask_text.inc MK_*).
TEXTS: tuple[tuple[str, str], ...] = (
    ("TITLE", TITLE),
    ("INTRO", "Little {a} has been playing with the other children at the edge of the forest. One day, towards the "
              "forbidden clearing, {he} spots a strange carved mask unlike anything {he} has ever seen! The other "
              "children wonder if someone dropped it, and {b} questions if the mask's owner lives somewhere nearby. "
              "Naturally, the children are afraid of strangers, even more so after hearing about the strange "
              "disappearances in the middle of the night, so no one moves a muscle. {b} innocently says \"We should go "
              "ask our Mommies and Daddies about it! Maybe someone's looking for it!\" But unfortunately, no one knows "
              "where their parents are or what direction the village is in. Being the finder, the other kids look to "
              "{a} to decide what to do. What shall they do?"),
    ("LABEL_WAIT", "Wait for their parents to come"),
    ("LABEL_CRY", "Cry for help"),
    ("LABEL_CLEARING", "Walk towards the clearing"),
    ("LABEL_FOREST", "Walk towards the forest"),
    ("WAIT", "The children wait all day for their parents to come. Eventually, they come and walk everyone back to the "
             "village. Little {a} shows the mask to {his} parents, who are alarmed and send for the elders. As night "
             "falls, {a} watches the elders chatter next to the fire."),
    ("CRY", "{a} does not know what to do, and immediately begins crying for help. The other children, being scared "
            "and lost, cry as well. The startled parents come running through the bushes and pick up their poor little "
            "darlings. That night, little {a} tells {his} parents about the strange mask. Alarmed, they immediately "
            "call the elders to discuss this discovery. {a} watches forlornly as the elders chatter beside the fire."),
    ("CLEARING", "Brave {a} grabs the mask and takes a step towards the clearing. The other children follow behind "
                 "{him}, and"),
    ("FOREST", "Brave {a} grabs the mask and takes a step towards the forest. The other children follow behind {him}, "
               "and"),
    ("HOME", "they eventually make it back to the village. That evening, {a} tells {his} parents what they saw, and "
             "shows them the mysterious mask. Alarmed, {a}'s parents tell the elders, who converse by moonlight next "
             "to the fire."),
    ("LOST", "they stumble into a dense part of the jungle. Night falls, and no one can see anything through the mist "
             "except their own shadows. Crack! Suddenly they hear the breaking of twigs beneath feet, and before "
             "anyone can react"),
    ("CAPTURED", "a group of masked strangers captures them and whisks them away to an unknown location. The worried "
                 "parents spot their footsteps in the mud several hours later, along with the mask {a} found earlier. "
                 "Fearing for the children's safety, they beg the elders to take action."),
    ("RESCUED", "a group of trusted adults from the village come and scoop them up. Startled, the children begin to "
                "cry. {a} manages to hold back {his} tears until they arrive back home, to which {he} bursts into a "
                "loud sob. {His} parents notice the strange mask and ask {him} where {he} got it from, to which {a} "
                "tells the adults the entire story. Fearing for the children's safety, they beg the elders to take "
                "action."),
    ("ELDERS", "After a long and tense discussion, the elders gather the villagers around the fire at daybreak. "
               "\"Recently, our village has been the victim of strange happenings involving masked people."),
    ("F_CAPTURED", "Just last night, a group of our children were possibly kidnapped and taken away to some hidden "
                   "location in the jungle. This mask was found at the scene.\""),
    ("F_RESCUED", "Just last night, a group of our children were found wandering in the jungle. Someone could have "
                  "kidnapped them, or worse. Luckily, our trusted scouts found them and successfully returned them "
                  "home. This mask was found at the scene.\""),
    ("F_BACK", "Just last night, our children got lost while playing in the jungle. They managed to make it back, "
               "thank goodness, but they found this mask sitting at the edge. It must have been planted there by "
               "someone.\""),
    ("F_WAITED", "Just last night, our children found this strange mask in the jungle, and they stayed put until "
                 "their parents could come and notify us.\""),
    ("F_CRIED", "Just last night, our children found this strange mask in the jungle, and they cried for help. Their "
                "parents notified us about the incident as soon as they could.\""),
    ("APPEAL", "\"We believe some foul play is happening. We understand that you are worried, and that everyone's "
               "safety is at risk. However, we need to get to the bottom of this. We cannot rest until this matter is "
               "settled. We need five able-bodied volunteers to come with us and form an expedition to find the "
               "makers of these masks. Only then will we know if they are truly a threat to our people.\""),
    ("VOLUNTEERS", "Five adults raise their hands and proceed into the elders' hut. After much planning, the "
                   "expedition team travels to the site where {a} found the mask, and heads off into parts unknown."),
    ("PARENTS", "The parents of {a}, {b} and the other kids wish the team good luck, and for justice for their "
                "children. The other villagers rally behind them, and hope for an end to the madness."),
)

PRONOUNS = {
    "m": {"he": "he", "He": "He", "his": "his", "His": "His", "him": "him"},
    "f": {"he": "she", "He": "She", "his": "her", "His": "Her", "him": "her"},
}
_PRONOUN = re.compile(r"\{(he|He|his|His|him)\}")
_NAME = re.compile(r"\{(a|b)\}")

# The four answers, in the popup's order (top to bottom; the keys 1 to 4).
ANSWERS = ("WAIT", "CRY", "CLEARING", "FOREST")
# The endings, in the C table's order (mask_core.inc MK_E_*).
ENDINGS = ("WAIT", "CRY", "CLEARING_HOME", "CLEARING_CAPTURED", "CLEARING_RESCUED", "FOREST_HOME",
           "FOREST_CAPTURED", "FOREST_RESCUED")
# The elders' speech on page F, by what happened (the owner: "matching what happened").
F_VERSION = {"WAIT": "F_WAITED", "CRY": "F_CRIED", "HOME": "F_BACK", "CAPTURED": "F_CAPTURED",
             "RESCUED": "F_RESCUED"}


def paragraphs_of(ending: str) -> tuple[tuple[tuple[str, ...], ...], ...]:
    """The popups an ending shows: each a tuple of paragraphs, each paragraph the keys joined with a space."""
    if ending in ("WAIT", "CRY"):
        story = ((ending,),)
        what = ending
    else:
        walk, what = ending.split("_")
        story = ((walk,) + (("HOME",) if what == "HOME" else ("LOST", what)),)
    elders = (("ELDERS", F_VERSION[what]), ("APPEAL",), ("VOLUNTEERS",), ("PARENTS",))
    return (story, elders)


def forms(key: str) -> tuple[str, ...]:
    """The forms a piece has: ("",) when it holds no pronoun, else ("m", "f") -- (name1)'s sex."""
    return ("m", "f") if _PRONOUN.search(dict(TEXTS)[key]) else ("",)


def english(key: str, form: str) -> str:
    """Piece `key` in form `form` ("m", "f" or ""), with %s for each name."""
    words = dict(PRONOUNS.get(form, PRONOUNS["m"]))
    words.update({"a": "%s", "b": "%s"})
    return re.sub(r"\{(\w+)\}", lambda m: words[m.group(1)], dict(TEXTS)[key])


def names_in(key: str) -> tuple[str, ...]:
    """The names a piece's %s stand for, in order: a (name1), b (name2)."""
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


def fill(key: str, form: str, name1: str = "", name2: str = "") -> str:
    """The English of a piece with the names put in, as the companion fills it."""
    text = english(key, form if forms(key) != ("",) else "")
    values = {"a": name1, "b": name2}
    for who in names_in(key):
        text = text.replace("%s", values[who], 1)
    return text


# ---- Who, the odds and the effects (the owner, 2026-11-13) -----------------------------------------------------------

POPULATION_AT_LEAST = 61         # The Lost Children's "A Dangerous Mission" rule: the living plus the babies carried
CHILD_UNDER_YEARS = 14           # the group: children under 14 (280 age units)
CHILDREN = (2, 4)                # at least 2 children; up to 4 picked when there are more
ADULT_YEARS = 18                 # the expedition: adults of 18 or more (360 age units)
VOLUNTEERS = 5
HOME_PERCENT = 50                # a walk: home safe (A) 50%, lost (B) 50% -- the clearing and the forest alike
CAPTURED_PERCENT = 25            # lost: captured (C) 25%, rescued (D) 75%
LINES_PER_EXTRA_ANSWER = 3       # the pages are laid out 3 lines shorter for each answer past two (4 answers: 11 - 6)

EFFECTS = {
    "volunteers": "the five volunteers leave for good on the expedition (gone, no graves), in every ending",
    "CAPTURED": "every child of the group is taken for good (gone, no graves)",
}


def outcome_chances() -> dict[str, dict[str, float]]:
    """Each ending's chance (percent) out of every time the player picks that answer."""
    lost = (100 - HOME_PERCENT) / 100
    out = {"WAIT": {"WAIT": 100.0}, "CRY": {"CRY": 100.0}}
    for walk in ("CLEARING", "FOREST"):
        out[walk] = {f"{walk}_HOME": float(HOME_PERCENT), f"{walk}_CAPTURED": lost * CAPTURED_PERCENT,
                     f"{walk}_RESCUED": lost * (100 - CAPTURED_PERCENT)}
    return out
