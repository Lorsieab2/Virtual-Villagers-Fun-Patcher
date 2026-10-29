/* head_look.h -- what "VVFP Head Look.dll" (native/vvfp_head_look) offers the Origins companions.

   Change Appearance lets the player pick each villager's head look: Auto (the game's own rule, the old head
   from a shown age of 1,100 age units -- 55 years), Young (always the young head) or Old (always the old,
   grey head).  The look is kept in the patcher's own per-save file and follows the villager; the head
   value in the record never changes.  Each game's Change Appearance window (VV1 native/vv1_origins_icons,
   VV2 native/vv2_origins_icons, VV3 native/vv3_full_mastery_candidate, VV4 native/vv4_origins_icons, VV5
   native/vv5_task9_origins) finds the DLL with GetModuleHandleA (VVFP Startup.dll loads it at game start)
   and shows the choice only when it is there and its draws follow the look (VvfpHeadLookInstalled); A New
   Home's draws are Grey Hair at 55's (native/vv1_grey_hair), so there the choice also needs that patch. */
#ifndef VVFP_HEAD_LOOK_H
#define VVFP_HEAD_LOOK_H

#define VVFP_HEAD_LOOK_DLL "VVFP Head Look.dll"

#define VVFP_HEAD_LOOK_AUTO 0
#define VVFP_HEAD_LOOK_YOUNG 1
#define VVFP_HEAD_LOOK_OLD 2

/* The age a villager starts to be drawn with the old head under Auto: a shown age of 1,100 age units. */
#define VVFP_HEAD_LOOK_OLD_AGE 1100

/* int __stdcall VvfpHeadLookInstalled(int game): 1 when that game's head draws follow the look. */
#define VVFP_HEAD_LOOK_INSTALLED "VvfpHeadLookInstalled"
/* int __stdcall VvfpHeadLookGet(int game, const void *record): the look kept for the villager in that
   record (0 Auto, 1 Young, 2 Old); Auto when nothing is kept or the village is not known yet. */
#define VVFP_HEAD_LOOK_GET "VvfpHeadLookGet"
/* int __stdcall VvfpHeadLookSet(int game, const void *record, int look): keep `look` for that villager;
   1 when the file says so, 0 when nothing changed. */
#define VVFP_HEAD_LOOK_SET "VvfpHeadLookSet"
/* int __stdcall VvfpHeadLookSetMany(int game, const void *const *records, const int *looks, int count):
   keep looks[i] for the villager in records[i], all of them in ONE write of the file; 1 when the file says
   so for every one, 0 when nothing changed (a record that is not a held villager of this village, a look
   above 2, or a write that failed -- every look is then as it was).  Change Appearance for All. */
#define VVFP_HEAD_LOOK_SET_MANY "VvfpHeadLookSetMany"

#ifndef RC_INVOKED
typedef int (__stdcall *vvfp_head_look_installed_fn)(int game);
typedef int (__stdcall *vvfp_head_look_get_fn)(int game, const void *record);
typedef int (__stdcall *vvfp_head_look_set_fn)(int game, const void *record, int look);
typedef int (__stdcall *vvfp_head_look_set_many_fn)(int game, const void *const *records, const int *looks,
                                                    int count);

/* The exports, or all NULL when the DLL is not in the game or this game's draws do not follow the look.
   Asked each time a Change Appearance window opens (the DLL is never unloaded). */
typedef struct {
    vvfp_head_look_get_fn get;
    vvfp_head_look_set_fn set;
    vvfp_head_look_set_many_fn set_many;
} vvfp_head_look_api;

static int vvfp_head_look_find(int game, vvfp_head_look_api *api) {
    HMODULE dll = GetModuleHandleA(VVFP_HEAD_LOOK_DLL);
    vvfp_head_look_installed_fn installed;
    api->get = NULL;
    api->set = NULL;
    api->set_many = NULL;
    if (dll == NULL) {
        return 0;
    }
    installed = (vvfp_head_look_installed_fn)GetProcAddress(dll, VVFP_HEAD_LOOK_INSTALLED);
    if (installed == NULL || !installed(game)) {
        return 0;
    }
    api->get = (vvfp_head_look_get_fn)GetProcAddress(dll, VVFP_HEAD_LOOK_GET);
    api->set = (vvfp_head_look_set_fn)GetProcAddress(dll, VVFP_HEAD_LOOK_SET);
    api->set_many = (vvfp_head_look_set_many_fn)GetProcAddress(dll, VVFP_HEAD_LOOK_SET_MANY);
    if (api->get == NULL || api->set == NULL || api->set_many == NULL) {
        api->get = NULL;
        api->set = NULL;
        api->set_many = NULL;
        return 0;
    }
    return 1;
}

/* Whether a villager of `age` is drawn with the old head under `look`. */
static int vvfp_head_look_old(int look, int age) {
    return look == VVFP_HEAD_LOOK_OLD || (look == VVFP_HEAD_LOOK_AUTO && age >= VVFP_HEAD_LOOK_OLD_AGE);
}

/* The Random look: Young or Old, never Auto (the owner: "Random in the Head look row: Young or Old").
   Rolled by the window that offers it, so what it previews (or plans, for Change Appearance for All) is
   exactly what is kept.  `rng` is the window's own xorshift state, never 0. */
static int vvfp_head_look_random(unsigned int *rng) {
    unsigned int x = *rng ? *rng : 0x9E3779B9u;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *rng = x;
    return (x >> 7) & 1u ? VVFP_HEAD_LOOK_OLD : VVFP_HEAD_LOOK_YOUNG;
}
#endif

/* The three radio buttons every Change Appearance window adds, in this order (ids per window). */
#define VVFP_HEAD_LOOK_LABEL_AUTO "Auto (old from 55)"
#define VVFP_HEAD_LOOK_LABEL_YOUNG "Young"
#define VVFP_HEAD_LOOK_LABEL_OLD "Old"

#endif /* VVFP_HEAD_LOOK_H */
