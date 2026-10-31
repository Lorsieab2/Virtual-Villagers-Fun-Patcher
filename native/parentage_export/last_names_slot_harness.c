/* Runtime harness: the slot the parentage companion hands VVFP Last Names (and
   Number Names) at a birth is the slot of the village ON SCREEN, never the
   village saved last.  tests/test_last_names_slot_is_the_games.py builds and
   runs it (32-bit MSVC only).

   The owner's Secret City, 2026-10-30/31: Save 2 was saved, Save 1 loaded in
   the same session, and the load's catch-up births were handed slot 2 -- the
   " (Save 2)" of the header the statistics companion published at Save 2's
   save, which nothing replaces until Save 1 is saved.  Save 2's Last Names
   record ("From the father", no villager lines) was read instead of Save 1's,
   where the father Pio Bandele's own rule was 50:50: all 37 children Bandele.

   The companion's source is compiled whole.  The game's save manager (the
   singleton whose field names the slot the game saves to,
   native/shared/game_save_slot.h) is a stand-in here, and so is VVFP Last
   Names: GetModuleHandleA / GetProcAddress answer a recorder for
   "VvfpRuleLastName2" that keeps the slot it is given.  Nothing is written to
   disk.  Exit code 0 when every check passes. */
#include <stdio.h>
#include <string.h>
#include <windows.h>

static const unsigned char *harness_managers[6];
#define VV_GAME_SAVE_MANAGER_AT(game) ((const unsigned char *const volatile *)&harness_managers[game])

static int g_rule_calls;
static int g_rule_slot;
static char g_rule_father[64];

static int __stdcall harness_rule(char *name, unsigned int room, const char *father, int father_head,
                                  int father_body, const char *mother, int mother_head, int mother_body,
                                  int slot) {
    (void)name; (void)room; (void)father_head; (void)father_body;
    (void)mother; (void)mother_head; (void)mother_body;
    ++g_rule_calls;
    g_rule_slot = slot;
    lstrcpynA(g_rule_father, father ? father : "", sizeof g_rule_father);
    return 0;
}

#define HARNESS_LAST_NAMES ((HMODULE)(UINT_PTR)0x1234)

static HMODULE harness_module(LPCSTR name) {
    if (name != NULL && lstrcmpiA(name, "VVFP Last Names.dll") == 0) {
        return HARNESS_LAST_NAMES;
    }
    return GetModuleHandleA(name);
}

static FARPROC harness_proc(HMODULE module, LPCSTR name) {
    if (module == HARNESS_LAST_NAMES) {
        return lstrcmpA(name, "VvfpRuleLastName2") == 0 ? (FARPROC)harness_rule : NULL;
    }
    return GetProcAddress(module, name);
}

#define GetModuleHandleA harness_module
#define GetProcAddress harness_proc
#define main parentage_export_main_unused
#include "../parentage_export/parentage_export.c"
#undef main
#undef GetModuleHandleA
#undef GetProcAddress

static int failures;
static int checks;

static void check(int ok, const char *what) {
    ++checks;
    printf("  %s %s\n", ok ? "ok  " : "FAIL", what);
    failures += !ok;
}

/* A stand-in save manager whose slot field says `slot`. */
static unsigned char g_manager[0x40000];

static void game_slot(int game, int slot) {
    memset(g_manager, 0, sizeof g_manager);
    *(int *)(g_manager + VV_GAME_SAVE_SLOT_FIELD[game]) = slot;
    harness_managers[game] = g_manager;
}

/* The child's record as the birth splice hands it: the parents the game copied onto it. */
static unsigned char g_record[0x20000];

static int born(int game) {
    const struct game_layout *g = layout_of(game);
    memset(g_record, 0, sizeof g_record);
    strcpy((char *)(g_record + g->name), "Oro Bahati");
    strcpy((char *)(g_record + g->parent_father_name), "Pio Bandele");
    strcpy((char *)(g_record + g->parent_mother_name), "Lomai Uzumati");
    *(int *)(g_record + g->parent_father_head) = 19;
    *(int *)(g_record + g->parent_father_body) = 8;
    *(int *)(g_record + g->parent_mother_head) = 8;
    *(int *)(g_record + g->parent_mother_body) = 28;
    g_rule_calls = 0;
    g_rule_slot = -1;
    rule_last_name(game, g_record);
    return g_rule_calls == 1 ? g_rule_slot : -1;
}

int main(void) {
    int game;
    char what[160];
    printf("last names slot harness\n");
    for (game = GAME_VV2; game <= GAME_VV5; ++game) {
        printf("game %d\n", game);
        /* Save 2 was saved this session: its header is the one published. */
        vv_village_publish("Village: Kalahuna Tribe 3: N (Save 2)\n");
        game_slot(game, 1);                         /* ...then Save 1 was loaded */
        _snprintf(what, sizeof what,
                  "Save 2 saved, Save 1 loaded: the catch-up's birth gets slot 1, not the published Save 2 (got %d)",
                  born(game));
        check(g_rule_slot == 1 && g_rule_calls == 1, what);
        check(strcmp(g_rule_father, "Pio Bandele") == 0, "with the father the record names");
        game_slot(game, 2);
        check(born(game) == 2, "the game saving to Save 2: slot 2");
        vv_village_publish("");                     /* nothing saved yet this session */
        game_slot(game, 3);
        check(born(game) == 3, "nothing published yet: the game's own slot");
        vv_village_publish("Village: Kalahuna Tribe 3: N (Save 2)\n");
        harness_managers[game] = NULL;              /* no save manager: no village known */
        check(born(game) == 0, "no save manager: 0 (the DLL finds the slot from the names), never the stale Save 2");
        game_slot(game, 22);                        /* a backup generation's number is no slot */
        check(born(game) == 0, "a slot field outside 1-5: 0, never the stale Save 2");
        game_slot(game, 4);
        check(last_names_slot(game_of_layout(layout_of(game))) == 4,
              "a change of looks (relook) asks the same: the game's slot");
        harness_managers[game] = NULL;
    }
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures ? 1 : 0;
}
