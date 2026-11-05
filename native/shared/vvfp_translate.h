/* vvfp_translate.h -- a companion's own text in the player's language, by key.

   The owner (2026-11-02): "FOR ALL TRANSLATIONS AND ALL GAMES PLEASE ADD THE ABILITY TO SUPPORT EVERY SINGLE
   PATCH!!!!"  A companion that builds a text itself -- a word it draws through the game's text routine, a
   line it copies into a game buffer, a message it formats -- asks "VVFP Translations.dll" for it by the row's
   stem (data/translations/patcher_strings.json: "vvfp.<part>/<id>", the key without its ~hash):

     vvfp_tr(stem, english, cap)            the translation of `english` that fits `cap` bytes with its NUL
                                            (cap 0: a text drawn from a pointer), or `english` itself;
     vvfp_trf(stem, english, text, out, cap)
                                            `text` is `english` (a format with %s %d %i %u) already filled in:
                                            its translation with the same values (plural and gender words
                                            chosen by them) in `out` when it fits, else `text`.

   The Translations companion answers only when a translation is chosen, the row's English is exactly
   `english` (the key's hash: an edited English, or another patch's text, stays English), its checks pass,
   and it fits.  Without that companion, or before it has started, every call returns the English: nothing
   changes.  Game thread only, never from DllMain.  No debug output. */
#ifndef VVFP_TRANSLATE_H
#define VVFP_TRANSLATE_H

#include <windows.h>

typedef const char *(__stdcall *vvfp_tr_key_fn)(const char *stem, const char *english, unsigned int cap);
typedef int (__stdcall *vvfp_tr_text_fn)(const char *stem, const char *english, const char *text, char *out,
                                         unsigned int cap);

static vvfp_tr_key_fn vvfp_tr_key_p;
static vvfp_tr_text_fn vvfp_tr_text_p;
static int vvfp_tr_tries;

/* The exports, found once; a few hundred tries while the companion may still be starting, then given up. */
static int vvfp_tr_bind(void) {
    HMODULE m;
    if (vvfp_tr_key_p != NULL) {
        return 1;
    }
    if (vvfp_tr_tries >= 512) {
        return 0;
    }
    ++vvfp_tr_tries;
    m = GetModuleHandleW(L"VVFP Translations.dll");
    if (m == NULL) {
        return 0;
    }
    vvfp_tr_key_p = (vvfp_tr_key_fn)(void *)GetProcAddress(m, "VvfpTranslateKey");
    vvfp_tr_text_p = (vvfp_tr_text_fn)(void *)GetProcAddress(m, "VvfpTranslateKeyText");
    if (vvfp_tr_key_p == NULL || vvfp_tr_text_p == NULL) {
        vvfp_tr_key_p = NULL;
        vvfp_tr_text_p = NULL;
        vvfp_tr_tries = 512;                 /* an older companion without them: English for good */
        return 0;
    }
    return 1;
}

static const char *vvfp_tr(const char *stem, const char *english, unsigned int cap) {
    const char *out;
    if (english == NULL || !vvfp_tr_bind()) {
        return english;
    }
    out = vvfp_tr_key_p(stem, english, cap);
    return out != NULL ? out : english;
}

static const char *vvfp_trf(const char *stem, const char *english, const char *text, char *out, unsigned int cap) {
    if (text == NULL || out == NULL || cap == 0 || !vvfp_tr_bind()) {
        return text;
    }
    return vvfp_tr_text_p(stem, english, text, out, cap) ? out : text;
}

/* Draws a (possibly translated) label with GDI.  A translation may be UTF-8 (when a Unicode companion is in)
   or Windows-1252, so the text is read the patcher's way -- valid UTF-8, else Windows-1252 -- and drawn with
   DrawTextW: never the ANSI code page, which would turn a translation into mojibake. */
static int vvfp_draw_text(HDC dc, const char *text, RECT *rc, UINT flags) {
    WCHAR wide[256];
    int n;
    if (text == NULL) {
        return 0;
    }
    n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, wide, 256);
    if (n <= 0) {
        n = MultiByteToWideChar(1252, 0, text, -1, wide, 256);
    }
    if (n <= 0) {
        wide[0] = 0;
    }
    wide[255] = 0;
    return DrawTextW(dc, wide, -1, rc, flags);
}

/* A (possibly translated) patcher text as UTF-16, read the same way (valid UTF-8, else Windows-1252); its
   length in characters. */
static int vvfp_to_wide(const char *text, WCHAR *wide, int cap) {
    int n = text != NULL ? MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, wide, cap) : 0;
    if (n <= 0 && text != NULL) {
        n = MultiByteToWideChar(1252, 0, text, -1, wide, cap);
    }
    if (n <= 0) {
        n = 1;
    }
    wide[n - 1] = 0;
    return n - 1;
}

/* MessageBoxA for a text that may hold a translation: shown as UTF-16, never in the ANSI code page. */
static int vvfp_message_box(HWND owner, const char *text, const char *caption, UINT type) {
    WCHAR wide_text[2048], wide_caption[256];
    vvfp_to_wide(text, wide_text, 2048);
    vvfp_to_wide(caption, wide_caption, 256);
    return MessageBoxW(owner, wide_text, wide_caption, type);
}

#endif
