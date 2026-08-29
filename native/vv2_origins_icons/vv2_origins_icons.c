#define VV_AGE_OFFSET 0x530
#define VV_SKILL_FARMING_OFFSET 0x7E4
#define VV_SKILL_BUILDING_OFFSET 0x7E8
#define VV_SKILL_RESEARCH_OFFSET 0x7EC
#define VV_SKILL_HEALING_OFFSET 0x7F0
#define VV_SKILL_PARENTING_OFFSET 0x7F4
#define VV_LIKES_OFFSET 0x5F0
#define VV_DISLIKES_OFFSET 0x6E8
#define VV_LIKE_SLOT_COUNT 62
#define VV_ALREADY_LIKES_TEXT "Already 62 likes."
#include "../vv1_origins_icons/vv1_origins_icons.c"
#include <shlobj.h>   /* SHGetFolderPathA for the sidecar path (link shell32) */

/* Task9-style prompt action / result codes and forward declarations, hoisted so
   the ApplyVV2* reporters below can route through the shared result renderer
   defined later in this file. */
enum {
    VV2_ACT_TIME_WARP = 0, VV2_ACT_ISLAND = 1, VV2_ACT_BARREL = 2,
    VV2_ACT_TECH_DOUBLER = 3, VV2_ACT_FOOD_DOUBLER = 4, VV2_ACT_CURE = 5,
    VV2_ACT_RUNNING_ALL = 6, VV2_ACT_MASTERY_ALL = 7, VV2_ACT_AGE_ALL = 8,
    VV2_ACT_COLLECT_COMPLETE = 9, VV2_ACT_COLLECT_RESET = 10,
    VV2_ACT_DIVIDE_PARENTING = 11, VV2_ACT_DIVIDE_NO_PARENTING = 12,
    VV2_ACT_APPEARANCE_ALL = 13,
    VV2_ACT_DETAIL_YOUTH = 100, VV2_ACT_DETAIL_MASTERY = 101,
    VV2_ACT_DETAIL_RUNNING = 102, VV2_ACT_DETAIL_AGE18 = 103,
    VV2_ACT_DETAIL_APPEARANCE = 104
};
enum {
    VV2_RES_SUCCESS = 0, VV2_RES_NO_CHANGE = 1, VV2_RES_INSUFFICIENT = 2,
    VV2_RES_INVALID = 3, VV2_RES_NO_SLOT = 4, VV2_RES_REMOVED = 5,
    VV2_RES_PURCHASED = 6, VV2_RES_POP_FULL = 7, VV2_RES_DISLIKE_ONLY = 8
};
__declspec(dllexport) void __stdcall ShowVV2UpgradeResult(
    int action, int status, unsigned int amount_a, unsigned int amount_b,
    unsigned int amount_c, unsigned int amount_d
);

/* ---------- VV2 self-contained upgrade menus + Change Appearance ----------
   VV2 uses its own dialog resources (211 tech, 212 villager, 213 Change
   Appearance) and its own dialog procs/exports so nothing here touches the
   shared VV1 dialogs, symbols, or resource IDs. The shared enums (ID_BUY_FIRST,
   ID_CHECK_FIRST, STATE_*) come from the included base source. */

#define IDD_VV2_TECH       211
#define IDD_VV2_VILLAGER   212
#define IDD_VV2_APPEARANCE 213

/* VV2 tech screen now carries 14 rows (two-column layout): the 9 shared Origins
   upgrades, Complete all Collections (1009), Reset all Collections (1010), the
   two Equal Division of Labor rows (1011 Includes Parenting, 1012 No Parenting),
   and Change Appearance for All (1013).  The shared ID_BUY_LAST (1008) only
   bounds the VV1 dialogs, so the VV2 proc uses its own upper bound instead of
   editing the shared enum. */
#define VV2_TECH_ROW_COUNT 14
#define ID_VV2_BUY_LAST    1013

/* The game can run fullscreen as a topmost SDL window at a resolution smaller
   than the desktop.  Our modal dialogs use DS_CENTER so Windows centers them on
   the display; this additionally lifts them above the fullscreen surface and to
   the foreground so they are visible and clickable in fullscreen.  Called from
   each dialog's WM_INITDIALOG. */
static void vv2_surface_dialog(HWND window) {
    SetWindowPos(
        window, HWND_TOPMOST, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
    );
    SetForegroundWindow(window);
}

/* The game is SDL2-based; in exclusive fullscreen SDL minimizes the window when
   it loses focus to our modal dialog, dropping the player to the desktop.  Turn
   off SDL's minimize-on-focus-loss so the game stays fullscreen behind the
   dialog.  SDL2.dll is already loaded by the game and re-reads the hint on
   focus loss, so setting it before we show a dialog is enough.  Call this
   BEFORE creating any dialog / message box. */
static void vv2_prep_fullscreen(void) {
    HMODULE sdl = GetModuleHandleA("SDL2.dll");
    if (sdl != NULL) {
        typedef int(__cdecl * set_hint_t)(const char *, const char *);
        set_hint_t set_hint = (set_hint_t)GetProcAddress(sdl, "SDL_SetHint");
        if (set_hint != NULL) {
            set_hint("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0");
        }
    }
}

/* VV2 upgrade dialog: every row stays visible and buyable. The game re-checks
   the selected villager / village state at click time and no-ops with a
   message (no charge) when there is nothing to do, so no row is hidden or
   disabled. The checkmark glyph is informational: it marks an already-
   satisfied row. */
static INT_PTR CALLBACK vv2_upgrade_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        int villager_menu = (lparam & STATE_VILLAGER) != 0;
        int village_wide_buy = (lparam & STATE_VILLAGE_WIDE_BUY) != 0;
        int row_count = villager_menu ? 5 : VV2_TECH_ROW_COUNT;
        int row;
        for (row = 0; row < 9; ++row) {
            ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_HIDE);
        }
        for (row = 0; row < row_count; ++row) {
            int satisfied = (lparam & (1 << row)) != 0;
            if (satisfied) {
                ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);
            }
            if (!villager_menu && satisfied && !(village_wide_buy && row >= 6)) {
                /* Owned Tech/Food Doubler: offer the removal toggle. */
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Remove");
            } else {
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Buy");
            }
            EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), TRUE);
        }
        vv2_surface_dialog(window);
        return TRUE;
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command >= ID_BUY_FIRST && command <= ID_VV2_BUY_LAST) {
            EndDialog(window, (INT_PTR)(command - ID_BUY_FIRST));
            return TRUE;
        }
        if (command == IDCANCEL) {
            EndDialog(window, -1);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, -1);
        return TRUE;
    }
    return FALSE;
}

__declspec(dllexport) int __stdcall ShowVV2UpgradeMenuState(
    int villager_menu,
    int dialog_state
) {
    int resource = villager_menu ? IDD_VV2_VILLAGER : IDD_VV2_TECH;
    vv2_prep_fullscreen();
    if (villager_menu) {
        dialog_state |= STATE_VILLAGER;
    }
    return (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(resource),
        GetForegroundWindow(),
        vv2_upgrade_dialog,
        dialog_state
    );
}

/* Full Heal / Cure All result message. sick = villagers whose sickness was
   cleared; health = villagers restored to full health. When both are zero the
   caller charged nothing. */
__declspec(dllexport) void __stdcall ShowVV2CureResult(int sick, int health) {
    char message[256];
    if (sick == 0 && health == 0) {
        MessageBoxA(
            GetForegroundWindow(),
            "Everyone is at full health already. No villagers are sick. "
            "No tech points have been deducted.",
            "Origins Upgrades",
            MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
        );
        return;
    }
    wsprintfA(
        message,
        "Cured sickness from %d villagers.\r\n\r\n"
        "Restored %d villagers to full health.",
        sick, health
    );
    MessageBoxA(
        GetForegroundWindow(), message, "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
}

/* ---- Village-wide Grant Running / Grant Full Mastery, with counted reports.
   `base` is the certified record array (sub_44F4E0 result): 256 records, stride
   0xE48C, record 0 at base+0.  Field offsets match the whole-village helper:
   +0x30 active byte, +0x52C health, +0x558 special flag, +0x5F0 likes[62],
   +0x6E8 dislikes[62], +0x7E4 the five skills.  A slot holds -1 when empty and
   a positive preference id otherwise; running is id 38. ---- */
#define VV2_RECORD_STRIDE   0xE48C
#define VV2_RECORD_COUNT    256
#define VV2_ACTIVE_OFFSET   0x30
#define VV2_HEALTH_OFFSET   0x52C
#define VV2_SPECIAL_OFFSET  0x558
#define VV2_LIKES_OFFSET    0x5F0
#define VV2_DISLIKES_OFFSET 0x6E8
#define VV2_PREF_SLOTS      62
#define VV2_RUNNING_PREF    38
#define VV2_LIKE_CAP        3
#define VV2_SKILL0_OFFSET   0x7E4

static int vv2_record_eligible(const unsigned char *record) {
    if (record[VV2_ACTIVE_OFFSET] == 0) {
        return 0;
    }
    if (*(const int *)(record + VV2_HEALTH_OFFSET) <= 0) {
        return 0;
    }
    if (record[VV2_SPECIAL_OFFSET] != 0) {
        return 0;
    }
    return 1;
}

/* Clear Running from a villager's Dislike slots; returns 1 if any were cleared.
   Called for every eligible villager: even one whose Likes are full (so Running
   can't be added) has their Running dislike removed, and is then reported under
   BOTH "removed a Running dislike" and "skipped: already have 3 likes" so the
   player sees exactly what happened. */
static int vv2_remove_running_dislikes(int *dislikes) {
    int j, removed = 0;
    for (j = 0; j < VV2_PREF_SLOTS; ++j) {
        if (dislikes[j] == VV2_RUNNING_PREF) {
            dislikes[j] = -1;
            removed = 1;
        }
    }
    return removed;
}

__declspec(dllexport) int __stdcall ApplyVV2RunningToAll(unsigned char *base) {
    int already_like = 0, full_likes = 0, granted = 0, removed_dislike = 0;
    int i, j;
    unsigned char *record = base;
    if (base == 0) {
        return 0;
    }
    for (i = 0; i < VV2_RECORD_COUNT; ++i, record += VV2_RECORD_STRIDE) {
        int *likes, *dislikes;
        int has_running = 0, occupied = 0, free_slot = -1;
        if (!vv2_record_eligible(record)) {
            continue;
        }
        dislikes = (int *)(record + VV2_DISLIKES_OFFSET);
        likes = (int *)(record + VV2_LIKES_OFFSET);
        for (j = 0; j < VV2_PREF_SLOTS; ++j) {
            int value = likes[j];
            if (value == VV2_RUNNING_PREF) {
                has_running = 1;
            } else if (value == -1) {
                if (free_slot < 0) {
                    free_slot = j;
                }
            } else if (value > 0) {
                ++occupied;
            }
        }
        /* Always clear a Running dislike, even when the Like can't be added, and
           count it -- a full-Likes villager with a Running dislike is reported
           under both "removed a dislike" and "skipped: already have 3 likes". */
        if (vv2_remove_running_dislikes(dislikes)) {
            ++removed_dislike;
        }
        if (has_running) {
            ++already_like;
        } else if (occupied >= VV2_LIKE_CAP || free_slot < 0) {
            ++full_likes;
        } else {
            likes[free_slot] = VV2_RUNNING_PREF;
            ++granted;
        }
    }
    if (granted == 0 && removed_dislike == 0) {
        ShowVV2UpgradeResult(VV2_ACT_RUNNING_ALL, VV2_RES_NO_CHANGE, 0, 0, 0, 0);
        return 0;
    }
    ShowVV2UpgradeResult(
        VV2_ACT_RUNNING_ALL, VV2_RES_SUCCESS,
        (unsigned int)granted, (unsigned int)removed_dislike,
        (unsigned int)already_like, (unsigned int)full_likes
    );
    return 1;
}

__declspec(dllexport) int __stdcall ApplyVV2MasteryToAll(unsigned char *base) {
    int granted = 0, already_mastered = 0;
    int i;
    unsigned char *record = base;
    if (base == 0) {
        return 0;
    }
    for (i = 0; i < VV2_RECORD_COUNT; ++i, record += VV2_RECORD_STRIDE) {
        int *skills;
        if (!vv2_record_eligible(record)) {
            continue;
        }
        skills = (int *)(record + VV2_SKILL0_OFFSET);
        if (skills[0] == 100 && skills[1] == 100 && skills[2] == 100 &&
            skills[3] == 100 && skills[4] == 100) {
            ++already_mastered;
        } else {
            skills[0] = 100;
            skills[1] = 100;
            skills[2] = 100;
            skills[3] = 100;
            skills[4] = 100;
            ++granted;
        }
    }
    if (granted == 0) {
        ShowVV2UpgradeResult(VV2_ACT_MASTERY_ALL, VV2_RES_NO_CHANGE, 0, 0, 0, 0);
        return 0;
    }
    ShowVV2UpgradeResult(
        VV2_ACT_MASTERY_ALL, VV2_RES_SUCCESS,
        (unsigned int)granted, (unsigned int)already_mastered, 0, 0
    );
    return 1;
}

/* Set every eligible villager's raw age field (+0x530) to exactly 360 (18
   years) regardless of current age.  Per the spec this touches ONLY the raw age
   field -- never the paired age field or pregnancy timer.  Returns 1 if any
   villager changed (so the Tech menu charges), 0 if all were already 18. */
__declspec(dllexport) int __stdcall ApplyVV2AgeToAll(unsigned char *base) {
    int changed = 0, already = 0;
    int i;
    unsigned char *record = base;
    if (base == 0) {
        return 0;
    }
    for (i = 0; i < VV2_RECORD_COUNT; ++i, record += VV2_RECORD_STRIDE) {
        int *age;
        if (!vv2_record_eligible(record)) {
            continue;
        }
        age = (int *)(record + 0x530);
        if (*age != 360) {
            *age = 360;
            ++changed;
        } else {
            ++already;
        }
    }
    if (changed == 0) {
        ShowVV2UpgradeResult(VV2_ACT_AGE_ALL, VV2_RES_NO_CHANGE, 0, 0, 0, 0);
        return 0;
    }
    ShowVV2UpgradeResult(VV2_ACT_AGE_ALL, VV2_RES_SUCCESS,
                         (unsigned int)changed, (unsigned int)already, 0, 0);
    return 1;
}

/* ---- Complete (mode 9) / Reset (mode 10) all Collections.  `player` is the
   Tech menu's game object: 48 collectible found-flags at +0x2E720, and the
   per-group goal "pending" bytes at +0x20F..+0x213.  Complete fills the flags
   and enqueues the four group goals plus the master goal through the stock goal
   queue (sub_4257A0, __thiscall on the player object) exactly the way the stock
   deposit handler does; Reset clears the flags and re-arms those pending bytes
   so a later real completion can fire them again. ---- */
/* sub_4257A0 is __thiscall (player in ECX, message id + flag on the stack,
   callee-cleaned).  Call it from C via __fastcall with an ignored EDX slot: the
   player lands in ECX, the ignored value in EDX, and message id + flag spill to
   the stack exactly where the thiscall expects them. */
typedef int(__fastcall *vv2_fire_goal_t)(
    void *player, int edx_ignored, int message_id, int flag
);

__declspec(dllexport) int __stdcall ApplyVV2Collections(
    unsigned char *player,
    int mode
) {
    static const int goal_pending[5] = {0x20F, 0x210, 0x211, 0x212, 0x213};
    static const int goal_message[5] = {0x1DE, 0x1DF, 0x1E0, 0x1E1, 0x1E2};
    unsigned char want = (mode == 9) ? 1 : 0;
    int action = (mode == 9) ? VV2_ACT_COLLECT_COMPLETE : VV2_ACT_COLLECT_RESET;
    unsigned int goals = 0;
    int changed = 0;
    int i;
    if (player == 0) {
        return 0;
    }
    for (i = 0; i < 48; ++i) {
        if (player[0x2E720 + i] != want) {
            player[0x2E720 + i] = want;
            changed = 1;
        }
    }
    if (mode == 9) {
        vv2_fire_goal_t fire = (vv2_fire_goal_t)(UINT_PTR)0x004257A0;
        for (i = 0; i < 5; ++i) {
            if (player[goal_pending[i]] != 0) {
                player[goal_pending[i]] = 0;
                fire(player, 0, goal_message[i], 1);
                ++goals;
                changed = 1;
            }
        }
    } else {
        for (i = 0; i < 5; ++i) {
            if (player[goal_pending[i]] != 1) {
                player[goal_pending[i]] = 1;
                changed = 1;
            }
        }
    }
    /* Nothing to do (already fully found, or already fully cleared): report it
       and charge nothing, matching the other village-wide rows. */
    if (!changed) {
        ShowVV2UpgradeResult(action, VV2_RES_NO_CHANGE, 0, 0, 0, 0);
        return 0;
    }
    ShowVV2UpgradeResult(action, VV2_RES_SUCCESS, goals, 0, 0, 0);
    return 1;
}

/* ---- Equal Division of Labor -------------------------------------------------
   Set every eligible villager's job-preference checkmark round-robin so the
   population is split evenly across the professions.  Record fields: sex at
   +0x538 (1 = male, otherwise female), job preference at +0x7F8 (0 none,
   1 Farming, 2 Building, 3 Research, 4 Healing, 5 Parenting/Breeding).  Each sex
   is round-robined so the male/female split stays balanced, and the female cycle
   continues from where the male cycle ends (female seats start at the male
   total) so that when both counts leave a remainder they don't stack onto the
   same professions -- the overall per-profession total then differs by at most
   one.  `parenting` picks 5 professions
   (Farmer..Breeding) or 4 (no Breeding).  The preference is overwritten
   unconditionally -- there is no "already correct" state -- so the count is
   simply how many villagers were eligible.  VV2 has no Golden Child, so nothing
   is excluded.  Eligibility here is deliberately EVERYONE alive -- children of
   any age, nursing mothers, and adults -- so it uses only the active + positive-
   health checks, not the special-state filter the other village-wide rows apply.
   The per-profession, per-sex breakdown does not fit ShowVV2UpgradeResult's four
   counts, so this composes and shows its own result. ---- */
#define VV2_SEX_OFFSET        0x538
#define VV2_PREFERENCE_OFFSET 0x7F8

__declspec(dllexport) int __stdcall ApplyVV2EqualDivision(
    unsigned char *base,
    int parenting
) {
    static const char *const profession_name[5] = {
        "Farming", "Building", "Research", "Healing", "Breeding"
    };
    int professions = parenting ? 5 : 4;
    int male_seat = 0, female_seat, male_total = 0;
    int male_count[5] = {0, 0, 0, 0, 0};
    int female_count[5] = {0, 0, 0, 0, 0};
    int total = 0;
    int i, p;
    char message[512];
    char line[128];
    unsigned char *record = base;
    if (base == 0) {
        return 0;
    }
    /* First pass: count eligible males so the female cycle can continue from the
       male total, keeping the overall split even (see the header comment). */
    for (i = 0; i < VV2_RECORD_COUNT; ++i, record += VV2_RECORD_STRIDE) {
        if (record[VV2_ACTIVE_OFFSET] == 0) {
            continue;
        }
        if (*(int *)(record + VV2_HEALTH_OFFSET) <= 0) {
            continue;
        }
        if (*(int *)(record + VV2_SEX_OFFSET) == 1) {
            ++male_total;
        }
    }
    female_seat = male_total;
    record = base;
    for (i = 0; i < VV2_RECORD_COUNT; ++i, record += VV2_RECORD_STRIDE) {
        int seat;
        if (record[VV2_ACTIVE_OFFSET] == 0) {
            continue;
        }
        if (*(int *)(record + VV2_HEALTH_OFFSET) <= 0) {
            continue;
        }
        if (*(int *)(record + VV2_SEX_OFFSET) == 1) {   /* male */
            seat = male_seat % professions;
            ++male_seat;
            ++male_count[seat];
        } else {                                         /* female */
            seat = female_seat % professions;
            ++female_seat;
            ++female_count[seat];
        }
        *(int *)(record + VV2_PREFERENCE_OFFSET) = seat + 1;   /* 1..5 */
        ++total;
    }
    if (total == 0) {
        MessageBoxA(
            GetForegroundWindow(),
            "No villagers were eligible. No tech points have been deducted.",
            "Origins Upgrades",
            MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
        );
        return 0;
    }
    wsprintfA(message, "Set %u Villagers' Job Preferences.", (unsigned int)total);
    for (p = 0; p < professions; ++p) {
        wsprintfA(line, "\r\n\r\n%s: %u Villagers (%u Male, %u Female).",
                  profession_name[p],
                  (unsigned int)(male_count[p] + female_count[p]),
                  (unsigned int)male_count[p], (unsigned int)female_count[p]);
        lstrcatA(message, line);
    }
    MessageBoxA(
        GetForegroundWindow(), message, "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
    return 1;
}

/* ---- VV5 Task9-style purchase prompts for every VV2 upgrade -----------------
   Confirm: an OK/Cancel box stating the action and its cost (with counts for
   Full Heal / Cure All), ending "Press OK to confirm, or Cancel." Result:
   status-based, counted where meaningful, else "<Action> completed." Every
   no-change / guard outcome ends "No tech points have been deducted." "Villager"
   and the named upgrades are capitalized, and counts use correct singular /
   plural. All wording lives here (the exe payload string cave is full).

   action codes: tech rows 0..10, detail rows 100..104. ---- */
static const char *vv2_action_name(int action) {
    switch (action) {
    case VV2_ACT_TIME_WARP: return "Time Warp";
    case VV2_ACT_ISLAND: return "Island Event";
    case VV2_ACT_BARREL: return "Barrel of Babies";
    case VV2_ACT_TECH_DOUBLER: return "Tech Point Doubler";
    case VV2_ACT_FOOD_DOUBLER: return "Food Point Doubler";
    case VV2_ACT_CURE: return "Full Heal / Cure All";
    case VV2_ACT_RUNNING_ALL: return "Grant Running to All Villagers";
    case VV2_ACT_MASTERY_ALL: return "Grant Full Mastery to All Villagers";
    case VV2_ACT_AGE_ALL: return "All Villagers are Exactly 18";
    case VV2_ACT_COLLECT_COMPLETE: return "Complete All Collections";
    case VV2_ACT_COLLECT_RESET: return "Reset All Collections";
    case VV2_ACT_DIVIDE_PARENTING:
        return "Equal Division of Labor (Includes Parenting)";
    case VV2_ACT_DIVIDE_NO_PARENTING:
        return "Equal Division of Labor (No Parenting)";
    case VV2_ACT_APPEARANCE_ALL: return "Change Appearance for All";
    case VV2_ACT_DETAIL_YOUTH: return "Grant Youth";
    case VV2_ACT_DETAIL_MASTERY: return "Grant Full Mastery";
    case VV2_ACT_DETAIL_RUNNING: return "Grant Running";
    case VV2_ACT_DETAIL_AGE18: return "Set Age to 18";
    case VV2_ACT_DETAIL_APPEARANCE: return "Change Appearance";
    default: return "Origins upgrade";
    }
}

static const char *vv2_villager_word(unsigned int count) {
    return count == 1 ? "Villager" : "Villagers";
}

static const char *vv2_result_title(int action) {
    return action >= 100 ? "Villager Upgrades" : "Origins Upgrades";
}

static unsigned int vv2_action_price(int action) {
    switch (action) {
    case VV2_ACT_TIME_WARP: return 50000;
    case VV2_ACT_ISLAND: return 30000;
    case VV2_ACT_BARREL: return 75000;
    case VV2_ACT_TECH_DOUBLER: return 500000;
    case VV2_ACT_FOOD_DOUBLER: return 500000;
    case VV2_ACT_CURE: return 30000;
    case VV2_ACT_RUNNING_ALL: return 1000000;
    case VV2_ACT_MASTERY_ALL: return 1000000;
    case VV2_ACT_AGE_ALL: return 1000000;
    case VV2_ACT_COLLECT_COMPLETE: return 1000000;
    case VV2_ACT_COLLECT_RESET: return 1000000;
    case VV2_ACT_DIVIDE_PARENTING: return 1000000;
    case VV2_ACT_DIVIDE_NO_PARENTING: return 1000000;
    case VV2_ACT_APPEARANCE_ALL: return 450000;
    case VV2_ACT_DETAIL_YOUTH: return 50000;
    case VV2_ACT_DETAIL_MASTERY: return 100000;
    case VV2_ACT_DETAIL_RUNNING: return 40000;
    case VV2_ACT_DETAIL_AGE18: return 50000;
    case VV2_ACT_DETAIL_APPEARANCE: return 5000;
    default: return 0;
    }
}

/* Task9-style purchase confirmation: an OK/Cancel box naming the action and its
   cost.  Returns 1 on OK, 0 on Cancel.  The payload passes only the action id;
   the price table above mirrors the payload's tech_costs / detail_costs. */
__declspec(dllexport) int __stdcall ConfirmVV2Upgrade(int action) {
    char message[256];
    wsprintfA(
        message,
        "Do you want to buy %s for %u tech points?\r\nPress OK to confirm, "
        "or Cancel.",
        vv2_action_name(action), vv2_action_price(action)
    );
    return MessageBoxA(
        GetForegroundWindow(), message, vv2_result_title(action),
        MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND
    ) == IDOK;
}

__declspec(dllexport) void __stdcall ShowVV2UpgradeResult(
    int action,
    int status,
    unsigned int amount_a,
    unsigned int amount_b,
    unsigned int amount_c,
    unsigned int amount_d
) {
    char message[512];
    char line[160];
    const char *name = vv2_action_name(action);

    if (status == VV2_RES_SUCCESS) {
        switch (action) {
        case VV2_ACT_CURE:
            wsprintfA(
                message,
                "Cleared sickness from %u %s and restored full health to %u %s.",
                amount_a, vv2_villager_word(amount_a),
                amount_b, vv2_villager_word(amount_b)
            );
            break;
        case VV2_ACT_RUNNING_ALL:
            /* a=granted, b=removed dislike, c=already like, d=at 3-like cap */
            wsprintfA(message, "Granted Running to %u %s.",
                      amount_a, vv2_villager_word(amount_a));
            wsprintfA(line, "\r\n\r\nRemoved a Running dislike from %u %s.",
                      amount_b, vv2_villager_word(amount_b));
            lstrcatA(message, line);
            wsprintfA(line, "\r\n\r\nSkipped %u %s: already like Running.",
                      amount_c, vv2_villager_word(amount_c));
            lstrcatA(message, line);
            wsprintfA(line, "\r\n\r\nSkipped %u %s: already have 3 likes.",
                      amount_d, vv2_villager_word(amount_d));
            lstrcatA(message, line);
            break;
        case VV2_ACT_MASTERY_ALL:
            /* a=granted, b=already mastered */
            wsprintfA(message, "Granted Full Mastery to %u %s.",
                      amount_a, vv2_villager_word(amount_a));
            wsprintfA(line, "\r\n\r\nSkipped %u %s: already fully mastered.",
                      amount_b, vv2_villager_word(amount_b));
            lstrcatA(message, line);
            break;
        case VV2_ACT_AGE_ALL:
            /* a=set to 18, b=already 18 */
            wsprintfA(message, "Set %u %s to Age 18.",
                      amount_a, vv2_villager_word(amount_a));
            wsprintfA(line, "\r\n\r\nSkipped %u %s: already exactly 18.",
                      amount_b, vv2_villager_word(amount_b));
            lstrcatA(message, line);
            break;
        case VV2_ACT_COLLECT_COMPLETE:
            wsprintfA(
                message,
                "Marked all 48 collectibles as found and triggered %u "
                "collection goal%s.",
                amount_a, amount_a == 1 ? "" : "s"
            );
            break;
        case VV2_ACT_COLLECT_RESET:
            lstrcpyA(message, "Cleared all 48 collectibles.");
            break;
        default:
            wsprintfA(message, "%s completed.", name);
            break;
        }
    } else if (status == VV2_RES_NO_CHANGE) {
        switch (action) {
        case VV2_ACT_RUNNING_ALL:
            lstrcpyA(message,
                     "Everyone already likes running, or has full Likes slots. "
                     "No tech points have been deducted.");
            break;
        case VV2_ACT_MASTERY_ALL:
            lstrcpyA(message,
                     "Everyone has already mastered their skills. No tech "
                     "points have been deducted.");
            break;
        case VV2_ACT_AGE_ALL:
            lstrcpyA(message,
                     "Everyone is already exactly 18. No tech points have been "
                     "deducted.");
            break;
        case VV2_ACT_DETAIL_YOUTH:
            lstrcpyA(message,
                     "This villager is already full of youth. No tech points "
                     "have been deducted.");
            break;
        case VV2_ACT_DETAIL_MASTERY:
            lstrcpyA(message,
                     "This villager is already fully mastered. No tech points "
                     "have been deducted.");
            break;
        case VV2_ACT_DETAIL_RUNNING:
            lstrcpyA(message,
                     "This villager already likes Running. No tech points have "
                     "been deducted.");
            break;
        case VV2_ACT_DETAIL_AGE18:
            lstrcpyA(message,
                     "No changes were needed. No tech points have been "
                     "deducted.");
            break;
        case VV2_ACT_DETAIL_APPEARANCE:
            lstrcpyA(message,
                     "The appearance is unchanged. No tech points have been "
                     "deducted.");
            break;
        case VV2_ACT_COLLECT_COMPLETE:
            lstrcpyA(message,
                     "All collectibles are already found. No tech points have "
                     "been deducted.");
            break;
        case VV2_ACT_COLLECT_RESET:
            lstrcpyA(message,
                     "The collections are already cleared. No tech points have "
                     "been deducted.");
            break;
        default:
            wsprintfA(message,
                      "%s is already complete. No tech points have been "
                      "deducted.", name);
            break;
        }
    } else if (status == VV2_RES_INSUFFICIENT) {
        lstrcpyA(message, "Not enough tech points.");
    } else if (status == VV2_RES_INVALID) {
        lstrcpyA(message,
                 "No valid living villager is selected. No tech points have "
                 "been deducted.");
    } else if (status == VV2_RES_NO_SLOT) {
        lstrcpyA(message,
                 "This villager already has full Likes slots. Running can not "
                 "be added.");
    } else if (status == VV2_RES_REMOVED) {
        wsprintfA(message, "%s was removed. No refund was issued.", name);
    } else if (status == VV2_RES_PURCHASED) {
        wsprintfA(message, "%s was purchased.", name);
    } else if (status == VV2_RES_POP_FULL) {
        lstrcpyA(message,
                 "Village population is close to its maximum. The Barrel of "
                 "Babies needs room for 3 children. No tech points have been "
                 "deducted.");
    } else if (status == VV2_RES_DISLIKE_ONLY) {
        lstrcpyA(message,
                 "This villager's Likes are full, so Running could not be "
                 "added, but its Running dislike was removed. No tech points "
                 "have been deducted.");
    } else {
        lstrcpyA(message, "The action stopped without a verified charge.");
    }

    MessageBoxA(
        GetForegroundWindow(), message, vv2_result_title(action),
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
}

/* ---- Barrel of Babies capacity gate ----------------------------------------
   The Barrel event drops in 3 children, so before we cue it (and before any
   tech points are deducted) confirm the village can actually hold 3 more.  We
   ask the game the same question its own birth code asks: sub_425860 returns
   the current population demand (living villagers plus pending / nursing
   babies), and the cap is whatever the population predicate at 0x44B310
   enforces for the build the player is running.

   That cap is dynamic: the Fun Patcher offers three population modes, and each
   edits 0x44B310 itself, so we read those edits live rather than assume the
   stock formula:
     - Stock / No Population Increase: base 90 plus a 0-25 collection bonus
       (each of the four 12-item collections adds 5; all four counts as 25).
       Both mode sites keep their stock 0x83 opcode.
     - Collection Progression detours the base add at 0x44B3AD (stock opcode
       0x83 -> 0xEB), raising the base from 90 to 231 while keeping the bonus.
     - Immediate Fixed rewrites the collection-bonus compare at 0x44B378 (stock
       opcode 0x83 -> 0xBF) so the bonus is discarded and the maximum is a flat
       256 at every collection state.
   The mode sites and their patched opcodes come straight from the population
   variants in data/builds.json; test_vv2_barrel_gate_matches_population_modes
   keeps this in sync.  If fewer than 3 slots remain, show the "close to
   maximum" notice and return 0 so the payload skips the charge and the cue;
   otherwise return 1.  `pool` is the Tech-menu game object (EDI): it carries
   both the +0x305A4 record-pool chain sub_425860 walks and the +0x2E720
   collectible flags sub_426120 reads. */
typedef int(__fastcall *vv2_pop_demand_t)(void *pool, int edx_ignored);
typedef char(__fastcall *vv2_collection_done_t)(
    void *pool, int edx_ignored, int start
);

static int vv2_population_cap(vv2_collection_done_t collection_done,
                              void *pool) {
    const unsigned char *fixed_site = (const unsigned char *)(UINT_PTR)0x0044B378;
    const unsigned char *base_site = (const unsigned char *)(UINT_PTR)0x0044B3AD;
    int bonus;
    if (fixed_site[0] == 0xBF) {
        /* Immediate Fixed: collection bonus overwritten with a constant, so the
           maximum is a flat 256 regardless of collections. */
        return 256;
    }
    /* Stock and Collection Progression both keep the 0-25 collection bonus. */
    bonus = 0;
    if (collection_done(pool, 0, 0x00)) {
        bonus += 5;
    }
    if (collection_done(pool, 0, 0x0C)) {
        bonus += 5;
    }
    if (collection_done(pool, 0, 0x18)) {
        bonus += 5;
    }
    if (collection_done(pool, 0, 0x24)) {
        bonus += 5;
    }
    if (bonus == 20) {
        bonus = 25;
    }
    /* Stock base is 90 (add edi,0x5a); Collection Progression's detour raises
       it to 231. */
    return (base_site[0] == 0xEB ? 231 : 90) + bonus;
}

__declspec(dllexport) int __stdcall GateVV2Barrel(void *pool) {
    vv2_pop_demand_t population_demand =
        (vv2_pop_demand_t)(UINT_PTR)0x00425860;
    vv2_collection_done_t collection_done =
        (vv2_collection_done_t)(UINT_PTR)0x00426120;
    int demand;
    int cap;
    if (pool == 0) {
        return 0;
    }
    demand = population_demand(pool, 0);
    cap = vv2_population_cap(collection_done, pool);
    if (demand + 3 > cap) {
        ShowVV2UpgradeResult(VV2_ACT_BARREL, VV2_RES_POP_FULL, 0, 0, 0, 0);
        return 0;
    }
    return 1;
}

/* ---- Change Appearance chooser (213) ---- */

#define IDB_HEAD_M_YOUNG 3001
#define IDB_HEAD_M_OLD   3002
#define IDB_HEAD_F_YOUNG 3003
#define IDB_HEAD_F_OLD   3004
#define IDB_BODY_M       3011
#define IDB_BODY_F       3012
#define IDC_BODY_PREVIEW 3101
#define IDC_HEAD_PREVIEW 3102
#define IDC_BODY_PREV    3103
#define IDC_BODY_NEXT    3104
#define IDC_HEAD_PREV    3105
#define IDC_HEAD_NEXT    3106
#define IDB_MASK         3020     /* 6-cell strip: none + 5 masks (40x65) */
#define IDC_MASK_PREVIEW 3107
#define IDC_MASK_PREV    3108
#define IDC_MASK_NEXT    3109
#define VV2_APPEARANCE_COUNT 30
#define VV2_MASK_COUNT   6        /* 0=none, 1..5 = Blue/Orange/Red/Purple/Chief */
#define VV2_APPEARANCE_CELL_W 40
#define VV2_APPEARANCE_CELL_H 65

/* Patch-owned per-villager mask table appended to the exe (.mtab @ 0x004B3000),
   indexed by record index; 0=none, 1..5=mask. The DLL runs in-process so it can
   read/write it directly. The render stubs (in the exe's .vvmk section) read it. */
#define VV2_MASK_TABLE       ((unsigned char *)0x004B3000)
#define VV2_MASK_TABLE_BYTES 256

/* The .mtab section exists ONLY in a mask-patched exe. On a build produced by the
   patcher without the mask exe-patch, 0x004B3000 is one byte past the end of the
   stock image and is NOT mapped, so touching it would access-violate and take the
   game down. Probe once with VirtualQuery and cache the answer; every access below
   is gated on it, so the DLL degrades to "no masks" instead of crashing. */
static int vv2_mask_table_state;   /* 0 = unprobed, 1 = usable, -1 = absent */

static int vv2_mask_table_ok(void)
{
    MEMORY_BASIC_INFORMATION mbi;
    if (vv2_mask_table_state == 0) {
        vv2_mask_table_state = -1;
        if (VirtualQuery((LPCVOID)VV2_MASK_TABLE, &mbi, sizeof(mbi)) == sizeof(mbi)
            && mbi.State == MEM_COMMIT
            && (mbi.Protect & (PAGE_READWRITE | PAGE_WRITECOPY
                               | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))
            && mbi.RegionSize >= VV2_MASK_TABLE_BYTES) {
            vv2_mask_table_state = 1;
        }
    }
    return vv2_mask_table_state > 0;
}

static int vv2_appearance_sex;   /* 0 = male, 1 = female */
static int vv2_appearance_old;   /* 0 = young head atlas, 1 = old head atlas */
static int vv2_appearance_head;
static int vv2_appearance_body;
static int vv2_appearance_mask;  /* 0=none, 1..5 */

static int vv2_appearance_head_bitmap(void) {
    if (vv2_appearance_sex) {
        return vv2_appearance_old ? IDB_HEAD_F_OLD : IDB_HEAD_F_YOUNG;
    }
    return vv2_appearance_old ? IDB_HEAD_M_OLD : IDB_HEAD_M_YOUNG;
}

static int vv2_appearance_body_bitmap(void) {
    return vv2_appearance_sex ? IDB_BODY_F : IDB_BODY_M;
}

static void vv2_appearance_draw(DRAWITEMSTRUCT *item, int bitmap_id, int index) {
    RECT rc = item->rcItem;
    int width = rc.right - rc.left;
    int height = rc.bottom - rc.top;
    HBRUSH background = CreateSolidBrush(RGB(236, 236, 236));
    HBITMAP bitmap;
    HDC source;
    HBITMAP previous;
    double scale_x, scale_y, scale;
    int draw_w, draw_h, draw_x, draw_y;

    FillRect(item->hDC, &rc, background);
    DeleteObject(background);

    bitmap = LoadBitmapA(module_instance, MAKEINTRESOURCEA(bitmap_id));
    if (bitmap == NULL) {
        return;
    }
    source = CreateCompatibleDC(item->hDC);
    previous = (HBITMAP)SelectObject(source, bitmap);

    scale_x = (double)width / VV2_APPEARANCE_CELL_W;
    scale_y = (double)height / VV2_APPEARANCE_CELL_H;
    scale = scale_x < scale_y ? scale_x : scale_y;
    draw_w = (int)(VV2_APPEARANCE_CELL_W * scale);
    draw_h = (int)(VV2_APPEARANCE_CELL_H * scale);
    draw_x = rc.left + (width - draw_w) / 2;
    draw_y = rc.top + (height - draw_h) / 2;

    SetStretchBltMode(item->hDC, COLORONCOLOR);
    StretchBlt(
        item->hDC, draw_x, draw_y, draw_w, draw_h,
        source, index * VV2_APPEARANCE_CELL_W, 0,
        VV2_APPEARANCE_CELL_W, VV2_APPEARANCE_CELL_H, SRCCOPY
    );

    SelectObject(source, previous);
    DeleteDC(source);
    DeleteObject(bitmap);
}

static void vv2_appearance_repaint(HWND window, int control) {
    InvalidateRect(GetDlgItem(window, control), NULL, TRUE);
}

/* Draw a centered text label in a preview cell (used for the mask picker's
   "(none)" / "No change" states instead of a sprite). */
static void vv2_draw_label(DRAWITEMSTRUCT *item, const char *text) {
    RECT rc = item->rcItem, calc = item->rcItem;
    HBRUSH bg = CreateSolidBrush(RGB(236, 236, 236));
    int th, top;
    FillRect(item->hDC, &rc, bg);
    DeleteObject(bg);
    SetBkMode(item->hDC, TRANSPARENT);
    /* DT_VCENTER only works with single-line text, so center manually: measure
       the wrapped height, then offset the draw rect to the vertical middle. */
    DrawTextA(item->hDC, text, -1, &calc, DT_CENTER | DT_WORDBREAK | DT_CALCRECT);
    th = calc.bottom - calc.top;
    top = rc.top + ((rc.bottom - rc.top) - th) / 2;
    if (top > rc.top) rc.top = top;
    DrawTextA(item->hDC, text, -1, &rc, DT_CENTER | DT_WORDBREAK);
}

static INT_PTR CALLBACK vv2_appearance_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    (void)lparam;
    if (message == WM_INITDIALOG) {
        vv2_surface_dialog(window);
        return TRUE;
    } else if (message == WM_DRAWITEM) {
        DRAWITEMSTRUCT *item = (DRAWITEMSTRUCT *)lparam;
        if (item->CtlID == IDC_BODY_PREVIEW) {
            vv2_appearance_draw(item, vv2_appearance_body_bitmap(), vv2_appearance_body);
            return TRUE;
        }
        if (item->CtlID == IDC_HEAD_PREVIEW) {
            vv2_appearance_draw(item, vv2_appearance_head_bitmap(), vv2_appearance_head);
            return TRUE;
        }
        if (item->CtlID == IDC_MASK_PREVIEW) {
            if (vv2_appearance_mask == 0) {
                vv2_draw_label(item, "(none)");
            } else {
                vv2_appearance_draw(item, IDB_MASK, vv2_appearance_mask);
            }
            return TRUE;
        }
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command == IDC_BODY_PREV) {
            vv2_appearance_body = (vv2_appearance_body + VV2_APPEARANCE_COUNT - 1) % VV2_APPEARANCE_COUNT;
            vv2_appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDC_BODY_NEXT) {
            vv2_appearance_body = (vv2_appearance_body + 1) % VV2_APPEARANCE_COUNT;
            vv2_appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDC_HEAD_PREV) {
            vv2_appearance_head = (vv2_appearance_head + VV2_APPEARANCE_COUNT - 1) % VV2_APPEARANCE_COUNT;
            vv2_appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == IDC_HEAD_NEXT) {
            vv2_appearance_head = (vv2_appearance_head + 1) % VV2_APPEARANCE_COUNT;
            vv2_appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == IDC_MASK_PREV) {
            vv2_appearance_mask = (vv2_appearance_mask + VV2_MASK_COUNT - 1) % VV2_MASK_COUNT;
            vv2_appearance_repaint(window, IDC_MASK_PREVIEW);
            return TRUE;
        }
        if (command == IDC_MASK_NEXT) {
            vv2_appearance_mask = (vv2_appearance_mask + 1) % VV2_MASK_COUNT;
            vv2_appearance_repaint(window, IDC_MASK_PREVIEW);
            return TRUE;
        }
        if (command == IDOK) {
            EndDialog(window, 1);
            return TRUE;
        }
        if (command == IDCANCEL) {
            EndDialog(window, 0);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, 0);
        return TRUE;
    }
    return FALSE;
}

/* ---- Mask persistence: a sidecar file, NEVER the game save (adapted from VV1's
   CRT-less design). The sidecar MUST sit next to the LDW saves, so the folder is
   derived from the EXE BASENAME exactly as the engine derives its save folder
   (GetModuleFileNameA -> strip dir + ".exe"). An earlier version hardcoded the
   canonical title, which put the sidecar in
   "...\LDW\Virtual Villagers - The Lost Children\" while a "- Modded" exe writes
   its .ldw saves to "...\LDW\Virtual Villagers - The Lost Children - Modded\" —
   i.e. NOT beside the saves (caught by the VV1 chat, verified on disk 2026-08-26;
   VV1/VV3/VV4 already derive from the basename and land correctly).
   Win32-only (wsprintfA/memcpy = intrinsics) to stay CRT-less.
   NEVER call from DllMain (loader lock + SHGetFolderPath). Index-keyed: relies on
   villagers reloading into the same record slots (positional VV2 save). ---- */
#define VV2_MASK_SIDECAR_MAGIC 0x32304D56u  /* 'V','M','0','2' */

static int vv2_mask_sidecar_path(char *out) {
    char docs[MAX_PATH];
    char exe[MAX_PATH];
    char *base;
    int i, last = -1, len;
    DWORD n;
    if (FAILED(SHGetFolderPathA(NULL, CSIDL_PERSONAL, NULL, 0, docs))) return 0;
    n = GetModuleFileNameA(GetModuleHandleA(NULL), exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return 0;          /* empty or truncated -> skip */
    for (i = 0; exe[i]; ++i) if (exe[i] == '\\' || exe[i] == '/') last = i;
    base = exe + last + 1;                          /* "<name>.exe" */
    len = lstrlenA(base);
    if (len > 4) {                                  /* strip a trailing ".exe" */
        char *ext = base + len - 4;
        if (ext[0] == '.' &&
            (ext[1] == 'e' || ext[1] == 'E') &&
            (ext[2] == 'x' || ext[2] == 'X') &&
            (ext[3] == 'e' || ext[3] == 'E')) {
            *ext = 0;
        }
    }
    if (base[0] == 0) return 0;                     /* no usable basename -> skip */
    /* MAX_PATH budget: docs + "\LDW\" + basename + "\vv2_masks.dat" */
    if (lstrlenA(docs) + 5 + lstrlenA(base) + (int)sizeof("\\vv2_masks.dat") >= MAX_PATH) {
        return 0;
    }
    wsprintfA(out, "%s\\LDW", docs);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s\\vv2_masks.dat", docs, base);
    return 1;
}

static void vv2_mask_sidecar_save(void) {
    char path[MAX_PATH];
    HANDLE f;
    DWORD w;
    unsigned int m = VV2_MASK_SIDECAR_MAGIC;
    if (!vv2_mask_table_ok()) return;          /* no .mtab -> nothing to persist */
    if (!vv2_mask_sidecar_path(path)) return;
    f = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) return;
    WriteFile(f, &m, 4, &w, NULL);
    WriteFile(f, VV2_MASK_TABLE, VV2_MASK_TABLE_BYTES, &w, NULL);
    CloseHandle(f);
}

static void vv2_mask_sidecar_load(void) {
    char path[MAX_PATH];
    HANDLE f;
    DWORD g;
    unsigned int m = 0;
    unsigned char buf[VV2_MASK_TABLE_BYTES];
    if (!vv2_mask_sidecar_path(path)) return;
    f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        /* MIGRATION (Codex P2): builds before the basename fix wrote the sidecar to a
           HARDCODED canonical folder.  A user who picked masks with one of those builds
           while running a renamed (e.g. "- Modded") exe would find the new basename path
           empty and appear to lose every mask.  Fall back to reading the old canonical
           location once; the next save writes to the correct basename path, so this
           self-heals without ever deleting or moving the user's file. */
        char legacy[MAX_PATH];
        char docs[MAX_PATH];
        if (FAILED(SHGetFolderPathA(NULL, CSIDL_PERSONAL, NULL, 0, docs))) return;
        if (lstrlenA(docs) + (int)sizeof("\\LDW\\Virtual Villagers - The Lost Children\\vv2_masks.dat") >= MAX_PATH) {
            return;
        }
        wsprintfA(legacy, "%s\\LDW\\Virtual Villagers - The Lost Children\\vv2_masks.dat", docs);
        if (lstrcmpiA(legacy, path) == 0) return;     /* already the canonical exe -> nothing to migrate */
        f = CreateFileA(legacy, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        if (f == INVALID_HANDLE_VALUE) return;        /* no legacy file either -> keep table as-is */
    }
    if (ReadFile(f, &m, 4, &g, NULL) && g == 4 && m == VV2_MASK_SIDECAR_MAGIC
        && ReadFile(f, buf, sizeof(buf), &g, NULL) && g == sizeof(buf)) {
        if (vv2_mask_table_ok()) memcpy(VV2_MASK_TABLE, buf, sizeof(buf));
    }
    CloseHandle(f);
}

/* exe-callable so an early exe hook can restore at startup, OUTSIDE the loader lock */
__declspec(dllexport) void __stdcall Vv2MaskRestore(void) { vv2_mask_sidecar_load(); }
/* exe-callable so the appearance handler can persist right after committing .mtab */
__declspec(dllexport) void __stdcall Vv2MaskSaveSidecar(void) { vv2_mask_sidecar_save(); }

/* Self-extract the embedded mask render atlas (RCDATA 5000) to <exe dir>\Images\
   heathen_masks.png if it is not already there, so a patched game gets the atlas
   with no separate asset deploy.  Uses the EXE's own directory (not cwd), so it
   works under any launch dir / renamed exe, and NEVER overwrites an existing file
   (so replacement art is respected).  Called by the exe's init hook BEFORE it
   loads the atlas — at startup, outside the loader lock.  CRT-less (Win32 only). */
__declspec(dllexport) void __stdcall Vv2ExtractAtlas(void) {
    char path[MAX_PATH];
    char tmp[MAX_PATH];
    int i, last = -1, dirlen;
    HRSRC res;
    HGLOBAL h;
    void *p;
    DWORD sz, w, n;
    HANDLE f;
    BOOL ok;
    n = GetModuleFileNameA(GetModuleHandleA(NULL), path, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return;          /* empty or truncated exe path -> skip */
    for (i = 0; path[i]; ++i) if (path[i] == '\\') last = i;   /* last backslash */
    if (last < 0) return;
    path[last] = 0;                               /* path = exe directory */
    dirlen = lstrlenA(path);
    /* Guard against MAX_PATH overflow: a short renamed exe near the path limit can
       still fit GetModuleFileNameA yet overflow once we append the sub-path. Need
       room for "\\Images\\heathen_masks.png" AND the ".tmp" staging suffix. */
    if (dirlen + (int)sizeof("\\Images\\heathen_masks.png.tmp") >= MAX_PATH) return;
    lstrcatA(path, "\\Images");
    CreateDirectoryA(path, NULL);
    lstrcatA(path, "\\heathen_masks.png");
    if (GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES) return;  /* already present */
    res = FindResourceA(module_instance, MAKEINTRESOURCEA(5000), RT_RCDATA);
    if (res == NULL) return;
    h = LoadResource(module_instance, res);
    if (h == NULL) return;
    p = LockResource(h);
    sz = SizeofResource(module_instance, res);
    if (p == NULL || sz == 0) return;
    /* Write to a temp file, verify the FULL payload landed, then atomically publish
       via MoveFileA. A disk-full / short WriteFile therefore never leaves a
       zero-length or truncated heathen_masks.png that the loader would choke on. */
    lstrcpyA(tmp, path);
    lstrcatA(tmp, ".tmp");
    f = CreateFileA(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) return;         /* can't write -> skip */
    ok = WriteFile(f, p, sz, &w, NULL);
    CloseHandle(f);
    if (!ok || w != sz) { DeleteFileA(tmp); return; }   /* incomplete write -> discard */
    if (!MoveFileA(tmp, path)) DeleteFileA(tmp);        /* publish; lost a race -> clean up */
}

/* Record field offsets + the per-villager cost, hoisted so the chooser (which now
   owns the whole commit) can read/write the record and charge itself.
   (VV2_SEX_OFFSET is already defined above.) */
#define VV2_HEAD_OFFSET         0x548
#define VV2_BODY_OFFSET         0x54C
#define VV2_TECH_BALANCE_OFFSET 0x2EADC
#define VV2_APPEARANCE_COST_DLL 5000

/* Per-villager Change Appearance: the DLL owns the ENTIRE flow — chooser dialog,
   the 5,000-tech charge, the record head/body + .mtab mask writes, and the
   sidecar SAVE — so the exe handler is a trivial one-call bridge that can never
   overrun its fixed 0x100 box (an earlier version that did the save exe-side
   overran the neighbouring handler and crashed).  player = the Detail/Tech player
   object (tech balance at +0x2EADC); record = the villager record base; idx = its
   record index (the .mtab entry).  Returns 1 if a change was applied.  The DLL
   only ever writes its own sidecar file, never the GAME save. */
__declspec(dllexport) int __stdcall ShowVV2AppearanceChooser(
    void *player,
    unsigned char *record,
    int idx
) {
    INT_PTR result;
    int *tech;
    int sex, age, h, b, m, orig_head, orig_body, orig_mask;
    if (player == 0 || record == 0 || idx < 0 || idx >= VV2_MASK_TABLE_BYTES) {
        return 0;
    }
    tech = (int *)((unsigned char *)player + VV2_TECH_BALANCE_OFFSET);
    sex = *(int *)(record + VV2_SEX_OFFSET);
    age = *(int *)(record + VV_AGE_OFFSET);
    h = *(int *)(record + VV2_HEAD_OFFSET);
    b = *(int *)(record + VV2_BODY_OFFSET);
    m = vv2_mask_table_ok() ? VV2_MASK_TABLE[idx] : 0;
    /* VV2 stores sex as 1 (male) or 2 (female); the stock renderer branches on
       `sex == 1` (0x4456A3). Match it: sex 1 -> male atlas (0), else female (1). */
    vv2_appearance_sex = (sex == 1) ? 0 : 1;
    vv2_appearance_old = age >= 1100 ? 1 : 0;
    vv2_appearance_head = (h >= 0 && h < VV2_APPEARANCE_COUNT) ? h : 0;
    vv2_appearance_body = (b >= 0 && b < VV2_APPEARANCE_COUNT) ? b : 0;
    vv2_appearance_mask = (m >= 0 && m < VV2_MASK_COUNT) ? m : 0;
    orig_head = vv2_appearance_head;
    orig_body = vv2_appearance_body;
    orig_mask = vv2_appearance_mask;

    result = DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_VV2_APPEARANCE),
        GetForegroundWindow(),
        vv2_appearance_dialog,
        0
    );
    if (result != 1) {
        return 0;
    }
    /* OK with nothing actually changed: write nothing, charge nothing. */
    if (vv2_appearance_head == orig_head && vv2_appearance_body == orig_body
            && vv2_appearance_mask == orig_mask) {
        ShowVV2UpgradeResult(VV2_ACT_DETAIL_APPEARANCE, VV2_RES_NO_CHANGE, 0, 0, 0, 0);
        return 0;
    }
    /* The head field is hereditary, so changing it affects descendants.  Warn and
       let the player back out with no write and no charge. */
    if (vv2_appearance_head != orig_head) {
        if (MessageBoxA(
                GetForegroundWindow(),
                "Warning: This will change the villager's head genetics.",
                "Change Appearance",
                MB_OKCANCEL | MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND
            ) != IDOK) {
            return 0;
        }
    }
    if (*tech < VV2_APPEARANCE_COST_DLL) {
        ShowVV2UpgradeResult(VV2_ACT_DETAIL_APPEARANCE, VV2_RES_INSUFFICIENT, 0, 0, 0, 0);
        return 0;
    }
    *tech -= VV2_APPEARANCE_COST_DLL;
    *(int *)(record + VV2_HEAD_OFFSET) = vv2_appearance_head;
    *(int *)(record + VV2_BODY_OFFSET) = vv2_appearance_body;
    if (vv2_mask_table_ok()) VV2_MASK_TABLE[idx] = (unsigned char)vv2_appearance_mask;
    vv2_mask_sidecar_save();   /* persist the mask table right after committing */
    return 1;
}

/* ---- Change Appearance for All (214): per-sex Head/Body/Mask + distribution
   + village-wide single mask, applied across every villager record. ---- */

#define IDD_VV2_APPEARANCE_ALL 214
#define VV2_SEX_OFFSET   0x538   /* 1 = male, 2 = female */
#define VV2_HEAD_OFFSET  0x548
#define VV2_BODY_OFFSET  0x54C

/* preview control ids: [sex][kind] kind 0=body,1=head,2=mask; sex 0=male,1=female */
static const int caf_preview_id[2][3] = {
    { 3201, 3202, 3203 }, { 3204, 3205, 3206 }
};

/* selector state; -1 = "No change" (default), so an untouched selector writes
   nothing.  head/body: 0..29.  mask: 0=None..5=Chief. */
static int caf_body[2], caf_head[2], caf_mask[2];
static int caf_dist;      /* 0 Off, 1 VV5, 2 Random(all5+none), 3 Equal, 4 Random(all5) */
static int caf_village;   /* -1 Off, else 0=None..5=Chief (table value) */
static int caf_head_mode; /* 0 Off, 1 Random(by gender), 2..6 = All Black/Brown/Red/Blonde/Other */
static int caf_body_mode; /* 0 Off, 1 Random(by gender) */

/* Village-wide head hair-colour buckets: head INDICES per gender per colour.
   [0]=male [1]=female; colours 0 Black,1 Brown,2 Red,3 Blonde,4 Other. Bucketed
   from the head-atlas hair band; adjust an index if any head is miscategorised. */
#define VV2_HAIR_MAX 7
static const unsigned char caf_hair[2][5][VV2_HAIR_MAX] = {
    { /* male */
        { 0, 1, 2, 3, 4, 6, 8 },       /* Black  */
        { 9, 11, 12, 13, 19, 20, 22 }, /* Brown  */
        { 10, 15, 16, 17, 18, 0, 0 },  /* Red    */
        { 14, 21, 23, 24, 25, 27, 28 },/* Blonde */
        { 5, 7, 26, 29, 0, 0, 0 },     /* Other  */
    },
    { /* female */
        { 0, 1, 2, 5, 6, 8, 9 },       /* Black  */
        { 4, 11, 12, 14, 20, 21, 0 },  /* Brown  */
        { 10, 16, 17, 18, 19, 0, 0 },  /* Red    */
        { 22, 23, 24, 25, 26, 27, 28 },/* Blonde */
        { 3, 7, 13, 15, 29, 0, 0 },    /* Other  */
    }
};
static const unsigned char caf_hair_n[2][5] = {
    { 7, 7, 5, 7, 4 },   /* male   counts */
    { 7, 6, 5, 7, 5 }    /* female counts */
};

static unsigned int caf_rng;
static unsigned int caf_rand(void) {
    caf_rng ^= caf_rng << 13; caf_rng ^= caf_rng >> 17; caf_rng ^= caf_rng << 5;
    return caf_rng;
}

/* Draw one selector preview: sex-appropriate strip, or "No change" when idx<0. */
static void caf_draw(DRAWITEMSTRUCT *item, int sex, int kind, int idx) {
    if (idx < 0) {
        vv2_draw_label(item, "No change");
        return;
    }
    if (kind == 2) {
        if (idx == 0) {
            vv2_draw_label(item, "(none)");
        } else {
            vv2_appearance_draw(item, IDB_MASK, idx);
        }
    } else if (kind == 1) {
        vv2_appearance_draw(item, sex ? IDB_HEAD_F_YOUNG : IDB_HEAD_M_YOUNG, idx);
    } else {
        vv2_appearance_draw(item, sex ? IDB_BODY_F : IDB_BODY_M, idx);
    }
}

/* cycle a selector value; -1 (No change) is one position before 0, count is the
   number of real options (30 for head/body, 6 for mask). */
static int caf_cycle(int value, int count, int delta) {
    value += delta;
    if (value < -1) value = count - 1;
    if (value >= count) value = -1;
    return value;
}

/* The 10 "mask for everyone" radios form ONE mutually-exclusive choice spread
   across two visual boxes: 3230 Off, 3231 VV5, 3232 Random, 3233 Equal, and
   3241..3246 = single mask None/Blue/Orange/Red/Purple/Chief. */
/* The three override groups (Masks / Heads / Bodies).  Each is one mutually-
   exclusive radio set; Off = use the per-sex cyclers, any other option overrides
   them.  Mask spans two visual boxes (distribution + single colour). */
static const int caf_mask_radio[11] = {
    3230, 3231, 3232, 3234, 3233, 3241, 3242, 3243, 3244, 3245, 3246
};
static const int caf_head_radio[7] = { 3250, 3251, 3252, 3253, 3254, 3255, 3256 };
static const int caf_body_radio[2] = { 3260, 3261 };
/* the four per-sex cycler buttons to grey when a group's override is active:
   male <, male >, female <, female > */
static const int caf_mask_cyc[4] = { 3213, 3223, 3216, 3226 };
static const int caf_head_cyc[4] = { 3212, 3222, 3215, 3225 };
static const int caf_body_cyc[4] = { 3211, 3221, 3214, 3224 };

/* Enforce single-select across `radios`, and grey the four per-sex cyclers when
   an override (anything but `off_id`) is chosen — so a per-sex selector and a
   village-wide override for the same part can never both apply.  `preview_col`
   (0 body / 1 head / 2 mask) + `slots` = the per-sex values to clear/repaint. */
static void caf_set_group(HWND w, const int *radios, int n, int selected,
                          int off_id, const int *cyc, int *slots, int preview_col) {
    int i, off = (selected == off_id);
    for (i = 0; i < n; ++i)
        CheckDlgButton(w, radios[i], radios[i] == selected ? BST_CHECKED : BST_UNCHECKED);
    for (i = 0; i < 4; ++i) EnableWindow(GetDlgItem(w, cyc[i]), off);
    if (!off) {                               /* override wins: clear the per-sex pair */
        slots[0] = slots[1] = -1;
        vv2_appearance_repaint(w, caf_preview_id[0][preview_col]);
        vv2_appearance_repaint(w, caf_preview_id[1][preview_col]);
    }
}
static void caf_set_mask_mode(HWND w, int sel) {
    caf_set_group(w, caf_mask_radio, 11, sel, 3230, caf_mask_cyc, caf_mask, 2);
}
static void caf_set_head_mode(HWND w, int sel) {
    caf_set_group(w, caf_head_radio, 7, sel, 3250, caf_head_cyc, caf_head, 1);
}
static void caf_set_body_mode(HWND w, int sel) {
    caf_set_group(w, caf_body_radio, 2, sel, 3260, caf_body_cyc, caf_body, 0);
}

static INT_PTR CALLBACK caf_dialog(HWND w, UINT msg, WPARAM wp, LPARAM lp) {
    (void)lp;
    if (msg == WM_INITDIALOG) {
        caf_set_head_mode(w, 3250);   /* defaults: all three groups Off */
        caf_set_body_mode(w, 3260);
        caf_set_mask_mode(w, 3230);
        vv2_surface_dialog(w);
        return TRUE;
    } else if (msg == WM_DRAWITEM) {
        DRAWITEMSTRUCT *item = (DRAWITEMSTRUCT *)lp;
        int s, k;
        for (s = 0; s < 2; ++s) {
            for (k = 0; k < 3; ++k) {
                if ((int)item->CtlID == caf_preview_id[s][k]) {
                    int v = k == 0 ? caf_body[s] : k == 1 ? caf_head[s] : caf_mask[s];
                    caf_draw(item, s, k, v);
                    return TRUE;
                }
            }
        }
    } else if (msg == WM_COMMAND) {
        unsigned int cmd = LOWORD(wp);
        if (cmd >= 3211 && cmd <= 3226) {
            int prev = cmd <= 3216;                 /* 3211-3216 prev, 3221-3226 next */
            int base = prev ? 3211 : 3221;
            int s = (cmd - base) / 3;               /* 0 male, 1 female */
            int k = (cmd - base) % 3;               /* 0 body,1 head,2 mask */
            int count = (k == 2) ? VV2_MASK_COUNT : VV2_APPEARANCE_COUNT;
            int *slot = k == 0 ? &caf_body[s] : k == 1 ? &caf_head[s] : &caf_mask[s];
            *slot = caf_cycle(*slot, count, prev ? -1 : 1);
            vv2_appearance_repaint(w, caf_preview_id[s][k]);
            return TRUE;
        }
        if ((cmd >= 3230 && cmd <= 3234) || (cmd >= 3241 && cmd <= 3246)) {
            caf_set_mask_mode(w, (int)cmd);   /* one exclusive mask choice */
            return TRUE;
        }
        if (cmd >= 3250 && cmd <= 3256) { caf_set_head_mode(w, (int)cmd); return TRUE; }
        if (cmd >= 3260 && cmd <= 3261) { caf_set_body_mode(w, (int)cmd); return TRUE; }
        if (cmd == IDOK) {
            int r;
            caf_dist = 0;
            caf_village = -1;
            if (IsDlgButtonChecked(w, 3231)) caf_dist = 1;        /* VV5-style */
            else if (IsDlgButtonChecked(w, 3232)) caf_dist = 2;   /* Random (All 5 + No Mask) */
            else if (IsDlgButtonChecked(w, 3234)) caf_dist = 4;   /* Random (All 5) */
            else if (IsDlgButtonChecked(w, 3233)) caf_dist = 3;   /* Equal */
            else for (r = 0; r < 6; ++r)                          /* single mask 0..5 */
                if (IsDlgButtonChecked(w, 3241 + r)) { caf_village = r; break; }
            /* Heads: 3250 Off..3256 Other -> mode 0..6.  Bodies: Off/Random. */
            caf_head_mode = 0;
            for (r = 0; r < 7; ++r)
                if (IsDlgButtonChecked(w, 3250 + r)) { caf_head_mode = r; break; }
            caf_body_mode = IsDlgButtonChecked(w, 3261) ? 1 : 0;
            /* an active override ignores the matching per-sex cyclers */
            if (caf_dist != 0 || caf_village >= 0) caf_mask[0] = caf_mask[1] = -1;
            if (caf_head_mode != 0) caf_head[0] = caf_head[1] = -1;
            if (caf_body_mode != 0) caf_body[0] = caf_body[1] = -1;
            EndDialog(w, 1);
            return TRUE;
        }
        if (cmd == IDCANCEL) { EndDialog(w, 0); return TRUE; }
    } else if (msg == WM_CLOSE) {
        EndDialog(w, 0);
        return TRUE;
    }
    return FALSE;
}

/* Fisher-Yates shuffle of an int array using caf_rand. */
static void caf_shuffle(int *a, int n) {
    int i, j, t;
    for (i = n - 1; i > 0; --i) {
        j = (int)(caf_rand() % (unsigned int)(i + 1));
        t = a[i]; a[i] = a[j]; a[j] = t;
    }
}

/* Apply the current selectors to every active villager record.  Order: per-sex
   Head/Body/Mask first, then a distribution preset (overrides masks), then a
   village-wide single mask (final override) — so leaving the later groups Off
   makes the per-sex selectors authoritative. */
/* Returns the number of active villagers processed (0 = nothing to change, so
   the caller must not charge). */
static int vv2_apply_caf(unsigned char *base) {
    int idx[VV2_RECORD_COUNT];       /* active record indices */
    int sexof[VV2_RECORD_COUNT];     /* 0 male, 1 female (parallel to idx) */
    int n = 0, i;
    unsigned char *rec = base;
    for (i = 0; i < VV2_RECORD_COUNT; ++i, rec += VV2_RECORD_STRIDE) {
        int s;
        if (rec[VV2_ACTIVE_OFFSET] == 0) continue;
        s = (*(int *)(rec + VV2_SEX_OFFSET) == 1) ? 0 : 1;
        idx[n] = i; sexof[n] = s; ++n;
        /* per-sex Head/Body/Mask (skipped when the matching village-wide override
           is active — those selectors were cleared/greyed, so these are -1) */
        if (caf_head[s] >= 0) *(int *)(rec + VV2_HEAD_OFFSET) = caf_head[s];
        if (caf_body[s] >= 0) *(int *)(rec + VV2_BODY_OFFSET) = caf_body[s];
        if (caf_mask[s] >= 0 && vv2_mask_table_ok()) VV2_MASK_TABLE[i] = (unsigned char)caf_mask[s];
    }
    if (caf_head_mode != 0) {                 /* village-wide Heads */
        for (i = 0; i < n; ++i) {
            int s = sexof[i], h;
            if (caf_head_mode == 1) {         /* Random (by gender) */
                h = (int)(caf_rand() % (unsigned)VV2_APPEARANCE_COUNT);
            } else {                          /* All <colour>: random within bucket */
                int c = caf_head_mode - 2;    /* 0 Black..4 Other */
                h = caf_hair[s][c][caf_rand() % caf_hair_n[s][c]];
            }
            *(int *)(base + idx[i] * VV2_RECORD_STRIDE + VV2_HEAD_OFFSET) = h;
        }
    }
    if (caf_body_mode == 1) {                 /* village-wide Bodies: Random */
        for (i = 0; i < n; ++i)
            *(int *)(base + idx[i] * VV2_RECORD_STRIDE + VV2_BODY_OFFSET) =
                (int)(caf_rand() % (unsigned)VV2_APPEARANCE_COUNT);
    }
    if (caf_dist == 1 && vv2_mask_table_ok()) {   /* VV5-style rarity */
        int order[VV2_RECORD_COUNT], k;
        static const int tier_mask[4] = { 5, 4, 3, 2 };   /* Chief,Purple,Red,Orange */
        static const int tier_cap[4]  = { 1, 4, 7, 10 };
        int t, cursor = 0;
        for (k = 0; k < n; ++k) order[k] = idx[k];
        caf_shuffle(order, n);
        for (k = 0; k < n; ++k) VV2_MASK_TABLE[order[k]] = 1;   /* default Blue */
        for (t = 0; t < 4 && cursor < n; ++t) {
            int c;
            for (c = 0; c < tier_cap[t] && cursor < n; ++c, ++cursor)
                VV2_MASK_TABLE[order[cursor]] = (unsigned char)tier_mask[t];
        }
    } else if (caf_dist == 2 && vv2_mask_table_ok()) {  /* Random (All 5 + No Mask): 0..5 */
        for (i = 0; i < n; ++i)
            VV2_MASK_TABLE[idx[i]] = (unsigned char)(caf_rand() % 6u);
    } else if (caf_dist == 4 && vv2_mask_table_ok()) {  /* Random (All 5): 1..5, never no-mask */
        for (i = 0; i < n; ++i)
            VV2_MASK_TABLE[idx[i]] = (unsigned char)(1u + caf_rand() % 5u);
    } else if (caf_dist == 3 && vv2_mask_table_ok()) {  /* Equal, balanced M/F */
        int order[VV2_RECORD_COUNT], males[VV2_RECORD_COUNT], females[VV2_RECORD_COUNT];
        int nm = 0, nf = 0, k, o = 0;
        for (k = 0; k < n; ++k) { if (sexof[k]) females[nf++] = idx[k]; else males[nm++] = idx[k]; }
        caf_shuffle(males, nm); caf_shuffle(females, nf);
        /* alternate M/F so each round-robin mask type gets a balanced sex mix */
        { int a = 0, b = 0; while (a < nm || b < nf) {
            if (a < nm) order[o++] = males[a++];
            if (b < nf) order[o++] = females[b++]; } }
        for (k = 0; k < n; ++k)
            VV2_MASK_TABLE[order[k]] = (unsigned char)((k % 5) + 1);   /* Blue..Chief */
    }
    if (caf_village >= 0 && vv2_mask_table_ok()) {  /* village-wide single mask override */
        for (i = 0; i < n; ++i)
            VV2_MASK_TABLE[idx[i]] = (unsigned char)caf_village;
    }
    return n;
}

#define VV2_CAF_COST 450000
#define VV2_TECH_BALANCE_OFFSET 0x2EADC   /* int tech-point balance in the player obj */
#define VV2_RECORD_ARRAY_FN     0x0044F4E0 /* stock getter: returns certified record array */

typedef unsigned char *(__stdcall *vv2_record_array_fn)(void);

/* player = the Tech-menu player object (exe passes EDI).  Derives the tech-point
   balance (+0x2EADC) and the certified record array (the stock getter the exe's
   other apply paths use) itself, so the exe dispatch is a one-arg call with no
   handler growth.  On OK — with a real change and enough points — charges 450k,
   applies to all villagers, and persists the mask table to the sidecar. */
__declspec(dllexport) int __stdcall ShowVV2AppearanceForAll(void *player) {
    INT_PTR result;
    int changed_head;
    unsigned char *base;
    int *tech;
    if (player == 0) return 0;
    tech = (int *)((unsigned char *)player + VV2_TECH_BALANCE_OFFSET);
    base = ((vv2_record_array_fn)VV2_RECORD_ARRAY_FN)();
    if (base == 0) return 0;
    caf_body[0] = caf_head[0] = caf_mask[0] = -1;
    caf_body[1] = caf_head[1] = caf_mask[1] = -1;
    caf_dist = 0;
    caf_village = -1;
    caf_head_mode = 0;
    caf_body_mode = 0;
    caf_rng = GetTickCount() | 1u;
    vv2_prep_fullscreen();

    result = DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_VV2_APPEARANCE_ALL),
                             GetForegroundWindow(), caf_dialog, 0);
    if (result != 1) return 0;   /* caf_dialog captured the radios before closing */

    /* nothing selected in any of the four groups -> no change, no charge */
    if (caf_body[0] < 0 && caf_head[0] < 0 && caf_mask[0] < 0 &&
        caf_body[1] < 0 && caf_head[1] < 0 && caf_mask[1] < 0 &&
        caf_dist == 0 && caf_village < 0 &&
        caf_head_mode == 0 && caf_body_mode == 0) {
        MessageBoxA(GetForegroundWindow(),
                    "No appearance options were selected. No tech points deducted.",
                    "Change Appearance for All",
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }

    if (tech && *tech < VV2_CAF_COST) {
        MessageBoxA(GetForegroundWindow(),
                    "Not enough tech points. This upgrade costs 450,000.",
                    "Change Appearance for All",
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }

    /* changing a head field rewrites hereditary genetics; warn once for all */
    changed_head = (caf_head[0] >= 0 || caf_head[1] >= 0 || caf_head_mode != 0);
    if (changed_head) {
        if (MessageBoxA(GetForegroundWindow(),
                "Warning: This will change the head genetics of every villager "
                "of the selected sex, affecting their descendants.\r\n\r\nProceed?",
                "Change Appearance for All",
                MB_OKCANCEL | MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND) != IDOK) {
            return 0;
        }
    }

    /* Apply first; charge only if there was at least one active villager to
       change (no-op selections / an empty village must not deduct 450k). */
    if (vv2_apply_caf(base) == 0) {
        MessageBoxA(GetForegroundWindow(),
                    "There are no villagers to change right now. "
                    "No tech points were deducted.",
                    "Change Appearance for All",
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    if (tech) *tech -= VV2_CAF_COST;
    vv2_mask_sidecar_save();
    MessageBoxA(GetForegroundWindow(),
                "Change Appearance for All applied to every villager.",
                "Change Appearance for All",
                MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return 1;
}
