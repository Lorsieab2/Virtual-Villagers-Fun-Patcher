/* VVFP Game Log -- the game's own log (ldwLog.txt) in all five games.

   WHAT THE GAMES HAVE.  Every Virtual Villagers game carries the LDW engine's
   log writer: writer(log, format, ...) prints "<date and time>: <line>" to
   Documents\LDW\<executable name>\ldwLog.txt (the name cut at its first dot,
   exactly as the game's own path builder cuts it).  The writer has no on/off
   switch, and every call to it is live in all five executables -- nothing is
   stubbed or jumped over -- but the base game keeps the log in a way that
   makes it next to useless:
     * the file is opened with "wt" (the logger's append flag is never set), so
       the first line of every run ERASES what the previous runs wrote;
     * it is written through a C-library buffer that is only flushed when the
       game closes cleanly, so nothing appears while the game runs and every
       line is lost if the game is killed or crashes;
     * the file is only created when something goes wrong, so A New Home, The
       Lost Children, The Secret City and The Tree of Life normally never have
       one at all.
   What each game logs is fixed by its own code (tests/test_game_log.py pins
   every call site):
     all five   "Font Image not found: <file>" (the game then closes),
                " Missing Graphic -> <file>", "ldwSoundFx Missing File -><file>";
     VV2-VV5    "Seconds Timer out of bounds!" (the game clock ran ahead);
     VV2        "Displaying Tip (<n>) message!" (a tutorial tip shown);
     VV3-VV5    "String Table (sm.xml) malformed near <id>" / "... looking for
                </Text> after <id>", "<name> could not find someone to heal.";
     VV5        "<name> is stuck!", "<name> cannot get from <x>, <y> (isBlocking=
                ...) to <x>, <y> (isBlocking=...)", "<name> is going to the love
                shack door at <x>, <y> (isBlocking=...)".
   A line a game's code does not contain is never written: The Secret City and
   The Tree of Life keep a pointer to the log on every villager but have no
   code left that writes through it, and the tip line exists only in The Lost
   Children.

   WHAT THIS DOES.  VvfpStartup -- called by "VVFP Startup.dll" before the
   game's WinMain -- verifies the writer's first 16 bytes in this executable
   and replaces its first instruction with a jump to write_line() below, which
   takes the same arguments and writes the same "<asctime>: <line>" text with
   the same CR-LF line ends, but:
     * appends, so every run's lines are kept, and marks the start of each
       run with one line of its own ("---- Game started ----"), which also
       makes the file appear in every game the first time it is opened;
     * writes each line to the file at once (no buffer), so the log can be read
       while the game runs and survives a crash;
     * writes a line that exactly repeats the one before it only once a
       minute, followed by how many times it repeated -- "Seconds Timer out of
       bounds!" is checked every frame and would otherwise fill the file;
     * writes at most RATE_LINES lines a minute, then one line saying how many
       it left out;
     * starts a new file when ldwLog.txt reaches ROLL_BYTES (4 MiB): the full
       file is renamed "ldwLog <n>.txt" (n one more than the highest already
       there) and kept; nothing is ever deleted.
   A different build of the game, or a missing DLL, installs nothing: the
   game's own writer then runs as before.  Nothing here reads or writes the
   game's data or calls a game routine. */
#ifndef _CRT_SECURE_NO_WARNINGS
#define _CRT_SECURE_NO_WARNINGS
#endif
#include <windows.h>
#include <shlobj.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#define ROLL_BYTES (4u * 1024u * 1024u)
#define REPEAT_SECONDS 60
#define RATE_SECONDS 60
#define RATE_LINES 1000u
#define LINE_CHARS 2048
#define SITE_LENGTH 6
#define STOCK_LENGTH 16

/* ---- Each game's writer ------------------------------------------------ */

struct site {
    unsigned int va;                         /* the writer's first byte */
    unsigned char stock[STOCK_LENGTH];
};

/* push esi; push edi; mov edi,[esp+0Ch]; mov esi,[edi]; cmp dword [esi],0;
   jne ...; mov eax,[esi+8] -- the same writer in all five games. */
static const struct site SITES[6] = {
    {0, {0}},
    {0x40A970, {0x56, 0x57, 0x8B, 0x7C, 0x24, 0x0C, 0x8B, 0x37, 0x83, 0x3E, 0x00, 0x75, 0x3A, 0x8B, 0x46, 0x08}},
    {0x40AB70, {0x56, 0x57, 0x8B, 0x7C, 0x24, 0x0C, 0x8B, 0x37, 0x83, 0x3E, 0x00, 0x75, 0x3A, 0x8B, 0x46, 0x08}},
    {0x40B800, {0x56, 0x57, 0x8B, 0x7C, 0x24, 0x0C, 0x8B, 0x37, 0x83, 0x3E, 0x00, 0x75, 0x3A, 0x8B, 0x46, 0x08}},
    {0x40B6C0, {0x56, 0x57, 0x8B, 0x7C, 0x24, 0x0C, 0x8B, 0x37, 0x83, 0x3E, 0x00, 0x75, 0x38, 0x8B, 0x46, 0x08}},
    {0x40BBB0, {0x56, 0x57, 0x8B, 0x7C, 0x24, 0x0C, 0x8B, 0x37, 0x83, 0x3E, 0x00, 0x75, 0x38, 0x8B, 0x46, 0x08}},
};

/* ---- State --------------------------------------------------------------- */

static CRITICAL_SECTION lock;
static int lock_ready;
static wchar_t folder[MAX_PATH];             /* Documents\LDW\<exe name> */
static int folder_state;                     /* 0 unknown, 1 known, -1 none */
static HANDLE file = INVALID_HANDLE_VALUE;
static unsigned int file_size;
static char last_line[LINE_CHARS];           /* the last line written (text only) */
static int have_last;
static ULONGLONG last_written;               /* seconds (see seconds_now) */
static unsigned int repeats;                 /* repeats of last_line not yet written */
static ULONGLONG rate_start;
static unsigned int rate_count;
static unsigned int rate_dropped;

/* The clock.  The time stamp is the computer's local time, as the game's own
   asctime() stamp; the repeat and rate windows count seconds since Windows
   started.  Both are Win32 calls only: the start of the run (VvfpStartup) is
   before the game, or this DLL's C runtime, has set anything up.  The C
   harness replaces both. */
static void real_local_time(SYSTEMTIME *now) {
    GetLocalTime(now);
}

static ULONGLONG real_seconds(void) {
    return GetTickCount64() / 1000u;
}

static void (*local_time)(SYSTEMTIME *) = real_local_time;
static ULONGLONG (*seconds_now)(void) = real_seconds;

/* ---- Text without the C runtime (also used before the game starts) ------- */

static int wlen(const wchar_t *s) {
    int n = 0;
    while (s[n] != 0) {
        ++n;
    }
    return n;
}

/* Append `src` to `dst` (capacity MAX_PATH); 0 when it would not fit. */
static int wappend(wchar_t *dst, const wchar_t *src) {
    int n = wlen(dst), i = 0;
    while (src[i] != 0) {
        if (n + 1 >= MAX_PATH) {
            return 0;
        }
        dst[n++] = src[i++];
    }
    dst[n] = 0;
    return 1;
}

static int wappend_number(wchar_t *dst, unsigned int value) {
    wchar_t digits[12];
    int n = 11;
    digits[n] = 0;
    do {
        digits[--n] = (wchar_t)(L'0' + value % 10);
        value /= 10;
    } while (value != 0);
    return wappend(dst, digits + n);
}

/* "Mon Sep 28 23:27:56 2026": asctime()'s text without its newline. */
static unsigned int stamp_text(char *out) {
    static const char DAYS[] = "SunMonTueWedThuFriSat";
    static const char MONTHS[] = "JanFebMarAprMayJunJulAugSepOctNovDec";
    SYSTEMTIME now;
    unsigned int n = 0, i, year;
    local_time(&now);
    for (i = 0; i < 3; ++i) out[n++] = DAYS[(now.wDayOfWeek % 7) * 3 + i];
    out[n++] = ' ';
    for (i = 0; i < 3; ++i) out[n++] = MONTHS[((now.wMonth + 11) % 12) * 3 + i];
    out[n++] = ' ';
    out[n++] = now.wDay >= 10 ? (char)('0' + now.wDay / 10 % 10) : ' ';
    out[n++] = (char)('0' + now.wDay % 10);
    out[n++] = ' ';
    out[n++] = (char)('0' + now.wHour / 10 % 10);
    out[n++] = (char)('0' + now.wHour % 10);
    out[n++] = ':';
    out[n++] = (char)('0' + now.wMinute / 10 % 10);
    out[n++] = (char)('0' + now.wMinute % 10);
    out[n++] = ':';
    out[n++] = (char)('0' + now.wSecond / 10 % 10);
    out[n++] = (char)('0' + now.wSecond % 10);
    out[n++] = ' ';
    year = now.wYear;
    out[n++] = (char)('0' + year / 1000 % 10);
    out[n++] = (char)('0' + year / 100 % 10);
    out[n++] = (char)('0' + year / 10 % 10);
    out[n++] = (char)('0' + year % 10);
    return n;
}

/* ---- The file ------------------------------------------------------------ */

/* Documents\LDW\<exe name, cut at its first dot> -- the game's own folder for
   ldwLog.txt (its path builder: SHGetSpecialFolderPath(CSIDL_PERSONAL) +
   "\LDW\" + the module name up to the first '.'), created as the game creates
   it. */
static int resolve_folder(void) {
    wchar_t docs[MAX_PATH], exe[MAX_PATH];
    wchar_t *base;
    DWORD n;
    int i;
    if (folder_state != 0) {
        return folder_state == 1;
    }
    folder_state = -1;
    if (!SHGetSpecialFolderPathW(NULL, docs, CSIDL_PERSONAL, TRUE)) {
        return 0;
    }
    n = GetModuleFileNameW(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    base = exe;
    for (i = 0; exe[i] != 0; ++i) {
        if (exe[i] == L'\\') {
            base = exe + i + 1;
        }
    }
    for (i = 0; base[i] != 0; ++i) {
        if (base[i] == L'.') {
            base[i] = 0;
            break;
        }
    }
    if (base[0] == 0 || wlen(docs) + wlen(base) + 40 >= MAX_PATH) {
        return 0;
    }
    folder[0] = 0;
    wappend(folder, docs);
    wappend(folder, L"\\LDW");
    CreateDirectoryW(folder, NULL);
    wappend(folder, L"\\");
    wappend(folder, base);
    CreateDirectoryW(folder, NULL);
    folder_state = 1;
    return 1;
}

static int log_path(wchar_t *out) {
    out[0] = 0;
    return wappend(out, folder) && wappend(out, L"\\ldwLog.txt");
}

static int open_file(void) {
    wchar_t path[MAX_PATH];
    LARGE_INTEGER size;
    if (file != INVALID_HANDLE_VALUE) {
        return 1;
    }
    if (!resolve_folder() || !log_path(path)) {
        return 0;
    }
    file = CreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                       NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    if (!GetFileSizeEx(file, &size)) {
        size.QuadPart = 0;
    }
    file_size = size.QuadPart > 0xFFFFFFFF ? 0xFFFFFFFFu : (unsigned int)size.QuadPart;
    return 1;
}

/* The highest n of an existing "ldwLog <n>.txt", or 0. */
static unsigned int highest_rolled(void) {
    wchar_t pattern[MAX_PATH];
    WIN32_FIND_DATAW found;
    HANDLE h;
    unsigned int best = 0;
    pattern[0] = 0;
    if (!wappend(pattern, folder) || !wappend(pattern, L"\\ldwLog *.txt")) {
        return 0;
    }
    h = FindFirstFileW(pattern, &found);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    do {
        const wchar_t *p = found.cFileName + 7;     /* after "ldwLog " */
        unsigned int n = 0;
        int digits = 0;
        while (*p >= L'0' && *p <= L'9' && digits < 9) {
            n = n * 10 + (unsigned int)(*p - L'0');
            ++p;
            ++digits;
        }
        if (digits > 0 && (p[0] == L'.') && (p[1] | 0x20) == L't' && (p[2] | 0x20) == L'x'
            && (p[3] | 0x20) == L't' && p[4] == 0 && n > best) {
            best = n;
        }
    } while (FindNextFileW(h, &found));
    FindClose(h);
    return best;
}

/* Rename the full ldwLog.txt to "ldwLog <n>.txt" and start a new one.  Returns
   0 when it could not be moved; the caller then writes nothing, so the file
   never grows past the cap. */
static int roll(void) {
    wchar_t from[MAX_PATH], to[MAX_PATH];
    if (file != INVALID_HANDLE_VALUE) {
        CloseHandle(file);
        file = INVALID_HANDLE_VALUE;
    }
    to[0] = 0;
    if (!log_path(from) || !wappend(to, folder) || !wappend(to, L"\\ldwLog ")
        || !wappend_number(to, highest_rolled() + 1) || !wappend(to, L".txt")) {
        return 0;
    }
    if (!MoveFileW(from, to)) {
        return 0;
    }
    return open_file();
}

/* Append `text` (already CR-LF), rolling first when it would pass the cap. */
static void append(const char *text, unsigned int length) {
    DWORD written;
    if (!open_file()) {
        return;
    }
    if (file_size > 0 && file_size + length > ROLL_BYTES && !roll()) {
        return;
    }
    if (WriteFile(file, text, length, &written, NULL)) {
        file_size += written;
    }
}

/* "<asctime>: <text>" with every '\n' written as CR-LF (the game opens the
   file in text mode) and a CR-LF at the end, as the game's writer does. */
static void write_stamped(const char *text) {
    char out[LINE_CHARS * 2 + 64];
    unsigned int n = stamp_text(out);
    unsigned int i;
    out[n++] = ':';
    out[n++] = ' ';
    for (i = 0; text[i] != 0 && n + 4 < sizeof out; ++i) {
        if (text[i] == '\n') {
            out[n++] = '\r';
        }
        out[n++] = text[i];
    }
    out[n++] = '\r';
    out[n++] = '\n';
    append(out, n);
}

static void flush_repeats(void) {
    char text[96];
    if (repeats > 0) {
        _snprintf(text, sizeof text, "(the line above was repeated %u more time%s)",
                  repeats, repeats == 1 ? "" : "s");
        text[sizeof text - 1] = 0;
        write_stamped(text);
        repeats = 0;
    }
}

/* One line from the game (text without the time stamp). */
static void log_line(const char *text) {
    ULONGLONG now = seconds_now();
    char note[128];
    /* An exact repeat of the last line: counted, and written at most once a
       minute. */
    if (have_last && strcmp(text, last_line) == 0 && now - last_written < REPEAT_SECONDS) {
        ++repeats;
        return;
    }
    /* At most RATE_LINES lines a minute. */
    if (rate_count == 0 || now - rate_start >= RATE_SECONDS) {
        if (rate_dropped > 0) {
            flush_repeats();
            _snprintf(note, sizeof note,
                      "(%u more line%s left out: the game wrote more than %u lines in a minute)",
                      rate_dropped, rate_dropped == 1 ? " was" : "s were", RATE_LINES);
            note[sizeof note - 1] = 0;
            write_stamped(note);
            rate_dropped = 0;
        }
        rate_start = now;
        rate_count = 0;
    }
    if (rate_count >= RATE_LINES) {
        /* Left out.  The file's last line is no longer the game's last line,
           so nothing after this counts as its repeat. */
        ++rate_dropped;
        have_last = 0;
        return;
    }
    ++rate_count;
    flush_repeats();
    write_stamped(text);
    strncpy(last_line, text, sizeof last_line - 1);
    last_line[sizeof last_line - 1] = 0;
    have_last = 1;
    last_written = now;
}

/* ---- The game's writer, replaced ----------------------------------------- */

/* Same arguments as the game's writer (cdecl: the log object, the format and
   its values); the log object is not used -- New Believers also hands it from
   a copy kept on each villager.  This runs on the game's thread with the
   game's C runtime and this DLL's both set up. */
static int __cdecl write_line(void *log, const char *format, ...) {
    char text[LINE_CHARS];
    va_list values;
    (void)log;
    if (!lock_ready || format == NULL) {
        return 0;
    }
    va_start(values, format);
    __try {
        _vsnprintf(text, sizeof text, format, values);
        text[sizeof text - 1] = 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        /* A value the format could not read: keep the format itself. */
        strncpy(text, format, sizeof text - 1);
        text[sizeof text - 1] = 0;
    }
    va_end(values);
    EnterCriticalSection(&lock);
    __try {
        log_line(text);
    } __finally {
        LeaveCriticalSection(&lock);
    }
    return 0;
}

/* ---- Installing ----------------------------------------------------------- */

static int code_is(unsigned int va, const unsigned char *bytes, size_t length) {
    MEMORY_BASIC_INFORMATION info;
    const void *where = (const void *)(UINT_PTR)va;
    if (VirtualQuery(where, &info, sizeof(info)) != sizeof(info)
        || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp(where, bytes, length) == 0;
}

/* jmp write_line; nop -- the writer's first two instructions and the first
   byte of its third, which nothing branches to. */
static void site_bytes(unsigned int va, unsigned char *out) {
    unsigned int rel = (unsigned int)((UINT_PTR)write_line - ((UINT_PTR)va + 5));
    out[0] = 0xE9;
    memcpy(out + 1, &rel, 4);
    out[5] = 0x90;
}

static int install_state;   /* 0 untried, 1 installed, -1 refused */

static int install(int game) {
    unsigned char bytes[SITE_LENGTH];
    unsigned int va;
    DWORD old;
    if (install_state != 0) {
        return install_state == 1;
    }
    install_state = -1;
    if (game < 1 || game > 5) {
        return 0;
    }
    va = SITES[game].va;
    if (!code_is(va, SITES[game].stock, STOCK_LENGTH)) {
        return 0;
    }
    site_bytes(va, bytes);
    if (!VirtualProtect((void *)(UINT_PTR)va, SITE_LENGTH, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy((void *)(UINT_PTR)va, bytes, SITE_LENGTH);
    VirtualProtect((void *)(UINT_PTR)va, SITE_LENGTH, old, &old);
    FlushInstructionCache(GetCurrentProcess(), (void *)(UINT_PTR)va, SITE_LENGTH);
    install_state = 1;
    return 1;
}

/* Arm the writer, then mark the start of this run (which also creates the
   file).  Only Win32 calls: nothing of the C runtime is used here. */
static void start(int game) {
    if (!lock_ready) {
        InitializeCriticalSection(&lock);
        lock_ready = 1;
    }
    if (install(game)) {
        EnterCriticalSection(&lock);
        write_stamped("---- Game started ----");
        LeaveCriticalSection(&lock);
    }
}

/* Called once by "VVFP Startup.dll" as the game opens. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    start(game);
}

#ifdef VVFP_TEST
/* For the test build only: a game's writer, its stock bytes, what they become
   and the replacement's address. */
__declspec(dllexport) int __stdcall VvfpGameLogProbe(int game, unsigned int *site_va,
                                                     unsigned char *stock, unsigned char *patched,
                                                     unsigned int *hook_va) {
    if (game < 1 || game > 5) {
        return 0;
    }
    *site_va = SITES[game].va;
    memcpy(stock, SITES[game].stock, STOCK_LENGTH);
    site_bytes(SITES[game].va, patched);
    *hook_va = (unsigned int)(UINT_PTR)write_line;
    return SITE_LENGTH;
}
#endif /* VVFP_TEST */

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    } else if (reason == DLL_PROCESS_DETACH && reserved != NULL && lock_ready
               && repeats > 0 && file != INVALID_HANDLE_VALUE) {
        /* The game is closing: write the count of a repeated last line, when
           the lock is free.  This DLL's own C runtime is still up here (its
           entry point calls DllMain before tearing the runtime down), and
           nothing is loaded or waited for. */
        if (TryEnterCriticalSection(&lock)) {
            flush_repeats();
            LeaveCriticalSection(&lock);
        }
    }
    return TRUE;
}
