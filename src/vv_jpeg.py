"""Picture Studio's JPEG reader (the Everything tab, src/vv_pictures_assets.py): the games' .jpg pictures.

The games load their JPEGs with SDL2_image's IMG_LoadJPG_RW, which decodes them with the IJG's libjpeg 9
(13-Jan-2013, libjpeg-9.dll beside the game) at its defaults: SDL2_image only sets the output colour space to
RGB and turns colour quantizing off.  So, as libjpeg 9 does:

* Huffman decoding, baseline and progressive (every scan read before output, so no block smoothing on a
  complete file), restart intervals;
* the integer "slow" IDCT (jidctint.c jpeg_idct_islow) for blocks at the full size; libjpeg 9 scales a 2 x 2
  subsampled colour component up in the IDCT itself (jdmaster.c picks a 16 x 16 IDCT for it,
  jpeg_idct_16x16) instead of upsampling it afterwards, so its upsampler copies;
* the Adobe APP14 marker's transform flag (0: RGB stored as is; 1: YCbCr), else YCbCr, converted with
  jdcolor.c's tables.

tests/test_vv_jpeg.py decodes every JPEG the five games ship with the game's own libjpeg-9.dll run in Unicorn
and requires every pixel to be the same.  Pure Python (struct only).
"""
from __future__ import annotations

import struct

import vv_picture_image as pi


class JpegError(pi.PictureError):
    pass


ZIGZAG = (0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5, 12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6,
          7, 14, 21, 28, 35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51, 58, 59, 52, 45, 38, 31,
          39, 46, 53, 60, 61, 54, 47, 55, 62, 63)
# libjpeg reads past the 64th coefficient into a padded natural order table: an out-of-range k maps to 63.
NATURAL = ZIGZAG + (63,) * 16

SOF_MARKERS = (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF)


def jpeg_size(data: bytes) -> tuple[int, int]:
    """(width, height) from the frame header."""
    data = bytes(data)
    if not data.startswith(b"\xff\xd8"):
        raise JpegError("not a JPEG file")
    at = 2
    while at + 4 <= len(data):
        if data[at] != 0xFF:
            at += 1
            continue
        marker = data[at + 1]
        if marker == 0xFF:
            at += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            at += 2
            continue
        length = struct.unpack_from(">H", data, at + 2)[0]
        if marker in SOF_MARKERS:
            h, w = struct.unpack_from(">HH", data, at + 5)
            return w, h
        if marker == 0xDA:
            break
        at += 2 + length
    raise JpegError("the JPEG has no frame header")


# ------------------------------------------------------------------ the IDCTs (jidctint.c, 8-bit samples)

CONST_BITS = 13
PASS1_BITS = 2
PASS2_BITS = 5
RANGE_MASK = 1023
PASS2_OFFSET = (512 << PASS2_BITS) + (1 << (PASS2_BITS - 1))
SHIFT1 = CONST_BITS - PASS1_BITS
SHIFT2 = CONST_BITS + PASS2_BITS
# The post-IDCT range limit (jdmaster.c prepare_range_limit_table, IDCT_range_limit): the masked index less
# 384, clamped to 0..255.
LIMIT = bytes(min(255, max(0, i - 384)) for i in range(1024))


def _fix(x: float) -> int:
    return int(x * (1 << CONST_BITS) + 0.5)


F_0_298631336, F_0_390180644, F_0_541196100, F_0_765366865 = 2446, 3196, 4433, 6270
F_0_899976223, F_1_175875602, F_1_501321110, F_1_847759065 = 7373, 9633, 12299, 15137
F_1_961570560, F_2_053119869, F_2_562915447, F_3_072711026 = 16069, 16819, 20995, 25172


def idct_8x8(coef, q) -> list[int]:
    """jpeg_idct_islow: 64 dequantized-on-the-fly coefficients (natural order) -> 64 samples."""
    ws = [0] * 64
    for c in range(8):
        if not (coef[8 + c] or coef[16 + c] or coef[24 + c] or coef[32 + c] or coef[40 + c] or coef[48 + c]
                or coef[56 + c]):
            dc = (coef[c] * q[c]) << PASS1_BITS
            for r in range(0, 64, 8):
                ws[r + c] = dc
            continue
        z2 = (coef[c] * q[c]) << CONST_BITS
        z3 = (coef[32 + c] * q[32 + c]) << CONST_BITS
        z2 += 1 << (CONST_BITS - PASS1_BITS - 1)
        tmp0, tmp1 = z2 + z3, z2 - z3
        z2 = coef[16 + c] * q[16 + c]
        z3 = coef[48 + c] * q[48 + c]
        z1 = (z2 + z3) * F_0_541196100
        tmp2 = z1 + z2 * F_0_765366865
        tmp3 = z1 - z3 * F_1_847759065
        tmp10, tmp13, tmp11, tmp12 = tmp0 + tmp2, tmp0 - tmp2, tmp1 + tmp3, tmp1 - tmp3
        tmp0 = coef[56 + c] * q[56 + c]
        tmp1 = coef[40 + c] * q[40 + c]
        tmp2 = coef[24 + c] * q[24 + c]
        tmp3 = coef[8 + c] * q[8 + c]
        z2 = tmp0 + tmp2
        z3 = tmp1 + tmp3
        z1 = (z2 + z3) * F_1_175875602
        z2 = z2 * -F_1_961570560 + z1
        z3 = z3 * -F_0_390180644 + z1
        z1 = (tmp0 + tmp3) * -F_0_899976223
        tmp0 = tmp0 * F_0_298631336 + z1 + z2
        tmp3 = tmp3 * F_1_501321110 + z1 + z3
        z1 = (tmp1 + tmp2) * -F_2_562915447
        tmp1 = tmp1 * F_2_053119869 + z1 + z3
        tmp2 = tmp2 * F_3_072711026 + z1 + z2
        ws[c] = (tmp10 + tmp3) >> SHIFT1
        ws[56 + c] = (tmp10 - tmp3) >> SHIFT1
        ws[8 + c] = (tmp11 + tmp2) >> SHIFT1
        ws[48 + c] = (tmp11 - tmp2) >> SHIFT1
        ws[16 + c] = (tmp12 + tmp1) >> SHIFT1
        ws[40 + c] = (tmp12 - tmp1) >> SHIFT1
        ws[24 + c] = (tmp13 + tmp0) >> SHIFT1
        ws[32 + c] = (tmp13 - tmp0) >> SHIFT1
    out = [0] * 64
    for r in range(0, 64, 8):
        z2 = ws[r] + PASS2_OFFSET
        if not (ws[r + 1] or ws[r + 2] or ws[r + 3] or ws[r + 4] or ws[r + 5] or ws[r + 6] or ws[r + 7]):
            v = LIMIT[(z2 >> PASS2_BITS) & RANGE_MASK]
            out[r:r + 8] = (v,) * 8
            continue
        z3 = ws[r + 4]
        z2 <<= CONST_BITS
        z3 <<= CONST_BITS
        tmp0, tmp1 = z2 + z3, z2 - z3
        z2, z3 = ws[r + 2], ws[r + 6]
        z1 = (z2 + z3) * F_0_541196100
        tmp2 = z1 + z2 * F_0_765366865
        tmp3 = z1 - z3 * F_1_847759065
        tmp10, tmp13, tmp11, tmp12 = tmp0 + tmp2, tmp0 - tmp2, tmp1 + tmp3, tmp1 - tmp3
        tmp0, tmp1, tmp2, tmp3 = ws[r + 7], ws[r + 5], ws[r + 3], ws[r + 1]
        z2 = tmp0 + tmp2
        z3 = tmp1 + tmp3
        z1 = (z2 + z3) * F_1_175875602
        z2 = z2 * -F_1_961570560 + z1
        z3 = z3 * -F_0_390180644 + z1
        z1 = (tmp0 + tmp3) * -F_0_899976223
        tmp0 = tmp0 * F_0_298631336 + z1 + z2
        tmp3 = tmp3 * F_1_501321110 + z1 + z3
        z1 = (tmp1 + tmp2) * -F_2_562915447
        tmp1 = tmp1 * F_2_053119869 + z1 + z3
        tmp2 = tmp2 * F_3_072711026 + z1 + z2
        out[r] = LIMIT[((tmp10 + tmp3) >> SHIFT2) & RANGE_MASK]
        out[r + 7] = LIMIT[((tmp10 - tmp3) >> SHIFT2) & RANGE_MASK]
        out[r + 1] = LIMIT[((tmp11 + tmp2) >> SHIFT2) & RANGE_MASK]
        out[r + 6] = LIMIT[((tmp11 - tmp2) >> SHIFT2) & RANGE_MASK]
        out[r + 2] = LIMIT[((tmp12 + tmp1) >> SHIFT2) & RANGE_MASK]
        out[r + 5] = LIMIT[((tmp12 - tmp1) >> SHIFT2) & RANGE_MASK]
        out[r + 3] = LIMIT[((tmp13 + tmp0) >> SHIFT2) & RANGE_MASK]
        out[r + 4] = LIMIT[((tmp13 - tmp0) >> SHIFT2) & RANGE_MASK]
    return out


G_1_306562965, G_0_275899379, G_1_387039845, G_0_601344887 = (_fix(1.306562965), _fix(0.275899379),
                                                              _fix(1.387039845), _fix(0.601344887))
G_0_509795579, G_1_353318001, G_1_247225013, G_1_093201867 = (_fix(0.509795579), _fix(1.353318001),
                                                              _fix(1.247225013), _fix(1.093201867))
G_0_897167586, G_0_666655658, G_0_410524528, G_2_286341144 = (_fix(0.897167586), _fix(0.666655658),
                                                              _fix(0.410524528), _fix(2.286341144))
G_1_835730603, G_0_138617169, G_0_071888074, G_1_125726048 = (_fix(1.835730603), _fix(0.138617169),
                                                              _fix(0.071888074), _fix(1.125726048))
G_1_407403738, G_0_766367282, G_1_971951411, G_1_065388962 = (_fix(1.407403738), _fix(0.766367282),
                                                              _fix(1.971951411), _fix(1.065388962))
G_3_141271809 = _fix(3.141271809)


def _idct16(e0, e2, e4, e6, o1, o3, o5, o7, first: bool) -> list[int]:
    """One 16-point pass of jpeg_idct_16x16 on (even, odd) inputs; `first`: pass 1 (columns, values not yet
    scaled) or pass 2 (rows)."""
    if first:
        tmp0 = (e0 << CONST_BITS) + (1 << (CONST_BITS - PASS1_BITS - 1))
    else:
        tmp0 = (e0 + PASS2_OFFSET) << CONST_BITS
    z1 = e4
    tmp1 = z1 * G_1_306562965
    tmp2 = z1 * F_0_541196100
    tmp10, tmp11, tmp12, tmp13 = tmp0 + tmp1, tmp0 - tmp1, tmp0 + tmp2, tmp0 - tmp2
    z1, z2 = e2, e6
    z3 = z1 - z2
    z4 = z3 * G_0_275899379
    z3 = z3 * G_1_387039845
    tmp0 = z3 + z2 * F_2_562915447
    tmp1 = z4 + z1 * F_0_899976223
    tmp2 = z3 - z1 * G_0_601344887
    tmp3 = z4 - z2 * G_0_509795579
    tmp20, tmp27 = tmp10 + tmp0, tmp10 - tmp0
    tmp21, tmp26 = tmp12 + tmp1, tmp12 - tmp1
    tmp22, tmp25 = tmp13 + tmp2, tmp13 - tmp2
    tmp23, tmp24 = tmp11 + tmp3, tmp11 - tmp3
    z1, z2, z3, z4 = o1, o3, o5, o7
    tmp11 = z1 + z3
    tmp1 = (z1 + z2) * G_1_353318001
    tmp2 = tmp11 * G_1_247225013
    tmp3 = (z1 + z4) * G_1_093201867
    tmp10 = (z1 - z4) * G_0_897167586
    tmp11 = tmp11 * G_0_666655658
    tmp12 = (z1 - z2) * G_0_410524528
    tmp0 = tmp1 + tmp2 + tmp3 - z1 * G_2_286341144
    tmp13 = tmp10 + tmp11 + tmp12 - z1 * G_1_835730603
    z1 = (z2 + z3) * G_0_138617169
    tmp1 += z1 + z2 * G_0_071888074
    tmp2 += z1 - z3 * G_1_125726048
    z1 = (z3 - z2) * G_1_407403738
    tmp11 += z1 - z3 * G_0_766367282
    tmp12 += z1 + z2 * G_1_971951411
    z2 += z4
    z1 = z2 * -G_0_666655658
    tmp1 += z1
    tmp3 += z1 + z4 * G_1_065388962
    z2 = z2 * -G_1_247225013
    tmp10 += z2 + z4 * G_3_141271809
    tmp12 += z2
    z2 = (z3 + z4) * -G_1_353318001
    tmp2 += z2
    tmp3 += z2
    z2 = (z4 - z3) * G_0_410524528
    tmp10 += z2
    tmp11 += z2
    return [tmp20 + tmp0, tmp21 + tmp1, tmp22 + tmp2, tmp23 + tmp3, tmp24 + tmp10, tmp25 + tmp11,
            tmp26 + tmp12, tmp27 + tmp13, tmp27 - tmp13, tmp26 - tmp12, tmp25 - tmp11, tmp24 - tmp10,
            tmp23 - tmp3, tmp22 - tmp2, tmp21 - tmp1, tmp20 - tmp0]


def idct_16x16(coef, q) -> list[int]:
    """jpeg_idct_16x16: 64 coefficients -> 256 samples (16 rows of 16)."""
    ws = [0] * 128                                    # 16 rows x 8 columns
    for c in range(8):
        d = [coef[r * 8 + c] * q[r * 8 + c] for r in range(8)]
        col = _idct16(d[0], d[2], d[4], d[6], d[1], d[3], d[5], d[7], True)
        for r in range(16):
            ws[r * 8 + c] = col[r] >> SHIFT1
    out = [0] * 256
    for r in range(16):
        w = ws[r * 8:r * 8 + 8]
        row = _idct16(w[0], w[2], w[4], w[6], w[1], w[3], w[5], w[7], False)
        out[r * 16:r * 16 + 16] = [LIMIT[(v >> SHIFT2) & RANGE_MASK] for v in row]
    return out


# ------------------------------------------------------------------ colour (jdcolor.c)

SCALEBITS = 16
ONE_HALF = 1 << (SCALEBITS - 1)


def _cfix(x: float) -> int:
    return int(x * (1 << SCALEBITS) + 0.5)


CR_R = [(_cfix(1.40200) * (i - 128) + ONE_HALF) >> SCALEBITS for i in range(256)]
CB_B = [(_cfix(1.77200) * (i - 128) + ONE_HALF) >> SCALEBITS for i in range(256)]
CR_G = [-_cfix(0.71414) * (i - 128) for i in range(256)]
CB_G = [-_cfix(0.34414) * (i - 128) + ONE_HALF for i in range(256)]
CLAMP = bytes([0] * 384) + bytes(range(256)) + bytes([255] * 384)     # index v + 384


# ------------------------------------------------------------------ the decoder

class _Component:
    __slots__ = ("ident", "h", "v", "tq", "bw", "bh", "aw", "ah", "blocks", "pred", "dc_table", "ac_table")


def _huffman(lengths: bytes, values: bytes) -> list:
    """A 16-bit lookup: entry = (code length << 8) | symbol, 0 for no code."""
    table = [0] * 65536
    code = 0
    at = 0
    for length in range(1, 17):
        for _ in range(lengths[length - 1]):
            span = 1 << (16 - length)
            start = code << (16 - length)
            if start + span > 65536:
                raise JpegError("the JPEG has a bad Huffman table")
            table[start:start + span] = [(length << 8) | values[at]] * span
            at += 1
            code += 1
        code <<= 1
    return table


class _Bits:
    """The entropy-coded bytes of one restart interval (stuffing removed), read MSB first; past the end, zeros
    (libjpeg's fill_bit_buffer inserts zeros)."""

    __slots__ = ("data", "pos")

    def __init__(self, data: bytes) -> None:
        self.data = data + b"\0\0\0\0"
        self.pos = 0

    def peek16(self) -> int:
        p = self.pos
        d = self.data
        i = p >> 3
        if i + 3 > len(d):
            return 0
        return (((d[i] << 16) | (d[i + 1] << 8) | d[i + 2]) >> (8 - (p & 7))) & 0xFFFF

    def decode(self, table) -> int:
        entry = table[self.peek16()]
        if not entry:
            # libjpeg: "Corrupt JPEG data: bad Huffman code", returns 0 and goes on
            self.pos += 16
            return 0
        self.pos += entry >> 8
        return entry & 0xFF

    def receive(self, n: int) -> int:
        if n == 0:
            return 0
        p = self.pos
        d = self.data
        i = p >> 3
        if i + 4 > len(d):
            self.pos += n
            return 0
        word = (d[i] << 24) | (d[i + 1] << 16) | (d[i + 2] << 8) | d[i + 3]
        self.pos = p + n
        return (word >> (32 - (p & 7) - n)) & ((1 << n) - 1)

    def bit(self) -> int:
        p = self.pos
        i = p >> 3
        self.pos = p + 1
        return (self.data[i] >> (7 - (p & 7))) & 1 if i < len(self.data) else 0


def _extend(v: int, s: int) -> int:
    return v - (1 << s) + 1 if v < (1 << (s - 1)) else v


def _segments(data: bytes, at: int) -> tuple[list[bytes], int]:
    """The entropy-coded data from `at` cut at its restart markers, stuffing removed; and where the next
    marker is."""
    out = []
    current = bytearray()
    n = len(data)
    while at < n:
        j = data.find(b"\xff", at)
        if j < 0:
            current += data[at:]
            at = n
            break
        current += data[at:j]
        if j + 1 >= n:
            at = n
            break
        nxt = data[j + 1]
        if nxt == 0x00:
            current.append(0xFF)
            at = j + 2
        elif 0xD0 <= nxt <= 0xD7:
            out.append(bytes(current))
            current = bytearray()
            at = j + 2
        elif nxt == 0xFF:
            at = j + 1                                  # fill byte
        else:
            at = j
            break
    out.append(bytes(current))
    return out, at


def decode_jpeg(data: bytes) -> pi.Image:
    """The picture as libjpeg 9 gives it to SDL2_image (opaque RGB)."""
    data = bytes(data)
    if not data.startswith(b"\xff\xd8"):
        raise JpegError("not a JPEG file")
    qt: dict[int, list[int]] = {}
    dc_tables: dict[int, list] = {}
    ac_tables: dict[int, list] = {}
    comps: list[_Component] = []
    width = height = 0
    progressive = False
    restart = 0
    adobe = None
    jfif = False
    hmax = vmax = 1
    mcux = mcuy = 0
    at = 2
    while at < len(data):
        if data[at] != 0xFF:
            at += 1
            continue
        marker = data[at + 1]
        if marker == 0xFF:
            at += 1
            continue
        if marker == 0xD8 or 0xD0 <= marker <= 0xD7 or marker == 0x01:
            at += 2
            continue
        if marker == 0xD9:
            break
        length = struct.unpack_from(">H", data, at + 2)[0]
        body = data[at + 4:at + 2 + length]
        at += 2 + length
        if marker == 0xDB:
            k = 0
            while k < len(body):
                pq, tq = body[k] >> 4, body[k] & 15
                if pq:
                    vals = struct.unpack_from(">64H", body, k + 1)
                    k += 129
                else:
                    vals = body[k + 1:k + 65]
                    k += 65
                table = [0] * 64
                for i in range(64):
                    table[ZIGZAG[i]] = vals[i]
                qt[tq] = table
        elif marker == 0xC4:
            k = 0
            while k < len(body):
                tc, th = body[k] >> 4, body[k] & 15
                lengths = body[k + 1:k + 17]
                count = sum(lengths)
                values = body[k + 17:k + 17 + count]
                (ac_tables if tc else dc_tables)[th] = _huffman(lengths, values)
                k += 17 + count
        elif marker in (0xC0, 0xC1, 0xC2):
            progressive = marker == 0xC2
            if body[0] != 8:
                raise JpegError("only 8-bit JPEGs are read")
            height, width = struct.unpack_from(">HH", body, 1)
            for i in range(body[5]):
                c = _Component()
                c.ident, sampling, c.tq = body[6 + 3 * i], body[7 + 3 * i], body[8 + 3 * i]
                c.h, c.v = sampling >> 4, sampling & 15
                comps.append(c)
            hmax = max(c.h for c in comps)
            vmax = max(c.v for c in comps)
            mcux = -(-width // (8 * hmax))
            mcuy = -(-height // (8 * vmax))
            for c in comps:
                c.bw = -(-(-(-width * c.h // hmax)) // 8)          # blocks a non-interleaved scan covers
                c.bh = -(-(-(-height * c.v // vmax)) // 8)
                c.aw, c.ah = mcux * c.h, mcuy * c.v               # blocks allocated (whole MCUs)
                c.blocks = [[0] * 64 for _ in range(c.aw * c.ah)]
        elif marker in SOF_MARKERS:
            raise JpegError("this kind of JPEG (lossless, hierarchical or arithmetic) is not read")
        elif marker == 0xDD:
            restart = struct.unpack_from(">H", body, 0)[0]
        elif marker == 0xEE and body[:5] == b"Adobe" and len(body) >= 12:
            adobe = body[11]
        elif marker == 0xE0 and body[:5] == b"JFIF\0":
            jfif = True
        elif marker == 0xDA:
            n = body[0]
            scan = []
            for i in range(n):
                cid, tables = body[1 + 2 * i], body[2 + 2 * i]
                c = next((x for x in comps if x.ident == cid), None)
                if c is None:
                    raise JpegError("a JPEG scan names a component the frame does not have")
                c.dc_table, c.ac_table = dc_tables.get(tables >> 4), ac_tables.get(tables & 15)
                scan.append(c)
            ss, se, a = body[1 + 2 * n], body[2 + 2 * n], body[3 + 2 * n]
            ah, al = a >> 4, a & 15
            segments, at = _segments(data, at)
            _scan(scan, segments, restart, progressive, ss, se, ah, al, mcux, mcuy)
    if not comps or not width or not height:
        raise JpegError("the JPEG has no picture")
    return _output(comps, width, height, hmax, vmax, qt, adobe, jfif)


def _scan(scan, segments, restart, progressive, ss, se, ah, al, mcux, mcuy) -> None:
    single = len(scan) == 1
    if single:
        c = scan[0]
        units = [(c, by * c.aw + bx) for by in range(c.bh) for bx in range(c.bw)]
        mcus = [[u] for u in units]
    else:
        mcus = []
        for my in range(mcuy):
            for mx in range(mcux):
                mcu = []
                for c in scan:
                    for y in range(c.v):
                        for x in range(c.h):
                            mcu.append((c, (my * c.v + y) * c.aw + mx * c.h + x))
                mcus.append(mcu)
    per = restart if restart else len(mcus)
    seg_index = 0
    for start in range(0, len(mcus), per or 1):
        bits = _Bits(segments[seg_index] if seg_index < len(segments) else b"")
        seg_index += 1
        for c in scan:
            c.pred = 0
        eobrun = [0]
        for mcu in mcus[start:start + per]:
            for c, index in mcu:
                block = c.blocks[index]
                if not progressive:
                    _baseline(bits, c, block)
                elif ss == 0:
                    if ah == 0:
                        s = bits.decode(c.dc_table)
                        diff = _extend(bits.receive(s), s) if s else 0
                        c.pred += diff
                        block[0] = c.pred << al
                    elif bits.bit():
                        block[0] |= 1 << al
                elif ah == 0:
                    _ac_first(bits, c, block, ss, se, al, eobrun)
                else:
                    _ac_refine(bits, c, block, ss, se, al, eobrun)


def _baseline(bits: _Bits, c, block) -> None:
    s = bits.decode(c.dc_table)
    if s:
        c.pred += _extend(bits.receive(s), s)
    block[0] = c.pred
    table = c.ac_table
    k = 1
    while k < 64:
        rs = bits.decode(table)
        r, s = rs >> 4, rs & 15
        if s:
            k += r
            block[NATURAL[k]] = _extend(bits.receive(s), s)
            k += 1
        else:
            if r != 15:
                break
            k += 16


def _ac_first(bits: _Bits, c, block, ss, se, al, eobrun) -> None:
    if eobrun[0] > 0:
        eobrun[0] -= 1
        return
    table = c.ac_table
    k = ss
    while k <= se:
        rs = bits.decode(table)
        r, s = rs >> 4, rs & 15
        if s:
            k += r
            block[NATURAL[k]] = _extend(bits.receive(s), s) << al
        else:
            if r == 15:
                k += 15
            else:
                run = 1 << r
                if r:
                    run += bits.receive(r)
                eobrun[0] = run - 1
                break
        k += 1


def _ac_refine(bits: _Bits, c, block, ss, se, al, eobrun) -> None:
    p1 = 1 << al
    m1 = -1 << al
    k = ss
    table = c.ac_table
    if eobrun[0] == 0:
        while k <= se:
            rs = bits.decode(table)
            r, s = rs >> 4, rs & 15
            if s:
                s = p1 if bits.bit() else m1
            elif r != 15:
                run = 1 << r
                if r:
                    run += bits.receive(r)
                eobrun[0] = run
                break
            while k <= se:
                z = NATURAL[k]
                if block[z] != 0:
                    if bits.bit() and (block[z] & p1) == 0:
                        block[z] += p1 if block[z] >= 0 else m1
                else:
                    r -= 1
                    if r < 0:
                        break
                k += 1
            if s:
                block[NATURAL[k]] = s
            k += 1
    if eobrun[0] > 0:
        while k <= se:
            z = NATURAL[k]
            if block[z] != 0 and bits.bit() and (block[z] & p1) == 0:
                block[z] += p1 if block[z] >= 0 else m1
            k += 1
        eobrun[0] -= 1


def _plane(c, qt, hmax, vmax) -> tuple[list, int, int]:
    """The component's samples at the output size, as libjpeg 9's IDCT scaling gives them: a component at
    the full sampling with the 8 x 8 IDCT; one subsampled 2 x 2 with the 16 x 16 IDCT (jdmaster.c)."""
    q = qt.get(c.tq)
    if q is None:
        raise JpegError("the JPEG has no quantization table for a component")
    hs = _scaled(hmax, c.h)
    vs = _scaled(vmax, c.v)
    if hs != vs or hs not in (8, 16):
        raise JpegError("this JPEG's colour sampling is not one the games use")
    size = hs
    pw = c.aw * size
    plane = [0] * (pw * c.ah * size)
    idct = idct_8x8 if size == 8 else idct_16x16
    zero_cache: dict[int, list] = {}
    for by in range(c.ah):
        for bx in range(c.aw):
            block = c.blocks[by * c.aw + bx]
            if not any(block[1:]):
                samples = zero_cache.get(block[0])
                if samples is None:
                    samples = zero_cache[block[0]] = idct(block, q)
            else:
                samples = idct(block, q)
            base = by * size * pw + bx * size
            for r in range(size):
                plane[base + r * pw:base + r * pw + size] = samples[r * size:(r + 1) * size]
    return plane, pw, size


def _scaled(maxf: int, f: int) -> int:
    """jdmaster.c's DCT scaled size at scale 1/1 with fancy upsampling: 8, doubled while 8 x s <= 8 ... i.e.
    once when the max sampling factor is a multiple of twice the component's."""
    size = 8
    s = 1
    while 8 * s <= 8 and maxf % (f * s * 2) == 0:
        s *= 2
    return size * s


def _output(comps, width, height, hmax, vmax, qt, adobe, jfif) -> pi.Image:
    image = pi.Image(width, height)
    out = image.data
    planes = [_plane(c, qt, hmax, vmax) for c in comps]
    for (_plane_, _pw, size), c in zip(planes, comps):
        # each component's scaled blocks must reach the full size (else libjpeg's upsampler would run)
        if size * c.h != 8 * hmax or size * c.v != 8 * vmax:
            raise JpegError("this JPEG's colour sampling is not one the games use")
    if len(comps) == 1:
        plane, pw, _s = planes[0]
        for y in range(height):
            row = plane[y * pw:y * pw + width]
            for x, v in enumerate(row):
                at = (y * width + x) * 4
                out[at:at + 4] = bytes((v, v, v, 255))
        return image
    if len(comps) != 3:
        raise JpegError("only grey and three-colour JPEGs are read")
    rgb = adobe == 0 if adobe is not None else (not jfif and [c.ident for c in comps] == [82, 71, 66])
    (p0, w0, _a), (p1, w1, _b), (p2, w2, _c) = planes
    for y in range(height):
        o = y * width * 4
        r0, r1, r2 = y * w0, y * w1, y * w2
        if rgb:
            for x in range(width):
                out[o] = p0[r0 + x]
                out[o + 1] = p1[r1 + x]
                out[o + 2] = p2[r2 + x]
                out[o + 3] = 255
                o += 4
        else:
            for x in range(width):
                yy, cb, cr = p0[r0 + x], p1[r1 + x], p2[r2 + x]
                out[o] = CLAMP[yy + CR_R[cr] + 384]
                out[o + 1] = CLAMP[yy + ((CB_G[cb] + CR_G[cr]) >> SCALEBITS) + 384]
                out[o + 2] = CLAMP[yy + CB_B[cb] + 384]
                out[o + 3] = 255
                o += 4
    return image
