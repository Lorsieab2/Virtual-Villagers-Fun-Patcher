/* New Believers' Heathen words in the Guardians of Isola wording, for the text a companion writes itself.

   The owner (2026-11-23): "with the Guardians of Isola patch Heathens = Isolans".  The owner's pairs:
       Heathen -> Isolan, Heathens -> Isolans, Heathens' -> Isolans', a Heathen -> an Isolan
   (and so heathen / heathens / A Heathen, the same word in other cases).  The people are never called
   "Guardians".  The game's own words are the rewrite's (sm.xml); this header is only for the patcher's own.

   vv5_isolan_words(in, out, cap)    `in` in the Isolan wording, in `out` (cap bytes with its NUL); 1 when a
                                     word changed.  Pure: it never asks the game, so a harness can call it.
   vv5_isolan(guardians, text)       with the rewrite on (`guardians`: the caller's own test, e.g. heathen_word.h
                                     vv5_guardians_of_isola or Story Upgrades' cg_guardians_on), `text` in the
                                     Isolan wording, in one of a few rotating buffers (read it before eight more
                                     calls); otherwise `text` itself.  New Believers only: the caller says so.

   A word is matched whole: "heathen" with no letter before it, then "s'", "s", "'s" or nothing, and no letter
   after.  The first letter keeps its case; Isolan is a name, so a lower-case "heathen" becomes "Isolan" too, as
   the rewrite writes it ("Talk to the heathen" -> "Talk to the Isolan").  "a"/"A" right before the word becomes
   "an"/"An".  Header-only and static.  No debug output. */
#ifndef VV_ISOLAN_WORDS_H
#define VV_ISOLAN_WORDS_H

#include <windows.h>

#define VV5_ISOLAN_BUFFERS 8
#define VV5_ISOLAN_ROOM 2048

static int vv5_isolan_letter(char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z');
}

static int vv5_isolan_heathen_at(const char *p) {
    static const char WORD[] = "heathen";
    int k;
    for (k = 0; k < 7; ++k) {
        char c = p[k];
        if (c >= 'A' && c <= 'Z') {
            c = (char)(c - 'A' + 'a');
        }
        if (c != WORD[k]) {
            return 0;
        }
    }
    return 1;
}

static int vv5_isolan_words(const char *in, char *out, int cap) {
    int i = 0, n = 0, changed = 0;
    if (out == NULL || cap <= 0) {
        return 0;
    }
    if (in == NULL) {
        out[0] = '\0';
        return 0;
    }
    while (in[i] != '\0') {
        if ((i == 0 || !vv5_isolan_letter(in[i - 1])) && vv5_isolan_heathen_at(in + i)) {
            int end = i + 7;
            const char *tail = "";
            int tail_len = 0;
            if (in[end] == 's' && in[end + 1] == '\'') {
                tail = "s'";
                tail_len = 2;
            } else if (in[end] == 's') {
                tail = "s";
                tail_len = 1;
            } else if (in[end] == '\'' && in[end + 1] == 's') {
                tail = "'s";
                tail_len = 2;
            }
            if (!vv5_isolan_letter(in[end + tail_len])) {
                const char *word = "Isolan";
                int k;
                /* "a Heathen" -> "an Isolan": the article just written, "a" or "A" on its own. */
                if (n >= 2 && out[n - 1] == ' ' && (out[n - 2] == 'a' || out[n - 2] == 'A')
                    && (n == 2 || !vv5_isolan_letter(out[n - 3]))) {
                    if (n + 1 >= cap) {
                        break;
                    }
                    out[n - 1] = 'n';
                    out[n++] = ' ';
                }
                for (k = 0; word[k] != '\0' && n + 1 < cap; ++k) {
                    out[n++] = word[k];
                }
                for (k = 0; k < tail_len && n + 1 < cap; ++k) {
                    out[n++] = tail[k];
                }
                i = end + tail_len;
                changed = 1;
                continue;
            }
        }
        if (n + 1 >= cap) {
            break;
        }
        out[n++] = in[i++];
    }
    out[n] = '\0';
    return changed;
}

static const char *vv5_isolan(int guardians, const char *text) {
    static char buffers[VV5_ISOLAN_BUFFERS][VV5_ISOLAN_ROOM];
    static int next;
    char *out;
    if (text == NULL || !guardians) {
        return text;
    }
    out = buffers[next];
    next = (next + 1) % VV5_ISOLAN_BUFFERS;
    return vv5_isolan_words(text, out, VV5_ISOLAN_ROOM) ? out : text;
}

#endif
