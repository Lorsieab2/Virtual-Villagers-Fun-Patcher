# 4K filter -- research and design (ships after v1.35.101, as its own release)

The owner, 2026-11-26: "I wonder if it could be possible to upscale the games with a filter or something? HD
version?" -- "We tried to upscale the textures in the past but they looked horrible. I prefer a filter made by you.
4k please".

Status: research and a working prototype (`native/vvfp_4k_filter/`). Nothing here ships yet, and nothing has been
tried in a running game. Labels used below: **proven** (measured on this machine with the games' own files),
**static** (read from the five stock executables or SDL2.dll), **inferred** (reasoning that still needs the live
check).

## 1. The decision in short

- **The frame.** Take each finished frame where the game hands it to SDL. Every frame, the game calls
  `SDL_UpdateTexture` with its own 800x600 (VV1-VV4) or 1024x768 (VV5) ARGB picture. That picture is already
  in memory, so nothing has to be read back from the GPU.
- **The display.** Hook four of the game's SDL imports (UpdateTexture, RenderClear, RenderCopy, RenderPresent).
  While the filter runs, SDL's own drawing is skipped. The frame goes to **a Direct3D 9Ex device of our own** on
  the game's window (option a). That device runs the filter on the GPU and presents at the window's real pixel
  size: 3840x2160 on a 4K screen, 2560x1600 on this laptop. If anything fails, the hooks hand the frame back to
  SDL, which draws it exactly as it does today.
- **The filter.** An **edge-directed 2x scaler, run twice (4x)**, then a **Catmull-Rom fit** down to the screen
  height, with letterbox bars for the 4:3 picture. The scaler was written for this project, using the method of
  Hyllian's Super-xBR. It is not AI and it does not replace any art. The GPU result matches the CPU reference
  within 4/255 on at most 0.0006% of pixels (**proven**).
- **The mouse.** A `WH_GETMESSAGE` hook on the game's thread rewrites each mouse message from screen pixels to
  game pixels before SDL reads it. As a result, `SDL_GetMouseState` returns game coordinates to the game and to
  every companion. A hook on the `SDL_WarpMouseInWindow` import maps the other way.
- **Sharp pixels.** The game window is made DPI-aware only while SDL creates it. Today, at 150% Windows scaling,
  Windows stretches the games' picture with a blur on top of SDL's uneven nearest-neighbour scaling.

## 2. What the games do (static, all five)

| | A New Home | The Lost Children | The Secret City | The Tree of Life | New Believers |
|---|---|---|---|---|---|
| frame size | 800x600 | 800x600 | 800x600 | 800x600 | 1024x768 |
| size getters (vtable pair) | 0x41BDC0 / 0x41BDD0 | 0x424960 / 0x424970 | 0x427C20 / 0x427C30 | 0x414710 / 0x41F000 | 0x4244B0 / 0x4244C0 |
| window setup | 0x40844F | 0x4086DF | 0x408D0F | 0x4084A0 | 0x408480 |
| frame routine | 0x403830 | 0x403AC0 | 0x4040E0 | 0x4046F0 | 0x404680 |
| frame period (`[win+0x74] = 0x21`) | 0x40851E | 0x4087AE | 0x408DDE | 0x408646 | 0x408626 |

- Setup (the same in all five): `SDL_CreateWindow(title, centred, centred, W, H, SDL_WINDOW_RESIZABLE)`,
  `SDL_SetWindowMinimumSize(W, H)`, `SDL_CreateRenderer(window, -1, 0)`, then
  `SDL_CreateTexture(ARGB8888, STREAMING, W, H)`. **After** the texture is created, the game sets
  `SDL_SetHint("SDL_RENDER_SCALE_QUALITY", "linear")`, then calls `SDL_RenderSetLogicalSize(W, H)`. SDL 2.0.3
  reads the scale hint when a texture is created, so the game's one texture is scaled **nearest-neighbour** at
  uneven factors. For example, 2560x1600 full screen gives 2.67x for VV1-VV4.
- Each frame: `SDL_UpdateTexture(tex, NULL, pixels, pitch)`, `SDL_RenderClear`, `SDL_RenderCopy(tex)`,
  `SDL_RenderPresent`. There is one call site of each in each game. The main loop paces itself with `SDL_Delay`
  to a **33 ms frame period (about 30 frames a second)** in all five games.
- Full screen is `SDL_SetWindowFullscreen(window, 0x1001)` (full screen desktop). Before the switch, the game
  saves `SDL_GetMouseState` and warps the mouse back to that spot 60 frames later (`SDL_WarpMouseInWindow` in
  the frame routine). In full screen it calls `SDL_ShowCursor(0)` and draws its own pointer.
- **Mouse input.** The event pump (VV5 0x4047C0) ignores the coordinates in SDL's mouse events. On motion,
  button-down and button-up it calls `SDL_GetMouseState` instead (VV5 0x404A20 / 0x404A4F / 0x404A77) and queues
  (kind, x, y). The game does not use the wheel.
- The games are **not DPI aware**: VV1-VV3 have no manifest, and VV4 and VV5 say `dpiAware` false. Neither the
  exes nor SDL2.dll call any DPI API. This laptop runs its 2560x1600 panel at 150% (144 DPI), so a game sees a
  1707x1067 desktop and Windows stretches it to the panel.

## 3. Facts measured with the games' SDL2.dll (proven; `vv4k_gpu_probe`)

SDL2.dll is 2.0.3, SHA-256 D1972860...FABD. The probe runs in hidden windows of its own; no game ran.

- Its render drivers are direct3d, opengl, opengles2 and software. The games' `SDL_CreateRenderer(window, -1, 0)`
  picks **direct3d (Direct3D 9)**. SDL's device is on adapter 0, "Intel(R) Graphics", with behaviour flags 0x42
  (FPU_PRESERVE). This laptop's NVIDIA GPU is **not** a Direct3D 9 adapter (Optimus), so Intel Graphics is the
  budget.
- `SDL_RenderGetD3D9Device` **is exported** by 2.0.3 and returns SDL's device. `SDL_SetRenderTarget` and
  `SDL_RenderReadPixels` are exported too. SDL 2.0.3 has no shader API.
- **`SDL_GetMouseState` is NOT scaled by the logical size; SDL's mouse events are.**

  | window | SDL scale | WM_MOUSEMOVE at | SDL event | `SDL_GetMouseState` (what the games read) |
  |---|---|---|---|---|
  | 800x600 | 1.0 | (400,300) | (400,300) | (400,300) |
  | 1200x900 | 1.5 | (600,450) | (400,300) | **(600,450)** |
  | 1920x1080 | 1.8, bars 133 px | (960,540) | (400,300) | **(960,540)** |

  The games therefore read **window pixels**, not game pixels, whenever the window is not 1:1. This includes
  stock full screen. (See owner question 6.)

## 4. Where to hook, and the three ways to get the frame to the screen

All three start from the same frame: the game's own pixels at `SDL_UpdateTexture`. Reading the frame back is
never needed. For comparison only, `SDL_RenderReadPixels` of an 800x600 frame costs 1.5-1.8 ms.

| | how | measured | verdict |
|---|---|---|---|
| (a) own D3D9Ex device | Upload to our texture, run our passes, PresentEx on the game's window. SDL's Clear/Copy/Present are skipped while the filter runs. | 4x: 10.8-10.9 ms a frame (800x600 to 4K, GPU at full clock), 4.2 ms for 2x. Identical to (c). | **chosen** |
| (b) CPU filter | Our scaler on the CPU, upload the big picture to SDL. | 1.3-3.1 **seconds** a frame, one thread, plain C (4x). 0.38-0.82 s (2x). Even 24 threads with SIMD would not make 33 ms reliably. | rejected |
| (c) SDL's own device | `SDL_RenderGetD3D9Device`, our passes inside the game's present, SDL's state saved and restored with a state block. | Same GPU time as (a) (10.9 ms). | rejected |

Why (a) over (c), when they cost the same:

- **SDL's back buffer is the wrong size.** It follows `SDL_GetWindowSize`, which for these DPI-unaware games is
  the scaled-down size (1707x1067 here). A device of our own presents at the real pixel count.
- **Reset.** SDL 2.0.3 creates a plain Direct3D 9 device, not 9Ex, and resets it on a window size change and on
  device loss (Ctrl+Alt+Del, UAC, the lock screen). A plain D3D9 `Reset` fails while any `D3DPOOL_DEFAULT`
  resource exists, and our render targets would be such resources. SDL resets inside its own calls, where we
  cannot release first. (This is the documented Direct3D 9 rule. The probe could not show it, because a hidden
  window never made SDL reset.) A 9Ex device is not lost on the secure desktop, and the 9Ex documentation says
  it keeps its resources across `ResetEx`; the live check confirms this.
- **No shared state.** SDL caches its sampler states and its scene state. Our own device cannot disturb SDL.
- **One way back.** If our device fails at any time, the hooks stop skipping SDL. SDL's texture is still updated
  every frame, so the next frame is SDL's stock picture.

To verify live: two Direct3D devices on one window, one of them idle. This is legal for windowed swap chains, but
**inferred** until seen in a game.

## 5. The filter

Pixel-art scalers (xBRZ, ScaleFX, HQx, Eagle) look for runs of **identical** colours. These games are painted,
anti-aliased art, and the map pictures are JPEGs (see `data/vv1_visual_mods/base/Images/MapX*.jpg`). On art like
that those scalers find almost no equal neighbours, so they behave close to nearest-neighbour or posterize.
xBRZ is also GPL-3, which this repository cannot take. Super-xBR (Hyllian, 2015) was designed for continuous-tone
images, so the scaler follows its method, written fresh here (`vv4k_filters.c`, `vv4k_shaders.hlsl`):

1. **Step 1.** The originals keep the even/even places of the doubled lattice. Each odd/odd place (the middle of
   four originals) gets a 4-tap interpolation along whichever diagonal the picture changes **less** along: that
   is the direction an edge runs. Luma differences decide the direction, weighted toward the centre. Near a tie
   both directions are mixed. Taps are -0.129633 / 0.629633.
2. **Step 2.** The places between two known points are filled the same way on the lattice turned 45 degrees,
   choosing between the row and the column. Taps are -0.175068 / 0.675068.
3. **No ringing.** Every new value is clamped between the lowest and highest of its four nearest known
   neighbours.
4. **Twice, for 4x.** The doubled image sits a quarter of a source pixel off; the fit corrects for it (offset
   -1.5 at 4x).
5. **The fit.** Catmull-Rom, with the kernel widened when shrinking, from the 4x image to the display height,
   centred, black bars left and right. At 3840x2160 this is 0.9x for VV1-VV4 (3200x2400 to 2880x2160) and 0.70x
   for VV5. Shrinking slightly from a larger picture keeps edges crisp without blur.

**The candidates in the before/after images** (`make_comparison.py`):

| | filter | look |
|---|---|---|
| A | today's SDL: nearest-neighbour at the uneven factor | uneven, blocky pixels |
| B | plain bilinear | soft, blurry |
| C | sharp pixels: integer nearest prescale, then the fit | crisp square pixels, stair-stepped edges |
| **D** | **edge-directed 4x, then the fit (proposed)** | smooth, crisp edges and text, no stair steps |
| E | edge-directed 2x, then the fit (the faster setting) | like D, a little softer |
| -- | "today at 150% scaling" (2560x1600 only) | A, then Windows' own stretch: what this laptop shows now |

## 6. Measured costs (Intel Graphics, the only Direct3D 9 adapter here)

Each frame below is timed with the GPU waited for: upload, all passes and PresentEx. The figures come from two
kinds of run:

- **Full clock:** the first, cool run.
- **Throttled:** later, back-to-back runs. The GPU had lowered its clock, and per-pass times doubled for the
  same work.

| frame to display | 4x (D), full clock | 4x (D), throttled | 2x (E), full clock | 2x (E), throttled |
|---|---|---|---|---|
| 800x600 to 3840x2160 | 10.8 ms | 23-40 ms | 4.2 ms | 14-20 ms |
| 1024x768 to 3840x2160 | -- | 19-30 ms | -- | 15-23 ms |
| 800x600 to 2560x1600 | -- | 19-35 ms | -- | 9-14 ms |
| 1024x768 to 2560x1600 | -- | 15-27 ms | -- | 5.5-17 ms |

GPU time per pass, 800x600 to 4K at full clock:

| pass | time |
|---|---|
| 2x step 1 | 0.57 ms |
| 2x step 2 | 0.63 ms |
| 4x step 1 | 2.27 ms |
| 4x step 2 | 2.50 ms |
| fit | 3.7 ms |

The game's frame period is 33 ms, and the GPU works while the game sleeps in `SDL_Delay`. 4x fits that period
at full clock with room to spare. On a hot, throttled iGPU, 4x reaches the period, while 2x stays inside it.

Video memory for 4x at 4K: about 190 MB for VV1-VV4 and 255 MB for VV5. That counts the two 4x targets, the two
2x targets, the 4K output and the prototype's 16-bit row buffer of the two-pass fit. An 8-bit row buffer would
save about 40%.

Optimisations not tried yet:

- Do both steps of a stage in one pass, which halves the big-target traffic.
- A 9-tap bilinear Catmull-Rom fit.
- Skip the work when the frame has not changed. Rare, since villagers are always moving.

## 7. Mouse and keyboard

- **The hook.** `WH_GETMESSAGE` on the game's thread, the same family as Window Restore's `WH_CALLWNDPROC`.
  The two hooks chain. For the SDL window's `WM_MOUSEMOVE`, `WM_LBUTTON*`, `WM_RBUTTON*` and `WM_MBUTTON*`,
  `lParam` (window pixels) is rewritten to game pixels:
  `gx = floor((x - fit_x) * W / fit_w)` and the same for y, clamped to the frame. SDL then stores game pixels.
  `SDL_GetMouseState` returns them to the game's eight call sites and to companions that read it straight from
  SDL2.dll (VV1 Parentage, the Scrolling Popups wheel target). An import-table hook of `SDL_GetMouseState`
  would miss those companions.
- **Letterbox bars.** Movement over a bar is clamped to the frame's edge. A **button press over a bar is
  dropped** (the message becomes `WM_NULL`), so clicking the black bars does nothing. (See owner question 2.)
- **`SDL_WarpMouseInWindow`** is hooked through the game's import: game pixels to window pixels. Its
  `WM_MOUSEMOVE` comes back mapped.
- **The wheel.** `WM_MOUSEWHEEL` carries screen coordinates that SDL 2.0.3 does not use. Nothing to map.
- **Leaving the window.** SDL handles `WM_MOUSELEAVE` with `GetCursorPos`, which gives window pixels. Only when
  the pointer leaves the window does the game's mouse briefly hold an unmapped value. This is harmless, because
  the pointer is outside. **Inferred.**
- The keyboard is untouched.

## 8. Sharp pixels: DPI

Not being DPI aware, the games draw into a scaled-down window, which Windows stretches with a blur (the "today at
150%" image). The companion hooks the `SDL_CreateWindow` import: `SetThreadDpiAwarenessContext(SYSTEM_AWARE)`
around the real call, restored right after (Windows 10 1607 and later). Only the game window becomes DPI-aware.
Dialogs that companions create later on the same thread stay as they are today.

To verify live:

- SDL 2.0.3's full screen bounds (`EnumDisplaySettings`) and `SetWindowPos` agree in a DPI-aware window.
- The windowed game, now 800x600 real pixels, small at 150%. The companion can create it at W×scale by H×scale
  instead. (See owner question 3.)

## 9. How it works with the rest of the patcher

- **Window Restore (bit 20)** stays on and is still needed: SDL's own window state drives full screen and
  restore. While the filter runs, SDL's hidden-renderer gate no longer decides whether a picture appears. Our
  present skips only while the window is minimised (`IsIconic`), and resizes its swap chain whenever the client
  size changes.
- **Translations, fonts, Unicode text, long words, scrolling pop-ups, and every overlay companion** draw into
  the game's own software frame before `SDL_UpdateTexture`, so the filter sees and scales them like the game's
  own art. None of them hooks SDL's renderer.
- **Win32 dialogs** (Change Appearance, Origins and the others) are separate windows. The windowed 9Ex swap chain
  does not take the screen exclusively, so they show over full screen as they do today.
- **Full-screen toggle.** The window size changes, the next present sees the new client size and calls `ResetEx`,
  and the warp-back after 60 frames goes through the warp hook.
- **All or none, like Window Restore.** The companion installs only when:
  - SDL2.dll is 2.0.3 with Window Restore's three stock byte checks;
  - the game's import slots for the six hooked SDL functions point into SDL2.dll;
  - the frame routine's bytes at the five addresses above are stock;
  - `Direct3DCreate9Ex` succeeds.

  Shaders ship precompiled (`fxc`, shader model 3) inside the DLL. No d3dcompiler is needed and no file is
  written.
- **The patch row:** one row per game ("Sharp full-screen picture (4K filter)"), off by default until the owner
  decides, bit 21 or the next free startup bit. A Settings button next to the patch holds quality (4x or 2x) and
  bars. Game files, art and saves are untouched.

## 10. Risks

1. **The Intel iGPU under heat.** 4x at 4K can take 23-40 ms when throttled, against a 33 ms frame. Owner
   question 4 offers 2x, or an automatic step-down, which would need the owner's approval.
2. **Two devices on one window** (section 4). If a driver dislikes it, the fallback is SDL's own device (c).
   That works, but it is tied to SDL's reset timing.
3. **DPI.** Making only the SDL window DPI-aware is new to this patcher. The full-screen bounds, the windowed
   size and companion dialog placement all need the live check.
4. **The look of grain.** On grainy sand and JPEG map pictures, the edge-directed scaler turns noise into small
   brush-like strokes. Text, outlines, faces and objects come out clean. Judge from the images; filter E is
   softer.
5. **Input edge cases** (inferred): the pointer leaving the window, touch screens (synthesised mouse messages
   are mapped the same way), and right-click and middle-click (mapped, though the games ignore them).
6. **Laptops with two GPUs.** Direct3D 9 sees only the integrated GPU. A player can set the game exe to "High
   performance" in Windows' Graphics settings; the patcher must not change that setting itself.

## 11. Owner questions

1. Which look (section 5): D (sharpest), E (a little softer, cheaper) or C (crisp square pixels)?
2. Black bars on the sides (4:3 kept), or stretch to fill a 16:9 screen (wider villagers)? Should a click on a
   bar do nothing, as proposed?
3. Windowed play: should the window open at the Windows-scaled size (1200x900 at 150%) and get the same filter,
   or keep today's look in a window?
4. On a slow GPU: always 4x, always 2x, or an automatic step-down to 2x when frames run late (an autonomous
   behaviour, so it needs your yes)?
5. The patch row: on by default, or off until you have seen it in your game?
6. Stock full screen today: does a click land exactly under the pointer on the right half of the screen?
   `SDL_GetMouseState` is not scaled (section 3). If it does not, that is a vanilla bug the filter's mouse
   mapping fixes as a side effect, and a smaller "full screen mouse fix" could ship on its own in Fix Vanilla
   Bugs.

## 12. The prototype (`native/vvfp_4k_filter/`, research only, not built by the release)

- `vv4k_filters.c` / `.h`: the CPU reference of every candidate.
- `vv4k_upscale.c`: runs every candidate on one frame and times the CPU (option b).
- `vv4k_shaders.hlsl`: the GPU filter: steps 1 and 2, the one-pass and two-pass fits.
- `vv4k_gpu_probe.c`: sections 3, 4 and 6. It loads the games' SDL2.dll, opens hidden windows only, compiles the
  HLSL at run time, times (a) and (c), and compares the GPU picture with the CPU reference.
- `make_comparison.py`: builds three test frames from the games' own art in this repository, writes the
  before/after PNGs, side-by-side detail sheets and the "today at 150%" picture.
  - VV1 map pictures, garden and heads, 800x600;
  - VV4 Options window, 800x600;
  - VV5 upgrades mock-up, 1024x768. This one is a JPEG, so it carries JPEG noise the live game does not have.
- `build_prototype.bat <out folder>`: builds both tools, 32-bit, with Visual Studio.

Run:

```
build_prototype.bat <out>
python -I make_comparison.py <out> <images> 3840 2160
python -I make_comparison.py <out> <images> 2560 1600 1.5
vv4k_gpu_probe.exe <folder with the games' SDL2.dll> vv4k_shaders.hlsl <images>\vv1_scene.argb 800 600 3840 2160 <prefix>
```
