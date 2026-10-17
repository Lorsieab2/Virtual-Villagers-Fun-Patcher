"""Every Villager Behaviour the Custom Island Event offers must name the action the game really runs.

The owner reported (VV2) that choosing "Celebrating" made the villager do "Relaxing at the beach".
EXPECTED pins, for each game and each offered behaviour, the label, how the adapter starts it
(the routine for A New Home / The Lost Children, the do-action id for the later games) and the
action text the stock game shows for that action.  Each row was proved from the stock executable:
the routine's own text lookup (or the do-action id's registered handler's lookup) yields `text`,
and the label says the same thing.  The live checks re-derive the text from the stock executable
when it is present (research/stock-executables), so a label cannot drift from the real action.

Row layout: (label, kind, routine-or-action-id, mode, string id, game's action text)
  mode "direct"   the routine/handler looks the text up itself (string id pushed before the lookup call)
  mode "indirect" the text is chosen on a branch (a conditional push), the id is still pushed in the routine
  mode "literal"  the text is a string constant, no table lookup
  mode "effect"   an animation only, the game sets no action text
  mode "none"     not an action starter (stop / recover)
"""
import re
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "vvfp_story_upgrades"
STOCK = ROOT / "research" / "stock-executables"
EXE = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}

EXPECTED = {
    1: [
        ('Stops what they are doing', 'ACT_STOP', 0x439470, 'none', None, None),
        ('Celebrates (Blessings Day dance)', 'ACT_CALL_ARG', 0x443fa0, 'direct', 190, 'Celebrating'),
        ('Goes swimming', 'ACT_CALL_ARG', 0x444990, 'direct', 195, 'Going swimming'),
        ('Relaxes', 'ACT_CALL', 0x4410c0, 'direct', 600, 'Relaxing'),
        ('Recovers fully (cured, full health)', 'ACT_RECOVER', 0x0, 'none', None, None),
        ('Dances', 'ACT_CALL', 0x43f200, 'direct', 582, 'Dancing'),
        ('Rain dancing', 'ACT_CALL', 0x4419a0, 'direct', 159, 'Rain dancing'),
        ('Makes a party', 'ACT_CALL', 0x440590, 'direct', 594, 'Making a party'),
        ('Exercises', 'ACT_CALL', 0x4411d0, 'direct', 156, 'Exercising'),
        ('Does the laundry', 'ACT_CALL', 0x441a50, 'direct', 160, 'Laundry'),
        ('Observes', 'ACT_CALL', 0x4408a0, 'direct', 595, 'Observing'),
        ('Unsure what to do (wanders)', 'ACT_CALL', 0x445ad0, 'direct', 211, 'Unsure what to do'),
        ('Goes indoors', 'ACT_CALL', 0x439de0, 'direct', 177, 'Going indoors'),
        ('Runs away', 'ACT_CALL', 0x439ef0, 'direct', 178, 'Running away'),
        ('Shakes their head', 'ACT_CALL', 0x43a040, 'direct', 212, 'Shaking head'),
        ('Not feeling well (only looks it)', 'ACT_CALL', 0x441cc0, 'direct', 168, 'Not feeling well'),
        ('Honors the dead', 'ACT_CALL', 0x4401e0, 'direct', 592, 'Honoring the Dead'),
        ('Honors the Idol (once it is carved)', 'ACT_CALL', 0x442810, 'direct', 173, 'Honoring the Idol'),
        ('Honors the temple (once it is restored)', 'ACT_CALL', 0x443d50, 'direct', 189, 'Honoring the temple'),
        ('Sees something unusual', 'ACT_CALL', 0x441750, 'direct', 158, 'Sees something unusual...'),
        ('Curious about the rock', 'ACT_CALL', 0x43ed50, 'direct', 580, 'Curious about the rock'),
        ('Curious about the ruins', 'ACT_CALL', 0x43ef10, 'direct', 581, 'Curious about the ruins'),
        ('Curious about the creek', 'ACT_CALL', 0x441620, 'direct', 157, 'Curious about the creek'),
        ('Curious about the field', 'ACT_CALL', 0x442e80, 'direct', 179, 'Curious about the field'),
        ('Curious about the cactus', 'ACT_CALL', 0x445670, 'direct', 206, 'Curious about the cactus'),
        ('Tries to push the boulder (no progress)', 'ACT_CALL', 0x440fa0, 'direct', 599, 'Trying to push the boulder'),
        ('Enjoys the lagoon', 'ACT_CALL', 0x43ff80, 'direct', 590, 'Enjoying the lagoon'),
        ('Enjoys the garden (once it is grown)', 'ACT_CALL', 0x442db0, 'direct', 176, 'Enjoying the garden'),
        ('Admires the treasure (once it is found)', 'ACT_CALL', 0x4404b0, 'direct', 593, 'Admiring the treasure'),
        ('Chases butterflies', 'ACT_CALL', 0x445840, 'direct', 207, 'Chasing butterflies'),
        ('Drinks well water', 'ACT_CALL', 0x444b40, 'direct', 197, 'Drinking well water'),
        ('Forages (Farming practice, food)', 'ACT_CALL', 0x441e10, 'direct', 169, 'Foraging'),
        ('Plants or harvests crops (Farming practice)', 'ACT_CALL', 0x4439f0, 'indirect', 187, 'Planting crops'),
        ('Waters the crops (Farming practice)', 'ACT_CALL', 0x445020, 'direct', 201, 'Watering crops'),
        ('Fishes (Farming practice, food; stock needs fishing)', 'ACT_CALL', 0x43f450, 'direct', 585, 'Fishing'),
        ('Eats (uses food, restores health)', 'ACT_CALL', 0x43fad0, 'direct', 587, 'Eating'),
        ('Fixes a hut (Building practice)', 'ACT_CALL', 0x440ad0, 'direct', 597, 'Fixing hut'),
        ('Heals someone (Healing practice, cures nobody)', 'ACT_CALL', 0x445580, 'direct', 205, 'Healing someone'),
        ('Goes to school (children; stock needs the school)', 'ACT_CALL', 0x444aa0, 'direct', 196, 'Going to school'),
    ],
    2: [
        ('Stops what they are doing', 'ACT_STOP', 0x4492a0, 'none', None, None),
        ('Enjoys the pond (Heat Wave swim)', 'ACT_CALL', 0x451690, 'direct', 845, 'Enjoying the pond'),
        ('Relaxes at the beach (Blessings Day)', 'ACT_CALL', 0x452920, 'direct', 834, 'Relaxing at the beach'),
        ('Honors the dead (Day of Honor)', 'ACT_CALL', 0x454890, 'direct', 847, 'Honoring the Dead'),
        ('Sneezes', 'ACT_EFFECT', 0x44af20, 'effect', None, None),
        ('Recovers fully (cured, full health)', 'ACT_RECOVER', 0x0, 'none', None, None),
        ('Does something of their own choosing', 'ACT_CALL', 0x461850, 'direct', 213, 'Nothing'),
        ('Dances', 'ACT_CALL', 0x450580, 'direct', 833, 'Dancing'),
        ('Dances in a circle (a long dance)', 'ACT_CALL', 0x4530e0, 'direct', 833, 'Dancing'),
        ('Rain dancing', 'ACT_CALL', 0x455a20, 'direct', 227, 'Rain dancing'),
        ('Jumpy!', 'ACT_CALL', 0x455ac0, 'direct', 236, 'Jumpy!'),
        ('Enjoys the pond', 'ACT_CALL', 0x45f420, 'direct', 845, 'Enjoying the pond'),
        ('Goes swimming', 'ACT_CALL_ARG', 0x45c1b0, 'direct', 306, 'Going swimming'),
        ('Relaxes at the beach', 'ACT_CALL', 0x451e10, 'direct', 834, 'Relaxing at the beach'),
        ('Relaxes', 'ACT_CALL', 0x454ab0, 'direct', 859, 'Relaxing'),
        ('Reflects', 'ACT_CALL', 0x4523a0, 'direct', 840, 'Reflecting'),
        ('Exercises (Building practice)', 'ACT_CALL', 0x455330, 'direct', 219, 'Exercising'),
        ('Gets a drink', 'ACT_CALL', 0x453430, 'direct', 842, 'Getting a drink'),
        ('Cools their feet in the stream', 'ACT_CALL', 0x453a70, 'direct', 347, 'Cooling feet in stream'),
        ('Does the laundry', 'ACT_CALL', 0x453d10, 'direct', 228, 'Doing laundry'),
        ('Listens to a story', 'ACT_CALL', 0x44a0e0, 'direct', 311, 'Listening to a story'),
        ('Tells a story (Parenting practice)', 'ACT_CALL', 0x449f40, 'direct', 310, 'Telling a story'),
        ('Thinking', 'ACT_CALL', 0x44fe10, 'direct', 829, 'Thinking'),
        ('Unsure what to do (wanders)', 'ACT_CALL', 0x45e700, 'direct', 322, 'Unsure what to do'),
        ('Nature is calling!', 'ACT_CALL', 0x45cd00, 'direct', 216, 'Nature is calling!'),
        ('A little bit lonely', 'ACT_CALL', 0x45cdc0, 'literal', None, 'A little bit lonely'),
        ('Goes indoors', 'ACT_CALL', 0x44a240, 'direct', 250, 'Going indoors'),
        ('Runs away', 'ACT_CALL', 0x44b010, 'direct', 256, 'Running away'),
        ('Shakes their head', 'ACT_CALL', 0x44b1b0, 'direct', 323, 'Shaking head'),
        ('Not feeling well (only looks it)', 'ACT_CALL', 0x45c590, 'direct', 235, 'Not feeling well'),
        ('Recovers at the hospital', 'ACT_CALL', 0x45c250, 'direct', 145, 'Recovering at the hospital'),
        ('Admires the ancient mosaic', 'ACT_CALL', 0x457aa0, 'direct', 245, 'Admiring the ancient mosaic'),
        ('Admires the ancient gong encasement', 'ACT_CALL', 0x459710, 'direct', 267, 'Admiring the ancient gong encasement'),
        ('Observes the Gong of Wonder', 'ACT_CALL', 0x459980, 'direct', 269, 'Observing the Gong of Wonder'),
        ('Reads the writings on the wall', 'ACT_CALL', 0x459a50, 'direct', 270, 'Reading the writings on the wall'),
        ('Curious about the thorny bushes', 'ACT_CALL', 0x4501f0, 'direct', 831, 'Curious about the thorny bushes'),
        ('Curious about the ancient place', 'ACT_CALL', 0x4503c0, 'direct', 832, 'Curious about the ancient place'),
        ('Curious about the vines', 'ACT_CALL', 0x454f50, 'direct', 223, 'Curious about the vines'),
        ('Curious about the patch of soil', 'ACT_CALL', 0x455030, 'direct', 224, 'Curious about the patch of soil'),
        ('Curious about the strange flower', 'ACT_CALL', 0x45d670, 'direct', 317, 'Curious about the strange flower'),
        ('Tries to reach the coconuts (children)', 'ACT_CALL', 0x454bc0, 'direct', 222, 'Trying to reach coconuts'),
        ('Plays in the very narrow stream (children)', 'ACT_CALL', 0x454d40, 'direct', 220, 'Playing in the very narrow stream'),
        ('Looks at the dry shrubs (children)', 'ACT_CALL', 0x454e40, 'direct', 221, 'Looking at the dry shrubs'),
        ('Looks at the fire (children)', 'ACT_CALL', 0x455170, 'direct', 225, 'Looking at the fire'),
        ('Fishes (Farming practice, food)', 'ACT_CALL', 0x4507a0, 'indirect', 837, 'Fishing'),
        ('Harvests coconuts (Farming practice, food)', 'ACT_CALL', 0x456f70, 'direct', 241, 'Harvesting coconuts'),
        ('Plants or harvests crops (Farming practice)', 'ACT_CALL', 0x4593d0, 'indirect', 265, 'Planting crops'),
        ('Waters the crops (Farming practice)', 'ACT_CALL', 0x45d280, 'direct', 312, 'Watering crops'),
        ('Eats (uses food)', 'ACT_CALL', 0x4513f0, 'direct', 839, 'Eating'),
    ],
    3: [
        ('Stops what they are doing', 'ACT_STOP', 0, 'none', None, None),
        ('Recovers fully (cured, full health)', 'ACT_RECOVER', 0, 'none', None, None),
        ('Dances', 'ACT_DO', 8, 'direct', 1142, 'Dancing'),
        ('Dances (another dance)', 'ACT_DO', 85, 'direct', 1142, 'Dancing'),
        ('Secretly practices a dance', 'ACT_DO', 181, 'direct', 563, 'Secretly practicing a dance'),
        ('Performs the ceremonial dance', 'ACT_DO', 67, 'direct', 361, 'Performing ceremonial dance'),
        ('Rain dancing', 'ACT_DO', 12, 'direct', 276, 'Rain dancing'),
        ('Celebrates Isola Day', 'ACT_DO', 66, 'direct', 369, 'Celebrating Isola Day'),
        ('Relaxes', 'ACT_DO', 13, 'direct', 1168, 'Relaxing'),
        ('Relaxes at the beach', 'ACT_DO', 21, 'direct', 1143, 'Relaxing at the beach'),
        ('Reflects', 'ACT_DO', 22, 'direct', 1149, 'Reflecting'),
        ('Watches the clouds', 'ACT_DO', 18, 'direct', 1145, 'Watching the clouds'),
        ('Goes swimming', 'ACT_DO', 1, 'direct', 340, 'Going swimming'),
        ('Enjoys the bath', 'ACT_DO', 23, 'direct', 1154, 'Enjoying the bath'),
        ('Bathes', 'ACT_DO', 143, 'direct', 493, 'Bathing'),
        ('Cools their feet in the stream', 'ACT_DO', 19, 'direct', 396, 'Cooling feet in stream'),
        ('Washes their face', 'ACT_DO', 140, 'direct', 491, 'Washing face'),
        ('Washes their hands', 'ACT_DO', 141, 'direct', 492, 'Washing hands'),
        ('Gets a drink', 'ACT_DO', 144, 'direct', 1151, 'Getting a drink'),
        ('Drinks the rain', 'ACT_DO', 60, 'direct', 364, 'Drinking rain'),
        ('Gets out of the rain', 'ACT_DO', 142, 'direct', 475, 'Getting out of the rain'),
        ('Cleans up after the rain', 'ACT_DO', 196, 'direct', 462, 'Cleaning up after the rain'),
        ('Washes the laundry', 'ACT_DO', 61, 'direct', 365, 'Washing the laundry'),
        ('Looks at the fishies', 'ACT_DO', 146, 'direct', 494, 'Looking at fishies'),
        ('Looks at the fire', 'ACT_DO', 34, 'direct', 274, 'Looking at the fire'),
        ('Honors the dead', 'ACT_DO', 10, 'direct', 1156, 'Honoring the Dead'),
        ('Stomps ants', 'ACT_DO', 68, 'direct', 359, 'Stomping ants'),
        ('Hides in a hut', 'ACT_DO', 69, 'direct', 360, 'Hiding in hut'),
        ('Acts sinister', 'ACT_DO', 62, 'direct', 366, 'Acting sinister'),
        ('Jumpy!', 'ACT_DO', 93, 'direct', 285, 'Jumpy!'),
        ('Nature is calling!', 'ACT_DO', 94, 'direct', 264, 'Nature is calling!'),
        ('A little bit lonely', 'ACT_DO', 102, 'direct', 527, 'A little bit lonely'),
        ('Unsure what to do (wanders)', 'ACT_DO', 123, 'direct', 370, 'Unsure what to do'),
        ('Sits', 'ACT_DO', 52, 'direct', 1144, 'Sitting'),
        ('Shakes their head', 'ACT_DO', 49, 'direct', 371, 'Shaking head'),
        ('Not feeling well (only looks it)', 'ACT_DO', 45, 'direct', 284, 'Not feeling well'),
        ('Recovers at the hospital', 'ACT_DO', 97, 'direct', 161, 'Recovering at the hospital'),
        ('Feels faint (only looks it)', 'ACT_DO', 152, 'direct', 466, 'Feeling faint'),
        ('Tries to get warm', 'ACT_DO', 153, 'direct', 448, 'Trying to get warm'),
        ('Tries to cool off', 'ACT_DO', 154, 'direct', 446, 'Trying to cool off'),
        ('Itchy', 'ACT_DO', 155, 'direct', 465, 'Itchy'),
        ('Needs to lie down', 'ACT_DO', 158, 'direct', 549, 'Needs to lie down'),
        ('Needs to sit down', 'ACT_DO', 159, 'direct', 550, 'Needs to sit down'),
        ('Has an epiphany', 'ACT_DO', 160, 'direct', 450, 'Having an epiphany'),
        ('In a trance', 'ACT_DO', 161, 'direct', 449, 'In a trance'),
        ('Stinky breath!', 'ACT_DO', 182, 'direct', 454, 'Stinky breath!'),
        ('Hic!', 'ACT_DO', 184, 'direct', 456, 'Hic!'),
        ('Blannesamagawa loomajoobamooga!!', 'ACT_DO', 191, 'direct', 459, 'Blannesamagawa loomajoobamooga!!'),
        ('Who turned out the lights?!', 'ACT_DO', 192, 'direct', 458, 'Who turned out the lights?!'),
        ('Something smells YUMMY!', 'ACT_DO', 193, 'direct', 460, 'Something smells YUMMY!'),
        ('Listens to a story (children)', 'ACT_DO', 96, 'direct', 344, 'Listening to a story'),
        ('Watches people work (children)', 'ACT_DO', 106, 'direct', 531, 'Watching people work'),
        ('Runs around (children)', 'ACT_DO', 148, 'direct', 497, 'Running around'),
        ('Plays (children)', 'ACT_DO', 151, 'direct', 488, 'Playing'),
        ('Plays in puddles (children)', 'ACT_DO', 180, 'direct', 554, 'Playing in puddles'),
        ('Plays in the dirt (children)', 'ACT_DO', 190, 'direct', 457, 'Playing in the dirt'),
        ('Makes sandcastles (children)', 'ACT_DO', 195, 'direct', 463, 'Making sandcastles'),
        ('Fishes (Farming practice, food)', 'ACT_DO', 11, 'direct', 1146, 'Fishing'),
        ('Researches (Research practice, tech points)', 'ACT_DO', 3, 'direct', 297, 'Researching'),
        ('Does exercise (Building practice)', 'ACT_DO', 150, 'direct', 498, 'Doing exercise'),
        ('Eats (uses food, heals a little)', 'ACT_DO', 84, 'direct', 1148, 'Eating'),
    ],
    4: [
        ('Stops what they are doing', 'ACT_STOP', 0, 'none', None, None),
        ('Recovers fully (cured, full health)', 'ACT_RECOVER', 0, 'none', None, None),
        ('Dances', 'ACT_DO', 7, 'direct', 1121, 'Dancing'),
        ('Dances (another dance)', 'ACT_DO', 45, 'direct', 1121, 'Dancing'),
        ('Rain dancing', 'ACT_DO', 10, 'direct', 379, 'Rain dancing'),
        ('Celebrates Isola Day', 'ACT_DO', 40, 'direct', 459, 'Celebrating Isola Day'),
        ('Celebrates the Banyan Festival', 'ACT_DO', 193, 'direct', 460, 'Celebrating Banyan Festival'),
        ('Relaxes', 'ACT_DO', 11, 'direct', 1148, 'Relaxing'),
        ('Relaxes at the beach', 'ACT_DO', 22, 'direct', 1122, 'Relaxing at the beach'),
        ('Reflects', 'ACT_DO', 23, 'direct', 1129, 'Reflecting'),
        ('Watches the clouds', 'ACT_DO', 19, 'direct', 1125, 'Watching the clouds'),
        ('Enjoys the pond', 'ACT_DO', 24, 'direct', 1138, 'Enjoying the pond'),
        ('Swims in the ocean', 'ACT_DO', 195, 'direct', 4, 'Swimming in the ocean'),
        ('Takes a shower', 'ACT_DO', 185, 'direct', 1133, 'Taking a shower'),
        ('Cools their feet in the stream', 'ACT_DO', 20, 'direct', 487, 'Cooling feet in the stream'),
        ('Drinks from the stream', 'ACT_DO', 134, 'direct', 94, 'Drinking from stream'),
        ('Gets a drink', 'ACT_DO', 21, 'direct', 1135, 'Getting a drink'),
        ('Drinks the rain', 'ACT_DO', 36, 'direct', 454, 'Drinking rain'),
        ('Gets out of the rain', 'ACT_DO', 68, 'direct', 597, 'Getting out of the rain'),
        ('Cleans up after the rain', 'ACT_DO', 98, 'direct', 556, 'Cleaning up after the rain'),
        ('Washes the laundry', 'ACT_DO', 37, 'direct', 455, 'Washing the laundry'),
        ('Honors the dead', 'ACT_DO', 9, 'direct', 1140, 'Honoring the Dead'),
        ('Admires a lei in the tree', 'ACT_DO', 158, 'direct', 59, 'Admiring a lei in the tree'),
        ('Wanders around', 'ACT_DO', 48, 'direct', 279, 'Wandering around'),
        ('Unsure what to do', 'ACT_DO', 66, 'direct', 461, 'Unsure what to do'),
        ('Jumpy!', 'ACT_DO', 50, 'direct', 388, 'Jumpy!'),
        ('Nature is calling!', 'ACT_DO', 51, 'direct', 367, 'Nature is calling!'),
        ('A little bit lonely', 'ACT_DO', 58, 'direct', 615, 'A little bit lonely'),
        ('Sits', 'ACT_DO', 34, 'direct', 1123, 'Sitting'),
        ('Shakes their head', 'ACT_DO', 32, 'direct', 462, 'Shaking head'),
        ('Not feeling well (only looks it)', 'ACT_DO', 27, 'direct', 387, 'Not feeling well'),
        ('Feels faint (only looks it)', 'ACT_DO', 72, 'direct', 569, 'Feeling faint'),
        ('Tries to get warm', 'ACT_DO', 73, 'direct', 540, 'Trying to get warm'),
        ('Tries to cool off', 'ACT_DO', 74, 'direct', 538, 'Trying to cool off'),
        ('Itchy', 'ACT_DO', 75, 'direct', 568, 'Itchy'),
        ('Needs to lie down', 'ACT_DO', 78, 'direct', 626, 'Needs to lie down'),
        ('Needs to sit down', 'ACT_DO', 79, 'direct', 627, 'Needs to sit down'),
        ('Has an epiphany', 'ACT_DO', 80, 'direct', 542, 'Having an epiphany'),
        ('In a trance', 'ACT_DO', 81, 'direct', 541, 'In a trance'),
        ('Hic!', 'ACT_DO', 90, 'direct', 548, 'Hic!'),
        ('That tasted soapy!', 'ACT_DO', 89, 'direct', 547, 'That tasted soapy!'),
        ('Runs away from wasps!', 'ACT_DO', 198, 'direct', 315, 'Running away from wasps!'),
        ('Curious about the carvings', 'ACT_DO', 200, 'direct', 13, 'Curious about the carvings'),
        ('Curious about the majestic fish statue', 'ACT_DO', 202, 'direct', 11, 'Curious about the majestic fish statue'),
        ('Curious about the hole in the tree', 'ACT_DO', 199, 'direct', 14, 'Curious about the hole in the tree'),
        ('Tells a story', 'ACT_DO', 52, 'direct', 445, 'Telling a story'),
        ('Listens to a story (children)', 'ACT_DO', 53, 'direct', 446, 'Listening to a story'),
        ('Watches people work (children)', 'ACT_DO', 61, 'direct', 618, 'Watching people work'),
        ('Runs around (children)', 'ACT_DO', 70, 'direct', 607, 'Running around'),
        ('Plays in puddles (children)', 'ACT_DO', 88, 'direct', 630, 'Playing in puddles'),
        ('Plays in the dirt (children)', 'ACT_DO', 95, 'direct', 549, 'Playing in the dirt'),
        ('Makes sandcastles (children)', 'ACT_DO', 97, 'direct', 557, 'Making sandcastles'),
        ('Races! (children)', 'ACT_DO', 191, 'direct', 23, 'Racing!'),
        ('Researches (Research practice, tech points)', 'ACT_DO', 2, 'direct', 397, 'Researching'),
        ('Harvests blackberries (Farming practice, food)', 'ACT_DO', 99, 'direct', 640, 'Harvesting blackberries'),
        ('Does exercise (Building practice)', 'ACT_DO', 71, 'direct', 608, 'Doing exercise'),
        ('Eats (uses food)', 'ACT_DO', 44, 'direct', 1128, 'Eating'),
    ],
    5: [
        ('Stops what they are doing', 'ACT_STOP', 0, 'none', None, None),
        ('Recovers fully (cured, full health)', 'ACT_RECOVER', 0, 'none', None, None),
        ('Dances', 'ACT_DO', 15, 'direct', 1211, 'Dancing'),
        ('Dances (another dance)', 'ACT_DO', 223, 'direct', 1211, 'Dancing'),
        ('Rain dancing', 'ACT_DO', 18, 'direct', 334, 'Rain dancing'),
        ('Celebrates Isola Day', 'ACT_DO', 47, 'direct', 413, 'Celebrating Isola Day'),
        ('Celebrates mushrooms', 'ACT_DO', 117, 'direct', 1212, 'Celebrating mushrooms'),
        ('Relaxes', 'ACT_DO', 19, 'direct', 1247, 'Relaxing'),
        ('Praises', 'ACT_DO', 42, 'direct', 341, 'Praising'),
        ('Watches the clouds', 'ACT_DO', 134, 'direct', 1217, 'Watching the clouds'),
        ('Goes swimming', 'ACT_DO', 1, 'direct', 393, 'Going swimming'),
        ('Enjoys the waterfall', 'ACT_DO', 34, 'direct', 1231, 'Enjoying the waterfall'),
        ('Enjoys the lake', 'ACT_DO', 30, 'direct', 1230, 'Enjoying the lake'),
        ('Strolls around the lake', 'ACT_DO', 28, 'direct', 327, 'Strolling around the lake'),
        ('Bathes', 'ACT_DO', 152, 'direct', 527, 'Bathing'),
        ('Cools their feet in the stream', 'ACT_DO', 26, 'direct', 441, 'Cooling feet in the stream'),
        ('Washes up in the stream', 'ACT_DO', 211, 'direct', 845, 'Washing up in the stream'),
        ('Drinks the rain', 'ACT_DO', 43, 'direct', 409, 'Drinking rain'),
        ('Gets out of the rain', 'ACT_DO', 74, 'direct', 521, 'Getting out of the rain'),
        ('Cleans up after the rain', 'ACT_DO', 107, 'direct', 508, 'Cleaning up after the rain'),
        ('Washes the laundry', 'ACT_DO', 44, 'direct', 410, 'Washing the laundry'),
        ('Honors the dead', 'ACT_DO', 17, 'direct', 1233, 'Honoring the dead'),
        ('Wanders around', 'ACT_DO', 55, 'direct', 260, 'Wandering around'),
        ('Unsure what to do', 'ACT_DO', 72, 'direct', 414, 'Unsure what to do'),
        ('A little bit lonely', 'ACT_DO', 65, 'direct', 539, 'A little bit lonely'),
        ('Nature is calling!', 'ACT_DO', 162, 'direct', 324, 'Nature is calling!'),
        ('Shakes their head', 'ACT_DO', 37, 'direct', 415, 'Shaking head'),
        ('Runs away', 'ACT_DO', 9, 'direct', 360, 'Running away'),
        ('Annoyed by the bees', 'ACT_DO', 10, 'direct', 809, 'Annoyed by the bees'),
        ('Hides from lightning', 'ACT_DO', 158, 'direct', 824, 'Hiding from lightning'),
        ('Hides in the water', 'ACT_DO', 170, 'direct', 799, 'Hiding in the water'),
        ('Escapes from foulness', 'ACT_DO', 209, 'direct', 826, 'Escaping from foulness'),
        ('Plays with butterflies!', 'ACT_DO', 229, 'direct', 365, 'Playing with butterflies!'),
        ('Chases fish', 'ACT_DO', 234, 'direct', 567, 'Chasing fish'),
        ('Excited about the puddles', 'ACT_DO', 235, 'direct', 568, 'Excited about the puddles'),
        ('Curious about the pools', 'ACT_DO', 200, 'direct', 573, 'Curious about the pools'),
        ('Curious about the hidden grove', 'ACT_DO', 202, 'direct', 575, 'Curious about the hidden grove'),
        ('Curious about the aqueduct', 'ACT_DO', 203, 'direct', 580, 'Curious about the aqueduct'),
        ('Curious about the cave', 'ACT_DO', 205, 'direct', 583, 'Curious about the cave'),
        ('Does exercise', 'ACT_DO', 78, 'direct', 532, 'Doing exercise'),
        ('Health chanting (Healing practice)', 'ACT_DO', 103, 'direct', 804, 'Health chanting'),
        ('Listens to a story (children)', 'ACT_DO', 60, 'direct', 399, 'Listening to a story'),
        ('Watches people work (children)', 'ACT_DO', 68, 'direct', 542, 'Watching people work'),
        ('Jumpy! (children)', 'ACT_DO', 57, 'direct', 344, 'Jumpy!'),
        ('Runs around (children)', 'ACT_DO', 77, 'direct', 531, 'Running around'),
        ('Plays in puddles (children)', 'ACT_DO', 94, 'direct', 553, 'Playing in puddles'),
        ('Plays in the dirt (children)', 'ACT_DO', 104, 'direct', 504, 'Playing in the dirt'),
        ('Races! (children)', 'ACT_DO', 131, 'direct', 45, 'Racing!'),
        ('Researches (Research practice, tech points)', 'ACT_DO', 4, 'direct', 355, 'Researching'),
        ('Harvests noni (Farming practice, food)', 'ACT_DO', 108, 'direct', 562, 'Harvesting noni'),
        ('Eats (uses food)', 'ACT_DO', 51, 'direct', 1220, 'Eating'),
    ],
}

# A label and the game's text may differ in wording (a verb for a gerund) but never in meaning.
# These are the labels whose text the owner's report or this audit corrected.
CORRECTED = {
    (1, "Celebrates (Blessings Day dance)"): "Celebrating",
    (2, "Enjoys the pond (Heat Wave swim)"): "Enjoying the pond",
    (2, "Relaxes at the beach (Blessings Day)"): "Relaxing at the beach",
    (2, "Honors the dead (Day of Honor)"): "Honoring the Dead",
}
# Old labels that named an action the game does not run for that routine.
RETIRED = {
    (1, "Dances (Blessings Day)"), (2, "Celebrates"), (2, "Cools off with a swim"), (2, "Visits the graves"),
}


def adapter_rows(game: int):
    source = (SOURCE / f"story_c{game}.inc").read_text(encoding="utf-8")
    body = source[source.index(f"static const ce_action C{game}_BEHAVIOURS[] = {{"):]
    body = body[:body.index("};")]
    rows = re.findall(r'\{ "((?:[^"\\]|\\.)*)", (ACT_[A-Z_]+), (0x[0-9A-Fa-f]+u?|0), (0x[0-9A-Fa-f]+|\d+) \}', body)
    out = []
    for label, kind, routine, arg in rows:
        routine = int(routine.rstrip("u"), 16)
        out.append((label, kind, routine if game <= 2 else int(arg, 0)))
    return out


def expected_keys(game: int):
    return [(label, kind, key if kind not in ("ACT_STOP", "ACT_RECOVER") else (key if game <= 2 else 0))
            for label, kind, key, *_ in EXPECTED[game]]


@pytest.mark.parametrize("game", [1, 2, 3, 4, 5])
def test_every_offered_behaviour_is_pinned_with_its_real_action(game):
    got = adapter_rows(game)
    want = [(label, kind, key) for label, kind, key, *_ in EXPECTED[game]]
    # VV3-VV5 stop/recover rows carry routine 0 and arg 0; VV1/VV2 stop rows carry the stop routine.
    norm = lambda rows: [(l, k, key if k not in ("ACT_RECOVER",) else 0) for l, k, key in rows]
    if game >= 3:
        norm = lambda rows: [(l, k, key if k == "ACT_DO" else 0) for l, k, key in rows]
    assert norm(got) == norm(want), f"VV{game}: the offered behaviours differ from the audited table"


@pytest.mark.parametrize("game", [1, 2, 3, 4, 5])
def test_corrected_labels_replaced_the_wrong_ones(game):
    labels = {row[0] for row in EXPECTED[game]}
    for (g, label), text in CORRECTED.items():
        if g == game:
            assert label in labels
            assert any(r[0] == label and r[5] == text for r in EXPECTED[game])
    for g, label in RETIRED:
        if g == game:
            assert label not in {l for l, _, _ in adapter_rows(game)}, f"VV{game}: {label!r} named the wrong action"


@pytest.mark.parametrize("game", [1, 2, 3, 4, 5])
def test_no_two_labels_in_a_game_are_the_same(game):
    labels = [l for l, _, _ in adapter_rows(game)]
    assert len(labels) == len(set(labels))


def test_the_owner_report_is_fixed_in_the_lost_children():
    labels = {l: k for l, _, k in adapter_rows(2)}
    # The Blessings Day routine 0x452920 shows "Relaxing at the beach"; no label may call it celebrating.
    name = [l for l, _, k in adapter_rows(2) if k == 0x452920]
    assert name == ["Relaxes at the beach (Blessings Day)"]
    assert "Celebrates" not in labels


# ---- live: re-derive each text from the stock executable --------------------------------------
def _stock(game):
    path = STOCK / f"Virtual Villagers - {EXE[game]}.exe"
    if not path.is_file():
        pytest.skip(f"stock executable not available: {path.name}")
    pefile = pytest.importorskip("pefile")
    capstone = pytest.importorskip("capstone")
    pe = pefile.PE(str(path))
    return pe, pe.OPTIONAL_HEADER.ImageBase, capstone


def _cstr(pe, base, va, n=200):
    try:
        return pe.get_data(va - base, n).split(b"\0")[0].decode("latin1")
    except Exception:
        return None


def _func(pe, base, capstone, va):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    data = pe.get_data(va - base, 12000)
    out = []
    for i in md.disasm(data, va):
        out.append(i)
        if i.mnemonic.startswith("ret") and len(out) > 3 and data[i.address + i.size - va:i.address + i.size - va + 1] in (b"\x90", b"\xcc"):
            break
        if len(out) > 1500:
            break
    return out


def _pushes_before_calls(ins, getters, window):
    ids = []
    for k, i in enumerate(ins):
        if i.mnemonic == "call" and i.op_str.startswith("0x") and int(i.op_str, 16) in getters:
            pj = [w for w in ins[max(0, k - window):k] if w.mnemonic == "push"]
            if pj:
                try:
                    ids.append(int(pj[-1].op_str, 0))
                except ValueError:
                    pass
    return ids


def _all_pushes(ins):
    out = set()
    for i in ins:
        if i.mnemonic == "push":
            try:
                out.add(int(i.op_str, 0))
            except ValueError:
                pass
    return out


@pytest.mark.parametrize("game", [1, 2])
def test_vv1_vv2_routines_show_the_pinned_text(game):
    pe, base, capstone = _stock(game)
    if game == 1:
        tab = {}
        for i in range(0x275):
            sid, p0, *_ = struct.unpack("<5I", pe.get_data(0x487208 - base + i * 20, 20))
            tab[sid] = _cstr(pe, base, p0)
        getters = {0x433970, 0x433880}
    else:
        tab = {}
        for i in range(0x36C):
            sid, p0, _p1 = struct.unpack("<III", pe.get_data(0x496300 - base + i * 12, 12))
            tab[sid] = _cstr(pe, base, p0)
        getters = {0x441680, 0x4415A0}
    for label, kind, routine, mode, sid, text in EXPECTED[game]:
        if mode == "none":
            continue
        ins = _func(pe, base, capstone, routine)
        found = _pushes_before_calls(ins, getters, 2)
        if mode == "direct":
            assert sid in found, f"VV{game} {label!r}: {routine:#x} never looks up string {sid}"
        elif mode == "indirect":
            assert sid in _all_pushes(ins), f"VV{game} {label!r}: {routine:#x} never uses string {sid}"
        elif mode == "literal":
            lits = {_cstr(pe, base, v) for v in _all_pushes(ins) if 0x400000 < v < 0x1000000}
            assert text in lits, f"VV{game} {label!r}: no literal {text!r}"
        elif mode == "effect":
            assert not found, f"VV{game} {label!r}: an effect routine that sets text"
        if mode in ("direct", "indirect"):
            assert tab[sid] == text, f"VV{game} {label!r}: string {sid} is {tab[sid]!r}, not {text!r}"


def _later_games_tables(pe, base, capstone):
    """The string table {id: (name, text)} and the do-action registrations {action id: handler}."""
    d = pe.__data__
    secs = [(s.PointerToRawData, s.PointerToRawData + s.SizeOfRawData) for s in pe.sections
            if s.Name.startswith((b".rdata", b".data"))]
    lo, hi = min(a for a, _ in secs), max(b for _, b in secs)

    def off(p):
        try:
            o = pe.get_offset_from_rva(p - base)
        except Exception:
            return None
        return o if 0 <= o < len(d) else None

    texts = {}
    for o in range(lo, hi - 16, 4):
        sid, pn, pt, _alt = struct.unpack_from("<IIII", d, o)
        if not (0 < sid < 4000 and 0x400000 < pn < 0x1000000 and 0x400000 < pt < 0x1000000):
            continue
        on, ot = off(pn), off(pt)
        if on is None or ot is None:
            continue
        name = d[on:on + 64].split(b"\0")[0]
        if re.fullmatch(rb"e[A-Z][A-Za-z0-9_]{3,60}", name):
            texts[sid] = (name.decode(), d[ot:ot + 200].split(b"\0")[0].decode("latin1"))

    text_sec = [s for s in pe.sections if s.Name.startswith(b".text")][0]
    data = pe.get_data(text_sec.VirtualAddress, text_sec.Misc_VirtualSize)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    ins, pos, start = [], 0, base + text_sec.VirtualAddress
    while pos < len(data):
        progressed = False
        for i in md.disasm(data[pos:], start + pos):
            ins.append(i)
            pos = i.address + i.size - start
            progressed = True
        if not progressed:
            pos += 1
    cand = {}
    for k in range(2, len(ins)):
        i = ins[k]
        if i.mnemonic != "call" or ins[k - 1].mnemonic != "push" or ins[k - 2].mnemonic != "push":
            continue
        try:
            target = int(i.op_str, 16)
            func = int(ins[k - 2].op_str, 0)
        except ValueError:
            continue
        if not 0x401000 <= func < 0x4A0000:
            continue
        try:
            aid = int(ins[k - 1].op_str, 0)
        except ValueError:
            aid = 0 if ins[k - 1].op_str in ("edx", "eax", "ecx", "ebx", "esi", "edi") else None
        if aid is None or not 0 <= aid <= 400:
            continue
        cand.setdefault(target, {})[aid] = func
    return texts, max(cand.values(), key=len)


GETTER = {3: 0x42F190, 4: 0x44D3D0, 5: 0x4506D0}


@pytest.mark.parametrize("game", [3, 4, 5])
def test_do_action_handlers_show_the_pinned_text(game):
    pe, base, capstone = _stock(game)
    texts, handlers = _later_games_tables(pe, base, capstone)
    for label, kind, aid, mode, sid, text in EXPECTED[game]:
        if mode == "none":
            continue
        assert aid in handlers, f"VV{game} {label!r}: action {aid} has no registered handler"
        ins = _func(pe, base, capstone, handlers[aid])
        found = _pushes_before_calls(ins, {GETTER[game]}, 8)
        assert sid in found, f"VV{game} {label!r}: action {aid} never looks up string {sid}"
        assert texts[sid][1] == text, f"VV{game} {label!r}: string {sid} is {texts[sid][1]!r}, not {text!r}"
