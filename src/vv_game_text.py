"""How the patcher reads and writes the games' own text bytes: names, tribe names, logs, saves.

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


class _Codec(codecs.Codec):
    def encode(self, text, errors="strict"):
        return codecs.charmap_encode(text, errors, ENCODING_MAP)

    def decode(self, data, errors="strict"):
        return codecs.charmap_decode(data, errors, DECODING_TABLE)


class _IncrementalEncoder(codecs.IncrementalEncoder):
    def encode(self, text, final=False):
        return codecs.charmap_encode(text, self.errors, ENCODING_MAP)[0]


class _IncrementalDecoder(codecs.IncrementalDecoder):
    def decode(self, data, final=False):
        return codecs.charmap_decode(data, self.errors, DECODING_TABLE)[0]


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
    """A character the games draw (with Render Unicode with In-Game Fonts) and accept typed: printable
    ASCII or a printable Windows-1252 character above it -- never a control byte, never a byte
    Windows-1252 leaves undefined."""
    b = game_char(ch)
    if b is None or b < 0x20 or b == 0x7F:
        return False
    return not 0x80 <= ord(DECODING_TABLE[b]) <= 0x9F     # the five bytes Windows-1252 leaves undefined
