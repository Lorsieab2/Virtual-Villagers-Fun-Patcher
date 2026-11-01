"""Write the translation inventory: data/translations/vv<N>_strings.json, data/translations/patcher_strings.json
and native/vvfp_translations/tr_sites.inc.

Inputs:
  * the stock executables (inputs/vv<N>-stock-copy/*.exe, gitignored), whose string tables are walked and
    whose code is scanned for the instructions that load each visible literal;
  * the research notes (--research DIR: vv<N>.json with each table row's context and the visible literals
    outside the tables, patcher_text.json with every string the patcher's own companions show).

The JSON files hold keys, addresses, notes and the stock English's SHA-256 prefix -- never a game's own words
(the English template is read from the player's own game, src/vv_translations.py).  patcher_strings.json
holds the patcher's own English, which is ours to ship.

    python scripts/build_translations_inventory.py --research <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_translations as vt  # noqa: E402
import vv_translation_format as fmt  # noqa: E402

DATA = ROOT / "data" / "translations"
SITES = ROOT / "native" / "vvfp_translations" / "tr_sites.inc"

# Each game's string table (verified by tests/test_translations_inventory.py against the stock executables).
TABLES = {
    1: {"table": {"va": 0x487208, "count": 629, "stride": 0x14, "id_offset": 0, "english_offset": 4}},
    2: {"table": {"va": 0x496300, "count": 0x36C, "stride": 12, "id_offset": 0, "english_offset": 4}},
    3: {"sm": {"va": 0x4AB990, "count": 0x4BA, "stride": 16, "id_offset": 0, "name_offset": 4, "english_offset": 8}},
    4: {"sm": {"va": 0x4C41F8, "count": 1338, "stride": 16, "id_offset": 0, "name_offset": 4, "english_offset": 8}},
    5: {"sm": {"va": 0x4D31F0, "count": 1409, "stride": 16, "id_offset": 0, "name_offset": 4, "english_offset": 8}},
}
EXE_NAMES = {n: f"{t}.exe" for n, t in vt.TITLES.items()}

EVENT_TOKENS = "*^&+="
PIECE_TOKENS = "|~@#$"
NAME_NOTE = "* = the villager's name (person; sex from the villager record); ^ & + = = he, He, him, his (the game picks them by sex)"


def sha8(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def stock_exe(number: int) -> Path:
    return ROOT / "inputs" / f"vv{number}-stock-copy" / EXE_NAMES[number]


def literal_list(research: dict) -> list[dict]:
    lits = research.get("literals", [])
    if isinstance(lits, dict):
        lits = lits.get("items", [])
    return [l for l in lits if isinstance(l, dict)]


def visible_literal(lit: dict) -> bool:
    if lit.get("kind") not in ("draw", "format"):
        return False
    text = lit.get("text") or ""
    words = re.sub(r"%[-+ #0]*\d*(?:\.\d+)?[a-zA-Z]", "", text)
    return bool(re.search(r"[A-Za-z]", words)) or text.strip() == "?"


def table_contexts(research: dict) -> dict[str, str]:
    out = {}
    for lit in literal_list(research):
        if lit.get("kind") != "table":
            continue
        ids = lit.get("ids") or ([lit["id"]] if "id" in lit else [])
        for ident in ids:
            try:
                ident = int(ident, 16) if isinstance(ident, str) else int(ident)
            except ValueError:
                continue
            out[f"table/{ident}"] = lit.get("context", "")
        if lit.get("key"):
            out[f"sm/{lit['key']}"] = lit.get("context", "")
    return out


def row_entry(number: int, stem: str, english: str, context: str) -> dict:
    entry: dict = {"stem": stem, "stock_hash": sha8(english)}
    notes: list[str] = []
    if context:
        entry["context"] = context
    convs = fmt.printf_conversions(english)
    for index, conv in enumerate(convs, start=1):
        kind = "number" if conv[-1] in "diouxX" else ("text" if conv[-1] == "s" else "value")
        if kind == "number":
            notes.append(f"%{index} = a number (number)")
        elif kind == "text":
            notes.append(f"%{index} = text, a villager's name where it is one (person)")
    if number in (1, 2) and stem.startswith("table/"):
        has_event = any(ch in english for ch in "*^&")
        has_piece = any(ch in english for ch in PIECE_TOKENS)
        if has_event or has_piece:
            entry["tokens"] = EVENT_TOKENS + PIECE_TOKENS
            entry["forbid_chars"] = EVENT_TOKENS + PIECE_TOKENS
            if "*" in english:
                entry["required_tokens"] = ["*"]
            if has_event and not has_piece:
                entry["subjects"] = {"*": "person"}
                notes.append(NAME_NOTE)
            else:
                entry["selects_allowed"] = False
                notes.append("game codes " + " ".join(ch for ch in EVENT_TOKENS + PIECE_TOKENS if ch in english)
                             + " must stay; selects cannot be used in this piece")
    if number >= 3 and "{name" in english:
        subjects = {}
        for var in ("name", "name2"):
            if "{" + var + "}" in english:
                subjects[var] = "person"
        entry["subjects"] = subjects
        notes.append("{name} = the villager's name (person); {name2} = a second villager (person); "
                     "{He/She}-style words: {male/female} for {name}, {male/2/female} for {name2}")
    if "{award}" in english:
        entry.setdefault("subjects", {})["award"] = "number"
    if context:
        notes.insert(0, context)
    entry["notes"] = "; ".join(notes)
    return entry


def scan_sites(image: vt.ExeImage, literal_vas: set[int]) -> dict[int, list[tuple[int, bytes, int]]]:
    """Each literal's loading instructions: push imm32 (68) and mov r32, imm32 (B8+r) in executable sections."""
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs  # noqa: PLC0415
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    out: dict[int, list] = {va: [] for va in literal_vas}
    data = image.data
    pe = int.from_bytes(data[0x3C:0x40], "little")
    count = int.from_bytes(data[pe + 6:pe + 8], "little")
    opt = int.from_bytes(data[pe + 20:pe + 22], "little")
    at = pe + 24 + opt
    for i in range(count):
        sec = at + 40 * i
        vsize, va, rsize, raw = (int.from_bytes(data[sec + o:sec + o + 4], "little") for o in (8, 12, 16, 20))
        chars = int.from_bytes(data[sec + 36:sec + 40], "little")
        if not chars & 0x20000000:
            continue
        code = data[raw:raw + min(vsize, rsize)]
        base = image.base + va
        offset = 0
        while offset < len(code):
            decoded = False
            for ins in md.disasm(code[offset:], base + offset):
                decoded = True
                b = bytes(ins.bytes)
                if len(b) == 5 and (b[0] == 0x68 or 0xB8 <= b[0] <= 0xBF):
                    imm = int.from_bytes(b[1:5], "little")
                    if imm in out:
                        out[imm].append((ins.address, b, 1))
                offset = ins.address - base + ins.size
            if not decoded:
                offset += 1
    return out


def build_game(number: int, research_dir: Path, sites_out: list[str]) -> dict:
    exe = stock_exe(number)
    image = vt.ExeImage(exe.read_bytes())
    research = json.loads((research_dir / f"vv{number}.json").read_text(encoding="utf-8"))
    contexts = table_contexts(research)
    inv: dict = {"game": number, "title": vt.TITLES[number],
                 "stock_exe_sha256": hashlib.sha256(image.data).hexdigest().upper()}
    inv.update({k: dict(v) for k, v in TABLES[number].items()})
    lits = []
    seen_va = set()
    for lit in literal_list(research):
        if not visible_literal(lit):
            continue
        va = int(lit["va"], 16)
        if va in seen_va:
            continue
        seen_va.add(va)
        lits.append({"va": f"0x{va:06x}", "context": lit.get("context") or str(lit.get("evidence", ""))[:80]})
    inv["literals"] = lits
    # The English by stem, from the stock executable alone (no sm.xml: stock hashes are the built-in English).
    tmp_inv_path = DATA / f"vv{number}_strings.json"
    DATA.mkdir(parents=True, exist_ok=True)
    tmp_inv_path.write_text(json.dumps(dict(inv, rows=[]), indent=1) + "\n", encoding="utf-8")
    english = vt.game_english(number, exe)
    rows = []
    for stem, text in english.items():
        if not text.strip():
            continue
        if stem.startswith("exe/"):
            ctx = next((l["context"] for l in lits if f"exe/{l['va']}" == stem), "")
        elif stem.startswith("sm/"):
            ctx = contexts.get(stem, "") or stem[3:]
        else:
            ctx = contexts.get(stem, "")
        rows.append(row_entry(number, stem, text, ctx))
    inv["rows"] = rows
    sites = scan_sites(image, {int(l["va"], 16) for l in lits})
    sites_out.append(f"static const tr_site TR_SITES_VV{number}[] = {{")
    kept = []
    for lit in lits:
        va = int(lit["va"], 16)
        found = sites.get(va, [])
        if not found:
            continue
        lit["sites"] = [f"0x{a:06x}" for a, _b, _o in found]
        kept.append(lit)
        for address, b, operand in found:
            stock = ", ".join(f"0x{x:02X}" for x in b)
            sites_out.append(f"    {{ 0x{va:06X}u, 0x{address:06X}u, {len(b)}, {operand}, {{ {stock} }} }},")
    inv["literals"] = kept
    inv["rows"] = [r for r in rows if not r["stem"].startswith("exe/") or any(
        r["stem"] == f"exe/{l['va']}" for l in kept)]
    sites_out.append("    { 0 },")
    sites_out.append("};")
    sites_out.append("")
    return inv


# ---- the patcher's own text ----------------------------------------------------------------------------

UNSHIPPED = ("vv1_full_mastery_candidate", "vv2_full_mastery_candidate", "vv4_full_mastery_candidate",
             "vv5_full_mastery_candidate", "vv4_full_heal_candidate", "shared/origins-upgrades.rc")
MECHANISM_NOTES = {
    "a": "drawn by the game's text routine",
    "b": "a patcher window",
    "d": "a patcher message shown by the game",
}


def normalise_stem(stem: str) -> str:
    stem = re.sub(r"\[(\d+)\]", r".\1", stem).replace("?", "x")
    source, _slash, ident = stem.partition("/")
    source = re.sub(r"[^a-z0-9_.\-]", "_", source.lower())
    ident = re.sub(r"[^A-Za-z0-9_.\-/]", "_", ident)
    return f"{source}/{ident}"


def build_patcher(research_dir: Path) -> dict:
    data = json.loads((research_dir / "patcher_text.json").read_text(encoding="utf-8"))
    out = []
    seen: dict[str, int] = {}
    for s in data["strings"]:
        if s.get("kind") in ("number", "exe_patch"):
            continue
        if any(part in s.get("file", "").replace("\\", "/") for part in UNSHIPPED):
            continue
        text = s.get("text") or ""
        if not re.search(r"[A-Za-z]{2,}", text):
            continue
        stem = normalise_stem(s.get("proposed_key", ""))
        if "/" not in stem:
            continue
        if stem in seen:
            seen[stem] += 1
            stem = f"{stem}.{seen[stem]}"
        else:
            seen[stem] = 1
        notes = [MECHANISM_NOTES.get(s.get("mechanism", ""), "")]
        for index, conv in enumerate(fmt.printf_conversions(text), start=1):
            if conv[-1] in "diouxX":
                notes.append(f"%{index} = a number (number)")
            elif conv[-1] == "s":
                notes.append(f"%{index} = text (person when it is a villager's name)")
        out.append({
            "stem": stem,
            "english": text,
            "games": sorted(s.get("games") or ["vv1", "vv2", "vv3", "vv4", "vv5"]),
            "mechanism": s.get("mechanism", ""),
            "context": s.get("companion", ""),
            "notes": "; ".join(n for n in notes if n),
        })
    return {"about": "The patcher's own in-game English (its companions' windows and messages), one row per "
                     "string; generated by scripts/build_translations_inventory.py. Keys: <source>/<id>, from the "
                     "source file and symbol, never a line number.",
            "strings": out}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--research", required=True, type=Path)
    args = parser.parse_args()
    sites_out = [
        "/* tr_sites.inc -- generated by scripts/build_translations_inventory.py; do not edit.",
        "",
        "   Per game, every code instruction whose 32-bit immediate is the address of a visible text literal",
        "   outside the string tables (\"exe/0x<literal_va>\" rows): push imm32 or mov r32, imm32, with its stock",
        "   bytes.  VVFP Translations.dll rewrites the immediate to the translation after checking those bytes",
        "   (all or none).  Each array ends with an all-zero entry. */",
        "",
    ]
    for number in range(1, 6):
        inv = build_game(number, args.research, sites_out)
        path = DATA / f"vv{number}_strings.json"
        path.write_text(json.dumps(inv, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"vv{number}: {len(inv['rows'])} rows, {len(inv['literals'])} literals")
    SITES.write_text("\n".join(sites_out) + "\n", encoding="utf-8", newline="\n")
    patcher = build_patcher(args.research)
    (DATA / "patcher_strings.json").write_text(json.dumps(patcher, indent=1, ensure_ascii=False) + "\n",
                                               encoding="utf-8", newline="\n")
    print(f"patcher: {len(patcher['strings'])} strings")


if __name__ == "__main__":
    main()
