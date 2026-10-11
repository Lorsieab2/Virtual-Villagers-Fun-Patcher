/* Custom Island Event: the dialogs.  Included by vvfp_story_upgrades.c after
   story_custom.inc.  Plain Windows dialogs (the owner's explicit choice),
   resources 302-309 in vvfp_story_upgrades.rc.

   Every control a game cannot support is disabled; "Not in this game..."
   says what is missing in that game and why.  Every value is checked when
   the dialog closes: a value outside what the game accepts is refused with
   a message naming the valid range, never silently clamped. */

enum {
    IDD_CUSTOM = 302, IDD_CHANGES = 303, IDD_SPAWN = 304, IDD_PARENTS = 305,
    IDD_VALUES = 306, IDD_PUZZLES = 307, IDD_REVIVE = 308, IDD_UNBORN = 309,
    IDC_CE_OTHER = 1131, IDC_CE_VALUES = 1132, IDC_CE_PUZZLES = 1133, IDC_CE_REVIVE = 1134,
    IDC_CE_OTHER_REMOVE = 1135, IDC_CE_QUEUE_NOTE = 1136, IDC_CE_CHOICE = 1137,
    IDC_CE_CHOICES = 1138, IDC_CE_TEXT_LABEL = 1139,
    IDD_CHOICES = 310,
    IDC_CC_LABEL_FIRST = 3701, IDC_CC_LIST_FIRST = 3711, IDC_CC_ADD_FIRST = 3721,
    IDC_CC_EDIT_FIRST = 3731, IDC_CC_REMOVE_FIRST = 3741, IDC_CC_CHANCE_FIRST = 3751,
    IDC_CC_NOTE_FIRST = 3761, IDC_CC_LIMIT = 3771, IDC_CC_FEATURED = 3781, IDC_CC_FEATURED_NOTE = 3782,
    IDC_VA_LIST = 3301, IDC_VA_AMOUNT = 3302, IDC_VA_NOTE = 3303, IDC_VA_SET = 3304,
    IDC_VA_KEEP = 3305,
    IDC_PZ_LIST = 3401, IDC_PZ_SOLVE = 3402, IDC_PZ_UNSOLVE = 3403, IDC_PZ_KEEP = 3404,
    IDC_PZ_NOTE = 3405,
    IDC_RV_LIST = 3501, IDC_RV_HEALTH = 3502, IDC_RV_CURE = 3503, IDC_RV_NOTE = 3504,
    IDC_RV_ALL = 3505,
    IDC_UB_NAME = 3601, IDC_UB_HEAD = 3602, IDC_UB_BODY = 3603, IDC_UB_RANGE = 3604,
    IDC_CH_UNBORN = 2082, IDC_CH_UNBORN_NOTE = 2083,
    IDC_CE_TITLE = 1101, IDC_CE_TEXT = 1102, IDC_CE_FOOD_OP = 1103, IDC_CE_FOOD = 1104,
    IDC_CE_TECH_OP = 1105, IDC_CE_TECH = 1106, IDC_CE_REFILL = 1107, IDC_CE_VILLAGE = 1108,
    IDC_CE_TEXT_NOTE = 1109, IDC_CE_NOTE = 1110, IDC_CE_SPAWNS = 1111, IDC_CE_SPAWN_ADD = 1112,
    IDC_CE_SPAWN_REMOVE = 1113, IDC_CE_OMITTED = 1114, IDC_CE_CHANGES = 1121,
    IDC_CE_CHANGE_ADD = 1122, IDC_CE_CHANGE_REMOVE = 1123, IDC_CE_TITLE_COUNT = 1124,
    IDC_CH_LIST = 2001, IDC_CH_TOGGLE_FIRST = 2002, IDC_CH_COUNT = 2007,
    IDC_CH_FATE = 2010, IDC_CH_SICK = 2011, IDC_CH_PREGNANCY = 2012, IDC_CH_FATHER = 2013,
    IDC_CH_HEAD = 2020, IDC_CH_BODY = 2021, IDC_CH_LOOK_RANGE = 2022,
    IDC_CH_LIKE_ADD = 2030, IDC_CH_LIKE_REMOVE = 2031, IDC_CH_DISLIKE_ADD = 2032,
    IDC_CH_DISLIKE_REMOVE = 2033, IDC_CH_SKILL_FIRST = 2040, IDC_CH_SKILL_LABEL_FIRST = 2050,
    IDC_CH_TITLE = 2060, IDC_CH_TITLE_CLEAR = 2061, IDC_CH_MASK = 2070, IDC_CH_STATUS = 2071,
    IDC_CH_BEHAVIOUR = 2074, IDC_CH_PARENTS = 2080, IDC_CH_PARENTS_NOTE = 2081, IDC_CH_NOTE = 2090,
    IDC_SP_COUNT = 3101, IDC_SP_SEX = 3102, IDC_SP_AGE = 3103, IDC_SP_AGE_RANGE = 3104,
    IDC_SP_NAME = 3105, IDC_SP_HEAD = 3106, IDC_SP_BODY = 3107, IDC_SP_LOOK_RANGE = 3108,
    IDC_SP_LIKE_FIRST = 3110, IDC_SP_DISLIKE_FIRST = 3113, IDC_SP_SKILL_FIRST = 3120,
    IDC_SP_SKILL_LABEL_FIRST = 3130, IDC_SP_TITLE = 3140, IDC_SP_MASK = 3141,
    IDC_SP_FACTION = 3142, IDC_SP_NOTE = 3150,
    IDC_PA_FATHER = 3201, IDC_PA_FATHER_HEAD = 3202, IDC_PA_FATHER_BODY = 3203,
    IDC_PA_MOTHER = 3204, IDC_PA_MOTHER_HEAD = 3205, IDC_PA_MOTHER_BODY = 3206,
    IDC_PA_RANGE = 3207
};

#define UI_ROSTER_MAX 256

static struct {
    int game;
    const ce_adapter *a;
    ce_event draft;                       /* kept between openings until queued */
    int draft_game;
    story_member roster[UI_ROSTER_MAX];
    char names[UI_ROSTER_MAX][CE_NAME_BYTES];
    int roster_count;
    ce_spawn spawn;                       /* the spawn dialog's result */
    ce_change parents;                    /* the parents dialog's result */
    int parents_chosen;
    ce_change unborn;                     /* the unborn baby's father dialog's result */
    int unborn_chosen;
    int values[CE_MAX_VALUES];            /* the amounts dialog's choices, CE_KEEP = none */
    int puzzles[CE_MAX_PUZZLES];          /* the puzzles dialog's: -1 none, 0 / 1 */
    /* Two choices: the draft's buttons and outcomes, kept with the draft.
       While an outcome is edited the main dialog runs again on `draft`
       holding that outcome's changes; the event's own draft waits in
       `main_draft`. */
    ce_choice choice;
    ce_event main_draft;
    int outcome_button;                   /* the outcome being edited */
    int outcome_index;
    int filling;                          /* the choices dialog is setting its own controls */
} ui;

/* The main dialog's two uses, its DialogBoxParam argument. */
enum { UI_MODE_EVENT = 0, UI_MODE_OUTCOME = 1 };

static const char *const UI_TOGGLE_NAMES[5] = {
    "All Adult Women", "All Adult Men", "All Females", "All Males", "All Children"
};
static const unsigned int UI_TOGGLE_BITS[5] = {
    STORY_T_ADULT_WOMEN, STORY_T_ADULT_MEN, STORY_T_FEMALES, STORY_T_MALES, STORY_T_CHILDREN
};

static void ui_message(HWND owner, const char *text) {
    MessageBoxA(owner, text, "Custom Island Event",
                MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
}

/* A number typed in an edit box: CE_KEEP when blank, -1 when not a number. */
static int ui_number(HWND window, int id) {
    char text[32];
    int value = 0;
    int i;
    GetDlgItemTextA(window, id, text, sizeof text);
    if (text[0] == '\0') {
        return CE_KEEP;
    }
    for (i = 0; text[i] != '\0'; ++i) {
        if (text[i] < '0' || text[i] > '9' || value > 100000000) {
            return -1;
        }
        value = value * 10 + (text[i] - '0');
    }
    return value;
}

static void ui_enable(HWND window, int id, int enable) {
    EnableWindow(GetDlgItem(window, id), enable ? TRUE : FALSE);
}

/* The index-th entry of a comma-separated list. */
static int ui_list_entry(const char *list, int index, char *out, int size) {
    int current = 0;
    int n = 0;
    while (*list != '\0' && current < index) {
        if (*list++ == ',') {
            ++current;
        }
    }
    if (current != index || *list == '\0') {
        return 0;
    }
    while (*list != '\0' && *list != ',' && n < size - 1) {
        out[n++] = *list++;
    }
    out[n] = '\0';
    return n > 0;
}

/* A preference combo: first entry `first` (item data -1), then the game's
   own list (item data = the game's index). */
static void ui_fill_prefs(HWND window, int id, const char *first) {
    char word[64];
    int i;
    int row = (int)SendDlgItemMessageA(window, id, CB_ADDSTRING, 0, (LPARAM)first);
    SendDlgItemMessageA(window, id, CB_SETITEMDATA, (WPARAM)row, (LPARAM)-1);
    for (i = 0; i < ui.a->pref_count; ++i) {
        if (ui_list_entry(ui.a->pref_list, i, word, sizeof word)) {
            row = (int)SendDlgItemMessageA(window, id, CB_ADDSTRING, 0, (LPARAM)word);
            SendDlgItemMessageA(window, id, CB_SETITEMDATA, (WPARAM)row, (LPARAM)i);
        }
    }
    SendDlgItemMessageA(window, id, CB_SETCURSEL, 0, 0);
}

static int ui_combo_data(HWND window, int id) {
    int sel = (int)SendDlgItemMessageA(window, id, CB_GETCURSEL, 0, 0);
    if (sel < 0) {
        return -1;
    }
    return (int)SendDlgItemMessageA(window, id, CB_GETITEMDATA, (WPARAM)sel, 0);
}

static void ui_combo_add(HWND window, int id, const char *text, int data) {
    int row = (int)SendDlgItemMessageA(window, id, CB_ADDSTRING, 0, (LPARAM)text);
    SendDlgItemMessageA(window, id, CB_SETITEMDATA, (WPARAM)row, (LPARAM)data);
}

/* A list of choices with a "No change" first entry (data CE_KEEP). */
static void ui_fill_choices(HWND window, int id, const char *const *names, int count) {
    int i;
    ui_combo_add(window, id, "No change", CE_KEEP);
    for (i = 0; i < count; ++i) {
        ui_combo_add(window, id, names[i], i);
    }
    SendDlgItemMessageA(window, id, CB_SETCURSEL, 0, 0);
}

static void ui_fill_masks(HWND window, int id, const char *keep) {
    int i;
    int count = story_mask_count(ui.game);
    ui_combo_add(window, id, keep, CE_KEEP);
    ui_combo_add(window, id, "No mask", 0);
    for (i = 1; i <= count; ++i) {
        ui_combo_add(window, id, story_mask_name(ui.game, i), i);
    }
    SendDlgItemMessageA(window, id, CB_SETCURSEL, 0, 0);
}

static const char *ui_years(int units, char *out) {
    wsprintfA(out, "%d", units / 20);
    return out;
}

static void ui_load_roster(void) {
    int i;
    ui.roster_count = ce_roster(ui.a, ui.roster, UI_ROSTER_MAX);
    for (i = 0; i < ui.roster_count; ++i) {
        const unsigned char *record = ui.a->record(ui.roster[i].index);
        ce_copy_name(ui.names[i], CE_NAME_BYTES, record + ui.a->off_name, ui.a->name_bytes);
    }
}

static int ui_roster_position(int index) {
    int i;
    for (i = 0; i < ui.roster_count; ++i) {
        if (ui.roster[i].index == index) {
            return i;
        }
    }
    return -1;
}

static const char *ui_name_of(int index) {
    int position = ui_roster_position(index);
    return position < 0 ? "(gone)" : ui.names[position];
}

/* ---- The parents dialog ------------------------------------------------ */

static INT_PTR CALLBACK ui_parents_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    char text[96];
    (void)lparam;
    if (message == WM_INITDIALOG) {
        SendDlgItemMessageA(window, IDC_PA_FATHER, EM_LIMITTEXT, (WPARAM)(ui.a->parent_name_bytes - 1), 0);
        SendDlgItemMessageA(window, IDC_PA_MOTHER, EM_LIMITTEXT, (WPARAM)(ui.a->parent_name_bytes - 1), 0);
        wsprintfA(text, "Heads 0-%d, bodies 0-%d.", ui.a->head_count - 1, ui.a->body_count - 1);
        SetDlgItemTextA(window, IDC_PA_RANGE, text);
        return TRUE;
    }
    if (message == WM_COMMAND && LOWORD(wparam) == IDOK) {
        ce_change *p = &ui.parents;
        int values[4];
        int ids[4] = { IDC_PA_FATHER_HEAD, IDC_PA_FATHER_BODY, IDC_PA_MOTHER_HEAD, IDC_PA_MOTHER_BODY };
        int limits[4];
        int i;
        limits[0] = limits[2] = ui.a->head_count;
        limits[1] = limits[3] = ui.a->body_count;
        GetDlgItemTextA(window, IDC_PA_FATHER, p->father_name, CE_NAME_BYTES);
        GetDlgItemTextA(window, IDC_PA_MOTHER, p->mother_name, CE_NAME_BYTES);
        if (!ce_text_ok(p->father_name, 0) || !ce_text_ok(p->mother_name, 0)) {
            ui_message(window, "A name may use letters, numbers, spaces and . , ! ? : - ' only.");
            return TRUE;
        }
        for (i = 0; i < 4; ++i) {
            values[i] = ui_number(window, ids[i]);
            if (values[i] != CE_KEEP && (values[i] < 0 || values[i] >= limits[i])) {
                ui_message(window, i % 2 == 0 ? "A head is out of range for this game."
                                              : "A body is out of range for this game.");
                return TRUE;
            }
        }
        p->father_head = values[0];
        p->father_body = values[1];
        p->mother_head = values[2];
        p->mother_body = values[3];
        p->parents_set = p->father_name[0] != '\0' || p->mother_name[0] != '\0'
            || values[0] != CE_KEEP || values[1] != CE_KEEP || values[2] != CE_KEEP
            || values[3] != CE_KEEP;
        EndDialog(window, IDOK);
        return TRUE;
    }
    if ((message == WM_COMMAND && LOWORD(wparam) == IDCANCEL) || message == WM_CLOSE) {
        EndDialog(window, IDCANCEL);
        return TRUE;
    }
    return FALSE;
}

/* ---- The unborn baby's father dialog ------------------------------------ */

static INT_PTR CALLBACK ui_unborn_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    char text[96];
    (void)lparam;
    if (message == WM_INITDIALOG) {
        SendDlgItemMessageA(window, IDC_UB_NAME, EM_LIMITTEXT, (WPARAM)(ui.a->parent_name_bytes - 2), 0);
        wsprintfA(text, "Heads 0-%d, bodies 0-%d.", ui.a->head_count - 1, ui.a->body_count - 1);
        SetDlgItemTextA(window, IDC_UB_RANGE, text);
        return TRUE;
    }
    if (message == WM_COMMAND && LOWORD(wparam) == IDOK) {
        ce_change *u = &ui.unborn;
        int head = ui_number(window, IDC_UB_HEAD);
        int body = ui_number(window, IDC_UB_BODY);
        GetDlgItemTextA(window, IDC_UB_NAME, u->unborn_name, CE_NAME_BYTES);
        if (!ce_text_ok(u->unborn_name, 0)) {
            ui_message(window, "A name may use letters, numbers, spaces and . , ! ? : - ' only.");
            return TRUE;
        }
        if ((head != CE_KEEP && (head < 0 || head >= ui.a->head_count))
            || (body != CE_KEEP && (body < 0 || body >= ui.a->body_count))) {
            ui_message(window, "A head or body is out of range for this game.");
            return TRUE;
        }
        u->unborn_head = head;
        u->unborn_body = body;
        u->unborn_set = u->unborn_name[0] != '\0' || head != CE_KEEP || body != CE_KEEP;
        EndDialog(window, IDOK);
        return TRUE;
    }
    if ((message == WM_COMMAND && LOWORD(wparam) == IDCANCEL) || message == WM_CLOSE) {
        EndDialog(window, IDCANCEL);
        return TRUE;
    }
    return FALSE;
}

/* ---- The villager changes dialog --------------------------------------- */

static unsigned int ui_toggles(HWND window) {
    unsigned int toggles = 0;
    int i;
    for (i = 0; i < 5; ++i) {
        if (IsDlgButtonChecked(window, IDC_CH_TOGGLE_FIRST + i) == BST_CHECKED) {
            toggles |= UI_TOGGLE_BITS[i];
        }
    }
    return toggles;
}

/* The chosen villagers: the list's selection combined with the toggles,
   each villager once (story_resolve_targets). */
static int ui_targets(HWND window, int *out) {
    unsigned char picked[UI_ROSTER_MAX];
    int i;
    memset(picked, 0, sizeof picked);
    for (i = 0; i < ui.roster_count; ++i) {
        if (SendDlgItemMessageA(window, IDC_CH_LIST, LB_GETSEL, (WPARAM)i, 0) > 0) {
            int position = (int)SendDlgItemMessageA(window, IDC_CH_LIST, LB_GETITEMDATA, (WPARAM)i, 0);
            if (position >= 0 && position < ui.roster_count) {
                picked[position] = 1;
            }
        }
    }
    return story_resolve_targets(ui.roster, ui.roster_count, picked, ui_toggles(window),
                                 ui.a->adult_age, out, UI_ROSTER_MAX);
}

static void ui_show_count(HWND window) {
    int targets[UI_ROSTER_MAX];
    char text[96];
    int n = ui_targets(window, targets);
    wsprintfA(text, n == 1 ? "1 villager chosen." : "%d villagers chosen.", n);
    SetDlgItemTextA(window, IDC_CH_COUNT, text);
}

static int ui_change_is_empty(const ce_change *c) {
    int i;
    if (c->fate != CE_FATE_NONE || c->sick || c->litter != 0 || c->unborn_set || c->head != CE_KEEP
        || c->body != CE_KEEP || c->like_add >= 0 || c->like_remove >= 0
        || c->dislike_add >= 0 || c->dislike_remove >= 0 || c->title_op != CE_TITLE_KEEP
        || c->mask != CE_KEEP || c->status != CE_KEEP || c->behaviour != CE_KEEP
        || c->parents_set) {
        return 0;
    }
    for (i = 0; i < CE_SKILLS; ++i) {
        if (c->skills[i] != CE_KEEP) {
            return 0;
        }
    }
    return 1;
}

static void ce_change_init(ce_change *c) {
    int i;
    memset(c, 0, sizeof *c);
    c->index = -1;
    c->father = -1;
    c->head = c->body = CE_KEEP;
    c->like_add = c->like_remove = c->dislike_add = c->dislike_remove = -1;
    for (i = 0; i < CE_SKILLS; ++i) {
        c->skills[i] = CE_KEEP;
    }
    c->mask = c->status = c->behaviour = CE_KEEP;
    c->father_head = c->father_body = c->mother_head = c->mother_body = CE_KEEP;
    c->unborn_head = c->unborn_body = CE_KEEP;
    c->unborn_skill = c->unborn_skill_value = CE_KEEP;
}

/* Merge `t` (the dialog's changes) into the draft's entry for villager
   `index`, creating it: every field `t` sets replaces the earlier one. */
static int ce_merge(ce_event *e, const ce_change *t, int index, unsigned int fingerprint) {
    ce_change *c = NULL;
    int i;
    for (i = 0; i < e->change_count; ++i) {
        if (e->changes[i].index == index) {
            c = &e->changes[i];
            break;
        }
    }
    if (c == NULL) {
        if (e->change_count >= CE_MAX_CHANGES) {
            return 0;
        }
        c = &e->changes[e->change_count++];
        ce_change_init(c);
        c->index = index;
    }
    c->fingerprint = fingerprint;
    if (t->fate != CE_FATE_NONE) c->fate = t->fate;
    if (t->sick) c->sick = 1;
    if (t->litter != 0) {
        c->litter = t->litter;
        c->father = t->father;
        c->father_fingerprint = t->father_fingerprint;
    }
    if (t->unborn_set) {
        c->unborn_set = 1;
        if (t->unborn_name[0]) lstrcpynA(c->unborn_name, t->unborn_name, CE_NAME_BYTES);
        if (t->unborn_head != CE_KEEP) c->unborn_head = t->unborn_head;
        if (t->unborn_body != CE_KEEP) c->unborn_body = t->unborn_body;
    }
    if (t->head != CE_KEEP) c->head = t->head;
    if (t->body != CE_KEEP) c->body = t->body;
    if (t->like_add >= 0) c->like_add = t->like_add;
    if (t->like_remove >= 0) c->like_remove = t->like_remove;
    if (t->dislike_add >= 0) c->dislike_add = t->dislike_add;
    if (t->dislike_remove >= 0) c->dislike_remove = t->dislike_remove;
    for (i = 0; i < CE_SKILLS; ++i) {
        if (t->skills[i] != CE_KEEP) c->skills[i] = t->skills[i];
    }
    if (t->title_op != CE_TITLE_KEEP) {
        c->title_op = t->title_op;
        lstrcpynA(c->title, t->title, sizeof c->title);
    }
    if (t->mask != CE_KEEP) c->mask = t->mask;
    if (t->status != CE_KEEP) c->status = t->status;
    if (t->behaviour != CE_KEEP) c->behaviour = t->behaviour;
    if (t->parents_set) {
        c->parents_set = 1;
        if (t->father_name[0]) lstrcpynA(c->father_name, t->father_name, CE_NAME_BYTES);
        if (t->mother_name[0]) lstrcpynA(c->mother_name, t->mother_name, CE_NAME_BYTES);
        if (t->father_head != CE_KEEP) c->father_head = t->father_head;
        if (t->father_body != CE_KEEP) c->father_body = t->father_body;
        if (t->mother_head != CE_KEEP) c->mother_head = t->mother_head;
        if (t->mother_body != CE_KEEP) c->mother_body = t->mother_body;
    }
    return 1;
}

/* Read the changes dialog into `t`; 0 (after saying why) when a value is
   refused. */
static int ui_read_changes(HWND window, ce_change *t, const int *targets, int count) {
    char text[64];
    int i;
    ce_change_init(t);
    t->fate = ui_combo_data(window, IDC_CH_FATE);
    if (t->fate < 0) t->fate = CE_FATE_NONE;
    t->sick = IsDlgButtonChecked(window, IDC_CH_SICK) == BST_CHECKED;
    t->litter = ui_combo_data(window, IDC_CH_PREGNANCY);
    if (t->litter < CE_LITTER_CANCEL || t->litter > 3) t->litter = 0;
    t->father = ui_combo_data(window, IDC_CH_FATHER);
    if (t->litter > 0 && t->father >= 0) {
        const unsigned char *father = ui.a->record(t->father);
        t->father_fingerprint = father != NULL ? ce_identity(ui.a, father) : 0;
    } else {
        t->father = -1;
    }
    t->head = ui_number(window, IDC_CH_HEAD);
    t->body = ui_number(window, IDC_CH_BODY);
    if ((t->head != CE_KEEP && (t->head < 0 || t->head >= ui.a->head_count))
        || (t->body != CE_KEEP && (t->body < 0 || t->body >= ui.a->body_count))) {
        wsprintfA(text, "Heads are 0-%d and bodies 0-%d in this game.",
                  ui.a->head_count - 1, ui.a->body_count - 1);
        ui_message(window, text);
        return 0;
    }
    t->like_add = ui_combo_data(window, IDC_CH_LIKE_ADD);
    t->like_remove = ui_combo_data(window, IDC_CH_LIKE_REMOVE);
    t->dislike_add = ui_combo_data(window, IDC_CH_DISLIKE_ADD);
    t->dislike_remove = ui_combo_data(window, IDC_CH_DISLIKE_REMOVE);
    for (i = 0; i < ui.a->skill_count && i < CE_SKILLS; ++i) {
        t->skills[i] = ui_number(window, IDC_CH_SKILL_FIRST + i);
        if (t->skills[i] != CE_KEEP && (t->skills[i] < 0 || t->skills[i] > 100)) {
            ui_message(window, "Skills are 0-100.");
            return 0;
        }
    }
    if (IsDlgButtonChecked(window, IDC_CH_TITLE_CLEAR) == BST_CHECKED) {
        t->title_op = CE_TITLE_CLEAR;
    } else {
        GetDlgItemTextA(window, IDC_CH_TITLE, t->title, sizeof t->title);
        if (t->title[0] != '\0') {
            if (!ce_text_ok(t->title, 0) || !vv_title_valid(t->title)) {
                ui_message(window, "A title is 1-31 letters, numbers, spaces and . , ! ? : - ' only.");
                return 0;
            }
            t->title_op = CE_TITLE_SET;
        }
    }
    t->mask = ui_combo_data(window, IDC_CH_MASK);
    if (!(ui.a->caps & CAP_MASK)) t->mask = CE_KEEP;
    t->status = ui_combo_data(window, IDC_CH_STATUS);
    if (!(ui.a->caps & CAP_STATUS)) t->status = CE_KEEP;
    t->behaviour = ui_combo_data(window, IDC_CH_BEHAVIOUR);
    if (!(ui.a->caps & CAP_BEHAVIOUR)) t->behaviour = CE_KEEP;
    if (ui.unborn_chosen && ui.unborn.unborn_set && (ui.a->caps & CAP_UNBORN)) {
        t->unborn_set = 1;
        lstrcpynA(t->unborn_name, ui.unborn.unborn_name, CE_NAME_BYTES);
        t->unborn_head = ui.unborn.unborn_head;
        t->unborn_body = ui.unborn.unborn_body;
    }
    if (ui.parents_chosen && ui.parents.parents_set) {
        t->parents_set = 1;
        lstrcpynA(t->father_name, ui.parents.father_name, CE_NAME_BYTES);
        lstrcpynA(t->mother_name, ui.parents.mother_name, CE_NAME_BYTES);
        t->father_head = ui.parents.father_head;
        t->father_body = ui.parents.father_body;
        t->mother_head = ui.parents.mother_head;
        t->mother_body = ui.parents.mother_body;
    }
    if (count == 0) {
        ui_message(window, "Choose at least one villager (or tick a group).");
        return 0;
    }
    if (ui_change_is_empty(t)) {
        ui_message(window, "Choose at least one change.");
        return 0;
    }
    if (t->litter > 0 || t->unborn_set) {
        for (i = 0; i < count; ++i) {
            int position = ui_roster_position(targets[i]);
            const story_member *m = &ui.roster[position];
            if (m->age < ui.a->min_carrier_age) {
                wsprintfA(text, "%s is too young: in this game a pregnancy needs an age of %d years or more.",
                          ui.names[position], ui.a->min_carrier_age / 20);
                ui_message(window, text);
                return 0;
            }
            if (m->sex == STORY_SEX_MALE && !(ui.a->caps & CAP_MALE_PREGNANCY)) {
                wsprintfA(text, "%s is male; in this game only females can be pregnant.",
                          ui.names[position]);
                ui_message(window, text);
                return 0;
            }
            if (t->father == targets[i]) {
                ui_message(window, "A villager can not be the father of their own baby.");
                return 0;
            }
        }
    }
    return 1;
}

static void ui_setup_changes(HWND window) {
    const ce_adapter *a = ui.a;
    char text[128];
    char years[16];
    int i;
    ui_load_roster();
    for (i = 0; i < ui.roster_count; ++i) {
        int row;
        const char *custom = titles_lookup(ui.game, a->record(ui.roster[i].index));
        wsprintfA(text, "%s (%s, %s)%s%s", ui.names[i],
                  ui.roster[i].sex == STORY_SEX_MALE ? "male" : "female",
                  ui_years(ui.roster[i].age, years),
                  custom != NULL ? " - " : "", custom != NULL ? custom : "");
        row = (int)SendDlgItemMessageA(window, IDC_CH_LIST, LB_ADDSTRING, 0, (LPARAM)text);
        SendDlgItemMessageA(window, IDC_CH_LIST, LB_SETITEMDATA, (WPARAM)row, (LPARAM)i);
    }
    for (i = 0; i < 5; ++i) {
        SetDlgItemTextA(window, IDC_CH_TOGGLE_FIRST + i, UI_TOGGLE_NAMES[i]);
    }
    ui_combo_add(window, IDC_CH_FATE, "No change", CE_FATE_NONE);
    if (a->caps & CAP_KILL) ui_combo_add(window, IDC_CH_FATE, "Dies (leaves a skeleton)", CE_FATE_KILL);
    if (a->caps & CAP_VANISH) ui_combo_add(window, IDC_CH_FATE, "Disappears (no skeleton)", CE_FATE_VANISH);
    SendDlgItemMessageA(window, IDC_CH_FATE, CB_SETCURSEL, 0, 0);
    ui_combo_add(window, IDC_CH_PREGNANCY, "No change", 0);
    if (a->caps & CAP_CANCEL) {
        ui_combo_add(window, IDC_CH_PREGNANCY, "Not pregnant (0 babies)", CE_LITTER_CANCEL);
    }
    ui_combo_add(window, IDC_CH_PREGNANCY, "Pregnant with a baby", 1);
    ui_combo_add(window, IDC_CH_PREGNANCY, "Pregnant with twins", 2);
    ui_combo_add(window, IDC_CH_PREGNANCY, "Pregnant with triplets", 3);
    SendDlgItemMessageA(window, IDC_CH_PREGNANCY, CB_SETCURSEL, 0, 0);
    ui_combo_add(window, IDC_CH_FATHER, "Unknown", -1);
    for (i = 0; i < ui.roster_count; ++i) {
        if (ui.roster[i].sex == STORY_SEX_MALE && ui.roster[i].age >= a->adult_age) {
            ui_combo_add(window, IDC_CH_FATHER, ui.names[i], ui.roster[i].index);
        }
    }
    SendDlgItemMessageA(window, IDC_CH_FATHER, CB_SETCURSEL, 0, 0);
    wsprintfA(text, "heads 0-%d, bodies 0-%d", a->head_count - 1, a->body_count - 1);
    SetDlgItemTextA(window, IDC_CH_LOOK_RANGE, text);
    ui_fill_prefs(window, IDC_CH_LIKE_ADD, "No change");
    ui_fill_prefs(window, IDC_CH_LIKE_REMOVE, "No change");
    ui_fill_prefs(window, IDC_CH_DISLIKE_ADD, "No change");
    ui_fill_prefs(window, IDC_CH_DISLIKE_REMOVE, "No change");
    for (i = 0; i < CE_SKILLS; ++i) {
        int shown = (a->caps & CAP_SKILLS) && i < a->skill_count;
        SetDlgItemTextA(window, IDC_CH_SKILL_LABEL_FIRST + i, shown ? a->skill_names[i] : "");
        ShowWindow(GetDlgItem(window, IDC_CH_SKILL_FIRST + i), shown ? SW_SHOW : SW_HIDE);
    }
    SendDlgItemMessageA(window, IDC_CH_TITLE, EM_LIMITTEXT, VV_TITLE_MAX, 0);
    if (a->caps & CAP_MASK) {
        ui_fill_masks(window, IDC_CH_MASK, "No change");
    }
    ui_fill_choices(window, IDC_CH_STATUS, a->statuses, a->status_count);
    ui_combo_add(window, IDC_CH_BEHAVIOUR, "No change", CE_KEEP);
    for (i = 0; i < a->behaviour_count; ++i) {
        ui_combo_add(window, IDC_CH_BEHAVIOUR, a->behaviours[i].label, i);
    }
    SendDlgItemMessageA(window, IDC_CH_BEHAVIOUR, CB_SETCURSEL, 0, 0);

    ui_enable(window, IDC_CH_FATE, (a->caps & (CAP_KILL | CAP_VANISH)) != 0);
    ui_enable(window, IDC_CH_SICK, (a->caps & CAP_SICK) != 0);
    ui_enable(window, IDC_CH_PREGNANCY, (a->caps & CAP_PREGNANT) != 0);
    ui_enable(window, IDC_CH_FATHER, (a->caps & CAP_PREGNANT) != 0);
    ui_enable(window, IDC_CH_HEAD, (a->caps & CAP_APPEARANCE) != 0);
    ui_enable(window, IDC_CH_BODY, (a->caps & CAP_APPEARANCE) != 0);
    ui_enable(window, IDC_CH_LIKE_ADD, (a->caps & CAP_PREFS) != 0);
    ui_enable(window, IDC_CH_LIKE_REMOVE, (a->caps & CAP_PREFS) != 0);
    ui_enable(window, IDC_CH_DISLIKE_ADD, (a->caps & CAP_PREFS) != 0);
    ui_enable(window, IDC_CH_DISLIKE_REMOVE, (a->caps & CAP_PREFS) != 0);
    ui_enable(window, IDC_CH_TITLE, (a->caps & CAP_TITLE) != 0);
    ui_enable(window, IDC_CH_TITLE_CLEAR, (a->caps & CAP_TITLE) != 0);
    ui_enable(window, IDC_CH_MASK, (a->caps & CAP_MASK) != 0);
    ui_enable(window, IDC_CH_STATUS, (a->caps & CAP_STATUS) != 0);
    ui_enable(window, IDC_CH_BEHAVIOUR, (a->caps & CAP_BEHAVIOUR) != 0);
    ui_enable(window, IDC_CH_PARENTS, (a->caps & CAP_PARENTS) != 0 && a->parents_supported());
    ui_enable(window, IDC_CH_UNBORN, (a->caps & CAP_UNBORN) != 0);
    SetDlgItemTextA(window, IDC_CH_NOTE,
                    "A villager who dies or disappears gets no other change. A pregnancy that "
                    "is already on its way changes its number of babies. \"Not in this "
                    "game...\" lists what is unavailable.");
    ui.parents_chosen = 0;
    ui.unborn_chosen = 0;
    ui_show_count(window);
}

static INT_PTR CALLBACK ui_changes_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    (void)lparam;
    if (message == WM_INITDIALOG) {
        ui_setup_changes(window);
        return TRUE;
    }
    if (message == WM_COMMAND) {
        int id = LOWORD(wparam);
        if ((id == IDC_CH_LIST && HIWORD(wparam) == LBN_SELCHANGE)
            || (id >= IDC_CH_TOGGLE_FIRST && id < IDC_CH_TOGGLE_FIRST + 5)) {
            ui_show_count(window);
            return TRUE;
        }
        if (id == IDC_CH_UNBORN) {
            ce_change_init(&ui.unborn);
            if (DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_UNBORN), window,
                                ui_unborn_dialog, 0) == IDOK) {
                ui.unborn_chosen = ui.unborn.unborn_set;
                SetDlgItemTextA(window, IDC_CH_UNBORN_NOTE,
                                ui.unborn_chosen ? "The baby's father will change." : "");
            }
            return TRUE;
        }
        if (id == IDC_CH_PARENTS) {
            ce_change_init(&ui.parents);
            if (DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_PARENTS), window,
                                ui_parents_dialog, 0) == IDOK) {
                ui.parents_chosen = ui.parents.parents_set;
                SetDlgItemTextA(window, IDC_CH_PARENTS_NOTE,
                                ui.parents_chosen ? "Parents will change." : "");
            }
            return TRUE;
        }
        if (id == IDOK) {
            int targets[UI_ROSTER_MAX];
            int count = ui_targets(window, targets);
            ce_change t;
            int i;
            if (!ui_read_changes(window, &t, targets, count)) {
                return TRUE;
            }
            for (i = 0; i < count; ++i) {
                const unsigned char *record = ui.a->record(targets[i]);
                if (record == NULL || !ce_merge(&ui.draft, &t, targets[i], ce_identity(ui.a, record))) {
                    ui_message(window, "The event can hold changes for 256 villagers at most.");
                    break;
                }
            }
            EndDialog(window, IDOK);
            return TRUE;
        }
        if (id == IDCANCEL) {
            EndDialog(window, IDCANCEL);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, IDCANCEL);
        return TRUE;
    }
    return FALSE;
}

/* ---- The new villagers dialog ------------------------------------------ */

static INT_PTR CALLBACK ui_spawn_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    const ce_adapter *a = ui.a;
    char text[128];
    int i;
    (void)lparam;
    if (message == WM_INITDIALOG) {
        SetDlgItemTextA(window, IDC_SP_COUNT, "1");
        ui_combo_add(window, IDC_SP_SEX, "Male", STORY_SEX_MALE);
        ui_combo_add(window, IDC_SP_SEX, "Female", STORY_SEX_FEMALE);
        SendDlgItemMessageA(window, IDC_SP_SEX, CB_SETCURSEL, 0, 0);
        wsprintfA(text, "%d-%d years", (a->min_spawn_age + 19) / 20, a->max_spawn_age / 20);
        SetDlgItemTextA(window, IDC_SP_AGE_RANGE, text);
        SetDlgItemInt(window, IDC_SP_AGE, (UINT)((a->adult_age + 19) / 20 + 4), FALSE);
        SendDlgItemMessageA(window, IDC_SP_NAME, EM_LIMITTEXT,
                            (WPARAM)((a->name_bytes < CE_NAME_BYTES ? a->name_bytes : CE_NAME_BYTES) - 1), 0);
        wsprintfA(text, "0-%d / 0-%d", a->head_count - 1, a->body_count - 1);
        SetDlgItemTextA(window, IDC_SP_LOOK_RANGE, text);
        for (i = 0; i < CE_SPAWN_PREFS; ++i) {
            ui_fill_prefs(window, IDC_SP_LIKE_FIRST + i, i == 0 ? "(game's choice)" : "(none)");
            ui_fill_prefs(window, IDC_SP_DISLIKE_FIRST + i, i == 0 ? "(game's choice)" : "(none)");
            if (!(a->caps & CAP_PREFS)) {
                ui_enable(window, IDC_SP_LIKE_FIRST + i, 0);
                ui_enable(window, IDC_SP_DISLIKE_FIRST + i, 0);
            }
        }
        for (i = 0; i < CE_SKILLS; ++i) {
            int shown = (a->caps & CAP_SKILLS) && i < a->skill_count;
            SetDlgItemTextA(window, IDC_SP_SKILL_LABEL_FIRST + i, shown ? a->skill_names[i] : "");
            ShowWindow(GetDlgItem(window, IDC_SP_SKILL_FIRST + i), shown ? SW_SHOW : SW_HIDE);
        }
        SendDlgItemMessageA(window, IDC_SP_TITLE, EM_LIMITTEXT, VV_TITLE_MAX, 0);
        if (a->caps & CAP_MASK) {
            ui_fill_masks(window, IDC_SP_MASK, "(none)");
        }
        ui_enable(window, IDC_SP_MASK, (a->caps & CAP_MASK) != 0);
        ui_combo_add(window, IDC_SP_FACTION, "(the game's own)", CE_KEEP);
        if (a->caps & CAP_SPAWN_FACTION) {
            for (i = 0; i < a->faction_count && i < a->status_count; ++i) {
                ui_combo_add(window, IDC_SP_FACTION, a->statuses[i], i);
            }
        }
        SendDlgItemMessageA(window, IDC_SP_FACTION, CB_SETCURSEL, 0, 0);
        ui_enable(window, IDC_SP_FACTION, (a->caps & CAP_SPAWN_FACTION) != 0);
        ui_enable(window, IDC_SP_NAME, (a->caps & CAP_SPAWN_NAME) != 0);
        ui_enable(window, IDC_SP_HEAD, (a->caps & CAP_APPEARANCE) != 0);
        ui_enable(window, IDC_SP_BODY, (a->caps & CAP_APPEARANCE) != 0);
        ui_enable(window, IDC_SP_TITLE, (a->caps & CAP_TITLE) != 0);
        SetDlgItemTextA(window, IDC_SP_NOTE, "New villagers are made only while the village has room.");
        return TRUE;
    }
    if (message == WM_COMMAND && LOWORD(wparam) == IDOK) {
        ce_spawn *s = &ui.spawn;
        int years;
        memset(s, 0, sizeof *s);
        s->count = ui_number(window, IDC_SP_COUNT);
        if (s->count < 1 || s->count > CE_MAX_SPAWN_COUNT) {
            wsprintfA(text, "Make 1-%d villagers of one kind at a time.", CE_MAX_SPAWN_COUNT);
            ui_message(window, text);
            return TRUE;
        }
        s->sex = ui_combo_data(window, IDC_SP_SEX);
        years = ui_number(window, IDC_SP_AGE);
        if (years == CE_KEEP || years < 0 || years * 20 < a->min_spawn_age || years * 20 > a->max_spawn_age) {
            wsprintfA(text, "The age must be %d-%d years.", (a->min_spawn_age + 19) / 20,
                      a->max_spawn_age / 20);
            ui_message(window, text);
            return TRUE;
        }
        s->age = years * 20;
        GetDlgItemTextA(window, IDC_SP_NAME, s->name, CE_NAME_BYTES);
        if (!ce_text_ok(s->name, 0) || lstrlenA(s->name) >= a->name_bytes) {
            ui_message(window, "A name may use letters, numbers, spaces and . , ! ? : - ' only.");
            return TRUE;
        }
        s->head = ui_number(window, IDC_SP_HEAD);
        s->body = ui_number(window, IDC_SP_BODY);
        if ((s->head != CE_KEEP && (s->head < 0 || s->head >= a->head_count))
            || (s->body != CE_KEEP && (s->body < 0 || s->body >= a->body_count))) {
            wsprintfA(text, "Heads are 0-%d and bodies 0-%d in this game.", a->head_count - 1,
                      a->body_count - 1);
            ui_message(window, text);
            return TRUE;
        }
        s->prefs_set = 0;
        for (i = 0; i < CE_SPAWN_PREFS; ++i) {
            s->likes[i] = (a->caps & CAP_PREFS) ? ui_combo_data(window, IDC_SP_LIKE_FIRST + i) : -1;
            s->dislikes[i] = (a->caps & CAP_PREFS) ? ui_combo_data(window, IDC_SP_DISLIKE_FIRST + i) : -1;
            if (s->likes[i] >= 0 || s->dislikes[i] >= 0) {
                s->prefs_set = 1;
            }
        }
        for (i = 0; i < CE_SKILLS; ++i) {
            s->skills[i] = (i < a->skill_count && (a->caps & CAP_SKILLS))
                ? ui_number(window, IDC_SP_SKILL_FIRST + i) : CE_KEEP;
            if (s->skills[i] != CE_KEEP && (s->skills[i] < 0 || s->skills[i] > 100)) {
                ui_message(window, "Skills are 0-100.");
                return TRUE;
            }
        }
        GetDlgItemTextA(window, IDC_SP_TITLE, s->title, sizeof s->title);
        if (s->title[0] != '\0' && (!ce_text_ok(s->title, 0) || !vv_title_valid(s->title))) {
            ui_message(window, "A title is 1-31 letters, numbers, spaces and . , ! ? : - ' only.");
            return TRUE;
        }
        s->mask = (a->caps & CAP_MASK) ? ui_combo_data(window, IDC_SP_MASK) : CE_KEEP;
        s->faction = (a->caps & CAP_SPAWN_FACTION) ? ui_combo_data(window, IDC_SP_FACTION) : CE_KEEP;
        EndDialog(window, IDOK);
        return TRUE;
    }
    if ((message == WM_COMMAND && LOWORD(wparam) == IDCANCEL) || message == WM_CLOSE) {
        EndDialog(window, IDCANCEL);
        return TRUE;
    }
    return FALSE;
}

/* ---- The amounts dialog ------------------------------------------------ */

static void ui_values_fill(HWND window) {
    char text[200];
    int i;
    int sel = (int)SendDlgItemMessageA(window, IDC_VA_LIST, LB_GETCURSEL, 0, 0);
    SendDlgItemMessageA(window, IDC_VA_LIST, LB_RESETCONTENT, 0, 0);
    for (i = 0; i < ui.a->value_count && i < CE_MAX_VALUES; ++i) {
        const ce_value_def *d = &ui.a->values[i];
        int now = ui.a->value_get(i);
        char *p = text;
        p += wsprintfA(p, "%s (%d-%d): ", d->name, d->min, d->max);
        p += now < 0 ? wsprintfA(p, "not there yet") : wsprintfA(p, "now %d", now);
        if (ui.values[i] != CE_KEEP) {
            wsprintfA(p, "  ->  %d", ui.values[i]);
        }
        SendDlgItemMessageA(window, IDC_VA_LIST, LB_ADDSTRING, 0, (LPARAM)text);
    }
    if (sel >= 0) {
        SendDlgItemMessageA(window, IDC_VA_LIST, LB_SETCURSEL, (WPARAM)sel, 0);
    }
}

static INT_PTR CALLBACK ui_values_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    int i;
    (void)lparam;
    if (message == WM_INITDIALOG) {
        for (i = 0; i < CE_MAX_VALUES; ++i) {
            ui.values[i] = CE_KEEP;
        }
        for (i = 0; i < ui.draft.value_count; ++i) {
            ui.values[ui.draft.values[i].which] = ui.draft.values[i].amount;
        }
        ui_values_fill(window);
        return TRUE;
    }
    if (message == WM_COMMAND) {
        int id = LOWORD(wparam);
        int sel = (int)SendDlgItemMessageA(window, IDC_VA_LIST, LB_GETCURSEL, 0, 0);
        if (id == IDC_VA_LIST && HIWORD(wparam) == LBN_SELCHANGE) {
            SetDlgItemTextA(window, IDC_VA_NOTE,
                            sel >= 0 && ui.a->values[sel].note != NULL ? ui.a->values[sel].note : "");
            return TRUE;
        }
        if (id == IDC_VA_SET || id == IDC_VA_KEEP) {
            char text[96];
            int amount;
            if (sel < 0 || sel >= ui.a->value_count) {
                ui_message(window, "Choose a food source or store first.");
                return TRUE;
            }
            if (id == IDC_VA_KEEP) {
                ui.values[sel] = CE_KEEP;
            } else {
                amount = ui_number(window, IDC_VA_AMOUNT);
                if (amount == CE_KEEP || amount < ui.a->values[sel].min || amount > ui.a->values[sel].max) {
                    wsprintfA(text, "Type an amount from %d to %d.", ui.a->values[sel].min,
                              ui.a->values[sel].max);
                    ui_message(window, text);
                    return TRUE;
                }
                ui.values[sel] = amount;
            }
            ui_values_fill(window);
            return TRUE;
        }
        if (id == IDOK) {
            ui.draft.value_count = 0;
            for (i = 0; i < ui.a->value_count && i < CE_MAX_VALUES; ++i) {
                if (ui.values[i] != CE_KEEP) {
                    ui.draft.values[ui.draft.value_count].which = i;
                    ui.draft.values[ui.draft.value_count].amount = ui.values[i];
                    ++ui.draft.value_count;
                }
            }
            EndDialog(window, IDOK);
            return TRUE;
        }
        if (id == IDCANCEL) {
            EndDialog(window, IDCANCEL);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, IDCANCEL);
        return TRUE;
    }
    return FALSE;
}

/* ---- The puzzles dialog ------------------------------------------------- */

static void ui_puzzles_fill(HWND window) {
    char text[200];
    int i;
    int top = (int)SendDlgItemMessageA(window, IDC_PZ_LIST, LB_GETTOPINDEX, 0, 0);
    int count = ui.a->puzzle_count < CE_MAX_PUZZLES ? ui.a->puzzle_count : CE_MAX_PUZZLES;
    unsigned char selected[CE_MAX_PUZZLES];
    for (i = 0; i < count; ++i) {
        selected[i] = SendDlgItemMessageA(window, IDC_PZ_LIST, LB_GETSEL, (WPARAM)i, 0) > 0;
    }
    SendDlgItemMessageA(window, IDC_PZ_LIST, LB_RESETCONTENT, 0, 0);
    for (i = 0; i < count; ++i) {
        const ce_puzzle_def *d = &ui.a->puzzles[i];
        wsprintfA(text, "%s: %s%s", d->name, ui.a->puzzle_solved(i) ? "solved" : "unsolved",
                  ui.puzzles[i] == 1 ? "  ->  solved" : ui.puzzles[i] == 0 ? "  ->  unsolved" : "");
        SendDlgItemMessageA(window, IDC_PZ_LIST, LB_ADDSTRING, 0, (LPARAM)text);
        if (selected[i]) {
            SendDlgItemMessageA(window, IDC_PZ_LIST, LB_SETSEL, TRUE, (LPARAM)i);
        }
    }
    SendDlgItemMessageA(window, IDC_PZ_LIST, LB_SETTOPINDEX, (WPARAM)top, 0);
}

static INT_PTR CALLBACK ui_puzzles_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    int i;
    int count = ui.a->puzzle_count < CE_MAX_PUZZLES ? ui.a->puzzle_count : CE_MAX_PUZZLES;
    (void)lparam;
    if (message == WM_INITDIALOG) {
        for (i = 0; i < CE_MAX_PUZZLES; ++i) {
            ui.puzzles[i] = -1;
        }
        for (i = 0; i < ui.draft.puzzle_count; ++i) {
            ui.puzzles[ui.draft.puzzles[i].which] = ui.draft.puzzles[i].solved;
        }
        ui_puzzles_fill(window);
        return TRUE;
    }
    if (message == WM_COMMAND) {
        int id = LOWORD(wparam);
        if (id == IDC_PZ_LIST && HIWORD(wparam) == LBN_SELCHANGE) {
            int caret = (int)SendDlgItemMessageA(window, IDC_PZ_LIST, LB_GETCARETINDEX, 0, 0);
            SetDlgItemTextA(window, IDC_PZ_NOTE, caret >= 0 && caret < count
                            && ui.a->puzzles[caret].note != NULL ? ui.a->puzzles[caret].note : "");
            return TRUE;
        }
        if (id == IDC_PZ_SOLVE || id == IDC_PZ_UNSOLVE || id == IDC_PZ_KEEP) {
            int refused = 0;
            for (i = 0; i < count; ++i) {
                if (SendDlgItemMessageA(window, IDC_PZ_LIST, LB_GETSEL, (WPARAM)i, 0) <= 0) {
                    continue;
                }
                if (id == IDC_PZ_KEEP) {
                    ui.puzzles[i] = -1;
                } else if (id == IDC_PZ_SOLVE ? ui.a->puzzles[i].can_solve : ui.a->puzzles[i].can_unsolve) {
                    ui.puzzles[i] = id == IDC_PZ_SOLVE ? 1 : 0;
                } else {
                    ++refused;
                }
            }
            ui_puzzles_fill(window);
            if (refused > 0) {
                ui_message(window, id == IDC_PZ_SOLVE
                    ? "Some of the chosen puzzles can not be marked solved here (see each one's note)."
                    : "Some of the chosen puzzles can not be marked unsolved here (see each one's note).");
            }
            return TRUE;
        }
        if (id == IDOK) {
            ui.draft.puzzle_count = 0;
            for (i = 0; i < count; ++i) {
                if (ui.puzzles[i] >= 0) {
                    ui.draft.puzzles[ui.draft.puzzle_count].which = i;
                    ui.draft.puzzles[ui.draft.puzzle_count].solved = ui.puzzles[i];
                    ++ui.draft.puzzle_count;
                }
            }
            EndDialog(window, IDOK);
            return TRUE;
        }
        if (id == IDCANCEL) {
            EndDialog(window, IDCANCEL);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, IDCANCEL);
        return TRUE;
    }
    return FALSE;
}

/* ---- The revive dialog --------------------------------------------------- */

/* The skeletons, oldest first (the owner's rule for any villager list the
   patcher builds), each with its record index as the row's data. */
static int ui_skeletons(int *out, int cap) {
    int n = 0;
    int i;
    int j;
    for (i = 0; i < ui.a->record_count && n < cap; ++i) {
        const unsigned char *r = ui.a->record(i);
        if (r != NULL && ui.a->skeleton(r)) {
            out[n++] = i;
        }
    }
    for (i = 1; i < n; ++i) {
        int index = out[i];
        int age = ce_age(ui.a, ui.a->record(index));
        for (j = i; j > 0 && ce_age(ui.a, ui.a->record(out[j - 1])) < age; --j) {
            out[j] = out[j - 1];
        }
        out[j] = index;
    }
    return n;
}

static INT_PTR CALLBACK ui_revive_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    (void)lparam;
    if (message == WM_INITDIALOG) {
        int skeletons[UI_ROSTER_MAX];
        int n = ui_skeletons(skeletons, UI_ROSTER_MAX);
        char name[CE_NAME_BYTES];
        char years[16];
        char text[96];
        int i;
        int k;
        for (i = 0; i < n; ++i) {
            const unsigned char *r = ui.a->record(skeletons[i]);
            int row;
            ce_copy_name(name, sizeof name, r + ui.a->off_name, ui.a->name_bytes);
            wsprintfA(text, "%s (%s, %s)", name, ce_sex(ui.a, r) == STORY_SEX_MALE ? "male" : "female",
                      ui_years(ce_age(ui.a, r), years));
            row = (int)SendDlgItemMessageA(window, IDC_RV_LIST, LB_ADDSTRING, 0, (LPARAM)text);
            SendDlgItemMessageA(window, IDC_RV_LIST, LB_SETITEMDATA, (WPARAM)row, (LPARAM)skeletons[i]);
            for (k = 0; k < ui.draft.revive_count; ++k) {
                if (ui.draft.revives[k].index == skeletons[i]) {
                    SendDlgItemMessageA(window, IDC_RV_LIST, LB_SETSEL, TRUE, (LPARAM)row);
                }
            }
        }
        if (n == 0) {
            SendDlgItemMessageA(window, IDC_RV_LIST, LB_ADDSTRING, 0, (LPARAM)"(no skeletons right now)");
            ui_enable(window, IDC_RV_LIST, 0);
            ui_enable(window, IDC_RV_ALL, 0);
        }
        SetDlgItemInt(window, IDC_RV_HEALTH, (UINT)(ui.draft.revive_count > 0 ? ui.draft.revives[0].health : 100),
                      FALSE);
        CheckDlgButton(window, IDC_RV_CURE,
                       ui.draft.revive_count == 0 || ui.draft.revives[0].cure ? BST_CHECKED : BST_UNCHECKED);
        SetDlgItemTextA(window, IDC_RV_NOTE,
                        "Only a villager who is still a skeleton can come back (a buried one is gone). "
                        "Each comes back only while the village has room. Without the cure a sick or "
                        "very old villager can die again within moments.");
        return TRUE;
    }
    if (message == WM_COMMAND) {
        int id = LOWORD(wparam);
        int rows = (int)SendDlgItemMessageA(window, IDC_RV_LIST, LB_GETCOUNT, 0, 0);
        int i;
        if (id == IDC_RV_ALL) {
            SendDlgItemMessageA(window, IDC_RV_LIST, LB_SETSEL, TRUE, (LPARAM)-1);
            return TRUE;
        }
        if (id == IDOK) {
            int health = ui_number(window, IDC_RV_HEALTH);
            int cure = IsDlgButtonChecked(window, IDC_RV_CURE) == BST_CHECKED;
            if (health == CE_KEEP || health < 1 || health > 100) {
                ui_message(window, "Health is 1-100.");
                return TRUE;
            }
            ui.draft.revive_count = 0;
            for (i = 0; i < rows && ui.draft.revive_count < CE_MAX_REVIVES; ++i) {
                int index;
                const unsigned char *r;
                if (SendDlgItemMessageA(window, IDC_RV_LIST, LB_GETSEL, (WPARAM)i, 0) <= 0) {
                    continue;
                }
                index = (int)SendDlgItemMessageA(window, IDC_RV_LIST, LB_GETITEMDATA, (WPARAM)i, 0);
                r = ui.a->record(index);
                if (r == NULL || !ui.a->skeleton(r)) {
                    continue;
                }
                ui.draft.revives[ui.draft.revive_count].index = index;
                ui.draft.revives[ui.draft.revive_count].identity = ce_identity(ui.a, r);
                ui.draft.revives[ui.draft.revive_count].health = health;
                ui.draft.revives[ui.draft.revive_count].cure = cure;
                ++ui.draft.revive_count;
            }
            EndDialog(window, IDOK);
            return TRUE;
        }
        if (id == IDCANCEL) {
            EndDialog(window, IDCANCEL);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, IDCANCEL);
        return TRUE;
    }
    return FALSE;
}

/* ---- The main dialog --------------------------------------------------- */

static void ui_describe_change(const ce_change *c, char *out) {
    char *p = out;
    int i;
    p += wsprintfA(p, "%s:", ui_name_of(c->index));
    if (c->fate == CE_FATE_KILL) p += wsprintfA(p, " dies");
    if (c->fate == CE_FATE_VANISH) p += wsprintfA(p, " disappears");
    if (c->sick) p += wsprintfA(p, " sick");
    if (c->litter == CE_LITTER_CANCEL) p += wsprintfA(p, " not pregnant");
    if (c->litter == 1) p += wsprintfA(p, " pregnant");
    if (c->litter == 2) p += wsprintfA(p, " twins");
    if (c->litter == 3) p += wsprintfA(p, " triplets");
    if (c->head != CE_KEEP) p += wsprintfA(p, " head %d", c->head);
    if (c->body != CE_KEEP) p += wsprintfA(p, " body %d", c->body);
    if (c->like_add >= 0 || c->like_remove >= 0 || c->dislike_add >= 0 || c->dislike_remove >= 0)
        p += wsprintfA(p, " likes/dislikes");
    for (i = 0; i < CE_SKILLS; ++i) {
        if (c->skills[i] != CE_KEEP) {
            p += wsprintfA(p, " skills");
            break;
        }
    }
    if (c->title_op == CE_TITLE_SET) p += wsprintfA(p, " title \"%s\"", c->title);
    if (c->title_op == CE_TITLE_CLEAR) p += wsprintfA(p, " no title");
    if (c->mask != CE_KEEP) p += wsprintfA(p, " mask");
    if (c->status != CE_KEEP) p += wsprintfA(p, " %s", ui.a->statuses[c->status]);
    if (c->behaviour != CE_KEEP) p += wsprintfA(p, " %s", ui.a->behaviours[c->behaviour].label);
    if (c->parents_set) p += wsprintfA(p, " parents");
    if (c->unborn_set) p += wsprintfA(p, " baby's father");
}

/* The amounts, puzzles and revivals the draft holds, one row each. */
static int ui_other_rows(void) {
    return ui.draft.value_count + ui.draft.puzzle_count + (ui.draft.revive_count > 0 ? 1 : 0);
}

static void ui_refresh_other(HWND window) {
    char text[256];
    int i;
    SendDlgItemMessageA(window, IDC_CE_OTHER, LB_RESETCONTENT, 0, 0);
    for (i = 0; i < ui.draft.value_count; ++i) {
        const ce_value *v = &ui.draft.values[i];
        wsprintfA(text, "%s: set to %d", ui.a->values[v->which].name, v->amount);
        SendDlgItemMessageA(window, IDC_CE_OTHER, LB_ADDSTRING, 0, (LPARAM)text);
    }
    for (i = 0; i < ui.draft.puzzle_count; ++i) {
        const ce_puzzle *z = &ui.draft.puzzles[i];
        wsprintfA(text, "%s: %s", ui.a->puzzles[z->which].name, z->solved ? "solved" : "unsolved");
        SendDlgItemMessageA(window, IDC_CE_OTHER, LB_ADDSTRING, 0, (LPARAM)text);
    }
    if (ui.draft.revive_count > 0) {
        wsprintfA(text, ui.draft.revive_count == 1 ? "1 skeleton comes back to life"
                                                   : "%d skeletons come back to life",
                  ui.draft.revive_count);
        SendDlgItemMessageA(window, IDC_CE_OTHER, LB_ADDSTRING, 0, (LPARAM)text);
    }
}

static void ui_refresh_lists(HWND window) {
    /* ui_describe_change can reach ~270 characters (a 28-character name, a
       31-character title, the longest status and action labels and every
       flag), so this holds twice that. */
    char text[512];
    char years[16];
    int i;
    ui_refresh_other(window);
    SendDlgItemMessageA(window, IDC_CE_SPAWNS, LB_RESETCONTENT, 0, 0);
    for (i = 0; i < ui.draft.spawn_groups; ++i) {
        const ce_spawn *s = &ui.draft.spawns[i];
        wsprintfA(text, "%d x %s, %s years%s%s", s->count,
                  s->sex == STORY_SEX_MALE ? "male" : "female", ui_years(s->age, years),
                  s->name[0] ? ", " : "", s->name);
        SendDlgItemMessageA(window, IDC_CE_SPAWNS, LB_ADDSTRING, 0, (LPARAM)text);
    }
    SendDlgItemMessageA(window, IDC_CE_CHANGES, LB_RESETCONTENT, 0, 0);
    for (i = 0; i < ui.draft.change_count; ++i) {
        ui_describe_change(&ui.draft.changes[i], text);
        SendDlgItemMessageA(window, IDC_CE_CHANGES, LB_ADDSTRING, 0, (LPARAM)text);
    }
}

static void ui_fill_amount(HWND window, int id) {
    ui_combo_add(window, id, "No change", CE_AMOUNT_NONE);
    ui_combo_add(window, id, "Add", CE_AMOUNT_ADD);
    ui_combo_add(window, id, "Subtract", CE_AMOUNT_SUBTRACT);
    ui_combo_add(window, id, "Set to 0", CE_AMOUNT_ZERO);
}

static void ui_select_data(HWND window, int id, int data) {
    int count = (int)SendDlgItemMessageA(window, id, CB_GETCOUNT, 0, 0);
    int i;
    for (i = 0; i < count; ++i) {
        if ((int)SendDlgItemMessageA(window, id, CB_GETITEMDATA, (WPARAM)i, 0) == data) {
            SendDlgItemMessageA(window, id, CB_SETCURSEL, (WPARAM)i, 0);
            return;
        }
    }
}

static int ui_mode(HWND window) {
    return (int)GetWindowLongPtrA(window, DWLP_USER);
}

/* The event itself asks a question: its changes live in the outcomes. */
static int ui_asks(HWND window) {
    return ui_mode(window) == UI_MODE_EVENT && ui.choice.enabled;
}

static int ui_read_main(HWND window) {
    ce_event *e = &ui.draft;
    int i;
    if (ui_mode(window) == UI_MODE_OUTCOME) {
        e->title[0] = '\0';                 /* an outcome has the event's title */
    } else {
        GetDlgItemTextA(window, IDC_CE_TITLE, e->title, sizeof e->title);
    }
    GetDlgItemTextA(window, IDC_CE_TEXT, e->text, sizeof e->text);
    if (ui_asks(window)) {
        /* The village controls are off: every change is an outcome's. */
        e->food_op = e->tech_op = CE_AMOUNT_NONE;
        e->food_amount = e->tech_amount = 0;
        e->refill = 0;
        e->village = 0;
        return 1;
    }
    e->food_op = (ui.a->caps & CAP_FOOD) ? ui_combo_data(window, IDC_CE_FOOD_OP) : CE_AMOUNT_NONE;
    e->tech_op = (ui.a->caps & CAP_TECH) ? ui_combo_data(window, IDC_CE_TECH_OP) : CE_AMOUNT_NONE;
    if (e->food_op < 0) e->food_op = CE_AMOUNT_NONE;
    if (e->tech_op < 0) e->tech_op = CE_AMOUNT_NONE;
    e->food_amount = ui_number(window, IDC_CE_FOOD);
    e->tech_amount = ui_number(window, IDC_CE_TECH);
    if ((e->food_op == CE_AMOUNT_ADD || e->food_op == CE_AMOUNT_SUBTRACT)
        && (e->food_amount == CE_KEEP || e->food_amount < 1 || e->food_amount > CE_MAX_AMOUNT)) {
        ui_message(window, "Type an amount of food from 1 to 1,000,000.");
        return 0;
    }
    if ((e->tech_op == CE_AMOUNT_ADD || e->tech_op == CE_AMOUNT_SUBTRACT)
        && (e->tech_amount == CE_KEEP || e->tech_amount < 1 || e->tech_amount > CE_MAX_AMOUNT)) {
        ui_message(window, "Type an amount of tech points from 1 to 1,000,000.");
        return 0;
    }
    if (e->food_amount < 0) e->food_amount = 0;
    if (e->tech_amount < 0) e->tech_amount = 0;
    e->refill = (ui.a->caps & CAP_REFILL) && IsDlgButtonChecked(window, IDC_CE_REFILL) == BST_CHECKED;
    e->village = 0;
    for (i = 0; i < ui.a->village_count && i < 32; ++i) {
        if (SendDlgItemMessageA(window, IDC_CE_VILLAGE, LB_GETSEL, (WPARAM)i, 0) > 0) {
            e->village |= 1u << i;
        }
    }
    return 1;
}

/* The popup the text box is written for: the plain island event, the
   question of a two-choice event, or an outcome's result. */
static ce_layout ui_layout(HWND window) {
    if (ui_mode(window) == UI_MODE_OUTCOME) {
        return ce_result_layout(ui.a);
    }
    return ui_asks(window) ? ce_question_layout(ui.a) : ce_plain_layout(ui.a);
}

/* The live word / character counter under the title and the text box.
   Lines are counted with that popup's own layout (ce_lines_used_in), so the
   counter agrees with the check made when the event is queued. */
static void ui_update_counts(HWND window) {
    const ce_adapter *a = ui.a;
    ce_layout l = ui_layout(window);
    char title[CE_TITLE_BYTES];
    char body[CE_TEXT_BYTES];
    char out[200];
    int title_chars;
    int lines;
    GetDlgItemTextA(window, IDC_CE_TITLE, title, sizeof title);
    GetDlgItemTextA(window, IDC_CE_TEXT, body, sizeof body);
    title_chars = lstrlenA(title);
    wsprintfA(out, title_chars > a->title_width ? "%d / %d characters - too long" : "%d / %d characters",
              title_chars, a->title_width);
    SetDlgItemTextA(window, IDC_CE_TITLE_COUNT, out);
    lines = ce_lines_used_in(&l, title, body);
    wsprintfA(out, "%d words, %d characters - %d of %d lines used (%d characters a line)%s",
              ce_word_count(body), ce_char_count(body), lines, l.lines, l.width,
              lines > l.lines ? " - too long" : "");
    SetDlgItemTextA(window, IDC_CE_TEXT_NOTE, out);
}

/* Which controls are live: what the game offers, and in a question every
   change is an outcome's (the Remove buttons stay, so changes made before
   the box was ticked can be taken out). */
static void ui_apply_mode(HWND window) {
    const ce_adapter *a = ui.a;
    int outcome = ui_mode(window) == UI_MODE_OUTCOME;
    int own = !ui_asks(window);
    ui_enable(window, IDC_CE_VILLAGE, own && (a->caps & CAP_VILLAGE) != 0);
    ui_enable(window, IDC_CE_FOOD_OP, own && (a->caps & CAP_FOOD) != 0);
    ui_enable(window, IDC_CE_FOOD, own && (a->caps & CAP_FOOD) != 0);
    ui_enable(window, IDC_CE_TECH_OP, own && (a->caps & CAP_TECH) != 0);
    ui_enable(window, IDC_CE_TECH, own && (a->caps & CAP_TECH) != 0);
    ui_enable(window, IDC_CE_REFILL, own && (a->caps & CAP_REFILL) != 0);
    ui_enable(window, IDC_CE_SPAWN_ADD, own && (a->caps & CAP_SPAWN) != 0);
    ui_enable(window, IDC_CE_CHANGE_ADD, own);
    ui_enable(window, IDC_CE_VALUES, own && (a->caps & CAP_VALUES) != 0);
    ui_enable(window, IDC_CE_PUZZLES, own && (a->caps & CAP_PUZZLES) != 0);
    ui_enable(window, IDC_CE_REVIVE, own && (a->caps & CAP_REVIVE) != 0);
    ui_enable(window, IDC_CE_TITLE, !outcome);
    ui_enable(window, IDC_CE_CHOICE, !outcome && ce_choice_available(a));
    ui_enable(window, IDC_CE_CHOICES, !outcome && ui.choice.enabled);
    ShowWindow(GetDlgItem(window, IDC_CE_CHOICE), outcome ? SW_HIDE : SW_SHOW);
    ShowWindow(GetDlgItem(window, IDC_CE_CHOICES), outcome ? SW_HIDE : SW_SHOW);
    SetDlgItemTextA(window, IDC_CE_TEXT_LABEL,
                    outcome ? "Result text:" : ui_asks(window) ? "Question:" : "Description:");
    SetDlgItemTextA(window, IDC_CE_QUEUE_NOTE,
                    outcome ? "The result text and these changes, when this outcome is rolled."
                    : ui_asks(window) ? "It happens shortly. Each button's outcomes are under Choices..."
                                      : "It happens shortly, as a bought Island Event does.");
    ui_update_counts(window);
}

static INT_PTR CALLBACK ui_choices_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam);

static INT_PTR CALLBACK ui_main_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    const ce_adapter *a = ui.a;
    if (message == WM_INITDIALOG) {
        int i;
        SetWindowLongPtrA(window, DWLP_USER, (LONG_PTR)lparam);
        SendDlgItemMessageA(window, IDC_CE_TITLE, EM_LIMITTEXT, CE_TITLE_BYTES - 1, 0);
        SendDlgItemMessageA(window, IDC_CE_TEXT, EM_LIMITTEXT, CE_TEXT_BYTES - 1, 0);
        if (lparam == UI_MODE_OUTCOME) {
            char caption[96];
            wsprintfA(caption, "Outcome %d of the \"%s\" button", ui.outcome_index + 1,
                      ui.choice.labels[ui.outcome_button]);
            SetWindowTextA(window, caption);
            SetDlgItemTextA(window, IDOK, "OK");
            SetDlgItemTextA(window, IDC_CE_TITLE, ui.main_draft.title);
        } else {
            SetDlgItemTextA(window, IDC_CE_TITLE, ui.draft.title);
            CheckDlgButton(window, IDC_CE_CHOICE, ui.choice.enabled ? BST_CHECKED : BST_UNCHECKED);
        }
        SetDlgItemTextA(window, IDC_CE_TEXT, ui.draft.text);
        ui_fill_amount(window, IDC_CE_FOOD_OP);
        ui_fill_amount(window, IDC_CE_TECH_OP);
        ui_select_data(window, IDC_CE_FOOD_OP, ui.draft.food_op);
        ui_select_data(window, IDC_CE_TECH_OP, ui.draft.tech_op);
        if (ui.draft.food_amount > 0) SetDlgItemInt(window, IDC_CE_FOOD, (UINT)ui.draft.food_amount, FALSE);
        if (ui.draft.tech_amount > 0) SetDlgItemInt(window, IDC_CE_TECH, (UINT)ui.draft.tech_amount, FALSE);
        CheckDlgButton(window, IDC_CE_REFILL, ui.draft.refill ? BST_CHECKED : BST_UNCHECKED);
        for (i = 0; i < a->village_count; ++i) {
            SendDlgItemMessageA(window, IDC_CE_VILLAGE, LB_ADDSTRING, 0, (LPARAM)a->villages[i]);
            if (ui.draft.village & (1u << i)) {
                SendDlgItemMessageA(window, IDC_CE_VILLAGE, LB_SETSEL, TRUE, (LPARAM)i);
            }
        }
        if (a->village_count == 0) {
            SendDlgItemMessageA(window, IDC_CE_VILLAGE, LB_ADDSTRING, 0,
                                (LPARAM)"(none are safe in this game)");
        }
        SetDlgItemTextA(window, IDC_CE_NOTE, a->refill_note);
        ui_apply_mode(window);
        ui_refresh_lists(window);
        return TRUE;
    }
    if (message == WM_COMMAND) {
        int id = LOWORD(wparam);
        if ((id == IDC_CE_TITLE || id == IDC_CE_TEXT) && HIWORD(wparam) == EN_CHANGE) {
            ui_update_counts(window);
            return TRUE;
        }
        if (id == IDC_CE_CHOICE) {
            ui.choice.enabled = IsDlgButtonChecked(window, IDC_CE_CHOICE) == BST_CHECKED;
            ui_apply_mode(window);
            return TRUE;
        }
        if (id == IDC_CE_CHOICES) {
            /* The outcomes' result-text check reads the event's title. */
            GetDlgItemTextA(window, IDC_CE_TITLE, ui.draft.title, sizeof ui.draft.title);
            GetDlgItemTextA(window, IDC_CE_TEXT, ui.draft.text, sizeof ui.draft.text);
            DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_CHOICES), window, ui_choices_dialog, 0);
            return TRUE;
        }
        if (id == IDC_CE_OMITTED) {
            MessageBoxA(window, a->omitted, "Not in this game",
                        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
            return TRUE;
        }
        if (id == IDC_CE_SPAWN_ADD) {
            if (ui.draft.spawn_groups >= CE_MAX_SPAWN_GROUPS) {
                ui_message(window, "The event can hold eight kinds of new villagers.");
            } else if (DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_SPAWN), window,
                                       ui_spawn_dialog, 0) == IDOK) {
                ui.draft.spawns[ui.draft.spawn_groups++] = ui.spawn;
                ui_refresh_lists(window);
            }
            return TRUE;
        }
        if (id == IDC_CE_SPAWN_REMOVE) {
            int sel = (int)SendDlgItemMessageA(window, IDC_CE_SPAWNS, LB_GETCURSEL, 0, 0);
            if (sel >= 0 && sel < ui.draft.spawn_groups) {
                memmove(&ui.draft.spawns[sel], &ui.draft.spawns[sel + 1],
                        (size_t)(ui.draft.spawn_groups - sel - 1) * sizeof(ce_spawn));
                --ui.draft.spawn_groups;
                ui_refresh_lists(window);
            }
            return TRUE;
        }
        if (id == IDC_CE_VALUES) {
            if (DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_VALUES), window,
                                ui_values_dialog, 0) == IDOK) {
                ui_refresh_other(window);
            }
            return TRUE;
        }
        if (id == IDC_CE_PUZZLES) {
            if (DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_PUZZLES), window,
                                ui_puzzles_dialog, 0) == IDOK) {
                ui_refresh_other(window);
            }
            return TRUE;
        }
        if (id == IDC_CE_REVIVE) {
            if (DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_REVIVE), window,
                                ui_revive_dialog, 0) == IDOK) {
                ui_refresh_other(window);
            }
            return TRUE;
        }
        if (id == IDC_CE_OTHER_REMOVE) {
            int sel = (int)SendDlgItemMessageA(window, IDC_CE_OTHER, LB_GETCURSEL, 0, 0);
            if (sel >= 0 && sel < ui.draft.value_count) {
                memmove(&ui.draft.values[sel], &ui.draft.values[sel + 1],
                        (size_t)(ui.draft.value_count - sel - 1) * sizeof(ce_value));
                --ui.draft.value_count;
            } else if (sel >= ui.draft.value_count && sel < ui.draft.value_count + ui.draft.puzzle_count) {
                int k = sel - ui.draft.value_count;
                memmove(&ui.draft.puzzles[k], &ui.draft.puzzles[k + 1],
                        (size_t)(ui.draft.puzzle_count - k - 1) * sizeof(ce_puzzle));
                --ui.draft.puzzle_count;
            } else if (sel >= 0 && sel < ui_other_rows()) {
                ui.draft.revive_count = 0;
            }
            ui_refresh_other(window);
            return TRUE;
        }
        if (id == IDC_CE_CHANGE_ADD) {
            if (DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_CHANGES), window,
                                ui_changes_dialog, 0) == IDOK) {
                ui_refresh_lists(window);
            }
            return TRUE;
        }
        if (id == IDC_CE_CHANGE_REMOVE) {
            int sel = (int)SendDlgItemMessageA(window, IDC_CE_CHANGES, LB_GETCURSEL, 0, 0);
            if (sel >= 0 && sel < ui.draft.change_count) {
                memmove(&ui.draft.changes[sel], &ui.draft.changes[sel + 1],
                        (size_t)(ui.draft.change_count - sel - 1) * sizeof(ce_change));
                --ui.draft.change_count;
                ui_refresh_lists(window);
            }
            return TRUE;
        }
        if (id == IDOK) {
            const char *refusal;
            if (!ui_read_main(window)) {
                return TRUE;
            }
            if (ui_mode(window) == UI_MODE_OUTCOME) {
                refusal = ce_result_refusal(ui.a, &ui.draft, ui.main_draft.title);
            } else if (ui.choice.enabled) {
                refusal = ce_choice_refusal(ui.game, &ui.draft, &ui.choice);
            } else {
                refusal = ce_refusal(ui.game, &ui.draft);
            }
            if (refusal != NULL) {
                ui_message(window, refusal);
                return TRUE;
            }
            EndDialog(window, IDOK);
            return TRUE;
        }
        if (id == IDCANCEL) {
            /* The event: keep the words typed for next time; nothing is
               checked.  An outcome: its changes are left as they were. */
            if (ui_mode(window) == UI_MODE_EVENT) {
                GetDlgItemTextA(window, IDC_CE_TITLE, ui.draft.title, sizeof ui.draft.title);
                GetDlgItemTextA(window, IDC_CE_TEXT, ui.draft.text, sizeof ui.draft.text);
            }
            EndDialog(window, IDCANCEL);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, IDCANCEL);
        return TRUE;
    }
    return FALSE;
}

/* ---- The choices dialog ---------------------------------------------------- */

/* Edit outcome `index` of `button` (index == the count: a new one) in the
   main dialog's outcome mode, on the outcome's own changes.  1 when kept. */
static void ui_choice_read_labels(HWND window);

/* The sum of `button`'s chances, leaving out outcome `except` (-1: none). */
static int ui_chance_total(int button, int except) {
    int total = 0;
    int k;
    for (k = 0; k < ui.choice.outcome_count[button]; ++k) {
        if (k != except) {
            total += ui.choice.outcomes[button][k].chance;
        }
    }
    return total;
}

static int ui_edit_outcome(HWND owner, int button, int index) {
    ce_outcome *o = &ui.choice.outcomes[button][index];
    int is_new = index >= ui.choice.outcome_count[button];
    INT_PTR answer;
    /* The outcome dialog's caption names the button by the label typed in
       the Choices dialog (`owner`), which is otherwise read only on OK. */
    ui_choice_read_labels(owner);
    ui.main_draft = ui.draft;
    if (is_new) {
        memset(&ui.draft, 0, sizeof ui.draft);
    } else {
        ui.draft = o->effects;
    }
    ui.outcome_button = button;
    ui.outcome_index = index;
    answer = DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_CUSTOM), owner, ui_main_dialog,
                             UI_MODE_OUTCOME);
    if (answer == IDOK) {
        o->effects = ui.draft;
        o->effects.title[0] = '\0';
        if (is_new) {
            int room = CE_MAX_CHANCE_TOTAL - ui_chance_total(button, -1);
            o->chance = room < 50 ? room : 50;
            ++ui.choice.outcome_count[button];
        }
    }
    ui.draft = ui.main_draft;
    return answer == IDOK;
}

/* A share in whole percent, rounded; an outcome that can come up but rounds
   to 0 says so ("under 1%"). */
static void ui_share(char *out, int chance, int total) {
    int percent = total > 0 ? (int)(((long long)chance * 100 + total / 2) / total) : 0;
    if (percent == 0 && chance > 0) {
        lstrcpyA(out, "under 1%");
    } else {
        wsprintfA(out, "%d%%", percent);
    }
}

/* One button's outcomes list (each row: its share and its result text) and
   the note under it; `select` is the row to select after (-1 none). */
static void ui_choice_fill(HWND window, int button, int select) {
    char row[96];
    char note[200];
    int count = ui.choice.outcome_count[button];
    int total = ui_chance_total(button, -1);
    int k;
    int i;
    SendDlgItemMessageA(window, IDC_CC_LIST_FIRST + button, LB_RESETCONTENT, 0, 0);
    for (k = 0; k < count; ++k) {
        const ce_outcome *o = &ui.choice.outcomes[button][k];
        int n;
        ui_share(row, o->chance, total);
        n = lstrlenA(row);
        row[n++] = ':';
        row[n++] = ' ';
        for (i = 0; o->effects.text[i] != '\0' && n < (int)sizeof row - 4; ++i) {
            char c = o->effects.text[i];
            if (c == '\r') {
                continue;
            }
            row[n++] = c == '\n' ? ' ' : c;
        }
        row[n] = '\0';
        if (o->effects.text[i] != '\0') {
            lstrcpyA(row + n, "...");
        }
        SendDlgItemMessageA(window, IDC_CC_LIST_FIRST + button, LB_ADDSTRING, 0, (LPARAM)row);
    }
    if (count == 0) {
        lstrcpyA(note, "No outcomes yet: add one.");
    } else if (count == 1) {
        lstrcpyA(note, "One outcome: it always happens when this button is clicked.");
    } else {
        wsprintfA(note, "%d outcomes; their chances add up to %d (at most %d). Each row shows its "
                        "share.", count, total, CE_MAX_CHANCE_TOTAL);
    }
    SetDlgItemTextA(window, IDC_CC_NOTE_FIRST + button, note);
    ui.filling = 1;
    if (select >= 0 && select < count) {
        SendDlgItemMessageA(window, IDC_CC_LIST_FIRST + button, LB_SETCURSEL, (WPARAM)select, 0);
        SetDlgItemInt(window, IDC_CC_CHANCE_FIRST + button,
                      (UINT)ui.choice.outcomes[button][select].chance, FALSE);
    } else {
        SetDlgItemTextA(window, IDC_CC_CHANCE_FIRST + button, "");
    }
    ui_enable(window, IDC_CC_CHANCE_FIRST + button, select >= 0 && select < count);
    ui_enable(window, IDC_CC_EDIT_FIRST + button, select >= 0 && select < count);
    ui_enable(window, IDC_CC_REMOVE_FIRST + button, select >= 0 && select < count);
    ui_enable(window, IDC_CC_ADD_FIRST + button, count < CE_MAX_OUTCOMES && total < CE_MAX_CHANCE_TOTAL);
    ui.filling = 0;
}

static int ui_choice_selection(HWND window, int button) {
    int sel = (int)SendDlgItemMessageA(window, IDC_CC_LIST_FIRST + button, LB_GETCURSEL, 0, 0);
    return sel >= 0 && sel < ui.choice.outcome_count[button] ? sel : -1;
}

static void ui_choice_read_labels(HWND window) {
    int b;
    int featured = ui_combo_data(window, IDC_CC_FEATURED);
    for (b = 0; b < 2; ++b) {
        GetDlgItemTextA(window, IDC_CC_LABEL_FIRST + b, ui.choice.labels[b], CE_BUTTON_BYTES);
    }
    /* The villager in the picture: record index + 1, 0 = a random one (its
       identity is taken again when the event is queued). */
    ui.choice.featured_record = featured > 0 ? featured : 0;
    ui.choice.featured_identity = featured > 0 ? ce_identity(ui.a, ui.a->record(featured - 1)) : 0;
}

/* "Villager in the picture": a random living villager, or one of the
   villagers the game may show (New Believers: believers only). */
static void ui_choice_fill_featured(HWND window) {
    char text[128];
    char years[16];
    int i;
    ui_load_roster();
    ui_combo_add(window, IDC_CC_FEATURED, "Random (a living villager)", 0);
    for (i = 0; i < ui.roster_count; ++i) {
        const unsigned char *record = ui.a->record(ui.roster[i].index);
        if (!ce_choice_may_show(ui.a, record)) {
            continue;
        }
        wsprintfA(text, "%s (%s, %s)", ui.names[i], ui.roster[i].sex == STORY_SEX_MALE ? "male" : "female",
                  ui_years(ui.roster[i].age, years));
        ui_combo_add(window, IDC_CC_FEATURED, text, ui.roster[i].index + 1);
    }
    SendDlgItemMessageA(window, IDC_CC_FEATURED, CB_SETCURSEL, 0, 0);
    ui_select_data(window, IDC_CC_FEATURED, ui.choice.featured_record);
    SetDlgItemTextA(window, IDC_CC_FEATURED_NOTE,
                    ui.a->featurable != NULL
                        ? "Shown in the question's picture (believers only); if they are gone, a "
                          "random living believer is."
                        : "Shown in the question's picture; if they are gone, a random living "
                          "villager is.");
}

static INT_PTR CALLBACK ui_choices_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    int b;
    (void)lparam;
    if (message == WM_INITDIALOG) {
        char text[160];
        int width = ce_label_width(ui.a);
        if (width > CE_BUTTON_BYTES - 1) {
            width = CE_BUTTON_BYTES - 1;
        }
        for (b = 0; b < 2; ++b) {
            SendDlgItemMessageA(window, IDC_CC_LABEL_FIRST + b, EM_LIMITTEXT, (WPARAM)width, 0);
            SetDlgItemTextA(window, IDC_CC_LABEL_FIRST + b, ui.choice.labels[b]);
            SendDlgItemMessageA(window, IDC_CC_CHANCE_FIRST + b, EM_LIMITTEXT, 5, 0);
            ui_choice_fill(window, b, ui.choice.outcome_count[b] > 0 ? 0 : -1);
        }
        wsprintfA(text, "A label is up to %d characters in %s. A chance is any number from 1; each "
                        "outcome's share is its chance out of the button's total (at most %d).",
                  width, ui.a->game_name, CE_MAX_CHANCE_TOTAL);
        SetDlgItemTextA(window, IDC_CC_LIMIT, text);
        ui_choice_fill_featured(window);
        return TRUE;
    }
    if (message == WM_COMMAND) {
        int id = LOWORD(wparam);
        int code = HIWORD(wparam);
        for (b = 0; b < 2; ++b) {
            int sel = ui_choice_selection(window, b);
            if (id == IDC_CC_LIST_FIRST + b && code == LBN_SELCHANGE) {
                ui_choice_fill(window, b, sel);
                return TRUE;
            }
            if ((id == IDC_CC_LIST_FIRST + b && code == LBN_DBLCLK) || id == IDC_CC_EDIT_FIRST + b) {
                if (sel >= 0 && ui_edit_outcome(window, b, sel)) {
                    ui_choice_fill(window, b, sel);
                }
                return TRUE;
            }
            if (id == IDC_CC_ADD_FIRST + b) {
                int count = ui.choice.outcome_count[b];
                if (count >= CE_MAX_OUTCOMES) {
                    char text[80];
                    wsprintfA(text, "A button can have %d outcomes at most.", CE_MAX_OUTCOMES);
                    ui_message(window, text);
                } else if (ui_chance_total(b, -1) >= CE_MAX_CHANCE_TOTAL) {
                    char text[120];
                    wsprintfA(text, "This button's chances already add up to %d: lower one first.",
                              CE_MAX_CHANCE_TOTAL);
                    ui_message(window, text);
                } else if (ui_edit_outcome(window, b, count)) {
                    ui_choice_fill(window, b, count);
                }
                return TRUE;
            }
            if (id == IDC_CC_REMOVE_FIRST + b) {
                if (sel >= 0) {
                    memmove(&ui.choice.outcomes[b][sel], &ui.choice.outcomes[b][sel + 1],
                            (size_t)(ui.choice.outcome_count[b] - sel - 1) * sizeof(ce_outcome));
                    --ui.choice.outcome_count[b];
                    ui_choice_fill(window, b, sel < ui.choice.outcome_count[b] ? sel : sel - 1);
                }
                return TRUE;
            }
            if (id == IDC_CC_CHANCE_FIRST + b && code == EN_CHANGE && !ui.filling) {
                int chance = ui_number(window, IDC_CC_CHANCE_FIRST + b);
                int most = sel >= 0 ? CE_MAX_CHANCE_TOTAL - ui_chance_total(b, sel) : 0;
                if (sel >= 0 && chance >= 1 && chance <= most) {
                    ui.choice.outcomes[b][sel].chance = chance;
                    /* The rows and the note, without resetting the box being typed in. */
                    ui.filling = 1;
                    ui_choice_fill(window, b, sel);
                    SendDlgItemMessageA(window, IDC_CC_CHANCE_FIRST + b, EM_SETSEL, 5, 5);
                    ui.filling = 0;
                } else if (sel >= 0) {
                    char text[120];
                    wsprintfA(text, "Type a chance from 1 to %d (what this button's other outcomes "
                                    "leave of %d).", most, CE_MAX_CHANCE_TOTAL);
                    SetDlgItemTextA(window, IDC_CC_NOTE_FIRST + b, text);
                }
                return TRUE;
            }
        }
        if (id == IDOK) {
            const char *refusal;
            ui_choice_read_labels(window);
            refusal = ce_buttons_refusal(ui.a, &ui.choice, ui.draft.title);
            if (refusal != NULL) {
                ui_message(window, refusal);
                return TRUE;
            }
            EndDialog(window, IDOK);
            return TRUE;
        }
        if (id == IDCANCEL) {
            /* As the event's own Cancel: what was typed is kept for next time. */
            ui_choice_read_labels(window);
            EndDialog(window, IDCANCEL);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        ui_choice_read_labels(window);
        EndDialog(window, IDCANCEL);
        return TRUE;
    }
    return FALSE;
}

/* Arm `e` for `game`: make the island event due exactly as the Island Event
   purchase does and remember the event -- with its two choices when `c` is
   an enabled choice (NULL or not enabled: a plain event).  1 on success. */
static int ce_arm_with(int game, const ce_event *e, const ce_choice *c) {
    if (!GAMES[game].arm()) {
        return 0;
    }
    ce_armed_event = *e;
    ce_armed_event.game = game;
    ce_store_choice(game, c);
    ce_armed = 1;
    ce_armed_tick = STORY_TICK();
    ce_armed_village = story_village_now(game);
    ce_last_lapsed = 0;
    return 1;
}

/* The Custom Island Event upgrade, called by the Origins companion when its
   Custom Island Event button is clicked (the companion has already refused
   a click while the Island Event row is locked).  Returns 1 when the event
   is on its way. */
__declspec(dllexport) int __stdcall VvfpStoryCustomIslandEvent(int game, HWND owner) {
    const char *refusal;
    if (!VvfpStoryActive(game) || ce_adapter_for(game) == NULL) {
        return 0;
    }
    drop_lapsed_pick();
    ce_drop_lapsed();
    if (pick_slot >= 0 || ce_armed || GAMES[game].island_pending()) {
        MessageBoxA(owner,
                    game == 5
                        ? "An island event or a barrel of babies is already queued "
                          "and on its way.\n\nIt arrives shortly. Close this screen "
                          "and wait for it to arrive."
                        : "An island event is already queued and on its way.\n\n"
                          "It arrives shortly. Close this screen and wait for it to arrive.",
                    "Not right now", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    if (ce_last_lapsed) {
        ce_last_lapsed = 0;
        ui_message(owner, "The last custom island event you queued did not happen within ten "
                          "minutes, so it was cancelled.");
    }
    ui.game = game;
    ui.a = ce_adapter_for(game);
    refusal = ui.a->arm_refusal();
    if (refusal != NULL) {
        ui_message(owner, refusal);
        return 0;
    }
    if (ui.draft_game != game) {
        memset(&ui.draft, 0, sizeof ui.draft);
        memset(&ui.choice, 0, sizeof ui.choice);
        ui.draft_game = game;
    }
    if (DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_CUSTOM), owner, ui_main_dialog,
                        UI_MODE_EVENT) != IDOK) {
        return 0;
    }
    if (MessageBoxA(owner,
                    "Do you want to buy Custom Island Event for 0 tech points?\r\n"
                    "Press OK to confirm, or Cancel.",
                    "Origins Upgrades",
                    MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND) != IDOK) {
        return 0;
    }
    /* The village may have moved on while the boxes were open. */
    refusal = ce_choice_refusal(game, &ui.draft, &ui.choice);   /* plain: ce_refusal */
    if (refusal == NULL && GAMES[game].island_pending()) {
        refusal = "An island event is already queued and on its way.";
    }
    if (refusal != NULL || !ce_arm_with(game, &ui.draft, &ui.choice)) {
        ui_message(owner, refusal != NULL ? refusal
                                          : "The event can not happen right now. No tech points have been deducted.");
        return 0;
    }
    memset(&ui.draft, 0, sizeof ui.draft);     /* queued: start the next one fresh */
    memset(&ui.choice, 0, sizeof ui.choice);
    ui_message(owner, "Your custom island event is on its way.");
    return 1;
}
