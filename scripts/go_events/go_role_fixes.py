"""Who a GO event's words and effects are about, where the importer named the wrong villager (the v1.35.98 lines audit,
2026-11-22).  Read by scripts/go_events/gen_go.py after the placeholders are named; tests/test_event_roles_and_gating.py
pins every entry.

THE IMPORTER'S RULE.  In an event of two or more villagers, the owner's bare "(he/she)", "(his/her)", "(him/her)" and
"(himself/herself)" become the main villager's ("(subject.his/her)"), and an EFFECT clause with no name of its own goes
to the main villager.  Where the owner's sentence is about another villager -- "(fisher) shakes (his/her) head",
"(sick name) has a PERMANENT DISABILITY (health loss 30%); now dislikes medicine; "old" head look" -- that names the
wrong one: the game says "his" for a woman, or gives the old look to the healer instead of the patient.

PRONOUNS: (event id, node) -> [(snippet, role)].  Every "(subject." in the snippet becomes "(role." -- only the role
name changes, never a word of the owner's text.  Each snippet is found exactly once on the page (after the roles are
named and {@chief} is written), or the build stops.  A pronoun about someone the event does not cast (the trader's
baby, the family's eldest, a grown child's partner) is left as it is: no role name can say it.

EFFECTS: (event id, node) -> [(do, from role, to role)].  The effect on the page, or on its own branches
("c1o2_g1", the game-gated parts), moves to the villager the owner's EFFECT line and the page name.  `to` "*all*" is
every villager ({"all": true}): "illness cured (for every sick villager)".  Each entry must find its effect, or the
build stops.
"""
from __future__ import annotations

PRONOUNS: dict[tuple[str, str], list[tuple[str, str]]] = {
    ("b021_hundred_year", "c1o2"): [("(friend) comes running when (subject.he/she) hears", "friend")],
    ("b054_two_same_name", "c2o2"): [("(friend) gets a goat (subject.he/she) didn't ask for", "friend")],
    ("b077_rope_bridge", "c1o2"): [("(builder) lets out a breath (subject.he/she) seems", "builder")],
    ("b077_rope_bridge", "c2o2"): [("(builder) shakes (subject.his/her) head", "builder")],
    ("b121_fever_tea", "ask"): [("squints at it and says (subject.his/her) grandmother", "healer")],
    ("b121_fever_tea", "c2o1"): [("(healer) opens (subject.his/her) eyes and starts to hum a song (subject.his/her) "
                                  "grandmother", "healer")],
    ("b121_fever_tea", "c2o2"): [('"Fevers," (subject.he/she) says', "healer"),
                                 ("(friend) gets better on (subject.his/her) own, one long week later, and tells "
                                  "everyone (subject.he/she) would", "friend")],
    ("b129_weaver_last_mat", "c1o1"): [("(weaver) runs (subject.his/her) hands over it and says it's the best first mat "
                                        "(subject.he/she) has", "weaver")],
    ("b133_grey_mist", "ask"): [("silver streaks in (subject.his/her) hair", "fisher")],
    ("b138_fisher_trip", "c1o2"): [("with (subject.his/her) hand trailing in the water. Then (subject.he/she) leans back "
                                    "against the side of the canoe, closes (subject.his/her) eyes", "fisher")],
    ("b138_fisher_trip", "c2o2"): [("so cross about it that (subject.he/she) sits", "fisher")],
    ("b139_bitter_berry_week", "ask"): [("which (subject.he/she) loves", "child"),
                                        ("(healer) says (subject.he/she) thinks", "healer")],
    ("b142_fig_fruits_once", "ask"): [("(farmer) and (subject.his/her) partner have", "farmer")],
    ("b142_fig_fruits_once", "c2o1"): [("(farmer) and (subject.his/her) partner share", "farmer")],
    ("b142_fig_fruits_once", "c2o2"): [("(farmer) and (subject.his/her) partner share", "farmer")],
    ("b142_fig_fruits_once", "c2"): [("(farmer) runs out of (subject.his/her) hut so fast (subject.he/she) forgets "
                                      "(subject.his/her) sandals", "farmer")],
    ("b152_shadow_stayed", "ask"): [("(healer) says (subject.his/her) grandmother", "healer")],
    ("b156_old_well", "c2o1"): [("(child) is so happy (subject.he/she) cries", "child")],
    ("b167_elders_dance", "ask"): [("argues with (subject.himself/herself) about the rest", "elder")],
    ("b172_trader_baby", "ask"): [("the baby on (subject.his/her) back", "trader"),
                                  ("with tears in (subject.his/her) eyes", "trader")],
    ("b174_falling_star", "c2o2"): [("(researcher) picks the stone up with (subject.his/her) bare hands, before anyone "
                                     "can stop (subject.him/her). By evening (subject.he/she) has a fever and a rash all "
                                     "up (subject.his/her) arm", "researcher"),
                                    ("while nursing (subject.him/her)", "researcher")],
    ("b182_hot_spring_rocks", "c1"): [("lower (subject.him/her) into", "friend")],
    ("b182_hot_spring_rocks", "c1o1"): [("until (subject.his/her) fingers wrinkle", "friend"),
                                        ("That evening, (subject.he/she) walks down", "friend")],
    ("b182_hot_spring_rocks", "c1o2"): [("When (friend) climbs out, (subject.his/her) skin is smooth and bright and "
                                         "(subject.his/her) face", "friend")],
    ("b184_mask_face", "c2o1"): [("(fisher) is so impressed that (subject.he/she) gives", "fisher")],
    ("b187_elder_hat", "ask"): [("gives away (subject.his/her) hat", "elder")],
    ("b189_coughing_season", "ask"): [("from (subject.his/her) mat between coughs", "healer")],
    ("b189_coughing_season", "c2o1"): [("(healer) gets up off (subject.his/her) mat, eats three spoonfuls just to be sure, "
                                        "and declares it the best medicine (subject.he/she) has", "healer")],
    ("b192_burning_fever", "ask"): [("(healer) has tried every brew (subject.he/she) knows. Tonight (subject.he/she) says",
                                     "healer")],
    ("b192_burning_fever", "c1o1"): [("by (subject.his/her) door", "healer")],
    ("b194_canoe_shed_baby", "c2o1"): [("a baby of (subject.his/her) own", "healer"),
                                       ('here," (subject.he/she) says', "healer")],
    ("b195_bitter_honey", "ask"): [('shakes (subject.his/her) head. "Swamp bees," (subject.he/she) says', "gatherer")],
    ("b199_chief_bad_day", "c1"): [("(elder) shakes (subject.his/her) head", "elder")],
    ("b203_sleepy_spell", "c2o2"): [("(apprentice), offended that (subject.his/her) cake is being refused, eats it "
                                     "(subject.himself/herself) to prove it's safe. (subject.He/She) falls asleep sitting "
                                     "up, falls sideways into the woodpile, and wakes up two days later with a lump on "
                                     "(subject.his/her) head", "apprentice")],
    ("b203_sleepy_spell", "c2"): [("(apprentice) looks so innocent (subject.he/she) goes red", "apprentice")],
    ("b204_scroll_bit", "c2o2"): [("(friend) gets better slowly, on (subject.his/her) own", "friend")],
    ("b212_last_canoe", "c1o2"): [("sits back on (subject.his/her) heels", "carver")],
    ("b212_last_canoe", "c2o1"): [("best first canoe (subject.he/she) has ever seen", "carver"),
                                  ("(carver) sits on (subject.his/her) log", "carver")],
    ("b212_last_canoe", "c2o2"): [("(carver) dies in (subject.his/her) sleep", "carver")],
    ("b216_apprentice", "c2o2"): [("When (healer) gets back, (subject.he/she) doesn't say anything at all, which is worse "
                                   "than anything (subject.he/she) could", "healer")],
    ("b220_feather_crown", "c2o2"): [("(elder) says (subject.he/she) has never heard", "elder")],
    ("b232_healing_rain", "ask"): [("with (subject.his/her) arms up, shouting. (subject.His/her) grandmother told "
                                    "(subject.him/her) about this", "healer"),
                                   ('healed," (subject.he/she) says', "healer")],
    ("b233_hut_raising_song", "c2o2"): [("sings the old song by (subject.himself/herself), the half of it "
                                         "(subject.he/she) remembers", "elder")],
    ("b241_night_roofs_flew", "c2o1"): [("the way (subject.his/her) grandmother taught (subject.him/her)", "builder")],
    ("b243_fever_bitter_root", "c1"): [("up to (subject.his/her) waist and comes back with a muddy black root that smells "
                                        "like a wet boot. (subject.He/She) grinds", "healer")],
    ("b243_fever_bitter_root", "c2o1"): [("with the cloth still in (subject.his/her) hand. When (subject.he/she) wakes, "
                                          "(subject.he/she) writes", "healer")],
    ("b246_vine_swing_over", "c2o1"): [("(subject) climbs down to (subject.him/her)", "teen"),
                                       ("(teen) lives, but (subject.his/her) hip never sets right, and (subject.he/she) "
                                        "walks", "teen")],
    ("b248_feast_nobody", "ask"): [("stands with (subject.his/her) hands on (subject.his/her) hips. \"Nobody told me there "
                                    "was a feast,\" (subject.he/she) says", "cook")],
    ("b248_feast_nobody", "c1"): [("(cook) throws (subject.his/her) hands", "cook")],
    ("b248_feast_nobody", "c2o1"): [("which (subject.he/she) calls", "cook"),
                                    ("turn (subject.his/her) stomach", "cook")],
    ("b248_feast_nobody", "c2o2"): [("(cook) says (subject.he/she) could", "cook")],
    ("b249_grandchild_spell", "ask"): [("today (subject.he/she) runs up to", "child"),
                                       ("(child) is bouncing on (subject.his/her) toes", "child")],
    ("b249_grandchild_spell", "c1o1"): [("with (subject.his/her) mouth open", "child")],
    ("b249_grandchild_spell", "c1"): [("a long word that (subject.he/she) gets wrong", "child")],
    ("b251_lightning_under", "c1o1"): [("(healer) admits (subject.he/she) has never", "healer")],
    ("b255_coughing_season", "ask"): [("(subject.He/She) has been coughing for nine days and can barely lift "
                                       "(subject.his/her) head", "sick")],
    ("b255_coughing_season", "c1o2"): [("That night (subject.he/she) can't sleep for the itching, nor the night after, and "
                                        "somewhere in all that scratching (subject.he/she) loses all love for "
                                        "(subject.his/her) sleeping mat. \"I'll lie down,\" (subject.he/she) says", "sick")],
    ("b255_coughing_season", "c2o1"): [("(subject.he/she) is sitting up and complaining", "sick")],
    ("b255_coughing_season", "c2o2"): [("from (subject.his/her) neck to (subject.his/her) belly", "sick")],
    ("b256_traveller", "c2o1"): [("(subject.his/her) footprints lead", "friend"),
                                 ("Nobody saw (subject.him/her) go", "friend")],
    ("b263_echo_conch", "ask"): [("(subject.He/She) has finally finished", "keeper")],
    ("b267_night_hill_moved", "c1o1"): [("crushed (subject.his/her) leg, and it never heals straight. (subject.He/She) "
                                         "walks with a stick after that. For years, whenever it rains hard, "
                                         "(subject.he/she) sits up", "friend")],
    ("b268_mask_carver_faces", "ask"): [("lately (subject.he/she) has started saying that the masks are telling "
                                         "(subject.him/her) who they're for. Today (subject.he/she) comes", "carver")],
    ("b268_mask_carver_faces", "c2o1"): [("comes out of (subject.his/her) hut with a new face: (subject.he/she) put the "
                                          "mask on (subject.himself/herself) in the night, just to see. \"It must have "
                                          "been for me after all,\" (subject.he/she) says", "carver")],
    ("b271_polished_shell", "c2o1"): [("one last look at (subject.his/her) work. In the morning there are two of "
                                       "(subject.him/her): one who polished the shell, and one who looks exactly like "
                                       "(subject.him/her)", "polisher")],
    ("b276_swamp_fever", "ask"): [("Now (subject.he/she) is burning up", "sick")],
    ("b278_cook_lost_taste", "ask"): [("burned (subject.his/her) tongue", "cook"),
                                      ("taste everything for (subject.him/her)", "cook")],
    ("b280_two_carved_totems", "c2"): [("(friend) takes (subject.his/her) hand off the post. \"Leave it,\" "
                                        "(subject.he/she) says", "friend")],
    ("b285_masks_harvest", "c1o2"): [("(subject.His/Her) own mother needs a moment to recognise (subject.him/her). "
                                      "(dancer), looking at (subject.himself/herself) in the water, decides "
                                      "(subject.he/she) likes", "dancer")],
    ("b287_fever_burns_away", "c2o2"): [("when (subject.he/she) does, it is to ask the elders to teach (subject.him/her)",
                                         "healer")],
    ("b293_potter_clay", "c1o1"): [("(potter) drops the pot (subject.he/she) is holding", "potter")],
    ("b293_potter_clay", "c2"): [("in (subject.his/her) fist", "potter")],
    ("b301_wrong_jar", "c1o1"): [("(sick)'s stomach has settled and (subject.he/she) is asking", "sick")],
    ("b301_wrong_jar", "c1o2"): [("sitting with (subject.him/her) and listening to (subject.his/her) breathing. When "
                                  "(subject.he/she) finally wakes, the stomach is fine. But (subject.his/her) hands are "
                                  "numb, and (subject.his/her) legs don't do what (subject.he/she) tells them", "sick"),
                                 ("(sick) never lets anyone treat (subject.him/her)", "sick")],
    ("b305_coconut_cried", "c1o1"): [("one of (subject.his/her) own. \"Well,\" (subject.he/she) says", "healer")],
    ("b306_pale_blossoms", "c1o1"): [("tells everyone (subject.he/she) did it. Technically, (subject.he/she) did",
                                      "child")],
    ("b306_pale_blossoms", "c1o2"): [("(child) puts the crown on (subject.his/her) own head afterwards, to see, and by the "
                                      "next morning nothing has happened to (subject.him/her) either, except that "
                                      "(subject.he/she) smells", "child")],
    ("b312_apprentice_roof", "ask"): [("today (subject.he/she) asks to do a roof alone", "apprentice")],
    ("b312_apprentice_roof", "c1o1"): [("and (subject.he/she) does, one after another", "apprentice")],
    ("b312_apprentice_roof", "c1o2"): [("(subject.He/She) lands badly on (subject.his/her) shoulder. The healers, whose "
                                        "roof (subject.he/she) was fixing, take care of (subject.him/her)", "apprentice")],
    ("b314_flood_scroll_hut", "ask"): [("asleep in (subject.his/her) hut", "keeper")],
    ("b314_flood_scroll_hut", "c1o1"): [("every smeared word (subject.he/she) can still make out", "keeper"),
                                        ("It costs (subject.him/her) a month of sleep, and (subject.he/she) is ill",
                                         "keeper")],
    ("b314_flood_scroll_hut", "c2"): [("in (subject.his/her) sleeping wrap", "keeper")],
    ("b320_sister_hills", "c2o1"): [("before (subject) can stop (subject.him/her)", "friend"),
                                    ("as if (subject.he/she) is having the time of (subject.his/her) life", "friend")],
    ("b324_hollow_log_drum", "c2o1"): [("says (subject.he/she) supposes it's (subject.his/her) turn. (subject.He/She) "
                                        "dances", "eldest"),
                                       ("(subject.his/her) face looks years younger", "eldest")],
    ("b324_hollow_log_drum", "c2o2"): [("lost (subject.his/her) love of drumming", "drummer")],
    ("b334_fever_ward", "c2o2"): [("The healers sit with (subject.him/her) on the last night. The village buries "
                                   "(subject.him/her)", "sick")],
    ("b340_shell_doubles", "ask"): [("After a month of trying, (subject.he/she) has made", "keeper"),
                                    ('"Would you sit under the big one?" (subject.he/she) asks', "keeper")],
    ("b340_shell_doubles", "c2"): [("Then (subject.his/her) apprentice", "keeper")],
    ("b341_octopus_fish_trap", "c2o2"): [("out of (subject.his/her) mouth for a week. After that, fish of any kind just "
                                          "tastes of ink to (subject.him/her)", "friend")],
    ("b344_lost_recipe", "c1o2"): [("(subject.his/her) patience with the healers", "sick")],
    ("b344_lost_recipe", "c2o1"): [("(subject.he/she) sets to work recalling", "oldest_healer")],
    ("b344_lost_recipe", "c2o2"): [("get (subject.his/her) strength back", "sick")],
    ("b345_games_hill", "c1o2"): [("back of (subject.his/her) leg", "runner")],
    ("b345_games_hill", "c2o2"): [("(subject.He/She) wins the swimming", "champion"),
                                  ("so happy (subject.he/she) can't stop", "champion")],
    ("b348_map_wrinkles", "ask"): [("every line is a place (subject.he/she) has been and a thing (subject.he/she) has "
                                    "learned. Today (subject.he/she) offers to give (subject) one of (subject.his/her) "
                                    "lines, the one that holds the way to the best fishing grounds, which "
                                    "(subject.he/she) has never", "elder")],
    ("b348_map_wrinkles", "c2o1"): [("When (subject.he/she) dies, years later", "elder")],
    ("b349_teenagers_cave", "c1o1"): [("pulls (subject.him/her) through the gap", "teen")],
    ("b349_teenagers_cave", "c1o2"): [("finds (subject.his/her) leg pinned", "teen"),
                                      ("never mends straight, and (subject.he/she) walks with a stick from then on. "
                                       "(subject.He/She) won't go", "teen")],
    ("b349_teenagers_cave", "c2o1"): [("which (subject.he/she) quite enjoys", "teen")],
    ("b349_teenagers_cave", "c2o2"): [("(subject.he/she) is clutching the thing (subject.he/she) went in for", "teen")],
    ("b350_second_naming", "c1"): [("clears (subject.his/her) throat", "elder")],
    ("b356_harvest_moon", "c2o1"): [("(friend) is so happy that (subject.he/she) dances alone around the fire the night "
                                     "the baby is born, until (subject.his/her) feet", "friend")],
    ("b359_healer_sweet", "ask"): [("which (subject.he/she) learned from a traveller", "healer")],
    ("my066_night_open_doors", "c3o2"): [("that (subject.he/she) seems to be wearing", "neighbour"),
                                         ("were (subject.his/her) doing; (subject.he/she) had been wandering from door to "
                                          "door, apparently looking for (subject.his/her) own", "neighbour")],
    ("my068_box_last_word", "c2o2"): [("(elder) just shakes (subject.his/her) head", "elder")],
    ("my069_watcher_cliff", "c3o2"): [("admits it is (subject.him/her)", "fisher"),
                                      ("(subject.he/she) mumbles", "fisher"),
                                      ("(subject.He/she) leaves before dawn because (subject.he/she) has nets", "fisher"),
                                      ("over (subject.his/her) quiet evenings. (subject) gives (subject.him/her) the rest",
                                       "fisher")],
    ("my081_cave_returned", "c3"): [("knees up to (subject.his/her) chin", "researcher")],
    ("my095_basket_unknown", "c1o2"): [("shakes (subject.his/her) head. \"I have no idea what this is,\" "
                                        "(subject.he/she) admits", "botanist")],
    ("my102_god_garden", "c1o2"): [("(friend) is not quite sure what (subject.he/she) is feeling", "friend")],
    ("my111_wandering", "c2o2"): [("(friend) slowly recovers on (subject.his/her) own", "friend")],
    ("my111_wandering", "c3o1"): [("(friend) recovers on (subject.his/her) own", "friend")],
    ("new101_spring", "c2o2"): [("(friend) bends over the spring, (subject.he/she) remembers", "friend")],
    ("new101_spring", "c2"): [("(friend) rolls up (subject.his/her) sleeves", "friend"),
                              ("(subject.He/She) leans out over the water, and the whole crowd leans with "
                               "(subject.him/her)", "friend")],
    ("new102_second_shadow", "c3"): [("with (subject.his/her) eyes closed", "elder")],
    ("new104_charm_forgot", "c3"): [("in (subject.his/her) knobbly fingers", "elder")],
    ("new105_night_exchanged", "c1o2"): [("in (subject.his/her) own soft voice", "friend")],
    ("new106_blessing_tree", "c2o2"): [("(friend) shakes (subject.his/her) head", "friend")],
    ("new106_blessing_tree", "c3"): [("with (subject.his/her) hand resting on the bark", "elder")],
    ("new109_blue_flame", "c2"): [("stop (subject.him/her), (subject.he/she) holds out a hand", "friend")],
    ("new109_blue_flame", "c2o1"): [("Blue light runs up (subject.his/her) arm like water up a reed, over "
                                     "(subject.his/her) shoulder and across (subject.his/her) face", "friend"),
                                    ("(friend) does not; (subject.he/she) just stands there with (subject.his/her) mouth "
                                     "open. When the light fades, (subject.he/she) is completely unhurt, but "
                                     "(subject.his/her) look", "friend")],
    ("new110_dream_two", "c2o2"): [("grabs (subject.his/her) mat", "friend")],
    ("new111_fishing_line", "c1o1"): [("uncrosses (subject.his/her) arms", "friend")],
    ("new115_water_jar_rule", "c1o2"): [("clears (subject.his/her) throat", "elder")],
    ("new119_broken_promise", "ask"): [("(leader) feels (subject.his/her) face go hot. What should (subject.he/she) do?",
                                        "leader")],
    ("new119_broken_promise", "c1"): [("the visitor (subject.his/her) own seat", "leader")],
    ("new119_broken_promise", "c3o1"): [("on (subject.his/her) shelf", "leader")],
    ("new119_broken_promise", "c3o2"): [("the least (subject.he/she) could do", "leader")],
    ("new120_vote_tied", "ask"): [("sitting on (subject.his/her) knee", "elder")],
    ("new120_vote_tied", "c3"): [("staring at (subject.him/her)", "elder")],
    ("new120_vote_tied", "c3o1"): [("Finally (subject.he/she) votes", "elder")],
    ("new122_secret_fort", "c1"): [("asks if (subject.he/she) may please", "adult")],
    ("new122_secret_fort", "c3"): [("(adult) bites (subject.his/her) tongue", "adult")],
    ("new124_teacher", "ask"): [("to (subject.his/her) credit", "teacher")],
    ("new131_elder_garden", "ask"): [("(young) opens (subject.his/her) mouth", "young")],
    ("new133_fisher_hands", "ask"): [("(young) noticed today. (subject.He/She) saw", "young"),
                                     ("but (subject.he/she) can't pretend (subject.he/she) didn't see it", "young")],
    ("new133_fisher_hands", "c2o1"): [("but (subject.he/she) can tie all seven. (subject) watches (subject.him/her) do it",
                                       "young")],
    ("new138_grandparent", "c2o1"): [("a cord of (subject.his/her) own", "young")],
    ("new138_grandparent", "c2"): [("so (subject.he/she) can remember both endings", "young")],
    ("new139_old_scar", "ask"): [("Tonight, by the fire, (subject.he/she) finally asks", "young"),
                                 ("(young) wonders if (subject.he/she) should have asked at all. Should (subject.he/she) "
                                  "let", "young")],
    ("new162_farmer_shy", "c3o1"): [("for once in (subject.his/her) life", "aunt"),
                                    ('," (subject.he/she) says. "Like a person', "aunt")],
    ("new163_proposal", "c3o1"): [('stew pot," (subject.he/she) says', "name3"),
                                  ("gives (subject.his/her) answer", "friend")],
    ("new163_proposal", "c3o2"): [("throw up (subject.his/her) hands", "name3"),
                                  ("(friend) follows (subject.his/her) own judgment", "friend")],
    ("new164_love_letter", "c3o2"): [("is that (subject.he/she) would have said yes", "elder"),
                                     ("(subject) thanks (subject.him/her)", "elder")],
    ("new165_couple_chose", "c3"): [("ask what (subject.he/she) thinks", "parent")],
    ("new166_wedding_without", "c1o2"): [("secretly, (subject.he/she) wants the feast", "friend"),
                                         ("(subject) stares at (subject.him/her)", "friend")],
    ("new167_partners_work", "c3o2"): [("sort the seeds (subject.his/her) way", "head")],
    ("new168_friendship", "c1o2"): [("that (subject.he/she) is still hurt", "friend")],
    ("new169_old_couple_walk", "c1o2"): [("(friend) admits (subject.he/she) would rather", "friend")],
    ("new172_wrong_name", "ask"): [("at the top of (subject.his/her) voice", "elder")],
    ("new177_two_histories", "ask"): [("(friend) says (subject.his/her) grandfather", "friend")],
    ("new182_overworked", "c3o2"): [("that (subject.he/she) fainted the one time (subject.he/she) tried", "builder")],
    ("new183_unwanted", "c3o2"): [("that (subject.he/she) hated leading", "mentor"),
                                  ("(subject.He/She) leans back against the logs", "mentor")],
    ("new184_fisher_wanted", "c3o2"): [("(subject.he/she) used to be a fisher", "mentor")],
    ("new185_without_tasks", "c2o2"): [("puts down (subject.his/her) knife and admits (subject.he/she) never learned",
                                        "mentor")],
    ("new188_long_way_home", "c3o2"): [("lowers (subject.his/her) voice. \"I haven't trusted that log in years,\" "
                                        "(subject.he/she) admits", "builder")],
    ("new190_worker_said", "c3o2"): [("that (subject.he/she) once refused", "mentor"),
                                     ("(subject.He/She) claps (subject)", "mentor")],
    ("new191_water_tasted", "c3o1"): [("(cook) narrows (subject.his/her) eyes", "cook")],
    ("s019_glowing_berries", "c2o2"): [("turns one berry over and over in (subject.his/her) fingers", "healer"),
                                       ("look after (subject.him/her), mixing teas, cooling (subject.his/her) forehead",
                                        "healer")],
    ("s037_coughing_season", "c2o2"): [("it goes deep into (subject.his/her) chest", "elder"),
                                       ("(subject.He/She) gets better, in the end. But (subject.he/she) never quite gets "
                                        "back (subject.his/her) strength", "elder"),
                                       ("The healers say (subject.he/she) was lucky. (Elder) says (subject.he/she) "
                                        "doesn't", "elder")],
    # found by tests/test_event_roles_and_gating.py's sentence check, beyond the audit's list
    ("b144_painter_pot", "c1o2"): [("(painter) admits (subject.he/she) got bored", "painter")],
    ("b145_rope_bridge", "c1o2"): [("all by (subject.himself/herself)", "builder")],
    ("b148_termite_year", "c2o2"): [("doesn't get out of the way (subject.himself/herself)", "builder")],
    ("b165_salve_clay_jar", "ask"): [("made by the healer before (subject.him/her)", "healer")],
    ("b187_elder_hat", "c2o2"): [("much more pleased with (subject.himself/herself)", "friend")],
    ("b203_sleepy_spell", "ask"): [("which (subject.he/she) says will", "apprentice"),
                                   ("(subject.He/She) hasn't tested it", "apprentice")],
    ("b203_sleepy_spell", "c1o2"): [("on (subject.his/her) recipe", "apprentice")],
    ("b211_frog_dance", "c2o1"): [("(elder) says from (subject.his/her) mat", "elder")],
    ("b223_rain_copies", "ask"): [("in (subject.his/her) great-grandmother's time", "researcher")],
    ("b224_wrong_jar", "ask"): [("asked from (subject.his/her) mat", "healer")],
    ("b226_flood", "c2o1"): [("wade down for (elder) and get (subject.him/her) out", "elder")],
    ("b261_dream_sharing_tea", "c2"): [("before anyone can stop (subject.him/her), drinks one (subject.himself/herself), "
                                        "and hands the other to (subject.his/her) assistant", "healer")],
    ("b263_echo_conch", "c2"): [("(keeper) throws (subject.himself/herself) flat", "keeper")],
    ("b263_echo_conch", "c2o2"): [("dusts (subject.himself/herself) off", "keeper")],
    ("b289_huts_stilts", "c2o1"): [("(chief) is very pleased with (subject.himself/herself)", "chief")],
    ("new110_dream_two", "c3"): [("anyone who brings (subject.him/her) a fish", "elder")],
    ("new140_bench_sun", "ask"): [("(young) finds (subject.himself/herself) already reaching", "young")],
    ("new194_ant_trail", "c4o1"): [("runs the test (subject.himself/herself) the next morning", "novice")],
    ("new198_stone_floats", "c4o1"): [("(novice) is surprised to find (subject.himself/herself)", "novice")],
    ("s081_feast_elders", "c1o2"): [("(subject.his/her) crown slipping over one eye, until (subject.he/she) finally spins",
                                     "elder"),
                                    ("(subject.He/She) is still smiling in the morning", "elder")],
}

ALL = "*all*"
_HURT = ("preference", "old_look")     # "(X) has a PERMANENT DISABILITY ...; now dislikes Y; "old" head look"
EFFECTS: dict[tuple[str, str], list[tuple[str, str, str]]] = {
    # "the Chief now dislikes turnips; the Chief gains 10 Building" / "NEW LOOK for the Chief": the Chief is (subject),
    # the event's own tribal chief, not a second villager
    ("s026_chief_bad_idea", "c2o2"): [("preference", "chief", "subject"), ("skill", "chief", "subject")],
    ("s071_robe_shrank", "c1o1"): [("appearance", "chief", "subject")],
    # the disabled villager's own dislike and old head look
    ("s037_coughing_season", "c2o2"): [(d, "subject", "elder") for d in _HURT],
    ("b019_mudslide", "c1o2"): [(d, "subject", "friend") for d in _HURT],
    ("b168_race_reef", "c1o2"): [(d, "subject", "friend") for d in _HURT],
    ("b198_jumping_rock", "c2o2"): [(d, "subject", "friend") for d in _HURT],
    ("b214_mango_tree", "c2o2"): [(d, "subject", "friend") for d in _HURT],
    ("b246_vine_swing_over", "c2o1"): [(d, "subject", "teen") for d in _HURT],
    ("b267_night_hill_moved", "c1o1"): [(d, "subject", "friend") for d in _HURT],
    ("b301_wrong_jar", "c1o2"): [(d, "subject", "sick") for d in _HURT] + [("cure", "subject", "sick")],
    ("b312_apprentice_roof", "c1o2"): [(d, "subject", "apprentice") for d in _HURT],
    ("b344_lost_recipe", "c1o2"): [(d, "subject", "sick") for d in _HURT],
    ("b345_games_hill", "c1o2"): [(d, "subject", "runner") for d in _HURT],
    ("b349_teenagers_cave", "c1o2"): [(d, "subject", "teen") for d in _HURT],
    # "illness cured": the patient, not the healer who cures them
    ("b255_coughing_season", "c1o2"): [("cure", "subject", "sick")],
    ("b255_coughing_season", "c2o1"): [("cure", "subject", "sick")],
    ("b276_swamp_fever", "c1o2"): [("cure", "subject", "sick")],
    ("b276_swamp_fever", "c2o1"): [("cure", "subject", "sick")],
    ("b301_wrong_jar", "c1o1"): [("cure", "subject", "sick")],
    ("b301_wrong_jar", "c2o1"): [("cure", "subject", "sick")],
    ("b344_lost_recipe", "c1o1"): [("cure", "subject", "sick")],
    ("b344_lost_recipe", "c2o1"): [("cure", "subject", "sick")],
    ("b344_lost_recipe", "c2o2"): [("cure", "subject", "sick")],
    # the fever ward's patients ("the fevers break", "Everyone recovers, except (sick)"): every sick villager, as A1
    ("b334_fever_ward", "c1o2"): [("cure", "subject", ALL)],
    ("b334_fever_ward", "c2o1"): [("cure", "subject", ALL)],
    ("b334_fever_ward", "c2o2"): [("cure", "subject", ALL)],
}


def apply(event_id: str, nodes: dict) -> None:
    """The fixes for one event, on its named pages (raises on a stale entry)."""
    for (eid, nid), pairs in PRONOUNS.items():
        if eid != event_id:
            continue
        node = nodes[nid]
        for snippet, role in pairs:
            assert "(subject." in snippet, (eid, nid, snippet)
            n = node["text"].count(snippet)
            assert n == 1, f"{eid} {nid}: {snippet!r} found {n} times"
            node["text"] = node["text"].replace(snippet, snippet.replace("(subject.", f"({role}."))
    for (eid, nid), moves in EFFECTS.items():
        if eid != event_id:
            continue
        for do, old, new in moves:
            hits = 0
            for k, node in nodes.items():
                if k != nid and not k.startswith(nid + "_"):
                    continue
                for e in node.get("effects") or []:
                    if e.get("do") == do and e.get("role") == old:
                        hits += 1
                        if new == ALL:
                            e.pop("role")
                            e["target"] = {"all": True}
                        else:
                            e["role"] = new
            assert hits, f"{eid} {nid}: no {do} on {old}"
