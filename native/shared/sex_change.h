/* sex_change.h -- a villager's sex field changed, and everything kept for them follows them.

   WHO CHANGES IT.  The Custom Island Event's `sex_change` effect ("VVFP Story Upgrades.dll",
   docs/event-collection/cie-v6-binary.md 29) and Change Appearance's "Change sex" (the Origins DLLs of all
   five games).  Both go through vv_sex_change_apply below, and nothing else writes the field.

   WHAT IS WRITTEN.  The game's own sex field, the other value -- nothing else on the record: the head and body
   rows stay (every game has as many male as female rows), the names stay, and the parents recorded on anyone's
   record (recorded at conception, frozen at birth) stay as recorded.

   THE PROTOCOL.  Every companion that keeps a villager's data by an identity holding the sex (the Origins masks,
   the Head and Original Looks, Cause of Death, Faith Loss, a Last Names rule, the VV1 parentage, the custom
   titles' looks) exports

       int __stdcall VvfpVillagerSexChanged(int game, int slot, const void *record, const void *before);

   `record` is the villager's live record, already holding the new sex; `before` a copy of it as it was (the
   whole record, the old sex).  The owner works out, by its OWN identity, the identity before and after, carries
   what it holds for the villager to the new identity (its roster, its stable / keep parts too, so a later rename
   of theirs is still told as one), and writes its own file through its own atomic write when it may -- exactly
   as VvfpVillagersRenamed carries a rename (villager_rekey.h; vv_rekey_pair_one there gives the one pair).  An
   owner that is not loaded is not asked; an export that is missing is skipped.  It returns 1 when it carried
   anything, 0 otherwise (nothing to carry is not an error).

   THE LOG.  Each change is also written, one line, to the save's own "Sex Changes - Save S.txt" (per_save_data.h:
   "Virtual Villagers Fun Patcher\Save S\Data\Sex Changes\"):

       <old>\t<new>\t<name>\r\n          old / new: M or F; the name as the record holds it

   It is read (a) by every owner as it reads its own file for the slot (vv_sex_log_pairs): for each living
   villager it names, the identity with the OTHER sex leads to the identity they have now -- so a file written
   after the change still finds them when the save was not saved after it (the owner Alt-F4s and restores
   backups), and a file the change never reached finds them too; and (b) by the patcher's Python tools (Repair
   Saves, Repair Logs: src/vv_sex_changes.py), which take a villager the log names to be the same villager
   whichever of the two sexes a record shows.  The log only grows; it is never rewritten.

   NEVER A GUESS: a name two living villagers share is skipped, and a pair whose `from` a villager outside the
   change still carries is dropped (villager_rekey.h vv_rekey_drop_carried).

   REFUSED (nothing written; vv_sex_change_refusal): the special villagers -- the Golden Child (never even offered),
   The Secret City's Tribal Chief and stand-in, New Believers' story villagers (roles 12-17).  A villager carrying or
   nursing may change: they go on carrying, and stay the carrying parent on the babies' records.

   Needs save_folder.c linked in (per_save_data.h).  Header-only and file-static. */
#ifndef VV_SEX_CHANGE_H
#define VV_SEX_CHANGE_H

#include <windows.h>
#include <string.h>
#include "per_save_data.h"
#include "game_save_slot.h"
#include "patcher_files.h"

/* The record fields, by game: the same offsets as the Story / Cheat Upgrades adapters
   (native/vvfp_story_upgrades/story_c*.inc) and the Head Look's LAYOUT. */
typedef struct {
    unsigned int stride;
    unsigned int name, name_bytes;
    unsigned int sex;
    int male, female;
    unsigned int pregnant;          /* the age at conception (0: not carrying); the babies are the dword after it */
    unsigned int head, body;
} vv_sex_layout;

static const vv_sex_layout VV_SEX_LAYOUT[6] = {
    { 0 },
    { 0x3D8u,  0x370u,  0x1Cu, 0x350u,  1, 2, 0x358u,  0x360u,  0x364u },
    { 0xE48Cu, 0x564u,  0x18u, 0x538u,  1, 2, 0x540u,  0x548u,  0x54Cu },
    { 0x1F8Cu, 0xDD4u,  0x19u, 0xDC8u,  0, 1, 0xE8Cu,  0xDF0u,  0xDF4u },
    { 0x2E3Cu, 0x1B9Cu, 0x19u, 0x1B90u, 0, 1, 0x1C4Cu, 0x1BB8u, 0x1BBCu },
    { 0x2F44u, 0x1B9Cu, 0x19u, 0x1B90u, 0, 1, 0x1C4Cu, 0x1BB8u, 0x1BBCu },
};

#define VV_SEX_OK        0
#define VV_SEX_SPECIAL   2          /* a story villager */
#define VV_SEX_UNUSABLE  3          /* no game, no record, no slot */

#define VV_SEX_RECORD_MAX 0xF000u   /* the largest record (The Lost Children's 0xE48C) */
#define VV_SEX_LOG_MAX    0x10000u  /* the log read, at most */
#define VV_SEX_EXPORT     "VvfpVillagerSexChanged"

typedef int (__stdcall *vv_sex_changed_fn)(int game, int slot, const void *record, const void *before);

static int vv_sex_game_ok(int game) {
    return game >= 1 && game <= 5;
}

/* 1 when the record's sex field says female. */
static int vv_sex_female(int game, const unsigned char *record) {
    return *(const int *)(record + VV_SEX_LAYOUT[game].sex) == VV_SEX_LAYOUT[game].female;
}

/* A New Home's Golden Child (family 0xC7): the change is never even offered for him (the owner, 2026-11-15:
   "breaks things") -- Change Appearance hides the button, the engine never casts him for sex_change. */
static int vv_sex_golden_child(int game, const unsigned char *record) {
    return game == 1 && record != NULL && *(const int *)(record + 0x36Cu) == 0xC7;
}

/* Whether A New Home's Golden Child keeps his look through a sex change (the owner's option 1, 2026-11-15):
   "VVFP Gender Presentation.dll" is in the game and its draws follow (VvfpGenderPresentationInstalled 1), so the
   two routines that pick his sheets by the sex field (the Villager Details portrait 0x437380, a dialog's figure
   0x43763E) are handed "male" for him whatever the field says (gp_drawn_sex). */
/* Only the companions that carry option 1 define VV_SEX_GC_OPTION1 (A New Home's Origins Icons, Gender
   Presentation, Story / Cheat Upgrades): the other games' companions are built exactly as before. */
#ifdef VV_SEX_GC_OPTION1
typedef int (__stdcall *vv_sex_gp_installed_fn)(int game);
static int vv_sex_gc_draws_follow(int game) {
    HMODULE gp;
    vv_sex_gp_installed_fn installed;
    if (game != 1 || (gp = GetModuleHandleA("VVFP Gender Presentation.dll")) == NULL) {
        return 0;
    }
    installed = (vv_sex_gp_installed_fn)(void *)GetProcAddress(gp, "VvfpGenderPresentationInstalled");
    return installed != NULL && installed(game) == 1;
}
#endif

/* Why villager `record` (record index `index`) cannot have their sex changed (VV_SEX_*), or VV_SEX_OK.  Carrying
   and nursing are NOT refused (the owner, 2026-11-15): no game's delivery depends on the carrier's sex
   (tests/test_sex_change_carrier_all.py runs each game's own delivery with the sex changed part way: the same
   babies, on time, the carrier in the mother's place on their records), so the villager goes on carrying. */
static int vv_sex_change_refusal(int game, const unsigned char *record, int index) {
    if (!vv_sex_game_ok(game) || record == NULL) {
        return VV_SEX_UNUSABLE;
    }
    (void)index;
    if (vv_sex_golden_child(game, record)) {
        return VV_SEX_SPECIAL;
    }
    if (game == 3 && (record[0xE80] != 0 || record[0xE94] != 0)) {
        return VV_SEX_SPECIAL;               /* the Tribal Chief, the stand-in */
    }
    if (game == 5) {
        int role = *(const int *)(record + 0x1CFCu);
        if (role >= 12 && role <= 17) {
            return VV_SEX_SPECIAL;           /* the story villagers */
        }
    }
    return VV_SEX_OK;
}

#ifdef VV_SEX_GC_OPTION1
/* The refusal of a SEX CHANGE (not of a gender presentation, which keeps vv_sex_change_refusal): the same, except
   that the Golden Child may change when his draws follow (vv_sex_gc_draws_follow). */
static int vv_sex_change_refusal_sex(int game, const unsigned char *record, int index) {
    if (vv_sex_golden_child(game, record) && vv_sex_gc_draws_follow(game)) {
        return VV_SEX_OK;
    }
    return vv_sex_change_refusal(game, record, index);
}
#endif

/* ---- the log ---------------------------------------------------------------------------------------------- */

static int vv_sex_log_path(int slot, char *out) {
    char name[] = "Sex Changes - Save 0.txt";
    if (slot < 1 || slot > 5) {
        return 0;
    }
    name[sizeof "Sex Changes - Save " - 1] = (char)('0' + slot);
    return vv_ps_data_file_a(out, "Sex Changes", name, VV_PS_RESERVE);
}

/* The record's name as a C string (at most name_bytes - 1 characters). */
static void vv_sex_name(int game, const unsigned char *record, char *out) {
    const vv_sex_layout *l = &VV_SEX_LAYOUT[game];
    unsigned int n = 0;
    while (n + 1u < l->name_bytes && record[l->name + n] != 0) {
        out[n] = (char)record[l->name + n];
        ++n;
    }
    out[n] = 0;
}

/* One line for the change of `record` (the new sex on it). 1 when written. */
static int vv_sex_log_add(int game, int slot, const unsigned char *record) {
    char path[MAX_PATH], line[96];
    HANDLE h;
    DWORD wrote = 0;
    int female = vv_sex_female(game, record), n;
    if (!vv_sex_log_path(slot, path)) {
        return 0;
    }
    line[0] = female ? 'M' : 'F';
    line[1] = '\t';
    line[2] = female ? 'F' : 'M';
    line[3] = '\t';
    vv_sex_name(game, record, line + 4);
    n = lstrlenA(line);
    line[n++] = '\r';
    line[n++] = '\n';
    h = CreateFileA(path, FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    if (!WriteFile(h, line, (DWORD)n, &wrote, NULL)) {
        wrote = 0;
    }
    CloseHandle(h);
    return wrote == (DWORD)n;
}

/* The slot's log, NUL-terminated, in `buf` (cap bytes); 0 when there is none. */
static int vv_sex_log_read(int slot, char *buf, DWORD cap) {
    char path[MAX_PATH];
    HANDLE h;
    DWORD got = 0;
    if (cap < 2 || !vv_sex_log_path(slot, path)) {
        return 0;
    }
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    if (!ReadFile(h, buf, cap - 1u, &got, NULL)) {
        got = 0;
    }
    CloseHandle(h);
    buf[got] = 0;
    return got > 0;
}

/* Does the log text name `name` (a line's third field)? */
static int vv_sex_log_names(const char *log, const char *name) {
    const char *line = log;
    size_t n = strlen(name);
    while (line != NULL && *line != 0) {
        const char *t1 = strchr(line, '\t');
        const char *t2 = t1 != NULL ? strchr(t1 + 1, '\t') : NULL;
        const char *end = strchr(line, '\n');
        const char *stop = end != NULL ? end : line + strlen(line);
        if (t2 != NULL && t2 < stop) {
            const char *s = t2 + 1, *e = stop;
            if (e > s && e[-1] == '\r') {
                --e;
            }
            if ((size_t)(e - s) == n && n > 0 && memcmp(s, name, n) == 0) {
                return 1;
            }
        }
        line = end != NULL ? end + 1 : NULL;
    }
    return 0;
}

/* THE SEX A VILLAGER WAS BORN WITH (the owner, 2026-11-15: only villagers born female carry; one born female who
   changed to male goes on carrying; one born male never conceives in the game on their own, even as female -- a
   Custom Island Event may still give them a baby with a partner the player chooses).

   By the slot's log: the OLD sex of the first line naming the villager (their name now); their sex now when no
   line does (never changed, or renamed since -- "VVFP Gender Presentation.dll" keeps the birth sex by identity
   too, through renames: VvfpBornFemale, gender_presentation.h).  1 when born female.  The log is read again at
   most every 500 ms. */
static int vv_sex_born_female_by_log(int game, const unsigned char *record) {
    static char log[VV_SEX_LOG_MAX];
    static int have, for_slot;
    static DWORD read_at;
    char name[64];
    const char *line;
    int slot;
    size_t n;
    if (!vv_sex_game_ok(game) || record == NULL) {
        return 0;
    }
    slot = vv_game_save_slot(game);
    if (slot <= 0) {
        return vv_sex_female(game, record);
    }
    if (for_slot != slot || (DWORD)(GetTickCount() - read_at) >= 500u) {
        have = vv_sex_log_read(slot, log, sizeof log);
        for_slot = slot;
        read_at = GetTickCount();
    }
    vv_sex_name(game, record, name);
    n = strlen(name);
    for (line = have ? log : NULL; line != NULL && *line != 0 && n > 0;) {
        const char *t1 = strchr(line, '\t');
        const char *t2 = t1 != NULL ? strchr(t1 + 1, '\t') : NULL;
        const char *end = strchr(line, '\n');
        const char *stop = end != NULL ? end : line + strlen(line);
        if (t2 != NULL && t2 < stop) {
            const char *s = t2 + 1, *e = stop;
            if (e > s && e[-1] == '\r') {
                --e;
            }
            if ((size_t)(e - s) == n && memcmp(s, name, n) == 0) {
                return line[0] == 'F';
            }
        }
        line = end != NULL ? end + 1 : NULL;
    }
    return vv_sex_female(game, record);
}

/* The pairs the slot's log gives an owner as it reads its own file: for each living record (`slots` of them,
   through record(i) / present(r)) whose name a line names and no other living record has, from[] = its identity
   with the OTHER sex, to[] = its identity now.  At most `cap`.  Returns how many. */
typedef const unsigned char *(*vv_sex_record_fn)(int index);
typedef int (*vv_sex_present_fn)(const unsigned char *record);
typedef unsigned int (*vv_sex_identity_fn)(const unsigned char *record);

static int vv_sex_log_pairs(int game, int slot, int slots, vv_sex_record_fn record, vv_sex_present_fn present,
                            vv_sex_identity_fn identity, unsigned int *from, unsigned int *to, int cap) {
    static char log[VV_SEX_LOG_MAX];
    static unsigned char copy[VV_SEX_RECORD_MAX];
    const vv_sex_layout *l;
    int i, j, n = 0;
    if (!vv_sex_game_ok(game) || slots <= 0 || !vv_sex_log_read(slot, log, sizeof log)) {
        return 0;
    }
    l = &VV_SEX_LAYOUT[game];
    if (l->stride > sizeof copy) {
        return 0;
    }
    for (i = 0; i < slots && n < cap; ++i) {
        const unsigned char *r = record(i);
        char name[64];
        int shared = 0;
        if (r == NULL || !present(r)) {
            continue;
        }
        vv_sex_name(game, r, name);
        if (name[0] == 0 || !vv_sex_log_names(log, name)) {
            continue;
        }
        for (j = 0; j < slots && !shared; ++j) {
            const unsigned char *o = record(j);
            if (j != i && o != NULL && present(o)
                && memcmp(o + l->name, r + l->name, l->name_bytes) == 0) {
                shared = 1;                  /* two living villagers of that name: never a guess */
            }
        }
        if (shared) {
            continue;
        }
        memcpy(copy, r, l->stride);
        *(int *)(copy + l->sex) = vv_sex_female(game, r) ? l->male : l->female;
        from[n] = identity(copy);
        to[n] = identity(r);
        if (from[n] != 0u && to[n] != 0u && from[n] != to[n]) {
            ++n;
        }
    }
    return n;
}

#ifdef VV_VILLAGER_REKEY_H
/* For an owner keeping pairs through villager_rekey.h (include it first).

   As it reads its own file for the slot: the log's pairs kept (vv_rekey_note), so its vv_rekey_apply reads every
   identity the file keeps for a villager the log names as the one they have now.  Returns how many were kept. */
static int vv_sex_log_note(int game, int slot, int slots, vv_rekey_record_fn record, vv_rekey_present_fn present,
                           vv_rekey_identity_fn identity) {
    static unsigned int from[VV_REKEY_BATCH], to[VV_REKEY_BATCH];
    int n = vv_sex_log_pairs(game, slot, slots, record, present, identity, from, to, VV_REKEY_BATCH);
    return n > 0 ? vv_rekey_note(slot, from, to, n) : 0;
}

/* In its VvfpVillagerSexChanged: the one pair (*from -> *to) kept for the slot, unless somebody else still
   carries `from`.  1 when kept (the owner then carries what it holds in memory: vv_rekey_apply). */
static int vv_sex_changed_note(int slot, const unsigned char *record, const unsigned char *before, int slots,
                               vv_rekey_record_fn record_fn, vv_rekey_present_fn present,
                               vv_rekey_identity_fn identity, unsigned int *from, unsigned int *to) {
    const void *batch[1];
    if (slot <= 0 || !vv_rekey_pair_one(record, before, identity, from, to)) {
        return 0;
    }
    batch[0] = record;
    (void)vv_rekey_drop_carried(from, 1, batch, slots, record_fn, present, identity);
    return vv_rekey_note(slot, from, to, 1) == 1;
}
#endif

/* ---- the change ------------------------------------------------------------------------------------------- */

/* Every companion that may keep data by the sex: told, if loaded, through its VvfpVillagerSexChanged. */
static const char *const VV_SEX_OWNERS[] = {
    "VVFP Story Upgrades.dll",          /* the custom titles' looks */
    "VVFP Head Look.dll",
    "VVFP Original Look.dll",
    "VVFP Gender Presentation.dll",
    "VVFP Origins Icons.dll",           /* The Secret City's and New Believers' masks */
    "VVFP VV1 Origins Icons.dll",
    "VVFP VV2 Origins Icons.dll",
    "VVFP VV4 Origins Icons.dll",
    "VVFP Cause of Death.dll",
    "VVFP Faith Loss.dll",
    "VVFP Last Names.dll",
    "VVFP VV1 Parentage.dll",
    "VVFP Parentage Export.dll",
    "VVFP Population Export.dll",
    "VVFP Heathens Keep Masks.dll",     /* New Believers' masks worn as Heathens */
    "VVFP Skin Tones.dll",              /* each villager's skin tone and birth tone */
};

/* Each loaded owner told; returns how many carried anything. */
static int vv_sex_tell_owners(int game, int slot, const unsigned char *record, const unsigned char *before) {
    size_t k;
    int carried = 0;
    for (k = 0; k < sizeof VV_SEX_OWNERS / sizeof VV_SEX_OWNERS[0]; ++k) {
        HMODULE owner = GetModuleHandleA(VV_SEX_OWNERS[k]);
        vv_sex_changed_fn changed = owner != NULL
            ? (vv_sex_changed_fn)(void *)GetProcAddress(owner, VV_SEX_EXPORT) : NULL;
        if (changed != NULL && changed(game, slot, record, before) == 1) {
            ++carried;
        }
    }
    return carried;
}

#ifndef VV_SEX_TELL_OWNERS
#define VV_SEX_TELL_OWNERS vv_sex_tell_owners
#endif

/* THE HISTORY LINE.  The change is logged in the Births and Conceptions log as an "Appearance changed" record
   (appearance_log.h; the Parentage Export DLL's WriteVillageRecord, kind 7: held until the next save, so the log
   never runs ahead of the save), the look the same before and after, with two more lines:

       Appearance changed
         Name: Ann
         Old head: 3
         Old body: 4
         New head: 3
         New body: 4
         Old sex: Male
         New sex: Female

   Nothing is written when that DLL is not part of the game. */
typedef int (__stdcall *vv_sex_write_record_fn)(int, int, const void *, int, const char *, const char *, int);

static void vv_sex_history(int game, const unsigned char *record) {
    HMODULE module = vvfp_load_patcher_dll("VVFP Parentage Export.dll");
    vv_sex_write_record_fn write_record = module != NULL
        ? (vv_sex_write_record_fn)(void *)GetProcAddress(module, "WriteVillageRecord") : NULL;
    const vv_sex_layout *l = &VV_SEX_LAYOUT[game];
    int head = *(const int *)(record + l->head), body = *(const int *)(record + l->body);
    int female = vv_sex_female(game, record);
    char lines[200];
    if (write_record == NULL) {
        return;
    }
    wsprintfA(lines, "  Old head: %d\n  Old body: %d\n  New head: %d\n  New body: %d\n  Old sex: %s\n  New sex: %s\n",
              head, body, head, body, female ? "Male" : "Female", female ? "Female" : "Male");
    (void)write_record(game, 7, record, 1, lines, NULL, 0);
}

#ifndef VV_SEX_HISTORY
#define VV_SEX_HISTORY vv_sex_history
#endif

/* Change villager `record` (record index `index`) to the other sex: refused (a VV_SEX_* other than OK, nothing
   written) or made -- the field written, the line logged when the game's slot is known, every loaded owner
   told.  VV_SEX_OK when made. */
static int vv_sex_change_apply(int game, unsigned char *record, int index) {
    static unsigned char before[VV_SEX_RECORD_MAX];
    const vv_sex_layout *l;
#ifdef VV_SEX_GC_OPTION1
    int why = vv_sex_change_refusal_sex(game, record, index), slot;
#else
    int why = vv_sex_change_refusal(game, record, index), slot;
#endif
    if (why != VV_SEX_OK) {
        return why;
    }
    l = &VV_SEX_LAYOUT[game];
    if (l->stride > sizeof before) {
        return VV_SEX_UNUSABLE;
    }
    memcpy(before, record, l->stride);
    *(int *)(record + l->sex) = vv_sex_female(game, record) ? l->male : l->female;
    slot = vv_game_save_slot(game);
    if (slot > 0) {
        (void)vv_sex_log_add(game, slot, record);
    }
    (void)VV_SEX_TELL_OWNERS(game, slot, record, before);
    VV_SEX_HISTORY(game, record);
    return VV_SEX_OK;
}

#endif /* VV_SEX_CHANGE_H */
