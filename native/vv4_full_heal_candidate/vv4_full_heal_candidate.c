/* Disabled VV4 Full Heal / Cure All candidate.
 *
 * This source is the ABI contract for the future emitted helper.  It is kept
 * separate from the certified Full Mastery DLL and is not catalog-visible.
 */
#include <windows.h>

typedef void (__cdecl *resolve_record_fn)(int index);
typedef int (__cdecl *read_record_fn)(void *record, int *health, int *sick,
                                      int *active, int *status);
typedef int (__thiscall *set_health_fn)(void *record, int reason, int value);
typedef int (__cdecl *deduct_fn)(int amount);

static const char kNoDeduction[] = "No tech points have been deducted.";

__declspec(dllexport) int __stdcall ShowVV4FullHealConfirmation(
    int predicted_sick, int predicted_partial) {
    char text[512];
    wsprintfA(text,
              "Full Heal / Cure All will cure %d sick villager(s) and restore "
              "partial health for %d villager(s) for 30,000 tech points?\r\n"
              "Press OK to confirm, or Cancel.",
              predicted_sick, predicted_partial);
    return MessageBoxA(NULL, text, "Villager Upgrades", MB_OKCANCEL);
}

__declspec(dllexport) int __stdcall ShowVV4FullHealResult(
    int actual_sick, int actual_partial, int status) {
    char text[512];
    if (status == 0) {
        wsprintfA(text,
                  "Full Heal / Cure All cured %d sick villager(s) and restored "
                  "partial health for %d villager(s).",
                  actual_sick, actual_partial);
    } else {
        wsprintfA(text,
                  "Full Heal / Cure All stopped after %d sickness clear(s) and "
                  "%d partial-health restore(s).\r\n%s",
                  actual_sick, actual_partial, kNoDeduction);
    }
    MessageBoxA(NULL, text, "Villager Upgrades", MB_OK);
    return status;
}

/* The executable helper must use these exact operations after the independent
 * VV4 disassembly gate is recorded.  This declaration intentionally avoids a
 * compiler-generated implementation until the native code/layout audit is
 * complete; no raw skill or sickness stores are permitted here. */
__declspec(dllexport) int __stdcall VV4FullHealContractMarker(void) {
    return 150;
}
