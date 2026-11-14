"""Write "Isola Grand Event Collection" (vvN_isola_grand_event_collection): the owner's collection of island events
(docs/more-island-events/Virtual_Villagers_Isola_Grand_Event_Collection_v26_user_source_credited.txt, the frozen
source), one row per game.

The events are data: one version 6 branching Custom Island Event graph per event under data/event_collection/
(any folder depth; data/event_collection/shared_pools.json holds the pools they share), each with its "collection"
block (id, source lines, section, credit, draw weight, series).  This compiles every one with the patcher's own
src/vv_cie_graph.py (validate, then compile_graph) and writes:

  * assets/event_collection/<id>.cieg -- each event's compiled file;
  * assets/event_collection/vvN/manifest.txt -- the events of game N, one line each:
    id<TAB>title<TAB>games<TAB>draw weight<TAB>series<TAB>credit (Story / Cheat Upgrades' story_collection.inc reads
    it from "<game folder>\\Virtual Villagers Fun Patcher Files\\Island Event Collection\\manifest.txt");
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

sys.path.insert(0, str(ROOT / "scripts"))
from collection_check import graph_for_engine  # noqa: E402  (drops the authoring-only keys)

SOURCE = ROOT / "docs" / "more-island-events" / \
    "Virtual_Villagers_Isola_Grand_Event_Collection_v26_user_source_credited.txt"
SOURCE_SHA256 = "F5ABB8BF95F7345EDA4F7ACF676E58C536841C7767322348AAD8134CDC96E567"
DATA = ROOT / "data" / "event_collection"
ASSETS = ROOT / "assets" / "event_collection"
FOLDER = "Island Event Collection"          # beside the companions (src/patcher_files.py PATCHER_READ_FOLDERS)
CREDITS_NAME = "Credits.txt"                # short: every path stays inside the game's own longest file's length
ID_MAX = 30                                 # an event id's longest (its .cieg's path, likewise)
CREDITS_MD = ROOT / "docs" / "more-island-events" / "Isola Grand Event Collection - Credits.md"
NAME = "Isola Grand Event Collection"
GAMES = (1, 2, 3, 4, 5)
NOT_EVENTS = {"manifest.json", "shared_pools.json"}

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
)


def source_lines() -> list[str]:
    """The frozen source's lines, each with its own line ending, after checking its SHA-256."""
    raw = SOURCE.read_bytes()
    digest = hashlib.sha256(raw).hexdigest().upper()
    if digest != SOURCE_SHA256:
        raise SystemExit(f"{SOURCE.name}: SHA-256 {digest}, expected {SOURCE_SHA256}")
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
        if not re.fullmatch(r"[a-z0-9_]+", ident) or len(ident) > ID_MAX:
            raise SystemExit(f"{path.relative_to(ROOT)}: collection id {ident!r} must be [a-z0-9_], at most "
                             f"{ID_MAX} characters (a deep game folder's paths must still fit)")
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
            "lines": meta.get("lines"),
            "cieg": cie.compile_graph(g),
        })
    return sorted(out, key=lambda e: e["id"])


def manifest_text(game: int, events: list[dict]) -> str:
    rows = ["# Isola Grand Event Collection: the events of this game, read by VVFP Story Upgrades.dll.",
            "# id\ttitle\tgames\tdraw weight\tseries\tcredit"]
    for e in events:
        if game in e["games"]:
            rows.append("\t".join((e["id"], e["title"], ",".join(str(n) for n in e["games"]), str(e["weight"]),
                                   e["series"], e["credit"])))
    return "\n".join(rows) + "\n"


def credits_text(events: list[dict], lines: list[str] | None = None) -> str:
    """The credits: the ledger and each section's credit block verbatim, then each event's own credit."""
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
    out += ["EACH EVENT'S CREDIT\n", "\n"]
    if not events:
        out.append("(No event of the collection is in this build yet.)\n")
    for e in events:
        where = f" (source lines {e['lines'][0]}-{e['lines'][1]})" if isinstance(e.get("lines"), list) else ""
        out.append(f"{e['title']}{where}: {e['credit']}\n")
    return "".join(out)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def description(game: int, count: int) -> str:
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
        + "Off by default; Owner's Defaults ticks it; not part of Classic VV Difficulty. "
        "**Needs Story / Cheat Upgrades (on by default), which runs these events; ticking this ticks it.** "
        "**Needs Scrolling Popups, which keeps every page of these events on the screen; ticking this ticks it.** "
        "**Unverified in play: the events have not been seen in a running game** (emulated)."
    )


def row(game: int, files: list[tuple[str, str, bytes]], count: int) -> dict:
    return {
        "id": f"vv{game}_isola_grand_event_collection",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": description(game, count),
        "output_tag": "Isola Grand Event Collection",
        "dependencies": [f"vv{game}_story_cheat_upgrades", f"vv{game}_scrolling_popups"],
        "behavior_changes": [
            "Story / Cheat Upgrades (native/vvfp_story_upgrades/story_collection.inc) rolls once after each natural "
            "island event (the Island Events Seen count went up with nothing armed or on its way), past the two "
            "opening events and outside trouble: A New Home 30%, The Lost Children 25%, the later three 20%. The "
            "roll is due 30% to 70% of the way to the next natural event; at due it waits while anything else is "
            "armed, within 60 seconds of a natural event, or while a God Power is armed (New Believers); the trouble "
            "guard cancels it. More Island Events and the collection are drawn 1:1, each event of the collection by "
            "its draw weight, a series as one event; the event is armed as a purchase arms one, so the island timer's "
            "keeper puts the natural next time back after it.",
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


def build(src: Path = DATA, assets: Path = ASSETS, data_dir: Path = ROOT / "data", docs: Path = CREDITS_MD,
          write: bool = True) -> dict[int, dict]:
    """Compile, write the files and the five rows; returns them by game."""
    lines = source_lines()
    events = compile_events(src)
    credits = credits_text(events, lines)
    rows = {}
    planned: dict[Path, bytes] = {}
    for e in events:
        planned[assets / f"{e['id']}.cieg"] = e["cieg"]
    planned[assets / CREDITS_NAME] = credits.encode("utf-8")
    for game in GAMES:
        manifest = manifest_text(game, events).encode("utf-8")
        planned[assets / f"vv{game}" / "manifest.txt"] = manifest
        files = [(f"{assets.relative_to(ROOT).as_posix()}/vv{game}/manifest.txt", f"{FOLDER}/manifest.txt", manifest),
                 (f"{assets.relative_to(ROOT).as_posix()}/{CREDITS_NAME}", f"{FOLDER}/{CREDITS_NAME}",
                  credits.encode("utf-8"))]
        mine = [e for e in events if game in e["games"]]
        files += [(f"{assets.relative_to(ROOT).as_posix()}/{e['id']}.cieg", f"{FOLDER}/{e['id']}.cieg", e["cieg"])
                  for e in mine]
        rows[game] = row(game, files, len(mine))
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
        print(f"vv{game}: {len(record['companion_files']) - 2} events -> "
              f"data/vv{game}_isola_grand_event_collection_feature.json")


if __name__ == "__main__":
    main()
