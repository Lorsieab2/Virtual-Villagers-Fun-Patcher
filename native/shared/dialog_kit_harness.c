/* The dialog kit harness (scripts/build_dialog_kit_harness.ps1).

   Real Windows dialogs, hidden: every dialog template of each companion DLL
   named on the command line (loaded as a resource file only -- no code of
   it runs) is created with a dialog procedure that does what every
   companion dialog procedure does first: vk_dialog_hook()
   (native/shared/vvfp_dialog_kit.h).  For each one:

   * the window has a sizing frame and minimise and maximise boxes;
   * its smallest size is the template's own size;
   * at the template's size nothing moves; made half as large again, and
     made as large as the screen's work area (a maximised window), every
     shown control is inside the window, no two shown controls that did
     not overlap overlap, lists and text grow, and back at the template's
     size every control is where it was.

   Then the kit's wrapping lists and villager sorting on real controls:
   a long entry gets more than one line's height, and sorting a list and a
   drop-down by age and by name (numbered names in numeral order, ties by
   name) keeps the chosen entries chosen and leaves the other entries where
   they were.

   Prints one line per check that fails and "dialogs N, failures F"; exits
   with F. */
#include <windows.h>
#include <stdio.h>
#include <string.h>

#include "vvfp_dialog_kit.h"

static int failures;
static int dialogs;

static void fail(const char *dll, int id, const char *what) {
    printf("FAIL %s dialog %d: %s\n", dll, id, what);
    ++failures;
}

static INT_PTR CALLBACK harness_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    INT_PTR handled;
    if (vk_dialog_hook(window, message, wparam, lparam, &handled)) {
        return handled;
    }
    return message == WM_INITDIALOG;
}

#define MAX_CHILDREN 400

typedef struct {
    HWND window;
    RECT rect;
    int shown;
    unsigned int flags;
} child_rect;

static int take_children(HWND dialog, child_rect *out) {
    HWND child;
    int n = 0;
    for (child = GetWindow(dialog, GW_CHILD); child != NULL && n < MAX_CHILDREN;
         child = GetWindow(child, GW_HWNDNEXT)) {
        RECT r;
        GetWindowRect(child, &r);
        MapWindowPoints(NULL, dialog, (POINT *)&r, 2);
        out[n].window = child;
        out[n].rect = r;
        out[n].shown = (GetWindowLongA(child, GWL_STYLE) & WS_VISIBLE) != 0;
        out[n].flags = vk_classify(dialog, child, &r);
        ++n;
    }
    return n;
}

static int overlaps(const RECT *a, const RECT *b) {
    return a->left < b->right && b->left < a->right && a->top < b->bottom && b->top < a->bottom;
}

static int is_group_box(HWND w) {
    char cls[16];
    return GetClassNameA(w, cls, sizeof cls) && lstrcmpiA(cls, "Button") == 0
           && (GetWindowLongA(w, GWL_STYLE) & BS_TYPEMASK) == BS_GROUPBOX;
}

static void resize_to(HWND dialog, int width, int height) {
    SetWindowPos(dialog, NULL, 0, 0, width, height, SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
}

static void check_layout(const char *dll, int id, HWND dialog, const child_rect *before, int n,
                         const char *label) {
    child_rect now[MAX_CHILDREN];
    RECT client;
    int m = take_children(dialog, now);
    int i;
    int j;
    char what[256];
    GetClientRect(dialog, &client);
    if (m != n) {
        sprintf(what, "%s: %d controls, %d before", label, m, n);
        fail(dll, id, what);
        return;
    }
    for (i = 0; i < n; ++i) {
        if (!now[i].shown) {
            continue;
        }
        if (now[i].rect.left < 0 || now[i].rect.top < 0 || now[i].rect.right > client.right
            || now[i].rect.bottom > client.bottom) {
            sprintf(what, "%s: control %d (%ld,%ld,%ld,%ld) outside the window (%ld x %ld)", label,
                    GetDlgCtrlID(now[i].window), now[i].rect.left, now[i].rect.top, now[i].rect.right,
                    now[i].rect.bottom, client.right, client.bottom);
            fail(dll, id, what);
        }
        for (j = i + 1; j < n; ++j) {
            if (!now[j].shown || is_group_box(now[i].window) || is_group_box(now[j].window)) {
                continue;
            }
            if (!overlaps(&before[i].rect, &before[j].rect) && overlaps(&now[i].rect, &now[j].rect)) {
                sprintf(what, "%s: controls %d and %d overlap", label, GetDlgCtrlID(now[i].window),
                        GetDlgCtrlID(now[j].window));
                fail(dll, id, what);
            }
        }
    }
}

static void check_dialog(HMODULE module, const char *dll, int id) {
    HWND dialog = CreateDialogParamA(module, MAKEINTRESOURCEA(id), NULL, harness_dialog, 0);
    child_rect before[MAX_CHILDREN];
    child_rect grown[MAX_CHILDREN];
    child_rect back[MAX_CHILDREN];
    MINMAXINFO info;
    RECT window;
    RECT work;
    int n;
    int i;
    int w;
    int h;
    char what[200];
    if (dialog == NULL) {
        sprintf(what, "not created (error %lu)", GetLastError());
        fail(dll, id, what);
        return;
    }
    ++dialogs;
    if ((GetWindowLongA(dialog, GWL_STYLE) & VK_STYLES) != VK_STYLES) {
        fail(dll, id, "no sizing frame / minimise / maximise box");
    }
    if (!(GetWindowLongA(dialog, GWL_EXSTYLE) & WS_EX_APPWINDOW)) {
        fail(dll, id, "no taskbar button: a minimised dialog could not be found again");
    }
    GetWindowRect(dialog, &window);
    w = window.right - window.left;
    h = window.bottom - window.top;
    memset(&info, 0, sizeof info);
    SendMessageA(dialog, WM_GETMINMAXINFO, 0, (LPARAM)&info);
    if (info.ptMinTrackSize.x != w || info.ptMinTrackSize.y != h) {
        sprintf(what, "smallest size %ld x %ld, template %d x %d", info.ptMinTrackSize.x,
                info.ptMinTrackSize.y, w, h);
        fail(dll, id, what);
    }
    n = take_children(dialog, before);
    resize_to(dialog, w, h);
    check_layout(dll, id, dialog, before, n, "template size");

    resize_to(dialog, w * 3 / 2, h * 3 / 2);
    check_layout(dll, id, dialog, before, n, "one and a half times");
    take_children(dialog, grown);
    for (i = 0; i < n; ++i) {
        if ((before[i].flags & VK_X)
            && grown[i].rect.right - grown[i].rect.left <= before[i].rect.right - before[i].rect.left) {
            sprintf(what, "control %d did not widen", GetDlgCtrlID(before[i].window));
            fail(dll, id, what);
        }
        if ((before[i].flags & VK_Y) && !(before[i].flags & VK_COMBO)
            && grown[i].rect.bottom - grown[i].rect.top <= before[i].rect.bottom - before[i].rect.top) {
            sprintf(what, "control %d did not grow taller", GetDlgCtrlID(before[i].window));
            fail(dll, id, what);
        }
    }

    SystemParametersInfoA(SPI_GETWORKAREA, 0, &work, 0);
    resize_to(dialog, work.right - work.left > w ? work.right - work.left : w,
              work.bottom - work.top > h ? work.bottom - work.top : h);
    check_layout(dll, id, dialog, before, n, "maximised");

    resize_to(dialog, w, h);
    take_children(dialog, back);
    for (i = 0; i < n; ++i) {
        const RECT *a = &before[i].rect;
        const RECT *b = &back[i].rect;
        if (abs(a->left - b->left) > 1 || abs(a->top - b->top) > 1 || abs(a->right - b->right) > 1
            || (abs(a->bottom - b->bottom) > 1 && !(before[i].flags & VK_COMBO))) {
            sprintf(what, "control %d not back in place at the template's size", GetDlgCtrlID(before[i].window));
            fail(dll, id, what);
        }
    }
    DestroyWindow(dialog);
}

static int ids[256];
static int id_count;

static BOOL CALLBACK collect(HMODULE module, LPCSTR type, LPSTR name, LONG_PTR param) {
    (void)module;
    (void)type;
    (void)param;
    if (IS_INTRESOURCE(name) && id_count < 256) {
        ids[id_count++] = (int)(ULONG_PTR)name;
    }
    return TRUE;
}

/* ---- the wrapping list and the villager sort on real controls ----------- */

static const char *const NAMES[] = {
    "Kenobi III", "kenobi II", "Anna Zed", "anna Young", "Kenobi X", "Kenobi IV", "Bo 10", "Bo 2"
};
static const int AGES[] = { 300, 900, 900, 100, 50, 900, 20, 20 };

static int about(void *context, LPARAM data, vk_villager *out) {
    (void)context;
    if (data < 0 || data >= 8) {
        return 0;
    }
    out->name = NAMES[data];
    out->age = AGES[data];
    out->rank = (int)data;
    return 1;
}

static void expect_order(HWND control, int combo, const int *want, int n, const char *label) {
    int i;
    char what[200];
    for (i = 0; i < n; ++i) {
        LPARAM data = (LPARAM)SendMessageA(control, combo ? CB_GETITEMDATA : LB_GETITEMDATA, (WPARAM)i, 0);
        if ((int)data != want[i]) {
            sprintf(what, "%s: entry %d is %d, want %d", label, i, (int)data, want[i]);
            fail("kit", 0, what);
            return;
        }
    }
}

static int selected_data(HWND list, int *out) {
    int n = (int)SendMessageA(list, LB_GETCOUNT, 0, 0);
    int i;
    int k = 0;
    for (i = 0; i < n; ++i) {
        if (SendMessageA(list, LB_GETSEL, (WPARAM)i, 0) > 0) {
            out[k++] = (int)SendMessageA(list, LB_GETITEMDATA, (WPARAM)i, 0);
        }
    }
    return k;
}

static void check_sorting(void) {
    HWND host = CreateWindowExA(0, "STATIC", "", WS_POPUP, 0, 0, 400, 400, NULL, NULL, NULL, NULL);
    HWND list = CreateWindowExA(0, "LISTBOX", "", WS_CHILD | LBS_EXTENDEDSEL | LBS_NOTIFY, 0, 0, 200, 300, host,
                                (HMENU)1, NULL, NULL);
    HWND combo = CreateWindowExA(0, "COMBOBOX", "", WS_CHILD | CBS_DROPDOWNLIST, 0, 0, 200, 300, host,
                                 (HMENU)2, NULL, NULL);
    /* by name: Anna Young / Anna Zed, Bo 2 < Bo 10, Kenobi II < III < IV < X */
    static const int by_name[] = { 3, 2, 7, 6, 1, 0, 5, 4 };
    /* oldest first, ties by name: 900 Anna Zed, kenobi II, Kenobi IV; 300; 100; 50; 20 Bo 2, Bo 10 */
    static const int by_age[] = { 2, 1, 5, 0, 3, 4, 7, 6 };
    static const int game[] = { 0, 1, 2, 3, 4, 5, 6, 7 };
    int combo_name[9];
    int chosen[8];
    int k;
    int i;
    for (i = 0; i < 8; ++i) {
        int at = (int)SendMessageA(list, LB_ADDSTRING, 0, (LPARAM)NAMES[i]);
        SendMessageA(list, LB_SETITEMDATA, (WPARAM)at, i);
    }
    SendMessageA(list, LB_SETSEL, TRUE, 1);              /* kenobi II */
    SendMessageA(list, LB_SETSEL, TRUE, 6);              /* Bo 10 */
    vk_sort_control(list, 0, VK_SORT_NAME, about, NULL);
    expect_order(list, 0, by_name, 8, "list by name");
    k = selected_data(list, chosen);
    if (k != 2 || !((chosen[0] == 6 && chosen[1] == 1) || (chosen[0] == 1 && chosen[1] == 6))) {
        fail("kit", 0, "list by name: the chosen villagers changed");
    }
    vk_sort_control(list, 0, VK_SORT_AGE, about, NULL);
    expect_order(list, 0, by_age, 8, "list by age");
    k = selected_data(list, chosen);
    if (k != 2 || !((chosen[0] == 1 && chosen[1] == 6) || (chosen[0] == 6 && chosen[1] == 1))) {
        fail("kit", 0, "list by age: the chosen villagers changed");
    }
    vk_sort_control(list, 0, VK_SORT_GAME, about, NULL);
    expect_order(list, 0, game, 8, "list back in the game's order");

    /* a drop-down with a first entry that is not a villager: it stays first */
    k = (int)SendMessageA(combo, CB_ADDSTRING, 0, (LPARAM)"Random (original game)");
    SendMessageA(combo, CB_SETITEMDATA, (WPARAM)k, -1);
    for (i = 0; i < 8; ++i) {
        int at = (int)SendMessageA(combo, CB_ADDSTRING, 0, (LPARAM)NAMES[i]);
        SendMessageA(combo, CB_SETITEMDATA, (WPARAM)at, i);
    }
    SendMessageA(combo, CB_SETCURSEL, 5, 0);             /* Kenobi IV (data 4) */
    vk_sort_control(combo, 1, VK_SORT_NAME, about, NULL);
    combo_name[0] = -1;
    for (i = 0; i < 8; ++i) {
        combo_name[i + 1] = by_name[i];
    }
    expect_order(combo, 1, combo_name, 9, "drop-down by name");
    k = (int)SendMessageA(combo, CB_GETCURSEL, 0, 0);
    if ((int)SendMessageA(combo, CB_GETITEMDATA, (WPARAM)k, 0) != 4) {
        fail("kit", 0, "drop-down by name: the chosen villager changed");
    }
    DestroyWindow(host);
}

static void check_wrapping(HMODULE module, const char *dll) {
    HWND dialog = CreateDialogParamA(module, MAKEINTRESOURCEA(301), NULL, harness_dialog, 0);
    HWND list;
    int one;
    int long_one;
    static const char LONG_TEXT[] =
        "Takes youth: villager slot 6 gets age value 1001 (stock writes record 6, NOT the ringer; or the "
        "villager chosen in 'The villager who rang it') and every other word of a long entry is shown";
    if (dialog == NULL) {
        return;                                         /* only the Story Upgrades have 301 */
    }
    list = GetDlgItem(dialog, 3001);
    if (list == NULL || !vk_is_wrap_list(list)) {
        fail(dll, 301, "the list on the left does not wrap its entries");
        DestroyWindow(dialog);
        return;
    }
    SendMessageA(list, LB_ADDSTRING, 0, (LPARAM)"Random (original game)");
    SendMessageA(list, LB_ADDSTRING, 0, (LPARAM)LONG_TEXT);
    one = (int)SendMessageA(list, LB_GETITEMHEIGHT, 0, 0);
    long_one = (int)SendMessageA(list, LB_GETITEMHEIGHT, 1, 0);
    if (!(long_one >= 2 * one - 4)) {
        char what[120];
        sprintf(what, "a long entry is not given more than one line (%d, one line %d)", long_one, one);
        fail(dll, 301, what);
    }
    resize_to(dialog, 3000, 1000);
    if ((int)SendMessageA(list, LB_GETITEMHEIGHT, 1, 0) >= long_one) {
        fail(dll, 301, "a long entry is not measured again when the list widens");
    }
    DestroyWindow(dialog);
}

int main(int argc, char **argv) {
    int a;
    int i;
    for (a = 1; a < argc; ++a) {
        HMODULE module = LoadLibraryExA(argv[a], NULL, LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE);
        if (module == NULL) {
            printf("FAIL %s: not loaded (error %lu)\n", argv[a], GetLastError());
            ++failures;
            continue;
        }
        id_count = 0;
        EnumResourceNamesA(module, (LPCSTR)RT_DIALOG, collect, 0);
        for (i = 0; i < id_count; ++i) {
            check_dialog(module, argv[a], ids[i]);
        }
        printf("%s: %d dialogs\n", argv[a], id_count);
        check_wrapping(module, argv[a]);
        FreeLibrary(module);
    }
    check_sorting();
    printf("dialogs %d, failures %d\n", dialogs, failures);
    return failures;
}
