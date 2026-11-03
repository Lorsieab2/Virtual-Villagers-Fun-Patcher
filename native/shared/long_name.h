/* long_name.h -- a villager's or tribe's WHOLE name, for the companions that write logs (v1.35.89).

   With "Render Unicode with In-Game Fonts" or "Use Unicode Font" a name longer than the game's field is
   saved there as a short form ending in the Windows-1252 ellipsis (0x85, or its UTF-8 E2 80 A6) and kept
   whole in the save's Long Names file (native/vvfp_unicode_text/long_names.inc).  vv_long_name(name)
   asks that companion -- "VVFP Unicode Text.dll" or "VVFP Unicode Font.dll", whichever is loaded -- for
   the whole name (its VvfpLongName export), and answers `name` itself when neither is loaded, the export
   is missing, or `name` is not a short form: it fails open, and costs nothing for a name with no
   ellipsis.  The answer is the companion's own copy: copy it before the next call.  Header-only. */
#ifndef VVFP_LONG_NAME_H
#define VVFP_LONG_NAME_H

#include <windows.h>

typedef const char *(__stdcall *vv_long_name_fn)(const char *);

static const char *vv_long_name(const char *name) {
    static vv_long_name_fn fn;
    static int tries;
    const unsigned char *p;
    int marked = 0;
    if (name == NULL) {
        return name;
    }
    for (p = (const unsigned char *)name; *p; ++p) {
        if (*p == 0x85 || (p[0] == 0xE2 && p[1] == 0x80 && p[2] == 0xA6)) {
            marked = 1;
            break;
        }
    }
    if (!marked) {
        return name;
    }
    if (fn == NULL && tries < 64) {
        HMODULE m = GetModuleHandleW(L"VVFP Unicode Text.dll");
        ++tries;
        if (m == NULL) {
            m = GetModuleHandleW(L"VVFP Unicode Font.dll");
        }
        if (m != NULL) {
            fn = (vv_long_name_fn)GetProcAddress(m, "VvfpLongName");
        }
    }
    if (fn != NULL) {
        const char *whole = fn(name);
        if (whole != NULL) {
            return whole;
        }
    }
    return name;
}

/* Copy `name`'s whole name into out (size bytes), when it fits whole; else leave out as it is (the short
   form the caller already copied: a log never holds a whole name cut in two). */
static void vv_long_name_into(char *out, size_t size) {
    const char *whole = vv_long_name(out);
    size_t n = 0;
    if (whole == out || whole == NULL) {
        return;
    }
    while (whole[n]) {
        ++n;
    }
    if (n + 1 <= size) {
        size_t i;
        for (i = 0; i <= n; ++i) {
            out[i] = whole[i];
        }
    }
}

#endif /* VVFP_LONG_NAME_H */
