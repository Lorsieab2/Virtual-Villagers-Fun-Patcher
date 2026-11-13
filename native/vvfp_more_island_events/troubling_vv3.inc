/* The Troubling Signs in The Secret City: its event object and its four-answer popup.  Included by
   vvfp_more_island_events.c after adv_vv345.inc, whose table slot, sites and dialog helpers it shares.

   ITS OWN SLOT.  The selector 0x419B30 lists the table's slots that can happen and draws one, rand(count).  This
   event and The Aspiring Adventurer share the table's slot 0 (the only slot no stock event owns), but each has its
   own place in the draw: when both can happen the list gets two entries for slot 0 (each a share of rand(count + 2),
   like any listed event) and the object put in slot 0 is either event's, 1 in 2 (t_list) -- so each is drawn 1 in
   (count + 2), as if it had a slot of its own.  The list holds one entry more than the stock slots (the dialog's
   frame follows it): when it is full the second entry is left out rather than written past it.

   THE POPUP is The Secret City's own two-choice island-event dialog (constructor 0x4192F0), built by the game, with
   two more answer buttons made exactly as the constructor makes its two (new 0x14 bytes 0x46EC93, the picture 4 of
   the image manager 0x42E9D0 / 0x42E8A0, the button 0x4019F0 with ids 4 and 5 and the dialog as its listener, the
   label 0x4185A0 + 0x401620 in the game's own label colours 0x4A460C..0x4A4614, the dialog's add-child 0x40C1F0):
   the game's art, font and button look.  The four stand one above the other, centred, 1.5 button heights apart as the
   constructor spaces its two (the two stock buttons move up, the new two take their places), so a label wider than
   its button stays whole on the screen and never meets another.  Room for them: before the answer the popup is sized
   for the tallest page plus blank lines worth three button heights (measured by the game's own justified paragraph,
   0x40A0C0, as the constructor measures), so every page fits above the four; Scrolling Popups is told of the room
   (VvfpMoreIslandEventsButtonRoom) so a capped, scrolled popup keeps its text above them too.
   This dialog's virtual table is a copy of the game's (0x47F28C) with two entries of its own: the click handler
   (ids 4 and 5 answered as the game answers 2 and 3: the buttons hidden, the answer, the first page, OK shown; every
   other click goes to the game's 0x419A00) and the keyboard handler (the stock one, 0x4011D0, takes no key): Enter or
   Esc is OK while OK is shown (as the game's message box, 0x41AC90), and the keys 1 to 4 pick the answers while they
   are shown.  The two new buttons are taken off the dialog when an answer is chosen and deleted at the next OK
   click, before the dialog closes.

   THE PAGES as the Adventurer's (t_ok): the opening with OK, its last page with the four answers; after the answer
   its pages with OK, the effects as the decree's last page is shown (adv_log.inc). */

#define TS_VV3_ROBE_BODY 29                    /* the robing 0x45FBC0: body +0xDF4 = 29 (0x45FBDE) */
#define TS_VV3_APP 0x4B309Cu                   /* the game object (0x428B60's singleton) */
#define TS_VV3_TRIBE 0x12ED4u                  /* its tribe name: the save writer's buffer +0x12ECC (0x427D61) */
#define TS_VV3_TRIBE_BYTES 0x50                /* up to the next field, +0x12F24 (the save slot) */
#define TS_BUTTON_IDS 2                        /* the new buttons: ids 4 and 5 */

/* ---- The village ------------------------------------------------------------------------------------------------ */

static int vv3_alive(const unsigned char *r) {
    return r[0xF10] != 0 && *(const int *)(r + 0xE78) > 0 && r[0xE94] == 0;
}

static int vv3_age(const unsigned char *r) {
    return *(const int *)(r + 0xDC4);
}

/* The Tribal Chief in the robe: the chief byte +0xE80 and the robe's body +0xDF4 (a chief the clothing dialog
   0x41BF89 has dressed otherwise is not robed). */
static int vv3_robed_chief(void) {
    int i;
    for (i = 0; i < g_records; ++i) {
        const unsigned char *r = t_record(i);
        if (r != NULL && vv3_alive(r) && r[0xE80] != 0 && *(const int *)(r + 0xDF4) == TS_VV3_ROBE_BODY) {
            return i;
        }
    }
    return -1;
}

/* The population as The Lost Children counts it for "A Dangerous Mission" (0x425860): every living villager who is
   not a look-alike, plus the babies each is carrying (The Secret City's litter +0xE90, 1 to 3, while +0xE8C). */
static int vv3_population(void) {
    int i, n = 0;
    for (i = 0; i < g_records; ++i) {
        const unsigned char *r = t_record(i);
        if (r != NULL && vv3_alive(r)) {
            ++n;
            if (*(const int *)(r + 0xE8C) != 0) {
                int litter = *(const int *)(r + 0xE90);
                n += litter >= 1 && litter <= 3 ? litter : 1;
            }
        }
    }
    return n;
}

/* The tribe's name the player typed: the game object's +0x12ED4 (the save writer 0x427D61 saves it, buffer
   +0x12ECC, native/shared/village_identity.c), read bounded; letters the player could type, else unknown. */
static int vv3_tribe(char *out, int cap) {
    int ok = 0;
    out[0] = '\0';
    __try {
        const unsigned char *app = *(const unsigned char *const *)(uintptr_t)TS_VV3_APP;
        int i;
        if (app != NULL) {
            const unsigned char *name = app + TS_VV3_TRIBE;
            for (i = 0; i < TS_VV3_TRIBE_BYTES && i < cap - 1 && name[i] != 0; ++i) {
                unsigned char c = name[i];
                if (c < 0x20 || c == 0x7F) {
                    break;
                }
                out[i] = (char)c;
            }
            ok = i > 0 && (i == TS_VV3_TRIBE_BYTES || i == cap - 1 || name[i] == 0);
            out[ok ? i : 0] = '\0';
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = 0;
        out[0] = '\0';
    }
    return ok;
}

static int vv3_stored(int kind) {
    return *t_store(kind);
}

static const ts_game TS_VV3 = { &ADV_VV3, vv3_robed_chief, vv3_population, vv3_tribe, vv3_stored, vv3_age,
                                vv3_alive };

/* The pages are laid out shorter than the Adventurer's 11 lines (TS_LINES): the popup also holds three more button
   heights for the four answers (3 x 42 px, about 6 of the font's 20-px lines), so a popup is no taller than the
   Adventurer's and fits the 600-px screen without Scrolling Popups. */
#define TS_LINES 5
static adv_game g_ts_layout;

/* ---- The event object ------------------------------------------------------------------------------------------- */

static unsigned int g_ts_vtable[17];
static const ts_game *g_ts;            /* the installed game's (The Secret City), NULL when not installed */
static int g_ts_stage, g_ts_page;
static int g_ts_effects_page = -1;
static void *g_ts_dialog;              /* the dialog showing the event */
static void *g_ts_buttons[TS_BUTTON_IDS];
static int g_ts_buttons_shown;
static int g_ts_room;                  /* three button heights: the room the four buttons take beyond the two */
static unsigned int g_ts_dvt[24];      /* the dialog's virtual table: [0] its RTTI locator */

typedef void *(__cdecl *ts_new_fn)(unsigned int size);
typedef void *(__cdecl *ts_getter_fn)(void);
typedef void *(__fastcall *ts_fetch_fn)(void *manager, void *unused, int id);
typedef void (__fastcall *ts_button_fn)(void *self, void *unused, int id, void *image, int a, int b, void *listener,
                                        int c);
typedef void (__fastcall *ts_label_fn)(void *self, void *unused, const char *text, unsigned int c1, unsigned int c2,
                                       unsigned int c3, int d);
typedef int (__fastcall *ts_justify_fn)(void *holder, void *unused, const char *text, int x, int y, int width,
                                        unsigned int a, unsigned int b, int measure);
typedef char (__fastcall *ts_message_fn)(void *self, void *unused, int message, int id);

static int ts_vcall(void *object, unsigned int slot) {
    return ((adv_tc0r)(*(void ***)object)[slot / 4])(object, NULL);
}

static void ts_place(void *button, int x, int y) {
    ADV_TC2((*(void ***)button)[1], button, x, y);
}

static int __fastcall ts_o_result(void *self, void *unused, int choice);

static char __fastcall ts_o_condition(void *self, void *unused) {
    (void)self; (void)unused;
    return (char)ts_possible(g_ts);
}

/* +0x08, asked once as the dialog is built: the event is composed here. */
static int __fastcall ts_o_title(void *self, void *unused) {
    (void)unused;
    g_ts_dialog = NULL;
    g_ts_stage = ADV_STAGE_NONE;
    g_ts_effects_page = -1;
    if (!ts_begin(g_ts, &g_ts_layout)) {
        ((adv_object *)self)->villager = NULL;         /* no villager: the dialog is not shown */
    } else {
        ((adv_object *)self)->villager = g_ts->g->record(ts.chief);
    }
    ts_piece(g_title, sizeof g_title, TS_TITLE, 0);
    if (ts.ready) {
        adv_log_event(g_ts->g->game, g_title);
    }
    t_strings_in();
    return g_tg->title_id;
}

static int __fastcall ts_o_question(void *self, void *unused) {
    (void)self; (void)unused;
    return t_text_id(ts.intro.count > 0 ? ts.intro.text[ts.intro.count - 1] : "");
}

static int ts_label_id(int group) {
    static char label[4][128];
    ts_piece(label[group], sizeof label[group], TS_LABELS[group], 0);
    t_strings_in();
    g_body_entry.text = label[group];
    return g_tg->body_id;
}

static int __fastcall ts_o_label_a(void *self, void *unused) {
    (void)self; (void)unused;
    return ts_label_id(TS_SPIRITUAL);
}

static int __fastcall ts_o_label_b(void *self, void *unused) {
    (void)self; (void)unused;
    return ts_label_id(TS_MAGICIANS);
}

/* The tallest page with blank lines worth `room` pixels more, measured by the game's own justified paragraph as the
   constructor measures (holder 0x408940, the box's width +0x858, the font 0x4B3D60, the colour +0x82C). */
static const char *ts_padded(const char *text, void *dialog, int room) {
    static char padded[ADV_PAGE_BYTES];
    ts_justify_fn justify = (ts_justify_fn)(uintptr_t)0x40A0C0u;
    void *holder;
    unsigned char *d = (unsigned char *)dialog;
    int base, k;
    adv_copy(padded, sizeof padded, text);
    if (dialog == NULL || room <= 0) {
        return padded;
    }
    holder = ((ts_getter_fn)(uintptr_t)0x408940u)();
    base = justify(holder, NULL, padded, 0, 0, *(int *)(d + 0x858), *(unsigned int *)(uintptr_t)0x4B3D60u,
                   *(unsigned int *)(d + 0x82C), 1);
    for (k = 0; k < 40 && adv_len(padded) + 3 < ADV_PAGE_TEXT_MAX; ++k) {
        if (justify(holder, NULL, padded, 0, 0, *(int *)(d + 0x858), *(unsigned int *)(uintptr_t)0x4B3D60u,
                    *(unsigned int *)(d + 0x82C), 1) >= base + room) {
            break;
        }
        adv_cat(padded, sizeof padded, "\n ");
    }
    return padded;
}

/* +0x28(c): before the answer the tallest page of the event with the four buttons' room (the popup is sized to it),
   then the answer's page. */
static int __fastcall ts_o_result(void *self, void *unused, int choice) {
    (void)self; (void)unused; (void)choice;
    if (!ts.answered) {
        const char *text = ts_tallest_text();
        __try {
            void *button = g_ctor_dialog != NULL ? *(void **)((unsigned char *)g_ctor_dialog + 0x85C) : NULL;
            if (button != NULL) {
                g_ts_room = 3 * ts_vcall(button, 0x10);
                text = ts_padded(text, g_ctor_dialog, g_ts_room);
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            text = ts_tallest_text();
        }
        return t_text_id(text);
    }
    return t_text_id(ts.result[ts.choice].text[g_ts_page < ts.result[ts.choice].count ? g_ts_page : 0]);
}

/* The answer's page that ends its text is shown: its effects. */
static void ts_page_effects(void) {
    g_ts_effects_page = -1;
    adv_log_effects(ts_flow_effects, ts.choice);
}

/* The answer `group`: logged, its first page next (with the effects when it is the last). */
static void ts_chosen(int group) {
    static char label[128];
    if (!ts_answer(group)) {
        return;
    }
    ts_piece(label, sizeof label, TS_LABELS[group], 0);
    adv_log_choice(label);
    g_ts_stage = ADV_STAGE_RESULT;
    g_ts_page = 0;
    g_ts_effects_page = ts.result[group].count - 1;
    if (g_ts_effects_page == 0) {
        ts_page_effects();
    }
}

/* +0x34(c): the game's own two buttons (c 0 the first: the spiritual leaders; 1 the magicians). */
static void __fastcall ts_o_choose(void *self, void *unused, int choice) {
    (void)self; (void)unused;
    ts_chosen(choice != 0 ? TS_MAGICIANS : TS_SPIRITUAL);
}

/* +0x2C(c): OK on the last page (the effects were made as it was shown). */
static void __fastcall ts_o_apply(void *self, void *unused, int choice) {
    (void)self; (void)unused; (void)choice;
    if (g_ts_effects_page >= 0 && ts.answered) {
        ts_page_effects();                       /* never left unmade (a page count that changed: a fault) */
    }
    g_ts_stage = ADV_STAGE_NONE;
    g_ts_dialog = NULL;
    t_strings_out();
}

static void ts_build_object(void) {
    static const int SLOTS[] = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13 };
    void *functions[13];
    int i;
    memcpy(g_ts_vtable, (const void *)(uintptr_t)(g_tg->source_vtable - 4u), sizeof g_ts_vtable);
    functions[0] = (void *)o_delete;
    functions[1] = (void *)ts_o_condition;
    functions[2] = (void *)ts_o_title;
    functions[3] = (void *)ts_o_question;
    functions[4] = (void *)o_true;
    functions[5] = (void *)ts_o_label_a;
    functions[6] = (void *)ts_o_label_b;
    functions[7] = (void *)o_villager;
    functions[8] = (void *)o_nobody;
    functions[9] = (void *)o_pose;
    functions[10] = (void *)ts_o_result;
    functions[11] = (void *)ts_o_apply;
    functions[12] = (void *)ts_o_choose;
    for (i = 0; i < 13; ++i) {
        g_ts_vtable[1 + SLOTS[i]] = (unsigned int)(uintptr_t)functions[i];
    }
    memset(&g_ts_object, 0, sizeof g_ts_object);
    g_ts_object.vtable = &g_ts_vtable[1];
    g_ts_object.amount = -1;
}

/* ---- The four buttons -------------------------------------------------------------------------------------------- */

/* The four answer buttons, top to bottom: the game's two, then ours. */
static void *ts_button(void *dialog, int group) {
    if (group < 2) {
        return t_control(dialog, group == 0 ? 0x85C : 0x860);
    }
    return g_ts_buttons[group - 2];
}

static void ts_show_answers(void *dialog, int shown) {
    int k;
    for (k = 0; k < TS_GROUPS; ++k) {
        void *b = ts_button(dialog, k);
        if (b != NULL) {
            ADV_TC1(shown ? g_tg->show : g_tg->hide, dialog, b);
        }
    }
    g_ts_buttons_shown = shown;
}

/* Our two buttons, made as the constructor makes its two; 0 when they could not be made. */
static int ts_make_buttons(void *dialog) {
    void *manager = ((ts_getter_fn)(uintptr_t)0x42E9D0u)();
    int k;
    for (k = 0; k < TS_BUTTON_IDS; ++k) {
        void *image, *b = ((ts_new_fn)(uintptr_t)0x46EC93u)(0x14);
        if (b == NULL) {
            return 0;
        }
        image = ((ts_fetch_fn)(uintptr_t)0x42E8A0u)(manager, NULL, 4);
        ((ts_button_fn)(uintptr_t)0x4019F0u)(b, NULL, 4 + k, image, 0, 0, dialog, 0);
        g_ts_buttons[k] = b;
        ADV_TC1(g_tg->set_text, dialog, ts_label_id(TS_NATURALISTS + k));
        ((ts_label_fn)(uintptr_t)0x401620u)(b, NULL, (const char *)dialog + 0x58, *(unsigned int *)(uintptr_t)0x4A460Cu,
                                           *(unsigned int *)(uintptr_t)0x4A4610u,
                                           *(unsigned int *)(uintptr_t)0x4A4614u, 0);
    }
    return 1;
}

/* The four one above the other at the panel's bottom, centred, 1.5 button heights apart (the constructor's spacing:
   its second at height - 2 x h, its first 1.5 x h above). */
static void ts_layout(void *dialog) {
    unsigned char *d = (unsigned char *)dialog;
    int width = *(int *)(d + 0x1C) - *(int *)(d + 0x14);
    int height = *(int *)(d + 0x20) - *(int *)(d + 0x18);
    int k;
    for (k = 0; k < TS_GROUPS; ++k) {
        void *b = ts_button(dialog, k);
        int bw = ts_vcall(b, 0x0C), bh = ts_vcall(b, 0x10);
        int step = bh + bh / 2;
        ts_place(b, (width - bw) / 2, height - 2 * bh - (TS_GROUPS - 1 - k) * step);
    }
}

/* Our two buttons deleted (taken off the dialog first). */
static void ts_free_buttons(void *dialog) {
    int k;
    for (k = 0; k < TS_BUTTON_IDS; ++k) {
        void *b = g_ts_buttons[k];
        if (b != NULL) {
            g_ts_buttons[k] = NULL;
            __try {
                if (dialog != NULL && g_ts_buttons_shown) {
                    ADV_TC1(g_tg->hide, dialog, b);
                }
                ((adv_tc1)(*(void ***)b)[0])(b, NULL, 1);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }
    }
    g_ts_buttons_shown = 0;
}

/* OK: 1 when this event's next page was shown (the dialog stays); the four answers back on the question's last. */
static int ts_ok(void *dialog) {
    if (dialog != g_ts_dialog) {
        return 0;
    }
    if (g_ts_stage == ADV_STAGE_INTRO) {
        ++g_ts_page;
        if (g_ts_page >= ts.intro.count - 1) {
            t_set_text(dialog, ts.intro.text[ts.intro.count - 1]);
            ADV_TC1(g_tg->hide, dialog, t_control(dialog, 0x864));
            ts_show_answers(dialog, 1);
            g_ts_stage = ADV_STAGE_QUESTION;
        } else {
            t_set_text(dialog, ts.intro.text[g_ts_page]);
        }
        return 1;
    }
    if (g_ts_stage == ADV_STAGE_RESULT && g_ts_page + 1 < ts.result[ts.choice].count) {
        ++g_ts_page;
        t_set_text(dialog, ts.result[ts.choice].text[g_ts_page]);
        if (g_ts_page == g_ts_effects_page) {
            ts_page_effects();
        }
        return 1;
    }
    return 0;
}

/* The dialog's click handler (its +0x0C): ids 4 and 5 are our answers, the rest the game's. */
static char __fastcall ts_message(void *dialog, void *unused, int message, int id) {
    char handled = 0;
    (void)unused;
    __try {
        if (message == 8 && (id == 4 || id == 5) && g_ts_stage == ADV_STAGE_QUESTION && !ts.answered) {
            ts_show_answers(dialog, 0);
            *(int *)((unsigned char *)dialog + 0x830) = id - 2;
            ts_chosen(id == 4 ? TS_NATURALISTS : TS_SCIENTISTS);
            t_set_text(dialog, ts.result[ts.choice].text[0]);
            ADV_TC1(g_tg->show, dialog, t_control(dialog, 0x864));
            return 0;                                  /* as the game's own answer: the dialog stays */
        }
        if (message == 8 && id == 1 && ts.answered) {
            ts_free_buttons(dialog);                   /* OK after the answer: our buttons are no longer needed */
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    handled = ((ts_message_fn)(uintptr_t)0x419A00u)(dialog, NULL, message, id);
    __try {
        if (message == 8 && (id == 2 || id == 3) && ts.answered && g_ts_buttons_shown) {
            ts_show_answers(dialog, 0);                /* the game hid its two: ours go too */
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return handled;
}

/* The dialog's keyboard handler (its +0x08; the game's own 0x4011D0 takes no key): Enter (0x3EB) or Esc (0x3E8) is
   OK while OK is shown, as the game's message box (0x41AC90); the typed keys 1 to 4 (type 5) pick the answers while
   they are shown.  1 when the key was used. */
static char __fastcall ts_key(void *dialog, void *unused, int type, int code, int raw) {
    (void)unused; (void)raw;
    __try {
        if (dialog != g_ts_dialog) {
            return 0;
        }
        if (type == 6 && (code == 0x3EB || code == 0x3E8) && g_ts_stage != ADV_STAGE_QUESTION) {
            ts_message(dialog, NULL, 8, 1);
            return 1;
        }
        if (type == 5 && g_ts_stage == ADV_STAGE_QUESTION && !ts.answered && code >= '1' && code <= '4') {
            ts_message(dialog, NULL, 8, 2 + (code - '1'));
            return 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return 0;
}

/* After the dialog's constructor: our two buttons, the four laid out, our virtual table; a question of more than one
   page starts with its first page and OK. */
static void ts_after_ctor(void *dialog) {
    unsigned char *d = (unsigned char *)dialog;
    if (!ts.ready || d[0x4C] == 0) {
        return;
    }
    ts_free_buttons(NULL);                             /* never two sets */
    g_ts_dialog = dialog;
    g_ts_page = 0;
    if (!ts_make_buttons(dialog)) {
        ts_free_buttons(NULL);
        return;
    }
    ADV_TC1(g_tg->show, dialog, g_ts_buttons[0]);      /* the constructor showed the game's two */
    ADV_TC1(g_tg->show, dialog, g_ts_buttons[1]);
    g_ts_buttons_shown = 1;
    ts_layout(dialog);
    memcpy(g_ts_dvt, (const void *)(uintptr_t)(0x47F28Cu - 4u), sizeof g_ts_dvt);
    g_ts_dvt[1 + 2] = (unsigned int)(uintptr_t)ts_key;
    g_ts_dvt[1 + 3] = (unsigned int)(uintptr_t)ts_message;
    if (*(unsigned int *)d == 0x47F28Cu) {
        *(unsigned int **)d = &g_ts_dvt[1];
    }
    if (ts.intro.count > 1) {
        ts_show_answers(dialog, 0);
        ADV_TC1(g_tg->show, dialog, t_control(dialog, 0x864));
        t_set_text(dialog, ts.intro.text[0]);
        g_ts_stage = ADV_STAGE_INTRO;
    } else {
        t_set_text(dialog, ts.intro.text[0]);    /* the labels went through the text: the question back */
        g_ts_stage = ADV_STAGE_QUESTION;
    }
}

/* The room the four buttons take beyond the game's two, for Scrolling Popups: 0 for any other dialog. */
int __stdcall VvfpMoreIslandEventsButtonRoom(const void *popup) {
    int room = 0;
    __try {
        room = popup != NULL && popup == g_ts_dialog && g_ts != NULL ? g_ts_room : 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        room = 0;
    }
    return room > 0 && room < 2048 ? room : 0;
}

/* Whether the selector lists it (t_list). */
static int ts_listable(void) {
    int possible = 0;
    __try {
        possible = g_ts != NULL && ts_possible(g_ts);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        possible = 0;
    }
    return possible;
}

static void ts_install(void) {
    g_ts_layout = ADV_VV3;
    g_ts_layout.lines = TS_LINES;
    ts_build_object();
    g_ts = &TS_VV3;
}
