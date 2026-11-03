"""Bring the template up to every patch's own text (the owner, 2026-11-02: "FOR ALL TRANSLATIONS AND ALL GAMES
PLEASE ADD THE ABILITY TO SUPPORT EVERY SINGLE PATCH!!!!").

1. Every player-visible string scripts/scan_patch_text.py finds in the companions' C sources that is neither in
   data/translations/patcher_strings.json nor a listed exclusion gets a row there: stem
   "vvfp.<part>/<file>.<function>.s<n>", its English, the games whose companion holds it, and a note.
2. Every text an exe patch writes (scan_patch_text.patch_texts) is listed in
   data/translations/exe_patch_strings.json with the row that covers it:
     * "table/<id>" or "exe/0x<va>" when the patch rewrites one of the game's own strings in place (the template
       reads that row's English from the player's patched game, so the patched text is what is translated);
     * otherwise a new "patch/0x<va>" row in patcher_strings.json (VVFP Translations.dll writes its translation
       over the patch's text in place when it fits, else matches it by content).
   The virtual address is read from the stock executable (inputs/vv<N>-stock-copy, gitignored), so this script
   runs where those are; tests/test_translations_patch_coverage.py checks the result without them.

    python scripts/build_patch_text_inventory.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import scan_patch_text as scan  # noqa: E402
import vv_translation_format as fmt  # noqa: E402
import vv_translations as vt  # noqa: E402

DATA = ROOT / "data" / "translations"
PATCHER = DATA / "patcher_strings.json"
EXE_PATCH = DATA / "exe_patch_strings.json"
ALL = ["vv1", "vv2", "vv3", "vv4", "vv5"]

PARTS = {
    "vvfp_story_upgrades": ("vvfp.story", "VVFP Story Upgrades.dll"),
    "vv1_origins_icons": ("vvfp.origins", "VVFP VV1 Origins Icons.dll"),
    "vv2_origins_icons": ("vvfp.origins", "VVFP VV2 Origins Icons.dll"),
    "vv4_origins_icons": ("vvfp.origins", "VVFP VV4 Origins Icons.dll"),
    "vv5_task9_origins": ("vvfp.origins", "VVFP Origins Icons.dll (VV5)"),
    "vvfp_cause_of_death": ("vvfp.cod", "VVFP Cause of Death.dll"),
    "vv1_parentage": ("vvfp.parentage", "VVFP VV1 Parentage.dll"),
    "vvfp_storytelling": ("vvfp.storytelling", "VVFP Storytelling.dll"),
    "vvfp_vv3_both_factions": ("vvfp.factions", "VVFP VV3 Both Factions.dll"),
}


def games_of(found: scan.Found) -> list[str]:
    parts = found.file.split("/")
    folder = parts[1]
    m = re.match(r"vv([1-5])_", folder)
    if m:
        number = int(m.group(1))
        return ["vv1", "vv2"] if number == 1 and folder == "vv1_origins_icons" else [f"vv{number}"]
    m = re.match(r"story_c([1-5])\.inc$", parts[-1])
    if m:
        return [f"vv{m.group(1)}"]
    m = re.match(r"(VV|vv)([1-5])_", found.context)
    if m:
        return [f"vv{m.group(2)}"]
    return list(ALL)


def part_of(found: scan.Found) -> tuple[str, str]:
    folder = found.file.split("/")[1]
    if folder in PARTS:
        return PARTS[folder]
    return f"vvfp.{re.sub(r'^vvfp_', '', folder)}", folder


def notes_for(text: str, mechanism: str) -> str:
    notes = [scan_mechanism(mechanism)]
    for index, conv in enumerate(fmt.printf_conversions(text), start=1):
        if conv[-1] in "diouxX":
            notes.append(f"%{index} = a number (number)")
        elif conv[-1] == "s":
            notes.append(f"%{index} = text (person when it is a villager's name)")
    return "; ".join(n for n in notes if n)


def scan_mechanism(mechanism: str) -> str:
    return {"a": "drawn by the game's text routine", "b": "a patcher window", "d": "a patcher message shown by the game",
            "e": "text an exe patch writes, shown by the game"}.get(mechanism, "")


def add_c_rows(strings: list[dict]) -> int:
    known = {s["english"] for s in strings}
    stems = {s["stem"] for s in strings}
    rules = scan.load_exclusions()
    counters: dict[str, int] = {}
    added = 0
    for found in scan.c_candidates():
        if found.text in known or scan.excluded_by(found, rules):
            continue
        source, context = part_of(found)
        base = f"{Path(found.file).stem}.{found.context or 'x'}"
        base = re.sub(r"[^A-Za-z0-9_.\-]", "_", base)
        n = counters.get(base, 0)
        while f"{source}/{base}.s{n}" in stems:
            n += 1
        counters[base] = n + 1
        stem = f"{source}/{base}.s{n}"
        stems.add(stem)
        known.add(found.text)
        strings.append({"stem": stem, "english": found.text, "games": games_of(found), "mechanism": "b",
                        "context": context, "notes": notes_for(found.text, "b")})
        added += 1
    return added


def _table_targets(number: int, image: vt.ExeImage) -> dict[int, str]:
    inv = vt.load_inventory(number)
    out: dict[int, str] = {}
    table = inv.get("table")
    if table:
        for i in range(table["count"]):
            entry = table["va"] + i * table["stride"]
            ident = image.dword(entry + table["id_offset"])
            ptr = image.dword(entry + table["english_offset"])
            if ptr:
                out.setdefault(ptr, f"table/{ident}")
    sm = inv.get("sm")
    if sm:
        for i in range(sm["count"]):
            entry = sm["va"] + i * sm["stride"]
            name = image.cstring(image.dword(entry + sm["name_offset"]))
            ptr = image.dword(entry + sm["english_offset"])
            if name and ptr:
                out.setdefault(ptr, "sm/" + name.decode("cp1252").rstrip())
    for lit in inv.get("literals", []):
        out.setdefault(int(lit["va"], 16), f"exe/{lit['va'].lower()}")
    return out


def _va(image: vt.ExeImage, offset: int) -> int | None:
    for sva, size, raw, rsize in image.sections:
        if raw <= offset < raw + max(rsize, 1):
            return image.base + sva + (offset - raw)
    return None


def add_patch_rows(strings: list[dict]) -> tuple[int, list[dict]]:
    stems = {s["stem"]: s for s in strings}
    rules = scan.load_exclusions()
    listed, added = [], 0
    images: dict[int, vt.ExeImage] = {}
    for item in sorted(scan.patch_texts(), key=lambda p: (p.game, p.offset, p.file)):
        if scan.patch_excluded_by(item, rules):
            continue
        if not item.game:
            raise SystemExit(f"{item.file} {item.where}: no game")
        if item.game not in images:
            exe = ROOT / "inputs" / f"vv{item.game}-stock-copy" / f"{vt.TITLES[item.game]}.exe"
            images[item.game] = vt.ExeImage(exe.read_bytes())
        image = images[item.game]
        va = _va(image, item.offset)
        if va is None:
            # A rebuilt executable's layout (the experimental Expanded-256 builds add sections): the address is
            # only known in that build, so the row is matched by content -- these are Windows message boxes
            # (the dialog hook) and game-drawn text (the Unicode Text draw hooks).
            stem = f"vvfp.exepatch/{Path(item.file).stem}.o{item.offset:x}"
            if stem not in stems:
                row = {"stem": stem, "english": item.text, "games": [f"vv{item.game}"], "mechanism": "b",
                       "context": f"{item.file} (an exe patch's text, file offset 0x{item.offset:X} of its rebuilt "
                                  "executable)", "notes": notes_for(item.text, "b")}
                strings.append(row)
                stems[stem] = row
                added += 1
            listed.append({"file": item.file, "where": item.where, "game": f"vv{item.game}",
                           "offset": f"0x{item.offset:x}", "va": "", "english": item.text, "covered_by": stem})
            continue
        covered = _table_targets(item.game, image).get(va)
        if covered is None:
            covered = f"patch/0x{va:x}"
            entry = stems.get(covered)
            if entry is None or entry["english"] != item.text:
                # Two patches can write different texts at one address: one row each, keyed apart by hash.
                stem = covered if entry is None else f"{covered}"
                same = [s for s in strings if s["stem"].startswith(covered) and s["english"] == item.text]
                if not same:
                    if entry is not None:
                        k = 2
                        while f"{covered}.v{k}" in stems:
                            k += 1
                        stem = f"{covered}.v{k}"
                    row = {"stem": stem, "english": item.text, "games": [f"vv{item.game}"], "mechanism": "e",
                           "context": f"{item.file} (an exe patch's text at 0x{va:X})",
                           "notes": notes_for(item.text, "e")}
                    strings.append(row)
                    stems[stem] = row
                    added += 1
                    covered = stem
                else:
                    covered = same[0]["stem"]
        listed.append({"file": item.file, "where": item.where, "game": f"vv{item.game}", "offset": f"0x{item.offset:x}",
                       "va": f"0x{va:x}", "english": item.text, "covered_by": covered})
    return added, listed


def main() -> None:
    data = json.loads(PATCHER.read_text(encoding="utf-8"))
    strings = data["strings"]
    c_added = add_c_rows(strings)
    p_added, listed = add_patch_rows(strings)
    keys = scan.key_call_stems()
    for row in strings:
        # How the row reaches the screen (scripts/scan_patch_text.py route_of): only a row a companion asks for by
        # its stem says so; the others are found by their address (patch/) or by the English they show.
        if scan.route_of(row["stem"], keys) == "key":
            row["route"] = "key"
        else:
            row.pop("route", None)
    data["about"] = ("The patcher's own in-game English (its companions' windows and messages, and the text its exe "
                     "patches write), one row per string; generated by scripts/build_translations_inventory.py and "
                     "scripts/build_patch_text_inventory.py. Keys: <source>/<id>, from the source file and symbol "
                     "(never a line number), or patch/0x<va> for an exe patch's own text.")
    PATCHER.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    EXE_PATCH.write_text(json.dumps({
        "about": "Every text an exe patch writes (scripts/scan_patch_text.py patch_texts) and the template row that "
                 "covers it: table/, sm/ or exe/ when the patch rewrites the game's own string in place (the "
                 "template reads it from the patched game), else its own patch/0x<va> row in patcher_strings.json. "
                 "Generated by scripts/build_patch_text_inventory.py.",
        "texts": listed}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{c_added} companion strings and {p_added} exe-patch strings added; {len(listed)} exe-patch texts listed")


if __name__ == "__main__":
    main()
