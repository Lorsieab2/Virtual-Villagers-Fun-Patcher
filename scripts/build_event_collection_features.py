"""Write "Isola Grand Event Collection" (vvN_isola_grand_event_collection): the owner's collection of island events
(docs/more-island-events/Isola_Grand_Event_Collection_V28_Consequences_Claude_Retrofit.txt, the frozen
source), one row per game.

The events are data: one version 6 branching Custom Island Event graph per event under data/event_collection/
(any folder depth; data/event_collection/shared_pools.json holds the pools they share), each with its "collection"
block (id, source lines, section, credit, draw weight, series).  This compiles every one with the patcher's own
src/vv_cie_graph.py (validate, then compile_graph) and writes:

  * assets/event_collection/<id>.cieg -- each event's compiled file;
  * assets/event_collection/vvN/manifest.txt -- the events of game N, one line each:
    id<TAB>title<TAB>games<TAB>draw weight<TAB>series<TAB>credit<TAB>description<TAB>Guardians title<TAB>Guardians
    description (Story / Cheat Upgrades' story_collection.inc reads it from "<game folder>\\Virtual Villagers Fun
    Patcher Files\\Island Event Collection\\manifest.txt"): the title the game shows (its title variant's, cie-v6-
    binary.md 18), Pick Island Event's sentence (collection.description), and -- New Believers only, empty when the
    same -- both with Guardians of Isola Rewrite on (the title variant and collection.description_variants);
  * assets/event_collection/Credits.txt ("Island Event Collection\\Credits.txt" in the game), and the same text as
    docs/more-island-events/Isola Grand Event Collection - Credits.md: the source's credit ledger (lines 1-91) and
    every section's credit block, verbatim, then each event's own credit;
  * data/vvN_isola_grand_event_collection_feature.json -- the five rows, pinning every file by SHA-256.

No executable byte, no DLL of its own: Story / Cheat Upgrades (the row's prerequisite) runs the events -- its separate
rare roll after a natural island event, Pick Island Event and the in-game library's "Isola Grand Event Collection"
group.  The script works on whatever event files exist (none yet is fine: the rows then ship only the manifest header
and the credits).

    python scripts/build_event_collection_features.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_cie_graph as cie  # noqa: E402
import vv_living_mixer as living  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from collection_check import graph_for_engine  # noqa: E402  (drops the authoring-only keys)

SOURCE = ROOT / "docs" / "more-island-events" / \
    "Isola_Grand_Event_Collection_V28_Consequences_Claude_Retrofit.txt"
SOURCE_SHA256 = "319712596BCCD325F47DF13B10DC895071F0306F7105B17CC8F3ED73BAE44C3E"
DATA = ROOT / "data" / "event_collection"
ASSETS = ROOT / "assets" / "event_collection"
FOLDER = "Island Event Collection"          # beside the companions (src/patcher_files.py PATCHER_READ_FOLDERS)
CREDITS_NAME = "Credits.txt"                # short: every path stays inside the game's own longest file's length
ID_MAX = 30                                 # an event id's longest (its .cieg's path, likewise)
# ... in an event A New Home shows: its .cieg ("Virtual Villagers Fun Patcher Files\Island Event Collection\<id>.cieg",
# 65 characters besides the id) must stay shorter than VV1's old patch-log path in the same folder (90 characters,
# tests/test_patcher_files_folder.py DeepOutputFoldersPatch), so a deep folder's longest path is still a file the
# old patcher refused: 24 at most, 22 with a margin of two.
VV1_ID_MAX = 22
CREDITS_MD = ROOT / "docs" / "more-island-events" / "Isola Grand Event Collection - Credits.md"
NAME = "Isola Grand Event Collection"
GAMES = (1, 2, 3, 4, 5)
NOT_EVENTS = {"manifest.json", "shared_pools.json"}
# The Living Event Engine (docs/event-collection/living-pack.md): its variants ship in one pack per game,
# "Island Event Collection\\living.pak", and its seeds are manifest rows (id living_..., one series per category).
LIVING_NAME = "living.pak"
LIVING_SOURCE = ROOT / "docs" / "more-island-events" / "Isola_ALL_IN_ONE_Modular_Living_Event_Engine.txt"
LIVING_SHA256 = (ROOT / "data" / "living_events" / "SOURCE.sha256").read_text(encoding="ascii").split()[0].upper()
LIVING_CREDIT_LINE = 23815

# The source's own credit texts, by line (1-based, inclusive): the ledger, then each section's credit block.
LEDGER = (1, 91)
CREDIT_BLOCKS = (
    (6840, 6848, "V13 (Cooking Contest add-ons and the other competition add-ons)"),
    (7627, 7634, "V14 (the Golden Child scenes)"),
    (7838, 7839, "V15 (new game-exclusive island events)"),
    (8037, 8043, "V17 (the competition suite in every game)"),
    (8496, 8499, "V18 (the twelve competitions)"),
    (8906, 8909, "V20 (crises and the canon and setting guide)"),
    (9367, 9368, "V21 (the potters' trials and the crafts fair)"),
    (9555, 9560, "V22 (drawing, parenting and the pending title note)"),
    (9973, 9976, "V23 (pranks, misunderstandings and everyday chaos)"),
    (10142, 10146, "V24 (the revolutionary invention / discovery)"),
    (10434, 10438, "V27 (all ages, personality, relationships and consequences)"),
    (10949, 10951, "V28 (consequences that follow the villagers)"),
)


# The second source: the owner's Companion Anthology (data/event_collection/companion/<volume>/<id>.json are its
# events).  Its credits go in the same Credits.txt, verbatim: the anthology's own credit, then each volume's or part's.
COMPANION = ROOT / "docs" / "more-island-events" / "Isola_COMPLETE_Master_Companion_Anthology_749_Events.txt"
COMPANION_SHA256 = "D39D14DA81B04225308452425069DB3186A62065A3EE634F5C6AFD074E64FF16"
COMPANION_CREDIT_BLOCKS = (
    (1, 5, "the Companion Anthology (its title and credit)"),
    (25, 29, "Companion Volume 5 (Professions, Everyday Life and Personalities)"),
    (54, 58, "Companion Volume 5, Part 1 (Professional Specialties and Exploration)"),
    (1124, 1128, "Companion Volume 5, Part 2 (Everyday Life and Personality)"),
    (2029, 2032, "Companion Volume 5, Part 3 (Small Lives, Deep Roots)"),
    (3771, 3777, "The Lives Between Legends"),
    (5402, 5406, "The Four Ways of Knowing"),
    (6051, 6053, "Stone, Spirit, Strangers and Ordinary Lives"),
    (6769, 6771, "Volume II, The Inner Lives of Isola"),
    (7087, 7088, "The Living Catalogue"),
)

# The third source: the owner's all-in-one Living Event Engine file (data/event_collection/living/<volume>/<id>.json
# are its fixed event volumes).  Its credits go in the same Credits.txt, verbatim: the file's own credit, then each
# volume's heading and credit line.
LIVING = ROOT / "docs" / "more-island-events" / "Isola_ALL_IN_ONE_Modular_Living_Event_Engine.txt"
LIVING_SHA256 = "CBB46FCBBDB594F54B69DA9297CA21242B51D15EE7B41080C795E8555ADDF31C"
LIVING_CREDIT_BLOCKS = (
    (1, 2, "the all-in-one Living Event Engine file (its title and credit)"),
    (20202, 20206, "Experimental Medicine, Last Resorts and Comfort Care"),
    (20625, 20627, "The Healer's Hands, the Farmer's Fields, and the Weaver's Dreams"),
    (21229, 21230, "The Circle of Life, Rights, and Remembrance"),
    (21650, 21650, "Colors, Masks, Peoples and Choice (its heading; no credit line of its own)"),
    (22165, 22165, "The Unseen Horizon, Cryptids, and the Silent Gods (its heading; no credit line of its own)"),
    (22689, 22689, "The Many Ways of Isola (its heading; no credit line of its own)"),
    (23315, 23316, "The Weight of a Name (its heading; no credit line of its own)"),
)

# The fourth and fifth sources (2026-11-15): the owner's separate companion anthology "Isola - Beyond the Horizon"
# (data/event_collection/horizon/) and "Role Models and Good Examples" (data/event_collection/rolemodels/).  Their
# credits go in the same Credits.txt, verbatim: each file's title lines (neither names an author).  The Role Models
# file has CRLF line ends; Credits.txt is LF, so its lines are copied with LF ends.
HORIZON = ROOT / "docs" / "more-island-events" / "Isola_Beyond_the_Horizon_Expanded_80_Events.txt"
HORIZON_SHA256 = "8EBAE8DE40A13179AC908777E4D02F43D2DCB4F397D77A367C3A75878A266F1C"
HORIZON_CREDIT_BLOCKS = (
    (1, 3, "Beyond the Horizon: The World We Imagine (its title lines)"),
    (546, 547, "Beyond the Horizon: Expansion Volume II (its heading)"),
)
ROLEMODELS = ROOT / "docs" / "more-island-events" / "Role_Models_and_Good_Examples_40_Events.txt"
ROLEMODELS_SHA256 = "688010B259DDA145CB9B7E3AFB78658BE5FC960CE323DA9C0BB9C241B26A14AD"
ROLEMODELS_CREDIT_BLOCKS = (
    (1, 3, "Role Models and Good Examples (its title and introduction)"),
)
SOURCE_LINE_WORDS = {"companion": "companion source lines", "living": "living source lines",
                     "horizon": "Beyond the Horizon source lines", "rolemodels": "Role Models source lines"}
# The owner-approved drafts of 2026-11-15, set A (data/event_collection/drafts_a/; collection_lib.DRAFTS_A): each
# file's title line(s), verbatim (Part II's: its heading after the ChatGPT preamble).
DRAFTS_A_DIR = ROOT / "data" / "event_collection" / "drafts_a"
DRAFTS_A_FILES = (   # (source id, file name, first credit line, last)
    ("da_il01", "New Events - Inner Life (draft for owner).txt", 1, 1),
    ("da_il02", "New Events - Inner Life Part II (11-40).txt", 15, 17),
    ("da_il03", "New Events - Inner Life Part III (41-60, draft for owner).txt", 1, 1),
    ("da_il04", "New Events - Inner Life Part IV (61-80, draft for owner).txt", 1, 1),
    ("da_il05", "New Events - Inner Life Part V (81-100, draft for owner).txt", 1, 1),
    ("da_il06", "New Events - Inner Life Part VI (101-120, draft for owner).txt", 1, 1),
    ("da_il07", "New Events - Inner Life Part VII (121-140, draft for owner).txt", 1, 1),
    ("da_il08", "New Events - Inner Life Part VIII (141-160, draft for owner).txt", 1, 1),
    ("da_il09", "New Events - Inner Life Part IX (161-180, draft for owner).txt", 1, 1),
    ("da_il10", "New Events - Inner Life Part X (181-200, draft for owner).txt", 1, 1),
    ("da_wd", "New Events - What's That Doing Here (draft for owner).txt", 1, 1),
    ("da_lo", "New Events - Luck, Omens and Lavastones (draft for owner).txt", 1, 1),
)
SOURCE_LINE_WORDS.update({sid: f"{name[len('New Events - '):-len('.txt')]} source lines"
                          for sid, name, _a, _b in DRAFTS_A_FILES})


def drafts_a_credit_sources() -> list[tuple[str, Path, str, tuple]]:
    """(name, path, SHA-256, credit blocks) of each draft file of set A."""
    out = []
    for sid, name, a, b in DRAFTS_A_FILES:
        digest = (DRAFTS_A_DIR / f"DA_{sid[3:].upper()}.sha256").read_text(encoding="ascii").split()[0].upper()
        out.append((name[len("New Events - "):-len(".txt")].upper(), ROOT / "docs" / "more-island-events" / name,
                    digest, ((a, b, "the draft's title"),)))
    return out


# The owner-approved draft event files, group B (data/event_collection/drafts_b/, scripts/drafts_b/): each file's title
# and introduction lines (1-3) verbatim, as the 2026-11-15 sources above.
DRAFTS_B_FILES = (   # (source id, topic, SHA-256)
    ("draft_hum", "Humor and Absurdity", "3E0CD2569773F511D29B33C6A6DE00A35F18BC17327B72E005DEC73A2A26D6FB"),
    ("draft_tt", "Tall Tales and Self-Interest", "A3236FA05F3D2E7EF2AE25854A12D36EC31125AB9E9AE3C6784BF5C83E22908A"),
    ("draft_hon", "Honesty and Accountability", "E5D919720B552C9887EB3139505704C440532FD49DEBEB8502B5287DC90AA418"),
    ("draft_jus", "Justice and Consequences", "7B178BDA4C21DFA1BF2887F1E98255D745A71B910F6F407E827091B5B6C392F8"),
    ("draft_dep", "Departures and Exile", "E45D9DAC577D689C6B32D973E398B95F4520AE687A73C051B56073C00F6C6E66"),
    ("draft_drm", "Dreams and Ambitions", "1193D682BC84B98BCF249D015991913DA280A92B31BAF13146C99B2ED9C1A87B"),
    ("draft_fea", "Fears and Doubts", "3D9320A0ECFD2A73FF03DAEB0C8A2B92E0F84ED2B41CBC211DD75CC55F97ED9E"),
    ("draft_day", "Good, Bad and Ordinary Days", "F2DFD2C82F722F7F7D69218D64ED3D574441EEF34F260C87AEDDC905E1E136AD"),
)
# Group C, the same way (data/event_collection/drafts_c/, scripts/drafts_c/).
DRAFTS_C_FILES = (   # (source id, topic, SHA-256)
    ("draft_hea", "Healing, Psychology and Medicine", "ED3A9EB0219F81643E6541EA9864F29D2E74EC6AAEC1ED31C7516B430C225E54"),
    ("draft_adv", "Advice and Decisions", "23B661573D688709C8D1A5DD835BB01B1130148094A14613F865D6451A8620CF"),
    ("draft_fam2", "Relationships, Singlehood and Family",
     "DE9AC31AF5065BE355570BE94220D4F03F785796E4BCDD0D333226D0D98C342F"),
    ("draft_blf", "Belief and Identity", "4F86DBE789C57167E1E9DABBE90F2D176C38444884771E07D557A03605F76250"),
    ("draft_nat", "Nature, Ecology and Animals", "9748288F9599AE37FAF9C0F8C90E3DAD7D3F7FDAEA6C8FA3F7059686FB9BB4AF"),
    ("draft_div", "Disability and Diversity", "949C258F820466F38E62D371E3904F16877DB4E364CFD4E2A1E0F83E16EF07C7"),
    ("draft_his", "History and Collective Memory", "3D379DC35AC8E4E3A6C1A1CE833B3C78DA1628AAE1BFBA743E2B0CA235863529"),
    ("draft_lif", "Pondering How Life Has Gone", "C2467D9089ECE3FE49249D8269F886ED54BBA827C9F121360AB4468612C31B89"),
)
SOURCE_LINE_WORDS.update({sid: f"{topic} source lines" for sid, topic, _ in DRAFTS_B_FILES + DRAFTS_C_FILES})


def source_lines(path: Path = SOURCE, sha256: str = SOURCE_SHA256) -> list[str]:
    """A frozen source's lines, each with its own line ending, after checking its SHA-256."""
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest().upper()
    if digest != sha256:
        raise SystemExit(f"{path.name}: SHA-256 {digest}, expected {sha256}")
    return raw.decode("utf-8").splitlines(keepends=True)


def span(lines: list[str], first: int, last: int) -> str:
    """Source lines first..last, verbatim."""
    return "".join(lines[first - 1:last])


def event_files(src: Path = DATA) -> list[Path]:
    if not src.is_dir():
        return []
    return sorted(p for p in src.rglob("*.json") if p.name not in NOT_EVENTS)


def shared_pools(src: Path = DATA):
    path = src / "shared_pools.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def one_line(text: str) -> str:
    return " ".join(str(text).replace("\t", " ").split())


def compile_events(src: Path = DATA) -> list[dict]:
    """Every event under `src`: {id, title, games, weight, series, credit, lines, cieg}.  A problem fails the build."""
    pools = shared_pools(src)
    out, seen = [], {}
    for path in event_files(src):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format") != "vvfp-cie-graph" or not isinstance(data.get("collection"), dict):
            continue
        g, problems = cie.validate(graph_for_engine(data), scrolling=True, shared_pools=pools)   # the rows require Scrolling Popups
        if problems:
            raise SystemExit(f"{path.relative_to(ROOT)}: " + "; ".join(problems[:5]))
        meta = data["collection"]
        ident = str(meta.get("id", ""))
        cap = VV1_ID_MAX if 1 in g.get("games", data.get("games", [])) else ID_MAX
        if not re.fullmatch(r"[a-z0-9_]+", ident) or len(ident) > cap:
            raise SystemExit(f"{path.relative_to(ROOT)}: collection id {ident!r} must be [a-z0-9_], at most "
                             f"{cap} characters (a deep game folder's paths must still fit)")
        if ident in seen:
            raise SystemExit(f"{path.relative_to(ROOT)}: collection id {ident} is also {seen[ident]}")
        seen[ident] = path.relative_to(ROOT).as_posix()
        out.append({
            "id": ident,
            "title": one_line(g.get("title", data.get("title", ident))),
            "games": sorted(int(n) for n in g.get("games", data.get("games", []))),
            "weight": int(meta.get("draw_weight", 1) or 1),
            "series": one_line(meta.get("series") or ""),
            "credit": one_line(meta.get("credit", "")),
            "graph": g,
            "description": one_line(meta.get("description", "")),
            "description_variants": meta.get("description_variants") or [],
            "lines": meta.get("lines"),
            "source": meta.get("source", "v28"),
            "cieg": cie.compile_graph(g),
        })
    return sorted(out, key=lambda e: e["id"])


GUARDIANS = "guardians_of_isola"            # Guardians of Isola Rewrite (New Believers): the engine's patch name


def description_with(e: dict, patches: tuple[str, ...]) -> str:
    """The event's Pick Island Event sentence with `patches` on: the first description variant whose patch is on."""
    for v in e["description_variants"]:
        if v["if"].get("patch") in patches:
            return one_line(v["description"])
    return e["description"]


def manifest_line(game: int, e: dict) -> str:
    title = one_line(cie.event_title(e["graph"], game))
    description = e["description"]
    extra = ["", ""]
    if game == 5:
        alt_title = one_line(cie.event_title(e["graph"], game, (GUARDIANS,)))
        alt_description = description_with(e, (GUARDIANS,))
        extra = [alt_title if alt_title != title else "", alt_description if alt_description != description else ""]
    return "\t".join([e["id"], title, ",".join(str(n) for n in e["games"]), str(e["weight"]), e["series"],
                      e["credit"], description] + extra)


def living_line(r: dict) -> str:
    """A Living Event Engine seed's row: its event is in living.pak (the id's living_ prefix says so)."""
    return "\t".join([r["id"], r["title"], ",".join(str(n) for n in r["games"]), str(r["weight"]), r["series"],
                      one_line(r["credit"]), one_line(r["description"]), "", ""])


def manifest_text(game: int, events: list[dict], living_rows: list[dict] | None = None) -> str:
    rows = ["# Isola Grand Event Collection: the events of this game, read by VVFP Story Upgrades.dll.",
            "# id\ttitle\tgames\tdraw weight\tseries\tcredit\tdescription\tGuardians title\tGuardians description"]
    for e in events:
        if game in e["games"]:
            rows.append(manifest_line(game, e))
    for r in living_rows or []:
        rows.append(living_line(r))
    return "\n".join(rows) + "\n"


def living_source_line(n: int) -> str:
    """Line n of the frozen Living Event Engine source, after checking its SHA-256."""
    raw = LIVING_SOURCE.read_bytes()
    digest = hashlib.sha256(raw).hexdigest().upper()
    if digest != LIVING_SHA256:
        raise SystemExit(f"{LIVING_SOURCE.name}: SHA-256 {digest}, expected {LIVING_SHA256}")
    return raw.decode("utf-8").split("\n")[n - 1].rstrip("\r")


def credits_text(events: list[dict], lines: list[str] | None = None, living_on: bool = False) -> str:
    """The credits: the ledger and each section's credit block verbatim, then each event's own credit (and, with the
    Living Event Engine, its source's credit line verbatim)."""
    lines = lines if lines is not None else source_lines()
    out = ["ISOLA GRAND EVENT COLLECTION - CREDITS\n",
           "\n",
           f"Source: {SOURCE.name} (SHA-256 {SOURCE_SHA256}). The texts below are copied from it verbatim.\n",
           "\n",
           f"THE CREDIT LEDGER (source lines {LEDGER[0]}-{LEDGER[1]})\n",
           "\n",
           span(lines, *LEDGER),
           "\n"]
    for first, last, what in CREDIT_BLOCKS:
        out += [f"SECTION CREDIT: {what} (source lines {first}-{last})\n", "\n", span(lines, first, last), "\n"]
    comp = source_lines(COMPANION, COMPANION_SHA256)
    out += ["THE COMPANION ANTHOLOGY\n",
            "\n",
            f"Source: {COMPANION.name} (SHA-256 {COMPANION_SHA256}). The texts below are copied from it verbatim.\n",
            "\n"]
    for first, last, what in COMPANION_CREDIT_BLOCKS:
        out += [f"COMPANION CREDIT: {what} (companion source lines {first}-{last})\n", "\n", span(comp, first, last),
                "\n"]
    liv = source_lines(LIVING, LIVING_SHA256)
    out += ["THE LIVING EVENT ENGINE'S EVENT VOLUMES\n",
            "\n",
            f"Source: {LIVING.name} (SHA-256 {LIVING_SHA256}). The texts below are copied from it verbatim.\n",
            "\n"]
    for first, last, what in LIVING_CREDIT_BLOCKS:
        out += [f"LIVING CREDIT: {what} (living source lines {first}-{last})\n", "\n", span(liv, first, last), "\n"]
    drafts_b = tuple((f"NEW EVENTS: {topic.upper()}",
                      ROOT / "docs" / "more-island-events" / f"New Events - {topic} (draft for owner).txt", digest,
                      ((1, 3, f"{topic} (its title and introduction)"),))
                     for _sid, topic, digest in DRAFTS_B_FILES + DRAFTS_C_FILES)
    for name, path, digest, blocks in (("BEYOND THE HORIZON", HORIZON, HORIZON_SHA256, HORIZON_CREDIT_BLOCKS),
                                       ("ROLE MODELS AND GOOD EXAMPLES", ROLEMODELS, ROLEMODELS_SHA256,
                                        ROLEMODELS_CREDIT_BLOCKS), *drafts_a_credit_sources(), *drafts_b):
        src = [s.replace("\r\n", "\n") for s in source_lines(path, digest)]
        out += [f"{name}\n", "\n",
                f"Source: {path.name} (SHA-256 {digest}). The texts below are copied from it verbatim.\n", "\n"]
        for first, last, what in blocks:
            out += [f"{name} CREDIT: {what} (source lines {first}-{last})\n", "\n", span(src, first, last), "\n"]
    out += ["EACH EVENT'S CREDIT\n", "\n"]
    if not events:
        out.append("(No event of the collection is in this build yet.)\n")
    for e in events:
        which = SOURCE_LINE_WORDS.get(e.get("source"), "source lines")
        where = f" ({which} {e['lines'][0]}-{e['lines'][1]})" if isinstance(e.get("lines"), list) else ""
        out.append(f"{e['title']}{where}: {e['credit']}\n")
    if living_on:
        out += ["\n",
                f"THE LIVING EVENT ENGINE (source: {LIVING_SOURCE.name}, SHA-256 {LIVING_SHA256}, line "
                f"{LIVING_CREDIT_LINE}, verbatim)\n",
                "\n",
                living_source_line(LIVING_CREDIT_LINE) + "\n",
                "\n",
                "Its situation seeds, roles, personalities, approaches and outcomes (the Living Engine bank, lines "
                "23812-25133) and its authored situations and outcomes (MC, lines 25134-26616) are combined by the "
                "patcher into the events in " + LIVING_NAME + "; the same credit covers both.\n"]
    return "".join(out)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def description(game: int, count: int, living_count: int = 0) -> str:
    return (
        "Adds the Isola Grand Event Collection, the owner's large collection of island events (written with ChatGPT; "
        "the credits come with it, in \"Virtual Villagers Fun Patcher Files\\" + FOLDER + "\\" + CREDITS_NAME + "\"), as rare, separate events: "
        "the game's own island events and their chances never change. After a natural island event, a separate rare "
        "roll (Story / Cheat Upgrades) may bring one of these events -- or one of More Island Events' -- some hours "
        "later, between two natural ones: about three in seven days of game time, never during a village's two "
        "opening events, never while the village is in trouble (the game's own rescue rule, little food, much "
        "sickness, few grown villagers) and never in place of a rescue event. Each event needs the villagers it names "
        "(never the protected ones for anything harmful); when it cannot be cast, another is drawn. Pick Island Event "
        "lists them (with what each needs), and the Custom Island Event library has them in its own \"" + NAME
        + "\" group. " + (f"{count} events in this game in this build. " if count else "")
        + (f"The Living Event Engine adds {living_count} situations, each shown as one of its owner-written "
           "variants with the villagers' names (each category counts as one event in the rare roll). "
           if living_count else "")
        + "Off by default; Owner's Defaults ticks it; not part of Classic VV Difficulty. "
        "**Needs Story / Cheat Upgrades (on by default), which runs these events; ticking this ticks it.** "
        "**Needs Scrolling Popups, which keeps every page of these events on the screen; ticking this ticks it.** "
        "**Unverified in play: the events have not been seen in a running game** (emulated)."
    )


def row(game: int, files: list[tuple[str, str, bytes]], count: int, living_count: int = 0) -> dict:
    return {
        "id": f"vv{game}_isola_grand_event_collection",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": description(game, count, living_count),
        "output_tag": "Isola Grand Event Collection",
        "dependencies": [f"vv{game}_story_cheat_upgrades", f"vv{game}_scrolling_popups"],
        "behavior_changes": [
            "Story / Cheat Upgrades (native/vvfp_story_upgrades/story_collection.inc) rolls once after each natural "
            "island event (the Island Events Seen count went up with nothing armed or on its way), past the two "
            "opening events and outside trouble: A New Home 30%, The Lost Children 25%, the later three 20%. The "
            "roll is due 30% to 70% of the way to the next natural event; at due it waits while anything else is "
            "armed, within 60 seconds of a natural event, or while a God Power is armed (New Believers); the trouble "
            "guard cancels it. Every event that can happen is equally likely, More Island Events' and the "
            "collection's (the Grand collection's and the Companion Anthology's) alike: one draw over all of them, "
            "each collection event by its draw weight (1), a series as one event; the event is armed as a purchase "
            "arms one, so the island timer's keeper puts the natural next time back after it.",
            f"The events of this game are compiled .cieg files in \"Virtual Villagers Fun Patcher Files\\{FOLDER}\", "
            "listed in its manifest.txt; Pick Island Event lists them (strict casting: every requirement must hold) "
            "and the in-game library's \"Isola Grand Event Collection\" group sells them (the library's casting: a "
            "requirement nobody meets is dropped, the protected villagers' safety never).",
        ],
        "explicit_non_changes": [
            "No executable byte is patched and no island event of the game's own changes, in its timing or its "
            "chances: the stock draw is never widened.",
            "Nothing is written to the save; the due roll is kept beside it, deleted once delivered or cancelled.",
        ],
        "evidence_status": ("the roll, its edge, its rates, the due time, the waits, the trouble guard, the choice and "
                            "the save's file emulated in tests/test_collection_trigger.py; the files and the rows in "
                            "tests/test_event_collection_package.py; runtime/player confirmation pending"),
        "companion_files": [
            {"source": source, "destination": destination, "sha256": sha(data)}
            for source, destination, data in files
        ],
        "patches": [],
        "runtime_detours": [],
    }


_LIVING_CACHE: dict = {}


def living_build() -> tuple[list, dict[int, bytes]]:
    """The Living Event Engine's variants and packs (built once per process: about half a minute)."""
    if "built" not in _LIVING_CACHE:
        _LIVING_CACHE["built"] = living.build()
    return _LIVING_CACHE["built"]


def build(src: Path = DATA, assets: Path = ASSETS, data_dir: Path = ROOT / "data", docs: Path = CREDITS_MD,
          write: bool = True, living_on: bool | None = None) -> dict[int, dict]:
    """Compile, write the files and the five rows; returns them by game.  The Living Event Engine's packs and rows
    come with the shipped collection (`living_on` None: when `src` is the shipped data)."""
    if living_on is None:
        living_on = Path(src) == DATA
    lines = source_lines()
    events = compile_events(src)
    credits = credits_text(events, lines, living_on)
    variants, packs = living_build() if living_on else ([], {})
    rows = {}
    planned: dict[Path, bytes] = {}
    for e in events:
        planned[assets / f"{e['id']}.cieg"] = e["cieg"]
    planned[assets / CREDITS_NAME] = credits.encode("utf-8")
    for game in GAMES:
        living_rows = living.manifest_rows(game, variants) if living_on else []
        manifest = manifest_text(game, events, living_rows).encode("utf-8")
        planned[assets / f"vv{game}" / "manifest.txt"] = manifest
        files = [(f"{assets.relative_to(ROOT).as_posix()}/vv{game}/manifest.txt", f"{FOLDER}/manifest.txt", manifest),
                 (f"{assets.relative_to(ROOT).as_posix()}/{CREDITS_NAME}", f"{FOLDER}/{CREDITS_NAME}",
                  credits.encode("utf-8"))]
        if living_on:
            planned[assets / f"vv{game}" / LIVING_NAME] = packs[game]
            files.append((f"{assets.relative_to(ROOT).as_posix()}/vv{game}/{LIVING_NAME}", f"{FOLDER}/{LIVING_NAME}",
                          packs[game]))
        mine = [e for e in events if game in e["games"]]
        files += [(f"{assets.relative_to(ROOT).as_posix()}/{e['id']}.cieg", f"{FOLDER}/{e['id']}.cieg", e["cieg"])
                  for e in mine]
        rows[game] = row(game, files, len(mine), len(living_rows))
    if write:
        for path, data in planned.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for stale in assets.glob("*.cieg"):
            if stale not in planned:
                stale.unlink()
        docs.write_bytes(credits.encode("utf-8"))
        for game, record in rows.items():
            (data_dir / f"vv{game}_isola_grand_event_collection_feature.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return rows


def main() -> None:
    rows = build()
    for game, record in rows.items():
        print(f"vv{game}: {len(record['companion_files']) - 3} events and living.pak -> "
              f"data/vv{game}_isola_grand_event_collection_feature.json")
    # The Game Mechanics page's index (src/vv_game_mechanics_collection.py), the living seeds from the variants.
    import vv_game_mechanics_collection as gc
    gc.write_index([(v.manifest_id, v.graph) for v in living_build()[0]])
    print("wrote data/event_collection_index.json")


if __name__ == "__main__":
    main()
