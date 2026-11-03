/* grapheme_harness.c -- runs text_utf8.h, the in-game companions' text units, outside the game, so
   tests/test_unicode18.py can hold the DLL's own C to Unicode 18.0's GraphemeBreakTest and emoji sequences.

   grapheme_harness.exe <in> <out>
     in:  one text per line, as hex UTF-8 bytes ("F09F9180 CC88" -- spaces ignored).
     out: one line per text: the byte length of each grapheme cluster ut_grapheme finds, then "|", each
          unit's kind and length (ut_unit), then "|" the length Backspace keeps (ut_erase_last). */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "unicode_text_tables.h"
#include "text_utf8.h"

static int hexval(int c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int main(int argc, char **argv) {
    FILE *in, *out;
    static char line[65536];
    static unsigned char text[32768];
    if (argc != 3 || fopen_s(&in, argv[1], "rb") != 0 || fopen_s(&out, argv[2], "wb") != 0) {
        return 2;
    }
    while (fgets(line, sizeof line, in) != NULL) {
        int n = 0, i, hi = -1;
        const unsigned char *s, *end;
        for (i = 0; line[i]; ++i) {
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
        end = text + n;
        for (s = text; s < end;) {
            unsigned int last;
            int k = ut_grapheme(s, end, &last);
            if (k <= 0) break;
            fprintf(out, "%d ", k);
            s += k;
        }
        fprintf(out, "|");
        for (s = text; s < end;) {
            ut_unit_t u;
            ut_unit(s, end, &u);
            if (u.len <= 0) break;
            fprintf(out, " %d:%d", u.kind, u.len);
            s += u.len;
        }
        fprintf(out, " | %d\n", ut_erase_last(text, n));
    }
    fclose(in);
    fclose(out);
    return 0;
}
