"""Audit of how every patch text reaches the screen (docs/reports/translation-keys/audit.md).

For each game, every row of data/translations/patcher_strings.json is classified by ROUTE:

  key      the companion asks "VVFP Translations.dll" for the row by its stem (vvfp_tr / vvfp_trf / ce_tr_printf);
  patch    an exe patch's text at an address (patch/0x<va>), written over in place;
  content  found by the English it shows (the Unicode Text draw hooks, the dialog hook): one translation per
           English, so a row whose English an earlier row already has is NOT offered in the template.

    python scripts/audit_translation_keys.py                 # the counts, per game (no game needed)
    python scripts/audit_translation_keys.py --write         # also write docs/reports/translation-keys/inventory.tsv
    python scripts/audit_translation_keys.py --emulate       # also run the sentinel proof (needs the stock exes)
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import scan_patch_text as scan  # noqa: E402
import vv_translations as vt  # noqa: E402

REPORT = ROOT / "docs" / "reports" / "translation-keys"


def sha32(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def classify(game: int) -> list[dict]:
    """One dict per row of the game: stem, english, route, offered (bool) and why not."""
    keys = scan.key_call_stems()
    inventory = vt.load_inventory(game)
    stock_hashes = {r["stock_hash"] for r in inventory["rows"]}
    taken: dict[str, str] = {}
    out = []
    for entry in vt.load_patcher_strings():
        if f"vv{game}" not in entry.get("games", ()):
            continue
        route = scan.route_of(entry["stem"], keys)
        why = ""
        if route == "content":
            key = vt.content_key(entry["english"])
            if sha32(entry["english"]) in stock_hashes:
                why = "the English equals a string of the game itself"
            elif key in taken:
                why = f"the English repeats {taken[key]}"
            else:
                taken[key] = entry["stem"]
        out.append({"stem": entry["stem"], "english": entry["english"], "route": route, "offered": not why,
                    "why": why, "mechanism": entry.get("mechanism", "")})
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--emulate", action="store_true")
    args = parser.parse_args()
    lines = ["game\tstem\troute\toffered\twhy not\tEnglish"]
    print(f"{'game':5}{'rows':>6}{'key':>6}{'patch':>7}{'content':>9}{'left out':>10}{'(stock)':>9}{'(repeat)':>10}")
    for game in range(1, 6):
        rows = classify(game)
        routes = collections.Counter(r["route"] for r in rows)
        out = [r for r in rows if not r["offered"]]
        stock = sum("game itself" in r["why"] for r in out)
        print(f"vv{game:<3}{len(rows):>6}{routes['key']:>6}{routes['patch']:>7}{routes['content']:>9}"
              f"{len(out):>10}{stock:>9}{len(out) - stock:>10}")
        for r in rows:
            lines.append("\t".join((f"vv{game}", r["stem"], r["route"], "yes" if r["offered"] else "no", r["why"],
                                    r["english"].replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r")
                                    .replace("\n", "\\n"))))
    if args.write:
        REPORT.mkdir(parents=True, exist_ok=True)
        (REPORT / "inventory.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {(REPORT / 'inventory.tsv').relative_to(ROOT)}")
    if args.emulate:
        from translations_emulation import stock_exe   # noqa: PLC0415
        from translations_sentinels import prove       # noqa: PLC0415
        for game in range(1, 6):
            exe = stock_exe(game)
            english = set(vt.game_english(game, exe, exe.parent / "Assets" / "sm.xml").values())
            run = prove(game, exe.read_bytes(), english)
            counts = collections.Counter((r.route, r.status) for r in run.results)
            print(f"vv{game}: {dict(counts)}")
            for r in run.unproven():
                print(f"   unproven {r.route} {r.stem}: {r.why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
