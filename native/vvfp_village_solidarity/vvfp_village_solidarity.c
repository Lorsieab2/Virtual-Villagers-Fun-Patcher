/* VVFP Village Solidarity -- "Village Solidarity" (all five games; the owner, 2026-11-17).

   WHAT.  Each village has a Village Solidarity score, 0 to 100, starting at 50.  The patcher's new island events
   (the Story / Cheat Upgrades companion's branching events: the Isola Grand Event Collection, the Companion
   Anthology, More Island Events' graphs and the player's own Custom Island Events) may tag a page "solidarity":
   raise, lower or neutral.  When the event reaches a tagged page, "VVFP Story Upgrades.dll" asks this companion to
   move the score: every raise and every lower by the same amount (VS_STEP), never below 0 or above 100; neutral
   never moves it.  Without this companion the tags are only words in the event's file.

   The score ONLY changes odds, and only of the patcher's own events (the owner: the one exception to "all endings
   equally likely", for these weighted outcomes only).  The Story companion asks VvfpVillageScoreFactor:

     * a cooperative or celebration event, and a weighted split's branch leading to a page tagged "raise" (a
       cooperative ending), is more likely the higher the score is above 50;
     * a repair, peace or apology event, and a branch leading to a page tagged "lower" (a tense ending), is more
       likely the lower the score is below 50.

   The factor (per mille, 1000 = unchanged) is 1000 + 2 x strength tenths x the distance from 50: at the normal
   strength (1x) +2% of the item's own weight for each point, double at 0 or 100.  It only ever RAISES the
   favoured item's weight: nothing is forced, nothing else is lowered, and the game's own island events are never
   drawn by the Story companion at all, so their odds never change.  Nothing changes work, helping, idling, skills
   or health.

   THE STRENGTH (the row's slider, 0.1x to 10x, 1 the normal strength) is the number in "VVFP Village
   Solidarity.txt" beside this DLL, written by the patcher; missing or unreadable: 1x.

   WHERE IT IS KEPT.  Outside the save (the owner's rule): "<save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\
   Village Scores\Village Scores - Save <S>.txt" (native/shared/per_save_data.h), one line per score ("Village
   Solidarity 62"), written atomically (native/shared/sidecar_io.h).  Start Over deletes the slot's folder with it.
   Each move is appended to "...Save <S>\Logs\Village Solidarity\Village Solidarity Log.txt" (append-only; the
   same words in all five games), created with the starting score the first time the village is seen.

   OTHER SCORES.  The scores are a table (VS_SCORES): another village score ("Village Happiness" ...) is one more
   row with its own name, log and translation stems; the file, the moves, the clamp and the factor are shared.

   THE COUNTER.  The Tech screen shows "Village Solidarity: 62 / 100" in the game's own font (counter_vvN.inc,
   each game's Tech screen draw), translated through "VVFP Translations.dll".

   SAFETY.  Nothing is written to the save or to a villager record.  The game's code is only spliced for the
   counter, all of a game's sites or none (native/shared/install_sites.h).  No debug output. */
#include <windows.h>
#include <string.h>
#include "../shared/sidecar_io.h"
#include "../shared/save_folder.h"
#include "../shared/per_save_data.h"
#include "../shared/game_save_slot.h"
#include "../shared/install_sites.h"
#include "../shared/patcher_files.h"
#include "../shared/vvfp_translate.h"

#define VS_STRENGTH_FILE "VVFP Village Solidarity.txt"
#define VS_KIND "Village Scores"
#define VS_FILE_NAME "Village Scores - Save %d.txt"
#define VS_FILE_HEADER "Virtual Villagers Fun Patcher - Village Scores 1"
#define VS_MIN 0
#define VS_MAX 100
#define VS_START 50
#define VS_STEP 5                       /* every raise and every lower: the same amount (the owner) */
#define VS_STRENGTH_DEFAULT 10          /* tenths: 1x, the normal strength */
#define VS_STRENGTH_MIN 1               /* 0.1x */
#define VS_STRENGTH_MAX 100             /* 10x */
#define VS_FILE_BYTES 4096
#define VS_LOG_ROLL_BYTES 524288        /* a log file this big rolls on to "... Log 2.txt", "... Log 3.txt" */

/* The tags (the .cieg node flags' solidarity field, src/vv_cie_graph.py SOLIDARITY_CODES). */
enum { VS_TAG_NONE = 0, VS_TAG_RAISE = 1, VS_TAG_LOWER = 2, VS_TAG_NEUTRAL = 3 };
/* What a weighted item is favoured by. */
enum { VS_FAVOUR_NONE = 0, VS_FAVOUR_HIGH = 1, VS_FAVOUR_LOW = 2 };

typedef struct {
    const char *name;                   /* the file's and the log's word for it: "Village Solidarity" */
    const char *log_folder;             /* its log's folder and file stem */
    const char *counter_stem;           /* the counter's translation stem */
    const char *counter_english;        /* "Village Solidarity: %d / 100" */
    const char *log_stem;               /* a log line's translation stems are never used: logs are English */
} vs_score_def;

/* The village scores.  APPEND ONLY: the index is each score's id in the exports. */
static const vs_score_def VS_SCORES[] = {
    { "Village Solidarity", "Village Solidarity", "vvfp.village_solidarity/vvfp_village_solidarity.VS_SCORES.s0", "Village Solidarity: %d / 100",
      NULL },
};
#define VS_COUNT ((int)(sizeof VS_SCORES / sizeof VS_SCORES[0]))

static int g_game;                      /* the game started for, 0 before VvfpStartup */
static int g_strength = VS_STRENGTH_DEFAULT;
static int g_counter_installed;
static int g_slot;                      /* the slot the scores below were read for, 0 none */
static int g_score[VS_COUNT];
static vv_sidecar_gate g_gate;
static CRITICAL_SECTION g_lock;

#ifdef VVFP_TEST
static int test_slot = -1;              /* -1: the game's own; else the slot (0: no village) */
#endif

/* ---- The pure rules ------------------------------------------------------------------------------------------- */

/* A score moved by `tag`: raise +VS_STEP, lower -VS_STEP, neutral and none unchanged; always 0..100. */
static int vs_moved(int score, int tag) {
    int next = score;
    if (tag == VS_TAG_RAISE) {
        next = score + VS_STEP;
    } else if (tag == VS_TAG_LOWER) {
        next = score - VS_STEP;
    }
    return next < VS_MIN ? VS_MIN : next > VS_MAX ? VS_MAX : next;
}

/* The factor, per mille, an item favoured by `favour` gets at `score` with `strength` tenths: 1000 + 2 x strength x
   the distance from 50 on the item's side, 1000 on the other side, at 50, or for an item favoured by neither. */
static int vs_factor(int score, int favour, int strength) {
    int distance = 0;
    if (score < VS_MIN || score > VS_MAX || strength < VS_STRENGTH_MIN || strength > VS_STRENGTH_MAX) {
        return 1000;
    }
    if (favour == VS_FAVOUR_HIGH && score > VS_START) {
        distance = score - VS_START;
    } else if (favour == VS_FAVOUR_LOW && score < VS_START) {
        distance = VS_START - score;
    }
    return 1000 + 2 * strength * distance;
}

/* "1", "0.5", "2.5" (0.1 to 10, at most one decimal place) as tenths; anything else 0. */
static int vs_parse_tenths(const char *text, int len) {
    int whole = 0, tenths = 0, digits = 0, i = 0;
    while (i < len && (text[i] == ' ' || text[i] == '\t')) {
        ++i;
    }
    for (; i < len && text[i] >= '0' && text[i] <= '9'; ++i) {
        whole = whole * 10 + (text[i] - '0');
        if (++digits > 3) {
            return 0;
        }
    }
    if (digits == 0) {
        return 0;
    }
    if (i < len && text[i] == '.') {
        ++i;
        if (i >= len || text[i] < '0' || text[i] > '9') {
            return 0;
        }
        tenths = text[i++] - '0';
    }
    while (i < len && (text[i] == ' ' || text[i] == '\t' || text[i] == '\r' || text[i] == '\n')) {
        ++i;
    }
    if (i != len) {
        return 0;
    }
    tenths += whole * 10;
    return tenths >= VS_STRENGTH_MIN && tenths <= VS_STRENGTH_MAX ? tenths : 0;
}

/* ---- The scores file ------------------------------------------------------------------------------------------ */

/* The pages already counted (EXACTLY ONCE: a page the game shows again after a restart, because the save it was
   killed before lacks it, never moves the score twice): the last VS_APPLIED keys, kept in the file as
   "Applied <16 hex>-<8 hex>" lines -- the event's purchase time and the page's place in its run. */
#define VS_APPLIED 64

typedef struct {
    unsigned __int64 when;
    unsigned int pos;
} vs_key;

typedef struct {
    int score[VS_COUNT];
    int found[VS_COUNT];
    vs_key applied[VS_APPLIED];
    int applied_count;
} vs_parsed;

static vs_key g_applied[VS_APPLIED];
static int g_applied_count;            /* how many of g_applied hold a key (the newest last) */

static int vs_hex(const char *p, int n, unsigned __int64 *out) {
    int i;
    *out = 0;
    for (i = 0; i < n; ++i) {
        char c = p[i];
        int v = c >= '0' && c <= '9' ? c - '0' : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
        if (v < 0) {
            return 0;
        }
        *out = *out << 4 | (unsigned __int64)v;
    }
    return 1;
}

/* The file: its header line, then "<name> <0..100>" lines; a name this build does not know is ignored (a later
   build's score), a known one twice, out of range or not a number makes the file unreadable. */
static int vs_validate(const unsigned char *data, DWORD len, void *ctx) {
    vs_parsed *out = (vs_parsed *)ctx;
    const char *p = (const char *)data, *end = (const char *)data + len, *line_end;
    int k, header = 0;
    for (k = 0; k < VS_COUNT; ++k) {
        out->score[k] = VS_START;
        out->found[k] = 0;
    }
    out->applied_count = 0;
    for (; p < end; p = line_end < end ? line_end + 1 : end) {
        int n;
        for (line_end = p; line_end < end && *line_end != '\n'; ++line_end) {
        }
        n = (int)(line_end - p);
        if (n > 0 && p[n - 1] == '\r') {
            --n;
        }
        if (!header) {
            if (n != (int)sizeof VS_FILE_HEADER - 1 || memcmp(p, VS_FILE_HEADER, (size_t)n) != 0) {
                return 0;
            }
            header = 1;
            continue;
        }
        if (n == 0) {
            continue;
        }
        if (n == 8 + 16 + 1 + 8 && memcmp(p, "Applied ", 8) == 0 && p[24] == '-') {
            unsigned __int64 when, pos;
            if (!vs_hex(p + 8, 16, &when) || !vs_hex(p + 25, 8, &pos)) {
                return 0;
            }
            if (out->applied_count < VS_APPLIED) {
                out->applied[out->applied_count].when = when;
                out->applied[out->applied_count].pos = (unsigned int)pos;
                ++out->applied_count;
            }
            continue;
        }
        for (k = 0; k < VS_COUNT; ++k) {
            int name = lstrlenA(VS_SCORES[k].name), value = 0, i, digits = 0;
            if (n <= name + 1 || memcmp(p, VS_SCORES[k].name, (size_t)name) != 0 || p[name] != ' ') {
                continue;
            }
            for (i = name + 1; i < n; ++i) {
                if (p[i] < '0' || p[i] > '9' || ++digits > 3) {
                    return 0;
                }
                value = value * 10 + (p[i] - '0');
            }
            if (out->found[k] || value < VS_MIN || value > VS_MAX) {
                return 0;
            }
            out->found[k] = 1;
            out->score[k] = value;
            break;
        }
    }
    return header;
}

static int vs_slot_now(void) {
#ifdef VVFP_TEST
    if (test_slot >= 0) {
        return test_slot;
    }
#endif
    return vv_game_save_slot(g_game);
}

static int vs_file_path(char *out, int slot) {
    char name[64];
    wsprintfA(name, VS_FILE_NAME, slot);
    return vv_ps_data_file_a(out, VS_KIND, name, VV_PS_RESERVE);
}

static int vs_publish(void);

/* ---- The log --------------------------------------------------------------------------------------------------- */

/* "<save folder>\...\Save <S>\Logs\<folder>\<folder> Log.txt" (or " Log <n>.txt" once a file is full), routed as
   every per-save log is (per_save.h).  1 when `out` names it. */
static int vs_log_path(wchar_t *out, int slot, const vs_score_def *def, int *fresh) {
    wchar_t folder[MAX_PATH], sub[160], leaf[160];
    int n;
    *fresh = 0;
    wsprintfW(sub, L"Virtual Villagers Fun Patcher Logs\\Save %d\\%hs", slot, def->log_folder);
    if (!vv_save_folder_w(folder, lstrlenW(sub) + 64)) {
        return 0;
    }
    for (n = 1; n < 10000; ++n) {
        WIN32_FILE_ATTRIBUTE_DATA info;
        if (n == 1) {
            wsprintfW(leaf, L"%hs Log.txt", def->log_folder);
        } else {
            wsprintfW(leaf, L"%hs Log %d.txt", def->log_folder, n);
        }
        if (lstrlenW(folder) + 1 + lstrlenW(sub) + 1 + lstrlenW(leaf) + 1 > MAX_PATH) {
            return 0;
        }
        lstrcpyW(out, folder);
        lstrcatW(out, L"\\");
        lstrcatW(out, sub);
        lstrcatW(out, L"\\");
        lstrcatW(out, leaf);
        vv_ps_route_w(out, MAX_PATH, 1);
        if (!GetFileAttributesExW(out, GetFileExInfoStandard, &info)) {
            *fresh = 1;
            return 1;                    /* not there yet: this one */
        }
        if (info.nFileSizeHigh == 0 && info.nFileSizeLow < VS_LOG_ROLL_BYTES) {
            return 1;
        }
    }
    return 0;
}

/* Appends one line (CRLF added) to score `k`'s log for `slot`; a new file starts with its title line. */
static void vs_log(int slot, int k, const char *line) {
    wchar_t path[MAX_PATH];
    char title[160];
    HANDLE h;
    int fresh;
    DWORD wrote;
    if (!vs_log_path(path, slot, &VS_SCORES[k], &fresh)) {
        return;
    }
    vv_ps_make_parents_w(path);
    {
        /* The folders of the older layout's path when the route kept it. */
        wchar_t dir[MAX_PATH];
        int i, last = 0;
        lstrcpyW(dir, path);
        for (i = 0; dir[i] != 0; ++i) {
            if (dir[i] == L'\\') {
                last = i;
            }
        }
        for (i = 3; i < last; ++i) {
            if (dir[i] == L'\\') {
                dir[i] = 0;
                (void)CreateDirectoryW(dir, NULL);
                dir[i] = L'\\';
            }
        }
        dir[last] = 0;
        (void)CreateDirectoryW(dir, NULL);
    }
    h = CreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return;
    }
    if (fresh) {
        wsprintfA(title, "%s (Save %d) -- every change, newest last.\r\n", VS_SCORES[k].name, slot);
        WriteFile(h, title, (DWORD)lstrlenA(title), &wrote, NULL);
    }
    WriteFile(h, line, (DWORD)lstrlenA(line), &wrote, NULL);
    WriteFile(h, "\r\n", 2, &wrote, NULL);
    CloseHandle(h);
}

/* "2026-11-17 20:15" in the computer's local time. */
static void vs_stamp(char *out) {
    SYSTEMTIME t;
    GetLocalTime(&t);
    wsprintfA(out, "%04u-%02u-%02u %02u:%02u", t.wYear, t.wMonth, t.wDay, t.wHour, t.wMinute);
}

/* ---- Loading and saving ---------------------------------------------------------------------------------------- */

/* The scores of the village on screen, read once per slot; 0 when there is no village or its file is blocked. */
static int vs_load(void) {
    static unsigned char buf[VS_FILE_BYTES];
    char path[MAX_PATH];
    vs_parsed parsed;
    DWORD len = 0;
    int slot = vs_slot_now(), result, k;
    if (slot < 1 || slot > 5) {
        g_slot = 0;
        return 0;
    }
    if (slot == g_slot && g_gate.state == VV_SIDECAR_SETTLED) {
        return 1;
    }
    if (!vs_file_path(path, slot)) {
        return 0;
    }
    vv_sidecar_gate_bind(&g_gate, slot);
    result = vv_sidecar_load(&g_gate, path, buf, sizeof buf, &len, vs_validate, &parsed);
    if (result == VV_SIDECAR_LOAD_BLOCKED) {
        g_slot = 0;
        return 0;
    }
    for (k = 0; k < VS_COUNT; ++k) {
        g_score[k] = result == VV_SIDECAR_LOAD_VALID ? parsed.score[k] : VS_START;
    }
    g_applied_count = result == VV_SIDECAR_LOAD_VALID ? parsed.applied_count : 0;
    memcpy(g_applied, parsed.applied, sizeof g_applied);
    g_slot = slot;
    if (result != VV_SIDECAR_LOAD_VALID) {
        /* The village's first moment with this patch: its file and its log, with the starting score. */
        char line[160], stamp[32];
        vs_stamp(stamp);
        for (k = 0; k < VS_COUNT; ++k) {
            wsprintfA(line, "%s  %s starts at %d / 100.", stamp, VS_SCORES[k].name, g_score[k]);
            vs_log(slot, k, line);
        }
        if (!vs_publish()) {
            return 1;                     /* kept in memory; the file is written at the next move */
        }
    }
    return 1;
}

static int vs_publish(void) {
    char path[MAX_PATH], text[VS_FILE_BYTES];
    const void *parts[1];
    DWORD sizes[1];
    int k, n;
    if (g_slot == 0 || !vs_file_path(path, g_slot)) {
        return 0;
    }
    n = wsprintfA(text, "%s\r\n", VS_FILE_HEADER);
    for (k = 0; k < VS_COUNT; ++k) {
        n += wsprintfA(text + n, "%s %d\r\n", VS_SCORES[k].name, g_score[k]);
    }
    for (k = 0; k < g_applied_count; ++k) {
        n += wsprintfA(text + n, "Applied %08X%08X-%08X\r\n", (unsigned int)(g_applied[k].when >> 32),
                       (unsigned int)g_applied[k].when, g_applied[k].pos);
    }
    parts[0] = text;
    sizes[0] = (DWORD)n;
    return vv_sidecar_publish(&g_gate, path, parts, sizes, 1);
}

/* ---- The strength ---------------------------------------------------------------------------------------------- */

static void vs_read_strength(void) {
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    char text[32];
    DWORD got = 0;
    HANDLE h;
    int tenths;
    g_strength = VS_STRENGTH_DEFAULT;
    if (vvfp_patcher_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, VS_STRENGTH_FILE) == 0) {
        return;
    }
    h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return;
    }
    if (ReadFile(h, text, sizeof text - 1, &got, NULL) && got > 0 && got < sizeof text - 1) {
        tenths = vs_parse_tenths(text, (int)got);
        if (tenths != 0) {
            g_strength = tenths;
        }
    }
    CloseHandle(h);
}

/* ---- The counter ---------------------------------------------------------------------------------------------- */

/* The counter's text for score `k` of the village on screen ("Village Solidarity: 62 / 100", or its translation
   with the same number), in `out` (`cap` bytes); its length, 0 when there is nothing to show (no village, the
   file blocked).  Game thread. */
static int sol_counter_text_of(int k, char *out, unsigned int cap) {
    char english[96];
    const char *shown;
    int score;
    if (out == NULL || cap < 2 || k < 0 || k >= VS_COUNT) {
        return 0;
    }
    EnterCriticalSection(&g_lock);
    score = vs_load() ? g_score[k] : -1;
    LeaveCriticalSection(&g_lock);
    if (score < 0) {
        out[0] = '\0';
        return 0;
    }
    wsprintfA(english, VS_SCORES[k].counter_english, score);
    shown = vvfp_trf(VS_SCORES[k].counter_stem, VS_SCORES[k].counter_english, english, out, cap);
    if (shown != out) {
        lstrcpynA(out, english, (int)cap);
    }
    return lstrlenA(out);
}

/* Village Solidarity's counter text (the counters draw this one). */
static int sol_counter_text(char *out, unsigned int cap) {
    return sol_counter_text_of(0, out, cap);
}

#include "counter_vv1.inc"
#include "counter_vv2.inc"
#include "counter_vv3.inc"
#include "counter_vv4.inc"
#include "counter_vv5.inc"

/* ---- Exports --------------------------------------------------------------------------------------------------- */

void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (g_game != 0 || game < 1 || game > 5) {
        return;
    }
    g_game = game;
    vs_read_strength();
    switch (game) {
    case 1: g_counter_installed = sol_counter_install_vv1(); break;
    case 2: g_counter_installed = sol_counter_install_vv2(); break;
    case 3: g_counter_installed = sol_counter_install_vv3(); break;
    case 4: g_counter_installed = sol_counter_install_vv4(); break;
    default: g_counter_installed = sol_counter_install_vv5(); break;
    }
}

/* The village on screen's score `score_id` (0 Village Solidarity), 0..100; -1 when this companion was not started
   for `game` or there is no village. */
int __stdcall VvfpVillageScoreGet(int game, int score_id) {
    int score;
    if (g_game == 0 || game != g_game || score_id < 0 || score_id >= VS_COUNT) {
        return -1;
    }
    EnterCriticalSection(&g_lock);
    score = vs_load() ? g_score[score_id] : -1;
    LeaveCriticalSection(&g_lock);
    return score;
}

/* An event reached a page tagged `tag` (1 raise, 2 lower, 3 neutral) for score `score_id`: the score moved (raise
   and lower by the same step, kept within 0..100), written and logged with `event_title` (may be NULL).  The new
   score, or -1 when nothing could be done (not started, no village, its file blocked). */
int __stdcall VvfpVillageScoreTag(int game, int score_id, int tag, const char *event_title) {
    char line[320], stamp[32], title[96];
    int before, after;
    if (g_game == 0 || game != g_game || score_id < 0 || score_id >= VS_COUNT || tag < VS_TAG_RAISE
        || tag > VS_TAG_NEUTRAL) {
        return -1;
    }
    EnterCriticalSection(&g_lock);
    if (!vs_load()) {
        LeaveCriticalSection(&g_lock);
        return -1;
    }
    before = g_score[score_id];
    after = vs_moved(before, tag);
    g_score[score_id] = after;
    if (after != before) {
        (void)vs_publish();
    }
    lstrcpynA(title, event_title != NULL && event_title[0] != '\0' ? event_title : "An island event", sizeof title);
    vs_stamp(stamp);
    if (tag == VS_TAG_NEUTRAL) {
        wsprintfA(line, "%s  %s: no change (%d / 100).", stamp, title, after);
    } else if (after == before) {
        wsprintfA(line, "%s  %s: would %s it, but it is already %d / 100.", stamp, title,
                  tag == VS_TAG_RAISE ? "raise" : "lower", after);
    } else {
        wsprintfA(line, "%s  %s: %s by %d, %d -> %d / 100.", stamp, title, tag == VS_TAG_RAISE ? "raised" : "lowered",
                  after > before ? after - before : before - after, before, after);
    }
    vs_log(g_slot, score_id, line);
    LeaveCriticalSection(&g_lock);
    return after;
}

/* VvfpVillageScoreTag EXACTLY ONCE for the page `when` (its event's purchase time, two dwords) and `pos` (its place
   in the run) name: a page already counted (shown again after a restart, the save it was killed before lacking it)
   changes nothing and returns the score as it is.  -1 as VvfpVillageScoreTag. */
int __stdcall VvfpVillageScoreTagOnce(int game, int score_id, int tag, const char *event_title, unsigned int when_lo,
                                      unsigned int when_hi, unsigned int pos) {
    unsigned __int64 when = (unsigned __int64)when_hi << 32 | when_lo;
    int k, score;
    if (g_game == 0 || game != g_game || score_id < 0 || score_id >= VS_COUNT || tag < VS_TAG_RAISE
        || tag > VS_TAG_NEUTRAL) {
        return -1;
    }
    EnterCriticalSection(&g_lock);
    if (!vs_load()) {
        LeaveCriticalSection(&g_lock);
        return -1;
    }
    for (k = 0; k < g_applied_count; ++k) {
        if (g_applied[k].when == when && g_applied[k].pos == pos) {
            score = g_score[score_id];
            LeaveCriticalSection(&g_lock);
            return score;
        }
    }
    if (g_applied_count == VS_APPLIED) {
        memmove(g_applied, g_applied + 1, sizeof g_applied - sizeof g_applied[0]);
        --g_applied_count;
    }
    g_applied[g_applied_count].when = when;
    g_applied[g_applied_count].pos = pos;
    ++g_applied_count;
    (void)vs_publish();                 /* the key kept, even for a move that changes nothing */
    LeaveCriticalSection(&g_lock);
    return VvfpVillageScoreTag(game, score_id, tag, event_title);
}

/* The factor, per mille (1000 = unchanged), for an event or ending favoured by `favour` (1 a high score: cooperative
   and celebration events, cooperative endings; 2 a low score: repair, peace and apology events, tense endings), at
   the village's score `score_id` and the row's strength.  1000 when this companion was not started for `game`, there
   is no village, or `favour` is neither. */
int __stdcall VvfpVillageScoreFactor(int game, int score_id, int favour) {
    int score = VvfpVillageScoreGet(game, score_id);
    return score < 0 ? 1000 : vs_factor(score, favour, g_strength);
}

/* Start Over (VVFP Save Reset.dll's ResetDeletedTribe, before it deletes the slot's folder): the score held for
   `slot` is forgotten, so the new village made there reads its own (missing: 50) and never gets the old one back. */
void __stdcall VvfpVillageScoreReset(int game, int slot) {
    if (g_game == 0 || game != g_game) {
        return;
    }
    EnterCriticalSection(&g_lock);
    if (slot == g_slot || g_gate.key == slot) {
        g_slot = 0;
        memset(&g_gate, 0, sizeof g_gate);
    }
    LeaveCriticalSection(&g_lock);
}

/* The row's strength in tenths (10 = 1x); 0 when not started for `game`. */
int __stdcall VvfpVillageScoreStrength(int game) {
    return g_game != 0 && game == g_game ? g_strength : 0;
}

/* 1 when the Tech screen counter is drawn in `game`. */
int __stdcall VvfpVillageScoreCounterInstalled(int game) {
    return g_game != 0 && game == g_game && g_counter_installed;
}

#ifdef VVFP_TEST
/* The pure rules and the file, for tests/test_village_solidarity.py. */
int __stdcall VvfpVillageScoreProbeMoved(int score, int tag) { return vs_moved(score, tag); }
int __stdcall VvfpVillageScoreProbeFactor(int score, int favour, int strength) {
    return vs_factor(score, favour, strength);
}
int __stdcall VvfpVillageScoreProbeParse(const char *text, int len) { return vs_parse_tenths(text, len); }
void __stdcall VvfpVillageScoreProbeStart(int game, int slot, int strength) {
    g_game = game;
    test_slot = slot;
    g_slot = 0;
    memset(&g_gate, 0, sizeof g_gate);
    g_strength = strength;
}
int __stdcall VvfpVillageScoreProbeCounterText(char *out, unsigned int cap) { return sol_counter_text(out, cap); }
#endif

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        InitializeCriticalSection(&g_lock);
    }
    return TRUE;
}
