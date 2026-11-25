/* Runtime harness for "VVFP Founder X Buttons.dll" (tests/test_founder_x_buttons.py): the companion's own source,
   built into a 32-bit console program, its generator splice, X click and draw-time button work driven against a
   fake "Select 5 villagers" screen and a fake villager table, for The Tree of Life's and New Believers' layouts and
   for 150 and 256 records.

   The fake stock generator does what the stock one does (0x43B830 / 0x43E220): it clears the present byte of record
   [screen+0x18], makes the candidate in the first record whose present byte is 0 (a pregnant one makes a stand-in
   father there next and clears him again), and returns [screen+0x18].  It counts every time the record it made is
   NOT record [screen+0x18] -- the stock code then treats another record as the candidate.  The fake stock handler
   does what 0x43BC00 / 0x43E600 do with Select (1) and Reject (2), the Done state and the manager's flag included.

   Checked: with no X used, every Select / Reject sequence leaves the table and the screen exactly as the stock code
   alone does; removing each slot 0..4 with 1..5 chosen (the Done state too) frees that villager, moves the later
   ones down and keeps the candidate; picking on afterwards always reaches five distinct present founders with no
   stray present record; Rejects after a removal never leave an extra villager; the X buttons are on the screen
   exactly for the filled slots, never once the island has started; an empty slot's X does nothing.  Prints
   "ok"/"FAIL" lines and "== <n> failure(s) ==". */
#include "vvfp_founder_x_buttons.c"
#include <stdio.h>
#include <stdlib.h>

static int failures;

#define CHECK(cond, ...) do { if (cond) { ++passes; } \
    else { ++failures; printf("  FAIL " __VA_ARGS__); printf("\n"); } } while (0)

static int passes;

/* ---- the fake game ------------------------------------------------------------------------------------------- */

#define H_MAX_RECORDS 256
#define H_SERIAL 0x10                   /* where a fake record keeps who it is */

typedef struct {
    int id;
    int x, y;
    const char *label;
} h_widget;

static fx_game H;                       /* FX_VV4 or FX_VV5 with the fakes' addresses */
static int h_record_size;
static int h_population;                /* 150 or 256 */
static unsigned char *h_table;
static unsigned char h_mov[5];          /* `mov ecx, <table>` */
static unsigned char h_screen[0x80];
static h_widget h_select = { FX_SELECT_ID, 0, 0, "Select" };
static h_widget h_reject = { FX_REJECT_ID, 0, 0, "Reject" };
static h_widget *h_children[32];
static int h_child_count;
static int h_flag;                      /* the manager's flag: the fifth Select starts the island at once */
static int h_started;                   /* the island was started (scene 15 or the flag's start) */
static int h_serial;                    /* the next villager made */
static int h_mismatch;                  /* the generator made a record other than [screen+0x18] */
static int h_sounds;
static int h_hooked = 1;                /* 0: the stock code alone (the comparison run) */
static unsigned int h_colour = 0xFF00FF00u;

static unsigned char *h_rec(int i) {
    return h_table + (size_t)i * (size_t)h_record_size;
}

static void *__fastcall h_get(void *table, void *edx, int i) {
    (void)edx;
    if (table != h_table || i < 0 || i >= h_population) {
        return NULL;
    }
    return h_rec(i);
}

static int h_allocate(void) {
    int i;
    for (i = 0; i < h_population; ++i) {
        if (h_rec(i)[H.present] == 0) {
            h_rec(i)[H.present] = 1;
            *(int *)(h_rec(i) + H_SERIAL) = ++h_serial;
            return i;
        }
    }
    return -1;
}

/* The stock generator, as the game's (see the top). */
static int __fastcall h_stock_generator(unsigned char *screen) {
    int at = *(int *)(screen + FX_COUNT), made;
    unsigned char *record = (unsigned char *)h_get(h_table, NULL, at);
    if (record != NULL) {
        record[H.present] = 0;
    }
    made = h_allocate();
    if (made != at) {
        ++h_mismatch;
    }
    if (h_serial % 4 == 0) {            /* a pregnant candidate: her stand-in father, made and hidden again */
        int father = h_allocate();
        if (father >= 0) {
            h_rec(father)[H.present] = 0;
        }
    }
    return *(int *)(screen + FX_COUNT);
}

static void __fastcall h_next(unsigned char *screen) {
    int made = h_hooked ? fx_generate(&H, screen, h_stock_generator) : h_stock_generator(screen);
    *(int *)(screen + FX_CANDIDATE) = made;
}

static h_widget *h_find_widget(int id) {
    int i;
    for (i = 0; i < h_child_count; ++i) {
        if (h_children[i]->id == id) {
            return h_children[i];
        }
    }
    return NULL;
}

static void *__fastcall h_find(void *screen, void *edx, int id) {
    (void)screen;
    (void)edx;
    return h_find_widget(id);
}

static void __fastcall h_add(void *screen, void *edx, void *child) {
    (void)screen;
    (void)edx;
    if (h_child_count < 32) {
        h_children[h_child_count++] = (h_widget *)child;
    }
}

static void __fastcall h_remove(void *screen, void *edx, void *child) {
    int i;
    (void)screen;
    (void)edx;
    for (i = 0; i < h_child_count; ++i) {
        if (h_children[i] == child) {
            h_children[i] = h_children[--h_child_count];
            return;
        }
    }
}

static void *__cdecl h_new(unsigned int size) {
    return calloc(1, size < sizeof(h_widget) ? sizeof(h_widget) : size);
}

static int h_images;
static void *__cdecl h_images_get(void) {
    return &h_images;
}

static int h_picture;
static void *__fastcall h_image(void *manager, void *edx, int id) {
    (void)manager;
    (void)edx;
    return id == H.image_id ? &h_picture : NULL;
}

static void *__fastcall h_button(void *button, void *edx, int id, void *picture, int x, int y, void *parent,
                                 int zero) {
    h_widget *w = (h_widget *)button;
    (void)edx;
    (void)zero;
    if (picture != &h_picture || parent != h_screen) {
        return NULL;
    }
    w->id = id;
    w->x = x;
    w->y = y;
    return w;
}

static void __fastcall h_label(void *button, void *edx, const char *text, unsigned int colour, unsigned int hover,
                               unsigned int pressed, int zero) {
    (void)edx;
    (void)zero;
    if (colour == h_colour && hover == h_colour && pressed == h_colour) {
        ((h_widget *)button)->label = text;
    }
}

static void __fastcall h_text(void *button, void *edx, const char *text, int zero) {
    (void)edx;
    (void)zero;
    ((h_widget *)button)->label = text;
}

static int h_resources;
static void *__cdecl h_resources_get(void) {
    return &h_resources;
}

static const char *__fastcall h_string(void *resources, void *edx, int id) {
    (void)resources;
    (void)edx;
    return id == H.select_string ? "Select" : "?";
}

static void __fastcall h_sound(void *sounds, void *edx, int id) {
    (void)sounds;
    (void)edx;
    if (id == H.sound_id) {
        ++h_sounds;
    }
}

/* The stock command handler with Select and Reject (0x43BC00 / 0x43E600). */
static void h_stock_command(int id) {
    int *count = (int *)(h_screen + FX_COUNT), *ids = (int *)(h_screen + FX_CHOSEN);
    if (id == FX_SELECT_ID) {
        if (*count == 5) {
            h_started = 1;              /* "Done": scene 15 */
            return;
        }
        ids[*count] = *(int *)(h_screen + FX_CANDIDATE);
        *count += 1;
        if (*count == 5) {
            if (!h_flag) {
                h_select.label = "Done";
                h_remove(h_screen, NULL, &h_reject);
            } else {
                h_started = 1;          /* the start-game step at once */
            }
            return;
        }
    }
    if (*count != 5) {
        h_next(h_screen);
    }
}

/* A click as the game sends it to the screen's slot 3. */
static void h_click(int id) {
    if (!h_hooked || !fx_command(&H, h_screen, FX_COMMAND, id)) {
        h_stock_command(id);
    }
}

static void h_draw(void) {
    if (h_hooked) {
        fx_draw_work(&H, h_screen);
    }
}

/* A new village's screen, as its show (0x43BB60 / 0x43E560) leaves it: every record cleared, the first candidate. */
static void h_show(void) {
    memset(h_table, 0, (size_t)H_MAX_RECORDS * (size_t)h_record_size);
    memset(h_screen, 0, sizeof h_screen);
    *(void **)(h_screen + FX_REJECT) = &h_reject;
    *(int *)(h_screen + FX_CANDIDATE) = -1;
    h_child_count = 0;
    h_add(h_screen, NULL, &h_select);
    h_add(h_screen, NULL, &h_reject);
    h_select.label = "Select";
    h_started = 0;
    h_serial = 0;
    h_mismatch = 0;
    h_next(h_screen);
}

static void h_setup(const fx_game *g, int record_size, int population) {
    static unsigned char *table;
    if (table == NULL) {
        table = (unsigned char *)calloc(H_MAX_RECORDS, 0x3000);
    }
    H = *g;
    h_table = table;
    h_record_size = record_size;
    h_population = population;
    h_mov[0] = 0xB9;
    *(void **)(h_mov + 1) = h_table;
    H.table_mov = (unsigned int)(UINT_PTR)h_mov;
    H.record_get = (unsigned int)(UINT_PTR)h_get;
    H.next_candidate = (unsigned int)(UINT_PTR)h_next;
    H.op_new = (unsigned int)(UINT_PTR)h_new;
    H.images_get = (unsigned int)(UINT_PTR)h_images_get;
    H.image_get = (unsigned int)(UINT_PTR)h_image;
    H.button_new = (unsigned int)(UINT_PTR)h_button;
    H.button_label = (unsigned int)(UINT_PTR)h_label;
    H.label_text = (unsigned int)(UINT_PTR)h_text;
    H.label_colour = (unsigned int)(UINT_PTR)&h_colour;
    H.add_child = (unsigned int)(UINT_PTR)h_add;
    H.find_child = (unsigned int)(UINT_PTR)h_find;
    H.remove_child = (unsigned int)(UINT_PTR)h_remove;
    H.resources_get = (unsigned int)(UINT_PTR)h_resources_get;
    H.string_get = (unsigned int)(UINT_PTR)h_string;
    H.sound = (unsigned int)(UINT_PTR)h_sound;
    H.sounds = 0;
    /* A new screen object each layout: the companion makes its buttons again. */
    g_screen = NULL;
    g_made = 0;
}

/* ---- checks -------------------------------------------------------------------------------------------------- */

static int h_count(void) {
    return *(int *)(h_screen + FX_COUNT);
}

static int h_id(int k) {
    return ((int *)(h_screen + FX_CHOSEN))[k];
}

static int h_present(int i) {
    return h_rec(i)[H.present] != 0;
}

static int h_serial_of(int i) {
    return *(int *)(h_rec(i) + H_SERIAL);
}

static int h_present_total(void) {
    int i, n = 0;
    for (i = 0; i < h_population; ++i) {
        n += h_present(i);
    }
    return n;
}

/* The X buttons on the screen: a bit per slot. */
static int h_xs(void) {
    int i, bits = 0;
    for (i = 0; i < h_child_count; ++i) {
        int k = h_children[i]->id - FX_ID;
        if (k >= 0 && k < FX_SLOTS) {
            bits |= 1 << k;
        }
    }
    return bits;
}

/* Every chosen villager and the candidate (unless the island has started or Done shows the fifth) present and
   distinct, and nothing else present. */
static int h_consistent(void) {
    int n = h_count(), k, j, candidate = *(int *)(h_screen + FX_CANDIDATE), expected;
    for (k = 0; k < n; ++k) {
        if (h_id(k) < 0 || h_id(k) >= h_population || !h_present(h_id(k))) {
            return 0;
        }
        for (j = 0; j < k; ++j) {
            if (h_id(j) == h_id(k)) {
                return 0;
            }
        }
    }
    expected = n;
    if (n < 5) {
        if (candidate < 0 || !h_present(candidate)) {
            return 0;
        }
        for (k = 0; k < n; ++k) {
            if (h_id(k) == candidate) {
                return 0;
            }
        }
        ++expected;
    }
    return h_present_total() == expected;
}

static unsigned int h_rand_state;
static int h_rand(int n) {
    h_rand_state = h_rand_state * 1103515245u + 12345u;
    return (int)((h_rand_state >> 16) % (unsigned int)n);
}

/* Select (1) or Reject (2) at random until five are chosen; the table and the screen at the end. */
static void h_random_picks(unsigned int seed, unsigned char *table_out, unsigned char *screen_out) {
    h_rand_state = seed;
    h_show();
    while (h_count() < 5) {
        h_click(h_rand(3) == 0 ? FX_SELECT_ID : FX_REJECT_ID);
        h_draw();
    }
    memcpy(table_out, h_table, (size_t)h_population * (size_t)h_record_size);
    memcpy(screen_out, h_screen, sizeof h_screen);
}

static void h_layout(const char *name, const fx_game *g, int record_size, int population) {
    static unsigned char a[H_MAX_RECORDS * 0x3000], b[H_MAX_RECORDS * 0x3000];
    unsigned char sa[0x80], sb[0x80];
    unsigned int seed;
    int n, k, i;
    h_setup(g, record_size, population);
    printf("%s, %d records\n", name, population);

    /* 1. No X used: the stock screen, byte for byte. */
    for (seed = 1; seed <= 40; ++seed) {
        h_hooked = 0;
        h_random_picks(seed, a, sa);
        h_hooked = 1;
        h_random_picks(seed, b, sb);
        CHECK(memcmp(a, b, (size_t)population * (size_t)record_size) == 0 && memcmp(sa, sb, sizeof sa) == 0,
              "%s/%d seed %u: with no X the table and screen are the stock code's", name, population, seed);
        CHECK(h_mismatch == 0, "%s/%d seed %u: every candidate made in record [+0x18]", name, population, seed);
        CHECK(h_xs() == 0x1F && h_find_widget(FX_REJECT_ID) == NULL && lstrcmpA(h_select.label, "Done") == 0,
              "%s/%d seed %u: the Done state shows all five X", name, population, seed);
    }

    /* 2. Each slot removed with 1..5 chosen, then picking on to five. */
    for (n = 1; n <= 5; ++n) {
        for (k = 0; k < n; ++k) {
            int before[5], candidate, candidate_serial, removed, gone_serial, sounds;
            h_show();
            for (i = 0; i < n; ++i) {
                h_click(FX_REJECT_ID);  /* a few rejects first, as a player does */
                h_click(FX_SELECT_ID);
                h_draw();
            }
            CHECK(h_xs() == (1 << n) - 1, "%s/%d: %d chosen show X on exactly their slots", name, population, n);
            for (i = 0; i < n; ++i) {
                before[i] = h_id(i);
            }
            candidate = *(int *)(h_screen + FX_CANDIDATE);
            candidate_serial = n < 5 ? h_serial_of(candidate) : -1;
            removed = before[k];
            gone_serial = h_serial_of(removed);
            sounds = h_sounds;
            h_click(FX_ID + k);
            CHECK(h_count() == n - 1, "%s/%d: %d chosen, X on slot %d: %d chosen", name, population, n, k, n - 1);
            CHECK(!h_present(removed) || h_serial_of(removed) != gone_serial,
                  "%s/%d: %d chosen, X on slot %d: that villager is gone", name, population, n, k);
            for (i = 0; i < n - 1; ++i) {
                CHECK(h_id(i) == before[i < k ? i : i + 1], "%s/%d: %d chosen, X on slot %d: slot %d holds the "
                      "right villager", name, population, n, k, i);
            }
            CHECK(h_sounds == sounds + 1, "%s/%d: the X clicks with the game's sound", name, population);
            if (n < 5) {
                CHECK(*(int *)(h_screen + FX_CANDIDATE) == candidate && h_serial_of(candidate) == candidate_serial,
                      "%s/%d: %d chosen, X on slot %d: the candidate on show stays", name, population, n, k);
            } else {
                CHECK(lstrcmpA(h_select.label, "Select") == 0, "%s/%d: Done, X on slot %d: Select is Select again",
                      name, population, k);
                CHECK(h_find_widget(FX_REJECT_ID) == NULL, "%s/%d: Reject goes back only in the draw", name,
                      population);
            }
            h_draw();
            CHECK(h_find_widget(FX_REJECT_ID) == &h_reject, "%s/%d: %d chosen, X on slot %d: Reject is on",
                  name, population, n, k);
            CHECK(h_xs() == (1 << (n - 1)) - 1, "%s/%d: %d chosen, X on slot %d: X on the %d filled slots", name,
                  population, n, k, n - 1);
            CHECK(h_consistent(), "%s/%d: %d chosen, X on slot %d: chosen and candidate present, nothing else",
                  name, population, n, k);
            /* 3. Rejects after the removal leave no extra villager. */
            for (i = 0; i < 7; ++i) {
                h_click(FX_REJECT_ID);
                CHECK(h_consistent(), "%s/%d: %d chosen, X on slot %d, Reject %d: nothing extra present", name,
                      population, n, k, i + 1);
            }
            /* An empty slot's X: nothing. */
            h_click(FX_ID + 4);
            CHECK(h_count() == n - 1 && h_consistent(), "%s/%d: an empty slot's X does nothing", name, population);
            while (h_count() < 5) {
                h_click(FX_SELECT_ID);
                h_draw();
            }
            CHECK(h_consistent() && h_xs() == 0x1F, "%s/%d: %d chosen, X on slot %d, picked on: five distinct "
                  "founders, nothing else present", name, population, n, k);
            h_click(FX_SELECT_ID);
            CHECK(h_started, "%s/%d: Done starts the island", name, population);
        }
    }

    /* 4. Every slot removed one after another in the Done state, then chosen again. */
    h_show();
    while (h_count() < 5) {
        h_click(FX_SELECT_ID);
    }
    for (i = 0; i < 5; ++i) {
        h_draw();
        h_click(FX_ID + 0);
        h_draw();
        CHECK(h_count() == 4 - i && h_consistent() && h_xs() == (1 << (4 - i)) - 1, "%s/%d: X after X (%d left)",
              name, population, 4 - i);
    }
    while (h_count() > 0) {
        h_click(FX_ID + h_count() - 1);
        h_draw();
    }
    CHECK(h_count() == 0 && h_xs() == 0 && h_consistent(), "%s/%d: every founder taken out: no X, the candidate only",
          name, population);
    while (h_count() < 5) {
        h_click(FX_SELECT_ID);
        h_draw();
    }
    CHECK(h_consistent() && h_find_widget(FX_REJECT_ID) == NULL, "%s/%d: chosen again to Done", name, population);

    /* 5. The manager's flag: the fifth Select starts the island; no X, and an X click does nothing. */
    h_flag = 1;
    h_show();
    while (h_count() < 5) {
        h_click(FX_SELECT_ID);
        h_draw();
    }
    CHECK(h_started && h_xs() == 0, "%s/%d: started at the fifth Select: no X", name, population);
    h_click(FX_ID + 2);
    CHECK(h_count() == 5 && h_present(h_id(2)), "%s/%d: started: an X click does nothing", name, population);
    h_flag = 0;

    /* 6. The X stand at the right end of each name plank, just above it, the size of the game's picture. */
    for (k = 0; k < FX_SLOTS; ++k) {
        h_widget *x = (h_widget *)g_button[k];
        CHECK(x != NULL && x->x + g->button_w == g->slot_x[k] + FX_PLANK_HALF
              && x->y + g->button_h == g->plank_top - FX_ABOVE_PLANK && lstrcmpA(x->label, "X") == 0,
              "%s: slot %d's X at the plank's right end, labelled X", name, k);
    }
}

int main(void) {
    h_layout("The Tree of Life", &FX_VV4, 0x2E3C, 150);
    h_layout("The Tree of Life", &FX_VV4, 0x2E3C, 256);
    h_layout("New Believers", &FX_VV5, 0x2F44, 150);
    h_layout("New Believers", &FX_VV5, 0x2F44, 256);
    printf("%d check(s) passed\n== %d failure(s) ==\n", passes, failures);
    return failures == 0 ? 0 : 1;
}
