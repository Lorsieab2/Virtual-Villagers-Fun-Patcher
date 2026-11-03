/* VVFP Translations -- the game's text in the player's language, all five games.

   ONE FEATURE, ONE DLL.  Started by "VVFP Startup.dll" (its second word of companions) on the game's own
   thread before WinMain, VvfpStartup reads

       <exe folder>\Virtual Villagers Fun Patcher Files\Translation\Translation.txt

   (docs/translation-file-format.md; tr_text.h is the C twin of src/vv_translation_format.py) and puts each
   row whose English is still the game's English in place of it.  No file, an unreadable one, one for
   another game, or one the format refuses: nothing is written and the game is exactly stock.

   WHERE THE TEXT IS.  Every game keeps its text in a string table:
     * A New Home and The Lost Children ("table/<id>"): {id, en, ...} rows the game's lookup (VV1 0x433880,
       VV2 0x4415A0) searches for the first row with the id.  Its en pointer is replaced.
     * The Secret City, The Tree of Life and New Believers ("sm/<eName>"): {id, name, built-in, loaded}
       entries filled by the string table's loader (VV3 0x42F4F0, VV4 0x44D750, VV5 0x450A60, each called
       from one site), whose loaded text (+0xC) wins over the built-in (+8) in the lookup and in the game's
       build_text.  The loader's call site calls a wrapper that runs the loader and then writes +0xC.
     * A literal outside the tables ("exe/0x<va>"): each instruction that pushes or loads its address
       (tr_sites.inc) gets the translation's address instead.
     * The patcher's own companions' text ("vvfp.*"): no address.  A companion that builds a text itself asks
       for it by key (VvfpTranslateKey / VvfpTranslateKeyText, native/shared/vvfp_translate.h: the row's
       stem and the English it holds; the translation only when the English is the row's and it fits the
       companion's buffer); VvfpTranslateText (the Unicode Text draw hooks) and the dialog hook match it by
       content (a dialog's text line by line when it was put together from several rows).
     * Text an exe patch wrote ("patch/0x<va>"): the live text at <va> is replaced in place when its
       translation fits the English's own bytes; a longer one is matched by content (VvfpTranslateText).
   A row is used only when the hash in its key is the hash of the live English (another patch that changed
   that text keeps its own text) and its translation passes the row checks of the format.

   SELECTS.  A gender or plural select whose subject the game can tell at the moment the text is used is
   resolved then:
     * "{name: ...}" / "{name2: ...}" in The Secret City to New Believers become the game's own build_text
       tokens {M/F} and {M/2/F};
     * "{*: ...}" in A New Home and The Lost Children: each island-event expander (thiscall(dialog; out,
       src), ret 8) is entered through a detour that copies src with the select resolved by the event
       villager's sex into a buffer of its own;
     * "{%N: ...}": the C runtime's _output is entered through a detour that, for a format of this DLL's
       own, resolves the select from the Nth argument (a number by the @code language's plural rules, a
       %s name by the living villager of that name) on a copy on its own stack.
   Any other select is resolved to its 'o' / 'other' branch when the row is prepared.

   INSTALL.  Every code write goes through the shared all-or-none writer (install_sites.h) after its stock
   bytes are checked; if it fails nothing at all is written.  Only the detours the rows need are installed.
   Table pointers are written after the code, through the same writer.  No debug output of any kind. */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"
#include "../shared/patcher_files.h"
#include "../shared/vv3_villager_table.h"
#include "../shared/vv4_villager_table.h"
#include "../shared/vv5_villager_table.h"
#include "tr_text.h"

/* The Unicode glyph companion: when it is loaded and its VvfpGlyphsUtf8() answers 1, the game draws UTF-8
   and the translations are kept in UTF-8; otherwise they are converted to Windows-1252. */
#define TR_GLYPHS_DLL L"VVFP Unicode Text.dll"
#define TR_FONT_DLL L"VVFP Unicode Font.dll"
#define TR_FONT_DLL_A "VVFP Unicode Font.dll"
#define TR_FILE_LEAF "Translation\\Translation.txt"
#define TR_MAX_FILE (4u * 1024u * 1024u)
/* The longest prepared text: the island-event sprintf buffers of A New Home and The Lost Children are
   0x2710 bytes, the format detour's copy 0x1000. */
#define TR_MAX_TEXT_BYTES 4000u
/* A translation may be up to this many times its English (or the English plus TR_GROWTH_PLUS bytes):
   a text the game copies into a buffer sized for its English must still fit. */
#define TR_GROWTH 3u
#define TR_GROWTH_PLUS 64u
/* A short English line may land in one of the games' 0x100-byte buffers (A New Home's and The Lost Children's
   event choice captions, which the expander fills without a bound, a name of up to 0x1C bytes included; the
   0xFF-byte labels): its translation stays below TR_SHORT bytes, whatever TR_GROWTH allows. */
#define TR_SHORT 224u
#define TR_FMT_STACK 0x1000
#define TR_EXP_BUF 0x4000
#define TR_INTERN_MAX (4u * 1024u * 1024u)

typedef struct {
    unsigned int literal_va;
    unsigned int site_va;
    unsigned char length;
    unsigned char operand_offset;
    unsigned char stock[8];
} tr_site;

#ifdef TR_HAVE_SITES
#include "tr_sites.inc"
#else
#include "tr_sites_placeholder.inc"
#endif

/* The trusted places where an exe patch writes visible text ("patch/0x<va>" rows), with the hash of that
   English: a translation row writes there only when its (address, hash) is listed, so a translation file
   cannot aim a row at code (the file supplies the address and the hash itself). */
typedef struct {
    unsigned int va;
    unsigned int hash;
} tr_patch_site;

#include "tr_patch_sites.inc"

/* The companions' own texts a companion asks for BY KEY only (vvfp_tr / vvfp_trf / ce_tr_printf, the rows with
   "route": "key" in data/translations/patcher_strings.json).  Such a row is found by its stem; it is never put in
   the content map, where its English ("%s of %s", "Disease") would also translate every other text of that shape
   -- another patch's, or the game's own.  Generated by scripts/build_translations_patch_sites.py. */
#include "tr_key_stems.inc"

/* ---- each game ------------------------------------------------------------------------------------ */

typedef struct {
    unsigned int va;
    unsigned int stack;         /* the stolen `sub esp, imm32` */
    unsigned int idx, base;     /* the dialog's villager index and village base */
    unsigned int choice1, choice2;   /* the dialog's 256-byte choice buffers (0: none) */
} tr_expander;

typedef struct {
    const char *title;
    unsigned int table, rows, stride, max_id;              /* VV1/VV2 */
    unsigned int sm, sm_count, loader, loader_site, singleton;   /* VV3-VV5 */
    unsigned int output;
    int output_args4;                                      /* VV4/VV5: _output_l(FILE*, fmt, locale, va) */
    unsigned int pool_global;                              /* VV1/VV2: the record array pointer */
    unsigned int rec_stride, rec_present, rec_name, rec_name_bytes, rec_sex;
    int male_value;
    unsigned int body_lo, body_hi;                         /* VV1/VV2 dialog body buffers */
    const tr_expander *expanders;
    int expander_count;
    const tr_site *sites;
    const tr_patch_site *patch_sites;
} tr_game;

static const tr_expander VV1_EXPANDERS[] = {
    { 0x427690u, 0x104u, 0x5094u, 0x50A8u, 0u, 0u },
    { 0x4184A0u, 0x108u, 0x5098u, 0x50A8u, 0x4E92u, 0x4F92u },
    { 0x42A750u, 0x104u, 0x5098u, 0x50ACu, 0u, 0u },
};
static const tr_expander VV2_EXPANDERS[] = {
    { 0x41F0F0u, 0x108u, 0x50A0u, 0x50B0u, 0x4E9Au, 0x4F9Au },
    { 0x437220u, 0x104u, 0x5098u, 0x50ACu, 0u, 0u },
};

static const tr_game GAMES[6] = {
    { 0 },
    { "Virtual Villagers - A New Home", 0x487208u, 0x275u, 0x14u, 0x280u, 0, 0, 0, 0, 0,
      0x44D9ADu, 0, 0x48B614u, 0x3D8u, 0x28u, 0x370u, 0x1Cu, 0x350u, 1, 0x74u, 0x2783u,
      VV1_EXPANDERS, 3, TR_SITES_VV1, TR_PATCH_SITES_VV1 },
    { "Virtual Villagers - The Lost Children", 0x496300u, 0x36Cu, 12u, 0x383u, 0, 0, 0, 0, 0,
      0x46AA2Du, 0, 0x499F24u, 0xE48Cu, 0x30u, 0x564u, 0x18u, 0x538u, 1, 0x7Cu, 0x278Bu,
      VV2_EXPANDERS, 2, TR_SITES_VV2, TR_PATCH_SITES_VV2 },
    { "Virtual Villagers - The Secret City", 0, 0, 0, 0, 0x4AB990u, 0x4BAu, 0x42F4F0u, 0x42F6E5u, 0x593A74u,
      0x471CFDu, 0, 0, 0x1F8Cu, 0xF10u, 0xDD4u, 0x19u, 0xDC8u, 0, 0, 0, NULL, 0, TR_SITES_VV3, TR_PATCH_SITES_VV3 },
    { "Virtual Villagers - The Tree of Life", 0, 0, 0, 0, 0x4C41F8u, 1338u, 0x44D750u, 0x44D98Au, 0x4DFF28u,
      0x477CEDu, 1, 0, 0x2E3Cu, 0x1CC4u, 0x1B9Cu, 0x19u, 0x1B90u, 0, 0, 0, NULL, 0, TR_SITES_VV4, TR_PATCH_SITES_VV4 },
    { "Virtual Villagers - New Believers", 0, 0, 0, 0, 0x4D31F0u, 1409u, 0x450A60u, 0x450C9Du, 0x525704u,
      0x4820FEu, 1, 0, 0x2F44u, 0x1CD4u, 0x1B9Cu, 0x19u, 0x1B90u, 0, 0, 0, NULL, 0, TR_SITES_VV5, TR_PATCH_SITES_VV5 },
};

static const unsigned char OUTPUT_STOCK_A[9] = { 0x55, 0x8B, 0xEC, 0x81, 0xEC, 0x54, 0x02, 0x00, 0x00 };
static const unsigned char OUTPUT_STOCK_B[8] = { 0x55, 0x8D, 0xAC, 0x24, 0x08, 0xFE, 0xFF, 0xFF };

/* ---- state ---------------------------------------------------------------------------------------- */

static int g_game;                 /* the game this process is; 0 before VvfpStartup */
static int g_active;               /* the translation is installed */
static int g_utf8;                 /* the game draws UTF-8 (the glyph companion) */
static int g_rule;                 /* the @code language's plural rule */

/* The prepared texts whose "{%N: ...}" selects the _output detour resolves: one contiguous range. */
static unsigned int g_fmt_lo, g_fmt_size;
/* Every prepared game text (the formats above included). */
static unsigned int g_text_lo, g_text_size;
static unsigned int g_output_cont;          /* _output's entry + the stolen bytes */
static unsigned int g_loader_fn;            /* the string table loader */
static unsigned int g_exp_cont[3];          /* each expander's entry + 6 */
static unsigned int g_exp_stack[3];         /* its `sub esp` immediate */
static unsigned char *g_exp_buf;            /* the expanders' resolved copy */

/* ---- memory --------------------------------------------------------------------------------------- */

typedef struct tr_chunk {
    struct tr_chunk *next;
    unsigned int size, used;
} tr_chunk;

static tr_chunk *g_scratch;        /* freed when VvfpStartup returns */
static tr_chunk *g_keep;           /* kept for the process life */
static unsigned int g_interned;    /* bytes VvfpTranslateText's results hold */

static void *tr_alloc_in(tr_chunk **list, unsigned int size) {
    tr_chunk *c = *list;
    size = (size + 7u) & ~7u;
    if (c == NULL || c->size - c->used < size) {
        unsigned int want = size + (unsigned int)sizeof(tr_chunk) + 64u;
        if (want < 0x40000u) {
            want = 0x40000u;
        }
        c = (tr_chunk *)VirtualAlloc(NULL, want, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (c == NULL) {
            return NULL;
        }
        c->next = *list;
        c->size = want;
        c->used = ((unsigned int)sizeof(tr_chunk) + 7u) & ~7u;
        *list = c;
    }
    c->used += size;
    return (unsigned char *)c + c->used - size;
}

static void tr_free_all(tr_chunk **list) {
    while (*list != NULL) {
        tr_chunk *next = (*list)->next;
        VirtualFree(*list, 0, MEM_RELEASE);
        *list = next;
    }
}

static void *tr_scratch(unsigned int size) {
    return tr_alloc_in(&g_scratch, size);
}

static void *tr_keep(unsigned int size) {
    return tr_alloc_in(&g_keep, size);
}

/* ---- the file ------------------------------------------------------------------------------------- */

/* The file's bytes (at most TR_MAX_FILE), or NULL. */
static unsigned char *tr_read_file(unsigned int *size) {
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    HANDLE file;
    LARGE_INTEGER length;
    unsigned char *data = NULL;
    DWORD got = 0, total = 0;
    if (vvfp_patcher_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, TR_FILE_LEAF) == 0) {
        return NULL;
    }
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return NULL;
    }
    if (GetFileSizeEx(file, &length) && length.HighPart == 0 && length.LowPart <= TR_MAX_FILE) {
        data = (unsigned char *)tr_scratch(length.LowPart + 4u);
        while (data != NULL && total < length.LowPart) {
            if (!ReadFile(file, data + total, length.LowPart - total, &got, NULL) || got == 0) {
                data = NULL;
                break;
            }
            total += got;
        }
    }
    CloseHandle(file);
    if (data == NULL || total != length.LowPart) {
        return NULL;
    }
    *size = total;
    return data;
}

/* decode_bytes(): the text as code points, or NULL when the format refuses the encoding. */
static tr_cp *tr_decode(const unsigned char *data, unsigned int size, int *count) {
    tr_cp *out = (tr_cp *)tr_scratch(size * 4u + 8u);
    unsigned int i = 0;
    int n = 0;
    if (out == NULL) {
        return NULL;
    }
    if (size >= 2 && ((data[0] == 0xFF && data[1] == 0xFE) || (data[0] == 0xFE && data[1] == 0xFF))) {
        int be = data[0] == 0xFE;
        i = 2;
        if ((size - i) % 2u != 0) {
            return NULL;
        }
        while (i < size) {
            unsigned int u = be ? ((unsigned int)data[i] << 8 | data[i + 1]) : ((unsigned int)data[i + 1] << 8 | data[i]);
            i += 2;
            if (u >= 0xD800u && u <= 0xDBFFu) {
                unsigned int v;
                if (i >= size) {
                    return NULL;
                }
                v = be ? ((unsigned int)data[i] << 8 | data[i + 1]) : ((unsigned int)data[i + 1] << 8 | data[i]);
                if (v < 0xDC00u || v > 0xDFFFu) {
                    return NULL;
                }
                i += 2;
                u = 0x10000u + ((u - 0xD800u) << 10) + (v - 0xDC00u);
            } else if (u >= 0xDC00u && u <= 0xDFFFu) {
                return NULL;
            }
            out[n++] = u;
        }
    } else {
        if (size >= 3 && data[0] == 0xEF && data[1] == 0xBB && data[2] == 0xBF) {
            i = 3;
        }
        while (i < size) {
            if (!tr_utf8_next(data, size, &i, &out[n])) {
                return NULL;
            }
            ++n;
        }
    }
    for (i = 0; i < (unsigned int)n; ++i) {
        if (out[i] == 0) {
            return NULL;
        }
    }
    *count = n;
    return out;
}

/* ---- rows ----------------------------------------------------------------------------------------- */

enum { TR_SRC_TABLE = 1, TR_SRC_SM, TR_SRC_EXE, TR_SRC_VVFP, TR_SRC_PATCH, TR_SRC_OTHER };

typedef struct tr_row {
    struct tr_row *next;
    int source;
    tr_span id;
    unsigned int hash;
    tr_cp *en;
    int en_n;
    tr_cp *tr;
    int tr_n;
    tr_span notes;
    tr_span key;
} tr_row;

/* _unquote() of one cell. */
static tr_span tr_unquote_span(tr_span cell, tr_cp *buffer, int *quoted) {
    *quoted = 0;
    if (cell.n >= 2 && cell.p[0] == '"' && cell.p[cell.n - 1] == '"') {
        int i, k = 0, ok = 1;
        for (i = 1; i < cell.n - 1; ++i) {
            if (cell.p[i] == '"') {
                if (i + 1 < cell.n - 1 && cell.p[i + 1] == '"') {
                    ++i;
                } else {
                    ok = 0;
                    break;
                }
            }
        }
        if (ok) {
            for (i = 1; i < cell.n - 1; ++i) {
                buffer[k++] = cell.p[i];
                if (cell.p[i] == '"') {
                    ++i;
                }
            }
            *quoted = 1;
            cell.p = buffer;
            cell.n = k;
        }
    }
    return cell;
}

/* unescape(): \n, \r, \t and \\ decoded, any other backslash kept. */
static int tr_unescape(tr_span cell, tr_cp *out) {
    int i = 0, k = 0;
    while (i < cell.n) {
        if (cell.p[i] == '\\' && i + 1 < cell.n
            && (cell.p[i + 1] == 'n' || cell.p[i + 1] == 'r' || cell.p[i + 1] == 't' || cell.p[i + 1] == '\\')) {
            out[k++] = cell.p[i + 1] == 'n' ? '\n'
                     : cell.p[i + 1] == 'r' ? '\r'
                     : cell.p[i + 1] == 't' ? '\t' : '\\';
            i += 2;
            continue;
        }
        out[k++] = cell.p[i++];
    }
    return k;
}

/* split_key(): source, id and hash, or 0. */
static int tr_split_key(tr_span key, tr_span *source, tr_span *id, unsigned int *hash) {
    int tilde = -1, slash = -1, i;
    for (i = key.n - 1; i >= 0; --i) {
        if (key.p[i] == '~') {
            tilde = i;
            break;
        }
    }
    if (tilde < 0 || key.n - tilde - 1 != 8) {
        return 0;
    }
    for (i = 0; i < tilde; ++i) {
        if (key.p[i] == '/') {
            slash = i;
            break;
        }
    }
    if (slash <= 0 || slash + 1 >= tilde) {
        return 0;
    }
    for (i = 0; i < slash; ++i) {
        tr_cp c = key.p[i];
        if (!((c >= 'a' && c <= 'z') || tr_digit(c) || c == '_' || c == '.' || c == '-')) {
            return 0;
        }
    }
    for (i = slash + 1; i < tilde; ++i) {
        tr_cp c = key.p[i];
        if (!(tr_alpha(c) || tr_digit(c) || c == '_' || c == '.' || c == '-' || c == '/')) {
            return 0;
        }
    }
    *hash = 0;
    for (i = tilde + 1; i < key.n; ++i) {
        tr_cp c = key.p[i];
        unsigned int v;
        if (tr_digit(c)) {
            v = c - '0';
        } else if (c >= 'a' && c <= 'f') {
            v = c - 'a' + 10u;
        } else {
            return 0;
        }
        *hash = (*hash << 4) | v;
    }
    source->p = key.p;
    source->n = slash;
    id->p = key.p + slash + 1;
    id->n = tilde - slash - 1;
    return 1;
}

/* ---- the row checks (Python check_row, errors only) --------------------------------------------------- */

typedef struct {
    tr_cp *strip;
    int strip_n;
    tr_piece pieces[2 * TR_MAX_SELECTS + 2];
    int npieces;
    tr_select sel[TR_MAX_SELECTS];
    tr_cp *values[TR_MAX_SELECTS];
    int nsel;
} tr_parsed;

/* parse_selects(): 1, or 0 for a malformed select. */
static int tr_parse_selects(const tr_cp *t, int n, tr_parsed *out) {
    int i, rest_n = 0;
    tr_cp *rest, *scratch;
    out->strip = (tr_cp *)tr_scratch((unsigned int)n * 4u + 8u);
    rest = (tr_cp *)tr_scratch((unsigned int)n * 4u + 8u);
    scratch = (tr_cp *)tr_scratch((unsigned int)n * 4u + 8u);
    out->nsel = 0;
    if (out->strip == NULL || rest == NULL || scratch == NULL) {
        return 0;
    }
    out->strip_n = tr_strip_braces(t, n, out->strip);
    out->npieces = tr_split_loose(out->strip, out->strip_n, out->pieces,
                                  (int)(sizeof out->pieces / sizeof out->pieces[0]));
    if (out->npieces < 0) {
        return 0;
    }
    for (i = 0; i < out->npieces; ++i) {
        const tr_piece *p = &out->pieces[i];
        if (p->select) {
            tr_cp *values;
            if (out->nsel >= TR_MAX_SELECTS) {
                return 0;
            }
            values = (tr_cp *)tr_scratch((unsigned int)(p->end - p->start) * 4u + 8u);
            if (values == NULL || !tr_parse_one(out->strip, p->start, p->end, &out->sel[out->nsel], values,
                                                scratch)) {
                return 0;
            }
            out->values[out->nsel++] = values;
        } else {
            int k;
            for (k = p->start; k < p->end; ++k) {
                rest[rest_n++] = out->strip[k];
            }
        }
    }
    for (i = 0; i < rest_n; ++i) {
        if (rest[i] == '{' && tr_loose_head(rest, rest_n, i)) {
            return 0;                       /* a select not closed with '}' */
        }
    }
    return 1;
}

/* _VAR_RE.findall over t[from, to): the names, appended to `out`; -1 when more than `cap`. */
static int tr_find_vars(const tr_cp *t, int from, int to, tr_span *out, int count, int cap) {
    int i = from;
    while (i < to) {
        if (t[i] == '{' && i + 1 < to && tr_ident_start(t[i + 1])) {
            int k = i + 2;
            while (k < to && tr_ident(t[k])) {
                ++k;
            }
            if (k < to && t[k] == '}') {
                if (count >= cap) {
                    return -1;
                }
                out[count].p = t + i + 1;
                out[count].n = k - i - 1;
                ++count;
                i = k + 1;
                continue;
            }
        }
        ++i;
    }
    return count;
}

/* named_variables(): -1 when there are too many or the text cannot be split. */
static int tr_named_vars(const tr_parsed *p, tr_span *out, int cap) {
    int i, count = 0;
    for (i = 0; i < p->npieces && count >= 0; ++i) {
        const tr_piece *piece = &p->pieces[i];
        if (!piece->select) {
            count = tr_find_vars(p->strip, piece->start, piece->end, out, count, cap);
        } else {
            int k = piece->start + 1;
            while (k < piece->end - 1 && p->strip[k] != ':') {
                ++k;
            }
            if (k < piece->end - 1) {
                count = tr_find_vars(p->strip, k + 1, piece->end - 1, out, count, cap);
            }
        }
    }
    return count;
}

static int tr_span_in(tr_span s, const tr_span *list, int n) {
    int i;
    for (i = 0; i < n; ++i) {
        if (tr_span_eq(s, list[i])) {
            return 1;
        }
    }
    return 0;
}

typedef struct {
    int type;          /* TR_SUBJ_* */
    int pct;
    tr_span name;
    int kind;
} tr_subject;

typedef struct {
    tr_subject s[TR_MAX_SUBJECTS];
    int n;
} tr_subjects;

static tr_subject *tr_subject_find(tr_subjects *list, int type, int pct, tr_span name) {
    int i;
    for (i = 0; i < list->n; ++i) {
        tr_subject *s = &list->s[i];
        if (s->type == type && (type != TR_SUBJ_PCT || s->pct == pct)
            && (type != TR_SUBJ_NAME || tr_span_eq(s->name, name))) {
            return s;
        }
    }
    return NULL;
}

/* Set (overwrite) or setdefault a subject's kind. */
static void tr_subject_put(tr_subjects *list, int type, int pct, tr_span name, int kind, int overwrite) {
    tr_subject *s = tr_subject_find(list, type, pct, name);
    if (s != NULL) {
        if (overwrite) {
            s->kind = kind;
        }
        return;
    }
    if (list->n >= TR_MAX_SUBJECTS) {
        return;
    }
    s = &list->s[list->n++];
    s->type = type;
    s->pct = pct;
    s->name = name;
    s->kind = kind;
}

static int tr_number_name(tr_span name) {
    static const char *const NUMBER_NAMES[] = {
        "count", "number", "n", "amount", "total", "award", "days", "years", "points",
    };
    tr_cp lowered[16];
    tr_span low;
    unsigned int k;
    int i;
    if (name.n > 16) {
        return 0;
    }
    for (i = 0; i < name.n; ++i) {
        lowered[i] = (name.p[i] >= 'A' && name.p[i] <= 'Z') ? name.p[i] + 32u : name.p[i];
    }
    low.p = lowered;
    low.n = name.n;
    for (k = 0; k < sizeof NUMBER_NAMES / sizeof NUMBER_NAMES[0]; ++k) {
        if (tr_span_is(low, NUMBER_NAMES[k])) {
            return 1;
        }
    }
    return 0;
}

/* subjects_from_notes(): "%1 = villager name (person; ...)", "{count} = number (number)", "* = ... (person)". */
static void tr_notes_subjects(tr_span notes, tr_subjects *out) {
    const tr_cp *t = notes.p;
    int n = notes.n, i = 0;
    while (i < n) {
        int type = 0, pct = 0, k, tries, matched = 0;
        tr_span name;
        name.p = NULL;
        name.n = 0;
        for (tries = 0; tries < 2 && !matched; ++tries) {
            int j = -1;
            if (t[i] == '%' && i + 1 < n && t[i + 1] >= '1' && t[i + 1] <= '9') {
                if (tries == 0) {
                    if (i + 2 < n && tr_digit(t[i + 2])) {
                        j = i + 3;
                        pct = (int)(t[i + 1] - '0') * 10 + (int)(t[i + 2] - '0');
                    }
                } else {
                    j = i + 2;
                    pct = (int)(t[i + 1] - '0');
                }
                type = TR_SUBJ_PCT;
            } else if (tries == 0 && t[i] == '{' && i + 1 < n && tr_ident_start(t[i + 1])) {
                k = i + 2;
                while (k < n && tr_word(t[k])) {
                    ++k;
                }
                if (k < n && t[k] == '}') {
                    j = k + 1;
                    type = TR_SUBJ_NAME;
                    name.p = t + i + 1;
                    name.n = k - i - 1;
                }
            } else if (tries == 0 && (t[i] == '*' || t[i] == '^' || t[i] == '&' || t[i] == '+' || t[i] == '=')) {
                j = i + 1;
                type = t[i] == '*' ? TR_SUBJ_STAR : -1;
            }
            if (j < 0) {
                continue;
            }
            while (j < n && tr_space(t[j])) {
                ++j;
            }
            if (j >= n || t[j] != '=') {
                continue;
            }
            ++j;
            while (j < n && tr_space(t[j])) {
                ++j;
            }
            for (k = j; k < n; ++k) {
                if (tr_starts(t, n, k, "(person") || tr_starts(t, n, k, "(number")) {
                    int kind = t[k + 1] == 'p' ? TR_KIND_PERSON : TR_KIND_NUMBER;
                    if (type > 0) {
                        tr_subject_put(out, type, pct, name, kind, 1);
                    }
                    i = k + 7;
                    matched = 1;
                    break;
                }
                if (t[k] == ';' || t[k] == '|') {
                    break;
                }
            }
        }
        if (!matched) {
            ++i;
        }
    }
}

static tr_parsed g_ptr, g_pen;      /* the translation and the English being checked */

/* A New Home's and The Lost Children's island-event codes (scripts/build_translations_inventory.py row_entry:
   EVENT_TOKENS + PIECE_TOKENS, the inventory's tokens / forbid_chars / required_tokens / selects_allowed). */
static const char TR_EVENT_CODES[] = "*^&";
static const char TR_GAME_CODES[] = "*^&+=|~@#$";
static const char TR_PIECE_CODES[] = "|~@#$";

static int tr_cp_in(tr_cp c, const char *set) {
    for (; *set; ++set) {
        if (c == (tr_cp)(unsigned char)*set) {
            return 1;
        }
    }
    return 0;
}

static int tr_has(const tr_cp *t, int n, tr_cp c) {
    int i;
    for (i = 0; i < n; ++i) {
        if (t[i] == c) {
            return 1;
        }
    }
    return 0;
}

/* No game code the English lacks: 1 when t[0..n) adds none. */
static int tr_codes_ok(const tr_row *row, const tr_cp *t, int n) {
    int i;
    for (i = 0; i < n; ++i) {
        if (tr_cp_in(t[i], TR_GAME_CODES) && !tr_has(row->en, row->en_n, t[i])) {
            return 0;
        }
    }
    return 1;
}

/* The editor's row rules for an island-event line of A New Home or The Lost Children (the English has one of
   * ^ & | ~ @ # $), applied to the parsed translation in g_ptr: no code the English lacks (outside the selects
   and in every branch), '*' kept when the English has it (outside the selects, or in every branch of one),
   and no select at all in a line with the outcome-piece codes.  Any other row: 1. */
static int tr_game_codes_ok(const tr_row *row) {
    int i, k, has_event = 0, has_piece = 0, star = 0;
    if (row->source != TR_SRC_TABLE || g_game < 1 || g_game > 2) {
        return 1;
    }
    for (i = 0; i < row->en_n; ++i) {
        has_event |= tr_cp_in(row->en[i], TR_EVENT_CODES);
        has_piece |= tr_cp_in(row->en[i], TR_PIECE_CODES);
    }
    if (!has_event && !has_piece) {
        return 1;
    }
    if (has_piece && g_ptr.nsel > 0) {
        return 0;
    }
    for (i = 0; i < g_ptr.npieces; ++i) {
        const tr_piece *p = &g_ptr.pieces[i];
        if (p->select) {
            continue;
        }
        if (!tr_codes_ok(row, g_ptr.strip + p->start, p->end - p->start)) {
            return 0;
        }
        star |= tr_has(g_ptr.strip + p->start, p->end - p->start, '*');
    }
    for (i = 0; i < g_ptr.nsel; ++i) {
        const tr_select *sel = &g_ptr.sel[i];
        int every = sel->count > 0;
        for (k = 0; k < sel->count; ++k) {
            const tr_cp *v = g_ptr.values[i] + sel->br[k].start;
            if (!tr_codes_ok(row, v, sel->br[k].len)) {
                return 0;
            }
            every &= tr_has(v, sel->br[k].len, '*');
        }
        star |= every;
    }
    if (tr_has(row->en, row->en_n, '*') && !star) {
        return 0;
    }
    return 1;
}
static tr_conv g_en_conv[TR_MAX_CONVS];
static int g_en_nconv;
static tr_subjects g_subjects;

/* check_row(): 1 when the row has no error.  Leaves the translation parsed in g_ptr, the English's
   conversions in g_en_conv and the subjects in g_subjects. */
static int tr_check_row(const tr_row *row) {
    tr_conv tr_conv_list[TR_MAX_CONVS];
    tr_span en_vars[TR_MAX_VARS], tr_vars[TR_MAX_VARS];
    int tr_nconv, n_en_vars, n_tr_vars, i;
    tr_cp *scratch = (tr_cp *)tr_scratch((unsigned int)(row->en_n > row->tr_n ? row->en_n : row->tr_n) * 4u + 8u);
    if (scratch == NULL || row->tr_n == 0) {
        return 0;
    }
    if (tr_has_email(row->tr, row->tr_n)) {
        return 0;
    }
    {
        /* The "%" rule: a '%' is a placeholder only when the line's own English has that token; in a line with a
           placeholder every other '%' is written "%%" (the text the program is handed). */
        int format = 0, escaped_n;
        tr_cp *masked = (tr_cp *)tr_scratch((unsigned int)row->tr_n * 4u + 8u);
        tr_cp *escaped = (tr_cp *)tr_scratch((unsigned int)row->tr_n * 8u + 8u);
        tr_row *mut = (tr_row *)row;
        if (masked == NULL || escaped == NULL) {
            return 0;
        }
        g_exact_conversions = row->source == TR_SRC_VVFP;
        g_en_nconv = tr_source_convs(row->en, row->en_n, g_en_conv, TR_MAX_CONVS, &format);
        if (g_en_nconv < 0) {
            return 0;
        }
        /* The patcher's own lines (vvfp.*) are filled by the companion from captured values, never by printf. */
        escaped_n = tr_escape_percent(row->tr, row->tr_n, masked, row->en, g_en_conv, g_en_nconv,
                                      format && row->source != TR_SRC_VVFP, escaped);
        if (escaped_n != row->tr_n) {
            mut->tr = escaped;
            mut->tr_n = escaped_n;
        }
        masked = (tr_cp *)tr_scratch((unsigned int)row->tr_n * 4u + 8u);
        if (masked == NULL) {
            return 0;
        }
        tr_nconv = tr_translation_tokens(row->tr, row->tr_n, masked, row->en, g_en_conv, g_en_nconv,
                                         tr_conv_list, TR_MAX_CONVS);
    }
    if (!tr_parse_selects(row->tr, row->tr_n, &g_ptr)) {
        return 0;
    }
    if (tr_nconv < 0 || tr_nconv != g_en_nconv) {
        return 0;
    }
    for (i = 0; i < tr_nconv; ++i) {
        if (!tr_same_value(&g_en_conv[i], &tr_conv_list[i])) {
            return 0;
        }
    }
    /* named variables: the same set */
    {
        int en_ok;
        tr_parsed *pe = &g_pen;
        en_ok = tr_parse_selects(row->en, row->en_n, pe);
        if (!en_ok) {
            if (pe->strip == NULL) {
                return 0;
            }
            /* _safe_selects: an English that does not parse declares no selects; its variables are still
               read from its loose pieces. */
            pe->nsel = 0;
            pe->strip_n = tr_strip_braces(row->en, row->en_n, pe->strip);
            pe->npieces = tr_split_loose(pe->strip, pe->strip_n, pe->pieces,
                                         (int)(sizeof pe->pieces / sizeof pe->pieces[0]));
            if (pe->npieces < 0) {
                return 0;
            }
        }
        n_en_vars = tr_named_vars(pe, en_vars, TR_MAX_VARS);
        n_tr_vars = tr_named_vars(&g_ptr, tr_vars, TR_MAX_VARS);
        if (n_en_vars < 0 || n_tr_vars < 0) {
            return 0;
        }
        for (i = 0; i < n_en_vars; ++i) {
            if (!tr_span_in(en_vars[i], tr_vars, n_tr_vars)) {
                return 0;
            }
        }
        for (i = 0; i < n_tr_vars; ++i) {
            if (!tr_span_in(tr_vars[i], en_vars, n_en_vars)) {
                return 0;
            }
        }
        /* infer_subjects(english), then the notes' declarations over them */
        g_subjects.n = 0;
        for (i = 0; i < g_en_nconv; ++i) {
            tr_cp spec = g_en_conv[i].spec;
            tr_span none;
            none.p = NULL;
            none.n = 0;
            tr_subject_put(&g_subjects, TR_SUBJ_PCT, i + 1, none,
                           (spec == 'd' || spec == 'i' || spec == 'o' || spec == 'u' || spec == 'x' || spec == 'X')
                               ? TR_KIND_NUMBER : (spec == 's' ? TR_KIND_PERSON : TR_KIND_NONE), 1);
        }
        {
            tr_span all[TR_MAX_VARS];
            int count = tr_find_vars(pe->strip, 0, pe->strip_n, all, 0, TR_MAX_VARS);
            if (count < 0) {
                return 0;
            }
            for (i = 0; i < count; ++i) {
                if (tr_number_name(all[i])) {
                    tr_subject_put(&g_subjects, TR_SUBJ_NAME, 0, all[i], TR_KIND_NUMBER, 1);
                } else {
                    tr_subject_put(&g_subjects, TR_SUBJ_NAME, 0, all[i], TR_KIND_PERSON, 0);
                }
            }
        }
        if (en_ok) {
            for (i = 0; i < pe->nsel; ++i) {
                tr_subject_put(&g_subjects, pe->sel[i].subject, pe->sel[i].pct, pe->sel[i].name,
                               pe->sel[i].kind, 0);
            }
        }
        tr_notes_subjects(row->notes, &g_subjects);
        /* An island-event line of A New Home or The Lost Children: '*' is the event's villager, as the
           inventory declares it (row_entry), whether or not the file kept the Notes column. */
        if (row->source == TR_SRC_TABLE && g_game >= 1 && g_game <= 2 && tr_has(row->en, row->en_n, '*')) {
            int piece = 0;
            tr_span none;
            none.p = NULL;
            none.n = 0;
            for (i = 0; i < row->en_n; ++i) {
                piece |= tr_cp_in(row->en[i], TR_PIECE_CODES);
            }
            if (!piece) {
                tr_subject_put(&g_subjects, TR_SUBJ_STAR, 0, none, TR_KIND_PERSON, 0);
            }
        }
    }
    for (i = 0; i < g_ptr.nsel; ++i) {
        const tr_select *sel = &g_ptr.sel[i];
        tr_subject *subject = tr_subject_find(&g_subjects, sel->subject, sel->pct, sel->name);
        if (sel->subject == TR_SUBJ_PCT) {
            if (sel->pct > g_en_nconv) {
                return 0;
            }
        } else if (subject == NULL) {
            return 0;
        }
        if (subject != NULL && subject->kind != TR_KIND_NONE && subject->kind != sel->kind) {
            return 0;
        }
    }
    for (i = 0; i < row->tr_n; ++i) {
        if (tr_control(row->tr[i]) && row->tr[i] != '\n' && row->tr[i] != '\r' && row->tr[i] != '\t') {
            return 0;
        }
    }
    return tr_game_codes_ok(row);
}

/* ---- preparing a translation ------------------------------------------------------------------------ */

/* A prepared text keeps a select the game resolves at run time as
     0x01, subject, branches..., 0x04
   subject: 'v' (the island-event villager) or N (1..99) for %N; each branch is its key -- 'm' 'f' 'o',
   'Z' 'O' 'T' 'F' 'M' 'X' (zero..other), "=N:" or '#' (an =N that never matches) -- then its text, the
   branches separated by 0x03.  A translation never holds a control character, so none of these can be
   text. */
#define TR_RT_OPEN 0x01
#define TR_RT_SEP 0x03
#define TR_RT_CLOSE 0x04

enum { TR_MODE_STATIC = 0, TR_MODE_RUNTIME, TR_MODE_NATIVE };

typedef struct {
    unsigned char *p;
    unsigned int n, cap;
    int utf8;
} tr_out;

static void tr_put(tr_out *o, unsigned char b) {
    if (o->n < o->cap) {
        o->p[o->n] = b;
    }
    ++o->n;
}

static void tr_put_cp(tr_out *o, tr_cp c) {
    if (o->utf8) {
        unsigned char buf[4];
        unsigned int k, m = tr_utf8_put(c, buf);
        for (k = 0; k < m; ++k) {
            tr_put(o, buf[k]);
        }
    } else {
        tr_put(o, tr_cp1252_byte(c));
    }
}

static void tr_put_cps(tr_out *o, const tr_cp *t, int n) {
    int i;
    for (i = 0; i < n; ++i) {
        tr_put_cp(o, t[i]);
    }
}

/* choose() with no value: a person's 'o' (else the first branch), a number's 'other' (else the first). */
static int tr_choose_static(const tr_select *sel) {
    int i, want = sel->kind == TR_KIND_PERSON ? TR_KEY_O : TR_KEY_OTHER;
    for (i = 0; i < sel->count; ++i) {
        if (sel->br[i].key == want) {
            return i;
        }
    }
    return 0;
}

/* choose() for a person of sex 'm' / 'f' / 'o'. */
static int tr_choose_person(const tr_select *sel, int sex) {
    int i, want = sex == 'm' ? TR_KEY_M : (sex == 'f' ? TR_KEY_F : TR_KEY_O);
    for (i = 0; i < sel->count; ++i) {
        if (sel->br[i].key == want) {
            return i;
        }
    }
    for (i = 0; i < sel->count; ++i) {
        if (sel->br[i].key == TR_KEY_O) {
            return i;
        }
    }
    return 0;
}

static int tr_branch_plain_for_native(const tr_select *sel, const tr_cp *values, int b) {
    int i;
    for (i = 0; i < sel->br[b].len; ++i) {
        tr_cp c = values[sel->br[b].start + i];
        if (c == '/' || c == '{' || c == '}' || c == TR_LBRACE_MARK || c == TR_RBRACE_MARK) {
            return 0;
        }
    }
    return 1;
}

/* The translation `p` (checked) written to `o`, each select by `modes`. */
static void tr_emit(tr_out *o, const tr_parsed *p, const int *modes) {
    int i, s = 0;
    for (i = 0; i < p->npieces; ++i) {
        const tr_piece *piece = &p->pieces[i];
        if (!piece->select) {
            tr_put_cps(o, p->strip + piece->start, piece->end - piece->start);
            continue;
        }
        {
            const tr_select *sel = &p->sel[s];
            const tr_cp *values = p->values[s];
            int mode = modes[s];
            ++s;
            if (mode == TR_MODE_NATIVE) {
                int m = tr_choose_person(sel, 'm'), f = tr_choose_person(sel, 'f');
                if (tr_branch_plain_for_native(sel, values, m) && tr_branch_plain_for_native(sel, values, f)) {
                    tr_put(o, '{');
                    tr_put_cps(o, values + sel->br[m].start, sel->br[m].len);
                    tr_put(o, '/');
                    if (sel->name.n == 5) {             /* name2 */
                        tr_put(o, '2');
                        tr_put(o, '/');
                    }
                    tr_put_cps(o, values + sel->br[f].start, sel->br[f].len);
                    tr_put(o, '}');
                    continue;
                }
                mode = TR_MODE_STATIC;
            }
            if (mode == TR_MODE_RUNTIME) {
                int b;
                tr_put(o, TR_RT_OPEN);
                tr_put(o, sel->subject == TR_SUBJ_STAR ? (unsigned char)'v' : (unsigned char)sel->pct);
                for (b = 0; b < sel->count; ++b) {
                    const tr_branch *br = &sel->br[b];
                    if (b > 0) {
                        tr_put(o, TR_RT_SEP);
                    }
                    if (br->key == TR_KEY_EXACT) {
                        if (br->exact < 0) {
                            tr_put(o, '#');
                        } else {
                            char digits[12];
                            int d = 0;
                            long v = br->exact;
                            do {
                                digits[d++] = (char)('0' + v % 10);
                                v /= 10;
                            } while (v > 0);
                            tr_put(o, '=');
                            while (d > 0) {
                                tr_put(o, (unsigned char)digits[--d]);
                            }
                            tr_put(o, ':');
                        }
                    } else {
                        tr_put(o, (unsigned char)"mfoZOTFMX"[br->key]);
                    }
                    tr_put_cps(o, values + br->start, br->len);
                }
                tr_put(o, TR_RT_CLOSE);
                continue;
            }
            {
                int b = tr_choose_static(sel);
                tr_put_cps(o, values + sel->br[b].start, sel->br[b].len);
            }
        }
    }
}

/* ---- run-time selects ------------------------------------------------------------------------------ */

typedef struct {
    int person;                        /* 1: `sex`; 0: the number */
    int known;                         /* a number: the value is known */
    int sex;                           /* 'm' / 'f' / 'o' */
    int negative;
    unsigned long long magnitude;
} tr_value;

/* One run-time select at `p` (just after TR_RT_OPEN and the subject): the chosen branch's text, and
   where the select ends. */
static const unsigned char *tr_rt_choose(const unsigned char *p, const tr_value *v, const unsigned char **text,
                                         unsigned int *len) {
    const unsigned char *b = p, *first = NULL, *fallback = NULL, *other = NULL, *exact = NULL, *category = NULL;
    unsigned int first_n = 0, fallback_n = 0, other_n = 0, exact_n = 0, category_n = 0;
    int want = 0;
    if (v->person) {
        want = v->sex == 'm' ? 'm' : (v->sex == 'f' ? 'f' : 'o');
    } else if (v->known) {
        static const char CATEGORIES[] = "ZOTFMX";
        want = CATEGORIES[tr_plural(g_rule, v->magnitude) - TR_KEY_ZERO];
    }
    for (;;) {
        int key = *b;
        const unsigned char *start;
        unsigned int n;
        int match_exact = 0;
        if (key == '=') {
            unsigned long long value = 0;
            ++b;
            while (*b >= '0' && *b <= '9') {
                value = value * 10u + (unsigned long long)(*b - '0');
                ++b;
            }
            ++b;                                       /* ':' */
            match_exact = !v->person && v->known && !v->negative && value == v->magnitude;
        } else {
            ++b;
        }
        start = b;
        while (*b != TR_RT_SEP && *b != TR_RT_CLOSE && *b != 0) {
            ++b;
        }
        n = (unsigned int)(b - start);
        if (first == NULL) {
            first = start;
            first_n = n;
        }
        if (match_exact && exact == NULL) {
            exact = start;
            exact_n = n;
        }
        if (key == want && category == NULL) {
            category = start;
            category_n = n;
        }
        if (key == 'o' && fallback == NULL) {
            fallback = start;
            fallback_n = n;
        }
        if (key == 'X' && other == NULL) {
            other = start;
            other_n = n;
        }
        if (*b != TR_RT_SEP) {
            break;
        }
        ++b;
    }
    if (*b == TR_RT_CLOSE) {
        ++b;
    }
    if (exact != NULL) {
        *text = exact;
        *len = exact_n;
    } else if (category != NULL) {
        *text = category;
        *len = category_n;
    } else if (v->person && fallback != NULL) {
        *text = fallback;
        *len = fallback_n;
    } else if (!v->person && other != NULL) {
        *text = other;
        *len = other_n;
    } else {
        *text = first;
        *len = first_n;
    }
    return b;
}

/* The person subject of an unknown value: 'o'; the number subject: 'other' (choose() with no value). */
static void tr_value_unknown(tr_value *v, int person) {
    v->person = person;
    v->known = 0;
    v->sex = 'o';
    v->negative = 0;
    v->magnitude = 0;
}

/* ---- the villagers ------------------------------------------------------------------------------- */

static unsigned int tr_records(int *count) {
    const tr_game *g = &GAMES[g_game];
    const unsigned char *image = (const unsigned char *)(UINT_PTR)0x400000u;
    unsigned int rva = 0, slots = 0;
    *count = 0;
    switch (g_game) {
    case 1:
    case 2:
        *count = 256;
        return *(const unsigned int *)(UINT_PTR)g->pool_global;
    case 3:
        vv3_villager_table(image, &rva, &slots);
        *count = (int)slots;
        return 0x400000u + rva + 0x14u;
    case 4:
        vv4_villager_table(image, &rva, &slots);
        *count = (int)slots;
        return 0x400000u + rva + 0x44u;
    case 5:
        vv5_villager_table(image, &rva, &slots);
        *count = (int)slots;
        return 0x400000u + rva + 0x48u;
    default:
        return 0;
    }
}

/* The sex of the living villager named exactly `name` (`len` bytes, the game's encoding): 'm', 'f', or 'o'
   when nobody or villagers of both sexes have that name. */
static int tr_sex_of_name(const unsigned char *name, unsigned int len) {
    const tr_game *g = &GAMES[g_game];
    int count, i, found = 0;
    unsigned int records = tr_records(&count);
    if (records == 0 || len == 0 || len >= g->rec_name_bytes) {
        return 'o';
    }
    for (i = 0; i < count; ++i) {
        const unsigned char *r = (const unsigned char *)(UINT_PTR)(records + (unsigned int)i * g->rec_stride);
        unsigned char held = r[g->rec_present];
        int sex, value;
        if (g_game == 1 ? held != 1 : held == 0) {
            continue;
        }
        if (memcmp(r + g->rec_name, name, len) != 0 || r[g->rec_name + len] != 0) {
            continue;
        }
        memcpy(&value, r + g->rec_sex, 4);
        if (g_game <= 2) {
            sex = value == 1 ? 'm' : (value == 0 ? 'f' : 'o');
        } else {
            sex = value == 0 ? 'm' : (value == 1 ? 'f' : 'o');
        }
        if (found == 0) {
            found = sex;
        } else if (found != sex) {
            return 'o';
        }
    }
    return found ? found : 'o';
}

/* ---- the C runtime's _output: "{%N: ...}" from the arguments ------------------------------------------ */

typedef struct {
    tr_cp spec;
    int wide;
    unsigned int offset;     /* the value's offset in the va_list */
} tr_arg;

/* The conversions of a prepared format (outside its run-time selects) and where each value is. */
static int tr_format_args(const unsigned char *fmt, tr_arg *args, int cap) {
    const unsigned char *p = fmt;
    unsigned int offset = 0;
    int count = 0;
    while (*p) {
        if (*p == TR_RT_OPEN) {
            while (*p && *p != TR_RT_CLOSE) {
                ++p;
            }
            if (*p) {
                ++p;
            }
            continue;
        }
        if (*p == '%') {
            tr_cp window[32];
            tr_conv c;
            int k = 0;
            while (k < 32 && p[k] && p[k] != TR_RT_OPEN) {
                window[k] = p[k];
                ++k;
            }
            if (tr_printf_at(window, k, 0, &c)) {
                if (!c.percent) {
                    offset += 4u * (unsigned int)c.stars;
                    if (count < cap) {
                        args[count].spec = c.spec;
                        args[count].wide = c.wide;
                        args[count].offset = offset;
                    }
                    ++count;
                    offset += c.wide ? 8u : 4u;
                }
                p += c.end;
                continue;
            }
        }
        ++p;
    }
    return count < cap ? count : cap;
}

static void tr_value_of_arg(const tr_arg *a, const unsigned char *va, int person, tr_value *v) {
    tr_value_unknown(v, person);
    if (person) {
        if (a->spec == 's') {
            const unsigned char *name;
            unsigned int len = 0;
            memcpy(&name, va + a->offset, 4);
            if (name != NULL) {
                while (len < 64u && name[len]) {
                    ++len;
                }
                v->sex = tr_sex_of_name(name, len);
            }
        }
        return;
    }
    if (a->spec == 'e' || a->spec == 'E' || a->spec == 'f' || a->spec == 'g' || a->spec == 'G') {
        double d;
        memcpy(&d, va + a->offset, 8);
        v->negative = d < 0;
        if (d < 0) {
            d = -d;
        }
        v->known = d < 1.8e19;
        v->magnitude = v->known ? (unsigned long long)d : 0;
        return;
    }
    if (a->spec == 's' || a->spec == 'p') {
        return;
    }
    v->known = 1;
    if (a->wide) {
        long long value;
        memcpy(&value, va + a->offset, 8);
        if ((a->spec == 'd' || a->spec == 'i') && value < 0) {
            v->negative = 1;
            v->magnitude = (unsigned long long)(-(value + 1)) + 1u;
        } else {
            v->negative = 0;
            v->magnitude = (unsigned long long)value;
        }
    } else {
        int value;
        memcpy(&value, va + a->offset, 4);
        if ((a->spec == 'd' || a->spec == 'i' || a->spec == 'c') && value < 0) {
            v->negative = 1;
            v->magnitude = (unsigned long long)(-(long long)value);
        } else {
            v->negative = 0;
            v->magnitude = (unsigned long long)(unsigned int)value;
        }
    }
}

/* Is the run-time select at `p` (its subject byte) about a person? */
static int tr_rt_is_person(const unsigned char *p) {
    int key = p[1];
    return key == 'm' || key == 'f' || key == 'o';
}

/* `fmt` (a prepared format of this DLL) with its "{%N: ...}" selects resolved, in `out` (TR_FMT_STACK). */
const unsigned char *__cdecl tr_resolve_format(unsigned char *out, const unsigned char *fmt, const unsigned char *va) {
    tr_arg args[TR_MAX_CONVS];
    int count = tr_format_args(fmt, args, TR_MAX_CONVS);
    unsigned int n = 0;
    const unsigned char *p = fmt;
    while (*p) {
        if (*p == TR_RT_OPEN && p[1]) {
            int subject = p[1];
            int person = tr_rt_is_person(p + 1);
            tr_value v;
            const unsigned char *text;
            unsigned int len, k;
            if (subject != 'v' && subject >= 1 && subject <= count) {
                tr_value_of_arg(&args[subject - 1], va, person, &v);
            } else {
                tr_value_unknown(&v, person);
            }
            p = tr_rt_choose(p + 2, &v, &text, &len);
            for (k = 0; k < len && n + 1 < TR_FMT_STACK; ++k) {
                out[n++] = text[k];
            }
            continue;
        }
        if (n + 1 < TR_FMT_STACK) {
            out[n++] = *p;
        }
        ++p;
    }
    out[n] = 0;
    return out;
}

static void tr_output_tramp_a(void);
static void tr_output_tramp_b(void);

/* A New Home, The Lost Children, The Secret City: _output(FILE*, fmt, va_list). */
static __declspec(naked) void tr_output_stub_a(void) {
    __asm {
        mov eax, [esp + 8]
        sub eax, g_fmt_lo
        cmp eax, g_fmt_size
        jb mine
        push ebp
        mov ebp, esp
        sub esp, 0x254
        jmp dword ptr [g_output_cont]
    mine:
        push ebp
        mov ebp, esp
        sub esp, TR_FMT_STACK
        test dword ptr [esp], eax
        mov eax, esp
        push dword ptr [ebp + 0x10]
        push dword ptr [ebp + 0x0C]
        push eax
        call tr_resolve_format
        add esp, 12
        push dword ptr [ebp + 0x10]
        push eax
        push dword ptr [ebp + 0x08]
        call tr_output_tramp_a
        add esp, 12
        mov esp, ebp
        pop ebp
        ret
    }
}

static __declspec(naked) void tr_output_tramp_a(void) {
    __asm {
        push ebp
        mov ebp, esp
        sub esp, 0x254
        jmp dword ptr [g_output_cont]
    }
}

/* The Tree of Life, New Believers: _output_l(FILE*, fmt, locale, va_list). */
static __declspec(naked) void tr_output_stub_b(void) {
    __asm {
        mov eax, [esp + 8]
        sub eax, g_fmt_lo
        cmp eax, g_fmt_size
        jb mine
        push ebp
        lea ebp, [esp - 0x1F8]
        jmp dword ptr [g_output_cont]
    mine:
        push ebp
        mov ebp, esp
        sub esp, TR_FMT_STACK
        test dword ptr [esp], eax
        mov eax, esp
        push dword ptr [ebp + 0x14]
        push dword ptr [ebp + 0x0C]
        push eax
        call tr_resolve_format
        add esp, 12
        push dword ptr [ebp + 0x14]
        push dword ptr [ebp + 0x10]
        push eax
        push dword ptr [ebp + 0x08]
        call tr_output_tramp_b
        add esp, 16
        mov esp, ebp
        pop ebp
        ret
    }
}

static __declspec(naked) void tr_output_tramp_b(void) {
    __asm {
        push ebp
        lea ebp, [esp - 0x1F8]
        jmp dword ptr [g_output_cont]
    }
}

/* ---- the island-event expanders (A New Home, The Lost Children): "{*: ...}" ----------------------------- */

typedef struct {
    const unsigned char *prepared;
    const unsigned char *english;
} tr_pair;

static tr_pair *g_table_pairs;      /* each table row in use: its prepared text and the English it replaced */
static int g_table_pair_count;

static const unsigned char *tr_english_of(const unsigned char *prepared) {
    int i;
    for (i = 0; i < g_table_pair_count; ++i) {
        if (g_table_pairs[i].prepared == prepared) {
            return g_table_pairs[i].english;
        }
    }
    return NULL;
}

static int tr_in_text(const void *p) {
    return (unsigned int)(UINT_PTR)p - g_text_lo < g_text_size;
}

/* How long the expander's output of `text` can be: every name token the villager's name, every pronoun
   token 64 bytes. */
static unsigned int tr_expanded_size(const unsigned char *text, unsigned int name_len) {
    unsigned int n = 0;
    for (; *text; ++text) {
        if (*text == '*') {
            n += name_len;
        } else if (*text == '^' || *text == '&' || *text == '+' || *text == '=') {
            n += 64u;
        } else {
            ++n;
        }
    }
    return n + 1u;
}

/* frame: [0..7] pushad (edi, esi, ebp, esp, ebx, edx, ecx, eax), [8] the expander's number (replaced with
   its trampoline), [9] the caller's return, [10] out, [11] src (replaced with the text to expand). */
static void tr_exp_tramp0(void);
static void tr_exp_tramp1(void);
static void tr_exp_tramp2(void);

static void __cdecl tr_expander_hit(unsigned int *frame) {
    static void (*const TRAMPS[3])(void) = { tr_exp_tramp0, tr_exp_tramp1, tr_exp_tramp2 };
    const tr_game *g = &GAMES[g_game];
    unsigned int k = frame[8];
    const tr_expander *e = &g->expanders[k];
    const unsigned char *dialog = (const unsigned char *)(UINT_PTR)frame[6];
    unsigned int out = frame[10];
    const unsigned char *src = (const unsigned char *)(UINT_PTR)frame[11];
    const unsigned char *p;
    int sex = 'o', idx, has_select = 0;
    unsigned int base, name_len = 32u, limit, n = 0;
    frame[8] = (unsigned int)(UINT_PTR)TRAMPS[k];
    if (src == NULL) {
        return;
    }
    for (p = src; *p; ++p) {
        if (*p == TR_RT_OPEN) {
            has_select = 1;
            break;
        }
    }
    if (!has_select && !tr_in_text(src)) {
        return;                                 /* the game's own text: untouched */
    }
    memcpy(&idx, dialog + e->idx, 4);
    memcpy(&base, dialog + e->base, 4);
    if (idx >= 0 && idx <= 255 && base != 0) {
        const unsigned char *r = (const unsigned char *)(UINT_PTR)(base + (unsigned int)idx * g->rec_stride);
        int value;
        memcpy(&value, r + g->rec_sex, 4);
        sex = value == 1 ? 'm' : 'f';
        name_len = 0;
        while (name_len < g->rec_name_bytes && r[g->rec_name + name_len]) {
            ++name_len;
        }
    }
    /* the out buffer's room: a choice (256 bytes), the dialog's body (0x270F), or a caller's stack buffer */
    if (e->choice1 != 0 && (out == (unsigned int)(UINT_PTR)dialog + e->choice1
                            || out == (unsigned int)(UINT_PTR)dialog + e->choice2)) {
        limit = 256u;
    } else if (out == (unsigned int)(UINT_PTR)dialog + g->body_lo || out == (unsigned int)(UINT_PTR)dialog + g->body_hi) {
        limit = 0x270Fu;
    } else {
        limit = 1000u;
    }
    p = src;
    while (*p && n + 1 < TR_EXP_BUF) {
        if (*p == TR_RT_OPEN && p[1]) {
            tr_value v;
            const unsigned char *text;
            unsigned int len, j;
            if (p[1] == 'v') {
                v.person = 1;
                v.known = 1;
                v.sex = sex;
                v.negative = 0;
                v.magnitude = 0;
            } else {
                tr_value_unknown(&v, tr_rt_is_person(p + 1));
            }
            p = tr_rt_choose(p + 2, &v, &text, &len);
            for (j = 0; j < len && n + 1 < TR_EXP_BUF; ++j) {
                g_exp_buf[n++] = text[j];
            }
            continue;
        }
        g_exp_buf[n++] = *p++;
    }
    g_exp_buf[n] = 0;
    if (tr_expanded_size(g_exp_buf, name_len) > limit) {
        const unsigned char *english = tr_english_of(src);
        if (english != NULL) {
            frame[11] = (unsigned int)(UINT_PTR)english;
            return;
        }
        /* cut the copy until it fits, at a character's start */
        while (n > 0 && tr_expanded_size(g_exp_buf, name_len) > limit) {
            --n;
            while (n > 0 && g_utf8 && (g_exp_buf[n] & 0xC0u) == 0x80u) {
                --n;
            }
            g_exp_buf[n] = 0;
        }
    }
    frame[11] = (unsigned int)(UINT_PTR)g_exp_buf;
}

static __declspec(naked) void tr_exp_common(void) {
    __asm {
        pushad
        push esp
        call tr_expander_hit
        add esp, 4
        popad
        ret                                 ; to the expander's trampoline
    }
}

#define TR_EXP_STUB(n) static __declspec(naked) void tr_exp_stub##n(void) { __asm push n __asm jmp tr_exp_common }
TR_EXP_STUB(0) TR_EXP_STUB(1) TR_EXP_STUB(2)

static __declspec(naked) void tr_exp_tramp0(void) {
    __asm {
        sub esp, dword ptr [g_exp_stack]
        jmp dword ptr [g_exp_cont]
    }
}

static __declspec(naked) void tr_exp_tramp1(void) {
    __asm {
        sub esp, dword ptr [g_exp_stack + 4]
        jmp dword ptr [g_exp_cont + 4]
    }
}

static __declspec(naked) void tr_exp_tramp2(void) {
    __asm {
        sub esp, dword ptr [g_exp_stack + 8]
        jmp dword ptr [g_exp_cont + 8]
    }
}

static void (*const TR_EXP_STUBS[3])(void) = { tr_exp_stub0, tr_exp_stub1, tr_exp_stub2 };

/* ---- the content map (VvfpTranslateText, the dialog hook) -------------------------------------------- */

#define TR_BUCKETS 4096u

typedef struct tr_entry {
    struct tr_entry *next;
    unsigned int h;
    const unsigned char *key;          /* UTF-8 */
    unsigned int klen;
    const unsigned char *utf8;         /* the translation, UTF-8 (a pattern row: with run-time selects) */
    const unsigned char *game;         /* the translation in the game's encoding (NULL for a pattern row) */
    int pattern;
    unsigned int row_hash;             /* g_keys: the hash of the row's English (its key's ~hash) */
    const unsigned char *english;      /* g_keys: the row's English, UTF-8 */
} tr_entry;

static tr_entry **g_map;               /* exact English -> translation */
static tr_entry *g_patterns;           /* the vvfp rows matched as patterns */
static tr_entry **g_interns;           /* VvfpTranslateText's pattern results: input -> result */
static tr_entry *g_sm_rows[TR_BUCKETS]; /* VV3-VV5: eName -> the prepared row (utf8 = prepared, game = map form) */
static tr_entry **g_keys;              /* "vvfp.*" and "patch/" rows by their stem ("source/id") */
static int g_have_vvfp;

static unsigned int tr_strlen(const unsigned char *p);

/* Whether a stem is one a companion asks for by key only (tr_key_stems.inc). */
static int tr_key_only(tr_span stem) {
    const char *const *s;
    for (s = TR_KEY_STEMS; *s != NULL; ++s) {
        if (tr_span_is(stem, *s)) {
            return 1;
        }
    }
    return 0;
}

static unsigned int tr_fnv(const unsigned char *p, unsigned int n) {
    unsigned int h = 2166136261u, i;
    for (i = 0; i < n; ++i) {
        h = (h ^ p[i]) * 16777619u;
    }
    return h;
}

static tr_entry *tr_lookup(tr_entry **table, const unsigned char *key, unsigned int klen) {
    unsigned int h = tr_fnv(key, klen);
    tr_entry *e;
    if (table == NULL) {
        return NULL;
    }
    for (e = table[h % TR_BUCKETS]; e != NULL; e = e->next) {
        if (e->h == h && e->klen == klen && memcmp(e->key, key, klen) == 0) {
            return e;
        }
    }
    return NULL;
}

static tr_entry *tr_insert(tr_entry **table, const unsigned char *key, unsigned int klen) {
    unsigned int h = tr_fnv(key, klen);
    tr_entry *e = (tr_entry *)tr_keep(sizeof(tr_entry));
    if (e == NULL) {
        return NULL;
    }
    memset(e, 0, sizeof *e);
    e->h = h;
    e->key = key;
    e->klen = klen;
    e->next = table[h % TR_BUCKETS];
    table[h % TR_BUCKETS] = e;
    return e;
}

static unsigned char *tr_keep_copy(const unsigned char *p, unsigned int n) {
    unsigned char *out = (unsigned char *)tr_keep(n + 1u);
    if (out != NULL) {
        memcpy(out, p, n);
        out[n] = 0;
    }
    return out;
}

/* UTF-8 (valid) to the game's encoding: kept as is, or Windows-1252 with '?'. */
static unsigned int tr_utf8_to_game(const unsigned char *in, unsigned int n, unsigned char *out) {
    unsigned int i = 0, k = 0;
    if (g_utf8) {
        memcpy(out, in, n);
        out[n] = 0;
        return n;
    }
    while (i < n) {
        tr_cp c;
        if (in[i] < 0x80u || !tr_utf8_next(in, n, &i, &c)) {
            c = in[i];
            ++i;
        }
        out[k++] = tr_cp1252_byte(c);
    }
    out[k] = 0;
    return k;
}

/* Add the English (code points) -> translation (UTF-8) to the map; the first row with an English wins. */
static void tr_map_add(const tr_cp *en, int en_n, const unsigned char *utf8, unsigned int utf8_n, int pattern) {
    tr_out key;
    unsigned char *k, *game;
    tr_entry *e;
    if (g_map == NULL) {
        return;
    }
    key.utf8 = 1;
    key.cap = (unsigned int)en_n * 4u + 1u;
    key.n = 0;
    key.p = (unsigned char *)tr_keep(key.cap);
    if (key.p == NULL) {
        return;
    }
    tr_put_cps(&key, en, en_n);
    k = key.p;
    if (tr_lookup(g_map, k, key.n) != NULL) {
        return;
    }
    e = tr_insert(g_map, k, key.n);
    if (e == NULL) {
        return;
    }
    e->utf8 = tr_keep_copy(utf8, utf8_n);
    e->pattern = pattern;
    if (!pattern) {
        game = (unsigned char *)tr_keep(utf8_n + 1u);
        if (game != NULL) {
            tr_utf8_to_game(utf8, utf8_n, game);
        }
        e->game = game;
    } else {
        /* also kept on the pattern list (the map's own copy stays for an exact match of the pattern) */
        tr_entry *pe = (tr_entry *)tr_keep(sizeof(tr_entry));
        if (pe != NULL) {
            *pe = *e;
            pe->next = g_patterns;
            g_patterns = pe;
        }
    }
}

/* A companion's row by its stem: its static form in the game's encoding, its map form (UTF-8, run-time selects
   kept for a pattern row) and its English. */
static void tr_key_add(tr_span stem, unsigned int hash, const tr_cp *en, int en_n, const unsigned char *game,
                       unsigned int game_n, const unsigned char *utf8, unsigned int utf8_n, int pattern) {
    tr_out key, eng;
    tr_entry *e;
    if (g_keys == NULL) {
        return;
    }
    key.utf8 = eng.utf8 = 1;
    key.cap = (unsigned int)stem.n * 4u + 1u;
    eng.cap = (unsigned int)en_n * 4u + 1u;
    key.n = eng.n = 0;
    key.p = (unsigned char *)tr_keep(key.cap);
    eng.p = (unsigned char *)tr_keep(eng.cap);
    if (key.p == NULL || eng.p == NULL) {
        return;
    }
    tr_put_cps(&key, stem.p, stem.n);
    tr_put_cps(&eng, en, en_n);
    eng.p[eng.n] = 0;
    if (tr_lookup(g_keys, key.p, key.n) != NULL) {
        return;                                    /* the first row with a stem wins */
    }
    e = tr_insert(g_keys, key.p, key.n);
    if (e == NULL) {
        return;
    }
    e->game = tr_keep_copy(game, game_n);
    e->utf8 = tr_keep_copy(utf8, utf8_n);
    e->pattern = pattern;
    e->row_hash = hash;
    e->english = eng.p;
}

/* ---- pattern matching (vvfp rows with %s %d %i %u) ------------------------------------------------- */

typedef struct {
    const unsigned char *p;
    unsigned int n;
} tr_capture;

static int tr_match(const unsigned char *pat, const unsigned char *t, tr_capture *caps, int k, int *budget) {
    for (;;) {
        if (--*budget < 0) {
            return 0;
        }
        if (*pat == '%') {
            unsigned char spec = pat[1];
            if (spec == '%') {
                if (*t != '%') {
                    return 0;
                }
                pat += 2;
                ++t;
                continue;
            }
            if (k >= TR_MAX_CONVS) {
                return 0;
            }
            if (spec == 's') {
                const unsigned char *e = t;
                for (;;) {
                    caps[k].p = t;
                    caps[k].n = (unsigned int)(e - t);
                    if (tr_match(pat + 2, e, caps, k + 1, budget)) {
                        return 1;
                    }
                    if (*e == 0 || *budget < 0) {
                        return 0;
                    }
                    ++e;
                }
            } else {
                const unsigned char *s = t, *e;
                if (spec != 'u' && *s == '-') {
                    ++s;
                }
                if (!(*s >= '0' && *s <= '9')) {
                    return 0;
                }
                e = s;
                while (*e >= '0' && *e <= '9') {
                    ++e;
                }
                for (; e > s; --e) {
                    caps[k].p = t;
                    caps[k].n = (unsigned int)(e - t);
                    if (tr_match(pat + 2, e, caps, k + 1, budget)) {
                        return 1;
                    }
                }
                return 0;
            }
        }
        if (*pat == 0) {
            return *t == 0;
        }
        if (*pat != *t) {
            return 0;
        }
        ++pat;
        ++t;
    }
}

/* A pattern row is one whose English's conversions are all plain %s %d %i %u. */
static int tr_pattern_english(const tr_cp *en, int en_n) {
    tr_conv c[TR_MAX_CONVS];
    int n = tr_conversions(en, en_n, c, TR_MAX_CONVS), i;
    if (n <= 0) {
        return 0;
    }
    for (i = 0; i < n; ++i) {
        if (c[i].end - c[i].start != 2 || !(c[i].spec == 's' || c[i].spec == 'd' || c[i].spec == 'i'
                                            || c[i].spec == 'u')) {
            return 0;
        }
    }
    return 1;
}

static void tr_value_of_capture(const tr_capture *c, int person, tr_value *v) {
    tr_value_unknown(v, person);
    if (person) {
        unsigned char name[64];
        unsigned int n = tr_utf8_to_game(c->p, c->n < 60u ? c->n : 60u, name);
        v->sex = tr_sex_of_name(name, n);
        return;
    }
    {
        unsigned int i = 0;
        unsigned long long m = 0;
        int digits = 0;
        v->negative = 0;
        if (i < c->n && c->p[i] == '-') {
            v->negative = 1;
            ++i;
        }
        for (; i < c->n && c->p[i] >= '0' && c->p[i] <= '9'; ++i) {
            m = m * 10u + (unsigned long long)(c->p[i] - '0');
            ++digits;
        }
        v->magnitude = m;
        v->known = digits > 0;
        if (v->negative && m == 0) {
            v->negative = 0;
        }
    }
}

/* The translation of a pattern row with the captured values, UTF-8, in `out` (`cap` bytes). */
static unsigned int tr_fill_pattern(const unsigned char *tr, const tr_capture *caps, int ncaps,
                                    unsigned char *out, unsigned int cap) {
    unsigned int n = 0;
    int conv = 0;
    const unsigned char *p = tr;
    while (*p && n + 1 < cap) {
        if (*p == TR_RT_OPEN && p[1]) {
            int subject = p[1];
            int person = tr_rt_is_person(p + 1);
            tr_value v;
            const unsigned char *text;
            unsigned int len, k;
            if (subject != 'v' && subject >= 1 && subject <= ncaps) {
                tr_value_of_capture(&caps[subject - 1], person, &v);
            } else {
                tr_value_unknown(&v, person);
            }
            p = tr_rt_choose(p + 2, &v, &text, &len);
            for (k = 0; k < len && n + 1 < cap; ++k) {
                out[n++] = text[k];
            }
            continue;
        }
        if (*p == '%' && p[1] == '%') {
            out[n++] = '%';
            p += 2;
            continue;
        }
        if (*p == '%' && (p[1] == 's' || p[1] == 'd' || p[1] == 'i' || p[1] == 'u')) {
            if (conv < ncaps) {
                unsigned int k;
                for (k = 0; k < caps[conv].n && n + 1 < cap; ++k) {
                    out[n++] = caps[conv].p[k];
                }
            }
            ++conv;
            p += 2;
            continue;
        }
        out[n++] = *p++;
    }
    out[n] = 0;
    return n;
}

/* Is `p` valid UTF-8 (n bytes)? */
static int tr_valid_utf8(const unsigned char *p, unsigned int n) {
    unsigned int i = 0;
    tr_cp c;
    while (i < n) {
        if (!tr_utf8_next(p, n, &i, &c)) {
            return 0;
        }
    }
    return 1;
}

/* The translation of `text` (UTF-8, n bytes), UTF-8, in `out`: 1 when one was found. */
static int tr_translate_utf8(const unsigned char *text, unsigned int n, unsigned char *out, unsigned int cap,
                             const tr_entry **exact) {
    tr_entry *e = tr_lookup(g_map, text, n);
    tr_capture caps[TR_MAX_CONVS];
    *exact = NULL;
    if (e != NULL && !e->pattern) {
        *exact = e;
        return 1;
    }
    {
        /* Every pattern that matches is tried and the MOST SPECIFIC one -- the most literal bytes around its
           conversions -- is used: "Each villager the game checks: %s." also matches the longer text of
           "Each villager the game checks: %s. If none ...", which must keep its own row. */
        const tr_entry *best = NULL;
        tr_capture best_caps[TR_MAX_CONVS];
        int best_n = 0;
        unsigned int best_literal = 0;
        for (e = g_patterns; e != NULL; e = e->next) {
            int budget = 20000;
            if (e->key[0] != '%' && e->key[0] != text[0]) {
                continue;
            }
            if (tr_match(e->key, text, caps, 0, &budget)) {
                int ncaps = 0;
                unsigned int literal = 0;
                const unsigned char *k;
                for (k = e->key; *k; ++k) {
                    if (*k == '%' && k[1] == '%') {
                        ++k;
                        ++literal;
                    } else if (*k == '%') {
                        ++ncaps;
                        ++k;
                    } else {
                        ++literal;
                    }
                }
                if (best == NULL || literal > best_literal || (literal == best_literal && ncaps < best_n)) {
                    best = e;
                    best_n = ncaps;
                    best_literal = literal;
                    memcpy(best_caps, caps, sizeof best_caps);
                }
            }
        }
        if (best != NULL) {
            tr_fill_pattern(best->utf8, best_caps, best_n, out, cap);
            return 1;
        }
    }
    return 0;
}

/* ---- the dialog hook (the companions' Win32 dialogs) ------------------------------------------------- */

static HHOOK g_hook;
static int g_in_hook;

#define TR_WIN_TEXT 2048

/* UTF-16 to UTF-8 (unpaired surrogates as U+FFFD). */
static unsigned int tr_wide_to_utf8(const wchar_t *w, int wn, unsigned char *out, unsigned int cap) {
    int i;
    unsigned int n = 0;
    for (i = 0; i < wn; ++i) {
        tr_cp c = w[i];
        unsigned char buf[4];
        unsigned int k, m;
        if (c >= 0xD800u && c <= 0xDBFFu && i + 1 < wn && w[i + 1] >= 0xDC00u && w[i + 1] <= 0xDFFFu) {
            c = 0x10000u + ((c - 0xD800u) << 10) + ((tr_cp)w[i + 1] - 0xDC00u);
            ++i;
        } else if (c >= 0xD800u && c <= 0xDFFFu) {
            c = 0xFFFDu;
        }
        m = tr_utf8_put(c, buf);
        if (n + m + 1 > cap) {
            break;
        }
        for (k = 0; k < m; ++k) {
            out[n++] = buf[k];
        }
    }
    out[n] = 0;
    return n;
}

static int tr_utf8_to_wide(const unsigned char *in, wchar_t *out, int cap) {
    unsigned int i = 0, n = 0;
    int k = 0;
    while (in[n]) {
        ++n;
    }
    while (i < n && k + 2 < cap) {
        tr_cp c;
        if (!tr_utf8_next(in, n, &i, &c)) {
            c = 0xFFFDu;
            ++i;
        }
        if (c >= 0x10000u) {
            c -= 0x10000u;
            out[k++] = (wchar_t)(0xD800u + (c >> 10));
            out[k++] = (wchar_t)(0xDC00u + (c & 0x3FFu));
        } else {
            out[k++] = (wchar_t)c;
        }
    }
    out[k] = 0;
    return k;
}

/* A text put together from several rows (a companion's message built line by line): each longest run of whole
   lines that is a row is translated, every other line kept.  1 when any run was. */
static int tr_translate_lines(const unsigned char *text, unsigned int n, unsigned char *out, unsigned int cap) {
    unsigned int starts[64], ends[64], count = 0, i = 0, o = 0, line;
    unsigned char piece[TR_WIN_TEXT * 3], result[TR_WIN_TEXT * 3];
    int any = 0;
    while (i <= n && count < 64) {
        unsigned int e = i;
        while (e < n && text[e] != '\n') {
            ++e;
        }
        starts[count] = i;
        ends[count] = e;
        ++count;
        i = e + 1;
    }
    if (count < 2 || i <= n) {
        return 0;                                  /* one line (already tried whole) or too many */
    }
    for (line = 0; line < count;) {
        unsigned int last, best = 0, best_n = 0;
        const unsigned char *best_text = NULL;
        for (last = count; last > line; --last) {
            unsigned int from = starts[line], to = ends[last - 1], k = to - from;
            const tr_entry *exact;
            /* a line's own \r stays outside the match */
            if (k > 0 && text[to - 1] == '\r') {
                --k;
            }
            if (k == 0 || k >= sizeof piece) {
                continue;
            }
            memcpy(piece, text + from, k);
            piece[k] = 0;
            if (tr_translate_utf8(piece, k, result, sizeof result, &exact)) {
                best_text = exact != NULL ? exact->utf8 : result;
                best_n = tr_strlen(best_text);
                best = last;
                break;
            }
        }
        if (best_text != NULL) {
            unsigned int to = ends[best - 1];
            if (o + best_n + 2 >= cap) {
                return 0;
            }
            memcpy(out + o, best_text, best_n);
            o += best_n;
            if (to > starts[line] && text[to - 1] == '\r') {
                out[o++] = '\r';
            }
            any = 1;
            line = best;
        } else {
            unsigned int k = ends[line] - starts[line];
            if (o + k + 2 >= cap) {
                return 0;
            }
            memcpy(out + o, text + starts[line], k);
            o += k;
            ++line;
        }
        if (line < count) {
            out[o++] = '\n';
        }
    }
    out[o] = 0;
    return any;
}

/* The translation of a window text (UTF-16), or 0. */
static int tr_translate_wide(const wchar_t *w, int wn, wchar_t *out, int cap) {
    unsigned char text[TR_WIN_TEXT * 3], result[TR_WIN_TEXT * 3];
    const tr_entry *exact;
    unsigned int n = tr_wide_to_utf8(w, wn, text, sizeof text);
    if (n == 0) {
        return 0;
    }
    if (tr_translate_utf8(text, n, result, sizeof result, &exact)) {
        tr_utf8_to_wide(exact != NULL ? exact->utf8 : result, out, cap);
        return 1;
    }
    if (tr_translate_lines(text, n, result, sizeof result)) {
        tr_utf8_to_wide(result, out, cap);
        return 1;
    }
    return 0;
}

static int tr_class_is(HWND hwnd, const wchar_t *name) {
    wchar_t cls[64];
    int n = GetClassNameW(hwnd, cls, 64), i;
    for (i = 0; name[i]; ++i) {
        wchar_t a = i < n ? cls[i] : 0, b = name[i];
        if (a >= 'A' && a <= 'Z') {
            a = (wchar_t)(a + 32);
        }
        if (b >= 'A' && b <= 'Z') {
            b = (wchar_t)(b + 32);
        }
        if (a != b) {
            return 0;
        }
    }
    return i == n;
}

/* A window whose text is a label: the dialog itself, a static or a button.  Never an edit (its text is
   the player's), a list or a combo box. */
static int tr_label_window(HWND hwnd) {
    return tr_class_is(hwnd, L"#32770") || tr_class_is(hwnd, L"Static") || tr_class_is(hwnd, L"Button");
}

static void tr_translate_window(HWND hwnd) {
    wchar_t text[TR_WIN_TEXT], out[TR_WIN_TEXT];
    int n;
    if (!tr_label_window(hwnd)) {
        return;
    }
    n = GetWindowTextW(hwnd, text, TR_WIN_TEXT);
    if (n <= 0 || n >= TR_WIN_TEXT - 1) {
        return;
    }
    if (tr_translate_wide(text, n, out, TR_WIN_TEXT)) {
        SetWindowTextW(hwnd, out);
    }
}

static BOOL CALLBACK tr_child(HWND hwnd, LPARAM unused) {
    (void)unused;
    tr_translate_window(hwnd);
    return TRUE;
}

/* A list or combo box item just added: replaced in place (same index, same item data, same selection)
   when the box keeps its own strings and does not sort them. */
static void tr_translate_item(HWND hwnd, int combo, int index) {
    wchar_t text[TR_WIN_TEXT], out[TR_WIN_TEXT];
    LONG style = GetWindowLongW(hwnd, GWL_STYLE);
    LRESULT len, data, at;
    int selected;
    if (index < 0) {
        return;
    }
    if (combo) {
        if ((style & CBS_SORT) || ((style & (CBS_OWNERDRAWFIXED | CBS_OWNERDRAWVARIABLE)) && !(style & CBS_HASSTRINGS))) {
            return;
        }
        len = SendMessageW(hwnd, CB_GETLBTEXTLEN, (WPARAM)index, 0);
    } else {
        if ((style & LBS_SORT) || ((style & (LBS_OWNERDRAWFIXED | LBS_OWNERDRAWVARIABLE)) && !(style & LBS_HASSTRINGS))) {
            return;
        }
        len = SendMessageW(hwnd, LB_GETTEXTLEN, (WPARAM)index, 0);
    }
    if (len <= 0 || len >= TR_WIN_TEXT - 1) {
        return;
    }
    SendMessageW(hwnd, combo ? CB_GETLBTEXT : LB_GETTEXT, (WPARAM)index, (LPARAM)text);
    text[len] = 0;
    if (!tr_translate_wide(text, (int)len, out, TR_WIN_TEXT)) {
        return;
    }
    if (combo) {
        data = SendMessageW(hwnd, CB_GETITEMDATA, (WPARAM)index, 0);
        selected = SendMessageW(hwnd, CB_GETCURSEL, 0, 0) == index;
        SendMessageW(hwnd, CB_DELETESTRING, (WPARAM)index, 0);
        at = SendMessageW(hwnd, CB_INSERTSTRING, (WPARAM)index, (LPARAM)out);
        if (at >= 0) {
            SendMessageW(hwnd, CB_SETITEMDATA, (WPARAM)at, data);
            if (selected) {
                SendMessageW(hwnd, CB_SETCURSEL, (WPARAM)at, 0);
            }
        }
    } else {
        data = SendMessageW(hwnd, LB_GETITEMDATA, (WPARAM)index, 0);
        selected = SendMessageW(hwnd, LB_GETSEL, (WPARAM)index, 0) > 0;
        SendMessageW(hwnd, LB_DELETESTRING, (WPARAM)index, 0);
        at = SendMessageW(hwnd, LB_INSERTSTRING, (WPARAM)index, (LPARAM)out);
        if (at >= 0) {
            SendMessageW(hwnd, LB_SETITEMDATA, (WPARAM)at, data);
            if (selected) {
                if (style & (LBS_MULTIPLESEL | LBS_EXTENDEDSEL)) {
                    SendMessageW(hwnd, LB_SETSEL, TRUE, at);
                } else {
                    SendMessageW(hwnd, LB_SETCURSEL, (WPARAM)at, 0);
                }
            }
        }
    }
}

static LRESULT CALLBACK tr_window_hook(int code, WPARAM wparam, LPARAM lparam) {
    if (code == HC_ACTION && !g_in_hook && lparam != 0) {
        const CWPRETSTRUCT *m = (const CWPRETSTRUCT *)lparam;
        g_in_hook = 1;
        switch (m->message) {
        case WM_INITDIALOG:
            tr_translate_window(m->hwnd);
            EnumChildWindows(m->hwnd, tr_child, 0);
            break;
        case WM_SETTEXT:
            tr_translate_window(m->hwnd);
            break;
        case LB_ADDSTRING:
        case LB_INSERTSTRING:
            if (tr_class_is(m->hwnd, L"ListBox")) {
                tr_translate_item(m->hwnd, 0, (int)m->lResult);
            }
            break;
        case CB_ADDSTRING:
        case CB_INSERTSTRING:
            if (tr_class_is(m->hwnd, L"ComboBox")) {
                tr_translate_item(m->hwnd, 1, (int)m->lResult);
            }
            break;
        default:
            break;
        }
        g_in_hook = 0;
    }
    return CallNextHookEx(g_hook, code, wparam, lparam);
}

/* ---- the string table loader (The Secret City, The Tree of Life, New Believers) -------------------------- */

typedef struct {
    const unsigned char *prepared;     /* the game's text */
    const unsigned char *map_utf8;     /* the translation for the content map, UTF-8 */
    unsigned int map_n;
    unsigned int hash;
} tr_sm_row;

static void __cdecl tr_after_loader(void) {
    const tr_game *g = &GAMES[g_game];
    unsigned int i;
    for (i = 0; i < g->sm_count; ++i) {
        unsigned int *entry = (unsigned int *)(UINT_PTR)(g->sm + i * 16u);
        const unsigned char *name = (const unsigned char *)(UINT_PTR)entry[1];
        const unsigned char *live = (const unsigned char *)(UINT_PTR)(entry[3] != 0 ? entry[3] : entry[2]);
        unsigned int n = 0, live_n = 0, prep_n = 0;
        tr_entry *e;
        const tr_sm_row *row;
        if (name == NULL || live == NULL) {
            continue;
        }
        while (name[n] && n < 200u) {
            ++n;
        }
        /* Two of the games' own names end in tabs ("eSayApprentice\t"); a key spells them without
           (src/vv_translations.py game_english). */
        while (n > 0u && (name[n - 1u] == '\t' || name[n - 1u] == ' ')) {
            --n;
        }
        e = tr_lookup(g_sm_rows, name, n);
        if (e == NULL) {
            continue;
        }
        row = (const tr_sm_row *)e->utf8;
        if (tr_hash_cp1252(live) != row->hash) {
            continue;                       /* another text than the row's English (another patch's) */
        }
        while (live[live_n]) {
            ++live_n;
        }
        while (row->prepared[prep_n]) {
            ++prep_n;
        }
        if ((prep_n > TR_GROWTH * live_n && prep_n > live_n + TR_GROWTH_PLUS)
            || (live_n < TR_SHORT && prep_n >= TR_SHORT)) {
            continue;
        }
        {
            tr_cp *en = (tr_cp *)tr_keep(live_n * 4u + 4u);
            unsigned int k;
            if (en != NULL) {
                for (k = 0; k < live_n; ++k) {
                    en[k] = tr_cp1252_char(live[k]);
                }
                tr_map_add(en, (int)live_n, row->map_utf8, row->map_n, 0);
            }
        }
        entry[3] = (unsigned int)(UINT_PTR)row->prepared;
    }
}

static __declspec(naked) void tr_loader_wrap(void) {
    __asm {
        call dword ptr [g_loader_fn]
        pushad
        call tr_after_loader
        popad
        ret
    }
}

/* ---- startup -------------------------------------------------------------------------------------- */

static int tr_readable(const void *p, unsigned int n) {
    MEMORY_BASIC_INFORMATION info;
    if (p == NULL || VirtualQuery(p, &info, sizeof info) != sizeof info || info.State != MEM_COMMIT
        || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) != 0) {
        return 0;
    }
    return (UINT_PTR)p + n <= (UINT_PTR)info.BaseAddress + info.RegionSize;
}

/* The game's text at `va` (NUL within 64 KB of readable memory), or NULL. */
static const unsigned char *tr_live_text(unsigned int va) {
    const unsigned char *p = (const unsigned char *)(UINT_PTR)va;
    unsigned int n = 0;
    if (!tr_readable(p, 1)) {
        return NULL;
    }
    while (n < 0x10000u) {
        if (((UINT_PTR)(p + n) & 0xFFFu) == 0 && !tr_readable(p + n, 1)) {
            return NULL;
        }
        if (p[n] == 0) {
            return p;
        }
        ++n;
    }
    return NULL;
}

static int tr_title_matches(tr_span value, const char *title) {
    int i;
    for (i = 0; title[i]; ++i) {
        tr_cp a, b = (tr_cp)(unsigned char)title[i];
        if (i >= value.n) {
            return 0;
        }
        a = value.p[i];
        if (a >= 'A' && a <= 'Z') {
            a += 32u;
        }
        if (b >= 'A' && b <= 'Z') {
            b += 32u;
        }
        if (a != b) {
            return 0;
        }
    }
    return i == value.n;
}

typedef struct {
    tr_span english, value;
    int seen;
} tr_info;

enum { TR_INFO_FORMAT = 0, TR_INFO_GAME, TR_INFO_LANGUAGE, TR_INFO_CODE, TR_INFO_TRANSLATOR, TR_INFO_COUNT };

/* check_info() and the file-level email rule of validate(): 1 when the file may be used. */
static int tr_info_ok(tr_info *info, const char *title) {
    tr_span language = tr_strip(info[TR_INFO_LANGUAGE].value);
    tr_span code = tr_strip(info[TR_INFO_CODE].value);
    tr_span game = tr_strip(info[TR_INFO_GAME].english);
    tr_span fmt = tr_strip(info[TR_INFO_FORMAT].value);
    tr_span credit = tr_strip(info[TR_INFO_TRANSLATOR].value);
    int i, k;
    if (fmt.n == 0) {
        fmt = tr_strip(info[TR_INFO_FORMAT].english);
    }
    if (fmt.n > 0) {
        unsigned long major = 0;
        for (i = 0; i < fmt.n && fmt.p[i] != '.'; ++i) {
            if (!tr_digit(fmt.p[i])) {
                return 0;
            }
            major = major * 10u + (fmt.p[i] - '0');
            if (major > 1000u) {
                return 0;
            }
        }
        if (i == 0 || major > 1u) {
            return 0;
        }
    }
    for (k = 0; k < TR_INFO_COUNT; ++k) {
        if (tr_has_email(info[k].english.p, info[k].english.n) || tr_has_email(info[k].value.p, info[k].value.n)) {
            return 0;
        }
    }
    if (language.n == 0) {
        return 0;
    }
    /* [A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})* */
    for (i = 0; i < code.n && tr_alpha(code.p[i]); ++i) {
    }
    if (i < 2 || i > 3) {
        return 0;
    }
    while (i < code.n) {
        int j;
        if (code.p[i] != '-') {
            return 0;
        }
        for (j = i + 1; j < code.n && (tr_alpha(code.p[j]) || tr_digit(code.p[j])); ++j) {
        }
        if (j - i - 1 < 2 || j - i - 1 > 8) {
            return 0;
        }
        i = j;
    }
    if (credit.n > 80) {
        return 0;
    }
    if (!tr_title_matches(game, title)) {
        return 0;
    }
    g_rule = tr_plural_rule(code);
    return 1;
}

/* The glyph companion keeps UTF-8 when it is loaded and says so.  "VVFP Unicode Text.dll" starts before
   this companion.  "VVFP Unicode Font.dll" (Use Unicode Font, the same code drawing in a Windows typeface)
   is later in VVFP Startup.dll's list (append-only), so when it is shipped beside this one and not yet
   loaded it is loaded by its full path in the patcher's folder and started here, when the translations
   are first prepared; its VvfpStartup installs once (VVFP Startup.dll's own call later does nothing). */
static int tr_glyphs_utf8(int game) {
    typedef int(__stdcall * glyphs_fn)(void);
    typedef void(__stdcall * start_fn)(int, unsigned int);
    HMODULE glyphs = GetModuleHandleW(TR_GLYPHS_DLL);
    glyphs_fn fn;
    if (glyphs == NULL) {
        glyphs = GetModuleHandleW(TR_FONT_DLL);
    }
    if (glyphs == NULL && vvfp_patcher_file_exists(TR_FONT_DLL_A)) {
        glyphs = vvfp_load_patcher_dll(TR_FONT_DLL_A);
        if (glyphs != NULL) {
            start_fn start = (start_fn)GetProcAddress(glyphs, "VvfpStartup");
            if (start != NULL) {
                start(game, 0);
            }
        }
    }
    if (glyphs == NULL) {
        return 0;
    }
    fn = (glyphs_fn)GetProcAddress(glyphs, "VvfpGlyphsUtf8");
    return fn != NULL && fn() == 1;
}

static int tr_span_ascii(tr_span s, char *out, int cap) {
    int i;
    if (s.n >= cap) {
        return 0;
    }
    for (i = 0; i < s.n; ++i) {
        if (s.p[i] >= 0x80u) {
            return 0;
        }
        out[i] = (char)s.p[i];
    }
    out[i] = 0;
    return 1;
}

/* A prepared game text, waiting for its address. */
typedef struct tr_prep {
    struct tr_prep *next;
    int source;
    unsigned int at;                   /* a table row's address / an exe literal's address */
    const unsigned char *live;         /* the English it replaces (table, exe) */
    unsigned char *bytes;
    unsigned int n;
    int fmt;                           /* holds a "{%N: ...}" run-time select */
    int star;                          /* holds a "{*: ...}" run-time select */
    unsigned char *map;                /* the map form, UTF-8 */
    unsigned int map_n;
    char *sm_name;                     /* "sm/" rows: the eName */
    unsigned int hash;
    unsigned char *final;              /* the address in the arena */
} tr_prep;

static int tr_token(unsigned char c) {
    return c == '*' || c == '^' || c == '&' || c == '+' || c == '=';
}

/* The expander tokens a prepared text can hold (every branch of a run-time select counted). */
static unsigned int tr_count_tokens(const unsigned char *p) {
    unsigned int n = 0;
    while (*p) {
        if (*p == TR_RT_OPEN && p[1]) {
            p += 2;
            for (;;) {
                if (*p == '=') {
                    while (*p && *p != ':') {
                        ++p;
                    }
                }
                if (*p) {
                    ++p;                          /* the key, or the ':' after =N */
                }
                while (*p && *p != TR_RT_SEP && *p != TR_RT_CLOSE) {
                    n += tr_token(*p) ? 1u : 0u;
                    ++p;
                }
                if (*p != TR_RT_SEP) {
                    break;
                }
                ++p;
            }
            if (*p == TR_RT_CLOSE) {
                ++p;
            }
            continue;
        }
        n += tr_token(*p) ? 1u : 0u;
        ++p;
    }
    return n;
}

static unsigned int tr_count_tokens_live(const unsigned char *p) {
    unsigned int n = 0;
    for (; *p; ++p) {
        n += tr_token(*p) ? 1u : 0u;
    }
    return n;
}

static unsigned int tr_strlen(const unsigned char *p) {
    unsigned int n = 0;
    while (p[n]) {
        ++n;
    }
    return n;
}

/* Prepare one checked row (the translation in g_ptr) for the game: `prep` filled; 0 when it cannot be. */
static int tr_prepare(const tr_row *row, tr_prep *prep) {
    int modes[TR_MAX_SELECTS];
    int i;
    tr_out o;
    for (i = 0; i < g_ptr.nsel; ++i) {
        const tr_select *sel = &g_ptr.sel[i];
        modes[i] = TR_MODE_STATIC;
        if (row->source == TR_SRC_VVFP) {
            continue;
        }
        if (sel->subject == TR_SUBJ_PCT && sel->pct <= g_en_nconv) {
            modes[i] = TR_MODE_RUNTIME;
        } else if (sel->subject == TR_SUBJ_STAR && row->source == TR_SRC_TABLE && g_game <= 2) {
            modes[i] = TR_MODE_RUNTIME;
        } else if (sel->subject == TR_SUBJ_NAME && row->source == TR_SRC_SM && sel->kind == TR_KIND_PERSON
                   && (tr_span_is(sel->name, "name") || tr_span_is(sel->name, "name2"))) {
            modes[i] = TR_MODE_NATIVE;
        }
    }
    o.utf8 = g_utf8;
    o.cap = (unsigned int)row->tr_n * 4u + 8u;
    o.n = 0;
    o.p = (unsigned char *)tr_scratch(o.cap + 1u);
    if (o.p == NULL) {
        return 0;
    }
    tr_emit(&o, &g_ptr, modes);
    if (o.n > o.cap || o.n > TR_MAX_TEXT_BYTES) {
        return 0;
    }
    o.p[o.n] = 0;
    prep->bytes = o.p;
    prep->n = o.n;
    prep->fmt = prep->star = 0;
    for (i = 0; i < g_ptr.nsel; ++i) {
        if (modes[i] == TR_MODE_RUNTIME) {
            if (g_ptr.sel[i].subject == TR_SUBJ_STAR) {
                prep->star = 1;
            } else {
                prep->fmt = 1;
            }
        }
    }
    /* the map form: UTF-8; a vvfp pattern row keeps its "{%N: ...}" for the captured values */
    {
        int pattern = row->source == TR_SRC_VVFP && tr_pattern_english(row->en, row->en_n);
        for (i = 0; i < g_ptr.nsel; ++i) {
            modes[i] = (pattern && g_ptr.sel[i].subject == TR_SUBJ_PCT) ? TR_MODE_RUNTIME : TR_MODE_STATIC;
        }
        o.utf8 = 1;
        o.cap = (unsigned int)row->tr_n * 4u + 8u;
        o.n = 0;
        o.p = (unsigned char *)tr_scratch(o.cap + 1u);
        if (o.p == NULL) {
            return 0;
        }
        tr_emit(&o, &g_ptr, modes);
        if (o.n > o.cap) {
            return 0;
        }
        o.p[o.n] = 0;
        prep->map = o.p;
        prep->map_n = o.n;
    }
    return 1;
}

/* May a prepared text replace `live` (the game's English)? */
static int tr_fits(const tr_prep *prep, const unsigned char *live) {
    unsigned int live_n = tr_strlen(live);
    if ((prep->n > TR_GROWTH * live_n && prep->n > live_n + TR_GROWTH_PLUS)
        || (live_n < TR_SHORT && prep->n >= TR_SHORT)) {
        return 0;
    }
    if (prep->source == TR_SRC_TABLE && tr_count_tokens(prep->bytes) > tr_count_tokens_live(live) + 2u) {
        return 0;
    }
    return 1;
}

static unsigned char *g_arena;      /* the prepared texts */

static void tr_cleanup_failed(void) {
    if (g_arena != NULL) {
        VirtualFree(g_arena, 0, MEM_RELEASE);
        g_arena = NULL;
    }
    tr_free_all(&g_scratch);
    tr_free_all(&g_keep);
    g_map = g_interns = g_keys = NULL;
    g_patterns = NULL;
    memset(g_sm_rows, 0, sizeof g_sm_rows);
    g_have_vvfp = 0;
    g_table_pairs = NULL;
    g_table_pair_count = 0;
    g_fmt_lo = g_fmt_size = g_text_lo = g_text_size = 0;
}

static void tr_start(int game) {
    const tr_game *g = &GAMES[game];
    unsigned int size = 0;
    unsigned char *data;
    tr_cp *text;
    int count = 0, i, line_start, header = 0;
    tr_info info[TR_INFO_COUNT];
    tr_row *rows = NULL, **tail = &rows;
    tr_prep *preps = NULL;
    int n_preps = 0;
    unsigned int fmt_bytes = 0, text_bytes = 0;
    int need_output = 0, need_star = 0, need_loader = 0, n_sites = 0, n_table = 0, n_patch = 0;
    tr_prep *patch_preps = NULL;
    vvfp_site_write *sites;
    tr_entry **seen;

    data = tr_read_file(&size);
    if (data == NULL) {
        return;
    }
    text = tr_decode(data, size, &count);
    if (text == NULL) {
        return;
    }
    memset(info, 0, sizeof info);
    seen = (tr_entry **)tr_scratch(TR_BUCKETS * sizeof(tr_entry *));
    if (seen == NULL) {
        return;
    }
    memset(seen, 0, TR_BUCKETS * sizeof(tr_entry *));

    /* parse(): every line */
    line_start = 0;
    for (i = 0; i <= count; ++i) {
        tr_span line, cells[4];
        int ncells = 0, k, start;
        if (i < count && !tr_line_break(text[i])) {
            continue;
        }
        line.p = text + line_start;
        line.n = i - line_start;
        if (i < count && text[i] == '\r' && i + 1 < count && text[i + 1] == '\n') {
            ++i;
        }
        line_start = i + 1;
        if (line.n > 0 && line.p[0] == '#') {
            if (tr_has_email(line.p, line.n)) {
                return;                              /* validate(): an email in a comment refuses the file */
            }
            continue;
        }
        if (tr_strip(line).n == 0) {
            continue;
        }
        if (i >= count && line.n == 0) {
            break;
        }
        start = 0;
        for (k = 0; k <= line.n && ncells < 4; ++k) {
            if (k == line.n || line.p[k] == '\t') {
                tr_cp *buffer = (tr_cp *)tr_scratch((unsigned int)(k - start) * 4u + 4u);
                int quoted;
                if (buffer == NULL) {
                    return;
                }
                cells[ncells].p = line.p + start;
                cells[ncells].n = k - start;
                cells[ncells] = tr_unquote_span(cells[ncells], buffer, &quoted);
                ++ncells;
                start = k + 1;
            }
        }
        if (!header) {
            if (ncells >= 3 && tr_span_is(tr_strip(cells[0]), "Key") && tr_span_is(tr_strip(cells[1]), "English")
                && tr_span_is(tr_strip(cells[2]), "Translation")) {
                header = 1;
                continue;
            }
            return;                                  /* no header row: the file is refused */
        }
        {
            tr_span key = tr_strip(cells[0]);
            tr_span source, id;
            unsigned int hash;
            tr_cp *en, *tr;
            int en_n, tr_n;
            if (ncells < 2) {
                continue;
            }
            en = (tr_cp *)tr_scratch((unsigned int)cells[1].n * 4u + 4u);
            tr = (tr_cp *)tr_scratch((unsigned int)(ncells > 2 ? cells[2].n : 0) * 4u + 4u);
            if (en == NULL || tr == NULL) {
                return;
            }
            en_n = tr_unescape(cells[1], en);
            tr_n = ncells > 2 ? tr_unescape(cells[2], tr) : 0;
            if (key.n > 0 && key.p[0] == '@') {
                static const char *const INFO_KEYS[TR_INFO_COUNT] = {
                    "@format", "@game", "@language", "@code", "@translator",
                };
                for (k = 0; k < TR_INFO_COUNT; ++k) {
                    if (tr_span_is(key, INFO_KEYS[k])) {
                        info[k].english.p = en;
                        info[k].english.n = en_n;
                        info[k].value.p = tr;
                        info[k].value.n = tr_n;
                        info[k].seen = 1;
                    }
                }
                continue;
            }
            if (!tr_split_key(key, &source, &id, &hash)) {
                continue;
            }
            /* a key seen before: this line is ignored */
            {
                unsigned char kb[512];
                tr_out ko;
                ko.p = kb;
                ko.cap = sizeof kb;
                ko.n = 0;
                ko.utf8 = 1;
                tr_put_cps(&ko, key.p, key.n);
                if (ko.n > ko.cap) {
                    continue;
                }
                if (tr_lookup(seen, kb, ko.n) != NULL) {
                    continue;
                }
                {
                    unsigned char *copy = (unsigned char *)tr_scratch(ko.n + 1u);
                    unsigned int h = tr_fnv(kb, ko.n);
                    tr_entry *e = (tr_entry *)tr_scratch(sizeof(tr_entry));
                    if (copy == NULL || e == NULL) {
                        return;
                    }
                    memcpy(copy, kb, ko.n);
                    memset(e, 0, sizeof *e);
                    e->h = h;
                    e->key = copy;
                    e->klen = ko.n;
                    e->next = seen[h % TR_BUCKETS];
                    seen[h % TR_BUCKETS] = e;
                }
            }
            {
                tr_row *row = (tr_row *)tr_scratch(sizeof(tr_row));
                if (row == NULL) {
                    return;
                }
                memset(row, 0, sizeof *row);
                row->key = key;
                row->id = id;
                row->hash = hash;
                row->en = en;
                row->en_n = en_n;
                row->tr = tr;
                row->tr_n = tr_n;
                if (ncells > 3) {
                    row->notes = cells[3];
                }
                if (tr_span_is(source, "table")) {
                    row->source = TR_SRC_TABLE;
                } else if (tr_span_is(source, "sm")) {
                    row->source = TR_SRC_SM;
                } else if (tr_span_is(source, "exe")) {
                    row->source = TR_SRC_EXE;
                } else if (tr_span_is(source, "patch")) {
                    row->source = TR_SRC_PATCH;
                } else if (source.n >= 4 && source.p[0] == 'v' && source.p[1] == 'v' && source.p[2] == 'f'
                           && source.p[3] == 'p' && (source.n == 4 || source.p[4] == '.')) {
                    row->source = TR_SRC_VVFP;
                } else {
                    row->source = TR_SRC_OTHER;
                }
                *tail = row;
                tail = &row->next;
                /* validate(): an email in a row's English or notes refuses the file */
                if (tr_has_email(en, en_n) || tr_has_email(row->notes.p, row->notes.n)) {
                    return;
                }
            }
        }
    }
    if (!header || !tr_info_ok(info, g->title)) {
        return;
    }
    g_utf8 = tr_glyphs_utf8(game);
    g_map = (tr_entry **)tr_keep(TR_BUCKETS * sizeof(tr_entry *));
    g_interns = (tr_entry **)tr_keep(TR_BUCKETS * sizeof(tr_entry *));
    g_keys = (tr_entry **)tr_keep(TR_BUCKETS * sizeof(tr_entry *));
    if (g_map == NULL || g_interns == NULL || g_keys == NULL) {
        tr_cleanup_failed();
        return;
    }
    memset(g_map, 0, TR_BUCKETS * sizeof(tr_entry *));
    memset(g_interns, 0, TR_BUCKETS * sizeof(tr_entry *));
    memset(g_keys, 0, TR_BUCKETS * sizeof(tr_entry *));

    /* every row: its English still the key's, its translation checked, its text found */
    {
        tr_row *row;
        for (row = rows; row != NULL; row = row->next) {
            tr_prep *prep;
            const unsigned char *live = NULL;
            unsigned int at = 0;
            if (row->tr_n == 0 || row->source == TR_SRC_OTHER) {
                continue;
            }
            if (tr_hash_cps(row->en, row->en_n) != row->hash) {
                continue;                       /* the English column was edited */
            }
            if (row->source == TR_SRC_TABLE && g->table != 0) {
                char id[16];
                unsigned long value = 0;
                unsigned int r;
                int k;
                if (!tr_span_ascii(row->id, id, sizeof id) || id[0] == 0) {
                    continue;
                }
                for (k = 0; id[k]; ++k) {
                    if (id[k] < '0' || id[k] > '9' || value > 100000u) {
                        value = 0xFFFFFFFFu;
                        break;
                    }
                    value = value * 10u + (unsigned long)(id[k] - '0');
                }
                if (value >= g->max_id) {
                    continue;
                }
                for (r = 0; r < g->rows; ++r) {
                    const unsigned int *trow = (const unsigned int *)(UINT_PTR)(g->table + r * g->stride);
                    if (trow[0] == value) {
                        at = (unsigned int)(UINT_PTR)&trow[1];
                        live = tr_live_text(trow[1]);
                        break;
                    }
                }
                if (live == NULL || tr_hash_cp1252(live) != row->hash) {
                    continue;
                }
            } else if (row->source == TR_SRC_EXE) {
                char id[16];
                unsigned int value = 0;
                int k;
                const tr_site *s;
                if (!tr_span_ascii(row->id, id, sizeof id) || id[0] != '0' || (id[1] != 'x' && id[1] != 'X')
                    || id[2] == 0) {
                    continue;
                }
                for (k = 2; id[k]; ++k) {
                    char c = id[k];
                    unsigned int v = (c >= '0' && c <= '9') ? (unsigned int)(c - '0')
                        : (c >= 'a' && c <= 'f') ? (unsigned int)(c - 'a' + 10)
                        : (c >= 'A' && c <= 'F') ? (unsigned int)(c - 'A' + 10) : 16u;
                    if (v > 15u || k > 9) {
                        value = 0;
                        break;
                    }
                    value = (value << 4) | v;
                }
                for (s = g->sites; s->site_va != 0; ++s) {
                    if (s->literal_va == value) {
                        break;
                    }
                }
                if (value == 0 || s->site_va == 0) {
                    continue;
                }
                at = value;
                live = tr_live_text(value);
                if (live == NULL || tr_hash_cp1252(live) != row->hash) {
                    continue;
                }
            } else if (row->source == TR_SRC_PATCH) {
                char id[16];
                unsigned int value = 0;
                int k;
                if (!tr_span_ascii(row->id, id, sizeof id) || id[0] != '0' || (id[1] != 'x' && id[1] != 'X')
                    || id[2] == 0) {
                    continue;
                }
                /* "0x<va>", or "0x<va>.v<n>" for a second patch text at the same address (its hash tells them
                   apart) */
                for (k = 2; id[k] && id[k] != '.'; ++k) {
                    char c = id[k];
                    unsigned int v = (c >= '0' && c <= '9') ? (unsigned int)(c - '0')
                        : (c >= 'a' && c <= 'f') ? (unsigned int)(c - 'a' + 10)
                        : (c >= 'A' && c <= 'F') ? (unsigned int)(c - 'A' + 10) : 16u;
                    if (v > 15u || k > 9) {
                        value = 0;
                        break;
                    }
                    value = (value << 4) | v;
                }
                /* only the game's own image: never another module's memory */
                if (value < 0x401000u || value >= 0x01000000u) {
                    continue;
                }
                /* ... and only an address (with that English's hash) an exe patch is known to write text at:
                   a translation file names both itself, so it must not be able to aim a row at code */
                {
                    const tr_patch_site *ps;
                    for (ps = g->patch_sites; ps->va != 0; ++ps) {
                        if (ps->va == value && ps->hash == row->hash) {
                            break;
                        }
                    }
                    if (ps->va == 0) {
                        continue;
                    }
                }
                at = value;
                live = tr_live_text(value);
                if (live == NULL || tr_hash_cp1252(live) != row->hash) {
                    continue;                   /* this build has no such patch text, or another one */
                }
            } else if (row->source == TR_SRC_SM) {
                if (g->sm == 0) {
                    continue;
                }
            } else if (row->source != TR_SRC_VVFP) {
                continue;
            }
            if (!tr_check_row(row)) {
                continue;
            }
            prep = (tr_prep *)tr_scratch(sizeof(tr_prep));
            if (prep == NULL) {
                tr_cleanup_failed();
                return;
            }
            memset(prep, 0, sizeof *prep);
            prep->source = row->source;
            prep->at = at;
            prep->live = live;
            prep->hash = row->hash;
            if (!tr_prepare(row, prep)) {
                continue;
            }
            if (row->source == TR_SRC_VVFP || row->source == TR_SRC_PATCH) {
                int pattern = tr_pattern_english(row->en, row->en_n);
                tr_span stem;
                stem.p = row->key.p;
                stem.n = 0;
                while (stem.n < row->key.n && row->key.p[stem.n] != '~') {
                    ++stem.n;
                }
                if (!tr_key_only(stem)) {
                    tr_map_add(row->en, row->en_n, prep->map, prep->map_n, pattern);
                }
                tr_key_add(stem, row->hash, row->en, row->en_n, prep->bytes, prep->n, prep->map, prep->map_n,
                           pattern);
                if (row->source == TR_SRC_VVFP) {
                    g_have_vvfp = 1;
                    continue;
                }
                /* An exe patch's text: in place when the translation fits the English's own bytes. */
                if (prep->n <= tr_strlen(live) && tr_strlen(live) + 1u <= VVFP_SITE_MAX_BYTES) {
                    prep->next = patch_preps;
                    patch_preps = prep;
                    ++n_patch;
                }
                g_have_vvfp = 1;
                continue;
            }
            if (row->source == TR_SRC_SM) {
                char name[200];
                if (!tr_span_ascii(row->id, name, sizeof name)) {
                    continue;
                }
                prep->sm_name = (char *)tr_scratch((unsigned int)row->id.n + 1u);
                if (prep->sm_name == NULL) {
                    continue;
                }
                memcpy(prep->sm_name, name, (size_t)row->id.n + 1u);
                need_loader = 1;
            } else if (!tr_fits(prep, live)) {
                continue;
            }
            if (row->source == TR_SRC_TABLE || row->source == TR_SRC_EXE) {
                /* the content map: the game's English (exact) */
                tr_map_add(row->en, row->en_n, prep->map, prep->map_n, 0);
            }
            if (prep->fmt) {
                need_output = 1;
                fmt_bytes += prep->n + 1u;
            } else {
                text_bytes += prep->n + 1u;
            }
            if (prep->star) {
                need_star = 1;
            }
            if (row->source == TR_SRC_TABLE) {
                ++n_table;
            } else if (row->source == TR_SRC_EXE) {
                const tr_site *s;
                for (s = g->sites; s->site_va != 0; ++s) {
                    if (s->literal_va == prep->at) {
                        ++n_sites;
                    }
                }
            }
            prep->next = preps;
            preps = prep;
            ++n_preps;
        }
    }

    /* the arenas: the formats first (one contiguous range for the _output detour), then every other text */
    {
        unsigned char *arena = NULL, *fmt_at, *text_at;
        tr_prep *prep;
        if (fmt_bytes + text_bytes > 0) {
            arena = (unsigned char *)VirtualAlloc(NULL, fmt_bytes + text_bytes + 16u, MEM_COMMIT | MEM_RESERVE,
                                                  PAGE_READWRITE);
            if (arena == NULL) {
                tr_cleanup_failed();
                return;
            }
        }
        g_arena = arena;
        fmt_at = arena;
        text_at = arena + fmt_bytes;
        for (prep = preps; prep != NULL; prep = prep->next) {
            unsigned char **at = prep->fmt ? &fmt_at : &text_at;
            memcpy(*at, prep->bytes, prep->n + 1u);
            prep->final = *at;
            *at += prep->n + 1u;
        }
        g_fmt_lo = (unsigned int)(UINT_PTR)arena;
        g_fmt_size = fmt_bytes;
        g_text_lo = (unsigned int)(UINT_PTR)arena;
        g_text_size = fmt_bytes + text_bytes;
    }

    /* the code: every site, or none */
    {
        int total = n_sites + (need_output ? 1 : 0) + (need_loader ? 1 : 0)
            + ((need_star && g->expanders != NULL) ? g->expander_count : 0);
        int w = 0;
        tr_prep *prep;
        if (total > 0) {
            sites = (vvfp_site_write *)tr_scratch((unsigned int)total * (unsigned int)sizeof(vvfp_site_write));
            if (sites == NULL) {
                tr_cleanup_failed();
                return;
            }
            for (prep = preps; prep != NULL; prep = prep->next) {
                const tr_site *s;
                if (prep->source != TR_SRC_EXE) {
                    continue;
                }
                for (s = g->sites; s->site_va != 0; ++s) {
                    unsigned int imm;
                    if (s->literal_va != prep->at) {
                        continue;
                    }
                    memcpy(&imm, s->stock + s->operand_offset, 4);
                    if (s->length < 5 || s->length > 8 || s->operand_offset + 4 > s->length || imm != s->literal_va) {
                        tr_cleanup_failed();
                        return;
                    }
                    imm = (unsigned int)(UINT_PTR)prep->final;
                    vvfp_site_bytes(&sites[w], s->site_va, s->length, s->stock, s->stock);
                    memcpy(sites[w].bytes + s->operand_offset, &imm, 4);
                    ++w;
                }
            }
            if (need_output) {
                g_output_cont = g->output + (g->output_args4 ? 8u : 9u);
                vvfp_site_branch(&sites[w], g->output, g->output_args4 ? 8 : 9,
                                 g->output_args4 ? OUTPUT_STOCK_B : OUTPUT_STOCK_A, 0xE9,
                                 g->output_args4 ? (const void *)tr_output_stub_b : (const void *)tr_output_stub_a);
                ++w;
            }
            if (need_loader) {
                static unsigned char stock[5];
                unsigned int rel = g->loader - (g->loader_site + 5u);
                stock[0] = 0xE8;
                memcpy(stock + 1, &rel, 4);
                g_loader_fn = g->loader;
                vvfp_site_branch(&sites[w], g->loader_site, 5, stock, 0xE8, (const void *)tr_loader_wrap);
                ++w;
            }
            if (need_star && g->expanders != NULL) {
                static const unsigned char SUB104[6] = { 0x81, 0xEC, 0x04, 0x01, 0x00, 0x00 };
                static const unsigned char SUB108[6] = { 0x81, 0xEC, 0x08, 0x01, 0x00, 0x00 };
                for (i = 0; i < g->expander_count; ++i) {
                    const tr_expander *e = &g->expanders[i];
                    g_exp_cont[i] = e->va + 6u;
                    g_exp_stack[i] = e->stack;
                    vvfp_site_branch(&sites[w], e->va, 6, e->stack == 0x108u ? SUB108 : SUB104, 0xE9,
                                     (const void *)TR_EXP_STUBS[i]);
                    ++w;
                }
                g_exp_buf = (unsigned char *)tr_keep(TR_EXP_BUF);
                if (g_exp_buf == NULL) {
                    tr_cleanup_failed();
                    return;
                }
            }
            if (!vvfp_install_sites(sites, w)) {
                tr_cleanup_failed();
                return;
            }
        }
    }

    /* the table rows' pointers (A New Home, The Lost Children): after the code */
    if (n_table > 0) {
        int w = 0;
        tr_prep *prep;
        vvfp_site_write *table = (vvfp_site_write *)tr_scratch((unsigned int)n_table * (unsigned int)sizeof(vvfp_site_write));
        unsigned int *expect = (unsigned int *)tr_scratch((unsigned int)n_table * 4u);
        g_table_pairs = (tr_pair *)tr_keep((unsigned int)n_table * (unsigned int)sizeof(tr_pair));
        if (table != NULL && expect != NULL && g_table_pairs != NULL) {
            for (prep = preps; prep != NULL; prep = prep->next) {
                unsigned int value;
                if (prep->source != TR_SRC_TABLE) {
                    continue;
                }
                expect[w] = (unsigned int)(UINT_PTR)prep->live;
                value = (unsigned int)(UINT_PTR)prep->final;
                vvfp_site_bytes(&table[w], prep->at, 4, (const unsigned char *)&expect[w], (const unsigned char *)&value);
                g_table_pairs[w].prepared = prep->final;
                g_table_pairs[w].english = prep->live;
                ++w;
            }
            if (vvfp_install_sites(table, w)) {
                g_table_pair_count = w;
            }
        }
    }

    /* The exe patches' texts that fit in place: written over their English (all or none), after the code */
    if (n_patch > 0) {
        int w = 0;
        tr_prep *prep;
        vvfp_site_write *writes = (vvfp_site_write *)tr_scratch((unsigned int)n_patch
                                                                * (unsigned int)sizeof(vvfp_site_write));
        if (writes != NULL) {
            for (prep = patch_preps; prep != NULL; prep = prep->next) {
                unsigned int live_n = tr_strlen(prep->live);
                unsigned char bytes[VVFP_SITE_MAX_BYTES];
                memset(bytes, 0, sizeof bytes);
                memcpy(bytes, prep->bytes, prep->n);
                vvfp_site_bytes(&writes[w], prep->at, (int)live_n + 1, prep->live, bytes);
                ++w;
            }
            vvfp_install_sites(writes, w);
        }
    }

    /* The Secret City to New Believers: the rows the loader's wrapper applies */
    if (need_loader) {
        tr_prep *prep;
        for (prep = preps; prep != NULL; prep = prep->next) {
            tr_sm_row *sm;
            unsigned int n;
            unsigned char *name;
            tr_entry *e;
            if (prep->source != TR_SRC_SM) {
                continue;
            }
            n = tr_strlen((const unsigned char *)prep->sm_name);
            name = tr_keep_copy((const unsigned char *)prep->sm_name, n);
            sm = (tr_sm_row *)tr_keep(sizeof(tr_sm_row));
            if (name == NULL || sm == NULL || tr_lookup(g_sm_rows, name, n) != NULL) {
                continue;
            }
            sm->prepared = prep->final;
            sm->map_utf8 = tr_keep_copy(prep->map, prep->map_n);
            sm->map_n = prep->map_n;
            sm->hash = prep->hash;
            e = tr_insert(g_sm_rows, name, n);
            if (e != NULL) {
                e->utf8 = (const unsigned char *)sm;
            }
        }
        /* the loader already ran (the string table was made before this): apply now */
        if (*(const unsigned int *)(UINT_PTR)g->singleton != 0) {
            tr_after_loader();
        }
    }

    if (g_have_vvfp) {
        g_hook = SetWindowsHookExW(WH_CALLWNDPROCRET, tr_window_hook, NULL, GetCurrentThreadId());
    }
    g_active = n_preps > 0 || g_have_vvfp;
    tr_free_all(&g_scratch);
    if (!g_active) {
        tr_cleanup_failed();
    }
}

/* ---- exports ------------------------------------------------------------------------------------- */

/* Called once at game start by "VVFP Startup.dll" (its second word), on the game's own thread, outside
   DllMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (g_game != 0 || game < 1 || game > 5) {
        return;
    }
    g_game = game;
    tr_start(game);
    if (!g_active) {
        tr_free_all(&g_scratch);
    }
}

/* The translation of a text (the game's encoding: Windows-1252, or UTF-8 with the glyph companion), or
   `text` itself.  Game thread only; the result stays valid for the process life. */
const char *__stdcall VvfpTranslateText(const char *text) {
    const unsigned char *in = (const unsigned char *)text;
    unsigned char utf8[TR_WIN_TEXT * 3], result[TR_WIN_TEXT * 3];
    unsigned int n = 0, len = 0, k;
    const tr_entry *exact;
    tr_entry *e;
    if (!g_active || in == NULL || g_map == NULL) {
        return text;
    }
    while (in[len]) {
        if (++len >= TR_WIN_TEXT) {
            return text;
        }
    }
    e = tr_lookup(g_interns, in, len);
    if (e != NULL) {
        return (const char *)e->game;
    }
    if (tr_valid_utf8(in, len)) {
        memcpy(utf8, in, len);
        n = len;
    } else {
        for (k = 0; k < len; ++k) {
            n += tr_utf8_put(tr_cp1252_char(in[k]), utf8 + n);
        }
    }
    utf8[n] = 0;
    if (!tr_translate_utf8(utf8, n, result, sizeof result, &exact)) {
        exact = NULL;
        if (!tr_translate_lines(utf8, n, result, sizeof result)) {
            return text;
        }
    }
    if (exact != NULL) {
        return exact->game != NULL ? (const char *)exact->game : text;
    }
    {
        unsigned int rn = tr_strlen(result);
        unsigned char *game, *key;
        if (g_interned + rn + len + 64u > TR_INTERN_MAX) {
            return text;
        }
        game = (unsigned char *)tr_keep(rn + 1u);
        key = tr_keep_copy(in, len);
        if (game == NULL || key == NULL) {
            return text;
        }
        tr_utf8_to_game(result, rn, game);
        e = tr_insert(g_interns, key, len);
        if (e == NULL) {
            return text;
        }
        e->game = game;
        g_interned += rn + len + 64u;
        return (const char *)game;
    }
}

/* A companion's own text by key (native/shared/vvfp_translate.h): `stem` is the row's "source/id", `english`
   the English the companion holds (the game's encoding).  The translation, in the game's encoding, when a row
   has that stem, its English is this English (the key's hash), and it fits `cap` bytes with its NUL (cap 0: a
   text drawn from a pointer, held to the game's own rule for a text of that length); else `english`.  Every
   select is its 'other' / 'o' branch: the result can be given to sprintf with the English's own arguments
   (the row checks keep every conversion, in order).  Game thread only; valid for the process life. */
const char *__stdcall VvfpTranslateKey(const char *stem, const char *english, unsigned int cap) {
    const tr_entry *e;
    unsigned int n, live_n;
    if (!g_active || g_keys == NULL || stem == NULL || english == NULL) {
        return english;
    }
    e = tr_lookup(g_keys, (const unsigned char *)stem, tr_strlen((const unsigned char *)stem));
    if (e == NULL || e->game == NULL || tr_hash_cp1252((const unsigned char *)english) != e->row_hash) {
        return english;
    }
    n = tr_strlen(e->game);
    live_n = tr_strlen((const unsigned char *)english);
    if (cap != 0 ? n + 1u > cap
                 : ((n > TR_GROWTH * live_n && n > live_n + TR_GROWTH_PLUS) || (live_n < TR_SHORT && n >= TR_SHORT))) {
        return english;
    }
    return (const char *)e->game;
}

/* `text` is the row's English (`english`, a format with %s %d %i %u) already filled in: its translation with
   the same values, gender and plural selects chosen by them, written to `out` (game encoding) when it fits
   `cap` bytes with its NUL.  1 when written; 0 leaves `out` untouched (the caller keeps `text`). */
int __stdcall VvfpTranslateKeyText(const char *stem, const char *english, const char *text, char *out,
                                   unsigned int cap) {
    const tr_entry *e;
    unsigned char utf8[TR_WIN_TEXT * 3], result[TR_WIN_TEXT * 3], game[TR_WIN_TEXT * 3];
    tr_capture caps[TR_MAX_CONVS];
    unsigned int len, n = 0, k, rn, gn;
    int budget = 20000, ncaps = 0;
    const unsigned char *p;
    if (!g_active || g_keys == NULL || stem == NULL || english == NULL || text == NULL || out == NULL || cap == 0) {
        return 0;
    }
    e = tr_lookup(g_keys, (const unsigned char *)stem, tr_strlen((const unsigned char *)stem));
    if (e == NULL || tr_hash_cp1252((const unsigned char *)english) != e->row_hash) {
        return 0;
    }
    if (!e->pattern) {
        if (strcmp(english, text) != 0 || e->game == NULL || tr_strlen(e->game) + 1u > cap) {
            return 0;
        }
        memcpy(out, e->game, tr_strlen(e->game) + 1u);
        return 1;
    }
    len = tr_strlen((const unsigned char *)text);
    if (len >= TR_WIN_TEXT) {
        return 0;
    }
    if (tr_valid_utf8((const unsigned char *)text, len)) {
        memcpy(utf8, text, len);
        n = len;
    } else {
        for (k = 0; k < len; ++k) {
            n += tr_utf8_put(tr_cp1252_char((unsigned char)text[k]), utf8 + n);
        }
    }
    utf8[n] = 0;
    if (!tr_match(e->english, utf8, caps, 0, &budget)) {
        return 0;
    }
    for (p = e->english; *p; ++p) {
        if (*p == '%' && p[1] == '%') {
            ++p;
        } else if (*p == '%') {
            ++ncaps;
            ++p;
        }
    }
    rn = tr_fill_pattern(e->utf8, caps, ncaps, result, sizeof result);
    gn = tr_utf8_to_game(result, rn, game);
    if (gn + 1u > cap) {
        return 0;
    }
    memcpy(out, game, gn + 1u);
    return 1;
}

int __stdcall VvfpTranslationsActive(void) {
    return g_active;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
