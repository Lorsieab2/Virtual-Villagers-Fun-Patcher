"""Write native/vvfp_island_events/stock_solidarity_table.inc from data/stock_island_event_solidarity.txt.

The table of tags Village Solidarity takes from the games' own island events (src/vv_stock_event_solidarity.py).
Afterwards rebuild "VVFP Island Events.dll" (scripts/build_vvfp_island_events.ps1) and re-pin it
(scripts/build_island_events_features.py, scripts/build_village_solidarity_feature.py --no-build).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_stock_event_solidarity as stock  # noqa: E402


def main() -> None:
    stock.TABLE_INC.write_text(stock.render_c(), encoding="utf-8", newline="\n")
    print("wrote", stock.TABLE_INC.relative_to(ROOT), len(stock.parse()), "rows")


if __name__ == "__main__":
    main()
