"""How the patcher reads and writes the games' own text bytes: names, tribe names, logs, saves.

v1.35.89 (UTF-8 in game): a well-formed UTF-8 sequence is read as its character, every other byte as
Windows-1252 as below -- the rule native/vvfp_unicode_text uses in the game.  Writing keeps each
Windows-1252 character as its one byte and writes every other character as UTF-8 (encode_game_text), so
every name the base game, an older patcher or PR #670 wrote reads and writes back byte for byte.

The games keep every character in one byte, and with "Render Unicode with In-Game Fonts" they draw and
accept every printable Windows-1252 character -- 0x80-0x9F included (the euro, curly quotes, dashes,
S and Z with caron, OE).  The patcher used to read those bytes as Latin-1, which shows 0x80-0x9F as
invisible control characters.  GAME_TEXT is Windows-1252 for reading, so every patcher window, log
reader, family tree and Picture Studio shows what the game shows; it keeps every byte, so nothing the
patcher copies or rewrites changes:

  * decoding: Windows-1252, and the five bytes Windows-1252 leaves undefined (0x81, 0x8D, 0x8F, 0x90,
    0x9D) as the Latin-1 characters of the same number -- every byte decodes, and back to itself;
  * encoding: the inverse, and also the Latin-1 characters U+0080-U+009F (which older patcher files and
    windows may hold) as their own bytes -- so text the patcher read before this change still encodes to
    the very bytes it came from.

The companion's C (native/vvfp_unicode_text/unicode_text_tables.h, VG_CP1252) uses the same table.

Usage:  data.decode(GAME_TEXT), text.encode(GAME_TEXT), path.read_text(encoding=GAME_TEXT).  Importing
this module registers the codec.
"""
from __future__ import annotations

import codecs

GAME_TEXT = "vv-game-text"


def _decoding_table() -> str:
    out = []
    for b in range(256):
        try:
            out.append(bytes([b]).decode("cp1252"))
        except UnicodeDecodeError:
            out.append(chr(b))
    return "".join(out)


DECODING_TABLE = _decoding_table()
ENCODING_MAP: dict[int, int] = {b: b for b in range(256)}          # Latin-1, as older text holds it
ENCODING_MAP.update({ord(ch): b for b, ch in enumerate(DECODING_TABLE)})


def _utf8_length(data, i: int) -> int:
    """The length of the well-formed UTF-8 sequence starting at data[i] (Unicode Table 3-7), or 0 when
    there is none -- a lone byte, a cut-off sequence, an overlong form, a surrogate, or beyond U+10FFFF."""
    b = data[i]
    n = len(data)
    if 0xC2 <= b <= 0xDF:
        return 2 if i + 1 < n and 0x80 <= data[i + 1] <= 0xBF else 0
    if 0xE0 <= b <= 0xEF:
        lo, hi = (0xA0, 0xBF) if b == 0xE0 else (0x80, 0x9F) if b == 0xED else (0x80, 0xBF)
        return 3 if (i + 2 < n and lo <= data[i + 1] <= hi and 0x80 <= data[i + 2] <= 0xBF) else 0
    if 0xF0 <= b <= 0xF4:
        lo, hi = (0x90, 0xBF) if b == 0xF0 else (0x80, 0x8F) if b == 0xF4 else (0x80, 0xBF)
        return 4 if (i + 3 < n and lo <= data[i + 1] <= hi and 0x80 <= data[i + 2] <= 0xBF
                     and 0x80 <= data[i + 3] <= 0xBF) else 0
    return 0


# While a full-name reader runs (vv_long_names.activate: the Family Tree Maker's load_village), every
# decoded text has each long name's short form made whole -- in the save, the logs and every other file
# it reads -- so a long-named villager is one person everywhere.  None otherwise (names as written).
LONG_NAMES = None


def decode_game_text(data) -> str:
    """The games' rule (the same in native/vvfp_unicode_text): each well-formed UTF-8 sequence is its
    character; every other byte is its Windows-1252 character (the five undefined ones as Latin-1)."""
    text = _decode(data)
    return LONG_NAMES(text) if LONG_NAMES is not None else text


def _decode(data) -> str:
    data = bytes(data)
    if data.isascii():
        return data.decode("ascii")
    out = []
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b < 0x80:
            j = i + 1
            while j < n and data[j] < 0x80:
                j += 1
            out.append(data[i:j].decode("ascii"))
            i = j
            continue
        k = _utf8_length(data, i)
        if k:
            out.append(data[i:i + k].decode("utf-8"))
            i += k
        else:
            out.append(DECODING_TABLE[b])
            i += 1
    return "".join(out)


def encode_game_text(text: str, errors: str = "strict") -> bytes:
    """The bytes the games store for `text`: each character Windows-1252 has as its one byte (so a name an
    older patcher or the base game wrote keeps its bytes, and stays as short as it can), every other
    character as UTF-8 -- unless that mix would read back as different text (two Windows-1252 letters can
    also spell one UTF-8 character), when every non-ASCII character is written as UTF-8."""
    if text.isascii():
        return text.encode("ascii")
    parts = []
    for ch in text:
        b = ENCODING_MAP.get(ord(ch))
        parts.append(bytes([b]) if b is not None else ch.encode("utf-8", errors))
    raw = b"".join(parts)
    # A Latin-1 control U+0080-U+009F (how an older patcher read bytes 0x80-0x9F) is written as its own byte,
    # which now reads as its Windows-1252 character: the same byte, so the same text.
    if _decode(raw) == "".join(DECODING_TABLE[ord(c)] if 0x80 <= ord(c) <= 0x9F else c for c in text):
        return raw
    return text.encode("utf-8", errors)


class _Codec(codecs.Codec):
    def encode(self, text, errors="strict"):
        return encode_game_text(text, errors), len(text)

    def decode(self, data, errors="strict"):
        return decode_game_text(data), len(data)


class _IncrementalEncoder(codecs.IncrementalEncoder):
    def encode(self, text, final=False):
        return encode_game_text(text, self.errors)


class _IncrementalDecoder(codecs.BufferedIncrementalDecoder):
    def _buffer_decode(self, data, errors, final):
        data = bytes(data)
        if not final:
            # Hold back a trailing partial UTF-8 sequence until the next chunk (or the end) decides it.
            for back in (1, 2, 3):
                if len(data) >= back:
                    b = data[-back]
                    need = 2 if 0xC2 <= b <= 0xDF else 3 if 0xE0 <= b <= 0xEF else 4 if 0xF0 <= b <= 0xF4 else 0
                    if need > back and all(0x80 <= c <= 0xBF for c in data[len(data) - back + 1:]):
                        return decode_game_text(data[:-back]), len(data) - back
                    if b < 0x80 or b >= 0xC0:
                        break
        return decode_game_text(data), len(data)


class _StreamWriter(_Codec, codecs.StreamWriter):
    pass


class _StreamReader(_Codec, codecs.StreamReader):
    pass


_INFO = codecs.CodecInfo(
    name=GAME_TEXT,
    encode=_Codec().encode,
    decode=_Codec().decode,
    incrementalencoder=_IncrementalEncoder,
    incrementaldecoder=_IncrementalDecoder,
    streamreader=_StreamReader,
    streamwriter=_StreamWriter,
)


def _search(name: str):
    return _INFO if name.replace("_", "-").lower() == GAME_TEXT else None


codecs.register(_search)


def game_char(ch: str) -> int | None:
    """The game byte of one character, or None when the games cannot hold it."""
    return ENCODING_MAP.get(ord(ch))


def printable(ch: str) -> bool:
    """A character the games draw and accept typed with "Render Unicode with In-Game Fonts" or "Use Unicode
    Font": decided by code point (docs/UNICODE_SPEC.md), never by this Python's Unicode version, so a letter
    newer than its data is still taken. Refused: NUL and the C0 controls, DEL, the C1 controls (which hold
    the five bytes Windows-1252 leaves undefined), lone surrogates, the line and paragraph separators
    (U+2028, U+2029) and the byte order mark (U+FEFF). Private-use and not-yet-assigned code points are
    taken, as in the other Fun Patchers; format characters such as the zero-width joiner of emoji too."""
    if len(ch) != 1:
        return False
    cp = ord(ch)
    return not (cp < 0x20 or 0x7F <= cp <= 0x9F or 0xD800 <= cp <= 0xDFFF
                or cp in (0x2028, 0x2029, 0xFEFF))


def byte_length(text: str) -> int:
    """How many bytes the games store for `text` (their limits count bytes)."""
    return len(encode_game_text(text))


ZERO_WIDTH_JOINER = chr(0x200D)


def _extends(ch: str) -> bool:
    import unicodedata
    cp = ord(ch)
    return (unicodedata.combining(ch) != 0 or unicodedata.category(ch) in ("Mn", "Me")
            or cp in (0x200C, 0x200D) or 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF
            or 0x1F3FB <= cp <= 0x1F3FF or 0xE0020 <= cp <= 0xE007F)


def clusters(text: str) -> list[str]:
    """`text` cut into the units the games' companion draws and erases whole (native text_utf8.h): a
    character with its combining marks, variation selectors, emoji modifiers, tags and zero-width-joined
    parts; a regional-indicator pair (a flag)."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        j = i + 1
        if 0x1F1E6 <= ord(text[i]) <= 0x1F1FF and j < n and 0x1F1E6 <= ord(text[j]) <= 0x1F1FF:
            j += 1
        while j < n and _extends(text[j]):
            j += 1
            if text[j - 1] == ZERO_WIDTH_JOINER and j < n and text[j] not in " \n":
                j += 1
        out.append(text[i:j])
        i = j
    return out


def fit_bytes(text: str, limit: int) -> str:
    """The longest start of `text`, cut between whole units (clusters()), whose bytes fit `limit`."""
    out = ""
    for unit in clusters(text):
        if byte_length(out + unit) > limit:
            break
        out += unit
    return out
