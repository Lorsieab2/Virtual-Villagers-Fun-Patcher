/* A stand-in "VVFP VV1 Parentage.dll" for population_export_harness.c only.
   Never shipped: scripts\build_population_export_harness.ps1 builds it into
   the harness's own scratch folder, under "Virtual Villagers Fun Patcher
   Files\", where the population exporter looks for the real companion.

   It answers the three queries the exporter makes, from fixed data the
   harness plants a matching village for:

     record 0  a founder: no parents, carrying nobody
     record 1  a child: father Goro (7, 2), mother Aisha (4, 9)
     record 2  carrying: expected father Papago, head 7, body 0
     record 3  NOT carrying, yet answered "Papago" too -- the exporter's own
               pregnancy gate must keep him out of her block
     record 4  carrying, with no recorded father: an empty name

   Usage: compiled /LD with vv1_parentage_stub.def. */
#include <windows.h>

__declspec(dllexport) int __stdcall Vv1ParentageQuery(int index, int *out) {
    if (out == NULL || index < 0 || index >= 256) {
        return 0;
    }
    out[0] = out[1] = out[2] = out[3] = -1;
    if (index == 1) {
        out[0] = 7; out[1] = 2; out[2] = 4; out[3] = 9;
    }
    return 1;
}

__declspec(dllexport) int __stdcall Vv1ParentageQueryNames(int index, char *father, char *mother,
                                                           int capacity) {
    if (father == NULL || mother == NULL || capacity < 1 || index < 0 || index >= 256) {
        return 0;
    }
    father[0] = '\0';
    mother[0] = '\0';
    if (index == 1) {
        lstrcpynA(father, "Goro", capacity);
        lstrcpynA(mother, "Aisha", capacity);
    }
    return 1;
}

__declspec(dllexport) int __stdcall Vv1ParentageQueryExpectedFather(int index, int *out, char *name,
                                                                    int capacity) {
    if (out == NULL || name == NULL || capacity < 1 || index < 0 || index >= 256) {
        return 0;
    }
    out[0] = out[1] = -1;
    name[0] = '\0';
    if (index == 2 || index == 3) {
        lstrcpynA(name, "Papago", capacity);
        out[0] = 7;
        out[1] = 0;
    }
    return 1;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance; (void)reason; (void)reserved;
    return TRUE;
}
