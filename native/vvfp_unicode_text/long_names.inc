/* long_names.inc -- names longer than the game's fields, kept whole in a per-save file.

   Every editable text box takes VV_SHARED_NAME_BYTES bytes (the same in all five games).  The game's
   own fields are shorter (a villager's name 27/23 bytes, the tribe name 31/19, an epitaph 64/31), and
   its code copies them through fixed buffers sized for them, so a box's text leaves the box through
   GetText(buffer, size) -- the only way out -- cut to the field: the SHORT FORM, the longest start of
   whole characters that fits with "\x85" (the Windows-1252 ellipsis) after it, "\x85" plus a number when
   another long name already has that short form.  Every stock path therefore only ever holds a short
   form, never more bytes than it was written for.

   The pair (short form, whole name) is appended at once to
       <save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\Long Names\
           Virtual Villagers <N> Long Names - Save <S>.dat
   (one "short<TAB>whole" line each, the game's own bytes; the file starts "VVFP Long Names v1").  Lines
   are only ever added, so a name set and never saved (the game saves only on a clean quit) leaves a
   line nothing uses, which harms nothing.  The patcher reads the same files (src/vv_long_names.py).

   Wherever the game draws or measures text, each short form in it is drawn as its whole name; a text
   box given a short form (the Details screen opening a villager, Change Tribe) holds the whole name.
   Without this companion the game shows the short form -- "Alexandria Montgo..." -- so nothing breaks. */

#define VV_SHARED_NAME_BYTES 1200       /* the engine's own text-box ceiling (SetEditable caps at 1200) */
#define LN_MAX 4096
#define LN_ARENA (2 * 1024 * 1024)

typedef struct ln_pair { unsigned char *shrt, *full; int shrt_len, pending; } ln_pair;

static ln_pair g_ln[LN_MAX];
static int g_ln_count;
static int g_ln_loaded;
static int g_ln_slot_pending;           /* pairs made while no slot was known: written later */
static unsigned char *g_ln_arena;
static int g_ln_arena_used;

typedef struct ln_seen { unsigned int hash; const unsigned char *in, *out; } ln_seen;
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
    if (g_ln[g_ln_count].shrt != NULL && g_ln[g_ln_count].full != NULL) {
        ++g_ln_count;
        ZeroMemory(g_ln_seen, sizeof g_ln_seen);
    }
}

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
    if (size == INVALID_FILE_SIZE || size > 4 * 1024 * 1024 || size < 18) {
        CloseHandle(f);
        return;
    }
    data = (unsigned char *)vg_alloc(size + 1);
    if (data == NULL || !ReadFile(f, data, size, &got, NULL) || got != size || memcmp(data, "VVFP Long Names v1", 18) != 0) {
        vg_free(data);
        CloseHandle(f);
        return;
    }
    CloseHandle(f);
    data[size] = 0;
    p = data;
    end = data + size;
    while (p < end && *p != '\n') ++p;
    while (p < end) {
        unsigned char *line = ++p, *tab = NULL;
        while (p < end && *p != '\n') {
            if (*p == '\t' && tab == NULL) tab = p;
            ++p;
        }
        if (tab != NULL && p <= end && (p < end || p == end)) {
            int sl = (int)(tab - line), fl = (int)(p - tab - 1);
            if (p < end && fl > 0 && sl > 0) {          /* only a whole line (it ends with '\n') */
                ln_add(line, sl, tab + 1, fl);
            }
        }
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

static void ln_write(ln_pair *pair) {
    WCHAR path[MAX_PATH];
    HANDLE f;
    DWORD put;
    int slot = vv_current_save_slot(g_game_number, 0);
    pair->pending = 1;
    if (!ln_path(slot, path)) {
        g_ln_slot_pending = 1;
        return;
    }
    f = CreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        g_ln_slot_pending = 1;
        return;
    }
    pair->pending = 0;
    if (GetFileSize(f, NULL) == 0) {
        WriteFile(f, "VVFP Long Names v1\n", 19, &put, NULL);
    }
    WriteFile(f, pair->shrt, (DWORD)pair->shrt_len, &put, NULL);
    WriteFile(f, "\t", 1, &put, NULL);
    WriteFile(f, pair->full, (DWORD)ln_len(pair->full), &put, NULL);
    WriteFile(f, "\n", 1, &put, NULL);
    CloseHandle(f);
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
        char digits[8];
        unsigned char mark[4];
        int nd = 0, base, nm, n, clash = 0;
        if (k > 1) {
            int v = k, j;
            char rev[8];
            while (v > 0 && nd < 7) {
                rev[nd++] = (char)('0' + v % 10);
                v /= 10;
            }
            for (j = 0; j < nd; ++j) {
                digits[j] = rev[nd - 1 - j];
            }
        }
        /* Room for the ellipsis (1 or 3 bytes) and the number. */
        base = ut_fit(text, len, cap - 1 - 3 - nd);
        if (base <= 0 && len > 0) {
            break;
        }
        CopyMemory(cand, text, (size_t)base);
        nm = ut_append(cand, base, 0x2026, mark);
        CopyMemory(cand + base, mark, (size_t)nm);
        n = base + nm;
        if (nd) {
            CopyMemory(cand + n, digits, (size_t)nd);
            n += nd;
        }
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
    int i;
    if (!g_ln_slot_pending || vv_current_save_slot(g_game_number, 0) == 0) {
        return;
    }
    g_ln_slot_pending = 0;
    for (i = 0; i < g_ln_count; ++i) {
        if (g_ln[i].pending) {
            ln_write(&g_ln[i]);
        }
    }
}

/* `s` with each short form in it replaced by its whole name; `s` itself when it holds none.  The
   answer stays valid for the rest of the game (the game's line breaking keeps pointers into it). */
static const unsigned char *ln_expand(const unsigned char *s) {
    const unsigned char *end, *p;
    unsigned int h = 2166136261u;
    int i, n, has = 0, slot_i;
    ln_seen *seen;
    if (s == NULL) {
        return s;
    }
    end = ut_end(s);
    for (p = s; p < end; ++p) {
        if (*p == 0x85 || (*p == 0xE2 && p + 2 < end && p[1] == 0x80 && p[2] == 0xA6)) {
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
    slot_i = (int)(h & 1023);
    seen = &g_ln_seen[slot_i];
    if (seen->hash == h && seen->in != NULL && lstrcmpA((const char *)seen->in, (const char *)s) == 0) {
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
            if (best >= 0 && o - out + ln_len(g_ln[best].full) < room - 1) {
                int fl = ln_len(g_ln[best].full);
                CopyMemory(o, g_ln[best].full, (size_t)fl);
                o += fl;
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
            seen->in = in;
            seen->out = out;
        }
        return out;
    }
}
