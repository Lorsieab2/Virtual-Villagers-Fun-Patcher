/* vv4k_gpu_probe -- the facts the 4K filter design rests on, measured with the games' own SDL2.dll (research
   prototype, not shipped).

   usage: vv4k_gpu_probe.exe <folder holding SDL2.dll> <vv4k_shaders.hlsl> <frame.argb> <w> <h> <out w> <out h>
                             <out prefix>

   Everything happens in HIDDEN windows of this process (Direct3D does not start on a private desktop); nothing is
   shown, no game runs.  It prints:
     1. SDL's render drivers and the renderer the games' own call SDL_CreateRenderer(window, -1, 0) picks;
     2. whether SDL_RenderGetD3D9Device gives SDL's device;
     3. the mouse: what a WM_MOUSEMOVE / WM_LBUTTONDOWN at window pixel (x, y) becomes, both in the SDL event and in
        SDL_GetMouseState (which is what the games read), at 1:1, 2x and letterboxed 1920x1080;
     4. the GPU filter (vv4k_shaders.hlsl, compiled at run time here), edge-directed 4x and 2x, on (a) a Direct3D
        9Ex device of our own on every Direct3D 9 adapter and (c) SDL's own device: milliseconds per frame (upload +
        passes, waited for), GPU time per pass, and the GPU picture compared with the CPU reference (vv4k_filters.c),
        written to <out prefix>.gpu-4x.argb / .gpu-2x.argb. */
#define COBJMACROS
#define INITGUID
#include <windows.h>
#include <d3d9.h>
#include <d3dcompiler.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vv4k_filters.h"

/* ---- SDL 2.0.3 entry points (the games' own SDL2.dll) ---- */
typedef struct {
    const char *name;
    unsigned int flags, num_texture_formats, texture_formats[16];
    int max_texture_width, max_texture_height;
} sdl_renderer_info;
typedef struct {
    int x, y, w, h;
} sdl_rect;
typedef int(__cdecl *init_fn)(unsigned int);
typedef void *(__cdecl *create_window_fn)(const char *, int, int, int, int, unsigned int);
typedef void *(__cdecl *create_renderer_fn)(void *, int, unsigned int);
typedef void *(__cdecl *create_texture_fn)(void *, unsigned int, int, int, int);
typedef int(__cdecl *int_ptr_fn)(void *);
typedef int(__cdecl *num_drivers_fn)(void);
typedef int(__cdecl *driver_info_fn)(int, sdl_renderer_info *);
typedef int(__cdecl *renderer_info_fn)(void *, sdl_renderer_info *);
typedef int(__cdecl *hint_fn)(const char *, const char *);
typedef int(__cdecl *logical_fn)(void *, int, int);
typedef void(__cdecl *window_size_fn)(void *, int, int);
typedef int(__cdecl *poll_fn)(void *);
typedef unsigned int(__cdecl *mouse_state_fn)(int *, int *);
typedef int(__cdecl *wm_info_fn)(void *, void *);
typedef void *(__cdecl *get_d3d9_fn)(void *);
typedef int(__cdecl *update_texture_fn)(void *, const sdl_rect *, const void *, int);
typedef int(__cdecl *render_copy_fn)(void *, void *, const sdl_rect *, const sdl_rect *);
typedef int(__cdecl *read_pixels_fn)(void *, const sdl_rect *, unsigned int, void *, int);
typedef const char *(__cdecl *error_fn)(void);
typedef void(__cdecl *viewport_fn)(void *, sdl_rect *);
typedef void(__cdecl *scale_fn)(void *, float *, float *);
typedef int(__cdecl *peep_fn)(void *, int, int, unsigned int, unsigned int);
static peep_fn s_peep;

static init_fn s_init;
static create_window_fn s_create_window;
static create_renderer_fn s_create_renderer;
static create_texture_fn s_create_texture;
static num_drivers_fn s_num_drivers;
static driver_info_fn s_driver_info;
static renderer_info_fn s_renderer_info;
static hint_fn s_hint;
static logical_fn s_logical;
static window_size_fn s_window_size;
static poll_fn s_poll;
static mouse_state_fn s_mouse_state;
static wm_info_fn s_wm_info;
static get_d3d9_fn s_get_d3d9;
static int_ptr_fn s_render_clear, s_render_present;
static update_texture_fn s_update_texture;
static render_copy_fn s_render_copy;
static read_pixels_fn s_read_pixels;
static error_fn s_error;
static viewport_fn s_viewport;
static scale_fn s_scale;

#define SDL_PIXELFORMAT_ARGB8888 0x16362004u
#define SDL_WINDOW_HIDDEN 0x8u
#define SDL_WINDOW_RESIZABLE 0x20u
#define SDL_MOUSEMOTION 0x400u
#define SDL_MOUSEBUTTONDOWN 0x401u

static double now_ms(void) {
    LARGE_INTEGER f, c;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    return 1000.0 * (double)c.QuadPart / (double)f.QuadPart;
}

static int load_sdl(const char *folder) {
    char path[MAX_PATH * 2];
    HMODULE sdl;
    sprintf_s(path, sizeof path, "%s\\SDL2.dll", folder);
    sdl = LoadLibraryA(path);
    if (sdl == NULL) {
        printf("FAIL load %s (%lu)\n", path, GetLastError());
        return 0;
    }
#define GET(var, type, name)                                                                                         \
    var = (type)GetProcAddress(sdl, name);                                                                           \
    if (var == NULL) {                                                                                               \
        printf("FAIL export %s\n", name);                                                                            \
        return 0;                                                                                                    \
    }
    GET(s_init, init_fn, "SDL_Init")
    GET(s_create_window, create_window_fn, "SDL_CreateWindow")
    GET(s_create_renderer, create_renderer_fn, "SDL_CreateRenderer")
    GET(s_create_texture, create_texture_fn, "SDL_CreateTexture")
    GET(s_num_drivers, num_drivers_fn, "SDL_GetNumRenderDrivers")
    GET(s_driver_info, driver_info_fn, "SDL_GetRenderDriverInfo")
    GET(s_renderer_info, renderer_info_fn, "SDL_GetRendererInfo")
    GET(s_hint, hint_fn, "SDL_SetHint")
    GET(s_logical, logical_fn, "SDL_RenderSetLogicalSize")
    GET(s_window_size, window_size_fn, "SDL_SetWindowSize")
    GET(s_poll, poll_fn, "SDL_PollEvent")
    GET(s_mouse_state, mouse_state_fn, "SDL_GetMouseState")
    GET(s_wm_info, wm_info_fn, "SDL_GetWindowWMInfo")
    GET(s_get_d3d9, get_d3d9_fn, "SDL_RenderGetD3D9Device")
    GET(s_render_clear, int_ptr_fn, "SDL_RenderClear")
    GET(s_render_present, int_ptr_fn, "SDL_RenderPresent")
    GET(s_update_texture, update_texture_fn, "SDL_UpdateTexture")
    GET(s_render_copy, render_copy_fn, "SDL_RenderCopy")
    GET(s_read_pixels, read_pixels_fn, "SDL_RenderReadPixels")
    GET(s_error, error_fn, "SDL_GetError")
    GET(s_viewport, viewport_fn, "SDL_RenderGetViewport")
    GET(s_scale, scale_fn, "SDL_RenderGetScale")
    GET(s_peep, peep_fn, "SDL_PeepEvents")
#undef GET
    return 1;
}

static void drain(void) {
    unsigned char event[64];
    MSG message;
    while (PeekMessageW(&message, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
    while (s_poll(event)) {
    }
}

/* One mouse message at window pixel (x, y): the SDL event's x, y and SDL_GetMouseState afterwards. */
static void mouse_at(HWND hwnd, UINT message, int x, int y, const char *where) {
    unsigned char event[64];
    int ex = -99999, ey = -99999, mx = -1, my = -1;
    drain();
    /* Read right after SDL handled the message: no pumping (it would also hand SDL the WM_MOUSELEAVE that Windows
       posts to a hidden window, and SDL answers that with the real cursor's place). */
    SendMessageW(hwnd, message, message == WM_LBUTTONDOWN ? MK_LBUTTON : 0, MAKELPARAM(x, y));
    s_mouse_state(&mx, &my);
    if (s_peep(event, 1, 2 /* SDL_GETEVENT */, message == WM_MOUSEMOVE ? SDL_MOUSEMOTION : SDL_MOUSEBUTTONDOWN,
               message == WM_MOUSEMOVE ? SDL_MOUSEMOTION : SDL_MOUSEBUTTONDOWN) == 1) {
        ex = *(int *)(event + 20);
        ey = *(int *)(event + 24);
    }
    printf("   %-44s window (%4d,%4d) -> SDL event (%5d,%5d), SDL_GetMouseState (%4d,%4d)\n", where, x, y, ex, ey, mx,
           my);
    if (message == WM_LBUTTONDOWN) {
        SendMessageW(hwnd, WM_LBUTTONUP, 0, MAKELPARAM(x, y));
        drain();
    }
}

/* ---- the GPU pipeline ---- */
typedef struct {
    IDirect3DDevice9 *dev;
    IDirect3DVertexShader9 *vs;
    IDirect3DPixelShader9 *step1, *step2, *fit, *fit_rows, *fit_columns;
    IDirect3DTexture9 *frame, *lattice2, *doubled2, *lattice4, *doubled4, *mid, *output;
    IDirect3DSurface9 *readback;
    int w, h, out_w, out_h, stages;   /* stages: 2 = the edge-directed 2x twice (4x), 1 = once (2x) */
    int separable;                    /* the fit in two passes (rows, columns) instead of one */
} pipeline;

static pD3DCompile s_compile;

static const char *g_hlsl;

static void *compile(const char *entry, const char *profile) {
    ID3DBlob *code = NULL, *errors = NULL;
    HRESULT hr = s_compile(g_hlsl, strlen(g_hlsl), "vv4k_shaders.hlsl", NULL, NULL, entry, profile,
                           D3DCOMPILE_OPTIMIZATION_LEVEL3, 0, &code, &errors);
    if (FAILED(hr)) {
        printf("FAIL compile %s: %s\n", entry, errors ? (const char *)ID3D10Blob_GetBufferPointer(errors) : "?");
        return NULL;
    }
    if (errors) {
        ID3D10Blob_Release(errors);
    }
    return code;
}

static int make_rt(IDirect3DDevice9 *dev, int w, int h, IDirect3DTexture9 **tex) {
    return SUCCEEDED(IDirect3DDevice9_CreateTexture(dev, w, h, 1, D3DUSAGE_RENDERTARGET, D3DFMT_A8R8G8B8,
                                                    D3DPOOL_DEFAULT, tex, NULL));
}

static int pipeline_make(pipeline *p, IDirect3DDevice9 *dev, int w, int h, int out_w, int out_h, int stages) {
    ID3DBlob *b;
    memset(p, 0, sizeof *p);
    p->stages = stages;
    p->dev = dev;
    p->w = w;
    p->h = h;
    p->out_w = out_w;
    p->out_h = out_h;
#define SHADER(entry, profile, kind, field)                                                                          \
    if ((b = (ID3DBlob *)compile(entry, profile)) == NULL) return 0;                                                 \
    if (FAILED(IDirect3DDevice9_Create##kind##Shader(dev, (const DWORD *)ID3D10Blob_GetBufferPointer(b), &p->field))) \
        return 0;                                                                                                    \
    ID3D10Blob_Release(b);
    SHADER("vs_quad", "vs_3_0", Vertex, vs)
    SHADER("ed_step1", "ps_3_0", Pixel, step1)
    SHADER("ed_step2", "ps_3_0", Pixel, step2)
    SHADER("fit", "ps_3_0", Pixel, fit)
    SHADER("fit_rows", "ps_3_0", Pixel, fit_rows)
    SHADER("fit_columns", "ps_3_0", Pixel, fit_columns)
#undef SHADER
    /* the rows pass keeps full precision and the overshoot (as the CPU's float rows) */
    if (FAILED(IDirect3DDevice9_CreateTexture(dev, out_w, h << stages, 1, D3DUSAGE_RENDERTARGET, D3DFMT_A16B16G16R16F,
                                              D3DPOOL_DEFAULT, &p->mid, NULL)))
        return 0;
    if (FAILED(IDirect3DDevice9_CreateTexture(dev, w, h, 1, D3DUSAGE_DYNAMIC, D3DFMT_A8R8G8B8, D3DPOOL_DEFAULT,
                                              &p->frame, NULL)))
        return 0;
    if (!make_rt(dev, 2 * w, 2 * h, &p->lattice2) || !make_rt(dev, 2 * w, 2 * h, &p->doubled2) ||
        (stages == 2 && (!make_rt(dev, 4 * w, 4 * h, &p->lattice4) || !make_rt(dev, 4 * w, 4 * h, &p->doubled4))) ||
        !make_rt(dev, out_w, out_h, &p->output))
        return 0;
    if (FAILED(IDirect3DDevice9_CreateOffscreenPlainSurface(dev, out_w, out_h, D3DFMT_A8R8G8B8, D3DPOOL_SYSTEMMEM,
                                                            &p->readback, NULL)))
        return 0;
    return 1;
}

static void release(void *unknown) {
    if (unknown != NULL) {
        IUnknown_Release((IUnknown *)unknown);
    }
}

static void pipeline_free(pipeline *p) {
    release(p->readback);
    release(p->output);
    release(p->mid);
    release(p->fit_columns);
    release(p->fit_rows);
    release(p->doubled4);
    release(p->lattice4);
    release(p->doubled2);
    release(p->lattice2);
    release(p->frame);
    release(p->fit);
    release(p->step2);
    release(p->step1);
    release(p->vs);
    memset(p, 0, sizeof *p);
}

static void draw_pass(pipeline *p, IDirect3DPixelShader9 *ps, IDirect3DTexture9 *from, int from_w, int from_h,
                      IDirect3DSurface9 *to) {
    static const float quad[4][4] = {{-2, 2, 0.5f, 1}, {2, 2, 0.5f, 1}, {-2, -2, 0.5f, 1}, {2, -2, 0.5f, 1}};
    float size[4];
    size[0] = (float)from_w;
    size[1] = (float)from_h;
    size[2] = 1.0f / from_w;
    size[3] = 1.0f / from_h;
    IDirect3DDevice9_SetRenderTarget(p->dev, 0, to);
    IDirect3DDevice9_SetPixelShader(p->dev, ps);
    IDirect3DDevice9_SetTexture(p->dev, 0, (IDirect3DBaseTexture9 *)from);
    IDirect3DDevice9_SetPixelShaderConstantF(p->dev, 0, size, 1);
    IDirect3DDevice9_DrawPrimitiveUP(p->dev, D3DPT_TRIANGLESTRIP, 2, quad, sizeof quad[0]);
}

static void pass_to_texture(pipeline *p, IDirect3DPixelShader9 *ps, IDirect3DTexture9 *from, int fw, int fh,
                            IDirect3DTexture9 *to) {
    IDirect3DSurface9 *surface;
    IDirect3DTexture9_GetSurfaceLevel(to, 0, &surface);
    draw_pass(p, ps, from, fw, fh, surface);
    IDirect3DSurface9_Release(surface);
}

/* Optional GPU timestamps: g_stamps[0] before the passes, [1..5] after each pass. */
static IDirect3DQuery9 *g_stamps[6];

static void stamp(int n) {
    if (g_stamps[n] != NULL) {
        IDirect3DQuery9_Issue(g_stamps[n], D3DISSUE_END);
    }
}

/* Upload the frame, the four edge-directed passes, the fit into `target` (NULL: our output texture). */
static int pipeline_run(pipeline *p, const vv4k_image *frame, IDirect3DSurface9 *target) {
    D3DLOCKED_RECT locked;
    IDirect3DSurface9 *out = target;
    float consts[3][4];
    int fx, fy, fw, fh, y;
    double ratio, stretch, support;
    if (FAILED(IDirect3DTexture9_LockRect(p->frame, 0, &locked, NULL, D3DLOCK_DISCARD))) {
        return 0;
    }
    for (y = 0; y < p->h; ++y) {
        memcpy((char *)locked.pBits + (size_t)y * locked.Pitch, frame->pixels + (size_t)y * p->w, (size_t)p->w * 4);
    }
    IDirect3DTexture9_UnlockRect(p->frame, 0);

    IDirect3DDevice9_BeginScene(p->dev);
    IDirect3DDevice9_SetVertexShader(p->dev, p->vs);
    IDirect3DDevice9_SetFVF(p->dev, D3DFVF_XYZW);
    IDirect3DDevice9_SetRenderState(p->dev, D3DRS_CULLMODE, D3DCULL_NONE);
    IDirect3DDevice9_SetRenderState(p->dev, D3DRS_ZENABLE, D3DZB_FALSE);
    IDirect3DDevice9_SetRenderState(p->dev, D3DRS_ALPHABLENDENABLE, FALSE);
    IDirect3DDevice9_SetRenderState(p->dev, D3DRS_SCISSORTESTENABLE, FALSE);
    IDirect3DDevice9_SetRenderState(p->dev, D3DRS_COLORWRITEENABLE, 0xF);
    IDirect3DDevice9_SetSamplerState(p->dev, 0, D3DSAMP_MINFILTER, D3DTEXF_POINT);
    IDirect3DDevice9_SetSamplerState(p->dev, 0, D3DSAMP_MAGFILTER, D3DTEXF_POINT);
    IDirect3DDevice9_SetSamplerState(p->dev, 0, D3DSAMP_MIPFILTER, D3DTEXF_NONE);
    IDirect3DDevice9_SetSamplerState(p->dev, 0, D3DSAMP_ADDRESSU, D3DTADDRESS_CLAMP);
    IDirect3DDevice9_SetSamplerState(p->dev, 0, D3DSAMP_ADDRESSV, D3DTADDRESS_CLAMP);
    IDirect3DDevice9_SetSamplerState(p->dev, 0, D3DSAMP_SRGBTEXTURE, FALSE);
    IDirect3DDevice9_SetRenderState(p->dev, D3DRS_SRGBWRITEENABLE, FALSE);

    stamp(0);
    pass_to_texture(p, p->step1, p->frame, p->w, p->h, p->lattice2);
    stamp(1);
    pass_to_texture(p, p->step2, p->lattice2, 2 * p->w, 2 * p->h, p->doubled2);
    stamp(2);
    if (p->stages == 2) {
        pass_to_texture(p, p->step1, p->doubled2, 2 * p->w, 2 * p->h, p->lattice4);
    }
    stamp(3);
    if (p->stages == 2) {
        pass_to_texture(p, p->step2, p->lattice4, 4 * p->w, 4 * p->h, p->doubled4);
    }
    stamp(4);

    vv4k_fit_rect(p->w, p->h, p->out_w, p->out_h, &fx, &fy, &fw, &fh);
    ratio = (double)fh / (p->h * (p->stages == 2 ? 4.0 : 2.0));
    stretch = ratio < 1.0 ? ratio : 1.0;
    support = 2.0 / stretch;
    consts[0][0] = (float)fx;
    consts[0][1] = (float)fy;
    consts[0][2] = (float)fw;
    consts[0][3] = (float)fh;
    consts[1][0] = (float)p->w;
    consts[1][1] = (float)p->h;
    consts[1][2] = p->stages == 2 ? 4.0f : 2.0f;
    consts[1][3] = p->stages == 2 ? -1.5f : -0.5f;
    consts[2][0] = (float)stretch;
    consts[2][1] = (float)support;
    consts[2][2] = (float)min(8, (int)ceil(2.0 * support));
    consts[2][3] = 0.0f;
    IDirect3DDevice9_SetPixelShaderConstantF(p->dev, 1, &consts[0][0], 3);
    if (out == NULL) {
        IDirect3DTexture9_GetSurfaceLevel(p->output, 0, &out);
    }
    {
        IDirect3DTexture9 *big = p->stages == 2 ? p->doubled4 : p->doubled2;
        int bw = p->w << p->stages, bh = p->h << p->stages;
        if (p->separable) {
            pass_to_texture(p, p->fit_rows, big, bw, bh, p->mid);
            draw_pass(p, p->fit_columns, p->mid, p->out_w, bh, out);
        } else {
            draw_pass(p, p->fit, big, bw, bh, out);
        }
    }
    stamp(5);
    if (target == NULL) {
        IDirect3DSurface9_Release(out);
    }
    IDirect3DDevice9_EndScene(p->dev);
    return 1;
}

static void gpu_wait(IDirect3DDevice9 *dev) {
    IDirect3DQuery9 *query = NULL;
    if (SUCCEEDED(IDirect3DDevice9_CreateQuery(dev, D3DQUERYTYPE_EVENT, &query))) {
        IDirect3DQuery9_Issue(query, D3DISSUE_END);
        while (IDirect3DQuery9_GetData(query, NULL, 0, D3DGETDATA_FLUSH) == S_FALSE) {
        }
        IDirect3DQuery9_Release(query);
    }
}

/* Times `frames` frames (each waited for), then reads the picture back and compares it with the CPU reference. */
static void pipeline_measure(pipeline *p, const vv4k_image *frame, const vv4k_image *reference, int frames,
                             const char *label, const char *out_path) {
    double t0, best = 1e30, total = 0;
    int i, max_diff = 0;
    long long over2 = 0;
    D3DLOCKED_RECT locked;
    IDirect3DSurface9 *surface;
    for (i = 0; i < frames + 10; ++i) {
        t0 = now_ms();
        if (!pipeline_run(p, frame, NULL)) {
            printf("FAIL %s run\n", label);
            return;
        }
        gpu_wait(p->dev);
        t0 = now_ms() - t0;
        if (i >= 10) {   /* the first frames warm the driver and the GPU clock up */
            total += t0;
            if (t0 < best) best = t0;
        }
    }
    printf("   %-34s %dx%d -> %dx%d: %.2f ms a frame on average, best %.2f ms (%d frames, upload + 5 passes, "
           "waited for)\n",
           label, p->w, p->h, p->out_w, p->out_h, total / frames, best, frames);
    {
        /* GPU time of each pass (timestamp queries, 20 frames). */
        IDirect3DQuery9 *disjoint = NULL, *freq = NULL;
        UINT64 f = 0, t[6];
        double sums[5] = {0, 0, 0, 0, 0};
        int n, k, ok = 1;
        static const char *names[5] = {"2x step 1", "2x step 2", "4x step 1", "4x step 2", "fit"};
        if (FAILED(IDirect3DDevice9_CreateQuery(p->dev, D3DQUERYTYPE_TIMESTAMPDISJOINT, &disjoint)) ||
            FAILED(IDirect3DDevice9_CreateQuery(p->dev, D3DQUERYTYPE_TIMESTAMPFREQ, &freq))) {
            ok = 0;
        }
        for (k = 0; ok && k < 6; ++k) {
            if (FAILED(IDirect3DDevice9_CreateQuery(p->dev, D3DQUERYTYPE_TIMESTAMP, &g_stamps[k]))) ok = 0;
        }
        for (n = 0; ok && n < 20; ++n) {
            BOOL dis = TRUE;
            IDirect3DQuery9_Issue(disjoint, D3DISSUE_BEGIN);
            pipeline_run(p, frame, NULL);
            IDirect3DQuery9_Issue(disjoint, D3DISSUE_END);
            IDirect3DQuery9_Issue(freq, D3DISSUE_END);
            while (IDirect3DQuery9_GetData(disjoint, &dis, sizeof dis, D3DGETDATA_FLUSH) == S_FALSE) {
            }
            while (IDirect3DQuery9_GetData(freq, &f, sizeof f, D3DGETDATA_FLUSH) == S_FALSE) {
            }
            for (k = 0; k < 6; ++k) {
                while (IDirect3DQuery9_GetData(g_stamps[k], &t[k], sizeof t[k], D3DGETDATA_FLUSH) == S_FALSE) {
                }
            }
            for (k = 0; k < 5 && !dis && f; ++k) sums[k] += 1000.0 * (double)(t[k + 1] - t[k]) / (double)f;
        }
        if (ok) {
            printf("   %-34s GPU time per pass:", label);
            for (k = 0; k < 5; ++k) printf(" %s %.2f ms;", names[k], sums[k] / 20);
            printf("\n");
        } else {
            printf("   %-34s (timestamp queries not available)\n", label);
        }
        for (k = 0; k < 6; ++k) {
            release(g_stamps[k]);
            g_stamps[k] = NULL;
        }
        release(disjoint);
        release(freq);
    }
    IDirect3DTexture9_GetSurfaceLevel(p->output, 0, &surface);
    IDirect3DDevice9_GetRenderTargetData(p->dev, surface, p->readback);
    IDirect3DSurface9_Release(surface);
    if (SUCCEEDED(IDirect3DSurface9_LockRect(p->readback, &locked, NULL, D3DLOCK_READONLY))) {
        FILE *file = NULL;
        int y, x;
        if (out_path != NULL) {
            fopen_s(&file, out_path, "wb");
        }
        for (y = 0; y < p->out_h; ++y) {
            const uint32_t *row = (const uint32_t *)((const char *)locked.pBits + (size_t)y * locked.Pitch);
            if (file) fwrite(row, 4, (size_t)p->out_w, file);
            for (x = 0; x < p->out_w; ++x) {
                uint32_t a = row[x], b = reference->pixels[(size_t)y * p->out_w + x];
                int c, worst = 0;
                for (c = 0; c < 24; c += 8) {
                    int d = abs((int)((a >> c) & 0xFF) - (int)((b >> c) & 0xFF));
                    if (d > worst) worst = d;
                }
                if (worst > max_diff) max_diff = worst;
                if (worst > 2) ++over2;
            }
        }
        if (file) fclose(file);
        IDirect3DSurface9_UnlockRect(p->readback);
        printf("   %-34s GPU picture vs CPU reference: largest difference %d/255, %.4f%% of pixels differ by more "
               "than 2\n",
               label, max_diff, 100.0 * (double)over2 / ((double)p->out_w * p->out_h));
    }
}

static char *read_file(const char *path, size_t *size) {
    FILE *file;
    char *data;
    long n;
    if (fopen_s(&file, path, "rb") != 0 || file == NULL) return NULL;
    fseek(file, 0, SEEK_END);
    n = ftell(file);
    fseek(file, 0, SEEK_SET);
    data = (char *)malloc((size_t)n + 1);
    if (data == NULL) {
        fclose(file);
        return NULL;
    }
    *size = fread(data, 1, (size_t)n, file);
    data[*size] = 0;
    fclose(file);
    return data;
}

static LRESULT CALLBACK plain_proc(HWND w, UINT m, WPARAM wp, LPARAM lp) {
    return DefWindowProcW(w, m, wp, lp);
}

int main(int argc, char **argv) {
    vv4k_image frame, reference;
    unsigned char info[64];
    sdl_renderer_info rinfo;
    void *window, *renderer, *texture;
    HWND hwnd;
    IDirect3DDevice9 *sdl_dev;
    const char *hlsl_path;
    size_t size;
    FILE *file;
    int i, w, h, out_w, out_h;
    char path[1024];

    if (argc < 9) {
        printf("usage: vv4k_gpu_probe <SDL2.dll folder> <vv4k_shaders.hlsl> <frame.argb> <w> <h> <out w> <out h> "
               "<out prefix>\n");
        return 2;
    }
    hlsl_path = argv[2];
    w = atoi(argv[4]);
    h = atoi(argv[5]);
    out_w = atoi(argv[6]);
    out_h = atoi(argv[7]);
    if (vv4k_alloc(&frame, w, h) != 0 || vv4k_alloc(&reference, out_w, out_h) != 0) return 3;
    if (fopen_s(&file, argv[3], "rb") != 0 || file == NULL) return 4;
    fread(frame.pixels, 4, (size_t)w * h, file);
    fclose(file);
    g_hlsl = read_file(hlsl_path, &size);
    if (g_hlsl == NULL) {
        printf("FAIL read %s\n", hlsl_path);
        return 5;
    }
    s_compile = (pD3DCompile)GetProcAddress(LoadLibraryA("d3dcompiler_47.dll"), "D3DCompile");
    if (s_compile == NULL || !load_sdl(argv[1])) return 6;
    /* The games are not DPI aware (no manifest entry); this probe is, so window sizes are real pixels. */
    SetProcessDPIAware();

    printf("== 1. SDL 2.0.3's renderers\n");
    for (i = 0; i < s_num_drivers(); ++i) {
        s_driver_info(i, &rinfo);
        printf("   driver %d: %s (flags 0x%x)\n", i, rinfo.name, rinfo.flags);
    }
    if (s_init(0x20u) != 0) {
        printf("FAIL SDL_Init: %s\n", s_error());
        return 7;
    }
    /* As the games (0x408480 in New Believers): a resizable window of the game's size (hidden here), renderer -1 / 0,
       a streaming ARGB8888 texture, the "linear" hint AFTER the texture, the logical size. */
    window = s_create_window("vv4k_gpu_probe", 0x2FFF0000, 0x2FFF0000, w, h, SDL_WINDOW_RESIZABLE | SDL_WINDOW_HIDDEN);
    renderer = window ? s_create_renderer(window, -1, 0) : NULL;
    if (renderer == NULL) {
        printf("FAIL renderer: %s\n", s_error());
        return 8;
    }
    texture = s_create_texture(renderer, SDL_PIXELFORMAT_ARGB8888, 1, w, h);
    s_hint("SDL_RENDER_SCALE_QUALITY", "linear");
    s_logical(renderer, w, h);
    s_renderer_info(renderer, &rinfo);
    printf("   the games' SDL_CreateRenderer(window, -1, 0) picks: %s (flags 0x%x, largest texture %dx%d)\n", rinfo.name,
           rinfo.flags, rinfo.max_texture_width, rinfo.max_texture_height);
    memset(info, 0, sizeof info);
    info[0] = 2;
    info[2] = 3;
    s_wm_info(window, info);
    hwnd = *(HWND *)(info + 8);

    printf("== 2. SDL_RenderGetD3D9Device\n");
    sdl_dev = (IDirect3DDevice9 *)s_get_d3d9(renderer);
    printf("   SDL_RenderGetD3D9Device -> %p\n", (void *)sdl_dev);
    if (sdl_dev) {
        IDirect3D9 *d3d = NULL;
        D3DADAPTER_IDENTIFIER9 id;
        D3DDEVICE_CREATION_PARAMETERS cp;
        IDirect3DDevice9_GetDirect3D(sdl_dev, &d3d);
        IDirect3DDevice9_GetCreationParameters(sdl_dev, &cp);
        IDirect3D9_GetAdapterIdentifier(d3d, cp.AdapterOrdinal, 0, &id);
        printf("   SDL's device: adapter %u \"%s\", behavior flags 0x%lx (FPU_PRESERVE %s)\n", cp.AdapterOrdinal,
               id.Description, cp.BehaviorFlags, (cp.BehaviorFlags & D3DCREATE_FPU_PRESERVE) ? "yes" : "no");
        IDirect3D9_Release(d3d);
    }

    printf("== 3. the mouse (the games read SDL_GetMouseState on every mouse event)\n");
    {
        sdl_rect vp;
        float sx, sy;
        int sizes[3][2];
        int k;
        sizes[0][0] = w; sizes[0][1] = h;
        sizes[1][0] = 3 * w / 2; sizes[1][1] = 3 * h / 2;
        sizes[2][0] = 1920; sizes[2][1] = 1080;
        for (k = 0; k < 3; ++k) {
            s_window_size(window, sizes[k][0], sizes[k][1]);
            drain();
            s_render_clear(renderer);   /* SDL applies a new size at the next drawing call */
            s_render_present(renderer);
            s_viewport(renderer, &vp);
            s_scale(renderer, &sx, &sy);
            printf("  window %dx%d: SDL viewport %d,%d %dx%d (logical units), scale %.4f x %.4f\n", sizes[k][0],
                   sizes[k][1], vp.x, vp.y, vp.w, vp.h, sx, sy);
            mouse_at(hwnd, WM_MOUSEMOVE, sizes[k][0] / 2, sizes[k][1] / 2, "move, middle of the window");
            mouse_at(hwnd, WM_MOUSEMOVE, sizes[k][0] - 3, sizes[k][1] - 3, "move, bottom right corner");
            mouse_at(hwnd, WM_LBUTTONDOWN, 10, sizes[k][1] / 2, "left button, 10 px from the left edge");
        }
        s_window_size(window, w, h);
        drain();
        s_render_clear(renderer);
        s_render_present(renderer);
    }

    printf("== 4. the GPU filter (vv4k_shaders.hlsl), %dx%d -> %dx%d\n", w, h, out_w, out_h);
    {
        IDirect3D9Ex *d3d = NULL;
        WNDCLASSW wc;
        HWND own;
        int stages;
        UINT adapter, adapters = 0;
        memset(&wc, 0, sizeof wc);
        wc.lpfnWndProc = plain_proc;
        wc.hInstance = GetModuleHandleW(NULL);
        wc.lpszClassName = L"vv4k_probe";
        RegisterClassW(&wc);
        /* A hidden window of our own: the device's window (never shown). */
        own = CreateWindowExW(0, L"vv4k_probe", L"vv4k_probe", WS_POPUP, 0, 0, out_w, out_h, NULL, NULL,
                              wc.hInstance, NULL);
        if (FAILED(Direct3DCreate9Ex(D3D_SDK_VERSION, &d3d))) {
            printf("FAIL Direct3DCreate9Ex\n");
        } else {
            adapters = IDirect3D9Ex_GetAdapterCount(d3d);
            for (adapter = 0; adapter < adapters; ++adapter) {
                D3DADAPTER_IDENTIFIER9 id;
                IDirect3D9Ex_GetAdapterIdentifier(d3d, adapter, 0, &id);
                printf("   Direct3D 9 adapter %u: \"%s\"\n", adapter, id.Description);
            }
        }
        for (stages = 2; stages >= 1; --stages) {
            double t0 = now_ms();
            vv4k_render(stages == 2 ? VV4K_EDGE_DIRECTED : VV4K_EDGE_DIRECTED_2X, &frame, &reference);
            printf("  -- edge-directed %s, then the fit\n   CPU reference (option b, one thread, not optimised): "
                   "%.1f ms\n",
                   stages == 2 ? "4x (2x twice)" : "2x (once)", now_ms() - t0);
            for (adapter = 0; d3d != NULL && adapter < adapters; ++adapter) {
                /* (a) a Direct3D 9Ex device of our own, FPU preserved like SDL's. */
                IDirect3DDevice9Ex *dev = NULL;
                D3DPRESENT_PARAMETERS pp;
                char label[64];
                pipeline p;
                memset(&pp, 0, sizeof pp);
                pp.Windowed = TRUE;
                pp.SwapEffect = D3DSWAPEFFECT_DISCARD;
                pp.BackBufferFormat = D3DFMT_X8R8G8B8;
                pp.BackBufferWidth = out_w;
                pp.BackBufferHeight = out_h;
                pp.BackBufferCount = 1;
                pp.hDeviceWindow = own;
                pp.PresentationInterval = D3DPRESENT_INTERVAL_IMMEDIATE;
                sprintf_s(label, sizeof label, "(a) own D3D9Ex, adapter %u", adapter);
                if (FAILED(IDirect3D9Ex_CreateDeviceEx(d3d, adapter, D3DDEVTYPE_HAL, own,
                                                       D3DCREATE_HARDWARE_VERTEXPROCESSING | D3DCREATE_FPU_PRESERVE,
                                                       &pp, NULL, &dev))) {
                    printf("   %s: FAIL CreateDeviceEx\n", label);
                    continue;
                }
                if (!pipeline_make(&p, (IDirect3DDevice9 *)dev, w, h, out_w, out_h, stages)) {
                    printf("   %s: FAIL pipeline\n", label);
                } else {
                    int sep;
                    for (sep = 0; sep <= 1; ++sep) {
                        IDirect3DSurface9 *bb = NULL;
                        double t1, total = 0;
                        p.separable = sep;
                        sprintf_s(label, sizeof label, "(a) own D3D9Ex, adapter %u, fit %s", adapter,
                                  sep ? "2 passes" : "1 pass");
                        sprintf_s(path, sizeof path, "%s.gpu-%s.argb", argv[8], stages == 2 ? "4x" : "2x");
                        pipeline_measure(&p, &frame, &reference, 60, label, adapter == 0 && sep ? path : NULL);
                        /* and straight into the back buffer with PresentEx, as the companion would */
                        IDirect3DDevice9_GetBackBuffer((IDirect3DDevice9 *)dev, 0, 0, D3DBACKBUFFER_TYPE_MONO, &bb);
                        for (i = 0; i < 63; ++i) {
                            t1 = now_ms();
                            pipeline_run(&p, &frame, bb);
                            IDirect3DDevice9Ex_PresentEx(dev, NULL, NULL, NULL, NULL, 0);
                            gpu_wait((IDirect3DDevice9 *)dev);
                            if (i >= 3) total += now_ms() - t1;
                        }
                        release(bb);
                        printf("   %-34s %.2f ms a frame on average into the back buffer with PresentEx (60 "
                               "frames)\n",
                               label, total / 60);
                    }
                    pipeline_free(&p);
                }
                release(dev);
            }
            if (sdl_dev) {
                /* (c) SDL's own device; SDL's state saved and put back around ours with a state block.  (SDL's own
                   drawing cannot be checked afterwards here: SDL skips drawing for a hidden window.) */
                pipeline p;
                IDirect3DStateBlock9 *saved = NULL;
                IDirect3DSurface9 *sdl_target = NULL;
                if (!pipeline_make(&p, sdl_dev, w, h, out_w, out_h, stages)) {
                    printf("   (c) SDL's own device: FAIL pipeline\n");
                } else {
                    IDirect3DDevice9_GetRenderTarget(sdl_dev, 0, &sdl_target);
                    IDirect3DDevice9_CreateStateBlock(sdl_dev, D3DSBT_ALL, &saved);
                    pipeline_measure(&p, &frame, &reference, 60, "(c) SDL's own device", NULL);
                    IDirect3DStateBlock9_Apply(saved);
                    IDirect3DDevice9_SetRenderTarget(sdl_dev, 0, sdl_target);
                    release(sdl_target);
                    release(saved);
                    pipeline_free(&p);
                }
            }
        }
        release(d3d);
        DestroyWindow(own);
    }
    vv4k_free(&frame);
    vv4k_free(&reference);
    return 0;
}
