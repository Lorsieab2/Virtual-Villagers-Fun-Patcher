"""One folder of logs per save slot: the Python side (the owner, 2026-10-10: "Just put the logs in
separate folders per slot").

Every log now lives in "<save folder>\\Virtual Villagers Fun Patcher Logs\\Save <S>\\<its folder>\\<its
name>".  The shared "...Logs\\<its folder>\\" older builds wrote is never moved, split, renamed or
deleted: every reader reads it first (each record kept under its own slot's "Village: ... (Save S)"
header) and then the slot's own folder, as one history.  Numbered records are numbered per GAME, so the
checks of repeated numbers look across every folder.  The Python writers append into the slot's own
folder.  All five games; every folder is a temporary one.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_log_contradictions as contra  # noqa: E402
import vv_log_tools as tools  # noqa: E402
import vv_move_old_names as move  # noqa: E402
import vv_save_backup  # noqa: E402
import vv_save_layout as layout  # noqa: E402
import vv_tribe_rename  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
NOW = datetime(2026, 10, 10, 12, 0, 0)
GAMES = (1, 2, 3, 4, 5)
TITLES = {g.number: g.title for g in vv_tribe_rename.GAMES}
checker = tools.load_checker()


class NoGame:
    def find(self, exe_name):
        return []


@pytest.fixture
def folder():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


def game_folder(root: Path, game: int) -> Path:
    path = root / f"{TITLES[game]} - Modded"          # the save folder's name for a patched game
    path.mkdir()
    return path


def write(folder: Path, relative: str, text: str) -> Path:
    path = folder / LOGS / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))
    return path


def births_name(game: int, n: int = 1) -> str:
    return f"Virtual Villagers {game} Births and Conceptions Log {n}.txt"


def birth(n: int, child: str) -> str:
    return (f"Birth {n}\n  Child: {child}\n    Sex: Male\n    Head: 3\n    Body: 4\n  Mother: Ma\n    Head: 1\n"
            f"    Body: 1\n  Father: Pa\n    Head: 2\n    Body: 2\n  Born as: Single birth\n\n")


def death(n: int, name: str) -> str:
    return (f"Death {n}\n  Name: {name}\n  Age at death: 1600\n  Sex: Male\n  Cause of death: Old age\n"
            f"  Head: 5\n  Body: 6\n  Likes: (none)\n  Dislikes: (none)\n\n")


def tree(path: Path) -> dict[str, bytes]:
    return {str(p.relative_to(path)): p.read_bytes() for p in sorted(path.rglob("*")) if p.is_file()}


# ---- reading: the shared folder, then the slot's own, as one history ----------------------------

@pytest.mark.parametrize("game", GAMES)
def test_records_in_the_slot_folder_are_read(folder, game):
    g = game_folder(folder, game)
    write(g, f"Save 3/Births and Conceptions/{births_name(game)}", "Village: Cee (Save 3)\n" + birth(1, "Kid"))
    records, files = checker.births_log(g, game, 3)
    assert [r.child.name for r in records if r.kind == "birth"] == ["Kid"]
    assert records.village == "Village: Cee (Save 3)"
    assert [layout.is_slot_folder(p) for p in files] == [3]


@pytest.mark.parametrize("game", GAMES)
def test_shared_then_slot_is_one_history_for_the_slot_only(folder, game):
    g = game_folder(folder, game)
    write(g, f"Births and Conceptions/{births_name(game)}",
          "Village: Ann (Save 1)\n" + birth(1, "Old1") + "Village: Bea (Save 2)\n" + birth(2, "Other")
          + "Village: Ann (Save 1)\n" + birth(3, "Old2"))
    write(g, f"Save 1/Births and Conceptions/{births_name(game)}", "Village: Ann (Save 1)\n" + birth(4, "New1"))
    write(g, f"Save 2/Births and Conceptions/{births_name(game)}", "Village: Bea (Save 2)\n" + birth(5, "New2"))
    one, files = checker.births_log(g, game, 1)
    assert [r.child.name for r in one] == ["Old1", "Old2", "New1"], "shared first, then the slot's; once each"
    assert [layout.is_slot_folder(p) for p in files] == [None, 1]
    two, _ = checker.births_log(g, game, 2)
    assert [r.child.name for r in two] == ["Other", "New2"], "two slots stay apart"
    # The same for the numbered records read by marker (Deaths, Unaccounted).
    stem = f"Virtual Villagers {game} Deaths Log"
    write(g, f"Deaths and Disappearances/{stem} 1.txt",
          "Village: Ann (Save 1)\n" + death(1, "A1") + "Village: Bea (Save 2)\n" + death(2, "B1"))
    write(g, f"Save 1/Deaths and Disappearances/{stem} 1.txt", "Village: Ann (Save 1)\n" + death(3, "A2"))
    write(g, f"Save 2/Deaths and Disappearances/{stem} 1.txt", "Village: Bea (Save 2)\n" + death(4, "B2"))
    names = [r.split("\n")[1] for r in checker.deaths_records(g, game, 1)]
    assert names == ["  Name: A1", "  Name: A2"]
    assert [r.split("\n")[1] for r in checker.deaths_records(g, game, 2)] == ["  Name: B1", "  Name: B2"]
    # log_files: every shared file before any slot's.
    slots = [layout.is_slot_folder(p) for p in checker.log_files(g)]
    assert slots == sorted(slots, key=lambda s: s or 0)


@pytest.mark.parametrize("game", GAMES)
def test_an_older_deaths_folder_and_the_slot_folder_read_together(folder, game):
    g = game_folder(folder, game)
    stem = f"Virtual Villagers {game} Deaths Log"
    write(g, f"Deaths/{stem} 1.txt", "Village: Ann (Save 1)\n" + death(1, "A1"))
    write(g, f"Deaths and Disappearances/{stem} 1.txt", "Village: Ann (Save 1)\n" + death(1, "A1") + death(2, "A2"))
    write(g, f"Save 1/Deaths and Disappearances/{stem} 1.txt", "Village: Ann (Save 1)\n" + death(3, "A3"))
    names = [r.split("\n")[1] for r in checker.deaths_records(g, game, 1)]
    assert names == ["  Name: A1", "  Name: A2", "  Name: A3"], "a record kept in both shared folders counts once"


# ---- numbering: one game-wide sequence ----------------------------------------------------------

@pytest.mark.parametrize("game", GAMES)
def test_birth_numbers_continue_across_folders(folder, game):
    g = game_folder(folder, game)
    write(g, f"Births and Conceptions/{births_name(game)}", "Village: Ann (Save 1)\n" + birth(1, "A") + birth(2, "B"))
    write(g, f"Save 1/Births and Conceptions/{births_name(game)}", "Village: Ann (Save 1)\n" + birth(3, "C"))
    write(g, f"Save 2/Births and Conceptions/{births_name(game)}", "Village: Bea (Save 2)\n" + birth(4, "D"))
    assert checker.repeated_birth_numbers(g, game) == {}, "no false repeat across folders"
    write(g, f"Save 2/Births and Conceptions/{births_name(game, 2)}", "Village: Bea (Save 2)\n" + birth(2, "E"))
    repeated = checker.repeated_birth_numbers(g, game)
    assert list(repeated) == [2]
    assert any(where.startswith("Save 2\\") for where in repeated[2]), "the slot file is named as such"


@pytest.mark.parametrize("game", GAMES)
def test_death_numbers_are_checked_across_folders(folder, game):
    g = game_folder(folder, game)
    stem = f"Virtual Villagers {game} Deaths Log"
    write(g, f"Deaths and Disappearances/{stem} 1.txt", "Village: Ann (Save 1)\n" + death(1, "A1") + death(2, "A2"))
    own = write(g, f"Save 1/Deaths and Disappearances/{stem} 1.txt", "Village: Ann (Save 1)\n" + death(3, "A3"))
    write(g, f"Save 2/Deaths and Disappearances/{stem} 1.txt", "Village: Bea (Save 2)\n" + death(4, "B1"))
    assert [f for f in contra.find(g, game, 1) if f.kind == "death_number"] == []
    own.write_bytes(own.read_bytes() + death(2, "A4").replace("\n", "\r\n").encode("latin-1"))
    found = [f for f in contra.find(g, game, 1) if f.kind == "death_number"]
    assert len(found) == 1 and "Save 1\\" in found[0].text
    assert found[0].edits[0][1] == own and found[0].edits[0][3] == "Death 5", "after the game's highest"


@pytest.mark.parametrize("game", GAMES)
def test_repair_numbers_are_checked_across_folders(folder, game):
    g = game_folder(folder, game)
    stem = f"Virtual Villagers {game} Repairs Log"
    write(g, f"Repairs Made/{stem} 1.txt", "Village: Ann (Save 1)\nRepair 1\n  Date: a\n\nRepair 2\n  Date: b\n\n")
    write(g, f"Save 1/Repairs Made/{stem} 1.txt", "Village: Ann (Save 1)\nRepair 3\n  Date: c\n\n")
    two = write(g, f"Save 2/Repairs Made/{stem} 1.txt", "Village: Bea (Save 2)\nRepair 4\n  Date: d\n\n")
    assert [f for f in contra.find(g, game, 1) if f.kind == "repair_number"] == []
    two.write_bytes(two.read_bytes() + b"Repair 3\r\n  Date: e\r\n\r\n")
    found = [f for f in contra.find(g, game, 1) if f.kind == "repair_number"]
    assert len(found) == 1
    assert found[0].edits[0][1] == two and found[0].edits[0][3] == "Repair 5"


# ---- writing: the slot's own folder, numbered after every folder's highest ------------------------

@pytest.mark.parametrize("game", GAMES)
def test_a_repair_note_lands_in_the_slots_repairs_made(folder, game):
    g = game_folder(folder, game)
    stem = f"Virtual Villagers {game} Repairs Log"
    shared = write(g, f"Repairs Made/{stem} 1.txt", "Village: Ann (Save 1)\nRepair 1\n  Date: a\n\nRepair 2\n  Date: b\n\n")
    write(g, f"Save 2/Repairs Made/{stem} 1.txt", "Village: Bea (Save 2)\nRepair 7\n  Date: c\n\n")
    before = shared.read_bytes()
    tools.note_word_repair(g, game, "Village: Ann (Save 1)", [tools.WordFix("x.txt", 1, "x.bak")], NOW)
    own = g / LOGS / "Save 1" / "Repairs Made" / f"{stem} 1.txt"
    text = own.read_bytes().decode("latin-1")
    assert text.startswith("Village: Ann (Save 1)\r\nRepair 8\r\n"), "after the highest in every folder"
    assert shared.read_bytes() == before, "the shared Repairs Made is never written again"
    # The next one follows it; with no village, the slot given.
    tools.note_word_repair(g, game, None, [tools.WordFix("y.txt", 1, "y.bak")], NOW, slot=1)
    assert "Repair 9\r\n" in own.read_bytes().decode("latin-1")
    # Move Old Files' note is no one village's: the shared folder, numbered on after all of them.
    path, start = tools.repair_record_start(g, game, "Village: (all villages in this save folder)", None, NOW)
    assert path == shared and "Repair 10\r\n" in start


@pytest.mark.parametrize("game", GAMES)
def test_an_appended_record_goes_to_the_slots_own_log(folder, game):
    g = game_folder(folder, game)
    stem = f"Virtual Villagers {game} Deaths Log"
    write(g, f"Deaths and Disappearances/{stem} 1.txt", "Village: Ann (Save 1)\n" + death(1, "A1"))
    target = layout.append_target(g, "Deaths and Disappearances", stem, 1, "Death ")
    assert target == g / LOGS / "Save 1" / "Deaths and Disappearances" / f"{stem} 1.txt"
    assert not target.exists(), "never made by looking"
    write(g, f"Save 1/Deaths and Disappearances/{stem} 1.txt",
          "Village: Ann (Save 1)\n" + "".join(death(k, f"D{k}") for k in range(2, 258)))
    assert layout.append_target(g, "Deaths and Disappearances", stem, 1, "Death ").name == f"{stem} 2.txt", \
        "rolls at 256 records, as the game does"


# ---- logs rewritten at each save: the slot's own first ---------------------------------------------

@pytest.mark.parametrize("game", GAMES)
def test_population_statistics_and_history_read_the_slot_first(folder, game):
    g = game_folder(folder, game)
    page = "Village: {v} (Save 1)\nVillager 1\n  Name: {n}\n  Age: 400\n  Head: 1\n  Body: 2\n\n"
    write(g, "Tribe Population/Village Population 1.txt", page.format(v="Ann", n="Stale"))
    assert [v["name"] for v in checker.population_for_slot(g, 1)] == ["Stale"], "the shared page while no own"
    write(g, "Save 1/Tribe Population/Village Population 1.txt", page.format(v="Ann", n="Fresh"))
    assert [v["name"] for v in checker.population_for_slot(g, 1)] == ["Fresh"]
    assert checker.population_for_slot(g, 2) is None
    write(g, "Village Statistics/Village Statistics v2 - Save 1.txt", "Village: Ann (Save 1)\nHighest Population: 5\n")
    assert checker.read_stats_text(g, 1)["Highest Population"] == "5"
    write(g, "Save 1/Village Statistics/Village Statistics v2 - Save 1.txt", "Village: Ann (Save 1)\nHighest Population: 9\n")
    assert checker.read_stats_text(g, 1)["Highest Population"] == "9"
    snap = "=== Virtual Villagers {g} -- {d} ===\nVillage: Ann (Save {s})\nVillager 1\n  Name: {n}\n  Head: 1\n  Body: 2\n\n"
    write(g, "Tribe History/Village History 1.txt",
          snap.format(g=game, d="2026-10-01 10:00:00", s=1, n="First") + snap.format(g=game, d="2026-10-02", s=2, n="X"))
    assert checker.history_last(g, 1)[0] == "2026-10-01 10:00:00"
    write(g, "Save 1/Tribe History/Village History 1.txt", snap.format(g=game, d="2026-10-03 09:00:00", s=1, n="Last"))
    stamp, villagers = checker.history_last(g, 1)
    assert (stamp, [v["name"] for v in villagers]) == ("2026-10-03 09:00:00", ["Last"]), "shared, then the slot's"
    assert len(checker.history_snapshots(g, "Village: Ann (Save 1)")) == 2
    assert checker.history_last(g, 2)[0] == "2026-10-02"


# ---- Rename Tribe, Move Old Files, Back Up / Restore ---------------------------------------------

@pytest.mark.parametrize("game", GAMES)
def test_the_rename_note_reaches_the_shared_and_the_slot_files(folder, game):
    g = game_folder(folder, game)
    shared = write(g, f"Births and Conceptions/{births_name(game)}", "Village: Ann (Save 1)\n" + birth(1, "A"))
    own = write(g, f"Save 1/Births and Conceptions/{births_name(game)}", "Village: Ann (Save 1)\n" + birth(2, "B"))
    other = write(g, f"Save 2/Births and Conceptions/{births_name(game)}", "Village: Bea (Save 2)\n" + birth(3, "C"))
    stats = write(g, "Save 1/Village Statistics/Village Statistics v2 - Save 1.txt",
                  "Virtual Villagers Statistics\n\nVillage: Ann (Save 1)\nHighest Population: 9\n")
    history = write(g, "Save 1/Tribe History/Village History 1.txt", "=== x -- y ===\nVillage: Ann (Save 1)\n\n")
    saves = next(s for s in vv_tribe_rename.GAMES if s.number == game)
    notes = {n.path for n in vv_tribe_rename.plan_log_notes(saves, g, 1, "Ann", "Zed", NOW)}
    assert {shared, own, stats, history} <= notes
    assert other not in notes


def test_move_old_files_never_touches_a_slot_folder(folder):
    g = game_folder(folder, 1)
    write(g, "Deaths/Virtual Villagers 1 Deaths Log 1.txt", "Village: Ann (Save 1)\n" + death(1, "Old") + death(9, "Gone"))
    # ...under both names: the two combined (the slot's own Deaths logs read alike in both views).
    write(g, "Deaths and Disappearances/Virtual Villagers 1 Deaths Log 1.txt", "Village: Ann (Save 1)\n" + death(1, "Old"))
    write(g, "Repairs/Virtual Villagers 1 Repairs Log 1.txt", "Village: Ann (Save 1)\nRepair 1\n  Date: a\n\n")
    write(g, "Save 1/Deaths and Disappearances/Virtual Villagers 1 Deaths Log 1.txt",
          "Village: Ann (Save 1)\n" + death(2, "New"))
    write(g, "Save 1/Repairs Made/Virtual Villagers 1 Repairs Log 1.txt", "Village: Ann (Save 1)\nRepair 2\n  Date: b\n\n")
    write(g, "Save 1/Deaths/Virtual Villagers 1 Deaths Log 1.txt", "Village: Ann (Save 1)\n" + death(3, "Odd"))
    slot = g / LOGS / "Save 1"
    before = tree(slot)
    stamps = {p: os.stat(p).st_mtime_ns for p in slot.rglob("*")}
    assert all(not item.old.lower().startswith(f"{LOGS}\\save".lower()) for item in move.plan(g))
    result = move.move_old_files(g, NoGame(), NOW)
    assert result.moved, "the older build's folders were moved"
    assert result.combined and not any("would change what the logs show" in line for line in result.left)
    assert tree(slot) == before and {p: os.stat(p).st_mtime_ns for p in slot.rglob("*")} == stamps
    assert (g / LOGS / "Deaths and Disappearances" / "Virtual Villagers 1 Deaths Log 1.txt").is_file()
    # Its own note: the shared Repairs Made, after the highest of every folder (Repair 2 in Save 1).
    note = (g / LOGS / "Repairs Made" / "Virtual Villagers 1 Repairs Log 1.txt").read_bytes().decode("latin-1")
    assert "Repair 3\r\n" in note


def test_a_slot_folder_belongs_to_its_slot_in_backups(folder):
    g = game_folder(folder, 1)
    write(g, "Save 2/Tribe History/Village History 1.txt", "=== x -- y ===\nVillage: Bea (Save 2)\n")
    write(g, "Save 4/Repairs Made/Virtual Villagers 1 Repairs Log 1.txt", "Village: (all villages)\nRepair 1\n")
    assert vv_save_backup.file_slot(Path(LOGS, "Save 2", "Tribe History", "Village History 1.txt"), g) == 2
    assert vv_save_backup.file_slot(Path(LOGS, "Save 4", "Repairs Made", "Virtual Villagers 1 Repairs Log 1.txt"), g) == 4
    assert Path(LOGS, "Save 2", "Tribe History", "Village History 1.txt") in vv_save_backup.files_to_back_up(g)


def test_a_slot_files_words_are_keyed_by_its_own_path(folder):
    g = game_folder(folder, 1)
    path = write(g, "Save 1/Tribe History/Village History 1.txt",
                 "=== x -- y ===\nVillage: Ann (Save 1)\nVillager 1\n  Likes: heights\n\n")
    key = f"{LOGS}\\Save 1\\Tribe History\\Village History 1.txt"
    assert checker.word_key(str(path.relative_to(g))) == key
    words = g / checker.LOG_WORDS.format(game=1)
    words.parent.mkdir(parents=True)
    words.write_bytes(f"0\t{key}\r\n".encode("utf-8"))
    assert checker.word_boundaries(g, 1) == {key.lower(): 0}
    assert checker.old_words(g, 1) == [], "a new slot file's words are all the game's own"
    tools.new_log_words(g, g / LOGS / "Save 1" / "Births and Conceptions" / births_name(1))
    assert checker.word_boundaries(g, 1)[f"{LOGS}\\Save 1\\Births and Conceptions\\{births_name(1)}".lower()] == 0
