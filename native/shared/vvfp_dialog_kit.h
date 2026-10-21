/* The companions' own dialogs: resizable windows, lists whose long entries
   wrap, and the villager sort orders.  Header-only; include after
   <windows.h>.

   The owner (v1.35.80): "make sure all these windows are expandable
   (max/minimizable)".  Every dialog a companion creates calls
   vk_dialog_hook() first in its dialog procedure:

     INT_PTR handled;
     if (vk_dialog_hook(window, message, wparam, lparam, &handled)) {
         return handled;
     }

   and its template carries WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
   (VK_STYLES; vk_dialog_hook adds them itself to a template that lacks
   them).  Then:

   * The smallest size is the template's own (WM_GETMINMAXINFO), where
     everything was laid out to fit.
   * Resizing (or maximising) moves every control into the same share of
     the larger window: a control's "slot" is its rectangle scaled by the
     window's growth.  Lists, multi-line text, group boxes, combo boxes and
     wide edit boxes fill their slot (text wraps wider, lists show more);
     buttons, check boxes, icons, art and small number boxes keep their size
     and sit in the middle of their slot.  Slots of controls that did not
     overlap never overlap, so nothing covers anything else.
   * Minimise minimises the dialog alone, to a taskbar button of its own
     (WS_EX_APPWINDOW): the game behind it, disabled while the dialog is
     open, is never minimised (VV1 / VV2 note that restoring an SDL game
     from a real minimise while it holds exclusive fullscreen is hazardous,
     native/vv1_origins_icons), and the dialog comes back from the taskbar
     or Alt+Tab.

   The positions are taken the first time the window is resized, so the
   controls a dialog adds or moves while it opens are included.

   Lists with LBS_OWNERDRAWVARIABLE | LBS_HASSTRINGS are "wrapping lists":
   every entry is drawn in full, on as many lines as it needs, and is
   measured again when the list is resized.  An entry whose item data is
   VK_LB_HEADER is a group heading (drawn as a band; never chosen).

   Villager sort orders (the owner, v1.35.80): the game's own order, "Age
   (oldest at top)" and "Alphabetical (first name, then last name)".
   vk_name_compare compares names word by word, case-insensitively, with
   numbered names in numeral order (Kenobi I, II, III ... and 2 < 10). */

#ifndef VVFP_DIALOG_KIT_H
#define VVFP_DIALOG_KIT_H

#ifdef _MSC_VER
#pragma warning(disable : 4505)   /* a companion uses only part of the kit */
#pragma comment(lib, "gdi32.lib")  /* the wrapping lists draw their own entries */
#endif

#define VK_PROP "VvfpDialogKit"
#define VK_MAX_ITEMS 320
#define VK_STYLES (WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)

#define VK_FIX 0u
#define VK_X 1u            /* fills its slot across */
#define VK_Y 2u            /* fills its slot down */
#define VK_WRAP 4u         /* a wrapping list */
#define VK_COMBO 8u        /* a combo box: its dropped height is kept */

#define VK_LB_HEADER (-100)

#define VK_SORT_GAME 0
#define VK_SORT_AGE 1
#define VK_SORT_NAME 2

typedef struct {
    HWND window;
    RECT rect;             /* client coordinates of the dialog, as captured */
    unsigned int flags;
    int drop;              /* a combo box's dropped height */
} vk_item;

typedef struct {
    int w0, h0;            /* the client size the template made */
    int min_w, min_h;      /* the window size the template made */
    int captured;
    int count;
    vk_item items[VK_MAX_ITEMS];
} vk_state;

/* ---- Layout (pure) ------------------------------------------------------ */

static int vk_scale(int value, int num, int den) {
    long long v;
    if (den <= 0) {
        return value;
    }
    v = (long long)value * num;
    return (int)(v >= 0 ? (v + den / 2) / den : -((-v + den / 2) / den));
}

/* Where a control captured at `r` goes when the client grows from w0 x h0
   to w x h: its slot is `r` scaled; VK_X / VK_Y fill the slot that way,
   otherwise the control keeps its size in the middle of the slot. */
static void vk_place(const RECT *r, unsigned int flags, int w0, int h0, int w, int h, RECT *out) {
    int L = vk_scale(r->left, w, w0);
    int R = vk_scale(r->right, w, w0);
    int T = vk_scale(r->top, h, h0);
    int B = vk_scale(r->bottom, h, h0);
    int cw = r->right - r->left;
    int ch = r->bottom - r->top;
    if (flags & VK_X) {
        out->left = L;
        out->right = R;
    } else {
        out->left = (L + R - cw) / 2;
        if (out->left < L) {
            out->left = L;
        }
        out->right = out->left + cw;
    }
    if (flags & VK_Y) {
        out->top = T;
        out->bottom = B;
    } else {
        out->top = (T + B - ch) / 2;
        if (out->top < T) {
            out->top = T;
        }
        out->bottom = out->top + ch;
    }
}

/* What kind of control `child` is for the layout. */
static unsigned int vk_classify(HWND dialog, HWND child, const RECT *r) {
    char cls[40];
    LONG style = GetWindowLongA(child, GWL_STYLE);
    RECT two_lines = { 0, 0, 4, 15 };
    RECT wide = { 0, 0, 80, 8 };
    MapDialogRect(dialog, &two_lines);
    MapDialogRect(dialog, &wide);
    if (!GetClassNameA(child, cls, sizeof cls)) {
        return VK_FIX;
    }
    if (lstrcmpiA(cls, "Button") == 0) {
        return (style & BS_TYPEMASK) == BS_GROUPBOX ? (VK_X | VK_Y) : VK_FIX;
    }
    if (lstrcmpiA(cls, "ListBox") == 0) {
        return VK_X | VK_Y
               | (((style & LBS_OWNERDRAWVARIABLE) && (style & LBS_HASSTRINGS)) ? VK_WRAP : 0u);
    }
    if (lstrcmpiA(cls, "SysListView32") == 0 || lstrcmpiA(cls, "SysTreeView32") == 0) {
        return VK_X | VK_Y;
    }
    if (lstrcmpiA(cls, "Edit") == 0) {
        if (style & ES_MULTILINE) {
            return VK_X | VK_Y;
        }
        return (r->right - r->left) >= wide.right ? VK_X : VK_FIX;
    }
    if (lstrcmpiA(cls, "ComboBox") == 0) {
        return VK_X | VK_COMBO;
    }
    if (lstrcmpiA(cls, "Static") == 0) {
        LONG type = style & SS_TYPEMASK;
        if (type == SS_LEFT || type == SS_CENTER || type == SS_RIGHT || type == SS_LEFTNOWORDWRAP
            || type == SS_SIMPLE) {
            return VK_X | ((r->bottom - r->top) > two_lines.bottom ? VK_Y : 0u);
        }
        return VK_FIX;      /* icons, bitmaps, owner-drawn art */
    }
    return VK_FIX;
}

/* ---- Wrapping lists ------------------------------------------------------ */

#define VK_PAD_X 4
#define VK_PAD_Y 2

static int vk_is_wrap_list(HWND list) {
    char cls[16];
    LONG style;
    if (list == NULL || !GetClassNameA(list, cls, sizeof cls) || lstrcmpiA(cls, "ListBox") != 0) {
        return 0;
    }
    style = GetWindowLongA(list, GWL_STYLE);
    return (style & LBS_OWNERDRAWVARIABLE) && (style & LBS_HASSTRINGS);
}

/* The height entry `text` needs in `list`: every word shown, wrapped. */
static int vk_wrap_height(HWND list, const char *text) {
    HDC dc = GetDC(list);
    HFONT font = (HFONT)SendMessageA(list, WM_GETFONT, 0, 0);
    HGDIOBJ old = NULL;
    RECT client;
    RECT r;
    int height;
    GetClientRect(list, &client);
    if (font != NULL) {
        old = SelectObject(dc, font);
    }
    r.left = 0;
    r.top = 0;
    /* the width with the scroll bar shown, so its arrival never rewraps */
    r.right = client.right - 2 * VK_PAD_X;
    {
        SCROLLBARINFO info;
        info.cbSize = sizeof info;
        if (!(GetScrollBarInfo(list, OBJID_VSCROLL, &info) && !(info.rgstate[0] & STATE_SYSTEM_INVISIBLE))) {
            r.right -= GetSystemMetrics(SM_CXVSCROLL);
        }
    }
    if (r.right < 40) {
        r.right = 40;
    }
    r.bottom = 0;
    DrawTextA(dc, text != NULL && text[0] ? text : " ", -1, &r,
              DT_CALCRECT | DT_WORDBREAK | DT_NOPREFIX | DT_EDITCONTROL);
    if (old != NULL) {
        SelectObject(dc, old);
    }
    ReleaseDC(list, dc);
    height = r.bottom + 2 * VK_PAD_Y;
    return height > 255 ? 255 : height;
}

/* Every entry of `list` measured again (its width changed). */
static void vk_wrap_remeasure(HWND list) {
    int n = (int)SendMessageA(list, LB_GETCOUNT, 0, 0);
    int i;
    char text[1200];
    for (i = 0; i < n; ++i) {
        int length = (int)SendMessageA(list, LB_GETTEXTLEN, (WPARAM)i, 0);
        if (length < 0 || length >= (int)sizeof text) {
            continue;
        }
        SendMessageA(list, LB_GETTEXT, (WPARAM)i, (LPARAM)text);
        SendMessageA(list, LB_SETITEMHEIGHT, (WPARAM)i, (LPARAM)vk_wrap_height(list, text));
    }
    InvalidateRect(list, NULL, TRUE);
}

static int vk_wrap_measure(HWND dialog, MEASUREITEMSTRUCT *m) {
    HWND list;
    char text[1200];
    int length;
    if (m->CtlType != ODT_LISTBOX) {
        return 0;
    }
    list = GetDlgItem(dialog, (int)m->CtlID);
    if (!vk_is_wrap_list(list)) {
        return 0;
    }
    /* the entry is in the list already when it is measured */
    text[0] = '\0';
    length = (int)SendMessageA(list, LB_GETTEXTLEN, (WPARAM)m->itemID, 0);
    if (length > 0 && length < (int)sizeof text) {
        SendMessageA(list, LB_GETTEXT, (WPARAM)m->itemID, (LPARAM)text);
    }
    m->itemHeight = (UINT)vk_wrap_height(list, text);
    return 1;
}

static int vk_wrap_draw(DRAWITEMSTRUCT *d) {
    char text[1200];
    int length;
    int header;
    int selected;
    COLORREF fore;
    COLORREF back;
    RECT r;
    if (d->CtlType != ODT_LISTBOX || !vk_is_wrap_list(d->hwndItem)) {
        return 0;
    }
    if (d->itemID == (UINT)-1) {
        if (d->itemState & ODS_FOCUS) {
            DrawFocusRect(d->hDC, &d->rcItem);
        }
        return 1;
    }
    text[0] = '\0';
    length = (int)SendMessageA(d->hwndItem, LB_GETTEXTLEN, d->itemID, 0);
    if (length >= 0 && length < (int)sizeof text) {
        SendMessageA(d->hwndItem, LB_GETTEXT, d->itemID, (LPARAM)text);
    }
    header = (int)d->itemData == VK_LB_HEADER;
    selected = (d->itemState & ODS_SELECTED) && !header;
    if (header) {
        back = GetSysColor(COLOR_BTNFACE);
        fore = GetSysColor(COLOR_BTNTEXT);
    } else if (selected) {
        back = GetSysColor(COLOR_HIGHLIGHT);
        fore = GetSysColor(COLOR_HIGHLIGHTTEXT);
    } else {
        back = GetSysColor(COLOR_WINDOW);
        fore = GetSysColor((d->itemState & ODS_DISABLED) ? COLOR_GRAYTEXT : COLOR_WINDOWTEXT);
    }
    SetBkColor(d->hDC, back);
    ExtTextOutA(d->hDC, 0, 0, ETO_OPAQUE, &d->rcItem, NULL, 0, NULL);
    SetTextColor(d->hDC, fore);
    SetBkMode(d->hDC, TRANSPARENT);
    r = d->rcItem;
    r.left += VK_PAD_X;
    r.right -= VK_PAD_X;
    r.top += VK_PAD_Y;
    DrawTextA(d->hDC, text, -1, &r, DT_WORDBREAK | DT_NOPREFIX | DT_EDITCONTROL);
    if ((d->itemState & ODS_FOCUS) && !header) {
        DrawFocusRect(d->hDC, &d->rcItem);
    }
    return 1;
}

/* ---- The dialog hook ------------------------------------------------------- */

static vk_state *vk_get(HWND dialog) {
    return (vk_state *)GetPropA(dialog, VK_PROP);
}

/* Takes every child's position and kind (the first resize). */
static void vk_capture(HWND dialog, vk_state *s) {
    HWND child;
    s->count = 0;
    for (child = GetWindow(dialog, GW_CHILD); child != NULL && s->count < VK_MAX_ITEMS;
         child = GetWindow(child, GW_HWNDNEXT)) {
        vk_item *it = &s->items[s->count];
        RECT r;
        GetWindowRect(child, &r);
        MapWindowPoints(NULL, dialog, (POINT *)&r, 2);
        it->window = child;
        it->rect = r;
        it->flags = vk_classify(dialog, child, &r);
        it->drop = r.bottom - r.top;
        if (it->flags & VK_COMBO) {
            RECT dropped;
            if (SendMessageA(child, CB_GETDROPPEDCONTROLRECT, 0, (LPARAM)&dropped)) {
                it->drop = dropped.bottom - dropped.top;
            }
        }
        ++s->count;
    }
    s->captured = 1;
}

static void vk_layout(HWND dialog, vk_state *s, int w, int h) {
    HDWP batch;
    int i;
    if (!s->captured) {
        vk_capture(dialog, s);
    }
    batch = BeginDeferWindowPos(s->count);
    for (i = 0; i < s->count; ++i) {
        const vk_item *it = &s->items[i];
        RECT r;
        int height;
        if (!IsWindow(it->window)) {
            continue;
        }
        vk_place(&it->rect, it->flags, s->w0, s->h0, w, h, &r);
        height = (it->flags & VK_COMBO) ? it->drop : r.bottom - r.top;
        if (batch != NULL) {
            batch = DeferWindowPos(batch, it->window, NULL, r.left, r.top, r.right - r.left, height,
                                   SWP_NOZORDER | SWP_NOACTIVATE);
        } else {
            SetWindowPos(it->window, NULL, r.left, r.top, r.right - r.left, height, SWP_NOZORDER | SWP_NOACTIVATE);
        }
    }
    if (batch != NULL) {
        EndDeferWindowPos(batch);
    }
    for (i = 0; i < s->count; ++i) {
        if ((s->items[i].flags & VK_WRAP) && IsWindow(s->items[i].window)) {
            vk_wrap_remeasure(s->items[i].window);
        }
    }
    InvalidateRect(dialog, NULL, TRUE);
}

/* Call first in a dialog procedure; nonzero = handled, *result the answer. */
static int vk_dialog_hook(HWND dialog, UINT message, WPARAM wparam, LPARAM lparam, INT_PTR *result) {
    vk_state *s;
    *result = 0;
    switch (message) {
    case WM_INITDIALOG: {
        RECT client;
        RECT window;
        LONG style = GetWindowLongA(dialog, GWL_STYLE);
        if ((style & VK_STYLES) != VK_STYLES) {
            /* a template without the frame: add it, the client size kept */
            RECT want;
            GetClientRect(dialog, &want);
            SetWindowLongA(dialog, GWL_STYLE, style | VK_STYLES);
            AdjustWindowRectEx(&want, style | VK_STYLES, FALSE, GetWindowLongA(dialog, GWL_EXSTYLE));
            SetWindowPos(dialog, NULL, 0, 0, want.right - want.left, want.bottom - want.top,
                         SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED);
        }
        /* a taskbar button of its own: a minimised dialog is always found */
        SetWindowLongA(dialog, GWL_EXSTYLE, GetWindowLongA(dialog, GWL_EXSTYLE) | WS_EX_APPWINDOW);
        s = (vk_state *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof *s);
        if (s == NULL) {
            return 0;
        }
        GetClientRect(dialog, &client);
        GetWindowRect(dialog, &window);
        s->w0 = client.right;
        s->h0 = client.bottom;
        s->min_w = window.right - window.left;
        s->min_h = window.bottom - window.top;
        if (!SetPropA(dialog, VK_PROP, s)) {
            HeapFree(GetProcessHeap(), 0, s);
        }
        return 0;                    /* the dialog's own WM_INITDIALOG runs */
    }
    case WM_GETMINMAXINFO:
        s = vk_get(dialog);
        if (s != NULL) {
            MINMAXINFO *m = (MINMAXINFO *)lparam;
            m->ptMinTrackSize.x = s->min_w;
            m->ptMinTrackSize.y = s->min_h;
            *result = 0;
            return 1;
        }
        return 0;
    case WM_SIZE:
        s = vk_get(dialog);
        if (s != NULL && wparam != SIZE_MINIMIZED) {
            int w = LOWORD(lparam);
            int h = HIWORD(lparam);
            if (s->captured || w != s->w0 || h != s->h0) {
                vk_layout(dialog, s, w, h);
            }
        }
        return 0;
    case WM_MEASUREITEM:
        if (vk_wrap_measure(dialog, (MEASUREITEMSTRUCT *)lparam)) {
            *result = TRUE;
            return 1;
        }
        return 0;
    case WM_DRAWITEM:
        if (vk_wrap_draw((DRAWITEMSTRUCT *)lparam)) {
            *result = TRUE;
            return 1;
        }
        return 0;
    case WM_NCDESTROY:
        s = (vk_state *)RemovePropA(dialog, VK_PROP);
        if (s != NULL) {
            HeapFree(GetProcessHeap(), 0, s);
        }
        return 0;
    default:
        return 0;
    }
}

/* ---- Villager sort orders (pure) ------------------------------------------ */

static int vk_fold(unsigned char c) {
    if (c >= 'A' && c <= 'Z') {
        return c + 32;
    }
    if (c >= 0xC0 && c <= 0xDE && c != 0xD7) {
        return c + 32;            /* Windows-1252 / Latin-1 capitals */
    }
    return c;
}

/* A word's numeral value: digits, or capital Roman numerals (I V X L C D
   M, written the usual way); 0 when it is not one. */
static int vk_numeral(const char *w, int n) {
    static const char *const letters = "IVXLCDM";
    static const int values[7] = { 1, 5, 10, 50, 100, 500, 1000 };
    int i;
    int total = 0;
    int digits = 1;
    if (n <= 0 || n > 15) {
        return 0;
    }
    for (i = 0; i < n; ++i) {
        if (w[i] < '0' || w[i] > '9') {
            digits = 0;
        }
    }
    if (digits) {
        for (i = 0; i < n && total < 100000000; ++i) {
            total = total * 10 + (w[i] - '0');
        }
        return total + 1;          /* 0 is a numeral too: values are shifted by one */
    }
    for (i = 0; i < n; ++i) {
        int k;
        int v = 0;
        int next = 0;
        for (k = 0; k < 7; ++k) {
            if (w[i] == letters[k]) {
                v = values[k];
            }
            if (i + 1 < n && w[i + 1] == letters[k]) {
                next = values[k];
            }
        }
        if (v == 0) {
            return 0;
        }
        if (i + 1 < n && next == 0) {
            return 0;
        }
        if (next > v) {
            /* only I before V / X, X before L / C, C before D / M */
            if (!((v == 1 && (next == 5 || next == 10)) || (v == 10 && (next == 50 || next == 100))
                  || (v == 100 && (next == 500 || next == 1000)))) {
                return 0;
            }
            total -= v;
        } else {
            total += v;
        }
    }
    return total > 0 ? total + 1 : 0;
}

static int vk_word_compare(const char *a, int na, const char *b, int nb) {
    int va = vk_numeral(a, na);
    int vb = vk_numeral(b, nb);
    int i;
    if (va && vb && va != vb) {
        return va < vb ? -1 : 1;
    }
    for (i = 0; i < na && i < nb; ++i) {
        int ca = vk_fold((unsigned char)a[i]);
        int cb = vk_fold((unsigned char)b[i]);
        if (ca != cb) {
            return ca < cb ? -1 : 1;
        }
    }
    return na == nb ? 0 : (na < nb ? -1 : 1);
}

/* Two names, first name then the rest, word by word. */
static int vk_name_compare(const char *a, const char *b) {
    for (;;) {
        int na = 0;
        int nb = 0;
        int c;
        while (*a == ' ') {
            ++a;
        }
        while (*b == ' ') {
            ++b;
        }
        if (*a == '\0' || *b == '\0') {
            return *a == *b ? 0 : (*a == '\0' ? -1 : 1);
        }
        while (a[na] != '\0' && a[na] != ' ') {
            ++na;
        }
        while (b[nb] != '\0' && b[nb] != ' ') {
            ++nb;
        }
        c = vk_word_compare(a, na, b, nb);
        if (c != 0) {
            return c;
        }
        a += na;
        b += nb;
    }
}

typedef struct {
    const char *name;
    int age;               /* the game's own age value */
    int rank;              /* the game's own order */
} vk_villager;

/* Villager x before y in sort order `mode`: <0, 0 or >0. */
static int vk_villager_compare(int mode, const vk_villager *x, const vk_villager *y) {
    int c;
    if (mode == VK_SORT_AGE && x->age != y->age) {
        return x->age > y->age ? -1 : 1;           /* oldest at the top */
    }
    if (mode == VK_SORT_AGE || mode == VK_SORT_NAME) {
        c = vk_name_compare(x->name, y->name);
        if (c != 0) {
            return c;
        }
    }
    return x->rank == y->rank ? 0 : (x->rank < y->rank ? -1 : 1);
}

/* order[0..n) = 0..n-1 sorted by `mode` (stable insertion sort). */
static void vk_sort_order(int mode, const vk_villager *v, int n, int *order) {
    int i;
    for (i = 0; i < n; ++i) {
        int k = i;
        order[i] = i;
        while (k > 0 && vk_villager_compare(mode, &v[order[k - 1]], &v[i]) > 0) {
            order[k] = order[k - 1];
            --k;
        }
        order[k] = i;
    }
}

/* ---- Sorting a list or combo box of villagers ---------------------------- */

/* Answers whether the entry with item data `data` is a villager, and its
   name, age and place in the game's order. */
typedef int (*vk_villager_fn)(void *context, LPARAM data, vk_villager *out);

#define VK_SORT_MAX 400

typedef struct {
    char text[160];
    LPARAM data;
    int selected;
    int villager;
} vk_entry;

/* Re-orders the villager entries of `control` (a list box, or a combo box
   when `combo`) by `mode`; every other entry keeps its place, the chosen
   entries stay chosen. */
static void vk_sort_control(HWND control, int combo, int mode, vk_villager_fn about, void *context) {
    vk_entry *e;
    vk_villager *v;
    int *slot;
    int *order;
    int n;
    int nv = 0;
    int i;
    int k;
    int multi = !combo && (GetWindowLongA(control, GWL_STYLE) & (LBS_EXTENDEDSEL | LBS_MULTIPLESEL)) != 0;
    int current = (int)SendMessageA(control, combo ? CB_GETCURSEL : LB_GETCURSEL, 0, 0);
    int top = combo ? 0 : (int)SendMessageA(control, LB_GETTOPINDEX, 0, 0);
    int first_selected = -1;
    n = (int)SendMessageA(control, combo ? CB_GETCOUNT : LB_GETCOUNT, 0, 0);
    if (n <= 1 || n > VK_SORT_MAX) {
        return;
    }
    e = (vk_entry *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY,
                              (sizeof *e + sizeof *v + 2 * sizeof(int)) * (size_t)n);
    if (e == NULL) {
        return;
    }
    v = (vk_villager *)(e + n);
    slot = (int *)(v + n);
    order = slot + n;
    for (i = 0; i < n; ++i) {
        int length = (int)SendMessageA(control, combo ? CB_GETLBTEXTLEN : LB_GETTEXTLEN, (WPARAM)i, 0);
        vk_villager who;
        if (length >= 0 && length < (int)sizeof e[i].text) {
            SendMessageA(control, combo ? CB_GETLBTEXT : LB_GETTEXT, (WPARAM)i, (LPARAM)e[i].text);
        }
        e[i].data = (LPARAM)SendMessageA(control, combo ? CB_GETITEMDATA : LB_GETITEMDATA, (WPARAM)i, 0);
        e[i].selected = multi ? SendMessageA(control, LB_GETSEL, (WPARAM)i, 0) > 0 : i == current;
        if (about(context, e[i].data, &who)) {
            e[i].villager = 1;
            v[nv] = who;
            slot[nv] = i;
            ++nv;
        }
    }
    if (nv > 1) {
        vk_entry *copy = (vk_entry *)HeapAlloc(GetProcessHeap(), 0, sizeof *copy * (size_t)nv);
        if (copy != NULL) {
            for (i = 0; i < nv; ++i) {
                copy[i] = e[slot[i]];
            }
            vk_sort_order(mode, v, nv, order);
            for (i = 0; i < nv; ++i) {
                e[slot[i]] = copy[order[i]];
            }
            HeapFree(GetProcessHeap(), 0, copy);
            SendMessageA(control, WM_SETREDRAW, FALSE, 0);
            SendMessageA(control, combo ? CB_RESETCONTENT : LB_RESETCONTENT, 0, 0);
            for (i = 0; i < n; ++i) {
                k = (int)SendMessageA(control, combo ? CB_ADDSTRING : LB_ADDSTRING, 0, (LPARAM)e[i].text);
                SendMessageA(control, combo ? CB_SETITEMDATA : LB_SETITEMDATA, (WPARAM)k, e[i].data);
            }
            for (i = 0; i < n; ++i) {
                if (!e[i].selected) {
                    continue;
                }
                if (first_selected < 0) {
                    first_selected = i;
                }
                if (combo) {
                    SendMessageA(control, CB_SETCURSEL, (WPARAM)i, 0);
                } else if (multi) {
                    SendMessageA(control, LB_SETSEL, TRUE, (LPARAM)i);
                } else {
                    SendMessageA(control, LB_SETCURSEL, (WPARAM)i, 0);
                }
            }
            if (!combo) {
                SendMessageA(control, LB_SETTOPINDEX, (WPARAM)(first_selected >= 0 ? first_selected : top), 0);
                if (multi && first_selected >= 0) {
                    SendMessageA(control, LB_SETCARETINDEX, (WPARAM)first_selected, FALSE);
                }
            }
            SendMessageA(control, WM_SETREDRAW, TRUE, 0);
            InvalidateRect(control, NULL, TRUE);
        }
    }
    HeapFree(GetProcessHeap(), 0, e);
}

/* The sort selector: a drop-down list of the orders `control` offers
   (`with_game`: the game's own order first). */
static void vk_fill_sort_selector(HWND combo, int with_game, int mode) {
    int i;
    int n;
    SendMessageA(combo, CB_RESETCONTENT, 0, 0);
    if (with_game) {
        i = (int)SendMessageA(combo, CB_ADDSTRING, 0, (LPARAM)"The game's own order");
        SendMessageA(combo, CB_SETITEMDATA, (WPARAM)i, VK_SORT_GAME);
    }
    i = (int)SendMessageA(combo, CB_ADDSTRING, 0, (LPARAM)"Age (oldest at top)");
    SendMessageA(combo, CB_SETITEMDATA, (WPARAM)i, VK_SORT_AGE);
    i = (int)SendMessageA(combo, CB_ADDSTRING, 0, (LPARAM)"Alphabetical (first name, then last name)");
    SendMessageA(combo, CB_SETITEMDATA, (WPARAM)i, VK_SORT_NAME);
    n = (int)SendMessageA(combo, CB_GETCOUNT, 0, 0);
    SendMessageA(combo, CB_SETCURSEL, 0, 0);
    for (i = 0; i < n; ++i) {
        if ((int)SendMessageA(combo, CB_GETITEMDATA, (WPARAM)i, 0) == mode) {
            SendMessageA(combo, CB_SETCURSEL, (WPARAM)i, 0);
        }
    }
}

static int vk_sort_selected(HWND combo) {
    int sel = (int)SendMessageA(combo, CB_GETCURSEL, 0, 0);
    return sel < 0 ? VK_SORT_GAME : (int)SendMessageA(combo, CB_GETITEMDATA, (WPARAM)sel, 0);
}

/* A combo box's dropped list as wide as its widest entry (within the
   screen), so no entry is cut off. */
static void vk_fit_dropped_width(HWND combo) {
    HDC dc = GetDC(combo);
    HFONT font = (HFONT)SendMessageA(combo, WM_GETFONT, 0, 0);
    HGDIOBJ old = font != NULL ? SelectObject(dc, font) : NULL;
    int n = (int)SendMessageA(combo, CB_GETCOUNT, 0, 0);
    int widest = 0;
    int i;
    RECT r;
    char text[1200];
    for (i = 0; i < n; ++i) {
        SIZE size;
        int length = (int)SendMessageA(combo, CB_GETLBTEXTLEN, (WPARAM)i, 0);
        if (length < 0 || length >= (int)sizeof text) {
            continue;
        }
        SendMessageA(combo, CB_GETLBTEXT, (WPARAM)i, (LPARAM)text);
        if (GetTextExtentPoint32A(dc, text, length, &size) && size.cx > widest) {
            widest = size.cx;
        }
    }
    if (old != NULL) {
        SelectObject(dc, old);
    }
    ReleaseDC(combo, dc);
    widest += GetSystemMetrics(SM_CXVSCROLL) + 4 * GetSystemMetrics(SM_CXEDGE) + 8;
    GetWindowRect(combo, &r);
    if (widest < r.right - r.left) {
        widest = r.right - r.left;
    }
    if (widest > GetSystemMetrics(SM_CXSCREEN)) {
        widest = GetSystemMetrics(SM_CXSCREEN);
    }
    SendMessageA(combo, CB_SETDROPPEDWIDTH, (WPARAM)widest, 0);
}

#endif
