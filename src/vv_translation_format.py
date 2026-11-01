"""The translation file format, version 1 (docs/translation-file-format.md): reading, writing and validating.

Game-neutral on purpose: the Virtual Families, Fish / Plant Tycoon and Virtual Villagers patchers share this
format, and the GitHub Action that checks a submitted translation runs this very module on the file alone
(scripts/validate_translation.py).  Nothing here reads a game; a program adds what it knows about its own
strings (which subjects are people or numbers, which tokens it protects) through `RowRules`.

A file is a tab-separated table, UTF-8 (written with a BOM; read with or without one, or as UTF-16 with a
BOM):

    Key<TAB>English<TAB>Translation<TAB>Notes

with `#` comment lines, `@` information rows (@format, @game, @language, @code, @translator) and one row per
string.  Keys are `<source>/<id>~<hash>`, the hash being the first 8 hex digits of the SHA-256 of the English.

Every error is a value, never an exception that reaches a caller who only wants a report: `parse` returns the
rows it could read and the issues it met, and `validate` lists, per row, why a row would fall back to English.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

FORMAT_VERSION = 1
HEADER = ("Key", "English", "Translation", "Notes")
INFO_KEYS = ("@format", "@game", "@language", "@code", "@translator")
MAX_FILE_BYTES = 4 * 1024 * 1024      # a translation is text; anything larger is refused unread

_SOURCE_RE = re.compile(r"^[a-z0-9_.\-]+$")
_ID_RE = re.compile(r"^[A-Za-z0-9_.\-/]+$")
_HASH_RE = re.compile(r"^[0-9a-f]{8}$")
# An email-like string anywhere (the owner, 2026-11-01: "Email addresses are never saved and are rejected
# from translation files").  Deliberately broad: something@something.tld, also with spaces around the @
# or written "at"/"dot"-free; a false positive only asks the translator to reword a line.
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+\s*@\s*[A-Za-z0-9\-]+(?:\s*\.\s*[A-Za-z0-9\-]+)+")
EMAIL_SENTENCE = "Email addresses are never saved and are rejected from translation files."


class FormatError(Exception):
    """The whole file cannot be read (encoding, size, header): everything stays English."""


# ---- encoding --------------------------------------------------------------------------------------------

def decode_bytes(data: bytes) -> str:
    """The file's text: UTF-8 (BOM optional) or UTF-16 with a BOM; anything else raises FormatError."""
    if len(data) > MAX_FILE_BYTES:
        raise FormatError(f"The file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.")
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
        codec = "utf-8"
    elif data.startswith(b"\xff\xfe"):
        data, codec = data[2:], "utf-16-le"
    elif data.startswith(b"\xfe\xff"):
        data, codec = data[2:], "utf-16-be"
    else:
        codec = "utf-8"
    try:
        text = data.decode(codec)
    except UnicodeDecodeError as error:
        raise FormatError(
            "The file is not UTF-8 text (byte %d). Save it as UTF-8 (or a spreadsheet's \"Unicode Text\")."
            % error.start) from None
    if "\x00" in text:
        raise FormatError("The file contains NUL characters; save it as UTF-8 text.")
    return text


# ---- escapes ---------------------------------------------------------------------------------------------

def escape(text: str) -> str:
    """A cell's spelling of `text`: backslash, tab and line breaks escaped."""
    return text.replace("\\", "\\\\").replace("\t", "\\t").replace("\r\n", "\n").replace("\n", "\\n")


def unescape(cell: str) -> str:
    """The text a cell stands for: \\n, \\t and \\\\ decoded; any other backslash kept as written."""
    out = []
    i = 0
    while i < len(cell):
        ch = cell[i]
        if ch == "\\" and i + 1 < len(cell) and cell[i + 1] in "nt\\":
            out.append({"n": "\n", "t": "\t", "\\": "\\"}[cell[i + 1]])
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _quote(cell: str) -> str:
    """A spreadsheet-safe cell: quoted when it begins with a double quote (which a spreadsheet would eat)."""
    if cell.startswith('"'):
        return '"' + cell.replace('"', '""') + '"'
    return cell


def _unquote(cell: str) -> str:
    if len(cell) >= 2 and cell.startswith('"') and cell.endswith('"'):
        inner = cell[1:-1]
        if '"' not in inner.replace('""', ""):
            return inner.replace('""', '"')
    return cell


# ---- keys ------------------------------------------------------------------------------------------------

def english_hash(english: str) -> str:
    return hashlib.sha256(english.encode("utf-8")).hexdigest()[:8]


def make_key(source: str, ident: str, english: str) -> str:
    if not _SOURCE_RE.match(source):
        raise ValueError(f"bad key source {source!r}")
    if not _ID_RE.match(ident):
        raise ValueError(f"bad key id {ident!r}")
    return f"{source}/{ident}~{english_hash(english)}"


def split_key(key: str) -> tuple[str, str, str] | None:
    """(source, id, hash), or None when the key is not well formed."""
    stem, sep, digest = key.rpartition("~")
    source, slash, ident = stem.partition("/")
    if not sep or not slash or not _SOURCE_RE.match(source) or not _ID_RE.match(ident) \
            or not _HASH_RE.match(digest):
        return None
    return source, ident, digest


def key_stem(key: str) -> str:
    """`<source>/<id>`: what stays the same when the English changes."""
    return key.rpartition("~")[0] if "~" in key else key


# ---- the file --------------------------------------------------------------------------------------------

@dataclass
class Row:
    key: str
    english: str
    translation: str = ""
    notes: str = ""
    line: int = 0


@dataclass
class Issue:
    severity: str          # "error" (the row falls back to English) or "warning" (the row is used)
    line: int              # 1-based line in the file, 0 when not from a file
    key: str
    message: str

    def __str__(self) -> str:
        where = f"line {self.line}" if self.line else (self.key or "file")
        return f"{where}: {self.message}"


@dataclass
class TranslationFile:
    info: dict[str, tuple[str, str]] = field(default_factory=dict)   # "@code" -> (english col, value)
    rows: list[Row] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)                # what parsing met

    def value(self, info_key: str) -> str:
        return self.info.get(info_key, ("", ""))[1].strip()

    def set_info(self, info_key: str, english: str, value: str) -> None:
        self.info[info_key] = (english, value)

    @property
    def language(self) -> str:
        return self.value("@language")

    @property
    def code(self) -> str:
        return self.value("@code")

    @property
    def game(self) -> str:
        return self.info.get("@game", ("", ""))[0].strip()

    @property
    def translator(self) -> str:
        return self.value("@translator")

    def by_key(self) -> dict[str, Row]:
        out: dict[str, Row] = {}
        for row in self.rows:
            out.setdefault(row.key, row)
        return out


def parse(text: str) -> TranslationFile:
    """Every readable row; malformed lines become issues (the rest of the file is still read)."""
    tf = TranslationFile()
    header_seen = False
    seen: dict[str, int] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        if raw.startswith("#"):
            tf.comments.append(raw)
            continue
        if not raw.strip():
            continue
        cells = [_unquote(cell) for cell in raw.split("\t")]
        if not header_seen:
            if [c.strip() for c in cells[:3]] == list(HEADER[:3]):
                header_seen = True
                continue
            raise FormatError(f"Line {number}: the header row \"Key<TAB>English<TAB>Translation<TAB>Notes\" "
                              "is missing (is the file tab-separated?).")
        key = cells[0].strip()
        if len(cells) < 2:
            tf.issues.append(Issue("error", number, key, "this row has no English column (tabs missing?)"))
            continue
        english = unescape(cells[1])
        translation = unescape(cells[2]) if len(cells) > 2 else ""
        notes = cells[3] if len(cells) > 3 else ""
        if key.startswith("@"):
            if key not in INFO_KEYS:
                tf.issues.append(Issue("warning", number, key, f"unknown information row {key}; ignored"))
                continue
            tf.info[key] = (english, translation)
            continue
        if split_key(key) is None:
            tf.issues.append(Issue("error", number, key, "the key is not well formed; never edit the Key column"))
            continue
        if key in seen:
            tf.issues.append(Issue("error", number, key, f"the same key is on line {seen[key]} too; this line "
                                                         "is ignored"))
            continue
        seen[key] = number
        tf.rows.append(Row(key, english, translation, notes, number))
    if not header_seen:
        raise FormatError("The file is empty or has no header row \"Key<TAB>English<TAB>Translation<TAB>Notes\".")
    fmt = tf.value("@format") or tf.info.get("@format", ("", ""))[0].strip()
    if fmt:
        major = fmt.split(".")[0]
        if not major.isdigit() or int(major) > FORMAT_VERSION:
            raise FormatError(f"The file is format version {fmt}; this program reads version {FORMAT_VERSION}. "
                              "Update the program.")
    return tf


def read_file(path: Path) -> TranslationFile:
    path = Path(path)
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise FormatError(f"The file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.")
    return parse(decode_bytes(path.read_bytes()))


def dumps(tf: TranslationFile) -> str:
    lines = list(tf.comments)
    lines.append("\t".join(HEADER))
    info = dict(tf.info)
    info.setdefault("@format", (str(FORMAT_VERSION), str(FORMAT_VERSION)))
    for info_key in INFO_KEYS:
        if info_key in info:
            english, value = info[info_key]
            lines.append("\t".join((info_key, _quote(escape(english)), _quote(escape(value)))))
    for row in tf.rows:
        cells = [row.key, _quote(escape(row.english)), _quote(escape(row.translation))]
        if row.notes:
            cells.append(_quote(row.notes.replace("\t", " ").replace("\r", " ").replace("\n", " ")))
        lines.append("\t".join(cells))
    return "\r\n".join(lines) + "\r\n"


def write_file(path: Path, tf: TranslationFile) -> None:
    """Atomically (a temp file in the same folder, then replace): UTF-8 with a BOM, CRLF."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = b"\xef\xbb\xbf" + dumps(tf).encode("utf-8")
    fd, temp = tempfile.mkstemp(prefix=".tmp-", suffix=".txt", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


# ---- placeholders ----------------------------------------------------------------------------------------

_PRINTF_RE = re.compile(r"%(?:%|[-+ #0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|h|ll|l|L|I64|I32|I)?[diouxXeEfgGcsp])")
_INT_CONVERSIONS = set("diouxX")
_VAR_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def printf_conversions(text: str) -> list[str]:
    """The printf conversions in order, `%%` left out."""
    return [m.group(0) for m in _PRINTF_RE.finditer(text) if m.group(0) != "%%"]


def _mask_subjects(text: str) -> str:
    """`{%1: ...}` select heads hidden, so their % is not read as a percent sign."""
    return re.sub(r"\{(\s*)%([1-9][0-9]?)(\s*):", r"{\1#\2\3:", text)


def bare_percents(text: str) -> list[int]:
    """Positions of '%' that start no conversion (an error: the program may use the text as a format)."""
    text = _mask_subjects(text)
    covered = set()
    for m in _PRINTF_RE.finditer(text):
        covered.update(range(m.start(), m.end()))
    return [i for i, ch in enumerate(text) if ch == "%" and i not in covered]


def _strip_escaped_braces(text: str) -> str:
    return text.replace("{{", "\x01").replace("}}", "\x02")


def named_variables(text: str) -> list[str]:
    """`{name}` variables outside selects, in order (with repeats)."""
    plain = _strip_escaped_braces(text)
    out = []
    for piece, is_select in _split_selects_loose(plain):
        if not is_select:
            out.extend(_VAR_RE.findall(piece))
        else:
            # variables inside branches count as used
            body = piece[1:-1]
            _subject, _colon, rest = body.partition(":")
            out.extend(_VAR_RE.findall(rest))
    return out


# ---- gender and plural selects -------------------------------------------------------------------------

PERSON_KEYS = ("m", "f", "o")
PLURAL_KEYS = ("zero", "one", "two", "few", "many", "other")
_SELECT_HEAD_RE = re.compile(r"^\{\s*(%[1-9][0-9]?|[A-Za-z_][A-Za-z0-9_]*|\*)\s*:")


class SelectError(ValueError):
    pass


@dataclass
class Select:
    subject: str                       # "%1", "name", "*"
    branches: dict[str, str]           # "m" / "f" / "o" / "one" / ... / "=3" -> text
    order: list[str]
    start: int
    end: int

    @property
    def kind(self) -> str:
        keys = set(self.branches)
        if keys <= set(PERSON_KEYS):
            return "person"
        return "number"


def _split_selects_loose(text: str) -> list[tuple[str, bool]]:
    """The text cut into plain pieces and `{subject: ...}` pieces (no validation)."""
    out: list[tuple[str, bool]] = []
    i = 0
    start = 0
    while i < len(text):
        if text[i] == "{" and _SELECT_HEAD_RE.match(text[i:]):
            depth = 0
            j = i
            while j < len(text):
                if text[j] == "\\" and j + 1 < len(text):
                    j += 2
                    continue
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j >= len(text):
                break
            if start < i:
                out.append((text[start:i], False))
            out.append((text[i:j + 1], True))
            i = j + 1
            start = i
            continue
        i += 1
    if start < len(text):
        out.append((text[start:], False))
    return out


def parse_selects(text: str) -> list[Select]:
    """Every select in `text`; SelectError for a malformed one."""
    plain = _strip_escaped_braces(text)
    selects: list[Select] = []
    pos = 0
    for piece, is_select in _split_selects_loose(plain):
        if is_select:
            selects.append(_parse_one(piece, pos))
        pos += len(piece)
    # An unbalanced select head with no closing brace.
    rest = plain
    for sel in selects:
        rest = rest.replace(plain[sel.start:sel.end], "", 1)
    if _SELECT_HEAD_RE.search(rest) or re.search(r"\{\s*(%[1-9][0-9]?|[A-Za-z_]\w*|\*)\s*:", rest):
        raise SelectError("a select is not closed with '}'")
    return selects


def _split_branches(body: str) -> list[str]:
    parts, cur, i = [], [], 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body) and body[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if ch == "|":
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    parts.append("".join(cur))
    return parts


def _parse_one(piece: str, start: int) -> Select:
    m = _SELECT_HEAD_RE.match(piece)
    assert m
    subject = m.group(1)
    body = piece[m.end():-1]
    if "{" in body.replace("\x01", "").replace("\x02", "") and _SELECT_HEAD_RE.search(body):
        raise SelectError(f"a select inside another select ({{{subject}: ...}}); put them side by side")
    branches: dict[str, str] = {}
    order: list[str] = []
    for part in _split_branches(body):
        if not part.strip():
            raise SelectError(f"an empty branch in {{{subject}: ...}}")
        stripped = part.lstrip()
        if stripped.startswith("="):
            mm = re.match(r"=(\d+)\s*=", stripped)
            if not mm:
                raise SelectError(f"a branch of {{{subject}: ...}} has no '=': {part.strip()!r}")
            key = "=" + mm.group(1)
            value = stripped[mm.end():]
        else:
            key, eq, value = stripped.partition("=")
            key = key.strip()
            if not eq:
                raise SelectError(f"a branch of {{{subject}: ...}} has no '=': {part.strip()!r}")
        if key not in PERSON_KEYS and key not in PLURAL_KEYS and not re.fullmatch(r"=\d+", key):
            raise SelectError(f"unknown branch key {key!r} in {{{subject}: ...}} (use m, f, o for people; "
                              "zero, one, two, few, many, other or =N for numbers)")
        if key in branches:
            raise SelectError(f"the branch {key!r} is written twice in {{{subject}: ...}}")
        value = value.strip()
        if printf_conversions(value) or bare_percents(value):
            raise SelectError(f"a printf placeholder or '%' inside {{{subject}: ...}}; put it outside the select")
        branches[key] = value
        order.append(key)
    keys = set(branches)
    if keys & set(PERSON_KEYS) and keys - set(PERSON_KEYS):
        raise SelectError(f"{{{subject}: ...}} mixes person keys (m, f, o) and number keys")
    return Select(subject, branches, order, start, start + len(piece))


def choose(select: Select, value, code: str = "en") -> str:
    """The branch for `value`: 'm'/'f'/'o' (or None) for a person, an int for a number."""
    b = select.branches
    if select.kind == "person":
        sex = value if value in ("m", "f") else "o"
        if sex in b:
            return b[sex]
        if "o" in b:
            return b["o"]
        return b[select.order[0]]
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 0
    exact = f"={n}"
    if exact in b:
        return b[exact]
    category = plural_category(code, n)
    if category in b:
        return b[category]
    if "other" in b:
        return b["other"]
    return b[select.order[0]]


def render(text: str, values: dict | None = None, code: str = "en") -> str:
    """`text` with every select replaced by its branch for `values` (subject -> sex or number); escaped
    braces back to single ones.  Unknown subjects take the person 'o' / number 'other' branch."""
    values = values or {}
    plain = _strip_escaped_braces(text)
    out = []
    for piece, is_select in _split_selects_loose(plain):
        if is_select:
            sel = _parse_one(piece, 0)
            out.append(choose(sel, values.get(sel.subject), code))
        else:
            out.append(piece)
    return "".join(out).replace("\x01", "{").replace("\x02", "}")


# ---- CLDR plural categories (cardinal, integers) ----------------------------------------------------------

def _rule_one_other(n):
    return "one" if n == 1 else "other"


def _rule_french(n):
    return "one" if n in (0, 1) else ("many" if n != 0 and n % 1000000 == 0 else "other")


def _rule_east_slavic(n):
    if n % 10 == 1 and n % 100 != 11:
        return "one"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "few"
    return "many"


def _rule_polish(n):
    if n == 1:
        return "one"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "few"
    return "many"


def _rule_czech(n):
    if n == 1:
        return "one"
    if 2 <= n <= 4:
        return "few"
    return "other"


def _rule_south_slavic(n):
    if n % 10 == 1 and n % 100 != 11:
        return "one"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "few"
    return "other"


def _rule_slovenian(n):
    if n % 100 == 1:
        return "one"
    if n % 100 == 2:
        return "two"
    if n % 100 in (3, 4):
        return "few"
    return "other"


def _rule_romanian(n):
    if n == 1:
        return "one"
    if n == 0 or 2 <= n % 100 <= 19:
        return "few"
    return "other"


def _rule_lithuanian(n):
    if n % 10 == 1 and not 11 <= n % 100 <= 19:
        return "one"
    if 2 <= n % 10 <= 9 and not 11 <= n % 100 <= 19:
        return "few"
    return "other"


def _rule_latvian(n):
    if n % 10 == 0 or 11 <= n % 100 <= 19:
        return "zero"
    if n % 10 == 1 and n % 100 != 11:
        return "one"
    return "other"


def _rule_arabic(n):
    if n == 0:
        return "zero"
    if n == 1:
        return "one"
    if n == 2:
        return "two"
    if 3 <= n % 100 <= 10:
        return "few"
    if 11 <= n % 100 <= 99:
        return "many"
    return "other"


def _rule_hebrew(n):
    if n == 1:
        return "one"
    if n == 2:
        return "two"
    return "other"


def _rule_irish(n):
    if n == 1:
        return "one"
    if n == 2:
        return "two"
    if 3 <= n <= 6:
        return "few"
    if 7 <= n <= 10:
        return "many"
    return "other"


def _rule_welsh(n):
    return {0: "zero", 1: "one", 2: "two", 3: "few", 6: "many"}.get(n, "other")


def _rule_icelandic(n):
    return "one" if n % 10 == 1 and n % 100 != 11 else "other"


def _rule_portuguese(n):
    return "one" if n in (0, 1) else ("many" if n != 0 and n % 1000000 == 0 else "other")


def _rule_other(n):
    return "other"


def _rule_spanish_italian(n):
    return "one" if n == 1 else ("many" if n != 0 and n % 1000000 == 0 else "other")


def _rule_macedonian(n):
    return "one" if n % 10 == 1 and n % 100 != 11 else "other"


def _rule_maltese(n):
    if n == 1:
        return "one"
    if n == 2:
        return "two"
    if n == 0 or 3 <= n % 100 <= 10:
        return "few"
    if 11 <= n % 100 <= 19:
        return "many"
    return "other"


# The same table is in native/vvfp_translations (tr_plural): keep them together (tests/test_translations*.py).
PLURAL_RULES = {
    "one_other": _rule_one_other, "french": _rule_french, "east_slavic": _rule_east_slavic,
    "polish": _rule_polish, "czech": _rule_czech, "south_slavic": _rule_south_slavic,
    "slovenian": _rule_slovenian, "romanian": _rule_romanian, "lithuanian": _rule_lithuanian,
    "latvian": _rule_latvian, "arabic": _rule_arabic, "hebrew": _rule_hebrew, "irish": _rule_irish,
    "welsh": _rule_welsh, "icelandic": _rule_icelandic, "portuguese": _rule_portuguese, "other": _rule_other,
    "spanish_italian": _rule_spanish_italian, "macedonian": _rule_macedonian, "maltese": _rule_maltese,
}
PLURAL_RULE_OF = {
    "en": "one_other", "de": "one_other", "nl": "one_other", "sv": "one_other", "da": "one_other",
    "nb": "one_other", "nn": "one_other", "no": "one_other", "fi": "one_other", "et": "one_other",
    "el": "one_other", "hu": "one_other", "tr": "one_other", "bg": "one_other", "af": "one_other",
    "eu": "one_other", "gl": "one_other", "ka": "one_other", "kk": "one_other", "az": "one_other",
    "sq": "one_other", "hy": "french", "ur": "one_other", "sw": "one_other", "ta": "one_other",
    "te": "one_other", "ml": "one_other", "mn": "one_other", "ne": "one_other", "uz": "one_other",
    "ca": "spanish_italian", "es": "spanish_italian", "it": "spanish_italian",
    "fr": "french", "pt": "portuguese", "pt-PT": "spanish_italian", "pt-BR": "portuguese",
    "ru": "east_slavic", "uk": "east_slavic", "be": "east_slavic",
    "pl": "polish", "cs": "czech", "sk": "czech",
    "hr": "south_slavic", "sr": "south_slavic", "bs": "south_slavic", "sl": "slovenian", "mk": "macedonian",
    "ro": "romanian", "mo": "romanian", "lt": "lithuanian", "lv": "latvian",
    "ar": "arabic", "he": "hebrew", "iw": "hebrew", "ga": "irish", "cy": "welsh", "is": "icelandic",
    "mt": "maltese",
    "ja": "other", "zh": "other", "zh-Hans": "other", "zh-Hant": "other", "ko": "other", "th": "other",
    "vi": "other", "id": "other", "ms": "other", "lo": "other", "my": "other", "km": "other",
    "yo": "other", "jv": "other",
    "hi": "french", "bn": "french", "fa": "french", "gu": "french", "kn": "french", "am": "french",
    "zu": "french",
}


def plural_rule_name(code: str) -> str:
    code = (code or "en").strip()
    if code in PLURAL_RULE_OF:
        return PLURAL_RULE_OF[code]
    base = code.split("-")[0].lower()
    return PLURAL_RULE_OF.get(base, "one_other")


def plural_category(code: str, n: int) -> str:
    return PLURAL_RULES[plural_rule_name(code)](abs(int(n)))


def plural_categories(code: str) -> list[str]:
    """The categories `code` uses, in CLDR order, each with an example number for previews."""
    rule = PLURAL_RULES[plural_rule_name(code)]
    seen: dict[str, int] = {}
    for n in list(range(0, 112)) + [1000000]:
        seen.setdefault(rule(n), n)
    return [c for c in PLURAL_KEYS if c in seen]


def plural_example(code: str, category: str) -> int:
    rule = PLURAL_RULES[plural_rule_name(code)]
    for n in list(range(0, 112)) + [1000000]:
        if rule(n) == category:
            return n
    return 0


# ---- validation ------------------------------------------------------------------------------------------

@dataclass
class RowRules:
    """What a program knows about one row beyond its English: which subjects are people or numbers, which
    tokens it protects (each must stay), and its box width in pixels (0: unknown)."""
    subjects: dict[str, str] = field(default_factory=dict)      # "%1" / "name" / "*" -> "person" | "number"
    tokens: tuple[str, ...] = ()
    required_tokens: tuple[str, ...] = ()
    forbid_chars: str = ""                                       # characters the game would misread here
    selects_allowed: bool = True
    byte_limit: int = 0                                          # the longest translation (UTF-8 bytes); 0: none


def find_emails(text: str) -> list[str]:
    return [m.group(0) for m in EMAIL_RE.finditer(text or "")]


def infer_subjects(english: str) -> dict[str, str]:
    """Subjects the English itself declares: %N by its conversion (%s person-or-text, integers numbers) and
    named variables (as person when named like one, else number)."""
    out: dict[str, str] = {}
    for index, conv in enumerate(printf_conversions(english), start=1):
        out[f"%{index}"] = "number" if conv[-1] in _INT_CONVERSIONS else ("person" if conv[-1] == "s" else "")
    for name in _VAR_RE.findall(_strip_escaped_braces(english)):
        lowered = name.lower()
        if lowered in ("count", "number", "n", "amount", "total", "award", "days", "years", "points"):
            out[name] = "number"
        else:
            out.setdefault(name, "person")
    for sel in _safe_selects(english):
        out.setdefault(sel.subject, sel.kind)
    return out


_NOTE_DECL_RE = re.compile(r"(%[1-9][0-9]?|\{[A-Za-z_]\w*\}|[*^&+=])\s*=\s*[^;|]*?\((person|number)")


def subjects_from_notes(notes: str) -> dict[str, str]:
    """Declarations the export writes in the Notes column, such as "%1 = villager name (person; ...)" or
    "* = the villager's name (person)"."""
    out = {}
    for subject, kind in _NOTE_DECL_RE.findall(notes or ""):
        out[subject.strip("{}")] = kind
    return out


def _outside_selects(text: str) -> str:
    """`text` without its selects (escaped braces kept as written)."""
    plain = _strip_escaped_braces(text)
    return "".join(piece for piece, is_select in _split_selects_loose(plain) if not is_select)


def _safe_selects(text: str) -> list[Select]:
    try:
        return parse_selects(text)
    except SelectError:
        return []


def check_row(english: str, translation: str, rules: RowRules | None = None, line: int = 0,
              key: str = "") -> list[Issue]:
    """Why `translation` would fall back to English (errors) or needs a look (warnings)."""
    issues: list[Issue] = []
    if not translation:
        return issues

    def err(message: str) -> None:
        issues.append(Issue("error", line, key, message))

    def warn(message: str) -> None:
        issues.append(Issue("warning", line, key, message))

    rules = rules or RowRules()
    for email in find_emails(translation):
        err(f"an email address ({email}) is not allowed. {EMAIL_SENTENCE}")
    try:
        selects = parse_selects(translation)
    except SelectError as error:
        err(f"malformed select: {error}")
        selects = []
    plain_tr = render(translation) if not any(i.severity == "error" for i in issues) else translation
    en_conv = printf_conversions(english)
    tr_conv = printf_conversions(translation)
    if en_conv != tr_conv:
        if sorted(en_conv) == sorted(tr_conv):
            err("the printf placeholders are in a different order than in the English (%s); the program "
                "cannot reorder them" % " ".join(en_conv))
        else:
            err("the printf placeholders must be exactly %s, in that order (found %s)"
                % (" ".join(en_conv) or "none", " ".join(tr_conv) or "none"))
    if not en_conv and "%" not in _mask_subjects(english) and "%" in _mask_subjects(translation):
        err("a '%' sign is not allowed in this line (the English has none, and the program may use the line "
            "as a format); write the word for percent instead")
    elif bare_percents(translation):
        err("a lone '%' sign; write %% for a percent sign in this line")
    en_vars = set(named_variables(english))
    tr_vars = set(named_variables(translation))
    for missing in sorted(en_vars - tr_vars):
        err(f"the variable {{{missing}}} is missing; keep it exactly as in the English")
    for extra in sorted(tr_vars - en_vars):
        err(f"the variable {{{extra}}} is not in the English")
    subjects = dict(infer_subjects(english))
    subjects.update(rules.subjects)
    for sel in selects:
        if not rules.selects_allowed:
            err("selects cannot be used in this line (the program shows it without its subjects)")
            break
        kind = subjects.get(sel.subject)
        if sel.subject.startswith("%"):
            index = int(sel.subject[1:])
            if index > len(en_conv):
                err(f"{{{sel.subject}: ...}} names placeholder {index}, but the English has {len(en_conv)}")
                continue
        elif sel.subject not in subjects:
            err(f"{{{sel.subject}: ...}}: {sel.subject} is not a person or number in this line")
            continue
        if kind and kind != sel.kind:
            err(f"{{{sel.subject}: ...}} uses {sel.kind} keys, but {sel.subject} is a {kind} here")
    # The same rules VVFP Translations.dll applies (tr_game_codes_ok): a token is kept when it is outside the
    # selects or in every branch of one; a forbidden character may appear nowhere, in no branch either.
    outside = _outside_selects(translation) if selects else translation
    branches = [value for sel in selects for value in sel.branches.values()]
    for token in rules.required_tokens:
        kept = token in outside or any(sel.branches and all(token in v for v in sel.branches.values())
                                        for sel in selects)
        if token in english and not kept:
            err(f"the game token {token!r} must stay in this line")
    for token in rules.tokens:
        if token in english and token not in translation and token not in rules.required_tokens:
            warn(f"the game token {token!r} from the English is not in the translation")
    for ch in rules.forbid_chars:
        if ch not in english and (ch in outside or any(ch in v for v in branches)):
            err(f"the character {ch!r} has a meaning to the game in this line; it cannot be added")
    if english[:1].isspace() != translation[:1].isspace() or english[-1:].isspace() != translation[-1:].isspace():
        warn("the spaces at the start or end differ from the English")
    if rules.byte_limit and len(plain_tr.encode("utf-8")) > rules.byte_limit:
        err(f"too long for the game: at most {rules.byte_limit} bytes here (a letter outside A-Z can take 2 to "
            "4 bytes); the line would stay English")
    if english.count("\n") and not translation.count("\n"):
        warn("the English has line breaks (\\n) and the translation has none")
    for ch in translation:
        if unicodedata.category(ch) in ("Cc",) and ch not in "\n\t":
            err(f"a control character U+{ord(ch):04X} is not allowed")
            break
    return issues


@dataclass
class Report:
    total: int = 0
    translated: int = 0
    used: int = 0                     # translated rows with no error (the ones the game will show)
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    stale: list[Row] = field(default_factory=list)       # English changed since the file was made
    unknown: list[Row] = field(default_factory=list)     # keys the program does not have
    missing: list[str] = field(default_factory=list)     # template keys absent from the file
    file_errors: list[str] = field(default_factory=list)  # the whole file is refused

    @property
    def coverage(self) -> float:
        return 100.0 * self.used / self.total if self.total else 0.0

    @property
    def ok(self) -> bool:
        return not self.file_errors

    def summary(self) -> str:
        if self.file_errors:
            return "Refused: " + " ".join(self.file_errors)
        return (f"{self.coverage:.0f}% translated ({self.used} of {self.total} lines). "
                f"{len(self.errors)} error(s) (those lines stay English), {len(self.warnings)} warning(s)"
                + (f", {len(self.stale)} line(s) whose English changed" if self.stale else "")
                + (f", {len(self.unknown)} line(s) this version no longer has" if self.unknown else "")
                + ".")


def check_info(tf: TranslationFile, game_title: str | None = None) -> list[str]:
    """Problems that refuse the whole file (the game stays English)."""
    problems = []
    for info_key, (english, value) in tf.info.items():
        for email in find_emails(english) + find_emails(value):
            problems.append(f"the {info_key} row contains an email address ({email}). {EMAIL_SENTENCE}")
    if not tf.language:
        problems.append("the @language row (the language's own name) is missing or empty")
    code = tf.code
    if not code or not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", code):
        problems.append("the @code row needs a language code such as fr, tr, ja or zh-Hans")
    if game_title is not None and tf.game and tf.game.casefold() != game_title.casefold():
        problems.append(f"this file is for {tf.game!r}, not {game_title!r}")
    credit = tf.translator
    if credit and len(credit) > 80:
        problems.append("the @translator credit is longer than 80 characters")
    return problems


def validate(tf: TranslationFile, template: dict[str, tuple[str, RowRules | None]] | None = None,
             game_title: str | None = None) -> Report:
    """The whole report.  `template`: the program's own rows (key -> (English, rules)); without it (the
    GitHub Action), the file's own English column is the reference and coverage counts the file's rows."""
    report = Report()
    report.file_errors = check_info(tf, game_title)
    for issue in tf.issues:
        (report.errors if issue.severity == "error" else report.warnings).append(issue)
    for comment_line, comment in enumerate(tf.comments):
        for email in find_emails(comment):
            report.file_errors.append(f"a comment contains an email address ({email}). {EMAIL_SENTENCE}")
    by_stem = {}
    if template is not None:
        by_stem = {key_stem(k): k for k in template}
    for row in tf.rows:
        for email in find_emails(row.english) + find_emails(row.notes):
            report.errors.append(Issue("error", row.line, row.key,
                                       f"an email address ({email}) is not allowed. {EMAIL_SENTENCE}"))
            report.file_errors.append(f"line {row.line} contains an email address. {EMAIL_SENTENCE}")
    for row in tf.rows:
        rules = None
        english = row.english
        if template is not None:
            if row.key in template:
                english, rules = template[row.key]
            elif key_stem(row.key) in by_stem:
                report.stale.append(row)
                if row.translation:
                    report.warnings.append(Issue("warning", row.line, row.key,
                                                 "the English of this line has changed; the old translation is "
                                                 "kept for review but not used"))
                continue
            else:
                report.unknown.append(row)
                report.warnings.append(Issue("warning", row.line, row.key,
                                             "this version of the program has no such line; ignored"))
                continue
        else:
            parts = split_key(row.key)
            if parts and parts[2] != english_hash(row.english):
                report.errors.append(Issue("error", row.line, row.key,
                                           "the English column was edited (it no longer matches the key); "
                                           "never edit the English or Key columns"))
                continue
        if not row.translation:
            continue
        report.translated += 1
        if rules is None:
            rules = RowRules(subjects=subjects_from_notes(row.notes))
        issues = check_row(english, row.translation, rules, row.line, row.key)
        errors = [i for i in issues if i.severity == "error"]
        report.errors.extend(errors)
        report.warnings.extend(i for i in issues if i.severity == "warning")
        if not errors:
            report.used += 1
    if template is not None:
        keys_in_file = {row.key for row in tf.rows}
        report.missing = [k for k in template if k not in keys_in_file]
        report.total = len(template)
    else:
        report.total = len(tf.rows)
    report.errors.sort(key=lambda i: i.line)
    report.warnings.sort(key=lambda i: i.line)
    return report


# ---- making and updating files ---------------------------------------------------------------------------

def template_file(rows: list[Row], game_title: str, language: str = "", code: str = "",
                  translator: str = "") -> TranslationFile:
    tf = TranslationFile()
    tf.comments = [
        f"# {game_title} - translation file (format {FORMAT_VERSION}). See docs/translation-file-format.md.",
        "# Fill the Translation column only. Keep every placeholder (%d, %s, {name}); never edit Key or English.",
        "# Save as UTF-8 text. " + EMAIL_SENTENCE,
    ]
    tf.set_info("@format", str(FORMAT_VERSION), str(FORMAT_VERSION))
    tf.set_info("@game", game_title, "")
    tf.set_info("@language", "English", language)
    tf.set_info("@code", "en", code)
    tf.set_info("@translator", "", translator)
    tf.rows = [Row(r.key, r.english, "", r.notes) for r in rows]
    return tf


def update(tf: TranslationFile, rows: list[Row]) -> tuple[TranslationFile, dict[str, str]]:
    """`tf` brought up to the program's current rows: each current row keeps its translation (same key),
    a row whose English changed starts untranslated with the old translation in its notes ("English changed;
    old translation: ..."), new rows start untranslated; rows the program no longer has are dropped.
    Returns the new file and {key: status} with status "kept" | "changed" | "new"."""
    old = tf.by_key()
    old_by_stem: dict[str, Row] = {}
    for row in tf.rows:
        old_by_stem.setdefault(key_stem(row.key), row)
    out = TranslationFile(info=dict(tf.info), comments=list(tf.comments))
    status: dict[str, str] = {}
    for row in rows:
        if row.key in old:
            prev = old[row.key]
            out.rows.append(Row(row.key, row.english, prev.translation, row.notes))
            status[row.key] = "kept"
        elif key_stem(row.key) in old_by_stem and old_by_stem[key_stem(row.key)].translation:
            prev = old_by_stem[key_stem(row.key)]
            note = f"English changed; old translation: {prev.translation}"
            out.rows.append(Row(row.key, row.english, "", (row.notes + " | " if row.notes else "") + note))
            status[row.key] = "changed"
        else:
            out.rows.append(Row(row.key, row.english, "", row.notes))
            status[row.key] = "new"
    return out, status


_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def file_name(game_title: str, language: str) -> str:
    """`<Game title> - <Language name>.txt`, safe for Windows."""
    name = f"{game_title} - {language}".strip()
    name = _UNSAFE_NAME.sub("_", name).rstrip(". ")
    return name + ".txt"


# ---- languages offered by "Make a translation" -----------------------------------------------------------

# (code, the language's own name, its English name).  Any other code can be typed.
LANGUAGES: tuple[tuple[str, str, str], ...] = (
    ("af", "Afrikaans", "Afrikaans"), ("ar", "العربية", "Arabic"), ("az", "Azərbaycanca", "Azerbaijani"),
    ("be", "Беларуская", "Belarusian"), ("bg", "Български", "Bulgarian"), ("bn", "বাংলা", "Bengali"),
    ("bs", "Bosanski", "Bosnian"), ("ca", "Català", "Catalan"), ("cs", "Čeština", "Czech"),
    ("cy", "Cymraeg", "Welsh"), ("da", "Dansk", "Danish"), ("de", "Deutsch", "German"),
    ("el", "Ελληνικά", "Greek"), ("eo", "Esperanto", "Esperanto"), ("es", "Español", "Spanish"),
    ("et", "Eesti", "Estonian"), ("eu", "Euskara", "Basque"), ("fa", "فارسی", "Persian"),
    ("fi", "Suomi", "Finnish"), ("fil", "Filipino", "Filipino"), ("fr", "Français", "French"),
    ("ga", "Gaeilge", "Irish"), ("gl", "Galego", "Galician"), ("he", "עברית", "Hebrew"),
    ("hi", "हिन्दी", "Hindi"), ("hr", "Hrvatski", "Croatian"), ("hu", "Magyar", "Hungarian"),
    ("hy", "Հայերեն", "Armenian"), ("id", "Bahasa Indonesia", "Indonesian"), ("is", "Íslenska", "Icelandic"),
    ("it", "Italiano", "Italian"), ("ja", "日本語", "Japanese"), ("ka", "ქართული", "Georgian"),
    ("kk", "Қазақ тілі", "Kazakh"), ("ko", "한국어", "Korean"), ("la", "Latina", "Latin"),
    ("lt", "Lietuvių", "Lithuanian"), ("lv", "Latviešu", "Latvian"), ("mk", "Македонски", "Macedonian"),
    ("ms", "Bahasa Melayu", "Malay"), ("mt", "Malti", "Maltese"), ("nb", "Norsk bokmål", "Norwegian Bokmål"),
    ("nl", "Nederlands", "Dutch"), ("pl", "Polski", "Polish"), ("pt-BR", "Português (Brasil)", "Portuguese (Brazil)"),
    ("pt-PT", "Português (Portugal)", "Portuguese (Portugal)"), ("ro", "Română", "Romanian"),
    ("ru", "Русский", "Russian"), ("sk", "Slovenčina", "Slovak"), ("sl", "Slovenščina", "Slovenian"),
    ("sq", "Shqip", "Albanian"), ("sr", "Српски", "Serbian"), ("sv", "Svenska", "Swedish"),
    ("sw", "Kiswahili", "Swahili"), ("ta", "தமிழ்", "Tamil"), ("th", "ไทย", "Thai"),
    ("tl", "Tagalog", "Tagalog"), ("tr", "Türkçe", "Turkish"), ("uk", "Українська", "Ukrainian"),
    ("ur", "اردو", "Urdu"), ("vi", "Tiếng Việt", "Vietnamese"), ("zh-Hans", "简体中文", "Chinese (Simplified)"),
    ("zh-Hant", "繁體中文", "Chinese (Traditional)"),
    ("akk", "𒀝𒅗𒁺𒌑", "Akkadian (cuneiform)"), ("sux", "𒅴𒂠", "Sumerian (cuneiform)"),
)
