/* VVFP Push Clouds -- "Push Clouds Away on the Overview Map", The Secret City.

   WHAT.  The Tree of Life's overview map (the Map button) has five clouds drifting left over the island, and
   they move away from the mouse: a cloud whose middle is near the cursor is pushed off, away from it, and fades
   a little each time the mouse moves there.  The Secret City's overview map has the same five drifting clouds
   (map_cloud01.png, the same 200 x 100 picture on the same 800 x 600 screen and the same map frame) but they
   ignore the mouse.  This companion gives The Secret City The Tree of Life's push, from The Tree of Life's own
   code and numbers (0x444B70, 0x444860, 0x4453C0, 0x4447A0 there):

     * on every mouse move (message 1 to the screen's event slot), for each cloud at (x, y):
         dx = x - mouse x + 90, dy = y - mouse y + 50          (the cloud's middle)
         distance = sqrt(dx*dx + dy*dy), kept as a float then truncated, as the game does
         push = (100 - distance) / 20                          (integer division, toward zero)
         push > 0:  fade -= 0.01;  vertical = dy >= 0 ? push : -push;  horizontal = dx >= 0 ? -push : 2*push
         else:      vertical = horizontal = 0
     * every frame the clouds move (the screen's update): x -= horizontal (as well as the drift the stock code
       already takes off), y += vertical -- what The Tree of Life does in one step (x -= horizontal + drift)
     * each cloud is drawn at its fade (The Tree of Life's alpha) instead of the stock 1.0
     * when the screen is shown (its activate slot) every cloud's fade is back to 1.0, as The Tree of Life's
       activate sets it.
   The push lasts until the next mouse move, as in The Tree of Life.  The drift, the wrap at the left edge and
   where a cloud comes back are The Secret City's own.

   HOW.  Three vtable slots of the overview screen class (0x49EA04: 1 events 0x46B980, 8 update 0x46C070, 9
   activate 0x46B930) and the cloud loop's draw call (0x46C3D8, the call of the sprite draw 0x42EB90) are
   replaced at run time, after every one is checked for its stock bytes, all or none
   (native/shared/install_sites.h).  No executable byte is patched.  The stock event slot still runs for every
   message (it ignores message 1); the stock update and activate run as before.  Our per-cloud state (push and
   fade) is kept here, for the screen object last seen.

   SAFETY.  Our steps run under structured exception handling: a fault leaves the clouds as the stock game
   moves and draws them.  Nothing is written to a save, a villager record or a file; no text is shown.  No
   debug output. */
#include <windows.h>
#include <math.h>
#include "../shared/install_sites.h"

#define PC_GAME 3                        /* The Secret City */
#define PC_CLOUDS 5
#define PC_CLOUD_FIRST 0x08              /* [screen+8 + 12*i]: x, y, drift (0x46BAD3, 0x46C29F) */
#define PC_CLOUD_STRIDE 12
#define PC_FADING 0x60                   /* the screen's two "leaving" bytes and their frame count (0x46C0BC) */
#define PC_LEAVING 0x61
#define PC_LEAVE_COUNT 0x68
#define PC_LEAVE_STEP 5
#define PC_LEAVE_FRAMES 200
#define PC_MESSAGE_MOVE 1

/* The Tree of Life's numbers (0x444C98..0x444D60). */
#define PC_MIDDLE_X 90
#define PC_MIDDLE_Y 50
#define PC_REACH 100
#define PC_STEP 20
#define PC_FADE_STEP 0.009999999776482582     /* the qword at 0x48EED8: (double)0.01f */

enum { SLOT_EVENTS = 1, SLOT_UPDATE = 8, SLOT_ACTIVATE = 9 };
#define PC_VTABLE 0x49EA04u
#define PC_STOCK_EVENTS 0x46B980u
#define PC_STOCK_UPDATE 0x46C070u
#define PC_STOCK_ACTIVATE 0x46B930u
#define PC_DRAW_CALL 0x46C3D8u           /* call 0x42EB90 in the cloud loop of the draw slot 0x46C2F0 */
#define PC_STOCK_DRAW 0x42EB90u
#define PC_SITES 4

typedef char (__fastcall *events_fn)(void *screen, int edx, int message, int x, int y);
typedef void (__fastcall *update_fn)(void *screen, int edx);
typedef void (__fastcall *activate_fn)(void *screen, int edx, char active);

static unsigned char *g_screen;          /* the screen our state belongs to */
static int g_across[PC_CLOUDS];          /* The Tree of Life's +0x10: taken off x every frame */
static int g_down[PC_CLOUDS];            /* its +0x0C: added to y every frame */
static float g_fade[PC_CLOUDS];          /* its +0x14: the alpha the cloud is drawn at */
static unsigned int g_draw = PC_STOCK_DRAW;   /* read by draw_cloud's jump */
static unsigned int g_expect[PC_SITES];
static unsigned int g_ours[PC_SITES];
static unsigned char g_call_stock[5];
static int g_installed;

static int *cloud(unsigned char *screen, int i) {
    return (int *)(screen + PC_CLOUD_FIRST + PC_CLOUD_STRIDE * i);
}

/* Our state is the screen's: a different screen object starts with no push and full fade. */
static void bind_screen(unsigned char *screen) {
    int i;
    if (screen == g_screen) {
        return;
    }
    for (i = 0; i < PC_CLOUDS; ++i) {
        g_across[i] = 0;
        g_down[i] = 0;
        g_fade[i] = 1.0f;
    }
    g_screen = screen;
}

/* The Tree of Life's mouse move (0x444C8F..0x444D6B), cloud by cloud. */
static void push_away(unsigned char *screen, int mouse_x, int mouse_y) {
    int i;
    bind_screen(screen);
    for (i = 0; i < PC_CLOUDS; ++i) {
        const int *c = cloud(screen, i);
        int dy = c[1] - mouse_y + PC_MIDDLE_Y;
        int dx = c[0] - mouse_x + PC_MIDDLE_X;
        float square = (float)((double)(dy * dy) + (double)(dx * dx));
        int distance = (int)(float)sqrt((double)square);
        int push = (PC_REACH - distance) / PC_STEP;
        if (push > 0) {
            g_fade[i] = (float)((double)g_fade[i] - PC_FADE_STEP);
            g_down[i] = dy >= 0 ? push : -push;
            g_across[i] = dx >= 0 ? -push : push + push;
        } else {
            g_down[i] = 0;
            g_across[i] = 0;
        }
    }
}

/* The stock update moves the clouds (x -= drift, then the wrap) unless the screen is leaving and this frame
   ends it: then it returns before the clouds (0x46C0BC..0x46C0FB). */
static int clouds_move(const unsigned char *screen) {
    if (screen[PC_LEAVING] == 0 && screen[PC_FADING] == 0) {
        return 1;
    }
    return *(const int *)(screen + PC_LEAVE_COUNT) + PC_LEAVE_STEP <= PC_LEAVE_FRAMES;
}

static char __fastcall events(unsigned char *screen, int edx, int message, int x, int y) {
    (void)edx;
    if (message == PC_MESSAGE_MOVE) {
        __try {
            push_away(screen, x, y);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
    return ((events_fn)(UINT_PTR)PC_STOCK_EVENTS)(screen, 0, message, x, y);
}

static void __fastcall update(unsigned char *screen, int edx) {
    (void)edx;
    __try {
        bind_screen(screen);
        if (clouds_move(screen)) {
            int i;
            for (i = 0; i < PC_CLOUDS; ++i) {
                int *c = cloud(screen, i);
                c[0] -= g_across[i];
                c[1] += g_down[i];
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    ((update_fn)(UINT_PTR)PC_STOCK_UPDATE)(screen, 0);
}

static void __fastcall activate(unsigned char *screen, int edx, char active) {
    (void)edx;
    ((activate_fn)(UINT_PTR)PC_STOCK_ACTIVATE)(screen, 0, active);
    __try {
        int i;
        bind_screen(screen);
        for (i = 0; i < PC_CLOUDS; ++i) {
            g_fade[i] = 1.0f;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* The alpha for the cloud loop's draw: esi is the screen, edi the cloud (0x46C3BD). */
static unsigned int __cdecl fade_of(unsigned char *screen, unsigned char *at) {
    float alpha = 1.0f;
    __try {
        int i;
        for (i = 0; i < PC_CLOUDS; ++i) {
            if (screen == g_screen && at == (unsigned char *)cloud(screen, i)) {
                alpha = g_fade[i];
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return *(unsigned int *)&alpha;
}

/* In place of the call of the sprite draw (sprite, x, y, alpha, 100; ecx the renderer): the alpha argument
   becomes the cloud's fade, then the stock draw runs with the stock return address. */
__declspec(naked) static void draw_cloud(void) {
    __asm {
        push ecx
        push edi
        push esi
        call fade_of
        add esp, 8
        pop ecx
        mov dword ptr [esp + 0x10], eax
        jmp dword ptr [g_draw]
    }
}

static void add_slot(vvfp_site_write *w, int n, int slot, unsigned int stock, const void *ours) {
    g_expect[n] = stock;
    g_ours[n] = (unsigned int)(UINT_PTR)ours;
    vvfp_site_bytes(&w[n], PC_VTABLE + 4u * (unsigned int)slot, 4, (const unsigned char *)&g_expect[n],
                    (const unsigned char *)&g_ours[n]);
}

/* 1 when every site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpPushCloudsInstalled(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write sites[PC_SITES];
    unsigned int rel = PC_STOCK_DRAW - (PC_DRAW_CALL + 5u);
    (void)shipped;
    if (g_installed || game != PC_GAME) {
        return;
    }
    add_slot(sites, 0, SLOT_EVENTS, PC_STOCK_EVENTS, (const void *)events);
    add_slot(sites, 1, SLOT_UPDATE, PC_STOCK_UPDATE, (const void *)update);
    add_slot(sites, 2, SLOT_ACTIVATE, PC_STOCK_ACTIVATE, (const void *)activate);
    g_call_stock[0] = 0xE8;
    memcpy(g_call_stock + 1, &rel, 4);
    vvfp_site_branch(&sites[3], PC_DRAW_CALL, 5, g_call_stock, 0xE8, (const void *)draw_cloud);
    if (vvfp_install_sites(sites, PC_SITES)) {
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
