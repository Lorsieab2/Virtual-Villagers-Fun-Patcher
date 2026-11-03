"""Find every player-visible string the patcher's own patches add: the companion DLLs' C sources and the exe
patches' written bytes.  Used by tests/test_translations_patch_coverage.py (every string found must be in the
"Make a translation" template, data/translations/patcher_strings.json, or be a listed exclusion) and by
scripts/build_patch_text_inventory.py (which adds the missing ones).

HOW STRINGS ARE FOUND

* C sources.  Every shipped companion's folder under native/ (UNSHIPPED ones skipped: the candidates that never
  ship) and native/shared/, every .c .h .inc .rc file except test harnesses.  Comments are removed, then every
  string literal is read with C's own rules (escapes decoded; adjacent literals joined, as the compiler joins
  them; L"" wide literals too).  #include / #pragma / #error lines are skipped; #define bodies are read.  Each
  literal is attributed to the function or array it sits in (the last name before its top-level "{").
* A literal is a CANDIDATE when it reads as words: after removing printf conversions it holds a letter pair,
  and it either holds a space or is one word that reads as a word (Capitalised, lowercase or ALL CAPS with
  letters only) -- an identifier (CamelCase, with _ or digits) is code, never text.  File-like literals (a
  path separator, or ending in a file extension) are names, never text.
* Exe patches.  Every hex "after" block in the feature and build JSONs under data/ (candidates/ skipped), each
  NUL-terminated run that differs from its "before" bytes and reads as text (letters and a space, at least one
  3-letter word; an identifier-looking run is a function or DLL name).

EXCLUSIONS (data/translations/patch_text_exclusions.json): rules by file, function and text pattern, each with
its reason -- text written to log files and sidecars the patcher itself reads back, file and folder names, the
games' own words copied to compare with the game's text, debug builds, and the patcher-side export DLLs.
"""
from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
DATA = ROOT / "data"
EXCLUSIONS = DATA / "translations" / "patch_text_exclusions.json"

# The companions that never ship (the same list scripts/build_translations_inventory.py uses).
UNSHIPPED = ("vv1_full_mastery_candidate", "vv2_full_mastery_candidate", "vv3_full_mastery_candidate",
             "vv4_full_mastery_candidate", "vv5_full_mastery_candidate", "vv4_full_heal_candidate")
UNSHIPPED_FILES = ("shared/origins-upgrades.rc",)
SOURCE_SUFFIXES = (".c", ".h", ".inc", ".rc")
FILE_RE = re.compile(r"\.(dll|txt|tsv|dat|png|jpg|ogg|wav|xml|json|log|exe|ini|bak|tmp|csv|sav|bin)\b", re.I)
PRINTF_RE = re.compile(r"%[-+ #0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|h|ll|l|I64|I32|I)?[diouxXeEfgGcspn%]")


@dataclass(frozen=True)
class Found:
    file: str          # "native/vvfp_cause_of_death/vvfp_cause_of_death.c"
    line: int
    context: str       # the function or array it is in ("" at file scope)
    text: str
    wide: bool = False


# ---- C literals ----------------------------------------------------------------------------------------------

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", "'": "'", '"': '"', "?": "?", "a": "\a",
            "b": "\b", "f": "\f", "v": "\v"}


def _decode(body: str, wide: bool) -> str:
    """A literal's text as the compiler stores it: escapes decoded; a narrow literal's bytes read as
    Windows-1252 (the companions' own encoding)."""
    out = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        nxt = body[i + 1] if i + 1 < len(body) else ""
        if nxt == "x":
            m = re.match(r"[0-9A-Fa-f]+", body[i + 2:])
            value = int(m.group(), 16) if m else 0
            out.append(chr(value) if wide or value > 0xFF else bytes([value]).decode("cp1252", "replace"))
            i += 2 + (len(m.group()) if m else 0)
        elif nxt in "01234567" and nxt:
            m = re.match(r"[0-7]{1,3}", body[i + 1:])
            value = int(m.group(), 8)
            out.append(chr(value) if wide else bytes([value & 0xFF]).decode("cp1252", "replace"))
            i += 1 + len(m.group())
        else:
            out.append(_ESCAPES.get(nxt, nxt))
            i += 2
    return "".join(out)


def _strip_comments(src: str) -> str:
    """Comments become spaces (line numbers kept); strings and character constants are left alone."""
    out = []
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            end = src.find("*/", i + 2)
            end = n if end < 0 else end + 2
            out.append("".join("\n" if c == "\n" else " " for c in src[i:end]))
            i = end
        elif ch == "/" and i + 1 < n and src[i + 1] == "/":
            end = src.find("\n", i)
            end = n if end < 0 else end
            out.append(" " * (end - i))
            i = end
        elif ch in "\"'":
            j = i + 1
            while j < n and src[j] != ch and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            out.append(src[i:j + 1])
            i = j + 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


_TOKEN_RE = re.compile(r'(L?)"((?:[^"\\\n]|\\.)*)"|\'(?:[^\'\\\n]|\\.)*\'|[A-Za-z_]\w*|\S', re.S)


def c_literals(path: Path, relative: str) -> list[Found]:
    src = path.read_text(encoding="utf-8", errors="replace")
    src = _strip_comments(src.replace("\\\r\n", "").replace("\\\n", ""))
    # Skip the directive lines that carry file names or messages.
    lines = src.split("\n")
    for k, line in enumerate(lines):
        if re.match(r"\s*#\s*(include|pragma|error|line|import)\b", line):
            lines[k] = ""
    src = "\n".join(lines)
    found: list[Found] = []
    depth = 0
    parens = 0
    last_name = ""            # the last identifier at file scope
    call_name = ""            # the name before the first top-level "(" (a function)
    decl_name = ""            # the name before a top-level "[" or "=" (an array or a variable)
    assigned = False          # "=" came after the function's ")" (an initializer)
    rc_name = ""              # an .rc resource's id, before DIALOG / DIALOGEX / MENU / STRINGTABLE
    previous = ""
    context = ""
    is_rc = relative.endswith(".rc")
    pending: list[tuple[str, bool, int]] = []
    pending_end = 0

    def flush():
        nonlocal pending
        if pending:
            text = "".join(p[0] for p in pending)
            where = context
            if depth == 0 and not is_rc:
                define = re.match(r"\s*#\s*define\s+(\w+)", lines[pending[0][2] - 1])
                where = define.group(1) if define else (context or decl_name or call_name)
            found.append(Found(relative, pending[0][2], where, text, pending[0][1]))
        pending = []

    for m in _TOKEN_RE.finditer(src):
        token = m.group(0)
        if m.group(2) is not None or token in ('""', 'L""'):
            body = m.group(2) or ""
            between = src[pending_end:m.start()]
            if pending and between.strip():
                flush()
            line = src.count("\n", 0, m.start()) + 1
            pending.append((_decode(body, bool(m.group(1))), bool(m.group(1)), line))
            pending_end = m.end()
            continue
        if pending:
            flush()
        if is_rc:
            if token in ("DIALOG", "DIALOGEX", "MENU", "MENUEX", "STRINGTABLE") and depth == 0:
                rc_name = "strings" if token == "STRINGTABLE" else ("dlg" if token.startswith("DIALOG") else "menu") \
                    + re.sub(r"\W", "_", previous)
                context = rc_name
            elif token in ("BEGIN", "{"):
                depth += 1
            elif token in ("END", "}"):
                depth = max(0, depth - 1)
            previous = token
            continue
        if depth == 0 and token == "(":
            if parens == 0 and not call_name:
                call_name = last_name
                assigned = False
            parens += 1
        elif depth == 0 and token == ")":
            parens = max(0, parens - 1)
        elif depth == 0 and parens == 0 and token in ("[", "="):
            if not decl_name or token == "=":
                decl_name = decl_name or last_name
            if token == "=":
                assigned = True
        elif token == "{":
            if depth == 0:
                context = decl_name if (assigned or not call_name) and decl_name else (call_name or last_name)
            depth += 1
        elif token == "}":
            depth = max(0, depth - 1)
            if depth == 0:
                call_name = decl_name = ""
                assigned = False
        elif token == ";" and depth == 0:
            call_name = decl_name = ""
            assigned = False
            parens = 0
            context = ""
        elif re.match(r"[A-Za-z_]\w*$", token) and depth == 0 and parens == 0 and token not in (
                "static", "const", "char", "int", "unsigned", "void", "struct", "typedef", "__stdcall", "WINAPI",
                "__declspec", "dllexport", "BOOL", "DWORD", "wchar_t", "extern", "volatile", "enum", "union",
                "__cdecl", "__fastcall", "CALLBACK", "LRESULT", "INT_PTR", "float", "double", "long", "short",
                "define", "if", "ifdef", "ifndef", "else", "endif", "elif", "undef"):
            last_name = token
        previous = token
    flush()
    return found


def is_candidate(text: str) -> bool:
    words = PRINTF_RE.sub("", text)
    if not re.search(r"[A-Za-z]{2,}", words):
        return False
    if "\\" in text or "/" in text and not re.search(r"[A-Za-z]{2,} ", text) or FILE_RE.search(text):
        return False
    stripped = words.strip()
    if " " in stripped or "\n" in stripped:
        return True
    return bool(re.fullmatch(r"[A-Z]?[a-z]+(?:'[a-z]+)?[.!?:]?|[A-Z]{2,}[.!?:]?|[A-Z][a-z]+(?:-[A-Za-z][a-z]+)+",
                             stripped))


def source_files() -> list[tuple[Path, str]]:
    out = []
    for path in sorted(NATIVE.rglob("*")):
        if path.suffix.lower() not in SOURCE_SUFFIXES or not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        part = path.relative_to(NATIVE).parts[0]
        if part in UNSHIPPED or any(relative.endswith(u) for u in UNSHIPPED_FILES):
            continue
        name = path.name.lower()
        if "harness" in name or "_test." in name or name.startswith("test_"):
            continue
        out.append((path, relative))
    return out


def c_candidates() -> list[Found]:
    out = []
    for path, relative in source_files():
        out += [f for f in c_literals(path, relative) if is_candidate(f.text)]
    return out


# ---- exe patches -----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class PatchText:
    file: str          # "data/vv3_origins_feature.json"
    where: str         # the JSON path of the patch
    offset: int        # the text's file offset in the executable
    text: str
    game: int = 0      # 1-5: the game whose executable the patch writes


def _game_of(obj, game: int) -> int:
    for key in ("game_id", "game", "id"):
        value = obj.get(key)
        if isinstance(value, str):
            m = re.match(r"vv([1-5])(?:_|$)", value)
            if m:
                return int(m.group(1))
    return game


def _walk(obj, path, out, game=0):
    if isinstance(obj, dict):
        game = _game_of(obj, game)
        after = obj.get("after")
        if isinstance(after, str) and re.fullmatch(r"(?:[0-9A-Fa-f]{2})+", after) and "offset" in obj:
            out.append((path, obj, game))
        for key, value in obj.items():
            _walk(value, f"{path}/{key}", out, game)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            _walk(value, f"{path}[{i}]", out, game)


def is_patch_text(raw: bytes) -> bool:
    if not re.fullmatch(rb"[\x20-\x7e\x0a\x0d\x80-\xff]+", raw):
        return False
    if not re.search(rb"[A-Za-z]{3,}", raw) or sum(b >= 0x80 for b in raw) * 10 > len(raw):
        return False                                       # machine code reads as a few letters among bytes
    if re.fullmatch(rb"[A-Za-z_][A-Za-z0-9_]*", raw) or FILE_RE.search(raw.decode("cp1252", "replace")):
        return False                                       # an export / function name or a file name
    text = raw.decode("cp1252", "replace")
    return bool(re.search(r"[A-Za-z]{2,}[ ,.;:!?'\-][ A-Za-z]", text)) and sum(c.isalpha() for c in text) >= \
        0.6 * sum(not c.isspace() for c in text)


def patch_files() -> list[Path]:
    return sorted(p for p in DATA.rglob("*.json") if "candidates" not in p.relative_to(DATA).parts
                  and p.parent.name != "translations")


def patch_texts() -> list[PatchText]:
    out = []
    for path in patch_files():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        hits: list = []
        m = re.match(r"vv([1-5])_", path.name)
        _walk(data, "", hits, int(m.group(1)) if m else 0)
        for where, patch, game in hits:
            try:
                offset = int(str(patch["offset"]), 16)
            except ValueError:
                continue
            after = bytes.fromhex(patch["after"])
            before = bytes.fromhex(patch.get("before") or "") if re.fullmatch(
                r"(?:[0-9A-Fa-f]{2})*", patch.get("before") or "") else b""
            start = 0
            for k in range(len(after) + 1):
                if k < len(after) and after[k] != 0:
                    continue
                raw = after[start:k]
                if k < len(after) and raw and before[start:k + 1] != after[start:k + 1] and is_patch_text(raw):
                    out.append(PatchText(path.relative_to(ROOT).as_posix(), where, offset + start,
                                         raw.decode("cp1252"), game))
                start = k + 1
    # The same text written by several builds' copies of one patch at one offset is one string.
    unique = {}
    for item in out:
        unique.setdefault((item.file, item.offset, item.text), item)
    return list(unique.values())



# ---- how a row's text reaches the screen ------------------------------------------------------------------------
#
# Three routes (docs/reports/translation-keys/audit.md):
#   "key"     the companion asks "VVFP Translations.dll" for the row by its stem (native/shared/vvfp_translate.h:
#             vvfp_tr / vvfp_trf / ce_tr_printf), so the row's own translation is what is drawn;
#   "patch"   an exe patch's text at an address (patch/0x<va>): the DLL writes the translation over it in place;
#   "content" the text is drawn by the game's text routine or a Windows dialog and the DLL finds its row by the
#             English it sees (VvfpTranslateText / the dialog hook): one translation per distinct English.
KEY_CALL = re.compile(r'(?:vvfp_tr|ce_tr_printf\([^;]*?|ce_tr_done\([^;]*?|vvfp_trf)\(?\s*"((?:vvfp|patch)[\w.\-]*/[\w.\-%]+)",\s*'
                      r'"((?:[^"\\]|\\.)*)"', re.S)
# Stems a companion builds with wsprintfA (native source: the format that builds each one is in KEY_FAMILY_SOURCES).
KEY_FAMILIES = (
    re.compile(r"^vvfp\.cod/vvfp_cause_of_death\.CAUSE_WORDS\.\d+$"),
    re.compile(r"^vvfp\.cod/vvfp_cause_of_death\.EPITAPHS\.\d+$"),
    re.compile(r"^vvfp\.story/story_custom\.CE_WHY_WORDS\.\d+$"),
    re.compile(r"^vvfp\.story/story_c[1-5]\.C[1-5]_ADAPTER\.4[3-6]$"),
)
KEY_FAMILY_SOURCES = (
    ("native/vvfp_cause_of_death/cod_vv12.inc", 'vvfp.cod/vvfp_cause_of_death.CAUSE_WORDS.%d'),
    ("native/vvfp_cause_of_death/cod_vv12.inc", 'vvfp.cod/vvfp_cause_of_death.EPITAPHS.%d'),
    ("native/vvfp_story_upgrades/story_custom.inc", 'vvfp.story/story_custom.CE_WHY_WORDS.%d'),
    ("native/vvfp_story_upgrades/story_custom.inc", 'vvfp.story/story_c%d.C%d_ADAPTER.%d'),
)


KEY_CALL_STEM = re.compile(r'(?:vvfp_tr|vvfp_trf|ce_tr_printf\([^;]*?|ce_tr_done\([^;]*?)\(?\s*"((?:vvfp|patch)[\w.\-]*/[\w.\-%]+)"', re.S)


def key_call_stems() -> dict[str, str | None]:
    """Every stem a companion's source asks for by key (a literal stem): the English it passes when that is a
    literal, else None (a named constant)."""
    out: dict[str, str | None] = {}
    for path, _relative in source_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in KEY_CALL_STEM.finditer(text):
            out.setdefault(m.group(1), None)
        for m in KEY_CALL.finditer(text):
            out[m.group(1)] = _decode(m.group(2), False)
    return out


def is_key_family(stem: str) -> bool:
    return any(rx.match(stem) for rx in KEY_FAMILIES)


def route_of(stem: str, key_stems) -> str:
    """"key", "patch" or "content" for a patcher_strings.json row."""
    if stem in key_stems or is_key_family(stem):
        return "key"
    return "patch" if stem.startswith("patch/") else "content"

# ---- exclusions -------------------------------------------------------------------------------------------------

def load_exclusions() -> list[dict]:
    return json.loads(EXCLUSIONS.read_text(encoding="utf-8"))["rules"]


def excluded_by(found: Found, rules: list[dict]) -> dict | None:
    for rule in rules:
        if not any(fnmatch.fnmatch(found.file, g) for g in rule.get("files", ["*"])):
            continue
        functions = rule.get("functions")
        if functions and not any(fnmatch.fnmatch(found.context, f) for f in functions):
            continue
        pattern = rule.get("match")
        if pattern and not re.search(pattern, found.text, re.S):
            continue
        return rule
    return None


def patch_excluded_by(item: PatchText, rules: list[dict]) -> dict | None:
    for rule in rules:
        if not any(fnmatch.fnmatch(item.file, g) for g in rule.get("patch_files", [])):
            continue
        pattern = rule.get("match")
        if pattern and not re.search(pattern, item.text, re.S):
            continue
        return rule
    return None
