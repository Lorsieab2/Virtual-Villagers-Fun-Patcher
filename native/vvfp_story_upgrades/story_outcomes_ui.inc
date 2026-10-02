/* Pick Island Event: the chooser, with each event's settings.  Included by
   vvfp_story_upgrades.c.

   The owner: each event gets an Outcome setting defaulting to "Random
   (original game)", offering only what was traced for that event in that
   game; a two-choice event's popup still appears and the player still
   clicks, the clicked choice's result being the one set here; settings whose
   condition fails right now say so and can not be bought.

   The dialog (resource 301): the events on the left; on the right the
   event's description, its settings (one row per setting, "label: value"),
   and the editor of the selected row -- a dropdown, a number box for an
   amount with a wide range, and a villager list (Ctrl / Shift extended
   selection) for "Choose who". */

enum {
    IDC_PICK_SETTINGS = 3003,
    IDC_PICK_VALUE = 3004,
    IDC_PICK_AMOUNT = 3005,
    IDC_PICK_RANGE = 3006,
    IDC_PICK_WHO = 3007,
    IDC_PICK_NOTE = 3009,
    IDC_PICK_HEADING = 3010
};

#define OC_AMOUNT_TYPED (-2)        /* "Type a number": the edit box holds it */
#define OC_AMOUNT_INVALID (-3)      /* the typed text is not a valid number */
#define OC_LIST_LIMIT 101           /* amounts with more values are typed */
#define OC_ROSTER_MAX 256

enum { OC_POSSIBLE_NO = 0, OC_POSSIBLE_YES = 1, OC_POSSIBLE_UNLOCK = 2 };

static struct {
    const story_game *game;
    int gid;
    int possible[STORY_MAX_EVENTS];
    int chosen;
    int current;                        /* the event shown, or -1 */
    int row;                            /* the settings row being edited, or -1 */
    int filling;                        /* the editor is being filled (ignore its notifications) */
    int gong;                           /* the dialog picks the Gong of Wonder's outcome */
    oc_settings settings[STORY_MAX_EVENTS];
    story_member roster[OC_ROSTER_MAX];
    char names[OC_ROSTER_MAX][CE_NAME_BYTES];
    int roster_count;
} chooser;

static void label_of(const story_event *e, char *out, size_t size);

/* Whether `e`, whose own condition does not hold, can be picked anyway: it
   is unlockable (a timing or story condition, or a developer-dead event,
   proven safe to pass), and what it still needs is there -- A New Home / The
   Lost Children: what every island event needs (an adult; the first event
   is an encounter / a two-choice event); the other games: the villager its
   own condition picked, read from the event object after asking it. */
static int oc_unlock_possible(int game, const story_event *e) {
    unsigned int table;
    getter_fn getter;
    void *object;
    if (!oc_event_unlockable(game, e->slot)) {
        return 0;
    }
    switch (game) {
    case 1: return vv1_base_possible(e);
    case 2: return vv2_base_possible(e);
    case 3: table = VV3_EVENT_TABLE; getter = (getter_fn)(uintptr_t)VV3_EVENT_GETTER; break;
    case 4: table = VV4_EVENT_TABLE; getter = (getter_fn)(uintptr_t)VV4_EVENT_GETTER; break;
    case 5: table = VV5_EVENT_TABLE; getter = (getter_fn)(uintptr_t)VV5_EVENT_GETTER; break;
    default: return 0;
    }
    object = *(void **)(uintptr_t)(table + 4u * (unsigned int)e->slot);
    if (object == NULL) {
        getter();
        object = *(void **)(uintptr_t)(table + 4u * (unsigned int)e->slot);
    }
    if (object == NULL) {
        return 0;
    }
    can_fire_with_retries(object);       /* its own condition picks the villager */
    return oc_unlock_ready(game, e->slot, object);
}

static const oc_event *chooser_oc(int index) {
    if (index < 0 || index >= chooser.game->event_count) {
        return NULL;
    }
    return oc_find_event(chooser.gid, chooser.game->events[index].slot);
}

static const oc_control *chooser_control(const oc_event *e, int i) {
    return &OC_GAMES[chooser.gid].controls[e->control_first + i];
}

/* Rows: the controls, then the strength (A New Home / The Lost Children). */
static int chooser_rows(const oc_event *e) {
    if (e == NULL) {
        return 0;
    }
    return e->control_count + (e->strength ? 1 : 0);
}

static int chooser_is_strength_row(const oc_event *e, int row) {
    return e != NULL && e->strength && row == e->control_count;
}

/* Whether a condition an option needs holds now. */
static int oc_condition_holds(int game, int cond) {
    const ce_adapter *a = ce_adapter_for(game);
    switch (cond) {
    case 0:
        return 1;
    case 1:
        return a != NULL && a->room();
    case 2:   /* The Lost Children: the Gong's tiers A and B (village byte +0x2E910) */
    case 3: { /* The Lost Children: breeding mastered (village +0x2EA8C == 3) */
        unsigned char *world = game == 2 ? *(unsigned char **)(uintptr_t)VV2_WORLD_GLOBAL : NULL;
        if (world == NULL) {
            return 0;
        }
        return cond == 2 ? world[0x2E910] != 0 : *(int *)(world + 0x2EA8C) == 3;
    }
    default:
        return 0;
    }
}

static const char *oc_name_of(int index) {
    int i;
    for (i = 0; i < chooser.roster_count; ++i) {
        if (chooser.roster[i].index == index) {
            return chooser.names[i];
        }
    }
    return "(gone)";
}

static int oc_who_count(const unsigned char *who) {
    int i;
    int n = 0;
    for (i = 0; i < chooser.roster_count; ++i) {
        if (oc_who_has(who, chooser.roster[i].index)) {
            ++n;
        }
    }
    return n;
}

static void oc_strength_text(const oc_event *e, int value, char *out) {
    if (value == 0) {
        lstrcpyA(out, "Normal (from the population)");
    } else if (e->strength == 2) {
        wsprintfA(out, "%s", value >= 8 ? "8-10 (three babies)" : value >= 5 ? "5-7 (two babies)"
                                                                         : "1-4 (one baby)");
    } else {
        wsprintfA(out, "%d", value);
    }
}

/* The text of control `c` with setting `choice`. */
static void oc_value_text(const oc_control *c, int ci, const oc_settings *s, char *out, int size) {
    int choice = s->choice[ci];
    const oc_game *g = &OC_GAMES[chooser.gid];
    if (choice == OC_RANDOM) {
        lstrcpynA(out, "Random (original game)", size);
        return;
    }
    switch (c->kind) {
    case OC_ENUM:
        lstrcpynA(out, g->options[c->option_first + choice].label, size);
        return;
    case OC_AMOUNT:
        if (choice < 0) {
            lstrcpynA(out, "(type a number)", size);
        } else {
            wsprintfA(out, "%d %s", c->base + c->step * choice, c->text != NULL ? c->text : "");
        }
        return;
    case OC_LOOP:
        if (choice == OC_LOOP_NOBODY) {
            lstrcpynA(out, "Nobody", size);
        } else if (choice == OC_LOOP_EVERYONE) {
            lstrcpynA(out, "Everyone", size);
        } else {
            wsprintfA(out, "The chosen villagers (%d)", oc_who_count(s->who[ci]));
        }
        return;
    case OC_VICTIM:
        lstrcpynA(out, oc_name_of(choice), size);
        return;
    default:
        lstrcpynA(out, "", size);
    }
}

static void chooser_row_text(const oc_event *e, int row, char *out) {
    char value[160];
    const oc_settings *s = &chooser.settings[chooser.current];
    if (chooser_is_strength_row(e, row)) {
        oc_strength_text(e, s->strength, value);
        wsprintfA(out, "Strength: %s", value);
        return;
    }
    oc_value_text(chooser_control(e, row), row, s, value, sizeof value);
    wsprintfA(out, "%s: %s", chooser_control(e, row)->label, value);
}

static void chooser_combo_add(HWND window, const char *text, int data) {
    int at = (int)SendDlgItemMessageA(window, IDC_PICK_VALUE, CB_ADDSTRING, 0, (LPARAM)text);
    SendDlgItemMessageA(window, IDC_PICK_VALUE, CB_SETITEMDATA, (WPARAM)at, (LPARAM)data);
}

static void chooser_select_data(HWND window, int data) {
    int n = (int)SendDlgItemMessageA(window, IDC_PICK_VALUE, CB_GETCOUNT, 0, 0);
    int i;
    for (i = 0; i < n; ++i) {
        if ((int)SendDlgItemMessageA(window, IDC_PICK_VALUE, CB_GETITEMDATA, (WPARAM)i, 0) == data) {
            SendDlgItemMessageA(window, IDC_PICK_VALUE, CB_SETCURSEL, (WPARAM)i, 0);
            return;
        }
    }
    SendDlgItemMessageA(window, IDC_PICK_VALUE, CB_SETCURSEL, 0, 0);
}

static void chooser_show_editor(HWND window, int value, int amount, int who) {
    ShowWindow(GetDlgItem(window, IDC_PICK_VALUE), value ? SW_SHOW : SW_HIDE);
    ShowWindow(GetDlgItem(window, IDC_PICK_AMOUNT), amount ? SW_SHOW : SW_HIDE);
    ShowWindow(GetDlgItem(window, IDC_PICK_RANGE), amount ? SW_SHOW : SW_HIDE);
    ShowWindow(GetDlgItem(window, IDC_PICK_WHO), who ? SW_SHOW : SW_HIDE);
}

/* Fills the villager list for loop row `row` and selects its villagers. */
static void chooser_fill_who(HWND window, int row) {
    const unsigned char *who = chooser.settings[chooser.current].who[row];
    int i;
    SendDlgItemMessageA(window, IDC_PICK_WHO, LB_RESETCONTENT, 0, 0);
    for (i = 0; i < chooser.roster_count; ++i) {
        char text[64];
        int at;
        wsprintfA(text, "%s (%s, %d)", chooser.names[i],
                  chooser.roster[i].sex == STORY_SEX_FEMALE ? "female" : "male",
                  chooser.roster[i].age / 20);
        at = (int)SendDlgItemMessageA(window, IDC_PICK_WHO, LB_ADDSTRING, 0, (LPARAM)text);
        SendDlgItemMessageA(window, IDC_PICK_WHO, LB_SETITEMDATA, (WPARAM)at, (LPARAM)chooser.roster[i].index);
        if (oc_who_has(who, chooser.roster[i].index)) {
            SendDlgItemMessageA(window, IDC_PICK_WHO, LB_SETSEL, TRUE, at);
        }
    }
}

/* The editor of the selected row. */
static void chooser_fill_editor(HWND window) {
    const oc_event *e = chooser_oc(chooser.current);
    const oc_settings *s;
    char text[256];
    int row = chooser.row;
    chooser.filling = 1;
    SendDlgItemMessageA(window, IDC_PICK_VALUE, CB_RESETCONTENT, 0, 0);
    SetDlgItemTextA(window, IDC_PICK_NOTE, "");
    if (e == NULL || row < 0 || row >= chooser_rows(e)) {
        chooser_show_editor(window, 0, 0, 0);
        chooser.filling = 0;
        return;
    }
    s = &chooser.settings[chooser.current];
    if (chooser_is_strength_row(e, row)) {
        chooser_combo_add(window, "Normal (from the population)", 0);
        if (e->strength == 2) {
            chooser_combo_add(window, "1-4 (one baby)", 1);
            chooser_combo_add(window, "5-7 (two babies)", 5);
            chooser_combo_add(window, "8-10 (three babies)", 8);
        } else {
            int v;
            for (v = 1; v <= 10; ++v) {
                wsprintfA(text, "%d", v);
                chooser_combo_add(window, text, v);
            }
        }
        SetDlgItemTextA(window, IDC_PICK_NOTE,
                        "The strength the game normally takes from the population (a third of it, 1 to 10).");
        chooser_select_data(window, s->strength);
        chooser_show_editor(window, 1, 0, 0);
    } else {
        const oc_control *c = chooser_control(e, row);
        const oc_game *g = &OC_GAMES[chooser.gid];
        int i;
        int choice = s->choice[row];
        int typed = 0;
        int who = 0;
        chooser_combo_add(window, "Random (original game)", OC_RANDOM);
        switch (c->kind) {
        case OC_ENUM:
            for (i = 0; i < c->option_count; ++i) {
                const oc_option *o = &g->options[c->option_first + i];
                if (o->cond && !oc_condition_holds(chooser.gid, o->cond)) {
                    wsprintfA(text, "%s - not possible right now (%s)", o->label,
                              o->condition != NULL ? o->condition : "its condition");
                } else {
                    lstrcpynA(text, o->label, sizeof text);
                }
                chooser_combo_add(window, text, i);
            }
            break;
        case OC_AMOUNT:
            if (c->bound <= OC_LIST_LIMIT) {
                for (i = 0; i < c->bound; ++i) {
                    wsprintfA(text, "%d %s", c->base + c->step * i, c->text != NULL ? c->text : "");
                    chooser_combo_add(window, text, i);
                }
            } else {
                int lo = c->base;
                int hi = c->base + c->step * (c->bound - 1);
                chooser_combo_add(window, "Type a number", OC_AMOUNT_TYPED);
                typed = choice != OC_RANDOM;
                wsprintfA(text, "%d to %d %s", lo < hi ? lo : hi, lo < hi ? hi : lo,
                          c->text != NULL ? c->text : "");
                SetDlgItemTextA(window, IDC_PICK_RANGE, text);
                if (choice >= 0) {
                    wsprintfA(text, "%d", c->base + c->step * choice);
                    SetDlgItemTextA(window, IDC_PICK_AMOUNT, text);
                } else if (choice == OC_RANDOM) {
                    SetDlgItemTextA(window, IDC_PICK_AMOUNT, "");
                }
            }
            break;
        case OC_LOOP:
            if (c->nobody >= 0) {
                chooser_combo_add(window, "Nobody", OC_LOOP_NOBODY);
            }
            if (c->everyone >= 0) {
                chooser_combo_add(window, c->warn != NULL ? "Everyone (see the warning)" : "Everyone",
                                  OC_LOOP_EVERYONE);
            }
            if (c->reg >= 0 && c->nobody >= 0 && c->everyone >= 0) {
                chooser_combo_add(window, "Choose who", OC_LOOP_CHOOSE);
                who = choice == OC_LOOP_CHOOSE;
            }
            if (c->text != NULL) {
                wsprintfA(text, "Each villager the game checks: %s.", c->text);
                SetDlgItemTextA(window, IDC_PICK_NOTE, text);
            }
            break;
        case OC_VICTIM:
            for (i = 0; i < chooser.roster_count; ++i) {
                chooser_combo_add(window, chooser.names[i], chooser.roster[i].index);
            }
            if (c->text != NULL) {
                wsprintfA(text, "The game picks among: %s. A villager it would not pick leaves the "
                                "choice to the game.", c->text);
                SetDlgItemTextA(window, IDC_PICK_NOTE, text);
            }
            break;
        default:
            break;
        }
        if (c->note != NULL && (c->kind == OC_ENUM || c->kind == OC_AMOUNT)) {
            lstrcpynA(text, c->note, sizeof text);
            SetDlgItemTextA(window, IDC_PICK_NOTE, text);
        }
        if (c->kind == OC_AMOUNT && c->bound > OC_LIST_LIMIT) {
            chooser_select_data(window, typed ? OC_AMOUNT_TYPED : OC_RANDOM);
        } else {
            chooser_select_data(window, choice);
        }
        if (who) {
            chooser_fill_who(window, row);
        }
        chooser_show_editor(window, 1, c->kind == OC_AMOUNT && typed, who);
    }
    chooser.filling = 0;
}

static void chooser_fill_rows(HWND window) {
    const oc_event *e = chooser_oc(chooser.current);
    int i;
    char text[320];
    SendDlgItemMessageA(window, IDC_PICK_SETTINGS, LB_RESETCONTENT, 0, 0);
    for (i = 0; i < chooser_rows(e); ++i) {
        chooser_row_text(e, i, text);
        SendDlgItemMessageA(window, IDC_PICK_SETTINGS, LB_ADDSTRING, 0, (LPARAM)text);
    }
    if (chooser_rows(e) == 0) {
        SendDlgItemMessageA(window, IDC_PICK_SETTINGS, LB_ADDSTRING, 0,
                            (LPARAM)"(nothing to set: the game decides this event the same way every time)");
        chooser.row = -1;
    } else {
        if (chooser.row < 0 || chooser.row >= chooser_rows(e)) {
            chooser.row = 0;
        }
        SendDlgItemMessageA(window, IDC_PICK_SETTINGS, LB_SETCURSEL, (WPARAM)chooser.row, 0);
    }
    chooser_fill_editor(window);
}

static void chooser_refresh_row(HWND window) {
    const oc_event *e = chooser_oc(chooser.current);
    char text[320];
    if (e == NULL || chooser.row < 0) {
        return;
    }
    chooser_row_text(e, chooser.row, text);
    SendDlgItemMessageA(window, IDC_PICK_SETTINGS, LB_DELETESTRING, (WPARAM)chooser.row, 0);
    SendDlgItemMessageA(window, IDC_PICK_SETTINGS, LB_INSERTSTRING, (WPARAM)chooser.row, (LPARAM)text);
    SendDlgItemMessageA(window, IDC_PICK_SETTINGS, LB_SETCURSEL, (WPARAM)chooser.row, 0);
}

/* The typed amount of the current row: its roll value, or OC_AMOUNT_INVALID. */
static int chooser_typed_value(HWND window, const oc_control *c) {
    char text[32];
    int i = 0;
    int sign = 1;
    int shown = 0;
    int digits = 0;
    int v;
    GetDlgItemTextA(window, IDC_PICK_AMOUNT, text, sizeof text);
    while (text[i] == ' ') {
        ++i;
    }
    if (text[i] == '-') {
        sign = -1;
        ++i;
    }
    for (; text[i] >= '0' && text[i] <= '9'; ++i) {
        if (shown > 100000000) {
            return OC_AMOUNT_INVALID;
        }
        shown = shown * 10 + (text[i] - '0');
        ++digits;
    }
    while (text[i] == ' ') {
        ++i;
    }
    if (digits == 0 || text[i] != '\0' || c->step == 0) {
        return OC_AMOUNT_INVALID;
    }
    shown *= sign;
    if ((shown - c->base) % c->step != 0) {
        return OC_AMOUNT_INVALID;
    }
    v = (shown - c->base) / c->step;
    return v >= 0 && v < c->bound ? v : OC_AMOUNT_INVALID;
}

static void chooser_value_changed(HWND window) {
    const oc_event *e = chooser_oc(chooser.current);
    oc_settings *s;
    int sel = (int)SendDlgItemMessageA(window, IDC_PICK_VALUE, CB_GETCURSEL, 0, 0);
    int data;
    if (e == NULL || chooser.row < 0 || sel < 0) {
        return;
    }
    s = &chooser.settings[chooser.current];
    data = (int)SendDlgItemMessageA(window, IDC_PICK_VALUE, CB_GETITEMDATA, (WPARAM)sel, 0);
    if (chooser_is_strength_row(e, chooser.row)) {
        s->strength = data;
    } else {
        const oc_control *c = chooser_control(e, chooser.row);
        if (c->kind == OC_AMOUNT && data == OC_AMOUNT_TYPED) {
            s->choice[chooser.row] = chooser_typed_value(window, c);
            chooser_show_editor(window, 1, 1, 0);
        } else {
            s->choice[chooser.row] = data;
            chooser_show_editor(window, 1, 0, c->kind == OC_LOOP && data == OC_LOOP_CHOOSE);
            if (c->kind == OC_LOOP && data == OC_LOOP_CHOOSE) {
                chooser_fill_who(window, chooser.row);
            }
        }
    }
    chooser_refresh_row(window);
}

static void chooser_who_changed(HWND window) {
    unsigned char *who;
    int n = (int)SendDlgItemMessageA(window, IDC_PICK_WHO, LB_GETCOUNT, 0, 0);
    int i;
    if (chooser.current < 0 || chooser.row < 0 || chooser.row >= OC_MAX_CONTROLS) {
        return;
    }
    who = chooser.settings[chooser.current].who[chooser.row];
    memset(who, 0, OC_WHO_BYTES);
    for (i = 0; i < n; ++i) {
        if (SendDlgItemMessageA(window, IDC_PICK_WHO, LB_GETSEL, (WPARAM)i, 0) > 0) {
            int index = (int)SendDlgItemMessageA(window, IDC_PICK_WHO, LB_GETITEMDATA, (WPARAM)i, 0);
            if (index >= 0 && index < OC_WHO_BYTES * 8) {
                who[index >> 3] |= (unsigned char)(1u << (index & 7));
            }
        }
    }
    chooser_refresh_row(window);
}

static void chooser_show(HWND window) {
    int sel = (int)SendDlgItemMessageA(window, IDC_PICK_LIST, LB_GETCURSEL, 0, 0);
    int index;
    char text[640];
    if (sel < 0) {
        SetDlgItemTextA(window, IDC_PICK_DESC, "");
        EnableWindow(GetDlgItem(window, IDOK), FALSE);
        chooser.current = -1;
        chooser_fill_rows(window);
        return;
    }
    index = (int)SendDlgItemMessageA(window, IDC_PICK_LIST, LB_GETITEMDATA, (WPARAM)sel, 0);
    if (index != chooser.current) {
        chooser.current = index;
        chooser.row = 0;
    }
    if (chooser.possible[index] == OC_POSSIBLE_YES) {
        lstrcpynA(text, chooser.game->events[index].description, sizeof text);
    } else if (chooser.possible[index] == OC_POSSIBLE_UNLOCK) {
        const oc_event *e = chooser_oc(index);
        wsprintfA(text, "%s\r\n\r\n%s", chooser.game->events[index].description,
                  e != NULL && e->dead_note != NULL
                      ? e->dead_note
                      : "Normally not possible right now; picking it makes it happen anyway.");
    } else {
        wsprintfA(text, "%s\r\n\r\nNot possible right now: %s",
                  chooser.game->events[index].description,
                  chooser.game->events[index].requires);
    }
    SetDlgItemTextA(window, IDC_PICK_DESC, text);
    EnableWindow(GetDlgItem(window, IDOK), chooser.possible[index] != OC_POSSIBLE_NO);
    chooser_fill_rows(window);
}

/* Why the settings of event `index` can not be bought now, or NULL. */
static const char *chooser_refusal(int index, char *buffer) {
    const oc_event *e = chooser_oc(index);
    const oc_settings *s = &chooser.settings[index];
    const oc_game *g = &OC_GAMES[chooser.gid];
    int i;
    if (e == NULL) {
        return NULL;
    }
    for (i = 0; i < e->control_count; ++i) {
        const oc_control *c = chooser_control(e, i);
        int choice = s->choice[i];
        if (choice == OC_RANDOM) {
            continue;
        }
        if (c->kind == OC_AMOUNT && choice < 0) {
            wsprintfA(buffer, "\"%s\": type a whole number from %d to %d, or choose Random.", c->label,
                      c->step >= 0 ? c->base : c->base + c->step * (c->bound - 1),
                      c->step >= 0 ? c->base + c->step * (c->bound - 1) : c->base);
            return buffer;
        }
        if (c->kind == OC_ENUM) {
            const oc_option *o = &g->options[c->option_first + choice];
            if (o->cond && !oc_condition_holds(chooser.gid, o->cond)) {
                wsprintfA(buffer, "\"%s: %s\" is not possible right now (%s).", c->label, o->label,
                          o->condition != NULL ? o->condition : "its condition does not hold");
                return buffer;
            }
        }
        if (c->kind == OC_LOOP && choice == OC_LOOP_CHOOSE && oc_who_count(s->who[i]) == 0) {
            wsprintfA(buffer, "\"%s\": choose at least one villager, or choose Nobody.", c->label);
            return buffer;
        }
    }
    return NULL;
}

/* The warning of a setting that ends the tribe, or NULL. */
static const char *chooser_warning(int index) {
    const oc_event *e = chooser_oc(index);
    const oc_settings *s = &chooser.settings[index];
    int i;
    if (e == NULL) {
        return NULL;
    }
    for (i = 0; i < e->control_count; ++i) {
        const oc_control *c = chooser_control(e, i);
        if (c->kind != OC_LOOP || c->warn == NULL) {
            continue;
        }
        if (s->choice[i] == OC_LOOP_EVERYONE
            || (s->choice[i] == OC_LOOP_CHOOSE && oc_who_count(s->who[i]) >= chooser.roster_count)) {
            return c->warn;
        }
    }
    return NULL;
}

/* "label: value" lines of every setting that is not Random. */
static void chooser_summary(int index, char *out, int size) {
    const oc_event *e = chooser_oc(index);
    int saved = chooser.current;
    int i;
    out[0] = '\0';
    if (e == NULL) {
        return;
    }
    chooser.current = index;
    for (i = 0; i < chooser_rows(e); ++i) {
        char line[320];
        if (chooser_is_strength_row(e, i) ? chooser.settings[index].strength == 0
                                          : chooser.settings[index].choice[i] == OC_RANDOM) {
            continue;
        }
        chooser_row_text(e, i, line);
        if (lstrlenA(out) + lstrlenA(line) + 4 < size) {
            lstrcatA(out, "\r\n");
            lstrcatA(out, line);
        }
    }
    chooser.current = saved;
}

static INT_PTR CALLBACK chooser_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    (void)lparam;
    if (message == WM_INITDIALOG) {
        int i;
        char label[200];
        for (i = 0; i < chooser.game->event_count; ++i) {
            int row;
            const oc_event *e = chooser_oc(i);
            label_of(&chooser.game->events[i], label, sizeof label);
            if (chooser.possible[i] == OC_POSSIBLE_UNLOCK) {
                lstrcatA(label, e != NULL && e->dead_note != NULL ? " (never happens in the original game)"
                                                                   : " (normally not possible right now)");
            } else if (!chooser.possible[i]) {
                lstrcatA(label, " - not possible right now");
            }
            row = (int)SendDlgItemMessageA(window, IDC_PICK_LIST, LB_ADDSTRING, 0, (LPARAM)label);
            SendDlgItemMessageA(window, IDC_PICK_LIST, LB_SETITEMDATA, (WPARAM)row, (LPARAM)i);
        }
        SendDlgItemMessageA(window, IDC_PICK_AMOUNT, EM_LIMITTEXT, 12, 0);
        if (chooser.gong) {
            SetWindowTextA(window, "Pick Gong of Wonder Outcome");
            SetDlgItemTextA(window, IDC_PICK_HEADING, "What the Gong of Wonder does the next time it is rung:");
            SendDlgItemMessageA(window, IDC_PICK_LIST, LB_SETCURSEL, 0, 0);
        }
        chooser.current = -1;
        chooser.row = -1;
        chooser_show(window);
        return TRUE;
    }
    if (message == WM_COMMAND) {
        int id = LOWORD(wparam);
        int code = HIWORD(wparam);
        if (id == IDC_PICK_LIST && code == LBN_SELCHANGE) {
            chooser_show(window);
            return TRUE;
        }
        if (id == IDC_PICK_LIST && code == LBN_DBLCLK) {
            if (IsWindowEnabled(GetDlgItem(window, IDOK))) {
                PostMessageA(window, WM_COMMAND, IDOK, 0);
            }
            return TRUE;
        }
        if (id == IDC_PICK_SETTINGS && code == LBN_SELCHANGE) {
            const oc_event *e = chooser_oc(chooser.current);
            int sel = (int)SendDlgItemMessageA(window, IDC_PICK_SETTINGS, LB_GETCURSEL, 0, 0);
            chooser.row = (e != NULL && sel >= 0 && sel < chooser_rows(e)) ? sel : -1;
            chooser_fill_editor(window);
            return TRUE;
        }
        if (id == IDC_PICK_VALUE && code == CBN_SELCHANGE && !chooser.filling) {
            chooser_value_changed(window);
            return TRUE;
        }
        if (id == IDC_PICK_AMOUNT && code == EN_CHANGE && !chooser.filling) {
            const oc_event *e = chooser_oc(chooser.current);
            if (e != NULL && chooser.row >= 0 && !chooser_is_strength_row(e, chooser.row)) {
                const oc_control *c = chooser_control(e, chooser.row);
                if (c->kind == OC_AMOUNT && chooser.settings[chooser.current].choice[chooser.row] != OC_RANDOM) {
                    chooser.settings[chooser.current].choice[chooser.row] = chooser_typed_value(window, c);
                    chooser_refresh_row(window);
                }
            }
            return TRUE;
        }
        if (id == IDC_PICK_WHO && code == LBN_SELCHANGE && !chooser.filling) {
            chooser_who_changed(window);
            return TRUE;
        }
        if (id == IDOK) {
            int sel = (int)SendDlgItemMessageA(window, IDC_PICK_LIST, LB_GETCURSEL, 0, 0);
            int index;
            char why[400];
            const char *refusal;
            if (sel < 0) {
                return TRUE;
            }
            index = (int)SendDlgItemMessageA(window, IDC_PICK_LIST, LB_GETITEMDATA, (WPARAM)sel, 0);
            if (chooser.possible[index] == OC_POSSIBLE_NO) {
                return TRUE;
            }
            refusal = chooser_refusal(index, why);
            if (refusal != NULL) {
                MessageBoxA(window, refusal, "Pick Island Event", MB_OK | MB_ICONINFORMATION);
                return TRUE;
            }
            chooser.chosen = index;
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

/* Opens the chooser for `game`: fills the possibilities and the roster.
   Returns the chosen event index, or -1. */
static int chooser_run(int game, const story_game *g, HWND owner) {
    const ce_adapter *a = ce_adapter_for(game);
    int i;
    int k;
    chooser.game = g;
    chooser.gid = game;
    chooser.chosen = -1;
    chooser.roster_count = a != NULL ? ce_roster(a, chooser.roster, OC_ROSTER_MAX) : 0;
    for (i = 0; i < chooser.roster_count; ++i) {
        const unsigned char *record = a->record(chooser.roster[i].index);
        ce_copy_name(chooser.names[i], CE_NAME_BYTES, record + a->off_name, a->name_bytes);
    }
    for (i = 0; i < g->event_count && i < STORY_MAX_EVENTS; ++i) {
        const oc_event *e = oc_find_event(game, g->events[i].slot);
        int possible = g->possible(&g->events[i]);
        chooser.possible[i] = possible ? OC_POSSIBLE_YES
                              : (e != NULL && e->unlock
                                 && oc_unlock_possible(game, &g->events[i]))
                                    ? OC_POSSIBLE_UNLOCK : OC_POSSIBLE_NO;
        memset(&chooser.settings[i], 0, sizeof chooser.settings[i]);
        for (k = 0; k < OC_MAX_CONTROLS; ++k) {
            chooser.settings[i].choice[k] = OC_RANDOM;
        }
        chooser.settings[i].unlocked = chooser.possible[i] == OC_POSSIBLE_UNLOCK;
    }
    if (DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_PICK), owner, chooser_dialog, 0) != IDOK) {
        return -1;
    }
    return chooser.chosen;
}

/* ---- The Lost Children: Pick Gong of Wonder Outcome --------------------------

   The owner: a separate upgrade, cost 0, that lets the player pick which
   outcome the NEXT use of the Gong of Wonder produces, defaulting to
   "Random (original game)", every possible outcome offered.  The settings
   are the Gong's own rolls (scripts/story_outcomes_gong.py), answered only
   inside the gong's own use (the call at 0x461B8E that runs its outcome
   routine 0x44E8A0) and ended when that use returns -- one use.  An armed
   choice also ends after ten minutes without a ring and when the village's
   save slot changes; the next opening says so. */

static const story_event OC_GONG_EVENTS[1] = {
    { OC_GONG_SLOT, "The Gong of Wonder", "",
      "The next time a villager rings the Gong of Wonder, it does what you set here; "
      "anything left Random is the game's own choice. The Gong rests about a day after each "
      "ring; your choice waits for the next ring for ten minutes, in this save slot.", "" },
};

static int oc_gong_possible(const story_event *event) {
    (void)event;
    return 1;
}

static const story_game OC_GONG_GAME = {
    NULL, 0, NULL, 0, NULL, 0, OC_GONG_EVENTS, 1, oc_gong_possible, NULL, NULL
};

static int oc_gong_lapsed_note;     /* 1 = lapsed (ten minutes), 2 = the save slot changed */

/* Ends an armed gong choice that is too old or belongs to another slot. */
static void oc_gong_check(void) {
    if (oc_gong.state != OC_ARMED) {
        return;
    }
    if (STORY_TICK() - oc_gong.tick > PICK_TIMEOUT_MS) {
        oc_arm_clear(&oc_gong);
        oc_gong_lapsed_note = 1;
    } else if (story_current_slot(2) != oc_gong.save_slot) {
        oc_arm_clear(&oc_gong);
        oc_gong_lapsed_note = 2;
    }
}

/* Whether the Gong of Wonder is resting now (village +0x2EAC8 is the time
   it can next be rung, on the game's clock 0x403200). */
static int oc_gong_resting(void) {
    unsigned char *world = *(unsigned char **)(uintptr_t)VV2_WORLD_GLOBAL;
    if (world == NULL) {
        return 0;
    }
    return *(unsigned int *)(world + 0x2EAC8)
           >= (unsigned int)((clock_fn)(uintptr_t)VV2_CLOCK)(world, NULL);
}

__declspec(dllexport) int __stdcall VvfpStoryPickGongOutcome(int game, HWND owner) {
    const oc_settings *settings;
    char summary[1200];
    char message[1600];
    if (game != 2 || !VvfpStoryActive(2)) {
        return 0;
    }
    oc_gong_check();
    if (oc_gong_lapsed_note) {
        MessageBoxA(owner,
                    oc_gong_lapsed_note == 1
                        ? "The Gong of Wonder outcome you picked last was not used within ten "
                          "minutes, so it was cancelled."
                        : "The Gong of Wonder outcome you picked last was for another village, so "
                          "it was cancelled.",
                    "Pick Gong of Wonder Outcome",
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        oc_gong_lapsed_note = 0;
    }
    if (oc_gong.state != OC_IDLE
        && MessageBoxA(owner,
                       "A Gong of Wonder outcome is already picked for the next ring.\r\n\r\n"
                       "Press OK to pick a new one instead, or Cancel to keep it.",
                       "Pick Gong of Wonder Outcome",
                       MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND) != IDOK) {
        return 0;
    }
    chooser.gong = 1;
    if (chooser_run(2, &OC_GONG_GAME, owner) != 0) {
        chooser.gong = 0;
        return 0;
    }
    chooser.gong = 0;
    settings = &chooser.settings[0];
    if (!oc_settings_any(oc_find_event(2, OC_GONG_SLOT), settings)) {
        MessageBoxA(owner, "Every setting is Random (original game): nothing to pick.",
                    "Pick Gong of Wonder Outcome",
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    chooser_summary(0, summary, sizeof summary);
    wsprintfA(message,
              "Do you want to buy Pick Gong of Wonder Outcome for 0 tech points?\r\n%s\r\n\r\n"
              "Press OK to confirm, or Cancel.", summary);
    if (MessageBoxA(owner, message, "Origins Upgrades",
                    MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND) != IDOK) {
        return 0;
    }
    oc_arm_set(&oc_gong, 2, OC_GONG_SLOT, settings);
    oc_gong.save_slot = story_current_slot(2);
    MessageBoxA(owner,
                oc_gong_resting()
                    ? "Picked. The Gong of Wonder is resting now; the next time a villager rings "
                      "it after it is ready (within ten minutes), it does what you picked."
                    : "Picked. The next time a villager rings the Gong of Wonder (within ten "
                      "minutes), it does what you picked.",
                "Origins Upgrades", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return 1;
}
