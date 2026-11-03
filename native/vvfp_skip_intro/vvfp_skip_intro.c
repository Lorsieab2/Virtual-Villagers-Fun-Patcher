/* VVFP Skip Intro -- "Skip All" on the intro story, A New Home and The Lost Children.

   WHAT.  The Secret City puts a "Skip All" button on its story pages: clicking it asks the game's own help
   question and the village starts.  A New Home and The Lost Children have no such button: their story
   (shown after the tribe is named) is two pages (A New Home) or three (The Lost Children), each turned by a
   click anywhere, and the LAST page itself asks the help question ("Would you like HELP the first time?",
   "Would you like tutorial tips turned on?") with the game's own Yes and No buttons.  This companion adds a
   Skip All button to every story page before the last; clicking it ends the story and brings the player to
   the last page with its Yes and No already shown.  The answer is the game's own: the last page's stock
   button slot runs untouched and sets exactly the flags a normal end of the story sets.  Design and
   addresses: docs/reports/vv12-skip-all/design.md.

   HOW.  Only vtable slots of the story page classes are replaced (SK_GAMES below), after every one is
   checked for its stock pointer, all or none (native/shared/install_sites.h).  No executable byte changes.
     * activate (slot 9), on a page before the last: the stock slot, then -- once per page object -- a button
       built as the last page builds its Yes button: the game's allocator, the game's button constructor with
       the game's own art name (the very pointer the Yes button uses), the game's label call with the Yes
       button's colours, at (640, the Yes/No row) -- The Secret City's Skip All column -- and added to the page
       as a child, so the page draws it and the game's event manager hands it the mouse.  Activating the first
       page (a new story) clears "skip pending".
     * buttons (slot 3), on a page before the last: message 8 from our button (id SK_ID) sets "skip pending"
       and calls the page's own event slot with event 2 -- the stock code a click anywhere runs -- so the page
       fades out and moves on exactly as it always does.  Everything else goes to the stock slot.
     * update (slot 8), The Lost Children's first page: the stock slot, then, if skip is pending and the
       stock code has just moved the game to the second page's state, the game goes to the last page's state
       instead (that page is built together with the first).
     * update (slot 8), the last page: while skip is pending, before the stock slot's first frame, its frame
       count is put at the end so the stock code adds its Yes and No buttons on that very frame; skip pending
       is then cleared.
     * destructor (slot 0), on a page before the last: our button is taken off the page with the game's own
       remove-child and freed by its own deleting destructor, then the stock destructor runs.
   Without a click on Skip All every replaced slot is the stock slot plus the button.

   SAFETY.  Each of our steps runs under structured exception handling: a fault leaves the page without the
   button or the skip, never without its stock behaviour.  Nothing is written to a save, a villager record or
   a file.  The label is asked of VVFP Translations.dll by key (native/shared/vvfp_translate.h); without it,
   or without a translation, it is "Skip All".  No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/vvfp_translate.h"

#define SK_ID 0x5C1A                 /* our button's id: message 8 carries it */
#define SK_FRAMES 1000               /* past the last page's 50-frame (25 fast) wait */
#define SK_MAX_BUTTONS 8
#define SK_MAX_PAGES 3
#define SK_MAX_SITES 12
#define SK_EVENT_PRESS 2             /* the page's own "click anywhere" event */
#define SK_MESSAGE_BUTTON 8          /* a button's click, reported to its parent's slot 3 */
#define SK_LABEL_INK 0xFF000000u     /* the Yes button's label colours (VV1 0x41EEA3, VV2 0x428E53) */
#define SK_LABEL_SHADE 0xFF555555u
#define SK_BUTTON_SIZE 0x14          /* the button object the page builds (VV1 0x41EE2B, VV2 0x428DDB) */

enum { ROLE_FIRST = 1, ROLE_MIDDLE = 2, ROLE_LAST = 3 };
enum { SLOT_DTOR = 0, SLOT_BUTTONS = 3, SLOT_UPDATE = 8, SLOT_ACTIVATE = 9 };

typedef struct {
    unsigned int vtable;
    unsigned char role;
    unsigned int dtor, buttons, update, activate;     /* the stock slot values; 0: slot not replaced */
} sk_page;

typedef struct {
    unsigned int alloc, ctor, label, add, remove;     /* the game's allocator and widget routines */
    unsigned int art;                                 /* the art name the last page's Yes button uses */
    int x, y;
    unsigned int state;                               /* the game state's field in the game object */
    unsigned int middle_state, last_state;            /* The Lost Children: page 2's and page 3's states */
    unsigned int counter, started;                    /* the last page's frame count and started flag */
    int pages;
    sk_page page[SK_MAX_PAGES];
} sk_game;

#define SK_PAGE_GAME 0x14            /* [page+0x14]: the game object (VV1 0x41ED96, VV2 0x428D46) */

static const sk_game SK_GAMES[3] = {
    {0},
    /* A New Home: page 1 (state 0x15) -> page 2 (state 0x16, the help question). */
    {0x44AF03u, 0x4019B0u, 0x4015B0u, 0x40AB80u, 0x40ABC0u, 0x459340u, 640, 560,
     0xACB4u, 0, 0, 0x25Cu, 0x08u, 2,
     {{0x4597F4u, ROLE_FIRST, 0x41EA00u, 0x41F640u, 0, 0x41E5C0u},
      {0x45982Cu, ROLE_LAST, 0, 0, 0x41F310u, 0}}},
    /* The Lost Children: page 1 (0x16) -> page 2 (0x17) -> page 3 (0x18, the help question). */
    {0x467F83u, 0x4019D0u, 0x4015D0u, 0x40B560u, 0x40B5A0u, 0x476378u, 640, 550,
     0x30470u, 0x17u, 0x18u, 0x19Cu, 0x08u, 3,
     {{0x476AC4u, ROLE_FIRST, 0x428220u, 0x401190u, 0x428240u, 0x427DB0u},
      {0x476AFCu, ROLE_MIDDLE, 0x4288F0u, 0x401190u, 0, 0x43A2B0u},
      {0x476B34u, ROLE_LAST, 0, 0, 0x4292C0u, 0}}},
};

typedef void *(__cdecl *alloc_fn)(unsigned int size);
typedef void *(__fastcall *ctor_fn)(void *button, int edx, int id, const char *art, int x, int y, void *parent,
                                    int zero);
typedef void (__fastcall *label_fn)(void *button, int edx, const char *text, unsigned int ink,
                                    unsigned int shade, unsigned int shade2, int zero);
typedef void (__fastcall *child_fn)(void *page, int edx, void *button);
typedef void *(__fastcall *dtor_fn)(void *object, int edx, unsigned int flags);
typedef char (__fastcall *buttons_fn)(void *page, int edx, int message, int id);
typedef char (__fastcall *event_fn)(void *page, int edx, int event, int x, int y);
typedef void (__fastcall *update_fn)(void *page, int edx);
typedef void (__fastcall *activate_fn)(void *page, int edx, char active);

typedef struct {
    unsigned char *page;
    void *button;
} sk_button;

static const sk_game *g_game;
static volatile LONG g_skip;
static sk_button g_buttons[SK_MAX_BUTTONS];
static unsigned int g_expect[SK_MAX_SITES];
static unsigned int g_ours[SK_MAX_SITES];
static int g_installed;

static const char *label_text(void) {
    return vvfp_tr("vvfp.skip_intro/vvfp_skip_intro.label_text.s0", "Skip All", 0);
}

static sk_button *button_of(const unsigned char *page) {
    int i;
    for (i = 0; i < SK_MAX_BUTTONS; ++i) {
        if (g_buttons[i].page == page && page != NULL) {
            return &g_buttons[i];
        }
    }
    return NULL;
}

/* The page's button: built and added the first time the page is activated. */
static void ensure_button(unsigned char *page) {
    const sk_game *g = g_game;
    sk_button *slot;
    void *button;
    if (button_of(page) != NULL) {
        return;
    }
    for (slot = g_buttons; slot < g_buttons + SK_MAX_BUTTONS && slot->page != NULL; ++slot) {
    }
    if (slot == g_buttons + SK_MAX_BUTTONS) {
        return;
    }
    button = ((alloc_fn)(UINT_PTR)g->alloc)(SK_BUTTON_SIZE);
    if (button == NULL) {
        return;
    }
    button = ((ctor_fn)(UINT_PTR)g->ctor)(button, 0, SK_ID, (const char *)(UINT_PTR)g->art, g->x, g->y, page, 0);
    if (button == NULL) {
        return;
    }
    ((label_fn)(UINT_PTR)g->label)(button, 0, label_text(), SK_LABEL_INK, SK_LABEL_SHADE, SK_LABEL_SHADE, 0);
    slot->page = page;
    slot->button = button;
    ((child_fn)(UINT_PTR)g->add)(page, 0, button);
}

static void drop_button(unsigned char *page) {
    sk_button *slot = button_of(page);
    void *button;
    if (slot == NULL) {
        return;
    }
    button = slot->button;
    slot->page = NULL;
    slot->button = NULL;
    ((child_fn)(UINT_PTR)g_game->remove)(page, 0, button);
    (*(dtor_fn *)*(void **)button)(button, 0, 1);
}

static void *dtor_common(unsigned char *page, unsigned int flags, int index) {
    __try {
        drop_button(page);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        sk_button *slot = button_of(page);
        if (slot != NULL) {
            slot->page = NULL;
            slot->button = NULL;
        }
    }
    return ((dtor_fn)(UINT_PTR)g_game->page[index].dtor)(page, 0, flags);
}

static char buttons_common(unsigned char *page, int message, int id, int index) {
    if (message == SK_MESSAGE_BUTTON && id == SK_ID) {
        __try {
            event_fn event = (event_fn)(*(void ***)page)[1];
            InterlockedExchange(&g_skip, 1);
            event(page, 0, SK_EVENT_PRESS, 0, 0);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
        return 1;
    }
    return ((buttons_fn)(UINT_PTR)g_game->page[index].buttons)(page, 0, message, id);
}

static void activate_common(unsigned char *page, char active, int index) {
    const sk_page *p = &g_game->page[index];
    ((activate_fn)(UINT_PTR)p->activate)(page, 0, active);
    if (!active) {
        return;
    }
    __try {
        if (p->role == ROLE_FIRST) {
            InterlockedExchange(&g_skip, 0);
        }
        ensure_button(page);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

static void update_common(unsigned char *page, int index) {
    const sk_game *g = g_game;
    const sk_page *p = &g->page[index];
    if (p->role == ROLE_LAST) {
        if (g_skip) {
            __try {
                if (page[g->started] == 0) {
                    *(int *)(page + g->counter) = SK_FRAMES;
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
            InterlockedExchange(&g_skip, 0);
        }
        ((update_fn)(UINT_PTR)p->update)(page, 0);
        return;
    }
    ((update_fn)(UINT_PTR)p->update)(page, 0);
    if (g_skip && g->middle_state != 0) {
        __try {
            unsigned char *game = *(unsigned char **)(page + SK_PAGE_GAME);
            unsigned int *state = (unsigned int *)(game + g->state);
            if (*state == g->middle_state) {
                *state = g->last_state;
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
}

/* One thiscall entry per page and slot (called as fastcall: ecx the page, edx unused). */
#define SK_ENTRIES(n)                                                                                         \
    static void *__fastcall dtor_##n(unsigned char *page, int edx, unsigned int flags) {                     \
        (void)edx;                                                                                            \
        return dtor_common(page, flags, n);                                                                   \
    }                                                                                                         \
    static char __fastcall buttons_##n(unsigned char *page, int edx, int message, int id) {                  \
        (void)edx;                                                                                            \
        return buttons_common(page, message, id, n);                                                          \
    }                                                                                                         \
    static void __fastcall update_##n(unsigned char *page, int edx) {                                         \
        (void)edx;                                                                                            \
        update_common(page, n);                                                                               \
    }                                                                                                         \
    static void __fastcall activate_##n(unsigned char *page, int edx, char active) {                          \
        (void)edx;                                                                                            \
        activate_common(page, active, n);                                                                     \
    }
SK_ENTRIES(0)
SK_ENTRIES(1)
SK_ENTRIES(2)

static const void *const SK_DTOR[SK_MAX_PAGES] = {(const void *)dtor_0, (const void *)dtor_1, (const void *)dtor_2};
static const void *const SK_BUTTONS[SK_MAX_PAGES] = {(const void *)buttons_0, (const void *)buttons_1,
                                                     (const void *)buttons_2};
static const void *const SK_UPDATE[SK_MAX_PAGES] = {(const void *)update_0, (const void *)update_1,
                                                    (const void *)update_2};
static const void *const SK_ACTIVATE[SK_MAX_PAGES] = {(const void *)activate_0, (const void *)activate_1,
                                                      (const void *)activate_2};

static void add_site(vvfp_site_write *w, int *count, unsigned int vtable, int slot, unsigned int stock,
                     const void *ours) {
    int n = *count;
    if (stock == 0 || n >= SK_MAX_SITES) {
        return;
    }
    g_expect[n] = stock;
    g_ours[n] = (unsigned int)(UINT_PTR)ours;
    vvfp_site_bytes(&w[n], vtable + 4u * (unsigned int)slot, 4, (const unsigned char *)&g_expect[n],
                    (const unsigned char *)&g_ours[n]);
    *count = n + 1;
}

/* The sites installed (for the tests' emulation): 0 when nothing was. */
int __stdcall VvfpSkipIntroSites(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write sites[SK_MAX_SITES];
    const sk_game *g;
    int count = 0, i;
    (void)shipped;
    if (g_installed || game < 1 || game > 2) {
        return;
    }
    g = &SK_GAMES[game];
    for (i = 0; i < g->pages; ++i) {
        const sk_page *p = &g->page[i];
        add_site(sites, &count, p->vtable, SLOT_DTOR, p->dtor, SK_DTOR[i]);
        add_site(sites, &count, p->vtable, SLOT_BUTTONS, p->buttons, SK_BUTTONS[i]);
        add_site(sites, &count, p->vtable, SLOT_UPDATE, p->update, SK_UPDATE[i]);
        add_site(sites, &count, p->vtable, SLOT_ACTIVATE, p->activate, SK_ACTIVATE[i]);
    }
    g_game = g;                      /* read by the entries only once a site points at them */
    if (!vvfp_install_sites(sites, count)) {
        g_game = NULL;
        return;
    }
    g_installed = count;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
