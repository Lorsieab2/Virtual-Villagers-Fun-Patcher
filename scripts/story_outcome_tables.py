"""The Pick Island Event outcome tables: checked against the renders, emitted as C.

Used by scripts/build_story_cheat_upgrades_features.py.  The data is
scripts/story_island_outcomes.py (one entry per offered event that has
settings); this module checks every site against the executable the patcher
renders (in every population mode, with only the Story row and with the
whole catalog) and writes the C tables "VVFP Story Upgrades.dll" reads
(story_outcomes.inc has the run-time side).

Every SITE is a 5-byte `E8 rel32` call to the game's rand(bound); every SCOPE
is a 5-byte `E8 rel32` call in the event's own code.  Both must hold exactly
the stock bytes in every render, and no two of them -- nor any other site the
companion writes -- may overlap.
"""
from __future__ import annotations

import json
import re
import struct

import story_island_outcomes as data

KINDS = {"enum": 1, "amount": 2, "loop": 3, "victim": 4}
PHASES = {"select": 1, "build": 2, "apply": 3}
REGS = {"eax": 0, "ecx": 1, "edx": 2, "ebx": 3, "esi": 4, "edi": 5, "ebp": 6, "esp": 7}
ELEMS = {"ptr": 1, "index": 2}
STRENGTH = {None: 0, "linear": 1, "barrel": 2}
MAX_CONTROLS = 48
GONG_SLOT = 1000                  # story_outcomes.inc OC_GONG_SLOT
MAX_SCOPES = 96

# The OK handler of each game's island-event popup, where the companion opens
# and closes the event's apply (story_outcomes.inc): name -> (VA, length).
APPLY_SITES = {
    "vv3": {"VV3_OC_CHOICE_APPLY_BYTES": (0x419A29, 12), "VV3_OC_SIMPLE_APPLY_BYTES": (0x419A41, 5)},
    "vv4": {"VV4_OC_CHOICE_APPLY_BYTES": (0x417EC9, 16), "VV4_OC_SIMPLE_APPLY_BYTES": (0x417EE5, 9)},
    "vv5": {"VV5_OC_CHOICE_APPLY_BYTES": (0x418749, 16), "VV5_OC_SIMPLE_APPLY_BYTES": (0x418765, 9)},
}
APPLY_ROUTINES = {
    "VV3_OC_CHOICE_APPLY_BYTES": "the island-event popup's OK: a two-choice event's apply (outcomes)",
    "VV3_OC_SIMPLE_APPLY_BYTES": "the island-event popup's OK: a single-result event's apply (outcomes)",
    "VV4_OC_CHOICE_APPLY_BYTES": "the island-event popup's OK: a two-choice event's apply (outcomes)",
    "VV4_OC_SIMPLE_APPLY_BYTES": "the island-event popup's OK: a single-result event's apply (outcomes)",
    "VV5_OC_CHOICE_APPLY_BYTES": "the island-event popup's OK: a two-choice event's apply (outcomes)",
    "VV5_OC_SIMPLE_APPLY_BYTES": "the island-event popup's OK: a single-result event's apply (outcomes)",
}

C_TYPES = [
    "typedef struct { unsigned int va; const unsigned char *expect; } oc_site;",
    "typedef struct { unsigned int va; const unsigned char *expect; unsigned char kind; "
    "signed char choice_arg; signed char choice_bias; int choice_off; signed char strength_arg; } oc_scope;",
    "typedef struct { unsigned short site; int value; } oc_force;",
    "typedef struct { const char *label; const char *condition; unsigned short force_first; "
    "unsigned short force_count; unsigned char cond; } oc_option;",
    "typedef struct { const char *label; const char *text; const char *warn; signed char branch; "
    "unsigned char kind; unsigned char phase; signed char scope; signed char scope2; short site; "
    "unsigned short option_first; unsigned short option_count; int bound; int base; int step; "
    "int everyone; int nobody; signed char reg; unsigned char mem; int mem_disp; int disp; "
    "unsigned char elem; signed char elem_size; int elem_disp; unsigned char cond; "
    "const char *note; unsigned short xsite_first; unsigned short xsite_count; "
    "unsigned char occurrence; } oc_control;",
    "typedef struct { int slot; unsigned short control_first; unsigned short control_count; "
    "unsigned char strength; unsigned char unlock; unsigned char unlock_need; "
    "const char *dead_note; } oc_event;",
]


def _c(text):
    return "NULL" if text is None else json.dumps(text, ensure_ascii=True)


def plain(text):
    """The player's words of a table text: the code references the research
    keeps beside them (addresses, record offsets, rand calls) removed; None
    when nothing plain is left."""
    if not text:
        return None
    t = text
    before = None
    while before != t:
        before = t
        t = re.sub(r"\s*\([^()]*(?:0x|\[|\]|rand\(|==|!=)[^()]*\)", "", t)
    t = re.sub(r"^0x[0-9A-Fa-f]+(?:\([^)]*\))?:\s*", "", t)
    t = re.sub(r"\s+", " ", t).strip().rstrip(";,")
    if not t or re.search(r"0x[0-9A-Fa-f]|\+0x|\[[a-z]|\bEDI\b|\bESI\b|\bEAX\b", t):
        return None
    return t


def _call_target(read, va):
    raw = read(va, 5)
    if raw[0] != 0xE8:
        return None
    return (va + 5 + struct.unpack("<i", raw[1:])[0]) & 0xFFFFFFFF


def collect(game: str) -> dict:
    """The game's sites, scopes and events from the data module, validated
    for shape (not yet against an executable)."""
    controls = data.CONTROLS.get(game, {})
    sites: set[int] = set()
    scopes: dict[int, tuple[int, int, int, int, int]] = {}
    for va, choice_arg, bias, off, strength_arg in data.APPLY_SCOPES.get(game, []):
        scopes[va] = (1, choice_arg, bias, off, strength_arg)
    for va in data.GONG_USE_CALLS.get(game, []):
        scopes[va] = (2, -1, 0, 0, -1)
    gong = data.GONG_CONTROLS.get(game)
    if gong:
        controls = dict(controls)
        controls[GONG_SLOT] = gong
    for slot, cs in controls.items():
        if len(cs) > MAX_CONTROLS:
            raise SystemExit(f"{game} slot {slot}: {len(cs)} controls > {MAX_CONTROLS}")
        for c in cs:
            if c["kind"] == "enum":
                for o in c["options"]:
                    for va, value in o["force"]:
                        sites.add(va)
                        if value < 0:
                            raise SystemExit(f"{game} slot {slot} {c['id']}: negative value")
            else:
                sites.add(c["site"])
                sites.update(c.get("sites", []))
            for key in ("scope_call", "scope_call_alt"):
                if c.get(key) is not None and c[key] not in scopes:
                    scopes[c[key]] = (0, -1, 0, 0, -1)
    if len(scopes) > MAX_SCOPES:
        raise SystemExit(f"{game}: {len(scopes)} scopes > {MAX_SCOPES}")
    return {"sites": sorted(sites), "scopes": sorted(scopes.items()), "controls": controls}


def check(game: str, info: dict, rand_va: int, stock_read, render_reads, taken: list[tuple[int, int]]):
    """Every site and scope holds the stock bytes in every render; nothing
    overlaps.  Returns {va: stock bytes}."""
    found = {}
    spans = list(taken)
    for va in info["sites"]:
        if _call_target(stock_read, va) != rand_va:
            raise SystemExit(f"{game}: outcome site 0x{va:X} is not a call to rand 0x{rand_va:X}")
        found[va] = stock_read(va, 5)
        spans.append((va, va + 5))
    for va, _ in info["scopes"]:
        if _call_target(stock_read, va) is None:
            raise SystemExit(f"{game}: outcome scope 0x{va:X} is not an E8 call")
        found[va] = stock_read(va, 5)
        spans.append((va, va + 5))
    spans.sort()
    for (a0, a1), (b0, b1) in zip(spans, spans[1:]):
        if b0 < a1:
            raise SystemExit(f"{game}: companion sites overlap at 0x{a0:X} and 0x{b0:X}")
    for read in render_reads:
        for va, expect in found.items():
            if read(va, 5) != expect:
                raise SystemExit(f"{game}: outcome site 0x{va:X} differs in a render")
    return found


def emit(game: str, info: dict, found: dict, events_order: list[int]) -> list[str]:
    tag = game.upper()
    lines = []
    site_index = {va: i for i, va in enumerate(info["sites"])}
    scope_index = {va: i for i, (va, _) in enumerate(info["scopes"])}
    for va in info["sites"]:
        lines.append(f"static const unsigned char {tag}_OCS_{va:X}[5] = {{ "
                     + ", ".join(f"0x{b:02X}" for b in found[va]) + " };")
    for va, _ in info["scopes"]:
        lines.append(f"static const unsigned char {tag}_OCC_{va:X}[5] = {{ "
                     + ", ".join(f"0x{b:02X}" for b in found[va]) + " };")
    lines.append(f"static const oc_site {tag}_OC_SITES[] = {{")
    for va in info["sites"]:
        lines.append(f"    {{ 0x{va:X}u, {tag}_OCS_{va:X} }},")
    if not info["sites"]:
        lines.append("    { 0u, NULL },")
    lines.append("};")
    lines.append(f"#define {tag}_OC_SITE_COUNT {len(info['sites'])}")
    lines.append(f"static const oc_scope {tag}_OC_SCOPES[] = {{")
    for va, (kind, arg, bias, off, strength_arg) in info["scopes"]:
        lines.append(f"    {{ 0x{va:X}u, {tag}_OCC_{va:X}, {kind}, {arg}, {bias}, {off}, {strength_arg} }},")
    if not info["scopes"]:
        lines.append("    { 0u, NULL, 0, -1, 0, 0, -1 },")
    lines.append("};")
    lines.append(f"#define {tag}_OC_SCOPE_COUNT {len(info['scopes'])}")

    forces, options, controls, events = [], [], [], []
    strength = data.STRENGTH.get(game, {})
    unlock = data.UNLOCKED.get(game, {})
    dead = data.DEAD_NOTES.get(game, {})
    slots = [s for s in events_order
             if s in info["controls"] or s in strength or s in unlock or s in dead]
    if GONG_SLOT in info["controls"]:
        slots.append(GONG_SLOT)
    for slot in slots:
        cs = info["controls"].get(slot, [])
        first_control = len(controls)
        for c in cs:
            kind = KINDS[c["kind"]]
            scope = scope_index[c["scope_call"]] if c.get("scope_call") is not None else -1
            scope2 = scope_index[c["scope_call_alt"]] if c.get("scope_call_alt") is not None else -1
            opt_first = len(options)
            if c["kind"] == "enum":
                for o in c["options"]:
                    ff = len(forces)
                    for va, value in o["force"]:
                        forces.append(f"    {{ {site_index[va]}, {value} }},")
                    cond = data.CONDITION_IDS[o.get("cond")] if o.get("cond") else 0
                    options.append(f"    {{ {_c(plain(o['label']) or o['label'])}, "
                                   f"{_c(plain(o.get('condition')) or ('its condition' if o.get('cond') else None))}, {ff}, "
                                   f"{len(o['force'])}, {cond} }},")
            site = site_index[c["site"]] if c["kind"] != "enum" else -1
            xfirst = len(forces)
            extra = [va for va in c.get("sites", []) if va != c.get("site")]
            for va in extra:
                forces.append(f"    {{ {site_index[va]}, 0 }},")
            where = c.get("record") if c["kind"] == "loop" else (c.get("candidates") or {}).get("base")
            reg, mem, mem_disp, disp = -1, 0, 0, 0
            if where:
                if "reg" in where:
                    reg = REGS[where["reg"]]
                else:
                    reg, mem, mem_disp = REGS[where["mem"][0]], 1, where["mem"][1]
                disp = where["disp"]
            cand = c.get("candidates") or {}
            if c["kind"] == "amount":
                text = plain(c.get("unit")) or ""
            elif c["kind"] == "loop":
                text = plain(c.get("what"))
            elif c["kind"] == "enum":
                text = None
            else:
                text = plain(c.get("filter")) or data.PICKER_FILTERS.get((game, c["site"]),
                                                                          data.PICKER_FALLBACK)
            cond = data.CONDITION_IDS[c["cond"]] if c.get("cond") else 0
            controls.append(
                f"    {{ {_c(plain(c['label']) or c['label'])}, {_c(text)}, {_c(plain(c.get('warn_everyone')))}, "
                f"{-1 if c['branch'] is None else c['branch']}, {kind}, {PHASES[c['phase']]}, "
                f"{scope}, {scope2}, {site}, {opt_first}, {len(options) - opt_first}, "
                f"{c.get('bound', 0)}, {c.get('base', 0)}, {c.get('step', 0)}, "
                f"{c.get('everyone') if c.get('everyone') is not None else -1}, "
                f"{c.get('nobody') if c.get('nobody') is not None else -1}, "
                f"{reg}, {mem}, {mem_disp}, {disp}, {ELEMS.get(cand.get('elem'), 0)}, "
                f"{cand.get('size', 4)}, {cand.get('elem_disp', 0)}, {cond}, "
                f"{_c(plain(c.get('note') or c.get('condition')))}, {xfirst}, {len(extra)}, "
                f"{c.get('occurrence', 0)} }},")
        need = 0
        for off in unlock.get(slot, {}).get("needs", []):
            need |= {4: 1, 0xC: 2, 0x10: 4, "room": 8}[off]
        events.append(f"    {{ {slot}, {first_control}, {len(controls) - first_control}, "
                      f"{STRENGTH[strength.get(slot)]}, {1 if slot in unlock else 0}, {need}, "
                      f"{_c(dead.get(slot))} }},")
    for name, rows, empty in ((f"{tag}_OC_FORCES", forces, "    { 0, 0 },"),
                              (f"{tag}_OC_OPTIONS", options, "    { NULL, NULL, 0, 0, 0 },"),
                              (f"{tag}_OC_CONTROLS", controls, "    { NULL },"),
                              (f"{tag}_OC_EVENTS", events, "    { -1, 0, 0, 0, 0, 0, NULL },")):
        ctype = {"FORCES": "oc_force", "OPTIONS": "oc_option", "CONTROLS": "oc_control",
                 "EVENTS": "oc_event"}[name.rsplit("_", 1)[1]]
        lines.append(f"static const {ctype} {name}[] = {{")
        lines.extend(rows or [empty])
        lines.append("};")
    lines.append(f"#define {tag}_OC_EVENT_COUNT {len(events)}")
    return lines


def manifest_rows(game: str, info: dict, found: dict, dll_name: str) -> list[dict]:
    rows = []
    for va in info["sites"]:
        rows.append({"va": f"0x{va:X}", "stock_bytes": found[va].hex().upper(),
                     "routine": "a random roll of an island event (Pick Island Event outcomes)",
                     "installed_by": f"{dll_name}, VvfpStoryInstall"})
    for va, (kind, _, _, _, _) in info["scopes"]:
        rows.append({"va": f"0x{va:X}", "stock_bytes": found[va].hex().upper(),
                     "routine": {1: "an island event's resolve call (Pick Island Event outcomes)",
                                 2: "the Gong of Wonder's use (Pick Gong of Wonder Outcome)"}.get(
                         kind, "a call in an island event's own code (Pick Island Event outcomes)"),
                     "installed_by": f"{dll_name}, VvfpStoryInstall"})
    return rows
