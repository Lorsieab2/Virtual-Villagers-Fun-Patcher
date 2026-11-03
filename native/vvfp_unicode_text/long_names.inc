/* long_names.inc -- names longer than the game's fields, kept whole in a per-save file.

   Every editable text box takes VV_SHARED_NAME_BYTES bytes (the same in all five games).  The game's
   own fields are shorter (a villager's name 27/23 bytes, the tribe name 31/19, an epitaph 64/31), and
   its code copies them through fixed buffers sized for them, so a box's text leaves the box through
   GetText(buffer, size) -- the only way out -- cut to the field: the SHORT FORM, the longest start of
   whole characters that fits, trailing spaces dropped, then "..." -- or "2...", "3..." (the number
   first) when another long name already has that short form (docs/UNICODE_SPEC.md: ASCII dots draw in
   every stock font).  The short forms of v1.35.89 end in the ellipsis "…" (0x85, or E2 80 A6) and a
   number; they and their records are read forever, and a name that has one keeps it.  Every stock path
   therefore only ever holds a short form, never more bytes than it was written for.

   The pair (short form, whole name) is appended at once to
       <save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\Long Names\
           Virtual Villagers <N> Long Names - Save <S>.dat
   (one "short<TAB>whole<TAB>CRC-32" line each, the game's own bytes; the file starts "VVFP Long Names
   v2").  Lines are only ever added, each in one write, and a pair counts as kept only when the whole
   line was written (else it is written again two seconds later, at the next draw); a line cut short is
   skipped by its checksum.  A name set and never saved (the game saves only on a clean quit) leaves a
   line nothing uses, which harms nothing.  The patcher reads the same files (src/vv_long_names.py).

   Wherever the game draws or measures text, each short form in it is drawn as its whole name -- fitted with
   "…" when it is wider than the room the game leaves for its field, as many "W" as the field holds bytes
   (text_hooks.inc vt_fit_name; docs/UNICODE_SPEC.md row 3) -- and a text box given a short form (the Details
   screen opening a villager, Change Tribe) holds the whole name.
   Without this companion the game shows the short form -- "Alexandria Montgo..." -- so nothing breaks. */

#define VV_SHARED_NAME_BYTES 1200       /* the engine's own text-box ceiling (SetEditable caps at 1200) */
#define LN_MAX 4096
#define LN_HEADER "VVFP Long Names v2\n"
#define LN_HEADER_LEN 19
#define LN_ARENA (2 * 1024 * 1024)
#define LN_MARK "..."                   /* the end of a new short form (the number, if any, goes first) */
#define LN_MARK_LEN 3

/* room: the bytes of the field the short form was made for (without its NUL); 0 when the record does not say
   (ln_room). */
typedef struct ln_pair { unsigned char *shrt, *full; int shrt_len, pending, room; } ln_pair;

static ln_pair g_ln[LN_MAX];
static int g_ln_count;
static int g_ln_loaded;
static int g_ln_slot_pending;           /* pairs made while no slot was known: written later */
static unsigned char *g_ln_arena;
static int g_ln_arena_used;

typedef struct ln_seen { unsigned int hash; const void *key; const unsigned char *in, *out; } ln_seen;
static ln_seen g_ln_seen[1024];

static int ln_len(const unsigned char *s) {
    return (int)(ut_end(s) - s);
}

static unsigned char *ln_dup(const unsigned char *s, int n) {
    unsigned char *d = (unsigned char *)vg_alloc((size_t)n + 1);
    if (d != NULL) {
        CopyMemory(d, s, (size_t)n);
        d[n] = 0;
    }
    return d;
}

static int ln_path(int slot, WCHAR *out) {
    WCHAR name[96];
    if (slot < 1 || slot > 5 || g_game == NULL) {
        return 0;
    }
    wsprintfW(name, L"Virtual Villagers %d Long Names - Save %d.dat", g_game_number, slot);
    return vv_ps_data_file_w(out, L"Long Names", name, VV_PS_RESERVE);
}

static void ln_add(const unsigned char *shrt, int sl, const unsigned char *full, int fl) {
    int i;
    if (g_ln_count >= LN_MAX || sl <= 0 || fl <= 0) {
        return;
    }
    for (i = 0; i < g_ln_count; ++i) {
        if (g_ln[i].shrt_len == sl && memcmp(g_ln[i].shrt, shrt, (size_t)sl) == 0) {
            return;                     /* the first pair of a short form wins (the files never disagree) */
        }
    }
    g_ln[g_ln_count].shrt = ln_dup(shrt, sl);
    g_ln[g_ln_count].full = ln_dup(full, fl);
    g_ln[g_ln_count].shrt_len = sl;
    g_ln[g_ln_count].pending = 0;
    g_ln[g_ln_count].room = 0;
    if (g_ln[g_ln_count].shrt != NULL && g_ln[g_ln_count].full != NULL) {
        ++g_ln_count;
        ZeroMemory(g_ln_seen, sizeof g_ln_seen);
    }
}

/* CRC-32 (IEEE, the zlib one): each record carries the checksum of its "short<TAB>whole" bytes. */
static unsigned int ln_crc32(const unsigned char *p, int n) {
    unsigned int c = 0xFFFFFFFFu;
    int i, k;
    for (i = 0; i < n; ++i) {
        c ^= p[i];
        for (k = 0; k < 8; ++k) {
            c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
        }
    }
    return ~c;
}

static int ln_hex8(const unsigned char *p, unsigned int *v) {
    int i;
    *v = 0;
    for (i = 0; i < 8; ++i) {
        unsigned int d;
        if (p[i] >= '0' && p[i] <= '9') d = p[i] - '0';
        else if (p[i] >= 'A' && p[i] <= 'F') d = p[i] - 'A' + 10;
        else return 0;
        *v = (*v << 4) | d;
    }
    return 1;
}

/* Every whole, intact record of a file: "short<TAB>whole<TAB>CRC32 (8 hex)\n".  A record cut short (a full
   disk, a crash) or merged with the next fails its checksum and is skipped; nothing else is lost. */
static void ln_load_slot(int slot) {
    WCHAR path[MAX_PATH];
    HANDLE f;
    DWORD size, got = 0;
    unsigned char *data, *p, *end;
    if (!ln_path(slot, path)) {
        return;
    }
    f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        return;
    }
    size = GetFileSize(f, NULL);
    if (size == INVALID_FILE_SIZE || size > 16 * 1024 * 1024 || size < LN_HEADER_LEN) {
        CloseHandle(f);
        return;
    }
    data = (unsigned char *)vg_alloc(size + 1);
    if (data == NULL || !ReadFile(f, data, size, &got, NULL) || got != size
        || memcmp(data, LN_HEADER, LN_HEADER_LEN) != 0) {
        vg_free(data);
        CloseHandle(f);
        return;
    }
    CloseHandle(f);
    data[size] = 0;
    p = data + LN_HEADER_LEN;
    end = data + size;
    while (p < end) {
        unsigned char *line = p, *tab1 = NULL, *tab2 = NULL;
        while (p < end && *p != '\n') {
            if (*p == '\t') {
                if (tab1 == NULL) tab1 = p; else if (tab2 == NULL) tab2 = p; else tab2 = (unsigned char *)1;
            }
            ++p;
        }
        if (p < end && tab1 != NULL && tab2 != NULL && tab2 != (unsigned char *)1 && p - tab2 == 9) {
            unsigned int want;
            int sl = (int)(tab1 - line), fl = (int)(tab2 - tab1 - 1);
            if (sl > 0 && fl > 0 && ln_hex8(tab2 + 1, &want) && ln_crc32(line, (int)(tab2 - line)) == want) {
                ln_add(line, sl, tab1 + 1, fl);
            }
        }
        ++p;                          /* past the '\n' (or the end) */
    }
    vg_free(data);
}

static void ln_load(void) {
    int slot;
    if (g_ln_loaded) {
        return;
    }
    g_ln_loaded = 1;
    for (slot = 1; slot <= 5; ++slot) {
        ln_load_slot(slot);
    }
}

/* Append one pair to the save's file: the header (a new file), a '\n' when the file does not end with one
   (a record cut short before stays alone and fails its checksum), then the whole record -- in ONE write.
   The pair stays pending, to be written again later, unless every byte was written. */
static void ln_write_once(ln_pair *pair);

static void ln_write(ln_pair *pair) {
    pair->pending = 1;
    ln_write_once(pair);
    if (pair->pending) {
        g_ln_slot_pending = 1;          /* tried again at a later draw (ln_flush_pending) */
    }
}

static void ln_write_once(ln_pair *pair) {
    WCHAR path[MAX_PATH];
    HANDLE f;
    DWORD put = 0, size;
    unsigned char *rec;
    int slot = vv_current_save_slot(g_game_number, 0), fl = ln_len(pair->full), n = 0, body;
    unsigned int crc;
    static const char HEX[] = "0123456789ABCDEF";
    if (!ln_path(slot, path)) {
        return;
    }
    rec = (unsigned char *)vg_alloc((size_t)(LN_HEADER_LEN + 1 + pair->shrt_len + 1 + fl + 1 + 8 + 1));
    if (rec == NULL) {
        return;
    }
    f = CreateFileW(path, GENERIC_READ | FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        vg_free(rec);
        return;
    }
    size = GetFileSize(f, NULL);
    if (size == INVALID_FILE_SIZE) {
        CloseHandle(f);
        vg_free(rec);
        return;
    }
    if (size == 0) {
        CopyMemory(rec, LN_HEADER, LN_HEADER_LEN);
        n = LN_HEADER_LEN;
    } else {
        unsigned char last = 0;
        DWORD got = 0;
        LARGE_INTEGER at;
        at.QuadPart = (LONGLONG)size - 1;
        if (SetFilePointerEx(f, at, NULL, FILE_BEGIN) && ReadFile(f, &last, 1, &got, NULL) && got == 1 && last != '\n') {
            rec[n++] = '\n';
        }
    }
    body = n;
    CopyMemory(rec + n, pair->shrt, (size_t)pair->shrt_len);
    n += pair->shrt_len;
    rec[n++] = '\t';
    CopyMemory(rec + n, pair->full, (size_t)fl);
    n += fl;
    crc = ln_crc32(rec + body, n - body);
    rec[n++] = '\t';
    {
        int k;
        for (k = 7; k >= 0; --k) {
            rec[n++] = (unsigned char)HEX[(crc >> (4 * k)) & 0xF];
        }
    }
    rec[n++] = '\n';
    if (WriteFile(f, rec, (DWORD)n, &put, NULL) && put == (DWORD)n) {
        pair->pending = 0;
    }
    CloseHandle(f);
    vg_free(rec);
}

/* The whole name of a short form, or NULL. */
static const unsigned char *ln_full_of(const unsigned char *s) {
    int i, n;
    if (s == NULL) {
        return NULL;
    }
    ln_load();
    n = ln_len(s);
    for (i = 0; i < g_ln_count; ++i) {
        if (g_ln[i].shrt_len == n && memcmp(g_ln[i].shrt, s, (size_t)n) == 0) {
            return g_ln[i].full;
        }
    }
    return NULL;
}

/* Write text's short form for a field of `cap` bytes (with its NUL) into out; records the pair. */
static void ln_shorten(const unsigned char *text, unsigned char *out, int cap) {
    int len = ln_len(text), i, k;
    unsigned char cand[VV_SHARED_NAME_BYTES + 16];
    ln_load();
    if (cap <= 1) {
        if (cap == 1) out[0] = 0;
        return;
    }
    for (i = 0; i < g_ln_count; ++i) {
        if (g_ln[i].shrt_len < cap && lstrcmpA((const char *)g_ln[i].full, (const char *)text) == 0) {
            CopyMemory(out, g_ln[i].shrt, (size_t)g_ln[i].shrt_len + 1);
            return;
        }
    }
    for (k = 1; k < 1000; ++k) {
        char tail[8 + LN_MARK_LEN];
        int tl = 0, base, n, clash = 0;
        if (k > 1) {
            int v = k, j;
            char rev[8];
            while (v > 0 && tl < 7) {
                rev[tl++] = (char)('0' + v % 10);
                v /= 10;
            }
            for (j = 0; j < tl; ++j) {
                tail[j] = rev[tl - 1 - j];
            }
        }
        CopyMemory(tail + tl, LN_MARK, LN_MARK_LEN);
        tl += LN_MARK_LEN;
        if (tl > cap - 1) {
            break;
        }
        /* The longest start of whole characters that fits with the number and the mark, trailing spaces
           dropped. */
        base = ut_fit(text, len, cap - 1 - tl);
        while (base > 0 && text[base - 1] == ' ') {
            --base;
        }
        if (base <= 0 && len > 0) {
            break;
        }
        CopyMemory(cand, text, (size_t)base);
        CopyMemory(cand + base, tail, (size_t)tl);
        n = base + tl;
        cand[n] = 0;
        for (i = 0; i < g_ln_count; ++i) {
            if (g_ln[i].shrt_len == n && memcmp(g_ln[i].shrt, cand, (size_t)n) == 0) {
                clash = 1;
                break;
            }
        }
        if (!clash) {
            ln_add(cand, n, text, len);
            if (g_ln_count > 0 && g_ln[g_ln_count - 1].shrt_len == n
                && memcmp(g_ln[g_ln_count - 1].shrt, cand, (size_t)n) == 0) {
                g_ln[g_ln_count - 1].room = cap - 1;
                ln_write(&g_ln[g_ln_count - 1]);
            }
            CopyMemory(out, cand, (size_t)n + 1);
            return;
        }
    }
    /* No short form could be made: the stock cut, at a character boundary. */
    k = ut_fit(text, len, cap - 1);
    CopyMemory(out, text, (size_t)k);
    out[k] = 0;
}

/* Pairs made before the save had a slot: written once it has one. */
static void ln_flush_pending(void) {
    static DWORD last_try;
    DWORD now = GetTickCount();
    int i;
    if (!g_ln_slot_pending || vv_current_save_slot(g_game_number, 0) == 0 || now - last_try < 2000) {
        return;
    }
    last_try = now;
    g_ln_slot_pending = 0;
    for (i = 0; i < g_ln_count; ++i) {
        if (g_ln[i].pending) {
            ln_write(&g_ln[i]);
        }
    }
}

/* The bytes of the field a pair's short form stands in (without its NUL): the one it was made for, else the
   smallest of the game's name fields that holds it -- a villager's name 27 (A New Home) / 23, the tribe name
   31 / 19, an epitaph 63 / 30 (the GetText sizes less the NUL). */
static int ln_room(const ln_pair *pair) {
    static const int FIELDS[6][4] = {{0}, {27, 31, 0}, {23, 31, 63, 0}, {19, 23, 30, 0}, {19, 23, 30, 0},
                                     {19, 23, 30, 0}};
    int i;
    if (pair->room > 0) {
        return pair->room;
    }
    if (g_game_number >= 1 && g_game_number <= 5) {
        for (i = 0; FIELDS[g_game_number][i]; ++i) {
            if (FIELDS[g_game_number][i] >= pair->shrt_len) {
                return FIELDS[g_game_number][i];
            }
        }
    }
    return pair->shrt_len;
}

/* Fits a whole name into the room its field leaves where it is drawn (text_hooks.inc vt_fit_name): writes the
   fitted bytes to out (cap) and returns their length, or returns -1 when the whole name fits as it is. */
typedef int (*ln_fit_fn)(void *state, const unsigned char *whole, int len, int room_bytes, unsigned char *out,
                         int cap);

/* `s` with each short form in it replaced by its whole name -- fitted by `fit` (with `state`; NULL: whole) --
   `s` itself when it holds none.  The answer stays valid for the rest of the game (the game's line breaking
   keeps pointers into it). */
static const unsigned char *ln_expand(const unsigned char *s, ln_fit_fn fit, void *state, const void *key) {
    const unsigned char *end, *p;
    unsigned int h = 2166136261u;
    int i, n, has = 0, slot_i;
    ln_seen *seen;
    if (s == NULL) {
        return s;
    }
    end = ut_end(s);
    for (p = s; p < end; ++p) {
        /* "..." (every new short form) or "…" (0x85 / E2 80 A6: the short forms of v1.35.89, read forever). */
        if (*p == 0x85 || (*p == 0xE2 && p + 2 < end && p[1] == 0x80 && p[2] == 0xA6)
            || (*p == '.' && p + 2 < end && p[1] == '.' && p[2] == '.')) {
            has = 1;
        }
        h = (h ^ *p) * 16777619u;
    }
    if (!has) {
        return s;
    }
    ln_load();
    if (g_ln_count == 0) {
        return s;
    }
    n = (int)(end - s);
    h = (h ^ (unsigned int)(UINT_PTR)key) * 16777619u;   /* a fitted answer is the font's own */
    slot_i = (int)(h & 1023);
    seen = &g_ln_seen[slot_i];
    if (seen->hash == h && seen->key == key && seen->in != NULL
        && lstrcmpA((const char *)seen->in, (const char *)s) == 0) {
        return seen->out;
    }
    {
        unsigned char *out, *o;
        int room = 0, changed = 0;
        const unsigned char *q = s;
        /* The expanded size: every whole name is at most the shared limit. */
        room = n + 1 + (VV_SHARED_NAME_BYTES + 1) * 8;
        if (g_ln_arena == NULL) {
            g_ln_arena = (unsigned char *)vg_alloc(LN_ARENA);
            if (g_ln_arena == NULL) {
                return s;
            }
        }
        if (g_ln_arena_used + room + n + 1 > LN_ARENA) {
            return s;
        }
        out = o = g_ln_arena + g_ln_arena_used;
        while (q < end) {
            int best = -1;
            for (i = 0; i < g_ln_count; ++i) {
                if (g_ln[i].shrt_len <= (int)(end - q) && memcmp(q, g_ln[i].shrt, (size_t)g_ln[i].shrt_len) == 0
                    && (best < 0 || g_ln[i].shrt_len > g_ln[best].shrt_len)) {
                    best = i;
                }
            }
            if (best >= 0 && o - out + ln_len(g_ln[best].full) + 4 < room - 1) {
                int fl = ln_len(g_ln[best].full), fitted = -1;
                if (fit != NULL) {
                    fitted = fit(state, g_ln[best].full, fl, ln_room(&g_ln[best]), o, (int)(room - 1 - (o - out)));
                }
                if (fitted < 0) {
                    CopyMemory(o, g_ln[best].full, (size_t)fl);
                    fitted = fl;
                }
                o += fitted;
                q += g_ln[best].shrt_len;
                changed = 1;
            } else {
                if (o - out >= room - 1) {
                    break;
                }
                *o++ = *q++;
            }
        }
        *o = 0;
        if (!changed) {
            return s;
        }
        g_ln_arena_used += (int)(o - out) + 1;
        /* Remember the input too (its own copy: the caller's buffer may change). */
        if (g_ln_arena_used + n + 1 <= LN_ARENA) {
            unsigned char *in = g_ln_arena + g_ln_arena_used;
            CopyMemory(in, s, (size_t)n + 1);
            g_ln_arena_used += n + 1;
            seen->hash = h;
            seen->key = key;
            seen->in = in;
            seen->out = out;
        }
        return out;
    }
}
