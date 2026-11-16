# Devotion in the games without it (2026-11-16)

The owner: a collection event's Devotion reward (or loss) goes, in VV1-VV4, to one of Farming, Building, Research,
Healing or Parenting that fits the event, and in VV5 to Devotion or one of those, at random; "Make sure it makes
sense! If not = flavor." A skill effect lists its skills and the game draws one it has, so a Devotion effect that
also lists the fitting skill does exactly that: VV1-VV4 give that skill, VV5 draws Devotion or it. Only a skill the
event's own text clearly ties the reward to is added (`scripts/food_tech_additions.py` DEVOTION_MAPPINGS); every
other Devotion reward stays as written, flavor only in VV1-VV4. The owner's three handwritten events are left as
they are. The Living Event Engine's bank gives no Devotion; the mixer versions follow the static events.

A craft counts as its profession (the owner, 2026-11-16): cooking, fishing, gathering and herb-growing are Farming;
carving, sculpture, weaving, pottery, canoe- and mask-making Building; stargazing, scroll-keeping, alchemy, mapping
and riddles Research; herbalism, bonesetting and midwifery Healing; teaching and storytelling to the young and
nursery care Parenting; prayer, ritual and omens Devotion (VV5). Also: hunting and trapping Farming (food-gathering);
jewelry, craftmaking, weaponsmithing and bow-making Building; archery as a practised skill Building (flavor when it is
only sport); potions and stews (cauldron brews) Research or Healing (the owner, 2026-11-16: list both,
["Research", "Healing"], and the game draws one it has, unless the text clearly shows only one; cooking food is still
Farming); writing scrolls or books Research;
any other craft an event names goes to the obvious main skill, and doubt is flavor. A craft that fits two professions
(archery: Farming by hunting, Building by bow-making; a medicine potion: Research and Healing) gives each when the text
shows both, else one of them at random (a skill effect's list draws one). Each Devotion reward below was
read against that list;
a contest recitation is storytelling, but not to the young, so it stays Devotion only.

## Mapped

| Event | Node | Skill added | The text that ties it |
|---|---|---|---|
| `all_storytelling` (The Great Isolan Storytelling Contest) | v3_5 (both competitors) | Parenting | "The judges declare a tie. Both competitors are invited to teach the children." |

## Left as written (Devotion only, or its list unchanged)

| Event | Node | Skills | Why |
|---|---|---|---|
| `all_storytelling` | v1_5, v2_5 | Devotion | A recitation won "for accuracy" / "for understanding and delivery": nothing ties it to another skill |
| `all_storytelling` | lesson | Devotion, Research | Already lists Research |
| `all_invention_showcase` | c4 | Devotion, Research | Already lists Research |
| `c5dn022_clumsy_morel` | e1 | all six (a loss) | Already lists every skill |
| `vv5_little_things_remember` | end, end_parent | Devotion | The endings (a keepsake, stories, a family afternoon) tie it to no other skill |
| `vv5_keeper_of_little_things`, `vv5_multicultural_festival`, `vv5_gift_or_insult`, `vv5_field_day`, `vv5_potluck_dispute` | their endings | Devotion with others | New Believers only; their lists already name the skills their texts give |
