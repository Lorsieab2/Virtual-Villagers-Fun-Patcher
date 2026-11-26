/* vv4k_filters -- CPU reference versions of the 4K filter candidates (research prototype, not shipped).

   Every image is packed 0xAARRGGBB (SDL_PIXELFORMAT_ARGB8888, the format of the games' frame texture), rows top to
   bottom, no padding.  The GPU version (vv4k_shaders.hlsl) computes the same thing; vv4k_gpu_probe compares them. */
#ifndef VV4K_FILTERS_H
#define VV4K_FILTERS_H

#include <stdint.h>

typedef struct {
    int width, height;
    uint32_t *pixels;
} vv4k_image;

/* The candidate filters. */
enum {
    VV4K_STOCK_NEAREST = 0,    /* what SDL 2.0.3 does today: nearest neighbour at the uneven factor (3.6x, 2.8125x) */
    VV4K_BILINEAR = 1,         /* plain smooth: bilinear straight to the target (the SDL "linear" look) */
    VV4K_SHARP_PIXELS = 2,     /* integer nearest prescale (ceil of the factor), then the Catmull-Rom fit */
    VV4K_EDGE_DIRECTED = 3,    /* the edge-directed 2x scaler twice (4x), then the Catmull-Rom fit */
    VV4K_EDGE_DIRECTED_2X = 4, /* the edge-directed 2x scaler once, then the Catmull-Rom fit (cheaper, softer) */
    VV4K_FILTER_COUNT = 5
};

extern const char *const vv4k_filter_names[VV4K_FILTER_COUNT];

int vv4k_alloc(vv4k_image *image, int width, int height);
void vv4k_free(vv4k_image *image);

/* The edge-directed 2x scaler (Super-xBR method, written for this project; see vv4k_filters.c). */
int vv4k_edge_directed_2x(const vv4k_image *in, vv4k_image *out);

/* Nearest-neighbour integer upscale. */
int vv4k_nearest_integer(const vv4k_image *in, int factor, vv4k_image *out);

/* The fit: resample `src` (the frame prescaled by `prescale`, with its content offset `offset` source-frame pixels --
   the edge-directed scaler's half-pixel lattice) into the `fit_w` x `fit_h` rectangle at (`fit_x`, `fit_y`) of `out`
   with a Catmull-Rom kernel widened when it shrinks; `out` keeps whatever is outside the rectangle. */
void vv4k_fit_catmull_rom(const vv4k_image *src, int frame_w, int frame_h, double prescale, double offset,
                          vv4k_image *out, int fit_x, int fit_y, int fit_w, int fit_h);
void vv4k_fit_bilinear(const vv4k_image *frame, vv4k_image *out, int fit_x, int fit_y, int fit_w, int fit_h);
void vv4k_fit_nearest(const vv4k_image *frame, vv4k_image *out, int fit_x, int fit_y, int fit_w, int fit_h);

/* The whole candidate: `frame` into `out` (out->width x out->height, e.g. 3840x2160), the frame's 4:3 picture as
   large as fits, centred, black bars (letterbox).  Returns 0 on success. */
int vv4k_render(int filter, const vv4k_image *frame, vv4k_image *out);

/* The letterboxed picture rectangle for a frame in a display (the same arithmetic the input mapping inverts). */
void vv4k_fit_rect(int frame_w, int frame_h, int out_w, int out_h, int *x, int *y, int *w, int *h);

#endif
