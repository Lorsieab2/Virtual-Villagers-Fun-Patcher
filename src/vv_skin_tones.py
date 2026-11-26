"""Skin tones: the tone table, the inheritance rule and the per-save file, as the patcher's Python reads them.

One place for what every part must agree on ("VVFP Skin Tones.dll" in native/vvfp_skin_tones keeps the same
numbers; tests/test_skin_tones.py holds the two together):

THE TONES.  Tone 0 is the game's own art ("Default").  Tones 1..TONE_COUNT run from light to dark:
Porcelain ... Ebony, the owner's ten (2026-11-26).  TONE_TABLE gives each tone's lit mid-skin;
scripts/skin_tone_preview.py turns it into pictures.

INHERITANCE.  "babies conceived from two parents inherit skin tones same as head rules" (the owner,
2026-11-26).  The later games' creators roll a newborn's head as (The Lost Children 0x44CBAB, The Secret
City 0x4564A7, The Tree of Life 0x45F235, New Believers 0x46853A; rand(n) is the game's rand() % n):

    if rand(100) >= 5 and a parent's value is not 0:  (father + mother) / 2 + rand(3) - 1, held to the range
    else:                                             any value, each as likely

inherit() is that rule on the tone number, held to 1..TONE_COUNT.  A New Home's own births inherit
nothing (its creator 0x43C350 rolls head and body at random), so its tones use the same rule.  A parent
whose tone is not known counts as the other parent's (a head is always known to the game; a tone is not),
and with neither known the tone is random, as the head is.  Founders and arrivals are random.  Twins and
triplets copy the first baby, as their heads do.

THE FILE.  "Virtual Villagers Fun Patcher\\Save <S>\\Data\\Skin Tones\\Skin Tones - Save <S>.dat", in the
shape of the Head Looks' file (native/vvfp_head_look/head_look_store.inc) with its own magic 'VST2':

    u32 magic, u32 game (1..5), u32 count (150 or 256),
    u32 roster[count], u32 id[count], u8 value[count], u8 birth[count]

birth: the tone the villager was born with or first given (0 none, 1..TONE_COUNT); "Reset to birth tone"
puts it back.  The first layout, 'VST1', had no birth bytes (12 + count * 9 bytes) and is still read: its
villagers' birth tones are the tones they had.

value: the low four bits are the villager's tone (0 none yet, 1..TONE_COUNT, 15 the game's own art, chosen); the
high four bits are, on a mother who is carrying, her baby's tone, rolled once at the conception (0 none):
the held baby is drawn with it and the newborn is given it unchanged.
"""
from __future__ import annotations

import struct
from pathlib import Path

# THE TEN TONES (the owner, 2026-11-26: "Skin tones should be similar to this", a picture of a Lost Children
# woman as Default and S1..S10).  Name and colour of each tone's lit mid-skin, light to dark; the colours
# are the picture's own swatches.  (scripts/build_vv2_skin_atlases.py holds an older list of ten, a little
# different: its TARGETS.)
TONE_COLOURS = (
    ("Porcelain", "#fbe3d7"),
    ("Fair", "#f0ccaa"),
    ("Light golden", "#e2b88c"),
    ("Light olive", "#cea878"),
    ("Copper", "#cc8a5a"),
    ("Warm brown", "#b0784e"),
    ("Medium brown", "#92623e"),
    ("Deep brown", "#724c32"),
    ("Dark", "#523423"),
    ("Ebony", "#322017"),
)


def _oklch(text: str):
    """(lightness, chroma, hue in degrees) of a "#rrggbb" colour in OKLCh."""
    import math
    lin = []
    for i in (1, 3, 5):
        c = int(text[i:i + 2], 16) / 255
        lin.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = lin
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    A = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    B = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, math.hypot(A, B), math.degrees(math.atan2(B, A))


# (name, hex, OKLab lightness, chroma, hue in degrees) of each tone's lit mid-skin.
TONE_TABLE = tuple((name, text) + _oklch(text) for name, text in TONE_COLOURS)
TONE_COUNT = len(TONE_TABLE)
TONE_NONE = 0               # no tone kept yet: drawn with the game's own art
TONE_GAMES_OWN = 15         # the game's own art, chosen in Change Appearance
GAMES_OWN_NAME = "Default"

MAGIC = 0x32545356          # 'VST2'
MAGIC_ONE_BYTE = 0x31545356  # 'VST1': no birth tones; still read
FOLDER = "Skin Tones"
LOG_WORD = "skin tone"      # "Old skin tone: ..." / "New skin tone: ..." in an "Appearance changed" record
BIRTH_LINE = "Skin tone"    # "Skin tone: ..." in a Birth record


def tone_name(tone: int) -> str:
    """A tone as the windows and the logs write it: "Copper", or "Default" for the game's own art."""
    if 1 <= tone <= TONE_COUNT:
        return TONE_TABLE[tone - 1][0]
    return GAMES_OWN_NAME


def inherit(father: int, mother: int, r100: int, r3: int, rn: int) -> int:
    """A newborn's tone by the games' head rule.  `father`, `mother`: 1..TONE_COUNT, or 0 for not known.
    r100, r3 and rn are the rolls rand(100), rand(3) and rand(TONE_COUNT).  Always 1..TONE_COUNT."""
    father = father if 1 <= father <= TONE_COUNT else 0
    mother = mother if 1 <= mother <= TONE_COUNT else 0
    if r100 < 5 or (father == 0 and mother == 0):
        return rn % TONE_COUNT + 1
    father, mother = father or mother, mother or father
    return min(max((father + mother) // 2 + r3 % 3 - 1, 1), TONE_COUNT)


def head_rule(father: int, mother: int, r100: int, r3: int, rn: int, count: int = 30) -> int:
    """The games' own head roll (heads 0..count-1), for comparing with the stock executables."""
    if r100 < 5 or (father == 0 and mother == 0):
        return rn % count
    return min(max((father + mother) // 2 + r3 % 3 - 1, 0), count - 1)


def file_path(patcher_folder: Path, slot: int) -> Path:
    return Path(patcher_folder) / f"Save {slot}" / "Data" / FOLDER / f"{FOLDER} - Save {slot}.dat"


def pack(game: int, roster, ids, values, births) -> bytes:
    count = len(roster)
    if not (len(ids) == len(values) == len(births) == count):
        raise ValueError("roster, ids, values and births must be the same length")
    return (struct.pack("<3I", MAGIC, game, count) + struct.pack(f"<{count}I", *roster)
            + struct.pack(f"<{count}I", *ids) + bytes(values) + bytes(births))


def unpack(data: bytes):
    """(game, roster, ids, values, births) of a file's bytes, either layout; ValueError for any other shape."""
    if len(data) < 12:
        raise ValueError("too short for a Skin Tones file")
    magic, game, count = struct.unpack_from("<3I", data)
    per = {MAGIC: 10, MAGIC_ONE_BYTE: 9}.get(magic)
    if per is None or not 1 <= game <= 5 or count not in (150, 256) or len(data) != 12 + count * per:
        raise ValueError("not a Skin Tones file")
    roster = struct.unpack_from(f"<{count}I", data, 12)
    ids = struct.unpack_from(f"<{count}I", data, 12 + 4 * count)
    values = tuple(data[12 + 8 * count:12 + 9 * count])
    births = tuple(data[12 + 9 * count:]) if magic == MAGIC else tuple(tone_of(v) for v in values)
    return game, roster, ids, values, births


def tone_of(value: int) -> int:
    """The tone a kept byte draws: 0 for none yet and for the game's own, else 1..TONE_COUNT."""
    tone = value & 0x0F
    return tone if 1 <= tone <= TONE_COUNT else 0


def pending_baby_tone(value: int) -> int:
    """The tone of the baby a carrying mother's kept byte promises: 1..TONE_COUNT, or 0 for none."""
    tone = (value >> 4) & 0x0F
    return tone if 1 <= tone <= TONE_COUNT else 0


def tones_by_identity(data: bytes) -> dict[int, int]:
    """{villager identity: tone} of a file's bytes, for the Family Tree, the Picture Studio and Revive: every
    villager a tone is kept for (0 = the game's own art)."""
    _, _, ids, values, _ = unpack(data)
    return {identity: tone_of(value) for identity, value in zip(ids, values) if identity and value & 0x0F}


def birth_tones_by_identity(data: bytes) -> dict[int, int]:
    """{villager identity: birth tone 1..TONE_COUNT} of a file's bytes."""
    _, _, ids, values, births = unpack(data)
    return {identity: birth for identity, value, birth in zip(ids, values, births)
            if identity and value & 0x0F and 1 <= birth <= TONE_COUNT}
