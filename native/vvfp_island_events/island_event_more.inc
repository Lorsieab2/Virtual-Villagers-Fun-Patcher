/* More of what an island event changes (the owner's order for v1.35.66,
   included by vvfp_island_events.c):

     1. A "New villager" record also says the newcomer's Sex and Age, in the
        Births and Conceptions log's words ("Sex: Female") and the age in the
        game's units with its years ("Age: 340 (17 years old)", 20 units a
        year in all five games, as the Golden Child's "Age at birth: 100 (5
        years old)" line says it).
     2. What a Custom Island Event can change on a villager that is not one
        of the record's own fields in island_event_games.inc: the custom
        title (kept in its own file, read through "VVFP Parentage Export.dll"
        VillageCustomTitle), the mask (native/shared/mask_line.h: New
        Believers' own Heathen masks and the Origins companions' cosmetic
        ones), the Special villager title (native/shared/special_title.h: the
        Golden Child, an Esteemed Elder, the Tribal Chief, New Believers'
        Heathen roles), The Lost Children's Esteemed Elder's totem (drawn by
        the elder's statue record), and A New Home's parents (kept by "VVFP
        VV1 Parentage.dll", Vv1ParentageQuery / Vv1ParentageQueryNames).  The
        later games' parents are record fields (the tables).  Each is read
        from the live record just before the event and just after, and a
        difference is one "  <Label>: <old> -> <new>" line in the villager's
        record, as every other change is.
     3. What an event changes in the village as a whole -- food, tech points,
        the food stores (the Custom Island Event's "food sources" and Refill),
        the puzzles (solved or not) and the weather -- in one record of its
        own, "Island event <n>" with the event's title and a "Village:" block
        of "<Label>: <old> -> <new>" lines, written only when something
        changed ("VVFP Parentage Export.dll" WriteVillageEventRecord).

   Every address is the Story / Cheat Upgrades' Custom Island Event's own
   (native/vvfp_story_upgrades/story_c1.inc .. story_c5.inc: the food and
   tech stores, the food sources, the puzzle tables), each traced in the
   stock executable there; the weather is the weather object's type, the
   dword the game's weather setter writes first (The Tree of Life 0x46BC56
   on 0x6C461C, New Believers 0x477040 reading 0x718EA0, The Secret City
   0x45C1D1 reading 0x4B86C4). */

#include "../shared/mask_line.h"
#include "../shared/special_title.h"

/* ---- 1. A new villager's sex and age --------------------------------------- */

#define UNITS_PER_YEAR 20

static const struct field *field_labelled(const char *label) {
    int k;
    for (k = 0; k < g_layout->field_count; ++k) {
        if (strcmp(g_layout->fields[k].label, label) == 0) {
            return &g_layout->fields[k];
        }
    }
    return NULL;
}

/* "  New villager: yes\n  Sex: Female\n  Age: 340 (17 years old)\n" */
static void more_arrival(const unsigned char *record, char *out, size_t size) {
    const struct field *sex = field_labelled("Sex");
    const struct field *age = field_labelled("Age");
    size_t used;
    out[0] = '\0';
    used = (size_t)_snprintf(out, size, "  New villager: yes\n");
    if (sex != NULL && used < size) {
        char text[32];
        field_text(sex, record, text, sizeof text);
        used += (size_t)_snprintf(out + used, size - used, "  Sex: %s\n", text);
    }
    if (age != NULL && used < size) {
        int units = *(const int *)(record + age->offset);
        int years = units >= 0 ? units / UNITS_PER_YEAR : 0;
        _snprintf(out + used, size - used, "  Age: %d (%d year%s old)\n", units, years, years == 1 ? "" : "s");
    }
    out[size - 1] = '\0';
}

/* ---- 2. What a Custom Island Event changes beyond the record's fields ------ */

#define MORE_VALUES 8
#define MORE_TEXT 40
struct more_values {
    char value[MORE_VALUES][MORE_TEXT];   /* "" = could not be read: never compared */
};
static struct more_values g_more_before[MAX_VILLAGERS];

typedef int (__stdcall *custom_title_fn)(int, const void *, char *, int);
typedef int (__stdcall *vv1_query_fn)(int, int *);
typedef int (__stdcall *vv1_query_names_fn)(int, char *, char *, int);

static custom_title_fn g_more_title;      /* resolved once (a harness sets its own) */

static custom_title_fn more_custom_title(void) {
    static int looked;
    if (!looked && g_more_title == NULL) {
        /* The Story companion's table in memory (it sets the titles; its file is
           published later, so the file can not say at the moment of the event,
           seen live in New Believers); without it, the file through the
           Parentage Export DLL. */
        HMODULE story = GetModuleHandleA("VVFP Story Upgrades.dll");
        looked = 1;
        g_more_title = story != NULL ? (custom_title_fn)GetProcAddress(story, "VvfpStoryCustomTitle") : NULL;
        if (g_more_title == NULL) {
            HMODULE module = vvfp_load_patcher_dll("VVFP Parentage Export.dll");
            g_more_title = module != NULL ? (custom_title_fn)GetProcAddress(module, "VillageCustomTitle") : NULL;
        }
    }
    return g_more_title;
}

/* The Lost Children's villager array (the records the statues are in too). */
static unsigned char *more_vv2_records_real(void) {
    return readable((const void *)(uintptr_t)0x499F24u, 4) ? *(unsigned char **)(uintptr_t)0x499F24u : NULL;
}
static unsigned char *(*g_more_vv2_records)(void) = more_vv2_records_real;

/* A New Home's villager array, for the parents' record index. */
static unsigned char *more_vv1_records_real(void) {
    return readable((const void *)(uintptr_t)0x48B614u, 4) ? *(unsigned char **)(uintptr_t)0x48B614u : NULL;
}
static unsigned char *(*g_more_vv1_records)(void) = more_vv1_records_real;

/* The totem the Esteemed Elder in `r` has: the statue 0x44D190 made, which
   copies the elder's name, sex, lineage and parents' names and keeps no
   index -- exactly one statue must agree (as story_c2.inc c2_totem_of) --
   drawn with art frame +0x550 modulo 8 (the words story_c2.inc gives them). */
static void more_vv2_totem(const unsigned char *r, char *out, size_t size) {
    static const char *const TOTEMS[8] = {
        "brown face, blue mouth", "green figure", "teal, red crest", "yellow and purple",
        "red headdress", "dark navy face", "tall carved wood", "green grinning face",
    };
    unsigned char *records = g_more_vv2_records();
    const unsigned char *found = NULL;
    int i;
    if (r[0x7FC] == 0) {
        _snprintf(out, size, "none");
        return;
    }
    if (records == NULL || !readable(records, (size_t)256 * 0xE48C)) {
        out[0] = '\0';
        return;
    }
    for (i = 0; i < 256; ++i) {
        const unsigned char *t = records + (size_t)i * 0xE48C;
        if (t == r || t[0x30] == 0 || t[0x558] == 0) {
            continue;
        }
        if (memcmp(t + 0x564, r + 0x564, 0x18) != 0 || *(const int *)(t + 0x538) != *(const int *)(r + 0x538)
            || *(const int *)(t + 0x554) != *(const int *)(r + 0x554) || memcmp(t + 0x57D, r + 0x57D, 0x32) != 0) {
            continue;
        }
        if (found != NULL) {
            out[0] = '\0';                /* two statues agree: nobody can say which */
            return;
        }
        found = t;
    }
    if (found == NULL) {
        _snprintf(out, size, "none");
        return;
    }
    _snprintf(out, size, "%s", TOTEMS[(*(const int *)(found + 0x550) % 8 + 8) % 8]);
}

/* A New Home's parents, kept by "VVFP VV1 Parentage.dll" by record index:
   values 2..7 of more_values (father, his head, his body, mother, her head,
   her body).  Nothing when the companion is not loaded (no Show Parents). */
static vv1_query_fn g_vv1_query;          /* resolved once (a harness sets its own) */
static vv1_query_names_fn g_vv1_names;

static void more_vv1_parents(const unsigned char *r, struct more_values *out) {
    static int looked;
    vv1_query_fn query;
    vv1_query_names_fn names;
    unsigned char *records = g_more_vv1_records();
    int looks[4], index;
    char father[0x20], mother[0x20];
    if (!looked && g_vv1_query == NULL) {
        /* Loaded by the Show Parents row only; never loaded from here. */
        HMODULE module = GetModuleHandleA("VVFP VV1 Parentage.dll");
        looked = 1;
        if (module != NULL) {
            g_vv1_query = (vv1_query_fn)GetProcAddress(module, "Vv1ParentageQuery");
            g_vv1_names = (vv1_query_names_fn)GetProcAddress(module, "Vv1ParentageQueryNames");
        }
    }
    query = g_vv1_query;
    names = g_vv1_names;
    if (query == NULL || names == NULL || records == NULL || r < records
        || (size_t)(r - records) % 0x3D8 != 0 || (size_t)(r - records) / 0x3D8 >= 256) {
        return;
    }
    index = (int)((size_t)(r - records) / 0x3D8);
    if (!query(index, looks) || !names(index, father, mother, (int)sizeof father)) {
        return;
    }
    father[sizeof father - 1] = mother[sizeof mother - 1] = '\0';
    _snprintf(out->value[2], MORE_TEXT, "%s", father[0] ? father : "(none)");
    _snprintf(out->value[5], MORE_TEXT, "%s", mother[0] ? mother : "(none)");
    {
        const int at[4] = { 3, 4, 6, 7 };
        int k;
        for (k = 0; k < 4; ++k) {
            if (looks[k] < 0) {
                _snprintf(out->value[at[k]], MORE_TEXT, "(unknown)");
            } else {
                _snprintf(out->value[at[k]], MORE_TEXT, "%d", looks[k]);
            }
        }
    }
}

/* The labels, in each game: 0 the custom title, 1 the mask, then the
   game's own (A New Home's parents; The Lost Children's totem), last the
   Special villager title. */
static const char *const MORE_LABELS[GAMES + 1][MORE_VALUES] = {
    { NULL },
    { "Custom title", "Mask", "Father", "Father's head", "Father's body", "Mother", "Mother's head",
      "Mother's body" },
    { "Custom title", "Mask", "Totem", NULL },
    { "Custom title", "Mask", NULL },
    { "Custom title", "Mask", NULL },
    { "Custom title", "Mask", NULL },
};
#define MORE_SPECIAL_LABEL "Special villager"

/* Read from a LIVE record (a mask and a custom title are kept by where the
   record is); the Special villager title from the record itself. */
static void more_read(const unsigned char *r, struct more_values *out, char *special, size_t special_size) {
    custom_title_fn title = more_custom_title();
    const char *mask, *named;
    int k;
    for (k = 0; k < MORE_VALUES; ++k) {
        out->value[k][0] = '\0';
    }
    if (r == NULL || !readable(r, g_layout->pad)) {
        special[0] = '\0';
        return;
    }
    if (title != NULL) {
        char text[MORE_TEXT];
        if (title(g_game, r, text, (int)sizeof text)) {
            text[sizeof text - 1] = '\0';
            _snprintf(out->value[0], MORE_TEXT, "%s", text[0] ? text : "none");
        }
    }
    mask = vv_mask_name(g_game, r);
    _snprintf(out->value[1], MORE_TEXT, "%s", mask != NULL ? mask : "none");
    if (g_game == 1) {
        more_vv1_parents(r, out);
    } else if (g_game == 2) {
        more_vv2_totem(r, out->value[2], MORE_TEXT);
    }
    for (k = 0; k < MORE_VALUES; ++k) {
        out->value[k][MORE_TEXT - 1] = '\0';
    }
    named = vv_special_title(g_game, r);
    _snprintf(special, special_size, "%s", named != NULL ? named : "none");
    special[special_size - 1] = '\0';
}

static char g_more_special[MAX_VILLAGERS][MORE_TEXT];

/* Appends this villager's changes to `changes` (at `used`); returns the new length. */
static size_t more_villager_changes(int i, const unsigned char *live, char *changes, size_t used, size_t size) {
    struct more_values now;
    char special[MORE_TEXT];
    int k;
    if (i < 0 || i >= MAX_VILLAGERS) {
        return used;
    }
    more_read(live, &now, special, sizeof special);
    for (k = 0; k < MORE_VALUES; ++k) {
        const char *label = MORE_LABELS[g_game][k];
        const char *was = g_more_before[i].value[k];
        if (label == NULL || was[0] == '\0' || now.value[k][0] == '\0' || strcmp(was, now.value[k]) == 0) {
            continue;
        }
        if (used < size) {
            int n = _snprintf(changes + used, size - used, "  %s: %s -> %s\n", label, was, now.value[k]);
            used = n < 0 ? size : used + (size_t)n;
        }
    }
    if (g_more_special[i][0] && special[0] && strcmp(g_more_special[i], special) != 0 && used < size) {
        int n = _snprintf(changes + used, size - used, "  %s: %s -> %s\n", MORE_SPECIAL_LABEL,
                          g_more_special[i], special);
        used = n < 0 ? size : used + (size_t)n;
    }
    return used;
}

/* ---- 3. The village -------------------------------------------------------- */

enum {
    VF_INT,                               /* a store: a number */
    VF_SOLVED_BYTE,                       /* a puzzle's solved byte */
    VF_SOLVED_AT,                         /* a puzzle's progress at least `extra` */
    VF_SOLVED_TABLE,                      /* a puzzle's progress at least the dword at `extra` (filled by the game) */
    VF_TREE_KIND,                         /* The Secret City's fruit tree: 0 Banana, 1 Mango, 2 Papaya (the exe's words) */
    VF_WEATHER                            /* the weather's type */
};
struct village_field {
    const char *label;
    unsigned int global;                  /* 0: `at` is an address; else the world pointer's address */
    unsigned int at;                      /* the address, or the offset in the world */
    int type;
    unsigned int extra;
};

/* A New Home: the world [0x48AEDC] (story_c1.inc). */
#define W1 0x48AEDCu
static const struct village_field VV1_VILLAGE[] = {
    { "Food", W1, 0xA2EC, VF_INT, 0 },
    { "Tech points", W1, 0xA2FC, VF_INT, 0 },
    { "Berries remaining", W1, 0xA2F4, VF_INT, 0 },
    { "Crops", W1, 0xA2F8, VF_INT, 0 },
    { "The Well", W1, 0xA058, VF_SOLVED_BYTE, 0 },
    { "The Hut", W1, 0x9FE8, VF_SOLVED_BYTE, 0 },
    { "The Beach", W1, 0x9FB8, VF_SOLVED_BYTE, 0 },
    { "The School", W1, 0xA050, VF_SOLVED_BYTE, 0 },
    { "The Lagoon", W1, 0x9FB0, VF_SOLVED_BYTE, 0 },
    { "The Magic Fish of Fertility", W1, 0xA090, VF_SOLVED_BYTE, 0 },
    { "The Cemetery", W1, 0xA000, VF_SOLVED_BYTE, 0 },
    { "Herb Mastery", W1, 0xA080, VF_SOLVED_BYTE, 0 },
    { "The Garden", W1, 0x9FC0, VF_SOLVED_BYTE, 0 },
    { "The Magic Plant of Life", W1, 0xA098, VF_SOLVED_BYTE, 0 },
    { "The Temple", W1, 0x9FE0, VF_SOLVED_BYTE, 0 },
    { "The Idol", W1, 0x9FD8, VF_SOLVED_BYTE, 0 },
    { "The Butterflies", W1, 0xA088, VF_SOLVED_BYTE, 0 },
    { "The Treasure", W1, 0x9FC8, VF_SOLVED_BYTE, 0 },
    { "The Cave", W1, 0x9FA8, VF_SOLVED_BYTE, 0 },
    { "Small hut 2", W1, 0x9FF0, VF_SOLVED_BYTE, 0 },
    { "Small hut 3", W1, 0x9FF8, VF_SOLVED_BYTE, 0 },
    { NULL, 0, 0, 0, 0 },
};

/* The Lost Children: the world [0x4997BC] (story_c2.inc). */
#define W2 0x4997BCu
static const struct village_field VV2_VILLAGE[] = {
    { "Food", W2, 0x2EAA4, VF_INT, 0 },
    { "Tech points", W2, 0x2EADC, VF_INT, 0 },
    { "Coconut trees", W2, 0x2EACC, VF_INT, 0 },
    { "Fish", W2, 0x2EAD0, VF_INT, 0 },
    { "Field protection from birds", W2, 0x2EAD4, VF_INT, 0 },
    { "Crops", W2, 0x2EAD8, VF_INT, 0 },
    { "The Lovely Hut", W2, 0x2E760, VF_SOLVED_BYTE, 0 },
    { "Fire", W2, 0x2E768, VF_SOLVED_BYTE, 0 },
    { "The Scarecrow", W2, 0x2E770, VF_SOLVED_BYTE, 0 },
    { "The Elder Totem", W2, 0x2E778, VF_SOLVED_BYTE, 0 },
    { "The Hospital", W2, 0x2E780, VF_SOLVED_BYTE, 0 },
    { "Herb Mastery", W2, 0x2E788, VF_SOLVED_BYTE, 0 },
    { "The Sewing Hut", W2, 0x2E790, VF_SOLVED_BYTE, 0 },
    { "The Dam", W2, 0x2E798, VF_SOLVED_BYTE, 0 },
    { "The Cutting Tool", W2, 0x2E7A0, VF_SOLVED_BYTE, 0 },
    { "The Stew", W2, 0x2E7A8, VF_SOLVED_BYTE, 0 },
    { "The Vine Wall", W2, 0x2E7B0, VF_SOLVED_BYTE, 0 },
    { "The Ancient Mosaic", W2, 0x2E7B8, VF_SOLVED_BYTE, 0 },
    { "The Boxed Gong Piece", W2, 0x2E7C0, VF_SOLVED_BYTE, 0 },
    { "The Sunken Gong Piece", W2, 0x2E7C8, VF_SOLVED_BYTE, 0 },
    { "The Inlaid Gong Piece", W2, 0x2E7D8, VF_SOLVED_BYTE, 0 },
    { "The Overgrown Gong Piece", W2, 0x2E7E0, VF_SOLVED_BYTE, 0 },
    { "Sustainable Fishing", W2, 0x2E7E8, VF_SOLVED_BYTE, 0 },
    { NULL, 0, 0, 0, 0 },
};

/* The Secret City (story_c3.inc): stores and puzzle i's progress at
   0x594990 + 8i, solved at its threshold (0x49D230[i]). */
#define P3(i) (0x594990u + 8u * (i))
static const struct village_field VV3_VILLAGE[] = {
    { "Food", 0, 0x582490u, VF_INT, 0 },
    { "Tech points", 0, 0x582644u, VF_INT, 0 },
    { "Fruit on tree 1", 0, 0x594810u, VF_INT, 0 },
    { "Fruit on tree 2", 0, 0x594828u, VF_INT, 0 },
    { "Fruit on tree 3", 0, 0x594840u, VF_INT, 0 },
    { "Tree 1 kind", 0, 0x59480Cu, VF_TREE_KIND, 0 },
    { "Tree 2 kind", 0, 0x594824u, VF_TREE_KIND, 0 },
    { "Tree 3 kind", 0, 0x59483Cu, VF_TREE_KIND, 0 },
    { "Honey", 0, 0x5945E0u, VF_INT, 0 },
    { "Weather", 0, 0x4B86C4u, VF_WEATHER, 0 },
    { "The First Chief", 0, P3(0), VF_SOLVED_AT, 1 },
    { "The Bee Hive", 0, P3(1), VF_SOLVED_AT, 1 },
    { "The Alchemy Lab", 0, P3(2), VF_SOLVED_AT, 5 },
    { "The Roster of the Dead", 0, P3(3), VF_SOLVED_AT, 700 },
    { "Weather Dancing", 0, P3(4), VF_SOLVED_AT, 1 },
    { "The Lift", 0, P3(5), VF_SOLVED_AT, 1 },
    { "The Ruins", 0, P3(6), VF_SOLVED_AT, 1800 },
    { "The Ancient Bath", 0, P3(7), VF_SOLVED_AT, 1400 },
    { "The Statue", 0, P3(8), VF_SOLVED_AT, 2 },
    { "The Orchard", 0, P3(9), VF_SOLVED_AT, 1 },
    { "The Sharks", 0, P3(10), VF_SOLVED_AT, 1 },
    { "Aromatherapy", 0, P3(11), VF_SOLVED_AT, 6 },
    { "The Ash Key", 0, P3(12), VF_SOLVED_AT, 1 },
    { "The Cliff Key", 0, P3(13), VF_SOLVED_AT, 1 },
    { "The Clam Key", 0, P3(14), VF_SOLVED_AT, 1 },
    { "The Chief and the Princess", 0, P3(15), VF_SOLVED_AT, 1 },
    { NULL, 0, 0, 0, 0 },
};

/* The Tree of Life (story_c4.inc): puzzle i at 0x4D8BF8 + 8i, solved at the
   threshold 0x4D8B20 + 4i the game fills. */
#define P4(i) (0x4D8BF8u + 8u * (i)), VF_SOLVED_TABLE, (0x4D8B20u + 4u * (i))
static const struct village_field VV4_VILLAGE[] = {
    { "Food", 0, 0x4D6DD0u, VF_INT, 0 },
    { "Tech points", 0, 0x4D6F88u, VF_INT, 0 },
    { "Blackberries", 0x4CB51Cu, 0x170F8, VF_INT, 0 },
    { "Cutting tools", 0, 0x4D8618u, VF_INT, 0 },
    { "Bars of soap", 0, 0x4D8D98u, VF_INT, 0 },
    { "Weather", 0, 0x6C461Cu, VF_WEATHER, 4 },
    { "The Cutting Tool", 0, P4(0) },
    { "The Stream", 0, P4(1) },
    { "Boiling Water", 0, P4(2) },
    { "Soap Invented", 0, P4(3) },
    { "The Butterflies", 0, P4(4) },
    { "The Frog Rescue", 0, P4(5) },
    { "The Cooking Pit", 0, P4(6) },
    { "Cloth Invented", 0, P4(7) },
    { "The Nursery School", 0, P4(8) },
    { "The Mossy Rocks", 0, P4(9) },
    { "The Grand Feast", 0, P4(10) },
    { "Fishing Nets", 0, P4(11) },
    { "Pruning the Tree", 0, P4(12) },
    { "Honoring the Tree", 0, P4(13) },
    { "Purify Tree", 0, P4(14) },
    { "Decorating the Tree", 0, P4(15) },
    { NULL, 0, 0, 0, 0 },
};

/* New Believers (story_c5.inc): item id at 0x51E008 + 8id, done at the
   threshold 0x51DF30 + 4id the game fills. */
#define P5(id) (0x51E008u + 8u * (id)), VF_SOLVED_TABLE, (0x51DF30u + 4u * (id))
static const struct village_field VV5_VILLAGE[] = {
    { "Food", 0, 0x51D34Cu, VF_INT, 0 },
    { "Tech points", 0, 0x51D5F8u, VF_INT, 0 },
    { "Noni remaining", 0x4DACE0u, 0x17D58, VF_INT, 0 },
    { "Crops", 0x4DACE0u, 0x17D5C, VF_INT, 0 },
    { "Weather", 0, 0x718EA0u, VF_WEATHER, 4 },
    { "The Nursery School", 0, P5(0) },
    { "The Prison Break", 0, P5(2) },
    { "The Hungry Totem", 0, P5(3) },
    { "The Knowing Totem", 0, P5(4) },
    { "The Buried Mausoleum", 0, P5(6) },
    { "The Blocking Totem", 0, P5(7) },
    { "The Hollow Totem", 0, P5(8) },
    { "The Lake", 0, P5(10) },
    { "The Pain Totem", 0, P5(11) },
    { "The Rainbow Totem", 0, P5(12) },
    { "The Tribute Statue", 0, P5(14) },
    { "The Blind Totem", 0, P5(15) },
    { "Small hut 1", 0, P5(19) },
    { "Small hut 2", 0, P5(20) },
    { "Small hut 3", 0, P5(21) },
    { "The clothing hut", 0, P5(22) },
    { "The love shack", 0, P5(23) },
    { "The nursery school building", 0, P5(24) },
    { NULL, 0, 0, 0, 0 },
};

static const struct village_field *const VILLAGE_FIELDS[GAMES + 1] = {
    NULL, VV1_VILLAGE, VV2_VILLAGE, VV3_VILLAGE, VV4_VILLAGE, VV5_VILLAGE,
};

#define VILLAGE_MAX 40
static char g_village_before[VILLAGE_MAX][MORE_TEXT];

/* Where a game address is in this process: itself (the harness maps it into
   memory of its own). */
static unsigned char *more_address_real(unsigned int address) {
    return (unsigned char *)(uintptr_t)address;
}
static unsigned char *(*g_more_address)(unsigned int address) = more_address_real;

static const unsigned char *village_dword(const struct village_field *f, unsigned int address) {
    unsigned char *at;
    if (f->global != 0) {
        unsigned char *global = g_more_address(f->global);
        unsigned char *world;
        if (!readable(global, 4)) {
            return NULL;
        }
        world = *(unsigned char **)global;
        at = world != NULL ? world + address : NULL;
    } else {
        at = g_more_address(address);
    }
    return at != NULL && readable(at, 4) ? at : NULL;
}

/* "" when it cannot be read (then it is not compared). */
static void village_text(const struct village_field *f, char *out, size_t size) {
    const unsigned char *at = village_dword(f, f->at);
    int value;
    out[0] = '\0';
    if (at == NULL) {
        return;
    }
    value = *(const int *)at;
    switch (f->type) {
    case VF_SOLVED_BYTE:
        _snprintf(out, size, "%s", at[0] != 0 ? "solved" : "unsolved");
        break;
    case VF_SOLVED_AT:
        _snprintf(out, size, "%s", value >= (int)f->extra ? "solved" : "unsolved");
        break;
    case VF_SOLVED_TABLE: {
        const unsigned char *threshold = g_more_address(f->extra);
        int t;
        if (!readable(threshold, 4)) {
            return;
        }
        t = *(const int *)threshold;
        if (t < 1) {
            return;                       /* the game has not filled the table yet */
        }
        _snprintf(out, size, "%s", value >= t ? "solved" : "unsolved");
        break;
    }
    case VF_TREE_KIND:
        _snprintf(out, size, "%s", value == 0 ? "Banana" : value == 1 ? "Mango" : value == 2 ? "Papaya" : "(unknown)");
        break;
    case VF_WEATHER:
        /* 0 the clear weather the games return to, 2 the rain (The Rainy
           Season, the Custom Island Event's "Rain begins"); the others by
           their number. */
        if (value == 0) {
            _snprintf(out, size, "clear");
        } else if (value == 2) {
            _snprintf(out, size, "rain");
        } else if (value == 4 && f->extra == 4) {
            /* The Tree of Life's and New Believers' type 4, the fog (its own
               periodic check, 0x46BE10 / 0x477348; The Mysterious Footprints
               sets it, seen live in New Believers). */
            _snprintf(out, size, "fog");
        } else {
            _snprintf(out, size, "type %d", value);
        }
        break;
    default:
        _snprintf(out, size, "%d", value);
        break;
    }
    out[size - 1] = '\0';
}

/* The record writer for the village record. */
typedef int (__stdcall *write_village_event_fn)(int, const char *);
static write_village_event_fn g_write_village;

static write_village_event_fn village_writer(void) {
    static int looked;
    if (!looked && g_write_village == NULL) {
        HMODULE module = vvfp_load_patcher_dll("VVFP Parentage Export.dll");
        looked = 1;
        if (module != NULL) {
            g_write_village = (write_village_event_fn)GetProcAddress(module, "WriteVillageEventRecord");
        }
    }
    return g_write_village;
}

/* ---- The two hooks the comparison calls ------------------------------------ */

/* After the snapshot: what is not in the copies, read now. */
static void more_take(const struct snapshot *s) {
    const struct village_field *fields = VILLAGE_FIELDS[g_game];
    int i;
    for (i = 0; i < s->count && i < MAX_VILLAGERS; ++i) {
        more_read(s->where[i], &g_more_before[i], g_more_special[i], MORE_TEXT);
    }
    for (i = 0; i < VILLAGE_MAX; ++i) {
        g_village_before[i][0] = '\0';
        if (fields != NULL && fields[i].label != NULL) {
            village_text(&fields[i], g_village_before[i], MORE_TEXT);
        } else {
            break;
        }
    }
}

/* After the villagers: one village record when the village changed. */
static void more_village(const char *before) {
    const struct village_field *fields = VILLAGE_FIELDS[g_game];
    char text[2048];
    size_t used, head;
    int i;
    if (fields == NULL || village_writer() == NULL) {
        return;
    }
    used = (size_t)_snprintf(text, sizeof text, "%s  Village:\n", before);
    if (used >= sizeof text) {
        return;
    }
    head = used;
    for (i = 0; i < VILLAGE_MAX && fields[i].label != NULL; ++i) {
        char now[MORE_TEXT];
        village_text(&fields[i], now, sizeof now);
        if (g_village_before[i][0] == '\0' || now[0] == '\0' || strcmp(g_village_before[i], now) == 0) {
            continue;
        }
        if (used < sizeof text) {
            int n = _snprintf(text + used, sizeof text - used, "    %s: %s -> %s\n", fields[i].label,
                              g_village_before[i], now);
            used = n < 0 ? sizeof text : used + (size_t)n;
        }
    }
    if (used == head || used >= sizeof text) {
        return;                           /* nothing changed (or too much to say whole) */
    }
    g_write_village(g_game, text);
}
