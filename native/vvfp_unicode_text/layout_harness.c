/* layout_harness.c -- runs text_layout.h, the in-game companions' line breaking and composition (NFC),
   outside the game, on the real Windows icu.dll, so tests/test_unicode_layout.py can hold the DLL's own C to the
   spec (docs/UNICODE_SPEC.md row 3).

   layout_harness.exe <in> <out> [<word lists folder>]
     with the folder, the built-in table (F) breaks Thai, Lao, Myanmar and Khmer between the words of the lists
     there (assets/word_lists), as the companions do without ICU.
     in:  one case per line: a command letter, a space, then the text as hex UTF-8 bytes ("E381AE E381AF").
          B  where a line may break (ICU when Windows has it)      -> "icu=<0|1> <byte offsets>"
          F  where a line may break by the built-in table alone    -> "<byte offsets>"
          E  fit a text to a room with "…" (the line starts with the room in decimal after the letter)
             over a model width: 'W' 10, 'i' 2, byte 0x89 12, byte 0x85 or U+2026 5, anything else 4
                                                                -> "-" when it fits, else the fitted bytes in hex
          N  the cluster composed (NFC) as the companion draws it  -> its bytes in hex, or "-" when unchanged
     out: one line per case. */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "unicode_text_tables.h"
#include "text_utf8.h"
#include "text_layout.h"

static int model_width(void *state, const unsigned char *s, int len) {
    int w = 0, i;
    (void)state;
    for (i = 0; i < len;) {
        unsigned int cp;
        int k = ut_next(s + i, s + len, &cp);
        w += cp == 'W' ? 10 : cp == 'i' ? 2 : cp == 0x89 || cp == 0x2030 ? 12 : cp == 0x85 || cp == 0x2026 ? 5 : 4;
        i += k;
    }
    return w;
}

static int hexval(int c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int main(int argc, char **argv) {
    FILE *in, *out;
    static char line[65536];
    static unsigned char text[32768], marks[32769];
    if ((argc != 3 && argc != 4) || fopen_s(&in, argv[1], "rb") != 0 || fopen_s(&out, argv[2], "wb") != 0) {
        return 2;
    }
    if (argc == 4 && MultiByteToWideChar(CP_ACP, 0, argv[3], -1, g_tl_words_dir, MAX_PATH - 2) > 0) {
        lstrcatW(g_tl_words_dir, L"\\");
    }
    while (fgets(line, sizeof line, in) != NULL) {
        int n = 0, i, hi = -1, b;
        char cmd = line[0];
        int room = 0;
        i = 1;
        if (cmd == 'E') {
            while (line[i] == ' ') ++i;
            while (line[i] >= '0' && line[i] <= '9') room = room * 10 + (line[i++] - '0');
        }
        for (; line[i]; ++i) {
            int v = hexval((unsigned char)line[i]);
            if (v < 0) continue;
            if (hi < 0) {
                hi = v;
            } else {
                text[n++] = (unsigned char)(hi * 16 + v);
                hi = -1;
            }
        }
        text[n] = 0;
        if (cmd == 'B' || cmd == 'F') {
            g_tl_icu_off = cmd == 'F';
            tl_breaks(text, n, marks);
            if (cmd == 'B') {
                fprintf(out, "icu=%d", tl_icu());
            }
            for (b = 1; b < n; ++b) {
                if (marks[b]) {
                    fprintf(out, " %d", b);
                }
            }
            fprintf(out, "\n");
        } else if (cmd == 'E') {
            unsigned char fitted[128];
            int k = tl_fit_ellipsis(text, n, room, model_width, NULL, fitted, (int)sizeof fitted);
            if (k < 0) {
                fprintf(out, "-");
            }
            for (b = 0; b < k; ++b) {
                fprintf(out, "%02X", fitted[b]);
            }
            fprintf(out, "\n");
        } else if (cmd == 'N') {
            unsigned char composed[64];
            int k = tl_compose(text, n, composed, (int)sizeof composed);
            if (k <= 0) {
                fprintf(out, "-");
            }
            for (b = 0; b < k; ++b) {
                fprintf(out, "%02X", composed[b]);
            }
            fprintf(out, "\n");
        } else {
            fprintf(out, "?\n");
        }
    }
    fclose(in);
    fclose(out);
    return 0;
}
