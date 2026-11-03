"""Write the Unicode 18.0 tables the patcher and the in-game Unicode companions use.

The owner, 2026-11-02: "please extend support to the entire Unicode 18.0 chart collection" -- "to all games".
Python's own `unicodedata` (16.0 in Python 3.14) and Windows' own segmentation are older than 18.0, so every
check whose answer depends on the Unicode version reads these tables instead:

  * data/unicode18/ucd18.json.gz -- compact range tables (general category, canonical combining class, bidi
    class, decompositions and composition exclusions, grapheme break, Indic_Conjunct_Break,
    Extended_Pictographic and the other emoji properties, East Asian width, scripts, blocks), the emoji
    sequences (emoji-sequences.txt, emoji-zwj-sequences.txt) and GraphemeBreakTest.txt's cases, all from
    Unicode 18.0.0; read by src/vv_unicode18.py;
  * data/unicode18/names18.txt.gz -- every character name (for the Text tab's character search);
  * native/vvfp_unicode_text/ucd18_tables.h -- the grapheme break, Indic_Conjunct_Break, Extended_Pictographic,
    shaped-script and line-breaking ranges the companions' text_utf8.h reads;
  * data/unicode18/SOURCES.json -- every source file's URL and SHA-256.
  * data/unicode18/LICENSE-Unicode.txt -- the Unicode License v3 the data is used under.

The raw UCD files are downloaded (never committed) into a new folder of their own under
research/unicode18/ (untrusted data: each run its own folder; this script only reads them as text).
--from <folder> rebuilds from an earlier download instead.

Usage:  python scripts/build_unicode18_tables.py [--from research/unicode18/ucd-YYYYMMDD-HHMMSS]
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "18.0.0"
BASE = f"https://www.unicode.org/Public/{VERSION}/"
LICENSE_URL = "https://www.unicode.org/license.txt"
FILES = (
    "ucd/UnicodeData.txt",
    "ucd/DerivedCoreProperties.txt",
    "ucd/DerivedNormalizationProps.txt",
    "ucd/CompositionExclusions.txt",
    "ucd/EastAsianWidth.txt",
    "ucd/Scripts.txt",
    "ucd/Blocks.txt",
    "ucd/PropList.txt",
    "ucd/extracted/DerivedBidiClass.txt",
    "ucd/auxiliary/GraphemeBreakProperty.txt",
    "ucd/auxiliary/GraphemeBreakTest.txt",
    "ucd/emoji/emoji-data.txt",
    "emoji/emoji-sequences.txt",
    "emoji/emoji-zwj-sequences.txt",
    "ucd/NormalizationTest.txt",
)
OUT = ROOT / "data" / "unicode18"
HEADER = ROOT / "native" / "vvfp_unicode_text" / "ucd18_tables.h"

# Scripts Windows must shape as a run (joined letters, reordered marks, right to left): the companions draw
# a run of one of these whole (text_utf8.h UT_RUN).  Every right-to-left script and every Brahmic and
# Southeast Asian script that reorders or stacks.
SHAPED_SCRIPTS = {
    "Arabic", "Hebrew", "Syriac", "Thaana", "Nko", "Samaritan", "Mandaic", "Devanagari", "Bengali", "Gurmukhi",
    "Gujarati", "Oriya", "Tamil", "Telugu", "Kannada", "Malayalam", "Sinhala", "Thai", "Lao", "Tibetan",
    "Myanmar", "Khmer", "Mongolian", "Tai_Le", "New_Tai_Lue", "Buginese", "Tai_Tham", "Balinese", "Sundanese",
    "Batak", "Lepcha", "Ol_Chiki", "Syloti_Nagri", "Phags_Pa", "Saurashtra", "Kayah_Li", "Rejang", "Javanese",
    "Cham", "Tai_Viet", "Meetei_Mayek", "Limbu", "Chakma", "Sharada", "Takri", "Khojki", "Khudawadi", "Grantha",
    "Tirhuta", "Siddham", "Modi", "Brahmi", "Kaithi", "Mahajani", "Newa", "Ahom", "Dogra", "Nandinagari",
    "Zanabazar_Square", "Soyombo", "Bhaiksuki", "Marchen", "Masaram_Gondi", "Gunjala_Gondi", "Makasar",
    "Kawi", "Dives_Akuru", "Hanifi_Rohingya", "Adlam", "Manichaean", "Psalter_Pahlavi", "Sogdian",
    "Old_Uyghur", "Chorasmian", "Elymaic", "Nabataean", "Palmyrene", "Hatran", "Imperial_Aramaic",
    "Inscriptional_Parthian", "Inscriptional_Pahlavi", "Avestan", "Phoenician", "Kharoshthi",
    "Old_South_Arabian", "Old_North_Arabian", "Lydian", "Meroitic_Cursive", "Meroitic_Hieroglyphs",
    "Mende_Kikakui", "Yezidi", "Garay", "Kirat_Rai", "Tulu_Tigalari", "Gurung_Khema", "Sunuwar",
    "Ol_Onal", "Tai_Yo", "Sidetic", "Tolong_Siki", "Beria_Erfe", "Old_Sogdian", "Pau_Cin_Hau", "Tangsa",
    "Toto", "Wancho", "Nag_Mundari", "Bassa_Vah", "Pahawh_Hmong", "Nyiakeng_Puachue_Hmong", "Miao",
    "Medefaidrin", "Duployan", "SignWriting", "Mro", "Khitan_Small_Script", "Egyptian_Hieroglyphs",
}
# A line may break between any two characters of these (Chinese, Japanese and their ideographic kin).
CJK_SCRIPTS = {"Han", "Hiragana", "Katakana", "Bopomofo", "Tangut", "Nushu", "Khitan_Small_Script", "Yi"}

GCB = ("Other", "CR", "LF", "Control", "Extend", "ZWJ", "Regional_Indicator", "Prepend", "SpacingMark", "L",
       "V", "T", "LV", "LVT")
INCB = ("None", "Linker", "Consonant", "Extend")


def fetch(folder: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=False)
    sources = {}
    for rel in FILES + ("license.txt",):
        url = LICENSE_URL if rel == "license.txt" else BASE + rel
        dest = folder / rel.replace("/", "_")
        print("fetch", url)
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
        dest.write_bytes(data)
        sources[rel] = {"url": url, "sha256": hashlib.sha256(data).hexdigest().upper(), "bytes": len(data)}
    (folder / "SOURCES.json").write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")
    return sources


def lines(folder: Path, rel: str):
    for raw in (folder / rel.replace("/", "_")).read_text(encoding="utf-8").splitlines():
        body = raw.split("#", 1)[0].strip()
        if body:
            yield [f.strip() for f in body.split(";")]


def cp_range(field: str) -> tuple[int, int]:
    if ".." in field:
        a, b = field.split("..")
        return int(a, 16), int(b, 16)
    return int(field, 16), int(field, 16)


def runs(values: dict[int, object], default) -> list:
    """A property over 0..10FFFF as [[start, value], ...]: each start where the value changes."""
    out = []
    last = object()
    for cp in range(0x110000):
        v = values.get(cp, default)
        if v != last:
            out.append([cp, v])
            last = v
    return out


def ranges_of(cps) -> list:
    out = []
    for cp in sorted(cps):
        if out and out[-1][1] == cp - 1:
            out[-1][1] = cp
        else:
            out.append([cp, cp])
    return out


def build(folder: Path) -> None:
    sources = json.loads((folder / "SOURCES.json").read_text(encoding="utf-8"))
    gc: dict[int, str] = {}
    ccc: dict[int, int] = {}
    decomp: dict[str, str] = {}
    names: list[str] = []
    name_ranges = []
    first = None
    for f in lines(folder, "ucd/UnicodeData.txt"):
        cp = int(f[0], 16)
        name = f[1]
        if name.endswith(", First>"):
            first = (cp, name)
            continue
        if name.endswith(", Last>"):
            label = first[1][1:-len(", First>")]
            for c in range(first[0], cp + 1):
                gc[c] = f[2]
                if int(f[3]):
                    ccc[c] = int(f[3])
            name_ranges.append([first[0], cp, label])
            continue
        gc[cp] = f[2]
        if int(f[3]):
            ccc[cp] = int(f[3])
        if f[5]:
            decomp[f"{cp:X}"] = f[5]
        if not name.startswith("<"):
            names.append(f"{cp:X};{name}")
    bidi = {}
    for f in lines(folder, "ucd/extracted/DerivedBidiClass.txt"):
        a, b = cp_range(f[0])
        for c in range(a, b + 1):
            bidi[c] = f[1]
    exclusions = set()
    for f in lines(folder, "ucd/DerivedNormalizationProps.txt"):
        if f[1] == "Full_Composition_Exclusion":
            a, b = cp_range(f[0])
            exclusions.update(range(a, b + 1))
    gcb = {}
    for f in lines(folder, "ucd/auxiliary/GraphemeBreakProperty.txt"):
        a, b = cp_range(f[0])
        for c in range(a, b + 1):
            gcb[c] = GCB.index(f[1])
    incb = {}
    default_ignorable = set()
    for f in lines(folder, "ucd/DerivedCoreProperties.txt"):
        if f[1] == "InCB":
            a, b = cp_range(f[0])
            for c in range(a, b + 1):
                incb[c] = INCB.index(f[2])
        elif f[1] == "Default_Ignorable_Code_Point":
            a, b = cp_range(f[0])
            default_ignorable.update(range(a, b + 1))
    emoji: dict[str, set] = {}
    for f in lines(folder, "ucd/emoji/emoji-data.txt"):
        a, b = cp_range(f[0])
        emoji.setdefault(f[1], set()).update(range(a, b + 1))
    eaw = {}
    for f in lines(folder, "ucd/EastAsianWidth.txt"):
        a, b = cp_range(f[0])
        for c in range(a, b + 1):
            eaw[c] = f[1]
    script = {}
    for f in lines(folder, "ucd/Scripts.txt"):
        a, b = cp_range(f[0])
        for c in range(a, b + 1):
            script[c] = f[1]
    blocks = []
    for f in lines(folder, "ucd/Blocks.txt"):
        a, b = cp_range(f[0])
        blocks.append([a, b, f[1]])
    white = set()
    for f in lines(folder, "ucd/PropList.txt"):
        if f[1] == "White_Space":
            a, b = cp_range(f[0])
            white.update(range(a, b + 1))
    sequences = []
    for rel in ("emoji/emoji-sequences.txt", "emoji/emoji-zwj-sequences.txt"):
        for f in lines(folder, rel):
            field, kind = f[0], f[1]
            if ".." in field:          # a range of single-code-point "sequences" (Basic_Emoji)
                a, b = cp_range(field)
                for c in range(a, b + 1):
                    sequences.append([kind, f"{c:X}"])
            else:
                sequences.append([kind, field.replace(" ", " ")])
    tests = []
    for raw in (folder / "ucd_auxiliary_GraphemeBreakTest.txt").read_text(encoding="utf-8").splitlines():
        body = raw.split("#", 1)[0].strip()
        if body:
            tests.append(body.replace("÷", "/").replace("×", "x"))
    scripts_index = sorted(set(script.values()) | {"Unknown"})
    table = {
        "version": VERSION,
        "gc": runs(gc, "Cn"),
        "ccc": runs(ccc, 0),
        "bidi": runs(bidi, "L"),
        "decomp": decomp,
        "composition_exclusions": ranges_of(exclusions),
        "gcb": runs(gcb, 0),
        "gcb_names": list(GCB),
        "incb": runs(incb, 0),
        "incb_names": list(INCB),
        "emoji": {k: ranges_of(v) for k, v in sorted(emoji.items())},
        "eaw": runs(eaw, "N"),
        "scripts": scripts_index,
        "script": runs({c: scripts_index.index(s) for c, s in script.items()}, scripts_index.index("Unknown")),
        "blocks": blocks,
        "white_space": ranges_of(white),
        "default_ignorable": ranges_of(default_ignorable),
        "name_ranges": name_ranges,
        "emoji_sequences": sequences,
        "grapheme_break_tests": tests,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(table, separators=(",", ":"), sort_keys=True).encode("utf-8")
    write_gz(OUT / "ucd18.json.gz", payload)
    write_gz(OUT / "names18.txt.gz", ("\n".join(names) + "\n").encode("utf-8"))
    (OUT / "LICENSE-Unicode.txt").write_bytes((folder / "license.txt").read_bytes().replace(b"\r\n", b"\n"))
    record = {
        "version": VERSION,
        "note": "The Unicode Character Database files these tables were generated from "
                "(scripts/build_unicode18_tables.py). The files themselves are not shipped.",
        "sources": sources,
    }
    (OUT / "SOURCES.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    write_header(gcb, incb, emoji["Extended_Pictographic"], script, scripts_index, eaw, gc)
    print("wrote", OUT / "ucd18.json.gz", (OUT / "ucd18.json.gz").stat().st_size, "bytes;",
          OUT / "names18.txt.gz", (OUT / "names18.txt.gz").stat().st_size, "bytes")


def write_gz(path: Path, payload: bytes) -> None:
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0, compresslevel=9) as g:
        g.write(payload)
    path.write_bytes(buf.getvalue())


def c_ranges(name: str, values: dict[int, int], comment: str) -> str:
    """A sorted {first, last, value} table of every non-zero run."""
    rows = []
    cur = None
    for cp in range(0x110000):
        v = values.get(cp, 0)
        if cur is not None and v == cur[2] and cp == cur[1] + 1:
            cur[1] = cp
            continue
        if cur is not None and cur[2]:
            rows.append(cur)
        cur = [cp, cp, v]
    if cur is not None and cur[2]:
        rows.append(cur)
    body = ",\n".join(f"    {{0x{a:X}u, 0x{b:X}u, {v}}}" for a, b, v in rows)
    return (f"/* {comment} */\n#define {name.upper()}_COUNT {len(rows)}\n"
            f"static const u18_range {name}[{name.upper()}_COUNT] = {{\n{body}\n}};\n")


def write_header(gcb, incb, extpict, script, scripts_index, eaw, gc) -> None:
    shaped = {c for c, s in script.items() if s in SHAPED_SCRIPTS}
    cjk = {c for c, s in script.items() if s in CJK_SCRIPTS}
    cjk |= {c for c, w in eaw.items() if w in ("W", "F") and gc.get(c, "Cn")[0] in "LS" and c not in extpict and script.get(c) != "Hangul"}
    unknown = sorted(SHAPED_SCRIPTS - set(scripts_index))
    if unknown:
        print("note: shaped scripts not in Scripts.txt 18.0:", ", ".join(unknown))
    parts = [
        "/* Generated by scripts/build_unicode18_tables.py from the Unicode " + VERSION + " Character Database --\n"
        "   do not edit.  The facts text_utf8.h needs to cut text into grapheme clusters by UAX #29 as of\n"
        "   Unicode " + VERSION + " (the same tables src/vv_unicode18.py reads from data/unicode18/ucd18.json.gz). */",
        "#ifndef VVFP_UCD18_TABLES_H\n#define VVFP_UCD18_TABLES_H\n",
        "typedef struct u18_range { unsigned int first, last; unsigned char value; } u18_range;\n",
        "enum { " + ", ".join(f"U18_GCB_{n.upper()} = {i}" for i, n in enumerate(GCB)) + " };",
        "enum { " + ", ".join(f"U18_INCB_{n.upper()} = {i}" for i, n in enumerate(INCB)) + " };\n",
        c_ranges("u18_gcb", gcb, "Grapheme_Cluster_Break (GraphemeBreakProperty.txt); absent = Other"),
        c_ranges("u18_incb", incb, "Indic_Conjunct_Break (DerivedCoreProperties.txt); absent = None"),
        c_ranges("u18_extpict", {c: 1 for c in extpict}, "Extended_Pictographic (emoji-data.txt)"),
        c_ranges("u18_shaped", {c: 1 for c in shaped}, "Scripts Windows shapes as a run (Scripts.txt)"),
        c_ranges("u18_cjk", {c: 1 for c in cjk},
                 "A line may break between two of these: Han, kana, Bopomofo, Yi, Tangut... and wide letters"),
        "\n/* The value of cp in a range table (0 when no range holds it). */",
        "static unsigned int u18_lookup(const u18_range *t, int n, unsigned int cp) {",
        "    int lo = 0, hi = n - 1;",
        "    while (lo <= hi) {",
        "        int mid = (lo + hi) >> 1;",
        "        if (cp < t[mid].first) hi = mid - 1;",
        "        else if (cp > t[mid].last) lo = mid + 1;",
        "        else return t[mid].value;",
        "    }",
        "    return 0;",
        "}\n",
        "#endif",
    ]
    HEADER.write_text("\n".join(parts) + "\n", encoding="utf-8", newline="\n")
    print("wrote", HEADER)


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["--from"]:
        folder = Path(args[1]).resolve()
    else:
        folder = ROOT / "research" / "unicode18" / time.strftime("ucd-%Y%m%d-%H%M%S")
        fetch(folder)
    build(folder)


if __name__ == "__main__":
    main()
