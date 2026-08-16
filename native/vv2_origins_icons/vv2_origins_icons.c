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

/* Task9-style prompt action / result codes and forward declarations, hoisted so
   the ApplyVV2* reporters below can route through the shared result renderer
   defined later in this file. */
enum {
    VV2_ACT_TIME_WARP = 0, VV2_ACT_ISLAND = 1, VV2_ACT_BARREL = 2,
    VV2_ACT_TECH_DOUBLER = 3, VV2_ACT_FOOD_DOUBLER = 4, VV2_ACT_CURE = 5,
    VV2_ACT_RUNNING_ALL = 6, VV2_ACT_MASTERY_ALL = 7, VV2_ACT_AGE_ALL = 8,
    VV2_ACT_COLLECT_COMPLETE = 9, VV2_ACT_COLLECT_RESET = 10,
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

/* VV2 tech screen now carries 11 rows: the 9 shared Origins upgrades plus
   Complete all Collections (1009) and Reset all Collections (1010).  The shared
   ID_BUY_LAST (1008) only bounds the VV1 dialogs, so the VV2 proc uses its own
   upper bound instead of editing the shared enum. */
#define VV2_TECH_ROW_COUNT 11
#define ID_VV2_BUY_LAST    1010

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
    case VV2_ACT_AGE_ALL: return "Set All Villagers to 18";
    case VV2_ACT_COLLECT_COMPLETE: return "Complete All Collections";
    case VV2_ACT_COLLECT_RESET: return "Reset All Collections";
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
            wsprintfA(line, "\r\n\r\nSkipped %u %s: already 18.",
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
                     "Everyone is already 18. No tech points have been "
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
#define VV2_APPEARANCE_COUNT 30
#define VV2_APPEARANCE_CELL_W 40
#define VV2_APPEARANCE_CELL_H 65

static int vv2_appearance_sex;   /* 0 = male, 1 = female */
static int vv2_appearance_old;   /* 0 = young head atlas, 1 = old head atlas */
static int vv2_appearance_head;
static int vv2_appearance_body;

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

/* Reports the chosen head/body indices back to the caller; the native handler
   owns eligibility, the 5,000-tech charge, and the record writes, so the DLL
   never touches save data. */
__declspec(dllexport) int __stdcall ShowVV2AppearanceChooser(
    int sex,
    int age,
    int *head,
    int *body
) {
    INT_PTR result;
    int orig_head, orig_body;
    /* VV2 stores sex as 1 (male) or 2 (female); the stock renderer branches on
       `sex == 1` (0x4456A3). Match it: sex 1 -> male atlas (0), else female (1). */
    vv2_appearance_sex = (sex == 1) ? 0 : 1;
    vv2_appearance_old = age >= 1100 ? 1 : 0;
    vv2_appearance_head = (head && *head >= 0 && *head < VV2_APPEARANCE_COUNT) ? *head : 0;
    vv2_appearance_body = (body && *body >= 0 && *body < VV2_APPEARANCE_COUNT) ? *body : 0;
    orig_head = vv2_appearance_head;
    orig_body = vv2_appearance_body;

    result = DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_VV2_APPEARANCE),
        GetForegroundWindow(),
        vv2_appearance_dialog,
        0
    );
    if (result == 1) {
        /* OK with nothing actually changed (opened and confirmed, or cycled the
           selectors back to where they started): write nothing, charge nothing. */
        if (vv2_appearance_head == orig_head && vv2_appearance_body == orig_body) {
            ShowVV2UpgradeResult(
                VV2_ACT_DETAIL_APPEARANCE, VV2_RES_NO_CHANGE, 0, 0, 0, 0
            );
            return 0;
        }
        /* The head field is hereditary (record +0x548), so changing it affects
           this villager's descendants.  Warn explicitly before committing, and
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
        if (head) {
            *head = vv2_appearance_head;
        }
        if (body) {
            *body = vv2_appearance_body;
        }
        return 1;
    }
    return 0;
}
