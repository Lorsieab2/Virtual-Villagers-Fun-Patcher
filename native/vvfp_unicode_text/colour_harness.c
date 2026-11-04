/* colour_harness.c -- colour_fonts.inc (Direct2D / DirectWrite colour letters) outside the game
   (tests/test_unicode_parity_ui.py).  Draws a text in a face and prints "colour=<0|1> ink=<pixels>
   rgb=<distinct colours>"; cf_start failing (no Direct2D) prints "unavailable".
   Usage: colour_harness.exe <face> <weight> <ppem> <hex code points...>  (32-bit, like the companion). */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "colour_fonts.inc"

int main(int argc, char **argv) {
    WCHAR face[64], text[32];
    int weight, ppem, n = 0, i, w = 200, h = 160, colour = 0, ink = 0, kinds = 0, ok;
    unsigned int *px, seen[64];
    if (argc < 5) {
        printf("usage: colour_harness face weight ppem hex...\n");
        return 2;
    }
    MultiByteToWideChar(CP_UTF8, 0, argv[1], -1, face, 64);
    if (strcmp(argv[2], "tables") == 0) {
        /* cf_has_bitmap_colour on the face: CBDT / sbix / SVG */
        HDC dc = CreateCompatibleDC(NULL);
        HFONT font = CreateFontW(-40, 0, 0, 0, 400, 0, 0, 0, DEFAULT_CHARSET, 0, 0, ANTIALIASED_QUALITY, 0, face);
        WCHAR got[64];
        HGDIOBJ old = SelectObject(dc, font);
        GetTextFaceW(dc, 64, got);
        printf("installed=%d bitmap=%d\n", lstrcmpiW(got, face) == 0, cf_has_bitmap_colour(dc));
        SelectObject(dc, old);
        DeleteObject(font);
        DeleteDC(dc);
        return 0;
    }
    weight = atoi(argv[2]);
    ppem = atoi(argv[3]);
    for (i = 4; i < argc && n < 30; ++i) {
        unsigned int cp = (unsigned int)strtoul(argv[i], NULL, 16);
        if (cp >= 0x10000) {
            text[n++] = (WCHAR)(0xD800 + ((cp - 0x10000) >> 10));
            text[n++] = (WCHAR)(0xDC00 + ((cp - 0x10000) & 0x3FF));
        } else {
            text[n++] = (WCHAR)cp;
        }
    }
    px = (unsigned int *)calloc((size_t)w * (size_t)h, 4);
    if (px == NULL) {
        return 2;
    }
    if (!cf_start()) {
        printf("unavailable\n");
        return 0;
    }
    ok = cf_draw(face, weight, ppem, text, n, w, h, 8, 100, px, &colour);
    if (!ok) {
        printf("not drawn\n");
        return 1;
    }
    for (i = 0; i < w * h; ++i) {
        if (px[i] >> 24) {
            int k;
            ++ink;
            for (k = 0; k < kinds && seen[k] != (px[i] & 0xF0F0F0u); ++k) {
            }
            if (k == kinds && kinds < 64) {
                seen[kinds++] = px[i] & 0xF0F0F0u;
            }
        }
    }
    printf("colour=%d ink=%d rgb=%d\n", colour, ink, kinds);
    free(px);
    return 0;
}
