/* VVFP VV4 Louder Wind Flutes -- "Louder Wind Flutes", The Tree of Life.

   WHAT.  The wind flutes (Flute1.ogg, Flute3.ogg, Flute5.ogg: in fog the weather update 0x46BE10 plays one every
   60 to 89 seconds of the game clock once a Wind Flute is found -- Flute1 with 1 to 4 pieces, Flute3 with 5 to 9,
   Flute5 with 10 to 12) are recorded quietly: peaks of -9.1, -11.7 and -11.4 dBFS, and the louder half of each
   about -23, -27 and -26 dBFS, against about -13 to -15 dBFS for the game's music (song1-4.ogg).  The game already
   plays them at 3.0 x the Sound slider (the float at 0x4AB3A8, used only there), which FMOD caps at full volume
   (255) from a third of the slider up, so a bigger volume number cannot make them louder.  This companion makes
   the three recordings themselves N times louder as the game loads them, N the patcher window's slider (5 unless
   moved; the owner, 2026-11-15; 2026-11-17: 0.1 to 100 in tenths, below 1 quieter than normal), read from "VVFP VV4
   Louder Flutes.txt" beside this DLL (native/shared/multiplier_choice.h's number, in tenths).

   A plain N x gain would clip from about 2.8 x up, so the gain goes through a limiter, worked out over the whole
   sample before any of it is changed: each frame (both channels together) gets the largest gain that keeps it
   at or under -1 dBFS (29,204), and the gain may then change only gradually -- it falls ahead of a loud frame by
   at most 3 dB per 220 frames (60 dB in 5 ms at 44,100 Hz, the rate of all three files) and recovers after it
   by at most 3 dB per 4,410 frames (60 dB in 100 ms).  So nothing is ever clipped, quiet passages get the whole
   N x, and every higher N is louder; below 1 nothing can clip, so the limiter never acts.  Whole numbers only
   (24-bit fixed point, N in tenths), so the result is the same on every machine.

   HOW.  Every sound effect the game loads goes through one call of FSOUND_Sample_Load (FMOD 3.74), at 0x40C4E1
   in the sound loader 0x40C490: FSOUND_Sample_Load(FSOUND_FREE, path, 0, 0, 0) through the import thunk 0x47099E.
   Mode 0 has FMOD decode the Ogg file into plain PCM in memory.  That call is pointed at load_sample (after its
   stock bytes are checked, native/shared/install_sites.h), which makes the very same call, and when the file is
   Flute1.ogg, Flute3.ogg or Flute5.ogg and the sample FMOD made is 16-bit signed PCM, locks the whole sample
   (FSOUND_Sample_Lock), scales it and unlocks it.  The game keeps each sample for the whole session (the
   preload 0x448B80 at start, or the first play 0x448C20), so a sample is scaled once; a fresh load reads the file
   again.  The game's files on disk are never changed.

   SAFETY.  The FMOD functions are found in the game's own fmod.dll at start; if any is missing, nothing is
   installed.  A sample that is not 16-bit signed PCM, or that FMOD does not hand back whole, or whose gain list
   cannot be allocated, is left as it is.  The scaling runs under structured exception handling: a fault leaves
   the sample unchanged or partly scaled, never out of range.  The setting file is only read (its first 15
   bytes); a number above 100 is 100, below 0.1 is 0.1, and no number is 5.  Nothing is written to a save, a villager
   record or a file; no text is shown.  No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/multiplier_choice.h"

#define LF_GAME 4                        /* The Tree of Life */
#define LF_LOAD_CALL 0x40C4E1u           /* call 0x47099E (FSOUND_Sample_Load) in the sound loader 0x40C490 */
#define LF_STOCK_LOAD 0x47099Eu          /* jmp [0x48A3xx]: fmod.dll's _FSOUND_Sample_Load@20 */
#define LF_CHOICE_FILE L"VVFP VV4 Louder Flutes.txt"
#define LF_DEFAULT 50u                   /* the slider's default, 5, in tenths */
#define LF_MINIMUM 1u                    /* 0.1 */
#define LF_MAXIMUM 1000u                 /* 100 */

/* The limiter (24-bit fixed point). */
#define LF_ONE 16777216u                 /* a gain of 1 */
#define LF_CEILING 29204u                /* -1 dBFS: 32768 x 10^(-1/20) */
#define LF_ATTACK 17312359u              /* 10^(3/220) x 2^24: 3 dB per 220 frames, ahead of a peak */
#define LF_RELEASE 16803516u             /* 10^(3/4410) x 2^24: 3 dB per 4,410 frames, after it */
#define LF_MAX_FRAMES 0x04000000u        /* the gain list's limit (256 MB); the flutes are about 1.3 million */

/* FMOD 3.74's sample mode bits (fmod.h). */
#define LF_8BITS 0x00000008u
#define LF_16BITS 0x00000010u
#define LF_STEREO 0x00000040u
#define LF_UNSIGNED 0x00000080u
#define LF_COMPRESSED (0x00000200u | 0x00000400u | 0x00000800u | 0x00400000u | 0x00800000u | 0x02000000u)
                                         /* DELTA, IT214, IT215, IMAADPCM, VAG, GCADPCM */

typedef void *(__stdcall *load_fn)(int index, const char *name, unsigned int mode, int offset, int length);
typedef unsigned int (__stdcall *length_fn)(void *sample);
typedef unsigned int (__stdcall *mode_fn)(void *sample);
typedef signed char (__stdcall *lock_fn)(void *sample, int offset, int length, void **ptr1, void **ptr2,
                                         unsigned int *len1, unsigned int *len2);
typedef signed char (__stdcall *unlock_fn)(void *sample, void *ptr1, void *ptr2, unsigned int len1,
                                           unsigned int len2);

static length_fn g_length;
static mode_fn g_mode;
static lock_fn g_lock;
static unlock_fn g_unlock;
static HMODULE g_module;
static unsigned char g_call_stock[5];
static int g_installed;
static int g_scaled;                     /* samples made louder (for the tests' emulation) */
static unsigned int g_tenths = LF_DEFAULT;     /* N in tenths */

static const char *const LF_FLUTES[] = { "flute1.ogg", "flute3.ogg", "flute5.ogg" };

/* 1 when the path's file name is one of the three wind flutes (any case, either slash). */
static int is_flute(const char *path) {
    const char *name = path;
    const char *at;
    int i;
    if (path == NULL) {
        return 0;
    }
    for (at = path; *at; ++at) {
        if (*at == '\\' || *at == '/') {
            name = at + 1;
        }
    }
    for (i = 0; i < (int)(sizeof LF_FLUTES / sizeof LF_FLUTES[0]); ++i) {
        if (lstrcmpiA(name, LF_FLUTES[i]) == 0) {
            return 1;
        }
    }
    return 0;
}

/* The slider's number from "VVFP VV4 Louder Flutes.txt" beside this DLL, in tenths: 0.1 to 100, else 5 (no
   number). */
static unsigned int read_tenths(void) {
    WCHAR path[MAX_PATH * 2];
    char text[16];
    DWORD length, got = 0, i, slash = 0;
    const DWORD room = (DWORD)(sizeof path / sizeof path[0]);
    HANDLE file;
    length = GetModuleFileNameW(g_module, path, room);
    if (length == 0 || length >= room) {
        return LF_DEFAULT;
    }
    for (i = 0; i < length; ++i) {
        if (path[i] == L'\\' || path[i] == L'/') {
            slash = i + 1;
        }
    }
    if (slash == 0 || slash + (DWORD)(sizeof LF_CHOICE_FILE / sizeof(WCHAR)) > room) {
        return LF_DEFAULT;
    }
    memcpy(path + slash, LF_CHOICE_FILE, sizeof LF_CHOICE_FILE);
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return LF_DEFAULT;
    }
    if (!ReadFile(file, text, (DWORD)(sizeof text - 1), &got, NULL)) {
        got = 0;
    }
    CloseHandle(file);
    return vvfp_parse_tenths(text, got, LF_DEFAULT, LF_MINIMUM, LF_MAXIMUM);
}

/* Sample k of the locked sample, in its one or two pieces. */
static short *sample_at(short *one, unsigned int count1, short *two, unsigned int k) {
    return k < count1 ? one + k : two + (k - count1);
}

/* The sample N x louder through the limiter (see WHAT); 0 when it cannot be (left as it is). */
static int scale(short *one, unsigned int count1, short *two, unsigned int count2, unsigned int channels) {
    unsigned int frames = (count1 + count2) / channels;
    unsigned int *gain;
    unsigned int f, c;
    if (frames == 0 || frames > LF_MAX_FRAMES || (count1 + count2) % channels != 0) {
        return 0;
    }
    gain = (unsigned int *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)frames * sizeof *gain);
    if (gain == NULL) {
        return 0;
    }
    /* The largest gain that keeps each frame at or under the ceiling. */
    for (f = 0; f < frames; ++f) {
        unsigned int peak = 0, loud;
        for (c = 0; c < channels; ++c) {
            int v = *sample_at(one, count1, two, f * channels + c);
            unsigned int size = (unsigned int)(v < 0 ? -v : v);
            if (size > peak) {
                peak = size;
            }
        }
        loud = peak * g_tenths / 10u;
        gain[f] = loud > LF_CEILING ? (unsigned int)(((unsigned long long)LF_CEILING << 24) / loud) : LF_ONE;
    }
    /* Falling gradually ahead of each loud frame (from the end back), then recovering gradually after it. */
    for (f = frames - 1; f-- > 0;) {
        unsigned int ahead = (unsigned int)(((unsigned long long)gain[f + 1] * LF_ATTACK) >> 24);
        if (ahead < gain[f]) {
            gain[f] = ahead;
        }
    }
    for (f = 1; f < frames; ++f) {
        unsigned int after = (unsigned int)(((unsigned long long)gain[f - 1] * LF_RELEASE) >> 24);
        if (after < gain[f]) {
            gain[f] = after;
        }
    }
    for (f = 0; f < frames; ++f) {
        long long factor = (long long)g_tenths * gain[f] / 10;
        for (c = 0; c < channels; ++c) {
            short *s = sample_at(one, count1, two, f * channels + c);
            long long v = ((long long)*s * factor) >> 24;
            *s = (short)(v > 32767 ? 32767 : (v < -32768 ? -32768 : v));
        }
    }
    HeapFree(GetProcessHeap(), 0, gain);
    return 1;
}

static void make_louder(void *sample) {
    unsigned int mode, bytes;
    void *ptr1 = NULL, *ptr2 = NULL;
    unsigned int len1 = 0, len2 = 0;
    mode = g_mode(sample);
    if ((mode & LF_16BITS) == 0 || (mode & (LF_8BITS | LF_UNSIGNED | LF_COMPRESSED)) != 0) {
        return;
    }
    bytes = g_length(sample) * ((mode & LF_STEREO) ? 4u : 2u);
    if (bytes == 0 || bytes > 0x7FFFFFFFu || !g_lock(sample, 0, (int)bytes, &ptr1, &ptr2, &len1, &len2)) {
        return;
    }
    if (ptr1 != NULL && len1 + len2 == bytes && (len1 & 1u) == 0 && (len2 & 1u) == 0
        && (len2 == 0 || ptr2 != NULL)) {
        if (scale((short *)ptr1, len1 / 2u, (short *)ptr2, len2 / 2u, (mode & LF_STEREO) ? 2u : 1u)) {
            ++g_scaled;
        }
    }
    g_unlock(sample, ptr1, ptr2, len1, len2);
}

/* In place of the loader's call of FSOUND_Sample_Load: the same call, then the flutes made louder. */
static void *__stdcall load_sample(int index, const char *name, unsigned int mode, int offset, int length) {
    void *sample = ((load_fn)(UINT_PTR)LF_STOCK_LOAD)(index, name, mode, offset, length);
    if (sample != NULL) {
        __try {
            if (is_flute(name)) {
                make_louder(sample);
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
    return sample;
}

/* 1 when the call is installed (for the tests' emulation), else 0. */
int __stdcall VvfpLouderFlutesInstalled(void) {
    return g_installed;
}

/* How many wind flute samples have been made louder (for the tests' emulation). */
int __stdcall VvfpLouderFlutesScaled(void) {
    return g_scaled;
}

/* The multiplier read at start, in tenths (for the tests' emulation): 50 is 5, 5 is 0.5. */
int __stdcall VvfpLouderFlutesMultiplier(void) {
    return (int)g_tenths;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write site;
    unsigned int rel = LF_STOCK_LOAD - (LF_LOAD_CALL + 5u);
    HMODULE fmod;
    (void)shipped;
    if (g_installed || game != LF_GAME) {
        return;
    }
    fmod = GetModuleHandleA("fmod.dll");
    if (fmod == NULL) {
        return;
    }
    g_length = (length_fn)(void *)GetProcAddress(fmod, "_FSOUND_Sample_GetLength@4");
    g_mode = (mode_fn)(void *)GetProcAddress(fmod, "_FSOUND_Sample_GetMode@4");
    g_lock = (lock_fn)(void *)GetProcAddress(fmod, "_FSOUND_Sample_Lock@28");
    g_unlock = (unlock_fn)(void *)GetProcAddress(fmod, "_FSOUND_Sample_Unlock@20");
    if (g_length == NULL || g_mode == NULL || g_lock == NULL || g_unlock == NULL) {
        return;
    }
    g_tenths = read_tenths();
    g_call_stock[0] = 0xE8;
    memcpy(g_call_stock + 1, &rel, 4);
    vvfp_site_branch(&site, LF_LOAD_CALL, 5, g_call_stock, 0xE8, (const void *)load_sample);
    if (vvfp_install_sites(&site, 1)) {
        g_installed = 1;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = instance;
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
