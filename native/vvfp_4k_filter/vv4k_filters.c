/* vv4k_filters -- CPU reference versions of the 4K filter candidates (research prototype, not shipped).

   THE EDGE-DIRECTED 2x SCALER.  Written for this project after the method of Hyllian's Super-xBR (2015): an image is
   doubled in two steps on the doubled lattice.  The original pixels keep the even/even places.  Step 1 fills each
   odd/odd place -- the middle of four original pixels -- from the 4x4 original pixels around it: it measures how much
   the picture changes along the "\" diagonal and along the "/" diagonal, and interpolates with a 4-tap filter along
   the diagonal that changes LESS (the direction an edge runs), softly mixing both when they are nearly equal.  Step 2
   fills the remaining places (between two originals in a row or a column) the same way on the 45-degree-turned
   lattice of the known points, choosing between the row and the column.  Each new value is clamped between the
   lowest and highest of its four nearest known neighbours, so edges never ring.  Unlike pixel-art scalers that look
   for runs of IDENTICAL colours (xBRZ, ScaleFX, HQx), this works on the games' painted, already anti-aliased art: it
   compares brightness differences, not colour equality.  Tap weights are Super-xBR's: step 1 -0.129633 / 0.629633,
   step 2 -0.175068 / 0.675068 (each 4-tap set sums to 1).

   The doubled image keeps the original at even places, so its content sits a quarter of an original pixel up and
   left of the exact doubled position: the 2x image pixel Z shows the original's centre coordinate Z/2.  The fit pass
   undoes it (offset -0.5 for 2x, -1.5 for 4x, in the prescaled image's pixels). */
#include "vv4k_filters.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

const char *const vv4k_filter_names[VV4K_FILTER_COUNT] = {
    "stock-nearest",
    "bilinear",
    "sharp-pixels",
    "edge-directed",
    "edge-directed-2x",
};

typedef struct {
    float r, g, b;
} px;

int vv4k_alloc(vv4k_image *image, int width, int height) {
    image->width = width;
    image->height = height;
    image->pixels = (uint32_t *)calloc((size_t)width * (size_t)height, sizeof(uint32_t));
    return image->pixels != NULL ? 0 : -1;
}

void vv4k_free(vv4k_image *image) {
    free(image->pixels);
    image->pixels = NULL;
    image->width = image->height = 0;
}

static px unpack(uint32_t c) {
    px p;
    p.r = (float)((c >> 16) & 0xFF);
    p.g = (float)((c >> 8) & 0xFF);
    p.b = (float)(c & 0xFF);
    return p;
}

static uint32_t to_byte(float v) {
    v = floorf(v + 0.5f);
    if (v < 0.0f) {
        return 0;
    }
    if (v > 255.0f) {
        return 255;
    }
    return (uint32_t)v;
}

static uint32_t pack(px p) {
    return 0xFF000000u | (to_byte(p.r) << 16) | (to_byte(p.g) << 8) | to_byte(p.b);
}

static float luma(px p) {
    return 0.2126f * p.r + 0.7152f * p.g + 0.0722f * p.b;
}

static int clampi(int v, int lo, int hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

/* Reflect into [0, n) keeping the parity of v (n even): the doubled lattice's known places stay known places. */
static int reflect_even(int v, int n) {
    if (v < 0) {
        v = -v;
    }
    if (v >= n) {
        v = 2 * (n - 1) - v;   /* 2(n-1) is even: the same parity as v */
    }
    return clampi(v, 0, n - 1);
}

/* One interpolation on a 4x4 window P (rows r, columns c): "\" is P00 P11 P22 P33, "/" is P03 P12 P21 P30. */
static px interpolate_window(px P[4][4], float wa, float wb) {
    float L[4][4];
    float along_main, along_anti, k, lo, hi;
    px main_line, anti_line, out;
    int r, c;
    for (r = 0; r < 4; ++r) {
        for (c = 0; c < 4; ++c) {
            L[r][c] = luma(P[r][c]);
        }
    }
    /* How much the picture changes walking along "\" (pairs (r,c)-(r+1,c+1)), the centre pair counting most. */
    along_main = 4.0f * fabsf(L[1][1] - L[2][2]) +
                 2.0f * (fabsf(L[0][1] - L[1][2]) + fabsf(L[1][2] - L[2][3]) + fabsf(L[1][0] - L[2][1]) +
                         fabsf(L[2][1] - L[3][2])) +
                 fabsf(L[0][0] - L[1][1]) + fabsf(L[2][2] - L[3][3]) + fabsf(L[0][2] - L[1][3]) +
                 fabsf(L[2][0] - L[3][1]);
    /* ... and along "/" (the mirror image of the same pairs). */
    along_anti = 4.0f * fabsf(L[1][2] - L[2][1]) +
                 2.0f * (fabsf(L[0][2] - L[1][1]) + fabsf(L[1][1] - L[2][0]) + fabsf(L[1][3] - L[2][2]) +
                         fabsf(L[2][2] - L[3][1])) +
                 fabsf(L[0][3] - L[1][2]) + fabsf(L[2][1] - L[3][0]) + fabsf(L[0][1] - L[1][0]) +
                 fabsf(L[2][3] - L[3][2]);
    main_line.r = wa * (P[0][0].r + P[3][3].r) + wb * (P[1][1].r + P[2][2].r);
    main_line.g = wa * (P[0][0].g + P[3][3].g) + wb * (P[1][1].g + P[2][2].g);
    main_line.b = wa * (P[0][0].b + P[3][3].b) + wb * (P[1][1].b + P[2][2].b);
    anti_line.r = wa * (P[0][3].r + P[3][0].r) + wb * (P[1][2].r + P[2][1].r);
    anti_line.g = wa * (P[0][3].g + P[3][0].g) + wb * (P[1][2].g + P[2][1].g);
    anti_line.b = wa * (P[0][3].b + P[3][0].b) + wb * (P[1][2].b + P[2][1].b);
    /* k = 1: interpolate along "\" (it changes less); a soft band of 10% of the total mixes both near a tie. */
    k = 0.5f + (along_anti - along_main) / (2.0f * (0.1f * (along_anti + along_main) + 0.0001f));
    k = k < 0.0f ? 0.0f : (k > 1.0f ? 1.0f : k);
    out.r = k * main_line.r + (1.0f - k) * anti_line.r;
    out.g = k * main_line.g + (1.0f - k) * anti_line.g;
    out.b = k * main_line.b + (1.0f - k) * anti_line.b;
    /* No ringing: between the lowest and highest of the four nearest known neighbours. */
#define VV4K_CLAMP4(ch)                                                                                              \
    lo = fminf(fminf(P[1][1].ch, P[1][2].ch), fminf(P[2][1].ch, P[2][2].ch));                                        \
    hi = fmaxf(fmaxf(P[1][1].ch, P[1][2].ch), fmaxf(P[2][1].ch, P[2][2].ch));                                        \
    out.ch = out.ch < lo ? lo : (out.ch > hi ? hi : out.ch);
    VV4K_CLAMP4(r)
    VV4K_CLAMP4(g)
    VV4K_CLAMP4(b)
#undef VV4K_CLAMP4
    return out;
}

int vv4k_edge_directed_2x(const vv4k_image *in, vv4k_image *out) {
    const float w1 = -0.129633f, w2 = 0.629633f;   /* step 1 taps */
    const float w3 = -0.175068f, w4 = 0.675068f;   /* step 2 taps */
    int W = in->width * 2, H = in->height * 2;
    int x, y, r, c;
    px *lattice;
    if (vv4k_alloc(out, W, H) != 0) {
        return -1;
    }
    lattice = (px *)malloc((size_t)W * (size_t)H * sizeof(px));
    if (lattice == NULL) {
        vv4k_free(out);
        return -1;
    }
    /* The originals at even/even. */
    for (y = 0; y < in->height; ++y) {
        for (x = 0; x < in->width; ++x) {
            lattice[(size_t)(2 * y) * W + 2 * x] = unpack(in->pixels[(size_t)y * in->width + x]);
        }
    }
    /* Step 1: odd/odd, from the 4x4 originals around it. */
    for (y = 0; y < in->height; ++y) {
        for (x = 0; x < in->width; ++x) {
            px P[4][4];
            for (r = 0; r < 4; ++r) {
                int sy = clampi(y - 1 + r, 0, in->height - 1);
                for (c = 0; c < 4; ++c) {
                    int sx = clampi(x - 1 + c, 0, in->width - 1);
                    P[r][c] = unpack(in->pixels[(size_t)sy * in->width + sx]);
                }
            }
            lattice[(size_t)(2 * y + 1) * W + 2 * x + 1] = interpolate_window(P, w1, w2);
        }
    }
    /* Step 2: the places with X+Y odd, on the turned lattice: window row r / column c are s = 2r-3, t = 2c-3, at
       offset (p, q) = ((s+t)/2, (s-t)/2) -- its "\" is this place's row, its "/" this place's column. */
    for (y = 0; y < H; ++y) {
        for (x = (y & 1) ? 0 : 1; x < W; x += 2) {
            px P[4][4];
            for (r = 0; r < 4; ++r) {
                for (c = 0; c < 4; ++c) {
                    int s = 2 * r - 3, t = 2 * c - 3;
                    int sx = reflect_even(x + (s + t) / 2, W);
                    int sy = reflect_even(y + (s - t) / 2, H);
                    P[r][c] = lattice[(size_t)sy * W + sx];
                }
            }
            lattice[(size_t)y * W + x] = interpolate_window(P, w3, w4);
        }
    }
    for (y = 0; y < H; ++y) {
        for (x = 0; x < W; ++x) {
            out->pixels[(size_t)y * W + x] = pack(lattice[(size_t)y * W + x]);
        }
    }
    free(lattice);
    return 0;
}

int vv4k_nearest_integer(const vv4k_image *in, int factor, vv4k_image *out) {
    int x, y;
    if (vv4k_alloc(out, in->width * factor, in->height * factor) != 0) {
        return -1;
    }
    for (y = 0; y < out->height; ++y) {
        const uint32_t *row = in->pixels + (size_t)(y / factor) * in->width;
        for (x = 0; x < out->width; ++x) {
            out->pixels[(size_t)y * out->width + x] = row[x / factor];
        }
    }
    return 0;
}

static float catmull_rom(float x) {
    x = fabsf(x);
    if (x < 1.0f) {
        return 1.5f * x * x * x - 2.5f * x * x + 1.0f;
    }
    if (x < 2.0f) {
        return -0.5f * x * x * x + 2.5f * x * x - 4.0f * x + 2.0f;
    }
    return 0.0f;
}

typedef struct {
    int first, count;
    float w[16];
} taps;

/* Taps for output pixel i of n across a source of `src_n` pixels; source coordinate (edge convention)
   e = prescale * u + offset where u runs over the frame's `frame_n` pixels. */
static void make_taps(taps *t, int i, int n, int frame_n, int src_n, double prescale, double offset) {
    double u = (i + 0.5) * (double)frame_n / (double)n;
    double centre = prescale * u + offset - 0.5;           /* source centre coordinate */
    double ratio = (double)n / ((double)frame_n * prescale); /* output pixels per source pixel */
    double stretch = ratio < 1.0 ? ratio : 1.0;              /* widen the kernel when shrinking */
    double support = 2.0 / stretch;
    int lo = (int)floor(centre - support) + 1, hi = (int)floor(centre + support);
    float sum = 0.0f;
    int k;
    if (hi - lo + 1 > 16) {
        hi = lo + 15;
    }
    t->first = lo;
    t->count = hi - lo + 1;
    for (k = 0; k < t->count; ++k) {
        t->w[k] = catmull_rom((float)(((lo + k) - centre) * stretch));
        sum += t->w[k];
    }
    for (k = 0; k < t->count; ++k) {
        t->w[k] /= sum;
    }
    (void)src_n;
}

void vv4k_fit_catmull_rom(const vv4k_image *src, int frame_w, int frame_h, double prescale, double offset,
                          vv4k_image *out, int fit_x, int fit_y, int fit_w, int fit_h) {
    /* Separable: rows first (fit_w x src->height, float), then columns. */
    float *mid = (float *)malloc((size_t)fit_w * (size_t)src->height * 3 * sizeof(float));
    taps *tx = (taps *)malloc((size_t)fit_w * sizeof(taps));
    taps ty;
    int x, y, k;
    if (mid == NULL || tx == NULL) {
        free(mid);
        free(tx);
        return;
    }
    for (x = 0; x < fit_w; ++x) {
        make_taps(&tx[x], x, fit_w, frame_w, src->width, prescale, offset);
    }
    for (y = 0; y < src->height; ++y) {
        const uint32_t *row = src->pixels + (size_t)y * src->width;
        float *m = mid + (size_t)y * fit_w * 3;
        for (x = 0; x < fit_w; ++x) {
            float r = 0, g = 0, b = 0;
            for (k = 0; k < tx[x].count; ++k) {
                uint32_t c = row[clampi(tx[x].first + k, 0, src->width - 1)];
                float w = tx[x].w[k];
                r += w * (float)((c >> 16) & 0xFF);
                g += w * (float)((c >> 8) & 0xFF);
                b += w * (float)(c & 0xFF);
            }
            m[3 * x] = r;
            m[3 * x + 1] = g;
            m[3 * x + 2] = b;
        }
    }
    for (y = 0; y < fit_h; ++y) {
        uint32_t *o = out->pixels + (size_t)(fit_y + y) * out->width + fit_x;
        make_taps(&ty, y, fit_h, frame_h, src->height, prescale, offset);
        for (x = 0; x < fit_w; ++x) {
            px p = {0, 0, 0};
            for (k = 0; k < ty.count; ++k) {
                const float *m = mid + ((size_t)clampi(ty.first + k, 0, src->height - 1) * fit_w + x) * 3;
                p.r += ty.w[k] * m[0];
                p.g += ty.w[k] * m[1];
                p.b += ty.w[k] * m[2];
            }
            o[x] = pack(p);
        }
    }
    free(mid);
    free(tx);
}

void vv4k_fit_bilinear(const vv4k_image *frame, vv4k_image *out, int fit_x, int fit_y, int fit_w, int fit_h) {
    int x, y;
    for (y = 0; y < fit_h; ++y) {
        double v = (y + 0.5) * frame->height / (double)fit_h - 0.5;
        int y0 = (int)floor(v);
        float fy = (float)(v - y0);
        int ya = clampi(y0, 0, frame->height - 1), yb = clampi(y0 + 1, 0, frame->height - 1);
        for (x = 0; x < fit_w; ++x) {
            double u = (x + 0.5) * frame->width / (double)fit_w - 0.5;
            int x0 = (int)floor(u);
            float fx = (float)(u - x0);
            int xa = clampi(x0, 0, frame->width - 1), xb = clampi(x0 + 1, 0, frame->width - 1);
            px a = unpack(frame->pixels[(size_t)ya * frame->width + xa]);
            px b = unpack(frame->pixels[(size_t)ya * frame->width + xb]);
            px c = unpack(frame->pixels[(size_t)yb * frame->width + xa]);
            px d = unpack(frame->pixels[(size_t)yb * frame->width + xb]);
            px p;
            p.r = (a.r * (1 - fx) + b.r * fx) * (1 - fy) + (c.r * (1 - fx) + d.r * fx) * fy;
            p.g = (a.g * (1 - fx) + b.g * fx) * (1 - fy) + (c.g * (1 - fx) + d.g * fx) * fy;
            p.b = (a.b * (1 - fx) + b.b * fx) * (1 - fy) + (c.b * (1 - fx) + d.b * fx) * fy;
            out->pixels[(size_t)(fit_y + y) * out->width + fit_x + x] = pack(p);
        }
    }
}

void vv4k_fit_nearest(const vv4k_image *frame, vv4k_image *out, int fit_x, int fit_y, int fit_w, int fit_h) {
    int x, y;
    for (y = 0; y < fit_h; ++y) {
        int sy = clampi((int)((y + 0.5) * frame->height / fit_h), 0, frame->height - 1);
        for (x = 0; x < fit_w; ++x) {
            int sx = clampi((int)((x + 0.5) * frame->width / fit_w), 0, frame->width - 1);
            out->pixels[(size_t)(fit_y + y) * out->width + fit_x + x] = frame->pixels[(size_t)sy * frame->width + sx];
        }
    }
}

void vv4k_fit_rect(int frame_w, int frame_h, int out_w, int out_h, int *x, int *y, int *w, int *h) {
    /* As large as fits, aspect kept (SDL_RenderSetLogicalSize's own rule, rounded to whole pixels). */
    if ((long long)out_w * frame_h >= (long long)out_h * frame_w) {
        *h = out_h;
        *w = (int)(((long long)out_h * frame_w + frame_h / 2) / frame_h);
    } else {
        *w = out_w;
        *h = (int)(((long long)out_w * frame_h + frame_w / 2) / frame_w);
    }
    *x = (out_w - *w) / 2;
    *y = (out_h - *h) / 2;
}

int vv4k_render(int filter, const vv4k_image *frame, vv4k_image *out) {
    int fx, fy, fw, fh;
    size_t i;
    for (i = 0; i < (size_t)out->width * out->height; ++i) {
        out->pixels[i] = 0xFF000000u;
    }
    vv4k_fit_rect(frame->width, frame->height, out->width, out->height, &fx, &fy, &fw, &fh);
    switch (filter) {
    case VV4K_STOCK_NEAREST:
        vv4k_fit_nearest(frame, out, fx, fy, fw, fh);
        return 0;
    case VV4K_BILINEAR:
        vv4k_fit_bilinear(frame, out, fx, fy, fw, fh);
        return 0;
    case VV4K_SHARP_PIXELS: {
        vv4k_image big;
        int factor = (int)ceil((double)fh / frame->height - 1e-9);
        if (factor < 1) {
            factor = 1;
        }
        if (vv4k_nearest_integer(frame, factor, &big) != 0) {
            return -1;
        }
        vv4k_fit_catmull_rom(&big, frame->width, frame->height, factor, 0.0, out, fx, fy, fw, fh);
        vv4k_free(&big);
        return 0;
    }
    case VV4K_EDGE_DIRECTED: {
        vv4k_image x2, x4;
        if (vv4k_edge_directed_2x(frame, &x2) != 0) {
            return -1;
        }
        if (vv4k_edge_directed_2x(&x2, &x4) != 0) {
            vv4k_free(&x2);
            return -1;
        }
        vv4k_fit_catmull_rom(&x4, frame->width, frame->height, 4.0, -1.5, out, fx, fy, fw, fh);
        vv4k_free(&x2);
        vv4k_free(&x4);
        return 0;
    }
    case VV4K_EDGE_DIRECTED_2X: {
        vv4k_image x2;
        if (vv4k_edge_directed_2x(frame, &x2) != 0) {
            return -1;
        }
        vv4k_fit_catmull_rom(&x2, frame->width, frame->height, 2.0, -0.5, out, fx, fy, fw, fh);
        vv4k_free(&x2);
        return 0;
    }
    default:
        return -1;
    }
}
