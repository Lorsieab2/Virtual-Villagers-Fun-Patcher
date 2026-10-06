/* Editing an epitaph, every game, and its "Epitaph changed" record.
   Included by cod_vv12.inc.

   The owner: the games have "pregenerated ones" and "typically the player
   can edit them"; give A New Home the same, and log each change as a
   separate "Epitaph changed" record (the logs are append-only, so the Death
   record keeps the epitaph the grave was made with).

   THE LATER GAMES.  The grave dialog holds an editable text box under
   "Here Lies" (The Lost Children's panel the same), filled from the grave
   when it opens; Done -- and only Done -- copies the box back over the
   grave's epitaph, unconditionally.  So the old text is read just before
   the copy and the new one just after, and a record is written when their
   text differs (epitaph_same: spaces before or after the same words are
   not an edit -- live, v1.35.59, stray Space presses in the box gave a
   record whose two epitaphs read the same):
                 before the copy          after it        the epitaph
       VV2       0x444433 (esi = panel)   0x44445C        grave + 0x19, char[0x41]
       VV3       0x41E6A3 (esi = dialog)  0x41E6BB        gravestone + 8, char[0x20]
       VV4       0x41C2D3                 0x41C2EB        roster entry + 0x38, char[0x20]
       VV5       0x41CB33                 0x41CB4B        roster entry + 0x38, char[0x20]
   VV2: grave = [esi+0x78] + [esi+0x60] * 0x7C + 0x2EB0C.  VV3: gravestone
   = [esi+0x4C], its slot at +0, its roster entry 0x5973F0 + 0x974 + slot *
   0x30.  VV4/VV5: roster entry = [esi+0x4C].

   A NEW HOME.  Its grave popup gets the same box, made with the game's own
   text widget exactly as its Villager Detail name box is made (0x449F43)
   and as The Lost Children's panel makes its epitaph box (0x444F91): at the
   end of the popup's constructor (0x436E5C, esi = popup), at x 0xA0, y
   0x46, rect (0x20, 0x46)-(0x11C, 0x5A), editable, at most 31 characters as
   in the later games, editing from the start.  The popup's own Done
   (onEvent 0x436400, code 8 with id [popup+0x64]; hooked at 0x436407, ecx
   = popup, [esp+8] = id) commits it: the text is read back with the
   widget's own getText and kept in the graves file as the player's own. */

static unsigned char *edit_scratch;
static char edit_old[72];
static const unsigned char *edit_target;     /* the epitaph being edited, or NULL */

/* "Epitaph changed": the villager's name (from the grave; their record is
   long gone), the grave, and both texts.  The name and age go into a copy
   rebuilt at the record's own offsets. */
static void epitaph_log(const unsigned char *name, unsigned int name_capacity, int age,
                        const char *title, const char *old_text, const char *new_text) {
    const struct game_records *r = &REC[g_game];
    char before[400];
    char old_line[72];
    char new_line[72];
    unsigned int n = name_capacity < r->name_capacity ? name_capacity : r->name_capacity;
    if (edit_scratch == NULL) {
        edit_scratch = (unsigned char *)VirtualAlloc(NULL, r->stride, MEM_COMMIT | MEM_RESERVE,
                                                     PAGE_READWRITE);
        if (edit_scratch == NULL) {
            return;
        }
    }
    memset(edit_scratch, 0, r->stride);
    memcpy(edit_scratch + r->name, name, n);
    edit_scratch[r->name + r->name_capacity - 1] = 0;
    *(int *)(edit_scratch + r->age) = age;
    cod_printable(old_line, sizeof old_line, old_text, 0x41);
    cod_printable(new_line, sizeof new_line, new_text, 0x41);
    wsprintfA(before, "  Age at death: %d\n  Grave: %s\n  Old epitaph: %s\n  New epitaph: %s\n",
              age, title, old_line[0] ? old_line : "(none)", new_line[0] ? new_line : "(none)");
    cod_write(LOG_EPITAPH, edit_scratch, 0, before, NULL, 0);
}

/* Whether two epitaphs (each at most `capacity` bytes, NUL-terminated
   within it or not) hold the same text: the same bytes once spaces before
   and after are set aside, since those show as nothing on the grave. */
static int epitaph_same(const char *a, const char *b, int capacity) {
    int a0 = 0, b0 = 0, a1 = 0, b1 = 0;
    while (a1 < capacity && a[a1] != 0) {
        ++a1;
    }
    while (b1 < capacity && b[b1] != 0) {
        ++b1;
    }
    while (a0 < a1 && a[a0] == ' ') {
        ++a0;
    }
    while (b0 < b1 && b[b0] == ' ') {
        ++b0;
    }
    while (a1 > a0 && a[a1 - 1] == ' ') {
        --a1;
    }
    while (b1 > b0 && b[b1 - 1] == ' ') {
        --b1;
    }
    return a1 - a0 == b1 - b0 && memcmp(a + a0, b + b0, (size_t)(a1 - a0)) == 0;
}

/* ---- The later games and The Lost Children --------------------------------- */

static const unsigned char *edit_epitaph_of(const unsigned int *regs) {
    const unsigned char *dialog = (const unsigned char *)(uintptr_t)regs[R_ESI];
    switch (g_game) {
    case 2: {
        const unsigned char *world = *(const unsigned char *const *)(dialog + 0x78);
        int slot = *(const int *)(dialog + 0x60);
        if (world == NULL || slot < 0 || slot >= GRAVES) {
            return NULL;
        }
        return world + GRV[2].graves + (size_t)slot * GRV[2].stride + GRV[2].epitaph;
    }
    case 3: {
        const unsigned char *stone = *(const unsigned char *const *)(dialog + 0x4C);
        return stone != NULL ? stone + 8 : NULL;
    }
    default: {
        const unsigned char *entry = *(const unsigned char *const *)(dialog + 0x4C);
        return entry != NULL ? entry + 0x38 : NULL;
    }
    }
}

static void edit_before(int site, const unsigned int *regs) {
    (void)site;
    edit_target = edit_epitaph_of(regs);
    if (edit_target != NULL) {
        memcpy(edit_old, edit_target, g_game == 2 ? 0x41 : EPITAPH_TEXT);
        edit_old[g_game == 2 ? 0x40 : EPITAPH_TEXT - 1] = '\0';
    }
}

static void edit_after(int site, const unsigned int *regs) {
    const unsigned char *epitaph = edit_target;
    char title[64];
    (void)site;
    edit_target = NULL;
    if (epitaph == NULL || epitaph != edit_epitaph_of(regs)
        || epitaph_same(edit_old, (const char *)epitaph, g_game == 2 ? 0x41 : EPITAPH_TEXT)) {
        return;
    }
    if (g_game == 2) {
        const unsigned char *grave = epitaph - GRV[2].epitaph;
        cod_grave_title(grave, title);
        epitaph_log(grave, GRV[2].name_capacity, *(const int *)(grave + GRV[2].age), title,
                    edit_old, (const char *)epitaph);
    } else {
        const unsigned char *entry;
        if (g_game == 3) {
            int slot = *(const int *)(epitaph - 8);
            entry = v345_entry(slot);
        } else {
            entry = epitaph - 0x38;
        }
        if (entry == NULL) {
            return;
        }
        v345_title(entry, title);
        epitaph_log(entry, 0x19u, *(const int *)(entry + V345[g_game].e_age), title,
                    edit_old, (const char *)epitaph);
    }
}

/* ---- A New Home ------------------------------------------------------------ */

typedef void *(__cdecl *vv1_new_fn)(unsigned int size);
typedef void *(__fastcall *vv1_box_ctor_fn)(void *box, int unused_edx, void *parent, int x, int y,
                                            const char *text, int one, int zero, float scale);
typedef void (__fastcall *vv1_colour_fn)(void *box, int unused_edx, unsigned int colour, void *font);
typedef void (__fastcall *vv1_rect_fn)(void *box, int unused_edx, const int *rect);
typedef void (__fastcall *vv1_add_child_fn)(void *parent, int unused_edx, void *child);
typedef void (__fastcall *vv1_editable_fn)(void *box, int unused_edx, int editable, int max);
typedef void (__fastcall *vv1_begin_fn)(void *box, int unused_edx);
typedef void (__fastcall *vv1_set_text_fn)(void *box, int unused_edx, const char *text);
typedef void (__fastcall *vv1_get_text_fn)(void *box, int unused_edx, char *out, int size);

static void *vv1_popup;          /* the popup the box belongs to */
static void *vv1_box;
static int vv1_box_slot;

/* 0x436E5C, the constructor's end: esi = the popup, its grave slot at +0x60
   and the graves' owner at +0x74 already set.  An empty grave (the popup
   closes itself) gets no box. */
static void vv1_popup_made(int site, const unsigned int *regs) {
    static const int rect[4] = { 0x20, 0x46, 0x11C, 0x5A };
    static const char empty[] = "";
    unsigned char *popup = (unsigned char *)(uintptr_t)regs[R_ESI];
    unsigned char *manager = *(unsigned char **)(popup + 0x74);
    int slot = *(const int *)(popup + 0x60);
    const struct cod_entry *entry;
    const char *epitaph;
    void *box;
    (void)site;
    vv1_popup = NULL;
    vv1_box = NULL;
    if (manager == NULL || slot < 0 || slot >= GRAVES) {
        return;
    }
    cod_bind(cod_slot());
    entry = cod_grave_entry(slot, manager + GRV[1].graves + (size_t)slot * GRV[1].stride);
    if (entry == NULL) {
        return;
    }
    epitaph = cod_entry_epitaph(entry);
    box = ((vv1_new_fn)(uintptr_t)0x44AF03u)(0x14u);
    if (box == NULL) {
        return;
    }
    box = ((vv1_box_ctor_fn)(uintptr_t)0x40C2C0u)(box, 0, popup, 0xA0, 0x46, empty, 1, 0, 1.0f);
    ((vv1_colour_fn)(uintptr_t)0x40BB00u)(box, 0, 0xFFFFFFFFu, *(void **)(uintptr_t)0x48B608u);
    ((vv1_rect_fn)(uintptr_t)0x40B9A0u)(box, 0, rect);
    ((vv1_add_child_fn)(uintptr_t)0x40AB80u)(popup, 0, box);
    ((vv1_editable_fn)(uintptr_t)0x40BB20u)(box, 0, 1, EPITAPH_TEXT - 1);
    ((vv1_set_text_fn)(uintptr_t)0x40BB30u)(box, 0, epitaph != NULL ? epitaph : empty);
    ((vv1_begin_fn)(uintptr_t)0x40BBA0u)(box, 0);
    vv1_popup = popup;
    vv1_box = box;
    vv1_box_slot = slot;
}

/* 0x436407, onEvent past its code-8 test: ecx = the popup, [esp+8] = the
   control's id; Done is [popup+0x64]. */
/* Keep `text` (what the box holds now) as grave `slot`'s epitaph when its
   text differs from the one it had (epitaph_same), and log the change. */
static void vv1_commit_epitaph(int slot, const unsigned char *grave, char *text) {
    const struct cod_entry *entry = cod_grave_entry(slot, grave);
    const char *old_text;
    char title[64];
    struct cod_event e;
    int i;
    if (entry == NULL) {
        return;
    }
    text[EPITAPH_TEXT - 1] = '\0';
    for (i = 0; i < EPITAPH_TEXT && text[i] != 0; ++i) {
        if ((unsigned char)text[i] < 0x20) {
            text[i] = ' ';            /* the widget takes 0x20-0xFF only */
        }
    }
    old_text = cod_entry_epitaph(entry);
    if (old_text == NULL) {
        old_text = "";
    }
    if (epitaph_same(old_text, text, EPITAPH_TEXT)) {
        return;
    }
    e.type = EVENT_GRAVE;
    e.index = slot;
    e.entry = *entry;
    e.entry.custom = 1;
    memset(e.entry.text, 0, sizeof e.entry.text);
    memcpy(e.entry.text, text, EPITAPH_TEXT - 1);
    cod_grave_title(grave, title);
    epitaph_log(grave, GRV[1].name_capacity, *(const int *)(grave + GRV[1].age), title,
                old_text, text);
    cod_event(&e);
}

static void vv1_popup_event(int site, const unsigned int *regs) {
    unsigned char *popup = (unsigned char *)(uintptr_t)regs[R_ECX];
    unsigned char *manager;
    char text[EPITAPH_TEXT];
    (void)site;
    if (popup != vv1_popup || vv1_box == NULL
        || reg_stack(regs, 8) != *(const unsigned int *)(popup + 0x64)) {
        return;
    }
    vv1_popup = NULL;
    manager = *(unsigned char **)(popup + 0x74);
    if (manager == NULL) {
        return;
    }
    memset(text, 0, sizeof text);
    ((vv1_get_text_fn)(uintptr_t)0x40BB70u)(vv1_box, 0, text, EPITAPH_TEXT);
    vv1_commit_epitaph(vv1_box_slot, manager + GRV[1].graves + (size_t)vv1_box_slot * GRV[1].stride,
                       text);
}

static void epitaph_edit_sites(void) {
    if (g_game == 1) {
        cod_add(0x436E5Cu, "C7465C22010000", vv1_popup_made);
        cod_add(0x436407u, "8B442408" "3B4164", vv1_popup_event);
    } else if (g_game == 2) {
        cod_add(0x444433u, "8B4E60" "8B5678", edit_before);
        cod_add(0x44445Cu, "B001" "5E" "C20800", edit_after);
    }
}

static void v345_edit_sites(void) {
    static const unsigned int BEFORE[6] = { 0, 0, 0, 0x41E6A3u, 0x41C2D3u, 0x41CB33u };
    static const unsigned int AFTER[6] = { 0, 0, 0, 0x41E6BBu, 0x41C2EBu, 0x41CB4Bu };
    cod_add(BEFORE[g_game], g_game == 3 ? "8B4E4C" "83C108" : "8B4E4C" "83C138", edit_before);
    cod_add(AFTER[g_game], "B001" "5E" "C20800", edit_after);
}
