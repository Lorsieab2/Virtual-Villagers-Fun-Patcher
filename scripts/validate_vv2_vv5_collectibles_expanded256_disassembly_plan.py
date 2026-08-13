from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "data" / "vv2_vv5_collectibles_expanded256_disassembly_plan.json"
BUILDS = ROOT / "data" / "builds.json"
GAMES = ("vv2", "vv3", "vv4", "vv5")
QUERY_IDS = (
    "resolver_selected_world",
    "table_collectible_roster_detail",
    "predicate_eligibility_order",
    "predicate_index_capacity",
    "writer_native_mutation",
    "effects_notification_statistics",
    "transaction_confirmation_reacquire",
    "save_serializer_loader",
    "expanded_index_consumers",
    "catchup_reload_identity",
)
SHA = set("0123456789ABCDEF")


class PlanError(ValueError):
    pass


def _fail(message: str) -> None:
    raise PlanError(message)


def _sha(value: object, label: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or set(value) - SHA or value != value.upper():
        _fail(f"{label} must be uppercase SHA-256")


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def validate(document: dict[str, object], root: Path = ROOT) -> None:
    if document.get("schema_version") != "vvfp.vv2_vv5_collectibles_expanded256_disassembly_plan.v1":
        _fail("schema version")
    if document.get("status") != "STOP":
        _fail("status must remain STOP")
    scope = document.get("scope")
    if not isinstance(scope, dict) or scope.get("games") != list(GAMES) or scope.get("features") != ["collectibles", "expanded_256"]:
        _fail("scope")
    for field in ("native_output", "catalog_enabled", "publication_ready", "runtime_go", "player_go"):
        if scope.get(field) is not False:
            _fail(f"scope.{field} guard")
    publication = document.get("publication")
    if publication != {"enabled": False, "catalog_enabled": False, "catalog_hidden": True, "native_output": False, "runtime_go": False, "player_go": False, "publication_ready": False}:
        _fail("publication guard")
    ordered = document.get("ordered_queries")
    if not isinstance(ordered, list) or [q.get("id") for q in ordered] != list(QUERY_IDS) or [q.get("order") for q in ordered] != list(range(1, 11)):
        _fail("ordered query list")
    builds = json.loads((root / "data" / "builds.json").read_text(encoding="utf-8"))
    expected = {row["id"]: row for row in builds["games"] if row["id"] in GAMES}
    games = document.get("games")
    if not isinstance(games, dict) or set(games) != set(GAMES):
        _fail("game set")
    for game_id in GAMES:
        game = games[game_id]
        if not isinstance(game, dict):
            _fail(f"{game_id} record")
        stock = game.get("stock")
        if not isinstance(stock, dict) or stock.get("filename") != expected[game_id]["input_name"] or stock.get("size") != expected[game_id]["size"] or stock.get("sha256") != expected[game_id]["sha256"]:
            _fail(f"{game_id} stock binding")
        _sha(stock["sha256"], f"{game_id} stock")
        folder = game.get("folder_binding")
        if folder != {"status": "absent_stop", "inventory_sha256": None, "runtime_receipt_sha256": None}:
            _fail(f"{game_id} folder guard")
        queries = game.get("queries")
        if not isinstance(queries, dict) or queries:
            _fail(f"{game_id} native queries must remain empty")
        parent = game.get("expanded_parent")
        if not isinstance(parent, dict):
            _fail(f"{game_id} expanded parent")
        if parent.get("status") not in ("absent_stop", "static_parent_only"):
            _fail(f"{game_id} parent status")
        for ledger in game.get("known_ledgers", []):
            if not isinstance(ledger, dict) or not isinstance(ledger.get("path"), str) or type(ledger.get("count")) is not int:
                _fail(f"{game_id} ledger shape")
            _sha(ledger.get("ledger_sha256"), f"{game_id} ledger")
    if len(document.get("blockers", [])) < 1:
        _fail("blockers")
    return None


def main() -> int:
    document = json.loads(PLAN.read_text(encoding="utf-8"))
    validate(document)
    print("STOP: vv2-vv5 collectibles and Expanded-256 disassembly plan is structurally valid; no native rows are populated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
