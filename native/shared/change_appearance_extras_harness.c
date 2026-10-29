/* Change Appearance's Undo changes, Reset to original and Random buttons, in all five games
   (native/shared/appearance_extras.h; the owner, 2026-10-28).

   Compiled once per game with /DHARNESS_GAME=<1..5>: this file includes that game's Origins companion
   source UNCHANGED and drives its real dialog procedures (and, where the export needs no game memory, the
   export itself) with the buttons' own WM_COMMANDs.  Stand-ins, as in change_appearance_harness.c: the
   Win32 calls a dialog needs a screen for (DialogBoxParamA runs the scripted presses, EndDialog records the
   result, MessageBoxA answers OK and remembers the text, InvalidateRect does nothing), and the two
   companions the windows ask by name -- "VVFP Original Look.dll" (each villager's original look, or not
   known) and "VVFP Head Look.dll" (the looks, kept in memory here) -- found through GetModuleHandleA /
   GetProcAddress.  Nothing is shown and no file is written (The Lost Children's mask table is switched off
   as in change_appearance_harness.c).

   Checked: Undo changes puts every control back and writes and charges nothing; Reset to original sets
   the known original (and only that villager's), says "Original look not known" and changes nothing
   otherwise; Random head, the hair colours, Random body, Random mask and Random look stay in the villager's
   sex, the game's colour groups and the window's pools; Cancel writes nothing; a look-only OK is charged
   (The Lost Children) or handed on as a change; and the Change Appearance for All look rows -- per sex, the
   covered villagers only, Leave as is changes nothing, Random only Young or Old. */
#include <windows.h>
#include <stdio.h>
#include <string.h>

#ifndef HARNESS_GAME
#error "build with /DHARNESS_GAME=1..5"
#endif

static int h_failures;
static int h_checks;
static INT_PTR h_end_result;
static int h_unknown_said;          /* "Original look not known" was shown */
static const UINT *h_script;
static int h_script_len;

static BOOL WINAPI h_EndDialog(HWND window, INT_PTR result) {
    (void)window;
    h_end_result = result;
    return TRUE;
}

static int WINAPI h_MessageBoxA(HWND window, LPCSTR text, LPCSTR caption, UINT flags) {
    (void)window; (void)caption; (void)flags;
    if (text != NULL && strstr(text, "Original look not known") != NULL) {
        h_unknown_said++;
    }
    return IDOK;
}

static BOOL WINAPI h_InvalidateRect(HWND window, const RECT *rect, BOOL erase) {
    (void)window; (void)rect; (void)erase;
    return TRUE;
}

/* Press each scripted button against the real dialog procedure (the script ends in IDOK or IDCANCEL). */
static INT_PTR h_press(DLGPROC proc, const UINT *script, int len) {
    int i;
    h_end_result = -1;
    for (i = 0; i < len; ++i) {
        proc(NULL, WM_COMMAND, MAKEWPARAM(script[i], BN_CLICKED), 0);
    }
    return h_end_result;
}

static INT_PTR WINAPI h_DialogBoxParamA(HINSTANCE instance, LPCSTR name, HWND owner, DLGPROC proc,
                                        LPARAM param) {
    (void)instance; (void)name; (void)owner; (void)param;
    return h_press(proc, h_script, h_script_len);
}

/* ---- the two companions the windows ask for -------------------------------------------------------- */

#define H_ORIGINAL ((HMODULE)(UINT_PTR)0x10000)
#define H_HEAD_LOOK ((HMODULE)(UINT_PTR)0x20000)
static int h_original_there;        /* "VVFP Original Look.dll" is in the game */
static const void *h_original_record; /* the one villager whose original is known */
static int h_original_head, h_original_body, h_original_mask;
static int h_head_look_there;       /* "VVFP Head Look.dll" is in the game and the draws follow it */

#define H_LOOKS 300
static const void *h_look_record[H_LOOKS];
static int h_look_value[H_LOOKS];
static int h_look_count;
static int h_look_writes;           /* how many times the looks were written */

static int __stdcall h_original_get(int game, const void *record, int *head, int *body, int *mask) {
    (void)game;
    if (record == NULL || record != h_original_record) {
        return 0;
    }
    *head = h_original_head;
    *body = h_original_body;
    *mask = h_original_mask;
    return 1;
}

static int __stdcall h_look_installed(int game) {
    return game == HARNESS_GAME && h_head_look_there;
}

static int __stdcall h_look_get(int game, const void *record) {
    int i;
    (void)game;
    for (i = 0; i < h_look_count; ++i) {
        if (h_look_record[i] == record) {
            return h_look_value[i];
        }
    }
    return 0;
}

static void h_look_put(const void *record, int look) {
    int i;
    for (i = 0; i < h_look_count; ++i) {
        if (h_look_record[i] == record) {
            h_look_value[i] = look;
            return;
        }
    }
    h_look_record[h_look_count] = record;
    h_look_value[h_look_count++] = look;
}

static int __stdcall h_look_set(int game, const void *record, int look) {
    (void)game;
    h_look_writes++;
    h_look_put(record, look);
    return 1;
}

static int __stdcall h_look_set_many(int game, const void *const *records, const int *looks, int count) {
    int k;
    (void)game;
    h_look_writes++;
    for (k = 0; k < count; ++k) {
        h_look_put(records[k], looks[k]);
    }
    return 1;
}

static HMODULE WINAPI h_GetModuleHandleA(LPCSTR name) {
    if (name != NULL && lstrcmpiA(name, "VVFP Original Look.dll") == 0) {
        return h_original_there ? H_ORIGINAL : NULL;
    }
    if (name != NULL && lstrcmpiA(name, "VVFP Head Look.dll") == 0) {
        return h_head_look_there ? H_HEAD_LOOK : NULL;
    }
    return name == NULL ? GetModuleHandleA(NULL) : NULL;   /* no other companion is in this test */
}

static FARPROC WINAPI h_GetProcAddress(HMODULE module, LPCSTR name) {
    if (module == H_ORIGINAL) {
        return lstrcmpA(name, "VvfpOriginalLookGet") == 0 ? (FARPROC)h_original_get : NULL;
    }
    if (module == H_HEAD_LOOK) {
        if (lstrcmpA(name, "VvfpHeadLookInstalled") == 0) return (FARPROC)h_look_installed;
        if (lstrcmpA(name, "VvfpHeadLookGet") == 0) return (FARPROC)h_look_get;
        if (lstrcmpA(name, "VvfpHeadLookSet") == 0) return (FARPROC)h_look_set;
        if (lstrcmpA(name, "VvfpHeadLookSetMany") == 0) return (FARPROC)h_look_set_many;
        return NULL;
    }
    return GetProcAddress(module, name);
}

#define EndDialog h_EndDialog
#define MessageBoxA h_MessageBoxA
#define InvalidateRect h_InvalidateRect
#define DialogBoxParamA h_DialogBoxParamA
#define GetModuleHandleA h_GetModuleHandleA
#define GetProcAddress h_GetProcAddress

#if HARNESS_GAME == 1
#include "../vv1_origins_icons/vv1_origins_icons.c"
#elif HARNESS_GAME == 2
#include "../vv2_origins_icons/vv2_origins_icons.c"
#elif HARNESS_GAME == 3
#include "../vv3_full_mastery_candidate/vv3_full_mastery_candidate.c"
#elif HARNESS_GAME == 4
#include "../vv4_origins_icons/vv4_origins_icons.c"
#elif HARNESS_GAME == 5
#include "../vv5_task9_origins/vv5_task9_origins.c"
#else
#error "HARNESS_GAME must be 1..5"
#endif

#undef EndDialog
#undef MessageBoxA
#undef InvalidateRect
#undef DialogBoxParamA
#undef GetModuleHandleA
#undef GetProcAddress

static void h_check(int ok, const char *what) {
    h_checks++;
    if (!ok) {
        h_failures++;
        printf("FAIL game %d: %s\n", HARNESS_GAME, what);
    }
}

static void h_fresh(void) {
    h_original_there = 0;
    h_original_record = NULL;
    h_head_look_there = 0;
    h_look_count = 0;
    h_look_writes = 0;
    h_unknown_said = 0;
}

static int h_in(const unsigned char *rows, int n, int v) {
    int i;
    for (i = 0; i < n; ++i) {
        if (rows[i] == v) {
            return 1;
        }
    }
    return 0;
}

/* ---- the shared Change Appearance for All look rows -------------------------------------------------- */

/* Six villagers, 0..2 men and 3..5 women; 2 and 5 are not covered (the window's game skips them). */
static void h_look_rows(void) {
    static unsigned char villagers[6][16];
    static vvfp_ax_look_plan plan;
    vvfp_head_look_api api;
    int choice[2], i, k, covered;
    unsigned int rng = 12345u;
    h_fresh();
    h_head_look_there = 1;
    h_check(vvfp_head_look_find(HARNESS_GAME, &api) && api.set_many != NULL, "the head-look exports are found");
    choice[0] = choice[1] = 99;
    vvfp_ax_look_rows_init(NULL, 1, choice);
    h_check(choice[0] == VVFP_AX_LEAVE && choice[1] == VVFP_AX_LEAVE, "both rows open on Leave as is");
    plan.count = 0;
    for (i = 0; i < 6; ++i) {
        covered = i != 2 && i != 5;
        if (covered) {
            vvfp_ax_look_plan_add(&plan, &api, HARNESS_GAME, villagers[i], choice[i < 3 ? 0 : 1], 0, &rng);
        }
    }
    h_check(plan.count == 0 && vvfp_ax_look_plan_commit(&plan, &api, HARNESS_GAME) && h_look_writes == 0,
            "Leave as is changes nobody and writes nothing");
    h_check(vvfp_ax_look_rows_command(VVFP_AX_LOOK_ROW(0) + 3, choice) && choice[0] == VVFP_HEAD_LOOK_OLD
            && choice[1] == VVFP_AX_LEAVE, "the men's Old changes the men's row only");
    h_check(vvfp_ax_look_rows_command(VVFP_AX_LOOK_ROW(1) + 4, choice) && choice[1] == VVFP_AX_RANDOM,
            "the women's Random");
    h_check(!vvfp_ax_look_rows_command(VVFP_AX_LOOK_ROW(1) + 5, choice), "the row's label is not a choice");
    for (k = 0; k < 40; ++k) {
        h_look_count = 0;
        h_look_writes = 0;
        plan.count = 0;
        for (i = 0; i < 6; ++i) {
            covered = i != 2 && i != 5;
            if (covered) {
                vvfp_ax_look_plan_add(&plan, &api, HARNESS_GAME, villagers[i], choice[i < 3 ? 0 : 1], 0, &rng);
            }
        }
        h_check(vvfp_ax_look_plan_commit(&plan, &api, HARNESS_GAME) && h_look_writes == 1,
                "the planned looks are kept in one write");
        h_check(h_look_get(HARNESS_GAME, villagers[0]) == VVFP_HEAD_LOOK_OLD
                && h_look_get(HARNESS_GAME, villagers[1]) == VVFP_HEAD_LOOK_OLD, "every covered man is Old");
        h_check(h_look_get(HARNESS_GAME, villagers[3]) == VVFP_HEAD_LOOK_YOUNG
                || h_look_get(HARNESS_GAME, villagers[3]) == VVFP_HEAD_LOOK_OLD, "Random is only Young or Old");
        h_check(h_look_get(HARNESS_GAME, villagers[4]) != VVFP_HEAD_LOOK_AUTO, "Random is never Auto");
        h_check(h_look_get(HARNESS_GAME, villagers[2]) == VVFP_HEAD_LOOK_AUTO
                && h_look_get(HARNESS_GAME, villagers[5]) == VVFP_HEAD_LOOK_AUTO, "nobody who is not covered");
        vvfp_ax_look_plan_undo(&plan, &api, HARNESS_GAME);
        h_check(h_look_get(HARNESS_GAME, villagers[0]) == VVFP_HEAD_LOOK_AUTO, "undone when the OK fails later");
    }
    /* Reset to original: Auto for a villager whose original is known, under a row left as is. */
    choice[0] = choice[1] = VVFP_AX_LEAVE;
    h_look_count = 0;
    h_look_put(villagers[0], VVFP_HEAD_LOOK_OLD);
    h_look_put(villagers[1], VVFP_HEAD_LOOK_OLD);
    plan.count = 0;
    vvfp_ax_look_plan_add(&plan, &api, HARNESS_GAME, villagers[0], choice[0], 1, &rng);
    vvfp_ax_look_plan_add(&plan, &api, HARNESS_GAME, villagers[1], choice[0], 0, &rng);
    vvfp_ax_look_plan_commit(&plan, &api, HARNESS_GAME);
    h_check(h_look_get(HARNESS_GAME, villagers[0]) == VVFP_HEAD_LOOK_AUTO
            && h_look_get(HARNESS_GAME, villagers[1]) == VVFP_HEAD_LOOK_OLD,
            "Reset to original makes the known villager Auto and leaves the unknown one");
}

/* ---- each game's per-villager window ---------------------------------------------------------------- */

#if HARNESS_GAME == 2
static unsigned char *h_record, *h_other, *h_player;

static int h_run(int sex, const UINT *script, int len) {
    memset(h_record, 0, 0x10000);
    *(int *)(h_record + VV2_SEX_OFFSET) = sex;
    *(int *)(h_record + VV_AGE_OFFSET) = 600;
    *(int *)(h_record + VV2_HEAD_OFFSET) = 3;
    *(int *)(h_record + VV2_BODY_OFFSET) = 4;
    *(int *)(h_other + VV2_HEAD_OFFSET) = 3;
    *(int *)(h_other + VV2_BODY_OFFSET) = 4;
    *(int *)(h_player + VV2_TECH_BALANCE_OFFSET) = 10000;
    vv2_mask_table_state = -1;
    h_script = script;
    h_script_len = len;
    return ShowVV2AppearanceChooser(h_player, h_record, 0);
}

#define H_HEAD() (*(int *)(h_record + VV2_HEAD_OFFSET))
#define H_BODY() (*(int *)(h_record + VV2_BODY_OFFSET))
#define H_TECH() (*(int *)(h_player + VV2_TECH_BALANCE_OFFSET))

static void h_game(void) {
    int s, c, k, result;
    {
        UINT script[] = { VVFP_AX_RANDOM_HEAD, VVFP_AX_RANDOM_BODY, VVFP_AX_RANDOM_MASK, VVFP_AX_UNDO, IDOK };
        h_fresh();
        result = h_run(1, script, 5);
        h_check(result == 0 && H_HEAD() == 3 && H_BODY() == 4 && H_TECH() == 10000,
                "Undo changes: nothing written, nothing charged");
    }
    {
        UINT script[] = { VVFP_AX_RANDOM_HEAD, VVFP_AX_RANDOM_BODY, IDCANCEL };
        h_fresh();
        result = h_run(1, script, 3);
        h_check(result == 0 && H_HEAD() == 3 && H_BODY() == 4 && H_TECH() == 10000, "Cancel writes nothing");
    }
    {
        UINT script[] = { VVFP_AX_RESET, IDOK };
        h_fresh();
        result = h_run(1, script, 2);
        h_check(h_unknown_said == 1 && result == 0 && H_HEAD() == 3 && H_TECH() == 10000,
                "no Original Look DLL: \"Original look not known\", nothing changed");
        h_fresh();
        h_original_there = 1;
        h_original_record = h_other;      /* someone else's original is known, not this villager's */
        result = h_run(1, script, 2);
        h_check(h_unknown_said == 1 && result == 0 && H_HEAD() == 3, "an unknown villager: nothing changed");
        h_fresh();
        h_original_there = 1;
        h_original_record = h_record;
        h_original_head = 9;
        h_original_body = 11;
        h_original_mask = 0;
        result = h_run(1, script, 2);
        h_check(result == 1 && H_HEAD() == 9 && H_BODY() == 11 && H_TECH() == 5000,
                "Reset to original: the known original, charged like any change");
        h_check(*(int *)(h_other + VV2_HEAD_OFFSET) == 3 && *(int *)(h_other + VV2_BODY_OFFSET) == 4,
                "and nobody else");
    }
    for (s = 0; s < 2; ++s) {
        for (c = 0; c < 5; ++c) {
            for (k = 0; k < 12; ++k) {
                UINT script[] = { (UINT)(VVFP_AX_HAIR_FIRST + c), IDOK };
                h_fresh();
                h_run(s ? 2 : 1, script, 2);
                h_check(h_in(caf_hair[s][c], caf_hair_n[s][c], H_HEAD()),
                        "a hair colour gives a head of that colour group and the villager's sex");
            }
        }
    }
    for (k = 0; k < 20; ++k) {
        UINT script[] = { VVFP_AX_RANDOM_HEAD, VVFP_AX_RANDOM_BODY, VVFP_AX_RANDOM_MASK, IDOK };
        h_fresh();
        h_run(1, script, 4);
        h_check(H_HEAD() >= 0 && H_HEAD() < VV2_APPEARANCE_COUNT && H_BODY() >= 0 && H_BODY() < VV2_APPEARANCE_COUNT
                && vv2_appearance_mask >= 0 && vv2_appearance_mask < VV2_MASK_COUNT, "the randoms stay in range");
    }
    {
        UINT script[] = { VVFP_AX_RANDOM_LOOK, IDOK };
        h_fresh();
        h_head_look_there = 1;
        result = h_run(1, script, 2);
        h_check(result == 1 && H_TECH() == 5000 && H_HEAD() == 3 && H_BODY() == 4
                && (h_look_get(2, h_record) == VVFP_HEAD_LOOK_YOUNG || h_look_get(2, h_record) == VVFP_HEAD_LOOK_OLD),
                "a look-only OK keeps the look (Young or Old) and is charged 5,000");
    }
    {
        UINT script[] = { VVFP_AX_RANDOM_LOOK, VVFP_AX_UNDO, IDOK };
        h_fresh();
        h_head_look_there = 1;
        result = h_run(1, script, 3);
        h_check(result == 0 && H_TECH() == 10000 && h_look_writes == 0, "Undo puts the look back: nothing kept");
    }
    {
        UINT script[] = { VVFP_AX_RANDOM_LOOK, IDCANCEL };
        h_fresh();
        h_head_look_there = 1;
        result = h_run(1, script, 2);
        h_check(result == 0 && H_TECH() == 10000 && h_look_writes == 0, "Cancel keeps no look");
    }
    /* Change Appearance for All's own plan, by sex, over the covered (active) records only. */
    {
        static vvfp_ax_look_plan plan;
        unsigned char *base = (unsigned char *)VirtualAlloc(NULL, (SIZE_T)VV2_RECORD_COUNT * VV2_RECORD_STRIDE,
                                                            MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        int i;
        h_fresh();
        h_head_look_there = 1;
        caf_look_offered = vvfp_head_look_find(2, &caf_look_api);
        for (i = 0; i < 4; ++i) {
            base[(size_t)i * VV2_RECORD_STRIDE + VV2_ACTIVE_OFFSET] = i != 3;   /* record 3 is not covered */
            *(int *)(base + (size_t)i * VV2_RECORD_STRIDE + VV2_SEX_OFFSET) = i < 2 ? 1 : 2;
        }
        caf_look[0] = VVFP_HEAD_LOOK_YOUNG;
        caf_look[1] = VVFP_AX_LEAVE;
        caf_reset = 0;
        caf_plan_looks(base, &plan);
        h_check(plan.count == 2 && plan.record[0] == base && plan.record[1] == base + VV2_RECORD_STRIDE,
                "For All: the men's row reaches the covered men only");
        caf_look[0] = VVFP_AX_LEAVE;
        caf_look[1] = VVFP_HEAD_LOOK_OLD;
        caf_plan_looks(base, &plan);
        h_check(plan.count == 1 && plan.record[0] == base + 2 * VV2_RECORD_STRIDE,
                "For All: the women's row reaches the covered women only");
        VirtualFree(base, 0, MEM_RELEASE);
    }
}

#elif HARNESS_GAME == 5
static void h_game(void) {
    int s, c, k, result, h, b, m;
    {
        UINT script[] = { VVFP_AX_RANDOM_HEAD, VVFP_AX_RANDOM_BODY, VVFP_AX_RANDOM_MASK, VVFP_AX_UNDO, IDOK };
        h_fresh();
        h = 3; b = 4; m = 2;
        h_script = script; h_script_len = 5;
        ShowAppearanceChooser(0, 600, &h, &b, &m);
        h_check(h == 3 && b == 4 && m == 2, "Undo changes: the router is handed back what it had (no change)");
    }
    {
        UINT script[] = { VVFP_AX_RANDOM_HEAD, VVFP_AX_RANDOM_MASK, IDCANCEL };
        h_fresh();
        h = 3; b = 4; m = 2;
        h_script = script; h_script_len = 3;
        result = ShowAppearanceChooser(0, 600, &h, &b, &m);
        h_check(result == 0 && h == 3 && b == 4 && m == 2, "Cancel hands nothing back");
    }
    {
        UINT script[] = { VVFP_AX_RESET, IDOK };
        h_fresh();
        h = 3; b = 4; m = 2;
        h_script = script; h_script_len = 2;
        ShowAppearanceChooser(0, 600, &h, &b, &m);
        h_check(h_unknown_said == 1 && h == 3 && b == 4 && m == 2,
                "no Original Look DLL: \"Original look not known\", nothing changed");
    }
    for (s = 0; s < 2; ++s) {
        for (c = 0; c < 5; ++c) {
            for (k = 0; k < 12; ++k) {
                UINT script[] = { (UINT)(VVFP_AX_HAIR_FIRST + c), IDOK };
                static const unsigned char *const groups[2][5] = {
                    { CAF_M_BLACK, CAF_M_BROWN, CAF_M_RED, CAF_M_BLONDE, CAF_M_OTHER },
                    { CAF_F_BLACK, CAF_F_BROWN, CAF_F_RED, CAF_F_BLONDE, CAF_F_OTHER } };
                static const int sizes[2][5] = {
                    { sizeof CAF_M_BLACK, sizeof CAF_M_BROWN, sizeof CAF_M_RED, sizeof CAF_M_BLONDE, sizeof CAF_M_OTHER },
                    { sizeof CAF_F_BLACK, sizeof CAF_F_BROWN, sizeof CAF_F_RED, sizeof CAF_F_BLONDE, sizeof CAF_F_OTHER } };
                h_fresh();
                h = 0; b = 0; m = 0;
                h_script = script; h_script_len = 2;
                ShowAppearanceChooser(s, 600, &h, &b, &m);
                h_check(h_in(groups[s][c], sizes[s][c], h),
                        "a hair colour gives a head of that colour group and the villager's sex");
            }
        }
    }
    for (k = 0; k < 20; ++k) {
        UINT script[] = { VVFP_AX_RANDOM_HEAD, VVFP_AX_RANDOM_BODY, VVFP_AX_RANDOM_MASK, IDOK };
        h_fresh();
        h = 0; b = 0; m = 0;
        h_script = script; h_script_len = 4;
        ShowAppearanceChooser(1, 600, &h, &b, &m);
        h_check(h >= 0 && h < APPEARANCE_HEAD_COUNT && b >= 0 && b < APPEARANCE_BODY_COUNT && m >= 0
                && m < APPEARANCE_MASK_COUNT, "the randoms stay in range (the mask pool: none or any of the five)");
    }
}

#elif HARNESS_GAME == 3
static unsigned char h_record[0x2000];

static void h_open(int sex) {
    vv3_appearance_sex = sex;
    vv3_appearance_age = 600;
    vv3_appearance_look_offered = 0;
    vv3_appearance_look = 0;
    vv3_appearance_head = vv3_appearance_open_head = 3;
    vv3_appearance_body = vv3_appearance_open_body = 4;
    vv3_appearance_mask = vv3_appearance_open_mask = 2;
    vv3_appearance_open_look = 0;
    vv3_appearance_record = h_record;
    vv3_appearance_rng = 77u;
}

static void h_game(void) {
    int s, c, k;
    {
        UINT script[] = { VVFP_AX_RANDOM_HEAD, VVFP_AX_RANDOM_BODY, VVFP_AX_RANDOM_MASK, VVFP_AX_UNDO, IDOK };
        h_fresh();
        h_open(0);
        h_press(vv3_appearance_dialog, script, 5);
        h_check(vv3_appearance_head == 3 && vv3_appearance_body == 4 && vv3_appearance_mask == 2,
                "Undo changes: every control as the villager looks now");
    }
    {
        UINT script[] = { VVFP_AX_RESET, IDOK };
        h_fresh();
        h_open(0);
        h_press(vv3_appearance_dialog, script, 2);
        h_check(h_unknown_said == 1 && vv3_appearance_head == 3 && vv3_appearance_body == 4,
                "no Original Look DLL: \"Original look not known\", nothing changed");
        h_fresh();
        h_original_there = 1;
        h_original_record = h_record;
        h_original_head = 12; h_original_body = 13; h_original_mask = 0;
        h_open(0);
        h_press(vv3_appearance_dialog, script, 2);
        h_check(h_end_result == 1 && vv3_appearance_head == 12 && vv3_appearance_body == 13
                && vv3_appearance_mask == 0, "Reset to original: the known original");
    }
    {
        UINT script[] = { VVFP_AX_RANDOM_HEAD, IDCANCEL };
        h_fresh();
        h_open(0);
        h_press(vv3_appearance_dialog, script, 2);
        h_check(h_end_result == 0, "Cancel ends with nothing to keep");
    }
    for (s = 0; s < 2; ++s) {
        for (c = 0; c < 5; ++c) {
            for (k = 0; k < 12; ++k) {
                UINT script[] = { (UINT)(VVFP_AX_HAIR_FIRST + c), IDOK };
                h_fresh();
                h_open(s);
                h_press(vv3_appearance_dialog, script, 2);
                /* vv3_appearance_sex 1 = female; the buckets are by sex. */
                h_check(h_in(s ? vv3_head_bucket_f[c] : vv3_head_bucket_m[c],
                             s ? vv3_head_bucket_f_count[c] : vv3_head_bucket_m_count[c], vv3_appearance_head),
                        "a hair colour gives a head of that colour group and the villager's sex");
            }
        }
    }
    for (k = 0; k < 20; ++k) {
        UINT script[] = { VVFP_AX_RANDOM_HEAD, VVFP_AX_RANDOM_BODY, VVFP_AX_RANDOM_MASK, IDOK };
        h_fresh();
        h_open(1);
        h_press(vv3_appearance_dialog, script, 4);
        h_check(vv3_appearance_head < VV3_HEAD_COUNT && vv3_appearance_body < VV3_BODY_COUNT
                && vv3_appearance_mask < VV3_MASK_COUNT, "the randoms stay in range");
    }
}

#else
/* A New Home and The Tree of Life write the live record from the dialog, and every button reads the mask
   table, which lives in the game's own memory (the mask manager, the side-table and its sidecar): their
   per-villager buttons cannot be driven here.  tests/test_change_appearance_extras.py checks their source;
   in play they are UNCONFIRMED. */
static void h_game(void) {
}
#endif

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
#if HARNESS_GAME == 2
    h_record = (unsigned char *)VirtualAlloc(NULL, 0x10000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    h_other = (unsigned char *)VirtualAlloc(NULL, 0x10000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    h_player = (unsigned char *)VirtualAlloc(NULL, 0x40000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
#endif
    h_look_rows();
    h_game();
    printf("game %d: %d checks, %d failures\n", HARNESS_GAME, h_checks, h_failures);
    if (h_checks == 0) {
        return 2;
    }
    return h_failures == 0 ? 0 : 1;
}
