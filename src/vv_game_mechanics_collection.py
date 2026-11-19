"""The Isola Grand Event Collection on the Game Mechanics pages' Island events group (all five games; v1.35.97).

Shown only when the game's exe has the patch (vvN_isola_grand_event_collection).  Every list is read from what the
patcher ships, so it cannot drift: the game's events and their order from assets/event_collection/vvN/manifest.txt
(the file "VVFP Story Upgrades.dll" reads); each event's section and the effects that can kill or remove a villager
from data/event_collection_index.json, which `build_index` makes from the source graphs
data/event_collection/<section>/<id>.json (the graphs the .cieg files are compiled from; they are not shipped) --
scripts/build_event_collection_features.py writes it (with the Living Event Engine's seeds, from the repository-only
vv_living_mixer), tests/test_game_mechanics_collection.py keeps it equal to
the sources and to every game's manifest.  When the new events come is native/vvfp_story_upgrades/story_collection.inc's
rule (tests/test_collection_trigger.py): from vv_game_mechanics_adventurer.REPLACE_MIN_POPULATION villagers, each
natural island event is replaced with a chance in REPLACE_PERCENT (rolled each time), kept equal to the C constants by
tests/test_more_island_events_stock_odds.py.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import vv_game_mechanics as gm
from vv_game_mechanics_adventurer import PROTECTED, REPLACE_MIN_POPULATION, REPLACE_PERCENT

ROOT = Path(__file__).resolve().parents[1]
PATCH = "vv{}_isola_grand_event_collection"
GROUP = "Island events"

# The collection's sections in the order the source file has them, in plain words.
SECTIONS = (
    ("universal", "Universal events"),
    ("original", "The owner's original events and their add-ons"),
    ("exclusive", "Events of one game only"),
    ("v6", "Part V6"), ("v8", "Part V8"), ("v9", "Part V9"), ("v10", "Part V10"), ("v11", "Part V11"),
    ("v13", "Part V13"), ("v14", "Part V14"), ("v17", "Part V17"), ("v18", "Part V18"), ("v20", "Part V20"),
    ("v21", "Part V21"), ("v22", "Part V22"), ("v23", "Part V23"), ("v24", "Part V24"), ("v27", "Part V27"),
    ("vv5_isolan", "Isolan events"),
    # The Companion Anthology (the owner's second source, data/event_collection/companion/<section>/), its volumes
    ("c5", "Companion Anthology: Companion Volume 5"), ("lbl", "Companion Anthology: The Lives Between Legends"),
    ("fwk", "Companion Anthology: The Four Ways of Knowing"),
    ("sss", "Companion Anthology: Stone, Spirit, Strangers and Mind and Belonging"),
    ("cat", "Companion Anthology: The Living Catalogue"),
    # The Living Event Engine's fixed event volumes (the owner's third source, data/event_collection/living/<section>/)
    ("lv_med", "Living Events: Experimental Medicine, Last Resorts and Comfort Care"),
    ("lv_life", "Living Events: The Healer's Hands, the Farmer's Fields, and the Weaver's Dreams"),
    ("lv_circle", "Living Events: The Circle of Life, Rights, and Remembrance"),
    ("lv_peoples", "Living Events: Colors, Masks, Peoples and Choice"),
    ("lv_unseen", "Living Events: The Unseen Horizon, Cryptids, and the Silent Gods"),
    ("lv_ways", "Living Events: The Many Ways of Isola"),
    ("lv_auth", "Living Events: The Weight of a Name"),
    # The owner's 2026-11-15 sources (data/event_collection/horizon/<section>/, data/event_collection/rolemodels/rm/)
    ("hz_world", "Beyond the Horizon: The World We Imagine"),
    ("hz_vol2", "Beyond the Horizon: The Constructs, the Cities, and the Common Fire"),
    ("rm", "Role Models and Good Examples"),
    # The owner-approved drafts, set A (data/event_collection/drafts_a/<section>/)
    ("da_il01", "Inner Life"), ("da_il02", "Inner Life, Part II"), ("da_il03", "Inner Life, Part III"),
    ("da_il04", "Inner Life, Part IV"), ("da_il05", "Inner Life, Part V"), ("da_il06", "Inner Life, Part VI"),
    ("da_il07", "Inner Life, Part VII"), ("da_il08", "Inner Life, Part VIII"), ("da_il09", "Inner Life, Part IX"),
    ("da_il10", "Inner Life, Part X"), ("da_wd", "What's That Doing Here?"),
    ("da_lo", "Luck, Omens and Lavastones"),
    # The owner-approved draft event files, group B (data/event_collection/drafts_b/<section>/)
    ("dr_hum", "New Events: Humor and Absurdity"),
    ("dr_tt", "New Events: Tall Tales and Self-Interest"),
    ("dr_hon", "New Events: Honesty and Accountability"),
    ("dr_jus", "New Events: Justice and Consequences"),
    ("dr_dep", "New Events: Departures and Exile"),
    ("dr_drm", "New Events: Dreams and Ambitions"),
    ("dr_fea", "New Events: Fears and Doubts"),
    ("dr_day", "New Events: Good, Bad and Ordinary Days"),
    # The owner-approved draft event files, group C (data/event_collection/drafts_c/<section>/)
    ("dr_hea", "New Events: Healing, Psychology and Medicine"),
    ("dr_adv", "New Events: Advice and Decisions"),
    ("dr_fam2", "New Events: Relationships, Singlehood and Family"),
    ("dr_blf", "New Events: Belief and Identity"),
    ("dr_nat", "New Events: Nature, Ecology and Animals"),
    ("dr_div", "New Events: Disability and Diversity"),
    ("dr_his", "New Events: History and Collective Memory"),
    ("dr_lif", "New Events: Pondering How Life Has Gone"),
    # The owner-approved files, group D (data/event_collection/drafts_d/<section>/)
    ("dr_rm2", "New Events: Role Models and Good Examples, RM-41 to RM-90"),
    ("dr_hz3", "New Events: Beyond the Horizon, Events 081 to 130"),
    ("dr_tim", "New Events: Tiny Island Moments, T001 to T125"),
    ("dr_tim2", "New Events: Tiny Island Moments, T126 to T175"),
    ("dr_arm_m", "New Events: Armor Flavor Moments, M01 to M35"),
    ("dr_armor", "New Events: Armor, Weapons and Inherited Traditions"),
    ("dr_arm2", "New Events: Armor, Weapons and Heirlooms, ARM-46 to ARM-95"),
    ("dr_fat", "New Events: Fathers, Pregnancy and Parenthood"),
    # The owner's all-in-one Animals anthology, its newest volumes (data/event_collection/anthology/<section>/)
    ("an_mom", "Anthology: Living Moments"),
    ("an_rel", "Anthology: Love by Choice, Coming Out, Names and Presentation"),
    ("an_child", "Anthology: Childhood Curiosity, Puppy Love and Questions"),
    ("an_fam", "Anthology: Family Friction, Everyday Boundaries, Separation and Reconciliation"),
    ("an_joy", "Anthology: Celebrations, Leisure, Remembrance and Body Art"),
    ("an_hs", "Anthology: The Human Spectrum, Island Comforts, Authority, Injury and Belonging"),
    ("an_age", "Anthology: Every Age in the Limelight"),
    ("an_jus", "Anthology: Justice, Bullying, Consequences, Trauma, Recovery and Defense"),
    ("an_expr", "Anthology: Self-Expression, Art, Sport, Ecology, Governance and Belief"),
    ("an_fauna", "Anthology: Animals of Fur, Feathers, Scales, Claws and Hooves"),
    # The Living Event Engine (living.pak): one row per seed, a category's seeds sharing its title (one series).
    ("living_engine", "The Living Event Engine"),
)
LIVING_SECTION = "living_engine"
SECTION_WORDS = dict(SECTIONS)


def manifest_paths(game: int) -> list[Path]:
    """The game's manifest files: one per source section and per living series (living-pack.md 1)."""
    return sorted((ROOT / "assets" / "event_collection" / f"vv{game}").glob("manifest-*.txt"))


@lru_cache(maxsize=None)
def manifest(game: int) -> tuple[tuple[str, str, str], ...]:
    """(id, title, series) of each event the patcher ships for this game, in its manifests' order.  The static
    events' mixer versions (living_st_*) are those events again, so the page lists the events once."""
    rows = []
    for path in manifest_paths(game):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            cells = line.split("\t")
            if cells[0].startswith("living_st_"):
                continue
            rows.append((cells[0], cells[1], cells[4] if len(cells) > 4 else ""))
    return tuple(rows)


INDEX_PATH = ROOT / "data" / "event_collection_index.json"
HARMFUL = ("kill", "vanish", "die_unrecovered", "baby_lost", "birth_then_die",   # the effects listed on the page
           "deliver_early")                                                   # (cie-v6-binary.md 22, 23, 30)


def _allows(graph: dict) -> bool:
    """A villager role whose author lets protected villagers be harmed (protected "allow"; cie-v6-binary.md 7)."""
    return any(isinstance(r, dict) and r.get("protected") == "allow" for r in (graph.get("roles") or {}).values())


def _effects(node) -> set[str]:
    out: set[str] = set()
    if isinstance(node, dict):
        for effect in node.get("effects") if isinstance(node.get("effects"), list) else ():
            if isinstance(effect, dict) and effect.get("do") in HARMFUL:
                out.add(effect["do"])
        for value in node.values():
            out |= _effects(value)
    elif isinstance(node, list):
        for value in node:
            out |= _effects(value)
    return out


def build_index(living_seeds=()) -> dict:
    """{event id: {"section": ..., "harm": [...]}} from the source graphs (repository only: not shipped).
    `living_seeds`: (manifest id, variant graph) of every Living Event Engine variant -- the caller makes them with
    vv_living_mixer.generate(), a repository-only module this shipped one never imports."""
    out = {}
    base = ROOT / "data" / "event_collection"
    # Every event file at any depth (the GO and More Island Events folders included), as the collection's builder
    # reads them; the content tag tables are not events.
    for source in sorted(p for p in base.rglob("*.json") if "content_tags" not in p.relative_to(base).parts):
        graph = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(graph, dict) or "collection" not in graph:
            continue                                       # manifest.json, shared_pools.json
        if graph["collection"].get("mixer_only") is True:
            continue                                       # More Island Events' own: listed by that patch's rows
        out[source.stem] = {"section": graph["collection"]["section"], "harm": sorted(_effects(graph))}
        if _allows(graph):
            out[source.stem]["allow"] = True
    # The Living Event Engine's seeds (docs/event-collection/living-pack.md): one manifest row per seed, its event one
    # of the seed's variants in living.pak -- the seed can make what any of its variants makes.
    for manifest_id, graph in living_seeds:
        entry = out.setdefault(manifest_id, {"section": LIVING_SECTION, "harm": []})
        entry["harm"] = sorted(set(entry["harm"]) | _effects(graph))
        if _allows(graph):
            entry["allow"] = True
    return {"format": "vvfp-event-collection-index", "version": 1, "events": out}


@lru_cache(maxsize=None)
def index() -> dict:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))["events"]


def event_info(event_id: str) -> tuple[str, frozenset]:
    """The event's section and the harmful effects its graph can make ("kill", "vanish")."""
    entry = index()[event_id]
    return entry["section"], frozenset(entry["harm"])


def sections(game: int) -> list[tuple[str, list[str]]]:
    """[(section words, [titles])] for this game, sections in the source's order, titles in the manifest's."""
    grouped: dict[str, list[str]] = {}
    for event_id, title, _series in manifest(game):
        titles = grouped.setdefault(event_info(event_id)[0], [])
        if event_info(event_id)[0] != LIVING_SECTION or title not in titles:   # a Living category's title once
            titles.append(title)
    order = [key for key, _ in SECTIONS] + sorted(set(grouped) - set(SECTION_WORDS))
    return [(SECTION_WORDS.get(key, key), grouped[key]) for key in order if key in grouped]


def deadly(game: int) -> tuple[list[str], list[str]]:
    """The titles of this game's events that can kill a villager, and of those that can make one disappear."""
    kill = [title for event_id, title, _ in manifest(game) if "kill" in event_info(event_id)[1]]
    vanish = [title for event_id, title, _ in manifest(game) if "vanish" in event_info(event_id)[1]]
    return kill, vanish


def titles_with(game: int, harm: str) -> list[str]:
    """This game's events that can make the harmful effect `harm` ("die_unrecovered", "baby_lost")."""
    return [title for event_id, title, _ in manifest(game) if harm in event_info(event_id)[1]]


def allowing(game: int) -> list[str]:
    """This game's events whose author lets a protected villager be harmed (cie-v6-binary.md 7)."""
    return [title for event_id, title, _ in manifest(game) if index()[event_id].get("allow")]


def series_count(game: int) -> int:
    return len({series for _id, _title, series in manifest(game) if series})


def lines(game: int) -> list[tuple[str, bool]]:
    """(text, sub) of each line, without the patch check."""
    events = manifest(game)
    kill, vanish = deadly(game)
    out = [
        (f"Isola Grand Event Collection: {len(events)} events in this game. They never take a share of the game's own "
         "draw: they come in place of some of the game's natural island events.", False),
        (f"How one comes: each natural island event has a {REPLACE_PERCENT[0]}-{REPLACE_PERCENT[1]}% chance (rolled "
         "each time) to be one of the new events instead (Story / Cheat Upgrades, with the game's own random "
         "routine); the game's own event then does not come that time, and the next natural event is due as after "
         "the game's own. The village's two opening events are never replaced.", True),
        (f"Events that can kill a villager, make one disappear or lose a pregnancy only happen once the village has "
         f"{REPLACE_MIN_POPULATION} or more villagers (counting the babies being carried"
         f"{'; believers only' if game == 5 else ''}), unless \"No Safeguards for Island Events (and Additional Events too)\" is installed. From "
         f"{REPLACE_MIN_POPULATION} villagers the food and tech points of the new events come in a random size each "
         "time (small, normal, large or huge, in the game's own ranges).", True),
        ("It never comes while the village is in trouble: the game's own rescue rule (too few men or women, or fewer "
         "than 3 people counting the babies being carried), food below 10 a villager, half the village sick, or "
         "fewer than 6 villagers of 14 villager years or more. So a rescue event is never replaced. When no new "
         "event can happen, the game's own event comes.", True),
        ("Which one: every event that can happen is equally likely, whether it is one of More Island Events', the "
         "collection's or the Companion Anthology's; a series counts as one event, its parts equally likely "
         f"({series_count(game)} series in this game). An event whose villagers cannot be found is left out and "
         "another is drawn.", True),
        ("Pick Island Event lists every event with what it needs, and the Custom Island Event library has them in "
         "its own \"Isola Grand Event Collection\" group.", True),
        ("Needs Story / Cheat Upgrades (it runs the events) and Scrolling Popups (it keeps every page "
         "on the screen).", True),
        (f"Who can be harmed: never a nursing mother or father, {PROTECTED[game]}, or anyone the game's own island "
         "events never pick. They may still take part in harmless roles (speaking, celebrating).", True),
        # cie-v6-binary.md 35 (the owner, 2026-11-16)
        ("An event's chief is called the Chief, the leader, the elder, the headman or headwoman, or the council head: "
         "one title drawn each time, the same on every page (and after a reload)."
         + (" The robed Tribal Chief takes a chief's part whenever they can, and is then always the Chief."
            if game == 3 else ""), True),
        ("A nursing parent's words (mother or father, he or she) follow how the villager is drawn with Gender "
         "Presentation, else their recorded sex, and change on the next page after a sex change."
         + (" The Golden Child's words follow the Golden Child's recorded sex." if game == 1 else ""), True),
    ]
    out.append((("Can kill a villager (a grave, cause \"Unknown causes\"): "
                 + ", ".join(kill) + ".") if kill else "No event in this game kills a villager.", True))
    out.append((("Can make a villager disappear (no grave): " + ", ".join(vanish) + ".") if vanish
                else "No event in this game makes a villager disappear.", True))
    # V28 (cie-v6-binary.md 7, 22): said only when an event of this game makes them.
    unrecovered, baby, allowed = titles_with(game, "die_unrecovered"), titles_with(game, "baby_lost"), allowing(game)
    if unrecovered:
        out.append(("Can kill a villager whose body is never found (no grave; the Deaths log records the death, "
                    "\"Unknown causes\"): " + ", ".join(unrecovered) + ".", True))
    if baby:
        out.append(("Can make a nursing mother or father lose the baby: " + ", ".join(baby) + ".", True))
    born = titles_with(game, "birth_then_die")
    if born:
        out.append(("Can make a nursing mother or father give birth early and then die (the baby lives on as its own "
                    "villager; the parent gets a grave): " + ", ".join(born) + ".", True))
    early = titles_with(game, "deliver_early")
    if early:
        out.append(("Can make a nursing mother or father give birth early (the parent lives; the baby is born younger "
                    "and weaker the earlier it is): " + ", ".join(early) + ".", True))
    if allowed:
        who = {1: ", the Golden Child", 3: ", the Tribal Chief"}.get(game, "")
        out.append((f"Where the story calls for it, these may harm a nursing mother or father{who}: "
                    + ", ".join(allowed) + ".", True))
    for words, titles in sections(game):
        out.append((f"{words} ({len(titles)}): " + ", ".join(titles) + ".", True))
    return out


def facts(village: gm.Village) -> list[gm.Fact]:
    """The collection's lines, shown only when the game's exe has the patch."""
    game = village.game
    if game not in (1, 2, 3, 4, 5) or village.has(PATCH.format(game)) is not True:
        return []
    return [gm.Fact(GROUP, text, gm.RUNNING, sub=sub) for text, sub in lines(game)]


def write_index(living_seeds) -> None:
    """Write data/event_collection_index.json (scripts/build_event_collection_features.py calls it)."""
    INDEX_PATH.write_text(json.dumps(build_index(living_seeds), indent=1, sort_keys=True) + "\n", encoding="utf-8",
                          newline="\n")
