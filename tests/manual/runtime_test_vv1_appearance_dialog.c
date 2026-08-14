/* Real runtime test of the compiled Change Appearance dialog: loads the
   actual shipped DLL, calls the actual exported function on a background
   thread (it blocks on the real DialogBoxParamA message loop, exactly as
   it will when called from the game), finds the real live window from the
   main thread, and drives it with real BM_CLICK messages to the real
   button controls. The head/body previews are owner-draw (real sprite art
   cropped from the stock game, not text), so correctness is read directly
   from the synthetic villager buffer this program owns rather than from
   dialog text; each preview control's presence is still confirmed so a
   dialog-template regression (missing/misnumbered control) would be
   caught. Built and run as a native 32-bit exe against the real 32-bit
   DLL -- no architecture mismatch, no mocking. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>

typedef int (__stdcall *PickerFn)(int);

#define ID_HEAD_LABEL 2000
#define ID_HEAD_PREV  2001
#define ID_HEAD_NEXT  2002
#define ID_BODY_LABEL 2010
#define ID_BODY_PREV  2011
#define ID_BODY_NEXT  2012
#define IDOK_ 1
#define IDCANCEL_ 2

#define VV_GENDER_OFFSET 0x350
#define VV_HEAD_OFFSET   0x360
#define VV_CLOTHING_OFFSET 0x364
#define BUF_SIZE 0x400

static int g_failures = 0;

#define CHECK(cond, msg, ...) do { \
    if (!(cond)) { \
        printf("  FAIL: " msg "\n", ##__VA_ARGS__); \
        g_failures++; \
    } else { \
        printf("  ok:   " msg "\n", ##__VA_ARGS__); \
    } \
} while (0)

static PickerFn g_picker;
static int g_villager_ptr;
static int g_result;

DWORD WINAPI call_picker_thread(LPVOID param) {
    (void)param;
    g_result = g_picker(g_villager_ptr);
    return 0;
}

static HWND find_dialog(void) {
    for (int i = 0; i < 150; ++i) {
        HWND h = FindWindowA(NULL, "Change Appearance");
        if (h) return h;
        Sleep(20);
    }
    return NULL;
}

static void check_control_exists(HWND dlg, int id, const char *name) {
    HWND child = GetDlgItem(dlg, id);
    CHECK(child != NULL, "%s control (id %d) exists", name, id);
}

static void click(HWND dlg, int id) {
    HWND child = GetDlgItem(dlg, id);
    if (!child) { printf("  FAIL: control %d not found\n", id); g_failures++; return; }
    SendMessageA(child, BM_CLICK, 0, 0);
}

static int read_i32(unsigned char *buf, int offset) {
    int v;
    memcpy(&v, buf + offset, 4);
    return v;
}

static void write_i32(unsigned char *buf, int offset, int value) {
    memcpy(buf + offset, &value, 4);
}

static void run_scenario(HMODULE dll, int gender, int start_head, int start_body, int expected_count, const char *label) {
    printf("\n=== %s: gender=%d start_head=%d start_body=%d expected_count=%d ===\n",
        label, gender, start_head, start_body, expected_count);

    unsigned char buf[BUF_SIZE];
    memset(buf, 0, sizeof(buf));
    write_i32(buf, VV_GENDER_OFFSET, gender);
    write_i32(buf, VV_HEAD_OFFSET, start_head);
    write_i32(buf, VV_CLOTHING_OFFSET, start_body);

    g_picker = (PickerFn)GetProcAddress(dll, "ShowOriginsAppearancePicker");
    if (!g_picker) { printf("  FAIL: export not found\n"); g_failures++; return; }
    g_villager_ptr = (int)(intptr_t)buf;
    g_result = -999;

    HANDLE thread = CreateThread(NULL, 0, call_picker_thread, NULL, 0, NULL);
    HWND dlg = find_dialog();
    CHECK(dlg != NULL, "dialog window appeared");
    if (!dlg) { WaitForSingleObject(thread, 3000); CloseHandle(thread); return; }

    check_control_exists(dlg, ID_HEAD_LABEL, "head preview");
    check_control_exists(dlg, ID_BODY_LABEL, "body preview");

    for (int i = 0; i < expected_count + 2; ++i) {
        click(dlg, ID_HEAD_NEXT);
    }
    int field = read_i32(buf, VV_HEAD_OFFSET);
    int expected_value = (start_head + expected_count + 2) % expected_count;
    CHECK(field == expected_value, "head field after %d clicks wrapped correctly: %d (expected %d)", expected_count + 2, field, expected_value);

    click(dlg, ID_BODY_PREV);
    field = read_i32(buf, VV_CLOTHING_OFFSET);
    expected_value = (start_body - 1 + expected_count) % expected_count;
    CHECK(field == expected_value, "body field after one prev-click: %d (expected %d)", field, expected_value);

    click(dlg, IDCANCEL_);
    WaitForSingleObject(thread, 3000);
    CloseHandle(thread);
    CHECK(g_result == 0, "Cancel returned 0 (got %d)", g_result);
    int head_after = read_i32(buf, VV_HEAD_OFFSET);
    int body_after = read_i32(buf, VV_CLOTHING_OFFSET);
    CHECK(head_after == start_head, "Cancel reverted head to original %d (got %d)", start_head, head_after);
    CHECK(body_after == start_body, "Cancel reverted body to original %d (got %d)", start_body, body_after);
}

static void run_ok_scenario(HMODULE dll) {
    printf("\n=== OK scenario: change then confirm, values must stick ===\n");
    unsigned char buf[BUF_SIZE];
    memset(buf, 0, sizeof(buf));
    write_i32(buf, VV_GENDER_OFFSET, 2);
    write_i32(buf, VV_HEAD_OFFSET, 0);
    write_i32(buf, VV_CLOTHING_OFFSET, 0);

    g_picker = (PickerFn)GetProcAddress(dll, "ShowOriginsAppearancePicker");
    g_villager_ptr = (int)(intptr_t)buf;
    g_result = -999;

    HANDLE thread = CreateThread(NULL, 0, call_picker_thread, NULL, 0, NULL);
    HWND dlg = find_dialog();
    CHECK(dlg != NULL, "dialog window appeared");
    if (!dlg) { WaitForSingleObject(thread, 3000); CloseHandle(thread); return; }

    click(dlg, ID_HEAD_NEXT);
    click(dlg, ID_HEAD_NEXT);
    click(dlg, ID_BODY_NEXT);
    click(dlg, IDOK_);
    WaitForSingleObject(thread, 3000);
    CloseHandle(thread);

    CHECK(g_result == 1, "OK returned 1 (got %d)", g_result);
    int head_after = read_i32(buf, VV_HEAD_OFFSET);
    int body_after = read_i32(buf, VV_CLOTHING_OFFSET);
    CHECK(head_after == 2, "OK kept tentative head value 2 (got %d)", head_after);
    CHECK(body_after == 1, "OK kept tentative body value 1 (got %d)", body_after);
}

int main(int argc, char **argv) {
    /* Defaults to the checkout-relative path, assuming this exe is run
       from the repository root; pass an explicit path as argv[1] to
       override (e.g. when running from a build output directory). */
    const char *path = argc > 1 ? argv[1] : "assets\\origins\\VVFP VV1 Origins Icons.dll";
    HMODULE dll = LoadLibraryA(path);
    if (!dll) {
        printf("FAIL: could not load DLL, GetLastError=%lu\n", GetLastError());
        return 1;
    }
    printf("DLL loaded OK: %s\n", path);

    run_scenario(dll, 1, 5, 3, 19, "male villager");
    run_scenario(dll, 2, 5, 3, 20, "non-male villager");
    run_ok_scenario(dll);

    printf("\n=====================================\n");
    if (g_failures == 0) {
        printf("ALL RUNTIME SCENARIOS PASSED\n");
    } else {
        printf("%d CHECK(S) FAILED\n", g_failures);
    }
    return g_failures == 0 ? 0 : 1;
}
