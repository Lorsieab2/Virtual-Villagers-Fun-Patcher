/* VVFP Copy and Paste -- "Copy and Paste in Text Boxes", all five games.

   WHAT.  Every Virtual Villagers game has one kind of text box (the tribe or village name, the villager
   names on the Details screen, ...): a box class whose keyboard handler (CP_GAMES[].handler) takes each
   typed character, keeps it when it passes the box's filter (0x20..0xFF; digits only, and '-' first, in a
   digits box) and the box's byte limit ([box+0x28]), and adds it at the END of the text -- the box has no
   movable caret: it draws its blinking caret after the last letter, and Backspace takes the last byte.
   Nothing in the stock games copies or pastes.

   This companion adds, only while a text box has typing focus:
     Ctrl+V, Shift+Insert   paste the Windows clipboard's text (CF_UNICODETEXT) at the caret -- the end;
     Ctrl+C, Ctrl+Insert    copy the box's whole text;
     Ctrl+X                 copy the whole text, then empty the box.
   Ctrl+A is left alone: the boxes have no selection to make.

   THE KEYS.  The event pump's SDL_KEYDOWN case is detoured at its first two instructions (key_site; not
   the SDL_TEXTINPUT case VVFP Unicode Text.dll detours).  A combination above, while a box has focus, is
   handled and the pump goes on with the next event, so the key never reaches the game as a key press or a
   letter (SDL sends no text for Ctrl+letters).  Any other key, or any key while no box has focus, runs the
   two moved instructions and the stock case exactly as before.  A held key's repeats are swallowed, not
   repeated.

   THE BOX.  The focused box is the one the game itself would type into: walking the game's own keyboard
   listeners in the game's own order (stopping where the game's dispatch stops), the first whose keyboard
   handler is the text box's, that has focus and whose screen takes input -- exactly the checks the handler
   makes before it takes a character.

   PASTE.  The clipboard text is put in composed form (NFC, so e + combining acute becomes e-acute), split
   into whole characters (a letter with its combining marks, an emoji with its modifiers and joined parts,
   a flag's two halves), and each character is turned into the bytes the box stores:
     * CR, LF (and CR LF as one) and Tab become a space; every other control character and every lone
       surrogate is dropped;
     * a Unicode companion loaded ("VVFP Unicode Text.dll", else "VVFP Unicode Font.dll") and its
       VvfpGlyphsUtf8() == 1: UTF-8, handed to its VvfpBoxInsertUtf8(box, text), which inserts it as typing
       does (without that export: typed in byte by byte as below);
       loaded, VvfpGlyphsUtf8() == 0: every printable Windows-1252 character, one byte each;
       neither loaded: printable ASCII only;
       a character the game cannot show is dropped, never turned into '?';
     * a digits box keeps only digits, and '-' only as its first character.
   The bytes go in through the box's own handler, one typed character each, so the game's own filter,
   limit and change notice apply exactly as if they were typed.  Before that, the text is cut at the last
   whole character that fits the box's limit: nothing is ever cut inside a character.

   COPY.  The box's bytes are read the same way back (UTF-8, or Windows-1252 with every byte kept) and put
   on the clipboard as CF_UNICODETEXT.  An empty box copies nothing.  CUT copies, and only when the copy
   succeeded empties the box with the box's own Backspace, one byte at a time.

   SAFETY.  The clipboard is opened and closed on the game thread and never waited for: when it is busy,
   empty or not text, nothing happens.  Nothing is written but the box's text, through the box's own
   handler; a box whose length the stock code keeps elsewhere ([box+0x2F], never set by the stock code)
   is left alone.  A fault anywhere is abandoned (structured exception handling), the clipboard closed,
   and the key goes on to the stock code.  The site is installed only after its stock bytes are checked
   (native/shared/install_sites.h).  No save, record or file is ever written. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "copy_paste_tables.h"

#define CP_MAX_UNITS 4096           /* clipboard text read, in UTF-16 units */
#define CP_MAX_TEXT  0x10000        /* longest box text looked at */

#define SDLK_INSERT  0x40000049u
#define KMOD_SHIFT   0x0003u
#define KMOD_CTRL    0x00C0u
#define KMOD_ALT     0x0300u
#define KMOD_GUI     0x0C00u

enum { ACT_NONE, ACT_PASTE, ACT_COPY, ACT_CUT };
enum { MODE_ASCII, MODE_CP1252, MODE_UTF8 };

typedef struct cp_node {
    unsigned char *listener;
    unsigned int flags;
    unsigned char last;
    unsigned char pad[3];
    struct cp_node *next;
} cp_node;

/* thiscall(box; type, 0, character), ret 0xC -- called as fastcall with edx unused. */
typedef char (__fastcall *cp_handler_fn)(unsigned char *box, int unused, int type, int zero, int ch);
typedef int (__stdcall *cp_utf8_fn)(void);
/* The Unicode companions' "insert as typing does" (the limit, whole characters, the caret). */
typedef int (__stdcall *cp_insert_fn)(void *box, const char *utf8);

static const cp_game *g_game;
static unsigned int g_sym_offset, g_cmp_imm, g_back, g_cont;
static int g_installed;
static int g_clipboard_open;
static volatile LONG g_handled;     /* combinations handled so far (for the tests) */

static WCHAR g_units[CP_MAX_UNITS + 1];
static WCHAR g_norm[CP_MAX_UNITS * 3 + 1];
static unsigned char g_bytes[CP_MAX_UNITS * 4 + 1];

/* Windows-1252 0x80..0x9F (0: not a character). */
static const unsigned short CP_HIGH[32] = {
    0x20AC, 0, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021,
    0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, 0, 0x017D, 0,
    0, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014,
    0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, 0, 0x017E, 0x0178,
};

/* ---- What the game can store ---------------------------------------------------------------- */

/* The loaded Unicode companion: "VVFP Unicode Text.dll", else "VVFP Unicode Font.dll" (Use Unicode Font);
   NULL when neither is loaded. */
static HMODULE unicode_module(void) {
    HMODULE module = GetModuleHandleW(L"VVFP Unicode Text.dll");
    if (module == NULL) {
        module = GetModuleHandleW(L"VVFP Unicode Font.dll");
    }
    return module;
}

/* What the boxes store, by the loaded Unicode companion's own answer (resolved on every key, so a later
   build of it is followed without rebuilding this one); *insert gets its VvfpBoxInsertUtf8, if it has one. */
static int text_mode(cp_insert_fn *insert) {
    HMODULE module = unicode_module();
    cp_utf8_fn utf8;
    if (insert != NULL) {
        *insert = NULL;
    }
    if (module == NULL) {
        return MODE_ASCII;
    }
    utf8 = (cp_utf8_fn)GetProcAddress(module, "VvfpGlyphsUtf8");
    if (utf8 == NULL || utf8() != 1) {
        return MODE_CP1252;
    }
    if (insert != NULL) {
        *insert = (cp_insert_fn)GetProcAddress(module, "VvfpBoxInsertUtf8");
    }
    return MODE_UTF8;
}

/* The bytes of one code point in `mode`; 0 when the game cannot show it. */
static int encode(unsigned int cp, int mode, unsigned char *out) {
    int i;
    if (cp >= 0x20 && cp <= 0x7E) {
        out[0] = (unsigned char)cp;
        return 1;
    }
    if (mode == MODE_ASCII || cp < 0xA0) {
        return 0;
    }
    if (mode == MODE_CP1252) {
        if (cp <= 0xFF) {
            out[0] = (unsigned char)cp;
            return 1;
        }
        for (i = 0; i < 32; ++i) {
            if (CP_HIGH[i] == cp) {
                out[0] = (unsigned char)(0x80 + i);
                return 1;
            }
        }
        return 0;
    }
    if (cp < 0x800) {
        out[0] = (unsigned char)(0xC0 | (cp >> 6));
        out[1] = (unsigned char)(0x80 | (cp & 0x3F));
        return 2;
    }
    if (cp < 0x10000) {
        out[0] = (unsigned char)(0xE0 | (cp >> 12));
        out[1] = (unsigned char)(0x80 | ((cp >> 6) & 0x3F));
        out[2] = (unsigned char)(0x80 | (cp & 0x3F));
        return 3;
    }
    out[0] = (unsigned char)(0xF0 | (cp >> 18));
    out[1] = (unsigned char)(0x80 | ((cp >> 12) & 0x3F));
    out[2] = (unsigned char)(0x80 | ((cp >> 6) & 0x3F));
    out[3] = (unsigned char)(0x80 | (cp & 0x3F));
    return 4;
}

/* A code point that belongs to the character before it. */
static int extends(unsigned int cp) {
    return (cp >= 0x0300 && cp <= 0x036F) || (cp >= 0x0483 && cp <= 0x0489)
        || (cp >= 0x0591 && cp <= 0x05BD) || (cp >= 0x0610 && cp <= 0x061A)
        || (cp >= 0x064B && cp <= 0x065F) || (cp >= 0x0900 && cp <= 0x0903)
        || (cp >= 0x093A && cp <= 0x094F) || (cp >= 0x0E31 && cp <= 0x0E3A && cp != 0x0E32 && cp != 0x0E33)
        || (cp >= 0x0E47 && cp <= 0x0E4E) || (cp >= 0x1AB0 && cp <= 0x1AFF)
        || (cp >= 0x1DC0 && cp <= 0x1DFF) || cp == 0x200C || cp == 0x200D
        || (cp >= 0x20D0 && cp <= 0x20FF) || (cp >= 0x302A && cp <= 0x302F)
        || cp == 0x3099 || cp == 0x309A || (cp >= 0xFE00 && cp <= 0xFE0F)
        || (cp >= 0xFE20 && cp <= 0xFE2F) || (cp >= 0x1F3FB && cp <= 0x1F3FF)
        || (cp >= 0xE0020 && cp <= 0xE007F) || (cp >= 0xE0100 && cp <= 0xE01EF);
}

static int regional(unsigned int cp) {
    return cp >= 0x1F1E6 && cp <= 0x1F1FF;
}

/* The code point at units[*at] (a pair joined); 0xFFFFFFFF for a lone surrogate. */
static unsigned int next_cp(const WCHAR *units, int n, int *at) {
    unsigned int u = units[*at];
    *at += 1;
    if (u >= 0xD800 && u <= 0xDBFF) {
        if (*at < n && units[*at] >= 0xDC00 && units[*at] <= 0xDFFF) {
            u = 0x10000u + ((u - 0xD800u) << 10) + (units[*at] - 0xDC00u);
            *at += 1;
            return u;
        }
        return 0xFFFFFFFFu;
    }
    if (u >= 0xDC00 && u <= 0xDFFF) {
        return 0xFFFFFFFFu;
    }
    return u;
}

/* ---- The box ---------------------------------------------------------------------------------- */

static unsigned char *focused_box(void) {
    unsigned char *manager, *list;
    cp_node *node;
    int n;
    manager = *(unsigned char **)(UINT_PTR)g_game->manager;
    if (manager == NULL || (list = *(unsigned char **)manager) == NULL) {
        return NULL;
    }
    for (node = *(cp_node **)list, n = 0; node != NULL && n < 4096; node = node->next, ++n) {
        unsigned char *box = node->listener;
        if ((node->flags & 2u) != 0 && box != NULL) {
            const unsigned int *vtable = *(const unsigned int **)box;
            unsigned char *parent = *(unsigned char **)(box + CP_BOX_PARENT);
            if (vtable != NULL && vtable[2] == g_game->handler && box[CP_BOX_FOCUSED] != 0
                && parent != NULL && parent[8] != 0) {
                return box;
            }
        }
        if (node->last) {
            break;
        }
    }
    return NULL;
}

static int box_length(const unsigned char *box) {
    const unsigned char *text = *(const unsigned char **)(box + CP_BOX_TEXT);
    int n = 0;
    if (text == NULL) {
        return -1;
    }
    while (n < CP_MAX_TEXT && text[n] != 0) {
        ++n;
    }
    return n < CP_MAX_TEXT ? n : -1;
}

/* One typed character, through the box's own handler. */
static void type_into(unsigned char *box, int ch) {
    cp_handler_fn handler = (cp_handler_fn)(UINT_PTR)(*(const unsigned int **)box)[2];
    handler(box, 0, 5, 0, ch);
}

/* ---- The clipboard ---------------------------------------------------------------------------- */

static int clipboard_open(void) {
    if (!OpenClipboard(GetActiveWindow())) {
        return 0;
    }
    g_clipboard_open = 1;
    return 1;
}

static void clipboard_close(void) {
    if (g_clipboard_open) {
        g_clipboard_open = 0;
        CloseClipboard();
    }
}

/* The clipboard's text into g_units; its length (0: none). */
static int clipboard_read(void) {
    HANDLE data;
    const WCHAR *p;
    SIZE_T size;
    int n = 0;
    if (!IsClipboardFormatAvailable(CF_UNICODETEXT) || !clipboard_open()) {
        return 0;
    }
    data = GetClipboardData(CF_UNICODETEXT);
    if (data != NULL && (p = (const WCHAR *)GlobalLock(data)) != NULL) {
        size = GlobalSize(data) / sizeof(WCHAR);
        while ((SIZE_T)n < size && n < CP_MAX_UNITS && p[n] != 0) {
            g_units[n] = p[n];
            ++n;
        }
        GlobalUnlock(data);
    }
    clipboard_close();
    g_units[n] = 0;
    return n;
}

static int clipboard_write(const WCHAR *units, int n) {
    HGLOBAL data = GlobalAlloc(GMEM_MOVEABLE, (SIZE_T)(n + 1) * sizeof(WCHAR));
    WCHAR *p;
    int ok = 0;
    if (data == NULL) {
        return 0;
    }
    if ((p = (WCHAR *)GlobalLock(data)) == NULL) {
        GlobalFree(data);
        return 0;
    }
    CopyMemory(p, units, (SIZE_T)n * sizeof(WCHAR));
    p[n] = 0;
    GlobalUnlock(data);
    if (clipboard_open()) {
        if (EmptyClipboard() && SetClipboardData(CF_UNICODETEXT, data) != NULL) {
            ok = 1;
        }
        clipboard_close();
    }
    if (!ok) {
        GlobalFree(data);
    }
    return ok;
}

/* ---- The three actions ------------------------------------------------------------------------ */

/* The bytes one code point takes in the box once in: with the Unicode companion's VvfpBoxInsertUtf8, a
   Windows-1252 character is stored as its one byte and anything else as UTF-8 (its "read by the rule");
   otherwise the bytes we type. */
static int stored(unsigned int cp, int bytes, cp_insert_fn insert) {
    unsigned char one[4];
    return (insert != NULL && encode(cp, MODE_CP1252, one) == 1) ? 1 : bytes;
}

static void paste(unsigned char *box) {
    cp_insert_fn insert;
    int mode = text_mode(&insert);
    int n = clipboard_read();
    const WCHAR *units = g_units;
    int at = 0, made = 0, grown = 0, length, room, digits, i;
    if (n <= 0) {
        return;
    }
    i = NormalizeString(NormalizationC, g_units, n, g_norm, CP_MAX_UNITS * 3);
    if (i > 0) {
        units = g_norm;
        n = i;
    }
    length = box_length(box);
    room = *(const int *)(box + CP_BOX_LIMIT) - length;
    digits = box[CP_BOX_DIGITS] != 0;
    if (length < 0 || room <= 0) {
        return;
    }
    while (at < n) {
        unsigned char one[64];
        unsigned int cp = next_cp(units, n, &at);
        int size = 0, cost, k, joined = 0, flag;
        if (cp == 0xFFFFFFFFu) {
            continue;
        }
        if (cp == '\r' || cp == '\n' || cp == '\t' || cp == 0x2028 || cp == 0x2029) {
            if (cp == '\r' && at < n && units[at] == '\n') {
                ++at;
            }
            cp = ' ';                           /* a line break or tab: one space */
        } else if (cp < 0x20 || (cp >= 0x7F && cp < 0xA0) || cp == 0xFEFF
                   || (cp >= 0x200B && cp <= 0x200F && cp != 0x200C && cp != 0x200D)
                   || (cp >= 0x202A && cp <= 0x202E) || (cp >= 0x2060 && cp <= 0x206F)) {
            continue;                           /* a control or invisible formatting character */
        }
        /* the whole character: the code point and all that belongs to it */
        size = encode(cp, mode, one);
        cost = stored(cp, size, insert);
        flag = regional(cp);
        while (at < n) {
            int peek = at;
            unsigned int next = next_cp(units, n, &peek);
            if (next == 0xFFFFFFFFu) {
                break;
            }
            if (!(extends(next) || joined || (flag && regional(next)))) {
                break;
            }
            joined = next == 0x200D;
            flag = 0;
            at = peek;
            if (size + 4 <= (int)sizeof one) {
                k = encode(next, mode, one + size);
                size += k;
                cost += stored(next, k, insert);
            }
        }
        if (size == 0) {
            continue;                           /* nothing of it the game can show */
        }
        if (digits && !(size == 1 && ((one[0] >= '0' && one[0] <= '9') || (one[0] == '-' && length + grown == 0)))) {
            continue;                           /* the box's own filter would drop it */
        }
        if (grown + cost > room) {
            break;                              /* the box is full: cut before this character */
        }
        CopyMemory(g_bytes + made, one, (SIZE_T)size);
        made += size;
        grown += cost;
    }
    if (made == 0) {
        return;
    }
    if (insert != NULL) {
        /* the Unicode companion inserts it exactly as typing does (its limit, whole characters, caret) */
        g_bytes[made] = 0;
        insert(box, (const char *)g_bytes);
        return;
    }
    for (i = 0; i < made; ++i) {
        type_into(box, g_bytes[i]);
        if (box_length(box) != length + i + 1) {
            break;                              /* the box did not take it: stop */
        }
    }
}

static int copy(unsigned char *box) {
    const unsigned char *text = *(const unsigned char **)(box + CP_BOX_TEXT);
    int length = box_length(box), mode, i = 0, n = 0;
    if (length <= 0) {
        return 0;
    }
    mode = text_mode(NULL);
    while (i < length && n < CP_MAX_UNITS - 1) {
        unsigned int b = text[i], cp = b;
        int extra = 0, k;
        if (mode == MODE_UTF8 && b >= 0xC2 && b <= 0xF4) {
            extra = b >= 0xF0 ? 3 : b >= 0xE0 ? 2 : 1;
            cp = b & (extra == 3 ? 0x07u : extra == 2 ? 0x0Fu : 0x1Fu);
            for (k = 1; k <= extra; ++k) {
                if (i + k >= length || (text[i + k] & 0xC0) != 0x80) {
                    break;
                }
                cp = (cp << 6) | (text[i + k] & 0x3Fu);
            }
            if (k <= extra || (extra == 2 && (cp < 0x800 || (cp >= 0xD800 && cp <= 0xDFFF)))
                || (extra == 3 && (cp < 0x10000 || cp > 0x10FFFF))) {
                extra = 0;                      /* not UTF-8: the byte as Windows-1252 */
                cp = b;
            }
        }
        if (extra == 0 && b >= 0x80 && b < 0xA0 && CP_HIGH[b - 0x80] != 0) {
            cp = CP_HIGH[b - 0x80];
        }
        i += 1 + extra;
        if (cp >= 0x10000) {
            g_units[n++] = (WCHAR)(0xD800 + ((cp - 0x10000) >> 10));
            g_units[n++] = (WCHAR)(0xDC00 + ((cp - 0x10000) & 0x3FF));
        } else {
            g_units[n++] = (WCHAR)cp;
        }
    }
    return clipboard_write(g_units, n);
}

static void cut(unsigned char *box) {
    int length = box_length(box), i;
    if (!copy(box)) {
        return;
    }
    for (i = 0; i < length; ++i) {
        int before = box_length(box);
        if (before <= 0) {
            break;
        }
        type_into(box, 8);
        if (box_length(box) >= before) {
            break;                              /* Backspace did nothing: stop */
        }
    }
}

/* ---- The key ---------------------------------------------------------------------------------- */

static int key(const unsigned char *frame) {
    unsigned int sym = *(const unsigned int *)(frame + g_sym_offset);
    unsigned int mod = *(const unsigned short *)(frame + g_sym_offset + 4);
    unsigned char repeat = frame[g_sym_offset - 7];
    int action = ACT_NONE;
    unsigned char *box;
    if ((mod & (KMOD_ALT | KMOD_GUI)) != 0) {
        return 0;
    }
    if (mod & KMOD_CTRL) {
        if (sym == 'v') {
            action = ACT_PASTE;
        } else if (sym == 'c' || (sym == SDLK_INSERT && !(mod & KMOD_SHIFT))) {
            action = ACT_COPY;
        } else if (sym == 'x') {
            action = ACT_CUT;
        }
    } else if ((mod & KMOD_SHIFT) && sym == SDLK_INSERT) {
        action = ACT_PASTE;
    }
    if (action == ACT_NONE || (box = focused_box()) == NULL || box[CP_BOX_OTHER] != 0) {
        return 0;
    }
    InterlockedIncrement(&g_handled);
    if (repeat) {
        return 1;
    }
    if (action == ACT_PASTE) {
        paste(box);
    } else if (action == ACT_COPY) {
        copy(box);
    } else {
        cut(box);
    }
    return 1;
}

/* 1: the key was ours and is done (the pump goes on with the next event); 0: the stock case runs. */
int __cdecl VvfpCopyPasteKey(const unsigned char *frame) {
    int handled = 0;
    if (g_game == NULL || frame == NULL) {
        return 0;
    }
    __try {
        handled = key(frame);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        handled = 0;
    }
    if (g_clipboard_open) {
        g_clipboard_open = 0;
        CloseClipboard();
    }
    return handled;
}

__declspec(naked) static void key_hook(void) {
    __asm {
        push    eax
        push    edx
        lea     eax, [esp + 8]              /* the stack as the stock case sees it */
        push    eax
        call    VvfpCopyPasteKey
        add     esp, 4
        test    eax, eax
        pop     edx
        pop     eax
        jnz     handled
        mov     ecx, esp                    /* the two moved instructions: mov ecx, [esp + sym] */
        add     ecx, g_sym_offset
        mov     ecx, dword ptr [ecx]
        cmp     ecx, dword ptr [g_cmp_imm]  /* cmp ecx, imm32 -- the same flags */
        jmp     dword ptr [g_back]
    handled:
        jmp     dword ptr [g_cont]
    }
}

/* Combinations handled so far (for the tests' emulation). */
int __stdcall VvfpCopyPasteHandled(void) {
    return (int)g_handled;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write site;
    const cp_game *g;
    (void)shipped;
    if (g_installed || game < 1 || game > 5) {
        return;
    }
    g = &CP_GAMES[game];
    g_sym_offset = (unsigned int)g->sym;
    g_cmp_imm = g->cmp_imm;
    g_back = g->key_site + 10u;
    g_cont = g->cont;
    vvfp_site_branch(&site, g->key_site, 10, g->key_bytes, 0xE9, (const void *)key_hook);
    if (!vvfp_install_sites(&site, 1)) {
        return;
    }
    g_game = g;
    g_installed = 1;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
