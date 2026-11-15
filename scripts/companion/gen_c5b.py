"""Write the Companion Anthology's Volume 1 Part 2, Everyday Life & Personality, as
data/event_collection/companion/c5/c5b<NNN>_<slug>.json, then format and check them.  Events 001-060 (companion
L1142-1665, chunk K2) and 061-100 (L1667-2015, chunk K3) are in the table E below.

The source's format (design notes L1132-1140):
  EVENT 0NN - Title / <one-sentence scene> /
    TWO CHOICES: A-B (the same two labels in every such event) or THREE CHOICES: A-C (the same three), then
    POSSIBLE ENDINGS: two bullets;  or  NO CHOICE - One possible ending is selected: two bullets
  / OPTIONAL CONTINUITY: (the same in all 100)

How it maps (docs/event-collection/companion-authoring.md):
- No-choice events: one popup -- the scene, then one of the two endings appended, equally likely ("No-choice events
  simply play one of their listed natural endings", L1134).  Choice events: the scene is the question page with the
  source's own generic labels, each with its own src, and all lead to the SAME ending branch ("Endings are
  alternatives", L1140; the labels are the same in every event, so they are not routes).
- "TWO CHOICES:", "THREE CHOICES:", "POSSIBLE ENDINGS:" and "NO CHOICE - ..." are structural; "OPTIONAL CONTINUITY:"
  is a designer note.
- Effects: the part's rule (L1137) "For events with a child and a designated caregiver/guardian, grant that
  caregiver Parenting experience on every outcome" -- where the text names a child's parent or caregiver (005, 032,
  033), that villager is cast and gains a small Parenting on BOTH endings.  "Effects should be subtle ... Many events
  need no mechanical reward" (L1135): no other effect.  Words the effects table reads that change nothing
  ("celebration", "celebrates") are text_only with the reason.
- An elder, a teacher or another adult who merely talks with a child is not a designated caregiver: no Parenting.
- Kinship the text states is cast as kinship (cie-v6-binary.md 21): a parent and child (033), a caregiver and child
  (032, cast as the child's parent: the games' caregivers are parents), two siblings (028).  An aunt (012) and a
  grandparent (034) have no relation yet (gap C2): text only, the roles are cast by age and sex.
- A parent humming to a baby (005) is a nursing parent (special nursing_parent; nothing harms her).
- Deceased loved ones (011, 090) stay generic text (gap C3).
- K3 (061-100): the parent of 077 is cast parent_of the child and gains Parenting on both endings; "a young adult"
  (062) is 18-25, "a young villager" (070, 083) 3-17, "a farmer" (067) has Farming; two "relatives" (094) have no
  stated kinship kind: text only, cast by age.  Text-only words: the fire that dies down (074), a traveler greeted
  with food (092), one villager's private celebration (095).

    python scripts/companion/gen_c5b.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import companion_common as c  # noqa: E402

HEAD = r"^EVENT \d{3}\s+-\s+"
V, G, CH, EL = c.VILLAGER, c.GROWN, c.CHILD, c.ELDER
LITTLE = {"kind": "villager", "min_age": 3, "max_age": 7}      # "a little child", "a toddler"
YOUNG = {"kind": "villager", "min_age": 3, "max_age": 17}      # "two young villagers"
YOUNG_ADULT = {"kind": "villager", "min_age": 18, "max_age": 25}    # "a young adult"
FARMER = c.skilled(V, "Farming")                                  # "a farmer"
NURSING = {"kind": "villager", "min_age": 14, "special": "nursing_parent"}

NOTE_PRIVATE = c.text_only("celebration", "a friend's small private celebration, not the village's (rule 7)")
NOTE_CELEB = c.text_only("celebrates", "a friend celebrates one villager, not the village (rule 7)")

# num: ({role: spec}, [roles that gain Parenting on every ending], description, {ending 1-2 or 0 (scene): [text_only]})
E = {
    1: ({"singer1": V, "singer2": V, "singer3": V}, [],
        "Several villagers gather around a low fire and sing a tune everyone knows.", {}),
    2: ({"elder": EL, "listener": c.ANY_AGE}, [],
        "An elder tells a familiar story but remembers an overlooked detail this time.", {}),
    3: ({"giver": V, "recipient": V}, [], "One villager leaves a polished pebble and a woven ribbon for another.", {}),
    4: ({"elder": EL, "child": LITTLE}, [], "An elder shows a little child how to braid coconut fiber without tangling it.", {}),
    5: ({"parent": NURSING}, ["parent"], "A parent hums to a restless baby beneath the palms.", {}),
    6: ({"child": CH, "adult": G}, [], "A child asks an adult why good people sometimes have bad days.", {}),
    7: ({"villager": V}, [], "A villager sits alone wondering what makes a life worthwhile.", {}),
    8: ({"villager": V}, [], "A villager watches the sea and wonders whether other islands lie beyond it.", {}),
    9: ({"friend1": V, "friend2": V}, [], "Two friends wonder whether anyone could ever touch a star.", {}),
    10: ({"child": CH, "elder": EL, "scholar": V}, [],
         "A child asks whether the gods and spirits live among the stars.", {}),
    11: ({"villager": V}, [], "A villager wonders whether a loved one who died still watches over the village.", {}),
    12: ({"aunt": c.sexed(G, "female"), "child": CH}, [],
         "An aunt quietly wonders whether her young relative will find happiness and success.", {}),
    13: ({"villager": V, "friend": V}, [], "A villager confesses a mistake made years ago and asks a friend for advice.", {}),
    14: ({"villager": V, "friend": V}, [], "A villager feels guilty about a mishap they could not have prevented.", {}),
    15: ({"friend1": V, "friend2": V}, [], "Two friends sit in the shade and braid each other's hair.", {}),
    16: ({"villager": V}, [], "A villager washes cloth by the stream and hangs it over smooth branches.", {}),
    17: ({"worker": V}, [], "An exhausted worker decides to spend the afternoon resting.", {}),
    18: ({"worker": V, "supervisor": G}, [], "A villager abandons their task to watch clouds shaped like animals.", {}),
    19: ({"villager": V}, [], "A villager realizes they were wrong about something important.", {}),
    20: ({"villager1": V, "villager2": V}, [], "Two villagers share roasted breadfruit without speaking much.", {}),
    21: ({"elder": EL, "elder2": EL}, [], "An elder struggles to recall the name of an old friend.", {}),
    22: ({"lender": V, "friend": V}, [], "A villager lends a carved wooden comb to a friend.", {}),
    23: ({"villager": V}, [], "A shy villager receives unexpected praise for ordinary work.", {}),
    24: ({"villager": V}, [], "Someone rehearses an apology but cannot find the right moment.", {}),
    25: ({"villager": V, "other": V}, [], "A villager lingers after a farewell, reluctant to leave.", {}),
    26: ({"villager": V, "newcomer": V}, [], "A villager notices someone sitting alone at the edge of a gathering.", {}),
    27: ({"villager": V}, [], "An unassuming villager is overheard singing beautifully while working.", {}),
    28: ({"sibling1": c.ANY_AGE, "sibling2": c.related(c.ANY_AGE, "sibling_of", "sibling1")}, [],
         "Two siblings argue over a woven blanket on a cool evening.", {}),
    29: ({"child": CH, "adult": G}, [], "A child brings a cracked wooden toy to a patient adult.", {}),
    30: ({"child": CH, "adult": G}, [], "A child asks why older children get privileges younger ones do not.", {}),
    31: ({"toddler": LITTLE, "adult": G}, [], "A toddler insists on carrying a basket far too large for them.", {}),
    32: ({"child": CH, "caregiver": c.related(G, "parent_of", "child")}, ["caregiver"],
         "A child asks why a usually affectionate caregiver seems distant today.", {}),
    33: ({"child": CH, "parent": c.related(G, "parent_of", "child")}, ["parent"],
         "A parent notices that their child no longer needs help with a familiar task.", {}),
    34: ({"grandparent": EL}, [], "A grandparent sings a lullaby once sung to them as a child.", {}),
    35: ({"relative1": G, "relative2": G}, [], "Relatives argue affectionately about whose smile a baby inherited.", {}),
    36: ({"child": CH, "adult": G}, [], "A child offers an adult a crooked bracelet of grass and shells.", {}),
    37: ({"adult": G, "child": CH}, [], "An adult admits to a child that they do not know the answer to a question.", {}),
    38: ({"villager": V}, [], "A villager stands under the first gentle rain after a long dry spell.", {}),
    39: ({"villager": V}, [], "Someone pauses to listen to waves breaking against the rocks.", {}),
    40: ({"villager": V}, [], "A villager stretches stiff arms before beginning work.", {}),
    41: ({"worker": V}, [], "A worker settles beneath a broad banana leaf for a short nap.", {}),
    42: ({"joker": V, "friend": V}, [], "A villager tells a harmless joke to cheer up a tired friend.", {}),
    43: ({"friend1": V, "friend2": V}, [], "Two friends exchange a secret and agree to keep it private.", {}),
    44: ({"villager": V}, [], "A villager finds a folded piece of barkcloth with a kind message.", {}),
    45: ({"villager": V}, [], "A villager hopes nobody remembers their birthday.", {1: [NOTE_PRIVATE]}),
    46: ({"elder": EL}, [], "The smell of warm breadfruit reminds an elder of childhood.", {}),
    47: ({"musician": V}, [], "A musician cannot find the ending to a melody.", {}),
    48: ({"friend1": V, "friend2": V}, [], "Two friends disagree about a village custom.", {}),
    49: ({"villager1": V, "villager2": V}, [], "Two villagers take the winding path along the shore for no particular reason.", {}),
    50: ({"villager": V}, [], "A villager keeps a smooth stone they believe brings luck.", {}),
    51: ({"villager": V}, [], "A villager experiments with a dramatic arrangement of feathers and braids.", {}),
    52: ({"friend": V, "recipient": V}, [], "A friend quietly repairs a torn piece of clothing for someone else.", {}),
    53: ({"villager": V, "other": V}, [], "A villager notices someone has eaten less than usual.", {}),
    54: ({"villager": V}, [], "A villager completes a difficult task without anyone noticing.", {2: [NOTE_CELEB]}),
    55: ({"beginner": V}, [], "A beginner tries something new and fails in front of others.", {}),
    56: ({"helper": V}, [], "Someone helps a stranger carry a heavy bundle.", {}),
    57: ({"child1": CH, "child2": CH, "child3": CH}, [], "Three children argue about what shape a cloud resembles.", {}),
    58: ({"villager": V}, [], "A villager stays awake a little longer to look at the moon.", {}),
    59: ({"young1": YOUNG, "young2": YOUNG}, [],
         "Two young villagers imagine what their village might look like in a hundred years.", {}),
    60: ({"villager": V}, [], "A villager misses someone who moved to another part of the island.", {}),
    61: ({"rival1": V, "rival2": V}, [], "Two former rivals meet while gathering firewood.", {}),
    62: ({"young": YOUNG_ADULT}, [], "A young adult is trusted with a small but important duty.", {}),
    63: ({"villager": V}, [], "A villager receives advice they did not ask for.", {}),
    64: ({"villager": V}, [], "A villager visits a quiet spot where they often go to think.", {}),
    65: ({"villager": G}, [], "A villager notices a silver strand in their hair.", {}),
    66: ({"elder": EL}, [], "An elder rests beside a tree they remember from childhood.", {}),
    67: ({"farmer": FARMER}, [], "A farmer notices the days growing subtly shorter.", {}),
    68: ({"friend1": V, "friend2": V}, [], "Two busy friends find a few minutes to talk between chores.", {}),
    69: ({"villager": V}, [], "A villager becomes emotional while hearing an old song.", {}),
    70: ({"young": YOUNG}, [], "A young villager worries they will never become a master at their craft.", {}),
    71: ({"villager": V}, [], "A talented villager worries that succeeding will change how others treat them.", {}),
    72: ({"friend1": V, "friend2": V}, [], "Two friends invent a greeting they use only with each other.", {}),
    73: ({"villager": V}, [], "A villager leaves fresh flowers beside the hospital doorway.", {}),
    74: ({"villager1": V, "villager2": V}, [], "The last two villagers at a gathering watch the fire burn low.",
         {0: [c.text_only("die", "the fire dies down; nobody dies")]}),
    75: ({"villager": V}, [], "A villager understands a problem only after stepping away from it.", {}),
    76: ({"traveler": V}, [], "A traveler wonders whether home is a place or the people who welcome them.", {}),
    77: ({"child": CH, "parent": c.related(G, "parent_of", "child")}, ["parent"],
         "A parent tells a child the names of familiar constellations.", {}),
    78: ({"villager": V, "friend": V}, [], "A villager notices a friend has been unusually quiet.", {}),
    79: ({"villager": V, "friend": V}, [], "A villager realizes winning an argument cost them a friend's feelings.", {}),
    80: ({"villager": V, "other": V}, [], "Someone receives forgiveness for an old offense they have long regretted.", {}),
    81: ({"villager": V}, [], "A villager looks around at familiar huts, trees and neighbors and suddenly feels grateful.", {}),
    82: ({"child": CH, "adult": G}, [], "A child shows an adult a drawing of the entire village.", {}),
    83: ({"young": YOUNG, "elder": EL}, [], "A young villager jokes about what they will be like when they are old.", {}),
    84: ({"villager": V, "friend": V}, [], "A villager asks a friend how to choose between two good opportunities.", {}),
    85: ({"villager": V}, [], "A villager wakes from a vivid dream about an unfamiliar shore.", {}),
    86: ({"dancer": V}, [], "Someone begins a gentle dance beside the communal fire.", {}),
    87: ({"apprentice": V, "mentor": G}, [], "An apprentice brings their mentor a handmade gift.", {}),
    88: ({"child": CH, "elder": EL}, [], "A child asks an elder why their hands look so different.", {}),
    89: ({"villager1": V, "villager2": V}, [], "Two villagers quietly discuss whether the spirits hear their prayers.", {}),
    90: ({"villager": V}, [], "A villager says aloud the name of someone who died long ago.", {}),
    91: ({"explorer": V}, [], "An explorer promises to tell the children what lies beyond the next ridge.", {}),
    92: ({"traveler": V}, [], "A tired traveler returns to the village at dusk.",
         {1: [c.text_only("food", "friends greet a traveler with a meal; the village's food is unchanged")]}),
    93: ({"villager": V}, [], "A timid villager finally speaks during a communal discussion.", {}),
    94: ({"relative1": V, "relative2": V}, [], "Two relatives who have avoided each other sit together at a festival.", {}),
    95: ({"villager": V}, [], "A villager marks a personal milestone nobody else knew about.",
         {1: [c.text_only("celebration", "a friend joins one villager's private celebration, not the village's (rule 7)")]}),
    96: ({"villager": V}, [], "A villager decides not to rush through breakfast for once.", {}),
    97: ({"child": CH, "elder": EL}, [], "A child retells an elder's tale with outrageous embellishments.", {}),
    98: ({"master": G, "child": CH}, [], "A master craftsperson allows a child to try a simple safe task.", {}),
    99: ({"child": CH, "adult": G}, [],
         "A child asks why people grow old, why stars shine and where dreams come from, all at once.", {}),
    100: ({"villager": V, "friend": V}, [], "A villager thanks a friend who sat beside them during a difficult time.", {}),
}


def build(row: dict) -> dict:
    num = c.num_of(row)
    roles, carers, desc, notes = E[num]
    assert c.description_ok(desc), (num, desc)
    h = c.heading_line(row, HEAD)
    title = c.re.split(HEAD, c.line(h), maxsplit=1)[1].strip()
    scene = h + 1
    body = {n: c.line(n).strip() for n in range(h + 2, row["lines"][1] + 1)}
    marker = h + 2
    head = body[marker]
    cont = next(n for n, s in body.items() if s.startswith("OPTIONAL CONTINUITY:"))
    ledger = []
    if head.startswith("NO CHOICE"):
        labels, ends_at = [], marker
        ledger.append({"src": c.L(marker), "kind": "structural", "why": "no choice: one ending is drawn"})
    else:
        assert head in ("TWO CHOICES:", "THREE CHOICES:"), (row["id"], head)
        ends_at = next(n for n, s in body.items() if s == "POSSIBLE ENDINGS:")
        labels = [n for n in range(marker + 1, ends_at) if body[n]]
        assert len(labels) == (2 if head.startswith("TWO") else 3), row["id"]
        ledger += [{"src": c.L(marker), "kind": "structural", "why": "the choices' heading"},
                   {"src": c.L(ends_at), "kind": "structural", "why": "the endings' heading: one is drawn"}]
    endings = [n for n in range(ends_at + 1, cont) if body[n]]
    assert len(endings) == 2 and all(body[n].startswith("•") for n in endings), row["id"]
    ledger.append({"src": c.L(cont), "kind": "note",
                   "why": "OPTIONAL CONTINUITY: a designer note on memory and callbacks, never shown (rule 9)"})
    nodes: dict = {}
    if labels:
        nodes["scene"] = {"type": "question", "name": "The scene", "text": c.shown(scene), "src": c.L(scene),
                          "choices": [{"label": c.shown(n), "next": "ending", "src": c.L(n)} for n in labels]}
        nodes["ending"] = {"type": "branch", "children": [{"next": "e1"}, {"next": "e2"}]}
    else:
        nodes["scene"] = {"name": "The scene", "text": c.shown(scene), "src": c.L(scene),
                          "children": [{"next": "e1"}, {"next": "e2"}]}
    if notes.get(0):
        nodes["scene"]["text_only"] = c.with_src(notes[0], c.L(scene))
    for k, n in enumerate(endings, 1):
        nodes[f"e{k}"] = c.page(f"Ending {k}", c.shown(n), c.L(n), [c.parenting(r) for r in carers],
                                notes.get(k, ()), append=not labels)
    col = {"id": row["id"], "title_src": c.L(h), "ledger": ledger, "description": desc}
    cast_only = [r for r in roles if r not in carers]
    if cast_only:
        col["cast_only"] = cast_only
    return {"format": "vvfp-cie-graph", "version": 6, "title": title, "games": c.ALL, "collection": col,
            "requirement": {"min_eligible": len(roles)}, "roles": roles, "start": "scene", "nodes": nodes}


def main() -> int:
    rows = [r for r in c.rows("c5b") if c.num_of(r) in E]
    assert len(rows) == len(E), (len(rows), len(E))
    return c.write_and_check([(r["section"], r["id"], build(r)) for r in rows])


if __name__ == "__main__":
    sys.exit(main())
