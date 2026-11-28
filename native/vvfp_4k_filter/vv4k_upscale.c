/* vv4k_upscale -- run the CPU reference filters on one game frame (research prototype, not shipped).

   usage: vv4k_upscale.exe <frame.argb> <width> <height> <out width> <out height> <out prefix> [repeats]

   <frame.argb> is the raw frame, 0xAARRGGBB little-endian (SDL_PIXELFORMAT_ARGB8888, as the game hands it to
   SDL_UpdateTexture).  Writes <out prefix>.<filter>.argb for each candidate and prints the single-thread CPU time of
   each (the best of `repeats` runs, default 1) -- the cost of doing the filter on the CPU (option b). */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

#include "vv4k_filters.h"

static double now_ms(void) {
    LARGE_INTEGER f, c;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    return 1000.0 * (double)c.QuadPart / (double)f.QuadPart;
}

int main(int argc, char **argv) {
    vv4k_image frame, out;
    FILE *file;
    int filter, repeats;
    char path[1024];
    if (argc < 7) {
        printf("usage: vv4k_upscale <frame.argb> <w> <h> <out w> <out h> <out prefix> [repeats]\n");
        return 2;
    }
    if (vv4k_alloc(&frame, atoi(argv[2]), atoi(argv[3])) != 0 || vv4k_alloc(&out, atoi(argv[4]), atoi(argv[5])) != 0) {
        return 3;
    }
    repeats = argc > 7 ? atoi(argv[7]) : 1;
    if (fopen_s(&file, argv[1], "rb") != 0 || file == NULL) {
        printf("FAIL open %s\n", argv[1]);
        return 4;
    }
    if (fread(frame.pixels, 4, (size_t)frame.width * frame.height, file) != (size_t)frame.width * frame.height) {
        printf("FAIL short frame\n");
        fclose(file);
        return 5;
    }
    fclose(file);
    for (filter = 0; filter < VV4K_FILTER_COUNT; ++filter) {
        double best = 1e30;
        int i;
        for (i = 0; i < repeats; ++i) {
            double t0 = now_ms();
            if (vv4k_render(filter, &frame, &out) != 0) {
                printf("FAIL %s\n", vv4k_filter_names[filter]);
                return 6;
            }
            t0 = now_ms() - t0;
            if (t0 < best) {
                best = t0;
            }
        }
        sprintf_s(path, sizeof path, "%s.%s.argb", argv[6], vv4k_filter_names[filter]);
        if (fopen_s(&file, path, "wb") != 0 || file == NULL) {
            printf("FAIL write %s\n", path);
            return 7;
        }
        fwrite(out.pixels, 4, (size_t)out.width * out.height, file);
        fclose(file);
        printf("cpu %-14s %dx%d -> %dx%d  %.1f ms (best of %d, one thread)\n", vv4k_filter_names[filter], frame.width,
               frame.height, out.width, out.height, best, repeats);
    }
    vv4k_free(&frame);
    vv4k_free(&out);
    return 0;
}
