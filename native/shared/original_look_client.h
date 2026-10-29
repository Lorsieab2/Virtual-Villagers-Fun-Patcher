/* original_look_client.h -- how the Change Appearance windows ask "VVFP Original Look.dll" for a villager's
   original head, body and mask (the look the villager was born or arrived with), for "Reset to original".

   The DLL itself is another feature (native/shared/original_look.h, feat/original-look); this header only
   declares its one export, resolved with GetModuleHandleA / GetProcAddress, so a window built without it
   still works: when the DLL is not in the game, or it does not know the villager, the window says
   "Original look not known" and changes nothing.  At the merge this header gives way to original_look.h.

       int __stdcall VvfpOriginalLookGet(int game, const void *record, int *head, int *body, int *mask);

   1 with the three values when that villager's original look is known; 0 otherwise. */
#ifndef VVFP_ORIGINAL_LOOK_CLIENT_H
#define VVFP_ORIGINAL_LOOK_CLIENT_H

#define VVFP_ORIGINAL_LOOK_DLL "VVFP Original Look.dll"
#define VVFP_ORIGINAL_LOOK_GET "VvfpOriginalLookGet"

#ifndef RC_INVOKED
typedef int (__stdcall *vvfp_original_look_get_fn)(int game, const void *record, int *head, int *body, int *mask);

/* The villager's original head, body and mask: 1 when known (the three set), 0 when the DLL is not in the
   game or does not know this villager (nothing set). */
static int vvfp_original_look(int game, const void *record, int *head, int *body, int *mask) {
    HMODULE dll = GetModuleHandleA(VVFP_ORIGINAL_LOOK_DLL);
    vvfp_original_look_get_fn get;
    int h = 0, b = 0, m = 0;
    if (dll == NULL || record == NULL) {
        return 0;
    }
    get = (vvfp_original_look_get_fn)GetProcAddress(dll, VVFP_ORIGINAL_LOOK_GET);
    if (get == NULL || !get(game, record, &h, &b, &m)) {
        return 0;
    }
    *head = h;
    *body = b;
    *mask = m;
    return 1;
}
#endif

#define VVFP_ORIGINAL_LOOK_UNKNOWN "Original look not known"

#endif /* VVFP_ORIGINAL_LOOK_CLIENT_H */
