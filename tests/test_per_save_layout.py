"""One folder per save (the owner, 2026-10-17: "FOR ANYTHING IN THE SAVES FOLDER, PLEASE MAKE SEPARATE
FOLDERS TO PUT ALL THE LOGS AND DATA FOR EACH SAVE IN ALL 5 GAMES"): src/vv_save_layout.py's routing for
every game's real per-save data files and every log folder, and the Python readers and writers built on
it (Like and Dislike Words, copies made before repairs, the Backups slot attribution).

Every save folder is built under pytest's tmp_path; no game is run and nothing outside it is touched."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_log_tools as tools  # noqa: E402
import vv_save_backup  # noqa: E402
import vv_save_layout as layout  # noqa: E402

LOGS, DATA, SAVES = layout.LOGS, layout.DATA, layout.SAVES
GAMES = (1, 2, 3, 4, 5)
SLOTS = (1, 2, 3, 4, 5)
LOG_SUBS = ("Births and Conceptions", "Deaths and Disappearances", "Unaccounted Villagers", "Island Events",
            "Tribe Population", "Tribe History", "Village Statistics", "Repairs Made")


def data_files(game: int, slot: int) -> list[str]:
    """Every per-save data file the game keeps, as "<kind folder>\\<name>" under the Data folder (its
    newest name)."""
    g, s = game, slot
    out = [
        f"Village Masks\\Virtual Villagers {g} Village Masks - Save {s}.dat" if g <= 2
        else f"Village Masks\\Village Masks - Save {s}.dat",
        f"Unaccounted Villagers\\Virtual Villagers {g} Villagers at Last Save - Save {s}.dat",
        f"Custom Titles\\Custom Titles - Save {s}.dat",
        f"Arrivals\\Virtual Villagers {g} Arrivals Recorded - Save {s}.dat",
        f"Deaths\\Virtual Villagers {g} Graves Logged - Save {s}.dat",
        f"Paid Purchases\\Virtual Villagers {g} Paid Purchases - Save {s}.dat",
        f"Last Names\\Virtual Villagers {g} Last Names - Save {s}.dat",
        f"Last Names\\Virtual Villagers {g} Missing Last Names - Save {s}.dat",
        f"{layout.LOG_CHECKS}\\Virtual Villagers {g} Repair Approved - Save {s}.dat",
        f"{layout.LOG_CHECKS}\\Virtual Villagers {g} Log Decisions - Save {s}.json",
        f"Village Statistics\\Village Statistics - Save {s}.dat",
        f"Village Statistics\\Villagers Counted - Save {s}.dat",
        f"Stew Discoveries\\Stew Discoveries - Save {s}.dat",
        f"Village Elders\\Village Elders - Save {s}.dat",
        f"{layout.TREE_EDITS}\\Virtual Villagers {g} Family Tree Edits - Save {s}.json",
    ]
    if g <= 2:
        out.append(f"Graves\\Virtual Villagers {g} Graves - Save {s}.dat")
    if g >= 2:
        out.append(f"Births\\Virtual Villagers {g} Births Recorded - Save {s}.dat")
    if g >= 3:
        out.append(f"Custom Island Event Deaths\\Virtual Villagers {g} Custom Island Event Deaths - Save {s}.dat")
    if g == 5:
        out.append(f"Former Heathens\\Former Heathens - Save {s}.dat")
    if g == 1:
        out.append(f"{layout.PARENTS_VV1}\\Virtual Villagers 1 Parentage Records - Save {s}.dat")
        out.append(f"{layout.LOG_CHECKS}\\Virtual Villagers 1 Cross-Check - Save {s}.dat")
    return out


ALL_DATA = [(g, s, f) for g in GAMES for s in (1, 5) for f in data_files(g, s)]


def put(path: Path, data: bytes = b"x", when: float | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if when is not None:
        os.utime(path, (when, when))
    return path


def older(folder: Path, kind_name: str) -> Path:
    return folder / DATA / kind_name


def own(folder: Path, slot: int, kind_name: str) -> Path:
    return folder / layout.save_root(slot) / layout.SAVE_DATA / kind_name


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    path = tmp_path / "f"
    path.mkdir()
    return path


# ---- data files ------------------------------------------------------------------------------------

@pytest.mark.parametrize("game,slot,kind_name", ALL_DATA)
def test_data_file_fresh_goes_to_the_saves_own_folder(folder, game, slot, kind_name):
    assert layout.route(folder, f"{DATA}\\{kind_name}") == own(folder, slot, kind_name)
    assert layout.per_save_place(f"{DATA}\\{kind_name}")[0] == slot


@pytest.mark.parametrize("game,slot,kind_name", ALL_DATA)
def test_data_file_only_in_the_older_layout_stays_there(folder, game, slot, kind_name):
    put(older(folder, kind_name))
    assert layout.route(folder, f"{DATA}\\{kind_name}") == older(folder, kind_name)


@pytest.mark.parametrize("game,slot,kind_name", ALL_DATA)
def test_data_file_in_both_places_is_the_one_written_last(folder, game, slot, kind_name):
    old, new = older(folder, kind_name), own(folder, slot, kind_name)
    put(old, when=1_700_000_000)
    put(new, when=1_700_000_100)
    assert layout.route(folder, f"{DATA}\\{kind_name}") == new
    os.utime(old, (1_700_000_200, 1_700_000_200))
    assert layout.route(folder, f"{DATA}\\{kind_name}") == old
    os.utime(old, (1_700_000_100, 1_700_000_100))         # a tie: the save's own
    assert layout.route(folder, f"{DATA}\\{kind_name}") == new


@pytest.mark.parametrize("game,slot,kind_name", ALL_DATA)
def test_data_file_only_in_the_saves_own_folder(folder, game, slot, kind_name):
    put(own(folder, slot, kind_name))
    assert layout.route(folder, f"{DATA}\\{kind_name}") == own(folder, slot, kind_name)
    assert layout.both_places(folder, f"{DATA}\\{kind_name}") == [own(folder, slot, kind_name)]


def test_helper_files_follow_their_data_file(folder):
    kind_name = "Village Masks\\Village Masks - Save 2.dat"
    put(older(folder, kind_name))
    assert layout.route(folder, f"{DATA}\\{kind_name}.tmp") == older(folder, kind_name + ".tmp")


# ---- older builds' names ----------------------------------------------------------------------------

@pytest.mark.parametrize("older_rel,newest_rel", [
    (f"{DATA}\\Cross-Check\\Virtual Villagers 1 Cross-Check - Save 2.dat",
     f"{DATA}\\{layout.LOG_CHECKS}\\Virtual Villagers 1 Cross-Check - Save 2.dat"),
    (f"{DATA}\\Cross-Check\\Virtual Villagers 3 Repair Approved - Save 1.dat",
     f"{DATA}\\{layout.LOG_CHECKS}\\Virtual Villagers 3 Repair Approved - Save 1.dat"),
    (f"{DATA}\\Parentage Records\\Virtual Villagers 1 Parentage Records - Save 3.dat",
     f"{DATA}\\{layout.PARENTS_VV1}\\Virtual Villagers 1 Parentage Records - Save 3.dat"),
    (f"{DATA}\\Unaccounted Villagers\\Virtual Villagers 4 Village Roster - Save 1.dat",
     f"{DATA}\\Unaccounted Villagers\\Virtual Villagers 4 Villagers at Last Save - Save 1.dat"),
    (f"{DATA}\\Village Statistics\\Village Roster - Save 5.dat",
     f"{DATA}\\Village Statistics\\Villagers Counted - Save 5.dat"),
    (f"{DATA}\\Genealogy\\Virtual Villagers 2 Genealogy Edits - Save 4.json",
     f"{DATA}\\{layout.TREE_EDITS}\\Virtual Villagers 2 Family Tree Edits - Save 4.json"),
])
def test_an_older_builds_name_is_still_found(folder, older_rel, newest_rel):
    assert layout.per_save_place(older_rel) is None          # never in a save's own folder
    put(folder / older_rel)
    assert layout.route(folder, newest_rel) == folder / older_rel
    # A newer copy in the save's own folder (newest name) wins over it once written last.
    place = layout.per_save_place(newest_rel)
    assert place is not None
    new = put(folder / place[1], when=os.stat(folder / older_rel).st_mtime + 100)
    assert layout.route(folder, newest_rel) == new


# ---- logs ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("sub", LOG_SUBS)
@pytest.mark.parametrize("slot", SLOTS)
def test_log_folder_routing(folder, sub, slot):
    rel = f"{LOGS}\\Save {slot}\\{sub}"
    new = layout.own_slot_log_folder(folder, sub, slot)
    old = layout.older_slot_log_folder(folder, sub, slot)
    assert new == folder / SAVES / f"Save {slot}" / "Logs" / sub
    assert old == folder / LOGS / f"Save {slot}" / sub
    # fresh: the save's own folder
    assert layout.route(folder, rel) == new
    assert layout.slot_log_folder(folder, sub, slot) == new
    # an empty older folder: still the save's own
    old.mkdir(parents=True)
    assert layout.slot_log_folder(folder, sub, slot) == new
    # the older folder holds the slot's logs: written there, and a file in it too
    put(old / "Log 1.txt")
    assert layout.slot_log_folder(folder, sub, slot) == old
    assert layout.route(folder, f"{rel}\\Log 1.txt") == old / "Log 1.txt"
    # the save's own folder exists: written there from then on
    new.mkdir(parents=True)
    assert layout.slot_log_folder(folder, sub, slot) == new
    assert layout.route(folder, f"{rel}\\Log 2.txt") == new / "Log 2.txt"


@pytest.mark.parametrize("sub", LOG_SUBS)
def test_log_folders_read_order(folder, sub):
    got = layout.log_folders(folder, sub, 3)
    shared = [folder / layout.old_name(f"{LOGS}\\{sub}")] if layout.old_name(f"{LOGS}\\{sub}") else []
    assert got == shared + [folder / LOGS / sub, folder / LOGS / "Save 3" / sub,
                            folder / SAVES / "Save 3" / "Logs" / sub]
    every = layout.log_folders(folder, sub)
    assert every[-10:] == [p for s in SLOTS for p in (folder / LOGS / f"Save {s}" / sub,
                                                       folder / SAVES / f"Save {s}" / "Logs" / sub)]


def test_numbered_logs_read_both_places_older_first(folder):
    sub, stem = layout.DEATHS_LOGS, "Virtual Villagers 2 Deaths Log"
    a = put(folder / LOGS / sub / f"{stem} 1.txt")
    b = put(folder / LOGS / "Save 2" / sub / f"{stem} 1.txt")
    c = put(folder / SAVES / "Save 2" / "Logs" / sub / f"{stem} 1.txt")
    put(folder / SAVES / "Save 3" / "Logs" / sub / f"{stem} 1.txt")
    assert layout.numbered_logs(folder, sub, stem, 2) == [a, b, c]
    assert layout.is_slot_folder(b) == 2 and layout.is_slot_folder(c) == 2 and layout.is_slot_folder(a) is None
    # a new record goes to the slot's routed folder: the save's own, now it exists
    assert layout.append_target(folder, sub, stem, 2, "Death ") == c


def test_older_layout_maps_back(folder):
    log = folder / SAVES / "Save 4" / "Logs" / "Island Events" / "Virtual Villagers 4 Island Events Log 1.txt"
    dat = folder / SAVES / "Save 4" / "Data" / "Graves" / "Virtual Villagers 2 Graves - Save 4.dat"
    assert layout.older_layout(folder, log) == f"{LOGS}\\Save 4\\Island Events\\{log.name}"
    assert layout.older_layout(folder, dat) == f"{DATA}\\Graves\\{dat.name}"
    assert layout.older_layout(folder, folder / LOGS / "Save 4" / "Island Events" / log.name) is None


# ---- never routed ----------------------------------------------------------------------------------

@pytest.mark.parametrize("rel", [
    f"{DATA}\\{layout.LOG_WORDS}\\Virtual Villagers 1 Log Words.dat",      # the shared words file
    f"{DATA}\\Virtual Villagers 1 Graves - Save 1.dat",                    # a loose file in the Data folder
    f"{DATA}\\{layout.COPIES}\\{LOGS}\\Save 1\\Deaths and Disappearances\\x - Save 1.dat",
    f"{LOGS}\\Deaths and Disappearances",                                  # the shared logs, no slot
    f"{LOGS}\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions Log 1.txt",
    f"{layout.TREES}\\Reports",
])
def test_shared_items_are_never_routed(folder, rel):
    assert layout.per_save_place(rel) is None
    assert layout.route(folder, rel) == layout.find(folder, rel) == folder / rel


# ---- Like and Dislike Words ------------------------------------------------------------------------

def test_words_files_and_where_a_boundary_goes(folder):
    shared = folder / DATA / layout.LOG_WORDS / "Virtual Villagers 1 Log Words.dat"
    key_own = f"{SAVES}\\Save 2\\Logs\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions Log 1.txt"
    key_older = f"{LOGS}\\Save 2\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions Log 1.txt"
    assert layout.words_file_for(folder, 1, key_own) == layout.save_words_file(folder, 1, 2)
    assert layout.save_words_file(folder, 1, 2) == \
        folder / SAVES / "Save 2" / "Data" / layout.LOG_WORDS / "Virtual Villagers 1 Log Words.dat"
    assert layout.words_file_for(folder, 1, key_older) == shared
    assert layout.words_files(folder, 1) == []
    put(shared)
    put(layout.save_words_file(folder, 1, 4))
    put(layout.save_words_file(folder, 1, 2))
    assert layout.words_files(folder, 1) == [shared, layout.save_words_file(folder, 1, 2),
                                             layout.save_words_file(folder, 1, 4)]


def test_checker_reads_every_words_file_smallest_boundary(folder):
    checker = tools.load_checker()
    key = f"{SAVES}\\Save 1\\Logs\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions Log 1.txt"
    put(folder / DATA / layout.LOG_WORDS / "Virtual Villagers 1 Log Words.dat", f"50\t{key}\r\n".encode())
    put(layout.save_words_file(folder, 1, 1), f"90\t{key}\r\n20\t{key}\r\n".encode())
    assert checker.word_boundaries(folder, 1)[key.lower()] == 20


def test_new_log_words_goes_to_the_saves_own_words_file(folder):
    log = put(folder / SAVES / "Save 3" / "Logs" / "Births and Conceptions"
              / "Virtual Villagers 1 Births and Conceptions Log 1.txt", b"Birth 1\r\n")
    tools.new_log_words(folder, log)
    own_words = layout.save_words_file(folder, 1, 3)
    assert own_words.read_bytes() == f"0\t{log.relative_to(folder)}\r\n".encode()
    assert not (folder / DATA).exists()                   # the shared file is not made


def test_move_word_boundary_updates_the_saves_own_file(folder):
    log = put(folder / SAVES / "Save 1" / "Logs" / "Island Events" / "Virtual Villagers 1 Island Events Log 1.txt")
    key = str(log.relative_to(folder))
    own_words = put(layout.save_words_file(folder, 1, 1), f"40\t{key}\r\n".encode())
    tools.move_word_boundary(folder, log, 1, lambda offset: offset + 10)
    assert own_words.read_bytes().decode().splitlines()[-1] == f"50\t{key}"
    assert not (folder / DATA).exists()


# ---- copies made before a repair -------------------------------------------------------------------

def test_copy_before_repair_in_both_layouts(folder):
    older_log = folder / LOGS / "Save 1" / "Tribe History" / "Village History 1.txt"
    own_log = folder / SAVES / "Save 1" / "Logs" / "Tribe History" / "Village History 1.txt"
    own_dat = folder / SAVES / "Save 5" / "Data" / "Custom Titles" / "Custom Titles - Save 5.dat"
    for p in (older_log, own_log, own_dat):
        put(p)
    assert tools.copy_before_repair(folder, older_log, ".before-x") == \
        folder / DATA / layout.COPIES / LOGS / "Save 1" / "Tribe History" / "Village History 1.txt.before-x"
    assert tools.copy_before_repair(folder, own_log, ".before-x") == \
        folder / SAVES / "Save 1" / "Data" / layout.COPIES / "Logs" / "Tribe History" / "Village History 1.txt.before-x"
    assert tools.copy_before_repair(folder, own_dat, ".b") == \
        folder / SAVES / "Save 5" / "Data" / layout.COPIES / "Data" / "Custom Titles" / "Custom Titles - Save 5.dat.b"


def test_copies_made_before_a_move_are_still_found(folder):
    """A file moved into its save's own folder keeps its earlier copies at the older place
    (src/vv_move_to_save_folders.py): readers look in both mirrors; new copies go to the save's own."""
    import vv_reconcile
    own_log = put(folder / SAVES / "Save 2" / "Logs" / "Tribe History" / "Village History 1.txt")
    older_copy = put(folder / DATA / layout.COPIES / LOGS / "Save 2" / "Tribe History"
                     / "Village History 1.txt.before-a", when=1_700_000_000)
    own_copy = put(tools.copy_before_repair(folder, own_log, ".before-b"), when=1_700_000_100)
    assert tools.copy_places(folder, own_log, ".before-a") == [
        tools.copy_before_repair(folder, own_log, ".before-a"), older_copy]
    found = vv_reconcile._copies_of(own_log, folder / DATA / layout.COPIES, folder)
    assert found == [own_copy, older_copy]                 # newest first
    # A file still in the older layout: one place, as before.
    older_log = put(folder / LOGS / "Save 3" / "Tribe History" / "Village History 1.txt")
    assert tools.copy_places(folder, older_log, ".x") == [tools.copy_before_repair(folder, older_log, ".x")]


# ---- Backups: a slot's own folder is that slot's ---------------------------------------------------

@pytest.mark.parametrize("slot", SLOTS)
def test_backup_attributes_the_saves_own_folder(folder, slot):
    for rel in (Path(SAVES) / f"Save {slot}" / "Logs" / "Tribe History" / "Village History 1.txt",
                Path(SAVES) / f"Save {slot}" / "Data" / "Graves" / f"Virtual Villagers 1 Graves - Save {slot}.dat",
                Path(SAVES) / f"Save {slot}" / "Data" / layout.LOG_WORDS / "Virtual Villagers 1 Log Words.dat"):
        put(folder / rel)
        assert vv_save_backup.file_slot(rel, folder) == slot
