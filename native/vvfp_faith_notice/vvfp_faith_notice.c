/* VVFP Faith Notice -- "Popup When Believers Become Heathens", New Believers.

   WHAT.  The owner (2026-11-08), after a catch-up in which every adult believer but a nursing mother became a
   Heathen and nothing said why: "There should be a popup too: (NUMBER) villagers have stopped believing in you
   because of: (FNR_COUNT)".  One island-event popup sums up the believers New Believers' own Faith drift turned
   Heathen -- live, and after the load-time catch-up, a Time Warp or Choose Time Skip Amount -- with the reasons:
   the drift's loss roll that took the Faith (starvation, hunger, sickness, too few believers).  The game's own bottom-bar
   line for each conversion stays as it is: the setter's to-a-Heathen routine 0x4669E0 already says string 0x48,
   eSayStoppedBelieving ("A villager has stopped believing in you!", or "A villager has left the tribe!" with the
   Guardians of Isola rewrite's sm.xml), through the say bar 0x520F68 / 0x44EF60 at 0x4669EC, on every conversion.

   THE DRIFT.  0x468040 runs once per age unit for every believer (the life tick 0x472C90, its one caller at
   0x472D17; Heathens are skipped at 0x472CB7), live and in every catch-up, so it is where the conversions of a
   catch-up, a Time Warp and a time skip happen too.  Its loss rolls are rand(100) calls (0x403660):
       0x468051  food under 10          -1 on rand(100) < [0x46805B]    (stock 30, Faith Loss 60)
       0x468071  food 250 or less       -1 on rand(100) < [0x46807B]    (stock 10, Faith Loss 20; made for food
                                                                         under 10 too when its own roll missed)
       0x4680AE  a sick believer        -1 on rand(100) < [0x4680B8]    (stock 15, Faith Loss 30)
       0x46816C  believers (edi = n)    n < [0x468176] (12): -1 on rand(100) < 12 - n, or 2 * (12 - n) with Faith
                                         Loss (the bytes at 0x468179 say which)
   The other rolls only give Faith.  The thresholds are read from the executable each time, so the reasons are the
   game's own with or without Faith Loss is Doubled/Gains Halved.

   HOW.  Five call sites are redirected at game start (VvfpStartup, from "VVFP Startup.dll"), all or none
   (native/shared/install_sites.h), after each is checked for its stock bytes and the thresholds' instructions for
   one of the two forms above:
     * the life tick's call of the drift (0x472D17): the record is noted before, and after the drift returns a
       believer who is now a Heathen (+0x1CEC) is counted, with the loss rolls that hit;
     * the four loss rolls' calls of rand: the same rand, its answer kept while a drift runs.
   No executable byte is patched, no Faith or record byte is written, and the game's random numbers are drawn
   exactly as before.  "VVFP Story Upgrades.dll" asks VvfpFaithNoticePending every frame and shows the popup with
   its island-event notice (story_faith_notice.inc), once no conversion has come for FN_QUIET_MS, so a catch-up's
   conversions make one popup; then it calls VvfpFaithNoticeTaken.

   THE FILE.  The owner (2026-11-09): save the waiting popup so a quit doesn't lose it.  The batch still waiting
   for its popup (the total and each reason's count) is kept per save slot in
       <save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\Faith Notice\Waiting Popup - Save <S>.dat
   (native/shared/sidecar_io.h: atomic writes, an unreadable file never replaced, an invalid one set aside, a locked
   one retried on the gate's throttle, as Faith Loss's).  It is written when the batch changes -- at most once in
   FN_WRITE_MS, from VvfpFaithNoticeKeep (VVFP Story Upgrades.dll calls it every frame, while the popup waits too)
   and VvfpFaithNoticePending, never from inside the game's life tick -- and deleted the moment the popup is armed
   (VvfpFaithNoticeTaken): from then on the Story queue's own file keeps the armed popup and restores it
   (story_queue.inc), so a quit after the arm never shows it twice.  It is read when the game's save slot (the save
   manager's own field, set before the slot's village is made or loaded) is first seen, and what it holds is added
   to the believers the load-time catch-up has turned since; the popup then comes by the usual rules.  Start Over
   or a deleted tribe (VvfpFaithNoticeVillageReset, the reset generation) forgets the batch in memory and the slot's
   file is read afresh: native/shared/save_reset.c deletes the reset slot's folder, the file with it, so that
   village's popup never comes back and another slot's still does.  A batch is only ever written to its own slot's
   file, and a file is only read for its own slot.  The save itself is never written.

   FORMAT (little-endian): u32 magic 'VFN1', u32 version 1, u32 game 5, u32 slot, u32 total (1 or more), then the
   five reasons' u32 counts (starvation, hunger, sickness, too few believers, other), which add up to the total.
   Exactly 40 bytes.

   SAFETY.  Our steps run under structured exception handling; a fault loses a count, never the game's drift.  No
   debug output. */
#include <windows.h>
#include <shlobj.h>
#include <string.h>
#include "../shared/install_sites.h"
#include "../shared/sidecar_io.h"
#include "../shared/game_save_slot.h"

#define FN_GAME 5                          /* New Believers */
#define FN_QUIET_MS 3000u                  /* a popup waits this long after the last conversion */

#define FN_LIFE_CALL 0x472D17u             /* call 0x468040, the life tick */
#define FN_DRIFT 0x468040u
#define FN_RAND 0x403660u
#define FN_FACTION 0x1CECu                 /* u8, non-zero: a Heathen */

enum { ROLL_FOOD_LOW = 0, ROLL_FOOD, ROLL_SICK, ROLL_BELIEVERS, ROLLS };

/* The reasons, in VvfpFaithNoticePending's out[1..5]: each conversion is counted once, under the first of these
   whose roll hit -- starvation (a food roll with food under 10), hunger (the food roll with food 10 to 250),
   sickness, too few believers; "other" when none did (it cannot happen in the stock drift). */
enum { FNR_STARVATION = 0, FNR_HUNGER, FNR_SICKNESS, FNR_BELIEVERS, FNR_OTHER, FNR_COUNT };
#define FN_FOOD 0x51D34Cu                  /* food in storage */
#define FN_STARVING 10                     /* the drift's own boundary (0x468044) */

static const unsigned int ROLL_CALL[ROLLS] = { 0x468051u, 0x468071u, 0x4680AEu, 0x46816Cu };
/* `cmp eax, imm8` after each food and sickness roll: the imm8's address. */
static const unsigned int ROLL_THRESHOLD[ROLL_BELIEVERS] = { 0x46805Bu, 0x46807Bu, 0x4680B8u };
#define FN_BELIEVERS_CMP 0x468174u         /* cmp edi, 12 */
#define FN_BELIEVERS_LOSS 0x468179u        /* the loss threshold's code: stock or Faith Loss's */
static const unsigned char BELIEVERS_STOCK[9] = { 0xB9, 0x0C, 0x00, 0x00, 0x00, 0x2B, 0xCF, 0x3B, 0xC1 };
static const unsigned char BELIEVERS_DOUBLED[9] = { 0x6B, 0xCF, 0xFE, 0x83, 0xC1, 0x18, 0x3B, 0xC1, 0x90 };
#define FN_SITES (1 + ROLLS)

typedef int (__cdecl *rand_fn)(int);

static unsigned int g_drift = FN_DRIFT;     /* read by drift_call's call */
static int g_installed;

/* The drift in progress. */
static int g_in_drift;
static unsigned char *g_record;
static int g_was_believer;
static int g_rolled[ROLLS];
static int g_roll[ROLLS];
static int g_believers;                    /* edi at the believers' roll */
static int g_food;                         /* food in storage when the drift began */

/* What the popup will say. */
static int g_count;
static int g_counts[FNR_COUNT];
static DWORD g_last;
/* The village the batch belongs to (Codex, #732): the save slot (the save manager's own field) and the reset
   generation (VvfpFaithNoticeVillageReset, from VVFP Story Upgrades.dll's VvfpStoryVillageReset, at Start Over
   or a deleted tribe).  A conversion in another village, or a popup asked for in another, discards the batch:
   one village's believers are never told in another's popup. */
static int g_batch_slot;
static unsigned int g_batch_generation;
static unsigned int g_generation;

static void forget_batch(void) {
    g_count = 0;
    memset(g_counts, 0, sizeof g_counts);
}

static int batch_is_here(void) {
    return g_batch_slot == vv_game_save_slot(FN_GAME) && g_batch_generation == g_generation;
}

static DWORD fn_now(void) {
    return GetTickCount();
}

/* ---- the file (THE FILE, above) ---------------------------------------------------------------------------- */

#define FN_MAGIC 0x314E4656u               /* 'VFN1' */
#define FN_VERSION 1u
#define FN_FILE_WORDS (5 + FNR_COUNT)
#define FN_WRITE_MS 500u                   /* the file follows the batch at most this often */
#define FN_RESERVE ((int)sizeof(".unreadable-4294967295-999"))   /* sidecar_io.h's set-aside name */

static vv_sidecar_gate g_gate;
static int g_file_slot;                    /* the slot whose file was read (0: none yet, or read it again) */
static int g_load_blocked;                 /* its file could not be read: retried on the gate's throttle */
static int g_dirty;                        /* the batch is not what the file says */
static DWORD g_synced_at;
static unsigned int g_buffer[FN_FILE_WORDS + 1];

/* "<Documents>\LDW\<executable's name>\Virtual Villagers Fun Patcher\Save <S>\Data\Faith Notice\
   Waiting Popup - Save <S>.dat"; `make` creates the folders. */
static int notice_path(int slot, char *out, int make) {
    static const char *const LEVELS[4] = {
        "\\Virtual Villagers Fun Patcher", "\\Save %d", "\\Data", "\\Faith Notice"
    };
    char docs[MAX_PATH], exe[MAX_PATH], part[64];
    char *base = exe, *p, *dot = NULL;
    DWORD n;
    int i;
    if (slot < 1 || slot > 5 || !SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) {
        return 0;
    }
    n = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    for (p = exe; *p != '\0'; ++p) {
        if (*p == '\\') {
            base = p + 1;
            dot = NULL;
        } else if (*p == '.') {
            dot = p;
        }
    }
    if (dot != NULL) {
        *dot = '\0';
    }
    if (base[0] == '\0' || lstrlenA(docs) + lstrlenA(base) + 160 >= MAX_PATH - FN_RESERVE) {
        return 0;
    }
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    for (i = 0; i < 4; ++i) {
        wsprintfA(part, LEVELS[i], slot);
        lstrcatA(out, part);
        if (make) {
            CreateDirectoryA(out, NULL);
        }
    }
    wsprintfA(part, "\\Waiting Popup - Save %d.dat", slot);
    lstrcatA(out, part);
    return 1;
}

static int valid_file(const unsigned char *data, DWORD len, void *ctx) {
    const unsigned int *u = (const unsigned int *)data;
    unsigned int sum = 0;
    int i;
    if (len != sizeof(unsigned int) * FN_FILE_WORDS || u[0] != FN_MAGIC || u[1] != FN_VERSION || u[2] != FN_GAME
        || u[3] != (unsigned int)*(const int *)ctx || u[4] == 0u || u[4] > 0xFFFFu) {
        return 0;
    }
    for (i = 0; i < FNR_COUNT; ++i) {
        sum += u[5 + i] <= 0xFFFFu ? u[5 + i] : 0x10000u;
    }
    return sum == u[4];
}

/* The slot's file, read into the batch: what it holds is added to the believers this village has turned since it
   came (the load-time catch-up) -- never to another village's, whose own slot's file has them. */
static void read_batch(int slot) {
    char path[MAX_PATH];
    DWORD got = 0;
    int status, i;
    if (g_count > 0 && (g_batch_slot != slot || g_batch_generation != g_generation)) {
        forget_batch();
    }
    g_load_blocked = 0;
    vv_sidecar_gate_bind(&g_gate, slot);
    if (!notice_path(slot, path, 0)) {
        vv_sidecar_gate_block(&g_gate);    /* retried on the gate's throttle */
        g_load_blocked = 1;
        return;
    }
    status = vv_sidecar_load(&g_gate, path, (unsigned char *)g_buffer, sizeof g_buffer, &got, valid_file, &slot);
    g_load_blocked = status == VV_SIDECAR_LOAD_BLOCKED;
    g_dirty = g_count > 0;                 /* what came before the file was read is not in it yet */
    g_synced_at = fn_now() - FN_WRITE_MS;  /* and it may be written at once */
    if (status == VV_SIDECAR_LOAD_VALID) {
        g_count += (int)g_buffer[4];
        for (i = 0; i < FNR_COUNT; ++i) {
            g_counts[i] += (int)g_buffer[5 + i];
        }
        g_batch_slot = slot;
        g_batch_generation = g_generation;
        g_last = fn_now();                 /* it waits its quiet time, as any batch */
    }
}

/* The file made what the batch is: written while believers wait, deleted once none does.  `now`: at once, else
   no sooner than FN_WRITE_MS after the last. */
static void sync_file(int now) {
    unsigned int words[FN_FILE_WORDS];
    const void *parts[1];
    DWORD sizes[1];
    char path[MAX_PATH];
    int i;
    if (!g_dirty || g_file_slot == 0 || g_load_blocked || !vv_sidecar_gate_ready(&g_gate, g_file_slot)
        || (!now && fn_now() - g_synced_at < FN_WRITE_MS)) {
        return;
    }
    if (g_count > 0 && (g_batch_slot != g_file_slot || g_batch_generation != g_generation)) {
        return;                            /* another village's believers: never this slot's file */
    }
    g_synced_at = fn_now();
    if (g_count <= 0) {
        if (!notice_path(g_file_slot, path, 0) || DeleteFileA(path) || GetLastError() == ERROR_FILE_NOT_FOUND
            || GetLastError() == ERROR_PATH_NOT_FOUND) {
            g_dirty = 0;                   /* else tried again after FN_WRITE_MS */
        }
        return;
    }
    if (!notice_path(g_file_slot, path, 1)) {
        return;
    }
    words[0] = FN_MAGIC;
    words[1] = FN_VERSION;
    words[2] = FN_GAME;
    words[3] = (unsigned int)g_file_slot;
    words[4] = (unsigned int)g_count;
    for (i = 0; i < FNR_COUNT; ++i) {
        words[5 + i] = (unsigned int)g_counts[i];
    }
    parts[0] = words;
    sizes[0] = sizeof words;
    if (vv_sidecar_publish(&g_gate, path, parts, sizes, 1)) {
        g_dirty = 0;
    }
}

/* The slot's file read when the slot is first seen (again after a reset, or once a lock clears), and the batch's
   changes written to it. */
static void keep_file(void) {
    int slot = vv_game_save_slot(FN_GAME);
    if (slot == 0) {
        return;
    }
    if (slot != g_file_slot) {
        sync_file(1);                      /* the last slot's batch reaches its own file first */
        g_file_slot = slot;
        read_batch(slot);
    } else if (g_load_blocked && !vv_sidecar_gate_throttled(&g_gate)) {
        read_batch(slot);                  /* the lock may have cleared */
    }
    sync_file(0);
}

static int fn_rand(int n) {
    return ((rand_fn)(UINT_PTR)FN_RAND)(n);
}

static void note_roll(int which, int value) {
    if (g_in_drift) {
        g_rolled[which] = 1;
        g_roll[which] = value;
    }
}

static int __cdecl rand_food_low(int n) {
    int value = fn_rand(n);
    note_roll(ROLL_FOOD_LOW, value);
    return value;
}

static int __cdecl rand_food(int n) {
    int value = fn_rand(n);
    note_roll(ROLL_FOOD, value);
    return value;
}

static int __cdecl rand_sick(int n) {
    int value = fn_rand(n);
    note_roll(ROLL_SICK, value);
    return value;
}

static int __cdecl rand_believers_c(int n) {
    int value = fn_rand(n);
    note_roll(ROLL_BELIEVERS, value);
    return value;
}

/* The believers' roll: edi holds the count the drift compares (0x46816A, mov edi, eax). */
__declspec(naked) static void rand_believers(void) {
    __asm {
        mov dword ptr [g_believers], edi
        jmp rand_believers_c
    }
}

/* Whether roll `which` took Faith away, by the executable's own threshold. */
static int roll_hit(int which) {
    const unsigned char *loss = (const unsigned char *)(UINT_PTR)FN_BELIEVERS_LOSS;
    int limit;
    if (!g_rolled[which]) {
        return 0;
    }
    if (which != ROLL_BELIEVERS) {
        return g_roll[which] < (int)*(const unsigned char *)(UINT_PTR)ROLL_THRESHOLD[which];
    }
    limit = (int)*(const unsigned char *)(UINT_PTR)(FN_BELIEVERS_CMP + 2u);
    if (g_believers >= limit) {
        return 0;                          /* the gain branch: n / 5 or n / 10 */
    }
    if (memcmp(loss, BELIEVERS_DOUBLED, sizeof BELIEVERS_DOUBLED) == 0) {
        return g_roll[which] < 2 * (limit - g_believers);
    }
    return g_roll[which] < limit - g_believers;
}

static void __cdecl drift_before(unsigned char *record) {
    __try {
        g_record = record;
        g_was_believer = record[FN_FACTION] == 0;
        g_food = *(const volatile int *)(UINT_PTR)FN_FOOD;
        memset(g_rolled, 0, sizeof g_rolled);
        g_in_drift = 1;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_in_drift = 0;
    }
}

static void __cdecl drift_after(void) {
    __try {
        if (g_in_drift && g_was_believer && g_record[FN_FACTION] != 0) {
            int reason = FNR_OTHER;
            if (roll_hit(ROLL_FOOD_LOW) || (roll_hit(ROLL_FOOD) && g_food < FN_STARVING)) {
                reason = FNR_STARVATION;
            } else if (roll_hit(ROLL_FOOD)) {
                reason = FNR_HUNGER;
            } else if (roll_hit(ROLL_SICK)) {
                reason = FNR_SICKNESS;
            } else if (roll_hit(ROLL_BELIEVERS)) {
                reason = FNR_BELIEVERS;
            }
            if (g_count > 0 && !batch_is_here()) {
                forget_batch();            /* the last batch was another village's (its own file has it) */
            }
            g_batch_slot = vv_game_save_slot(FN_GAME);
            g_batch_generation = g_generation;
            ++g_count;
            ++g_counts[reason];
            g_last = fn_now();
            g_dirty = 1;                   /* written by the next VvfpFaithNoticeKeep, never in the life tick */
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    g_in_drift = 0;
}

/* In place of the life tick's `call 0x468040` (ecx the record; the drift takes nothing on the stack). */
__declspec(naked) static void drift_call(void) {
    __asm {
        push ecx
        push ecx
        call drift_before
        add esp, 4
        pop ecx
        call dword ptr [g_drift]
        pushad
        call drift_after
        popad
        ret
    }
}

/* 1 when every site is installed, else 0. */
int __stdcall VvfpFaithNoticeInstalled(void) {
    return g_installed;
}

/* Asked every frame by "VVFP Story Upgrades.dll": 1 when believers became Heathens in `game` and none has for
   FN_QUIET_MS; out[0] = how many, out[1..5] = how many for each reason (starvation, hunger, sickness, too few
   believers, other). */
int __stdcall VvfpFaithNoticePending(int game, int *out) {
    int i;
    if (game != FN_GAME || !g_installed || out == NULL) {
        return 0;
    }
    keep_file();
    if (g_count <= 0) {
        return 0;
    }
    if (!batch_is_here()) {
        forget_batch();                    /* another village is loaded now: that batch is not this one's */
        return 0;
    }
    if (fn_now() - g_last < FN_QUIET_MS) {
        return 0;
    }
    out[0] = g_count;
    for (i = 0; i < FNR_COUNT; ++i) {
        out[1 + i] = g_counts[i];
    }
    return 1;
}

/* Called every frame by "VVFP Story Upgrades.dll", while the popup waits too (a time skip, a menu): the slot's
   file read, and kept what the batch is. */
void __stdcall VvfpFaithNoticeKeep(int game) {
    if (game == FN_GAME && g_installed) {
        keep_file();
    }
}

/* The popup is armed (the Story queue's file keeps it from now on): start counting again, and the file goes at
   once, so a quit never shows it twice. */
void __stdcall VvfpFaithNoticeTaken(int game) {
    if (game == FN_GAME) {
        forget_batch();
        g_dirty = 1;
        sync_file(1);
    }
}

/* Start Over or a deleted tribe (VVFP Story Upgrades.dll's VvfpStoryVillageReset, before native/shared/save_reset.c
   deletes the slot's folder): the village the batch was for is gone, so the batch is, and the slot's file is read
   afresh when next asked -- gone for the reset slot, another slot's waiting popup kept. */
void __stdcall VvfpFaithNoticeVillageReset(int game) {
    if (game == FN_GAME) {
        ++g_generation;
        forget_batch();
        g_dirty = 0;
        g_file_slot = 0;
    }
}

static unsigned char g_call_stock[FN_SITES][5];

static void call_site(vvfp_site_write *w, int n, unsigned int va, unsigned int target, const void *ours) {
    unsigned int rel = target - (va + 5u);
    g_call_stock[n][0] = 0xE8;
    memcpy(g_call_stock[n] + 1, &rel, 4);
    vvfp_site_branch(w, va, 5, g_call_stock[n], 0xE8, ours);
}

/* The thresholds' instructions are one of the two forms this reads (the top of this file). */
static int thresholds_known(void) {
    static const unsigned char CMP_EAX[2] = { 0x83, 0xF8 };
    static const unsigned char CMP_EDI_12[3] = { 0x83, 0xFF, 0x0C };
    int i;
    for (i = 0; i < ROLL_BELIEVERS; ++i) {
        if (!vvfp_site_holds(ROLL_THRESHOLD[i] - 2u, CMP_EAX, 2)) {
            return 0;
        }
    }
    return vvfp_site_holds(FN_BELIEVERS_CMP, CMP_EDI_12, 3)
        && (vvfp_site_holds(FN_BELIEVERS_LOSS, BELIEVERS_STOCK, 9)
            || vvfp_site_holds(FN_BELIEVERS_LOSS, BELIEVERS_DOUBLED, 9));
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write sites[FN_SITES];
    (void)shipped;
    if (g_installed || game != FN_GAME || !thresholds_known()) {
        return;
    }
    call_site(&sites[0], 0, FN_LIFE_CALL, FN_DRIFT, (const void *)drift_call);
    call_site(&sites[1], 1, ROLL_CALL[ROLL_FOOD_LOW], FN_RAND, (const void *)rand_food_low);
    call_site(&sites[2], 2, ROLL_CALL[ROLL_FOOD], FN_RAND, (const void *)rand_food);
    call_site(&sites[3], 3, ROLL_CALL[ROLL_SICK], FN_RAND, (const void *)rand_sick);
    call_site(&sites[4], 4, ROLL_CALL[ROLL_BELIEVERS], FN_RAND, (const void *)rand_believers);
    if (vvfp_install_sites(sites, FN_SITES)) {
        g_installed = 1;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
