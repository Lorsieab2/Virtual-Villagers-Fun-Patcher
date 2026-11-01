/* glyph_harness.c -- runs glyphs.inc, the in-game companion's letter maker, outside the game, so
   tests/test_unicode_text.py can require that it makes the very pixels src/vv_font_glyphs.py makes.

   glyph_harness.exe <in> <out> <burweed | no-burweed> [<in> <out> <mode> ...]
     in:  int32 sheet width, height, entry count, spacing, burweed (1/0); the entries (5 int32 each);
          the sheet's alpha, row by row.
     out: for each code 0..255: int32 source (0 none, 1 game, 2 alias, 3 ttf, 4 composed, 5 stand-in),
          width, height, then width*height alpha bytes (only for codes the font lacks: the rest 0, 0, 0).
   "no-burweed" leaves Burweed ICG out, as on a machine without it. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include "unicode_text_tables.h"
#include "glyphs.inc"

static vg_gdi gdi;
static WCHAR found_burweed[64];

static int one(const char *in_path, const char *out_path, const char *mode) {
    FILE *in, *out;
    int head[5], code;
    int (*ent)[5];
    unsigned char *alpha;
    vg_sheet sheet;
    vg_font f;
    lstrcpynW(gdi.burweed, strcmp(mode, "no-burweed") == 0 ? L"" : found_burweed, 64);
    if (fopen_s(&in, in_path, "rb") != 0) {
        return 2;
    }
    if (fread(head, sizeof head, 1, in) != 1) {
        return 3;
    }
    ent = (int (*)[5])malloc(sizeof(int[5]) * (size_t)(head[2] + 1));
    alpha = (unsigned char *)malloc((size_t)head[0] * (size_t)head[1]);
    if (ent == NULL || alpha == NULL
        || fread(ent, sizeof(int[5]), (size_t)head[2], in) != (size_t)head[2]
        || fread(alpha, 1, (size_t)head[0] * (size_t)head[1], in) != (size_t)head[0] * (size_t)head[1]) {
        return 4;
    }
    fclose(in);
    sheet.alpha = alpha;
    sheet.sw = head[0];
    sheet.sh = head[1];
    sheet.ent = (const int (*)[5])ent;
    sheet.n = head[2];
    if (!vg_font_open(&f, &gdi, &sheet, head[3], head[4])) {
        return 6;
    }
    if (fopen_s(&out, out_path, "wb") != 0) {
        return 7;
    }
    for (code = 0; code < 256; ++code) {
        int row[3] = {0, 0, 0};
        const vg_mask *g = NULL;
        if (VG_CP1252[code] != 0 && vg_entry(&sheet, code) < 0) {
            g = vg_glyph(&f, code);
            row[0] = f.source[code];
            if (g != NULL) {
                row[1] = g->w;
                row[2] = g->h;
            }
        }
        fwrite(row, sizeof row, 1, out);
        if (g != NULL) {
            fwrite(g->px, 1, (size_t)g->w * (size_t)g->h, out);
        }
    }
    fclose(out);
    vg_font_close(&f);
    free(ent);
    free(alpha);
    return 0;
}

int main(int argc, char **argv) {
    int i, r;
    if (argc < 4 || (argc - 1) % 3 != 0 || !vg_gdi_open(&gdi)) {
        return 2;
    }
    lstrcpynW(found_burweed, gdi.burweed, 64);
    for (i = 1; i + 2 < argc; i += 3) {
        r = one(argv[i], argv[i + 1], argv[i + 2]);
        if (r != 0) {
            printf("failed %s: %d\n", argv[i], r);
            return r;
        }
    }
    printf("burweed=%ls\n", found_burweed);
    return 0;
}
