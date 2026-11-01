"""Picture Studio: every item a villager can carry, in all five games (docs/picture-studio.md, "Carried items").

Each game keeps what a villager carries in one field of the villager record, and its village draw turns that
number into a picture: a cell of carrying.png, or (The Lost Children on, for the higher numbers) a cell of the
collectables sheet.  The renderers (vv_pictures_vv1.py ... vv_pictures_vv5.py) draw any number exactly as the
game does; this module is the list of numbers worth offering, each named, and what the game does with it:

  GAME     the game's own code puts this number in the carry field (the evidence: docs/picture-studio-vv<N>.md,
           "Carried items", every place that stores it);
  UNUSED   the picture is on the sheet and the game's carry draw draws it, but no code the game runs ever
           stores the number (either nothing stores it at all, or only code that never runs -- DEAD, with the
           reason in the docs).  Offered, marked "(unused in the game)";
  BLANK    a number the carry draw accepts whose cell is empty art; marked "(blank picture, unused in the game)";
  PATCHER  only a patcher feature makes it appear (the Super-Secret Golden Mushroom); marked "(patcher)".

The carry field and nothing-value per game (the renderers' own constants): A New Home +0x3C (0x13 nothing),
The Lost Children +0x44 (0x1A), The Secret City +0xF20 (-1), The Tree of Life +0x1CDC (-1), New Believers
+0x1D0C (-1).  No game keeps the field in its save: each rebuilds it on loading -- a baby (item 3) for a villager
who is expecting or nursing, otherwise nothing -- so From my save offers "As the game shows it after loading".

THE GOLDEN MUSHROOM (the "Super-Secret Golden Mushroom" patch, data/builds.json vv<N>_super_secret_golden_mushroom).
Its row's code makes the mushroom spawn and be carried as GOLDEN_ITEM[game].  In The Lost Children that number
is collectables_images.png cell 50, the game's own golden mushroom picture.  In the others the companion
"VVFP Golden Mushroom.dll" (native/vvfp_golden_mushroom/vvfp_golden_mushroom.c) draws Images\\golden_mushroom.png
(the patcher's assets/golden_mushroom/golden_mushroom.png) in place of the golden frame, moved by GOLDEN_SHIFT:
A New Home hooks the frame draw 0x4093D0 (carrying.png frame 15, which the 15 x 1 sheet does not have), the
others the world draw their item draw calls (The Secret City 0x42E510, The Tree of Life 0x44C640, New Believers
0x44F380) for collectables frame 50.  The litter copies are carrying.png cells (never the golden frame), so
they stay the game's own picture.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import vv_picture_image as pi

ROOT = Path(__file__).resolve().parents[1]
GAME, UNUSED, BLANK, PATCHER = "game", "unused", "blank", "patcher"
SAVED = "saved"                         # From my save: what the game rebuilds on loading
UNUSED_MARK = " (unused in the game)"
BLANK_MARK = " (blank picture, unused in the game)"
BABY = 3                                # every game's carried baby (carrying.png cell 3)

GOLDEN_FILE = "golden_mushroom.png"
GOLDEN_ART = ROOT / "assets" / "golden_mushroom" / GOLDEN_FILE
GOLDEN_SIZE = (29, 22)
GOLDEN_ITEM = {1: 15, 2: 0x50, 3: 0x66, 4: 0x78, 5: 0x82}
# The companion's offsets (vvfp_golden_mushroom.c VV1_DX/VV1_DY and LATER_STUB(vvN, slot, resume, DX, DY)).
GOLDEN_SHIFT = {1: (6, 2), 3: (7, 0), 4: (7, 0), 5: (7, 1)}


@dataclass(frozen=True)
class Item:
    value: int
    name: str
    status: str = GAME
    doing: str = ""                     # what the villager is doing (the game's status text), or why unused


def _collection(first: int, name: str, per_rarity: int, rarities=("common", "uncommon", "rare"),
                doing: str = "") -> list[Item]:
    out = []
    for r, rarity in enumerate(rarities):
        for k in range(per_rarity):
            out.append(Item(first + r * per_rarity + k, f"{name}, {rarity} {k + 1}", GAME, doing))
    return out


# --------------------------------------------------------------------------------------- A New Home (+0x3C)
VV1 = [
    Item(0, "Berries", GAME, "Foraging"),
    Item(1, "Rock", GAME, "Exercising; Clearing blockage; Building small hut"),
    Item(2, "Crops (second picture)", UNUSED, "no code stores 2 (the art is cell 6's)"),
    Item(3, "Baby", GAME, "expecting (until the birth)"),
    Item(4, "Wood", GAME, "Fixing hut; Building small hut; Cleaning up the beach; Uncovering the well"),
    Item(5, "Laundry", GAME, "Laundry"),
    Item(6, "Crops", GAME, "Planting crops; Harvesting crops"),
    Item(7, "Flowers", GAME, "Honoring the Dead; Honoring the Idol; Honoring the temple"),
    Item(8, "Fish", GAME, "Fishing"),
    Item(9, "Crab", GAME, "Fishing (Farming 90 or more, 1 in 5)"),
    Item(10, "Water", GAME, "Watering crops; Watering the field; Trying to water strange patch"),
    Item(11, "Body", GAME, "Burying the dead"),
    Item(12, "Strange fish", GAME, "Hunting a strange fish!"),
    Item(13, "Brown mushroom", GAME, "Picking a mushroom"),
    Item(14, "Red mushroom", GAME, "Picking a mushroom (1 in 20 mushrooms)"),
    Item(15, "Golden Mushroom", PATCHER, "Picking a mushroom (Super-Secret Golden Mushroom)"),
]

# --------------------------------------------------------------------------------- The Lost Children (+0x44)
_VV2_KIDS = "Collecting a new item! (children)"
VV2 = [
    Item(0, "Berries", UNUSED, "no code stores 0"),
    Item(1, "Rock", GAME, "Exercising; Building small hut"),
    Item(2, "Feathers", UNUSED, "no code stores 2"),
    Item(3, "Baby", GAME, "expecting (until the birth)"),
    Item(4, "Wood", GAME, "Rebuilding broken hut; Building small hut; Fixing hut; Gathering firewood; "
                          "Creating cutting tools; Building a scarecrow; Building a dam; Teaching children"),
    Item(5, "Laundry", GAME, "Doing laundry; Teaching children"),
    Item(6, "Crops", GAME, "Harvesting crops; Adding food to the stew; Teaching children"),
    Item(7, "Flowers", GAME, "Honoring the Dead; Researching; Teaching children"),
    Item(8, "Fish", GAME, "Fishing; Teaching children"),
    Item(9, "Crab", GAME, "Fishing; Teaching children"),
    Item(10, "Water", GAME, "Adding water to the stew; Watering crops"),
    Item(11, "Body", GAME, "Burying the dead"),
    Item(12, "Algae-eating fish", GAME, "Catching algae-eating fish!"),
    Item(13, "Brown mushroom (carrying.png)", UNUSED, "no code stores 13: a carried mushroom is collectables "
                                                      "picture 49"),
    Item(14, "Red mushroom (carrying.png)", UNUSED, "no code stores 14"),
    Item(15, "Dry grass", GAME, "Gathering dry grass"),
    Item(16, "Coconut", GAME, "Harvesting coconuts"),
    Item(17, "Empty bowl", UNUSED, "no code stores 17"),
    Item(18, "Cutting tool", GAME, "Fishing; Removing the vines; Cutting away briar thorns"),
    Item(19, "Cauldron", GAME, "Retrieving a cauldron"),
    Item(20, "Pot of stew", UNUSED, "no code stores 20"),
    Item(21, "Herb", GAME, "Adding an herb to the stew"),
    Item(22, "Stone blades", GAME, "Creating cutting tools"),
    Item(23, "Gong piece", GAME, "Retrieving something from the pond; Retrieving a piece of the gong"),
    Item(24, "Mortar", UNUSED, "no code stores 24"),
    Item(25, "Potion", UNUSED, "no code stores 25"),
]
VV2_COLLECTABLE = 0x1E                  # carry value of collectables_images.png cell 0 (a walking child)
for _first, _name in ((0, "Butterfly"), (12, "Shell"), (24, "Beetle"), (36, "Pebble")):
    VV2 += _collection(VV2_COLLECTABLE + _first, _name, 4, doing=_VV2_KIDS)
VV2 += [
    Item(0x4E, "Brown mushroom", GAME, "Picking a mushroom (children)"),
    Item(0x4F, "Red mushroom", GAME, "Picking a mushroom (children; 1 in 10)"),
    Item(0x50, "Golden Mushroom", PATCHER, "Picking a mushroom (Super-Secret Golden Mushroom; the game's own "
                                           "picture)"),
    Item(0x51, "Collectables picture 52", BLANK, "no code stores it"),
    Item(0x52, "Collectables picture 53", BLANK, "no code stores it"),
    Item(0x53, "Collectables picture 54", BLANK, "no code stores it"),
]

# ---------------------------------------------------------------------------------- The Secret City (+0xF20)
_LECTURE = "Lecturing (a random item 0-25)"
VV3 = [
    Item(0, "Berries", GAME, f"{_LECTURE}; Researching"),
    Item(1, "Rock", GAME, "Doing exercise; Repairing the bath; Clearing rubble"),
    Item(2, "Feathers", GAME, f"Researching; {_LECTURE}"),
    Item(3, "Baby", GAME, "expecting or nursing"),
    Item(4, "Wood", GAME, "Fixing hut; Gathering firewood; Building small hut"),
    Item(5, "Laundry", GAME, "Washing the laundry"),
    Item(6, "Crops", GAME, "Bringing back a prize"),
    Item(7, "Flowers", GAME, "Honoring the Dead; Researching"),
    Item(8, "Fish", GAME, "Fishing"),
    Item(9, "Crab", GAME, "Fishing (1 in 10, skilled)"),
    Item(10, "Water", GAME, "Emptying the pot; Putting water on the firepit; Cleaning up after the rain"),
    Item(11, "Body", GAME, "Burying the dead"),
    Item(12, "Magic fish", GAME, _LECTURE),
    Item(13, "Brown mushroom (carrying.png)", GAME, _LECTURE),
    Item(14, "Red mushroom (carrying.png)", GAME, _LECTURE),
    Item(15, "Kindling", GAME, f"Gathering dry grass; {_LECTURE}"),
    Item(16, "Coconut", GAME, _LECTURE),
    Item(17, "Empty bowl", GAME, f"Researching; {_LECTURE}"),
    Item(18, "Tool", GAME, _LECTURE),
    Item(19, "Pot", GAME, _LECTURE),
    Item(20, "Full pot", GAME, _LECTURE),
    Item(21, "Herbs", GAME, _LECTURE),
    Item(22, "Spear tips", GAME, _LECTURE),
    Item(23, "Bounty", GAME, "Bringing back a prize"),
    Item(24, "Lab equipment 1", GAME, "Researching"),
    Item(25, "Lab equipment 2", GAME, _LECTURE),
] + [Item(26 + k, f"Alchemy Lab piece {k + 1}", GAME, "picking up a piece of the Alchemy Lab") for k in range(5)] + [
    Item(0x1F + k, name, GAME, "Gathering herbs; Doing alchemy; Studying medicine")
    for k, name in enumerate(("Tiger Lily", "Cactus", "Lotus", "Black Orchid", "Rose", "Pitcher Plant",
                              "Berry Plant"))] + [
    Item(38, "Banana", GAME, "Harvesting fruit"),
    Item(39, "Mango", GAME, "Harvesting fruit"),
    Item(40, "Papaya", GAME, "Harvesting fruit"),
    Item(41, "Honey", GAME, "Harvesting honey"),
    Item(42, "Lit torch", GAME, "Lighting burners; Trying an idea"),
    Item(43, "Bowl of junk", GAME, "Cleaning up after the rain"),
    Item(44, "Key 1 (diamond)", GAME, "picking up a key"),
    Item(45, "Key 2 (red gem)", GAME, "picking up a key; Trying to reach the key"),
    Item(46, "Key 3 (dark sphere)", GAME, "Swapping the pearl"),
    Item(47, "Shark charmer vial", GAME, "Carrying vial to ocean"),
    Item(48, "Leaves", GAME, "Clearing leaves"),
    Item(49, "Giant pearl", GAME, "picking up the giant pearl"),
    Item(50, "Unlit torch", GAME, "Trying an idea"),
    Item(51, "Irregular pearl", GAME, "picking up the irregular pearl"),
]
VV3_COLLECTABLE = 0x34                  # carry value of collectables_small.png cell 0
_VV3_KIDS = "Collecting a new item! (children)"
for _first, _name in ((0, "Turtle shell"), (12, "Coral"), (24, "Tablet piece"), (36, "Feather")):
    VV3 += _collection(VV3_COLLECTABLE + _first, _name, 4, doing=_VV3_KIDS)
VV3 += [
    Item(0x64, "Brown mushroom", GAME, "Picking a mushroom (children)"),
    Item(0x65, "Red mushroom", GAME, "Picking a mushroom (children; 8%)"),
    Item(0x66, "Golden Mushroom", PATCHER, "Picking a mushroom (Super-Secret Golden Mushroom)"),
    Item(0x67, "Collectables picture 52", BLANK, "no code stores it"),
    Item(0x68, "Collectables picture 53", BLANK, "no code stores it"),
    Item(0x69, "Collectables picture 54", BLANK, "no code stores it"),
]

# --------------------------------------------------------------------------------- The Tree of Life (+0x1CDC)
_NONE = "no code stores it"
_VV4_DEAD = "only the never-started jobs Hiding something / Spring cleaning store it (DEAD)"
VV4 = [
    Item(0, "Berries", GAME, "Harvesting blackberries; Researching; Adding to the stew"),
    Item(1, "Rock", GAME, "Heating a rock in the fire; Clearing rubble; Doing exercise"),
    Item(2, "Feathers", GAME, "Researching"),
    Item(3, "Baby", GAME, "expecting"),
    Item(4, "Wood", GAME, "Attempting to fix the piers; Keeping the stream clear; Fixing the hut; Gathering "
                          "firewood; Building a hut"),
    Item(5, "Laundry", GAME, "Washing the laundry"),
    Item(6, "Crops", GAME, "Adding to the stew"),
    Item(7, "Flowers", GAME, "Honoring the Dead; Researching"),
    Item(8, "Fish (carrying.png)", UNUSED, _NONE),
    Item(9, "Crab", GAME, "Catching a crab"),
    Item(10, "Water", GAME, "Filling a pot; Emptying the pot; Cleaning up the nasty mold; Cleaning up after the rain"),
    Item(11, "Body", GAME, "Burying the dead"),
    Item(12, "Magic fish", UNUSED, _NONE),
    Item(13, "Brown mushroom (carrying.png)", UNUSED, _NONE + " (a carried mushroom is collectables picture 49)"),
    Item(14, "Red mushroom (carrying.png)", UNUSED, _NONE),
    Item(15, "Dry grass", GAME, "Gathering dry grass; Researching"),
    Item(16, "Coconut", UNUSED, _NONE),
    Item(17, "Empty bowl", GAME, "Filling a pot with fresh water / salt water; Researching"),
    Item(18, "Tool", GAME, "Sharpening into a cutting tool; Cutting some pulpy vines; Looking for a tool to cut "
                           "some stalks"),
    Item(19, "Pot", UNUSED, _VV4_DEAD),
    Item(20, "Stew pot", GAME, "Something smells YUMMY!"),
    Item(21, "Big leaf", GAME, "Covering the hot rocks"),
    Item(22, "Stone tips", GAME, "Attempting to cut the branch"),
    Item(23, "Bounty", UNUSED, _VV4_DEAD),
    Item(24, "Lab bowl", GAME, "Researching"),
    Item(25, "Nothing to see (an empty picture)", GAME, "Researching (1 in 7: the hands look empty)"),
    Item(26, "Lab bowl (second picture)", UNUSED, _NONE),
    Item(27, "Striped jar", UNUSED, _NONE),
    Item(28, "Striped vase", UNUSED, _NONE),
    Item(29, "Tool (second picture)", UNUSED, _NONE),
    Item(30, "Clay amphora", UNUSED, _NONE),
    Item(31, "Spicy herb", GAME, "Gathering herbs; Retrieving medicinal plant for study; Cooking"),
    Item(32, "Sweet herb", GAME, "Gathering herbs; Retrieving medicinal plant for study; Cooking"),
    Item(33, "Soapy herb", GAME, "Gathering herbs; Retrieving medicinal plant for study; Cooking"),
    Item(34, "Pulpy vines", GAME, "Gathering herbs; Cutting some pulpy vines; Cooking"),
    Item(35, "Medicinal plant", GAME, "Retrieving medicinal plant for study; Cooking"),
    Item(36, "Red-topped stalk", UNUSED, _NONE),
    Item(37, "Yellow berry cluster", UNUSED, _NONE),
    Item(38, "Banana", UNUSED, _NONE),
    Item(39, "Mango", UNUSED, _NONE),
    Item(40, "Papaya", UNUSED, _NONE),
    Item(41, "Cloth pulp", GAME, "Spreading cloth pulp; Honoring the tree"),
    Item(42, "Lit torch", UNUSED, _NONE),
    Item(43, "Debris", GAME, "Cleaning up after the rain"),
    Item(44, "Keystone", GAME, "Attempting to install the keystone"),
    Item(45, "Red gem", UNUSED, _NONE),
    Item(46, "Dark sphere", UNUSED, _NONE),
    Item(47, "Red striped pot", UNUSED, _NONE),
    Item(48, "Leaves", UNUSED, _NONE),
    Item(49, "Pearl", UNUSED, _NONE),
    Item(50, "Unlit torch", UNUSED, _NONE),
    Item(51, "Irregular pearl", UNUSED, _NONE),
    Item(52, "Hot rock", GAME, "Taking a hot rock to the pot; Carrying a hot rock"),
    Item(53, "Cloth", GAME, "Repairing braid for a lei; Attempting to fix fishing nets; Storing finished cloth; "
                            "Attempting to bind the branch"),
    Item(54, "Yellow fruit", GAME, "Shaking down some fruit!"),
    Item(55, "Orange fruit", GAME, "Carrying fruit to the food bin; Adding to the stew"),
    Item(56, "Fish", GAME, "Retrieving a fish"),
    Item(57, "Golden fish", GAME, "Retrieving a fish (once the fish scales are found)"),
    Item(58, "Soap", GAME, "Stacking soap; Attempting to clean the stump; Adding soap to the pond"),
    Item(59, "Fish bone", GAME, "Retrieving a fish bone"),
    Item(60, "Heat-treated bone", GAME, "Heat treating a fish bone"),
    Item(61, "Beetle", GAME, "Purifying the tree"),
    Item(62, "Blackberries", GAME, "Harvesting blackberries"),
    Item(63, "Lei braid", GAME, "Taking braid to start a lei"),
    Item(64, "Lei", GAME, "Hanging a lei on the tree"),
    Item(65, "Lei flower (orange)", GAME, "Picking a flower for the lei; Taking flower to lab"),
    Item(66, "Lei flower (purple)", GAME, "Picking a flower for the lei; Taking flower to lab"),
    Item(67, "Lei flower (white)", GAME, "Picking a flower for the lei; Taking flower to lab"),
    Item(68, "Frog", GAME, "Rescuing frogs"),
    Item(69, "Twig nest", UNUSED, _NONE),
]
VV4_COLLECTABLE = 0x46
for _first, _name, _doing in ((0, "Fish scale", "Collecting a fish scale"), (12, "Lab equipment", "Collecting lab gear"),
                              (24, "Mausoleum mural piece", "Collecting mausoleum piece"),
                              (36, "Wind flute head", "Collecting a wind flute head")):
    VV4 += _collection(VV4_COLLECTABLE + _first, _name, 4, doing=f"{_doing} (children)")
VV4 += [
    Item(0x76, "Brown mushroom", GAME, "Picking a mushroom (children)"),
    Item(0x77, "Red mushroom", GAME, "Picking a mushroom (children; 8%)"),
    Item(0x78, "Golden Mushroom", PATCHER, "Picking a mushroom (Super-Secret Golden Mushroom)"),
    Item(0x79, "Collectables picture 52", BLANK, "the game refuses it (0x4132B5: nothing above 0x78)"),
    Item(0x7A, "Collectables picture 53", BLANK, "the game refuses it"),
    Item(0x7B, "Collectables picture 54", BLANK, "the game refuses it"),
]

# --------------------------------------------------------------------------------- New Believers (+0x1D0C)
_RESEARCH = "Researching (a random pick)"
_VV5_DEAD = "only the never-started actions Hiding something / Spring cleaning store it (DEAD)"
VV5 = [
    Item(0, "Noni", GAME, "Harvesting noni; Harvesting crops; Researching"),
    Item(1, "Rock", GAME, "Doing exercise"),
    Item(2, "Feathers", GAME, _RESEARCH),
    Item(3, "Baby", GAME, "expecting (heathens too)"),
    Item(4, "Wood", GAME, "Building; Gathering firewood; Fixing huts; the totems, the mausoleum, the aqueduct, "
                          "the granary"),
    Item(5, "Laundry", GAME, "Washing the laundry"),
    Item(6, "Bowl of nuts", UNUSED, _VV5_DEAD),
    Item(7, "Flowers", GAME, f"Honoring the dead; {_RESEARCH}"),
    Item(8, "Fish (carrying.png)", UNUSED, _NONE),
    Item(9, "Crab", UNUSED, _NONE),
    Item(10, "Pan", GAME, "Panning for gold; Retrieving a pan"),
    Item(11, "Body", GAME, "Burying the dead"),
    Item(12, "Magic fish", UNUSED, _NONE),
    Item(13, "Brown mushroom (carrying.png)", UNUSED, _NONE + " (a carried mushroom is collectables picture 49)"),
    Item(14, "Red mushroom (carrying.png)", UNUSED, _NONE),
    Item(15, "Dry grass", GAME, f"Gathering dry grass; {_RESEARCH}"),
    Item(16, "Coconut", UNUSED, _NONE),
    Item(17, "Bowl of soup", GAME, _RESEARCH),
    Item(18, "Tool", GAME, "Building a statue"),
    Item(19, "Pot", UNUSED, _VV5_DEAD),
    Item(20, "Stew pot", UNUSED, _NONE),
    Item(21, "Big leaf", UNUSED, _NONE),
    Item(22, "Spear tips", GAME, "Building a statue"),
    Item(23, "Bounty", UNUSED, _VV5_DEAD),
    Item(24, "Lab bowl", GAME, _RESEARCH),
    Item(25, "Nothing to see (an empty picture)", GAME, f"{_RESEARCH}: the hands look empty"),
    Item(26, "Lab bowl (second picture)", UNUSED, _NONE),
    Item(27, "Striped jar", UNUSED, _NONE),
    Item(28, "Striped vase", UNUSED, _NONE),
    Item(29, "Tool (second picture)", UNUSED, _NONE),
    Item(30, "Red amphora", UNUSED, _NONE),
] + [Item(0x1F + k, f"Medicinal plant {k + 1} ({look})", GAME, "Studying medicine"
          + ("; Scratching for roots (heathens)" if k == 1 else ""))
     for k, look in enumerate(("orange flowers", "yellow flowers", "white flowers", "dark leaves", "red berries"))] + [
    Item(36, "Red-topped stalk", UNUSED, _NONE),
    Item(37, "Yellow berry cluster", UNUSED, _NONE),
    Item(38, "Banana", UNUSED, _NONE),
    Item(39, "Mango", UNUSED, _NONE),
    Item(40, "Papaya", UNUSED, _NONE),
    Item(41, "Gold dust", GAME, "Panning for gold"),
    Item(42, "Lit torch", UNUSED, _NONE),
    Item(43, "Debris", UNUSED, _NONE),
    Item(44, "Flat stone", UNUSED, _NONE),
    Item(45, "Red gem", UNUSED, _NONE),
    Item(46, "Dark sphere", UNUSED, _NONE),
    Item(47, "Red striped pot", UNUSED, _NONE),
    Item(48, "Leaves", UNUSED, _NONE),
    Item(49, "Pearl", UNUSED, _NONE),
    Item(50, "Unlit torch", UNUSED, _NONE),
    Item(51, "Irregular pearl", UNUSED, _NONE),
    Item(52, "Hot rock", UNUSED, _NONE),
    Item(53, "Cloth", UNUSED, _NONE),
    Item(54, "Yellow fruit", UNUSED, _NONE),
    Item(55, "Orange fruit", UNUSED, _NONE),
    Item(56, "Flying fish", GAME, "Retrieving a fish"),
    Item(57, "Golden fish", UNUSED, _NONE),
    Item(58, "Soap", UNUSED, _NONE),
    Item(59, "Fish bone", UNUSED, _NONE),
    Item(60, "Heat-treated bone", UNUSED, _NONE),
    Item(61, "Beetle", UNUSED, _NONE),
    Item(62, "Big bowl of noni", UNUSED, "only the never-started action Harvesting noni (the other way) stores it "
                                         "(DEAD)"),
    Item(63, "Lei braid", UNUSED, _NONE),
    Item(64, "Lei", UNUSED, _NONE),
    Item(65, "Lei flower (orange)", UNUSED, _NONE),
    Item(66, "Lei flower (purple)", UNUSED, _NONE),
    Item(67, "Lei flower (white)", UNUSED, _NONE),
    Item(68, "Frog", UNUSED, _NONE),
    Item(69, "Twig nest", UNUSED, _NONE),
    Item(70, "Scientist's necklace piece", GAME, "bringing a necklace piece (The Heathen Chief's necklace)"),
    Item(71, "Farmer's necklace piece", GAME, "bringing a necklace piece"),
    Item(72, "Doctor's necklace piece", GAME, "bringing a necklace piece"),
    Item(73, "Builder's necklace piece", GAME, "bringing a necklace piece"),
    Item(74, "Necklace", GAME, "Bringing necklace to chief"),
    Item(75, "Red dye", GAME, "Putting dye in the pools"),
    Item(76, "Yellow dye", GAME, "Putting dye in the pools"),
    Item(77, "Blue dye", GAME, "Putting dye in the pools"),
    Item(78, "Smelted gold", GAME, "Smelting the gold dust"),
    Item(79, "Golden eye", GAME, "Installing the golden eye (The Blind Totem)"),
]
VV5_COLLECTABLE = 0x50
VV5 += _collection(VV5_COLLECTABLE, "Lab gear", 8, doing="Collecting science item (children)")
VV5 += _collection(VV5_COLLECTABLE + 24, "Relic", 8, doing="Collecting a relic (children)")
VV5 += [
    Item(0x80, "Brown mushroom", GAME, "Picking a mushroom (children)"),
    Item(0x81, "Red mushroom", GAME, "Picking a mushroom (children)"),
    Item(0x82, "Golden Mushroom", PATCHER, "Picking a mushroom (Super-Secret Golden Mushroom)"),
    Item(0x83, "Collectables picture 52", BLANK, "the game refuses it (0x41375B: nothing above 0x82)"),
    Item(0x84, "Collectables picture 53", BLANK, "the game refuses it"),
    Item(0x85, "Collectables picture 54", BLANK, "the game refuses it"),
]

CATALOGUE = {1: VV1, 2: VV2, 3: VV3, 4: VV4, 5: VV5}
NOTHING = {1: 0x13, 2: 0x1A, 3: -1, 4: -1, 5: -1}


def items(game: int) -> list[Item]:
    return CATALOGUE[game]


def item(game: int, value: int) -> Item | None:
    return next((i for i in CATALOGUE[game] if i.value == value), None)


def label(i: Item) -> str:
    if i.status == UNUSED:
        return i.name + UNUSED_MARK
    if i.status == BLANK:
        return i.name + BLANK_MARK
    return i.name


def options(game: int, saved: bool = False) -> tuple:
    """The Carrying choices: Nothing (and, From my save, what the game rebuilds on loading), then the items the
    game carries, the patcher's, and last the unused and blank pictures -- every one, marked."""
    out = [pi.Option(NOTHING[game], "Nothing")]
    if saved:
        out.insert(0, pi.Option(SAVED, "As the game shows it after loading (a baby while expecting)"))
    order = {GAME: 0, PATCHER: 1, UNUSED: 2, BLANK: 3}
    for i in sorted(CATALOGUE[game], key=lambda i: (order[i.status], i.value)):
        out.append(pi.Option(i.value, label(i), patcher=i.status == PATCHER))
    return tuple(out)


def litter_options(values: tuple, saved: bool = False) -> tuple:
    """Babies carried: one, twins, triplets, by the game's own litter values (`values`: one, twins, triplets)."""
    out = [pi.Option(values[0], "One"), pi.Option(values[1], "Twins (the item drawn twice)"),
           pi.Option(values[2], "Triplets (the item drawn three times)")]
    if saved:
        out.insert(0, pi.Option(SAVED, "As in the save"))
    return tuple(out)


def resolve(value, expecting: bool, nothing: int) -> int:
    """A Carrying choice as a carry value: SAVED is what the game rebuilds on loading."""
    if value is None:
        return nothing
    if value == SAVED:
        return BABY if expecting else nothing
    return int(value)


def golden_draw(game: int, x: int, y: int, scale: float = 1.0, alpha: float = 1.0, what: str = "carried",
                sheets=None) -> pi.Draw:
    """The companion's golden picture where the golden frame was drawn at (x, y)."""
    dx, dy = GOLDEN_SHIFT[game]
    try:
        w, h = sheets.size(GOLDEN_FILE) if sheets is not None else GOLDEN_SIZE
    except Exception:  # noqa: BLE001 -- a plan without the art: the shipped picture's size
        w, h = GOLDEN_SIZE
    return pi.Draw(GOLDEN_FILE, (0, 0, w, h), x + dx, y + dy, scale, alpha, what=what)


def golden_bytes() -> bytes | None:
    try:
        return GOLDEN_ART.read_bytes()
    except OSError:
        return None
