"""Render a companion DLL's dialog template to a PNG, as Windows draws it: the Change Appearance pictures in
docs/ (the head look row, the owner, 2026-10-28).

    python scripts/render_change_appearance.py <dll> <dialog id> <out.png> [<control>=<bitmap>:<cell>[:v][@<dll>] ...]
        [--check <control> ...]

The DLL is loaded as a resource file only (none of its code runs).  The dialog is created by Windows from
its own template, off screen, and printed with PrintWindow; each owner-drawn preview named on the command
line is filled with that cell (40 x 65) of that BITMAP resource -- of the DLL, or of the one after "@" -- scaled
to fit as the companions draw it: cells side by side, or one under another with ":v" (A New Home's 40 x 1300
strips and Grey Hair's grey ones).  Every other owner-drawn control is left blank.  The first radio button of
each group is checked, as the windows open for a villager whose look is Auto, unless --check names others.
Windows only.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

CELL_W, CELL_H = 40, 65


def render(dll: Path, dialog: int, out: Path, previews: dict[int, tuple[int, int, bool, Path | None]],
           checked: tuple[int, ...] = ()) -> tuple[int, int]:
    from PIL import Image

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LoadLibraryExW.restype = wintypes.HMODULE
    kernel32.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
    module = kernel32.LoadLibraryExW(str(dll), None, 0x2 | 0x20)   # LOAD_LIBRARY_AS_DATAFILE | AS_IMAGE_RESOURCE
    if not module:
        raise OSError(f"cannot load {dll} as a resource file")
    extra = {}
    for _, _, _, other in previews.values():
        if other is not None and other not in extra:
            extra[other] = kernel32.LoadLibraryExW(str(other), None, 0x2 | 0x20)
            if not extra[other]:
                raise OSError(f"cannot load {other} as a resource file")

    DLGPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class DRAWITEMSTRUCT(ctypes.Structure):
        _fields_ = [("CtlType", wintypes.UINT), ("CtlID", wintypes.UINT), ("itemID", wintypes.UINT),
                    ("itemAction", wintypes.UINT), ("itemState", wintypes.UINT), ("hwndItem", wintypes.HWND),
                    ("hDC", wintypes.HDC), ("rcItem", wintypes.RECT), ("itemData", ctypes.c_size_t)]

    user32.LoadImageW.restype = wintypes.HANDLE
    user32.LoadImageW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                  wintypes.UINT]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
    user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.HBRUSH]
    gdi32.StretchBlt.argtypes = [wintypes.HDC] + [ctypes.c_int] * 4 + [wintypes.HDC] + [ctypes.c_int] * 4 \
        + [wintypes.DWORD]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.SetStretchBltMode.argtypes = [wintypes.HDC, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                                ctypes.c_void_p, wintypes.UINT]
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetDlgCtrlID.argtypes = [wintypes.HWND]
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND] + [ctypes.c_int] * 4 + [wintypes.UINT]
    user32.UpdateWindow.argtypes = [wintypes.HWND]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    kernel32.FreeLibrary.argtypes = [wintypes.HMODULE]

    def draw(item: DRAWITEMSTRUCT) -> None:
        rc = item.rcItem
        brush = gdi32.CreateSolidBrush(0x00ECECEC)
        user32.FillRect(item.hDC, ctypes.byref(rc), brush)
        gdi32.DeleteObject(brush)
        if item.CtlID not in previews:
            return
        bitmap_id, cell, vertical, other = previews[item.CtlID]
        source_module = extra[other] if other is not None else module
        bitmap = user32.LoadImageW(source_module, ctypes.c_void_p(bitmap_id), 0, 0, 0, 0)   # IMAGE_BITMAP
        if not bitmap:
            return
        source = gdi32.CreateCompatibleDC(item.hDC)
        previous = gdi32.SelectObject(source, bitmap)
        width, height = rc.right - rc.left, rc.bottom - rc.top
        scale = min(width / CELL_W, height / CELL_H)
        w, h = int(CELL_W * scale), int(CELL_H * scale)
        gdi32.SetStretchBltMode(item.hDC, 3)                   # COLORONCOLOR
        gdi32.StretchBlt(item.hDC, rc.left + (width - w) // 2, rc.top + (height - h) // 2, w, h,
                         source, 0 if vertical else cell * CELL_W, cell * CELL_H if vertical else 0, CELL_W, CELL_H,
                         0x00CC0020)  # SRCCOPY
        gdi32.SelectObject(source, previous)
        gdi32.DeleteDC(source)
        gdi32.DeleteObject(bitmap)

    def proc(window, message, wparam, lparam):
        if message == 0x0110:                                  # WM_INITDIALOG
            child = user32.GetWindow(window, 5)                # GW_CHILD
            while child:
                style = user32.GetWindowLongW(child, -16)
                name = ctypes.create_unicode_buffer(32)
                user32.GetClassNameW(child, name, 32)
                is_radio = name.value.lower() == "button" and style & 0xF == 9
                wanted = user32.GetDlgCtrlID(child) in checked if checked else style & 0x00020000   # first of a group
                if is_radio and wanted:
                    user32.SendMessageW(child, 0x00F1, 1, 0)   # BM_SETCHECK
                child = user32.GetWindow(child, 2)             # GW_HWNDNEXT
            return 1
        if message == 0x002B:                                  # WM_DRAWITEM
            draw(DRAWITEMSTRUCT.from_address(lparam))
            return 1
        return 0

    callback = DLGPROC(proc)
    user32.CreateDialogParamW.restype = wintypes.HWND
    user32.CreateDialogParamW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p, wintypes.HWND, DLGPROC,
                                          wintypes.LPARAM]
    window = user32.CreateDialogParamW(module, ctypes.c_void_p(dialog), None, callback, 0)
    if not window:
        raise OSError(f"dialog {dialog} could not be created ({ctypes.get_last_error()})")
    try:
        rect = wintypes.RECT()
        user32.GetWindowRect(window, ctypes.byref(rect))
        width, height = rect.right - rect.left, rect.bottom - rect.top
        user32.SetWindowPos(window, None, -32000, -32000, 0, 0, 0x0001 | 0x0004 | 0x0010 | 0x0040)
        user32.UpdateWindow(window)
        screen = user32.GetDC(None)
        dc = gdi32.CreateCompatibleDC(screen)
        gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
        bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
        previous = gdi32.SelectObject(dc, bitmap)
        user32.PrintWindow(window, dc, 2)                      # PW_RENDERFULLCONTENT
        buffer = ctypes.create_string_buffer(width * height * 4)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                        ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                        ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                        ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]
        header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        gdi32.SelectObject(dc, previous)
        gdi32.GetDIBits(dc, bitmap, 0, height, buffer, ctypes.byref(header), 0)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(dc)
        user32.ReleaseDC(None, screen)
        image = Image.frombuffer("RGBA", (width, height), buffer.raw, "raw", "BGRA", 0, 1).convert("RGB")
        out.parent.mkdir(parents=True, exist_ok=True)
        image.save(out)
        return width, height
    finally:
        user32.DestroyWindow(window)
        kernel32.FreeLibrary(module)
        for handle in extra.values():
            kernel32.FreeLibrary(handle)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    previews = {}
    checked = []
    specs = argv[3:]
    while specs:
        spec = specs.pop(0)
        if spec == "--check":
            checked.append(int(specs.pop(0)))
            continue
        control, rest = spec.split("=")
        rest, _, other = rest.partition("@")
        parts = rest.split(":")
        previews[int(control)] = (int(parts[0]), int(parts[1]), parts[2:] == ["v"], Path(other) if other else None)
    size = render(Path(argv[0]), int(argv[1]), Path(argv[2]), previews, tuple(checked))
    print(f"wrote {argv[2]} ({size[0]} x {size[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
