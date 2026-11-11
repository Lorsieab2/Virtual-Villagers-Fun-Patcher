/* VVFP VV4 Louder Wind Flutes -- "Louder Wind Flutes", The Tree of Life.

   WHAT.  The wind flutes (Flute1.ogg, Flute3.ogg, Flute5.ogg: in fog the weather update 0x46BE10 plays one every
   60 to 89 seconds of the game clock once a Wind Flute is found -- Flute1 with 1 to 4 pieces, Flute3 with 5 to 9,
   Flute5 with 10 to 12) are recorded quietly: peaks of -9.1, -11.7 and -11.4 dBFS and an average of about -26 to
   -29 dBFS, against about -16 dBFS for the game's music (song1-4.ogg).  The game already plays them at 3.0 x the
   Sound slider (the float at 0x4AB3A8, used only there), which FMOD caps at full volume (255) from a third of
   the slider up, so a bigger volume number cannot make them louder.  This companion makes the three recordings
   themselves 2.5 times louder (+8 dB) as the game loads them: every 16-bit sample is multiplied by 5/2 and kept
   within -32768..32767 (with these three files nothing reaches the limit: the loudest peak becomes -1.2 dBFS).
   Every other sound, the music, the volume the game asks for and when the flutes play are unchanged.

   HOW.  Every sound effect the game loads goes through one call of FSOUND_Sample_Load (FMOD 3.74), at 0x40C4E1
   in the sound loader 0x40C490: FSOUND_Sample_Load(FSOUND_FREE, path, 0, 0, 0) through the import thunk 0x47099E.
   Mode 0 has FMOD decode the Ogg file into plain PCM in memory.  That call is pointed at load_sample (after its
   stock bytes are checked, native/shared/install_sites.h), which makes the very same call, and when the file is
   Flute1.ogg, Flute3.ogg or Flute5.ogg and the sample FMOD made is 16-bit signed PCM, locks the whole sample
   (FSOUND_Sample_Lock), scales it and unlocks it.  The game keeps each sample for the whole session (the
   preload 0x448B80 at start, or the first play 0x448C20), so a sample is scaled once; a fresh load reads the file
   again.  The game's files on disk are never changed.

   SAFETY.  The FMOD functions are found in the game's own fmod.dll at start; if any is missing, nothing is
   installed.  A sample that is not 16-bit signed PCM, or that FMOD does not hand back whole, is left as it is.
   The scaling runs under structured exception handling: a fault leaves the sample as loaded.  Nothing is written
   to a save, a villager record or a file; no text is shown.  No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"

#define LF_GAME 4                        /* The Tree of Life */
#define LF_LOAD_CALL 0x40C4E1u           /* call 0x47099E (FSOUND_Sample_Load) in the sound loader 0x40C490 */
#define LF_STOCK_LOAD 0x47099Eu          /* jmp [0x48A3xx]: fmod.dll's _FSOUND_Sample_Load@20 */
#define LF_GAIN_TIMES 5                  /* 2.5 = 5 / 2 (+8 dB) */
#define LF_GAIN_OVER 2

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
static unsigned char g_call_stock[5];
static int g_installed;
static int g_scaled;                     /* samples made louder (for the tests' emulation) */

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

static void scale(short *pcm, unsigned int count) {
    unsigned int i;
    for (i = 0; i < count; ++i) {
        int v = (int)pcm[i] * LF_GAIN_TIMES / LF_GAIN_OVER;
        pcm[i] = (short)(v > 32767 ? 32767 : (v < -32768 ? -32768 : v));
    }
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
        scale((short *)ptr1, len1 / 2u);
        if (len2 != 0) {
            scale((short *)ptr2, len2 / 2u);
        }
        ++g_scaled;
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
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
