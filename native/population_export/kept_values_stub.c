/* Stand-ins, for population_export_harness.c only (never shipped), of the companions whose values the rosters print
   for a villager (population_export.c write_kept_values): built three times by
   scripts/build_population_export_harness.ps1, each under the name of the companion it stands in for --

     KEPT_GP     "VVFP Gender Presentation.dll"  VvfpBornFemale, VvfpGenderPresentationGet
     KEPT_HL     "VVFP Head Look.dll"            VvfpHeadLookGet
     KEPT_STORY  "VVFP Story Upgrades.dll"       VvfpStoryTraitsOf

   Each answers by the villager's name (the harness's villagers): Kiwi was born female, is drawn with the other sex's
   look, has the Old head look and the story trait mute; Budi has the Young head look; everyone else nothing. */
#include <windows.h>
#include <string.h>

static const unsigned int NAME_AT[6] = { 0, 0x370u, 0x564u, 0xDD4u, 0x1B9Cu, 0x1B9Cu };

static int named(int game, const void *record, const char *name) {
    return game >= 1 && game <= 5 && record != NULL
           && strcmp((const char *)record + NAME_AT[game], name) == 0;
}

/* Undecorated names, as the companions' own .def files export them. */
#ifdef KEPT_GP
#pragma comment(linker, "/EXPORT:VvfpBornFemale=_VvfpBornFemale@8")
#pragma comment(linker, "/EXPORT:VvfpGenderPresentationGet=_VvfpGenderPresentationGet@8")
int __stdcall VvfpBornFemale(int game, const void *record) {
    return named(game, record, "Kiwi");
}

int __stdcall VvfpGenderPresentationGet(int game, const void *record) {
    return named(game, record, "Kiwi");
}
#endif

#ifdef KEPT_HL
#pragma comment(linker, "/EXPORT:VvfpHeadLookGet=_VvfpHeadLookGet@8")
int __stdcall VvfpHeadLookGet(int game, const void *record) {
    return named(game, record, "Kiwi") ? 2 : named(game, record, "Budi") ? 1 : 0;
}
#endif

#ifdef KEPT_STORY
#pragma comment(linker, "/EXPORT:VvfpStoryTraitsOf=_VvfpStoryTraitsOf@8")
int __stdcall VvfpStoryTraitsOf(int game, const void *record) {
    return named(game, record, "Kiwi") ? 1 : 0;
}
#endif

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance;
    (void)reason;
    (void)reserved;
    return TRUE;
}
