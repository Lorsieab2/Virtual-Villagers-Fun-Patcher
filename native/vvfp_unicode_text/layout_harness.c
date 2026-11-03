/* layout_harness.c -- runs text_layout.h, the in-game companions' line breaking and composition (NFC),
   outside the game, on the real Windows icu.dll, so tests/test_unicode_layout.py can hold the DLL's own C to the
   spec (docs/UNICODE_SPEC.md row 3).

   layout_harness.exe <in> <out>
     in:  one case per line: a command letter, a space, then the text as hex UTF-8 bytes ("E381AE E381AF").
          B  where a line may break (ICU when Windows has it)      -> "icu=<0|1> <byte offsets>"
          F  where a line may break by the built-in table alone    -> "<byte offsets>"
          N  the cluster composed (NFC) as the companion draws it  -> its bytes in hex, or "-" when unchanged
     out: one line per case. */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "unicode_text_tables.h"
#include "text_utf8.h"
#include "text_layout.h"

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
    if (argc != 3 || fopen_s(&in, argv[1], "rb") != 0 || fopen_s(&out, argv[2], "wb") != 0) {
        return 2;
    }
    while (fgets(line, sizeof line, in) != NULL) {
        int n = 0, i, hi = -1, b;
        char cmd = line[0];
        for (i = 1; line[i]; ++i) {
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
