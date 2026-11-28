// sharp_picture.hlsl -- the shaders of "VVFP Sharp Picture.dll" (the 4K filter), shader model 3 (Direct3D 9).
// Compiled by scripts/build_vvfp_sharp_picture.ps1 (fxc) into headers the DLL includes.  The same arithmetic as the
// research prototype's CPU reference (native/vvfp_4k_filter/vv4k_filters.c), which docs/4k-filter-design.md
// describes; every pass draws one quad over its whole target and VPOS gives the target pixel.
//
//   ed_step1     frame (W x H)     -> lattice (2W x 2H): originals at even/even, step 1 at odd/odd
//   ed_step2     lattice (2W x 2H) -> doubled (2W x 2H): step 2 where X+Y is odd, the rest copied
//   fit_rows     doubled image     -> (window width) x (doubled height): Catmull-Rom along each row
//   fit_columns  rows picture      -> the window: Catmull-Rom along each column; outside the picture black

sampler2D src : register(s0);         // POINT, CLAMP
float4 srcSize : register(c0);        // width, height, 1/width, 1/height of src
float4 fitRect : register(c1);        // the picture's x, y, w, h in window pixels
float4 fitMap : register(c2);         // frame w, frame h, prescale, offset (src = prescale * frame + offset)
float4 fitKernel : register(c3);      // this pass's axis: stretch, support, taps, 0

static const float W1 = -0.129633, W2 = 0.629633;   // step 1 taps
static const float W3 = -0.175068, W4 = 0.675068;   // step 2 taps

float3 texel(float2 p) {
    return tex2Dlod(src, float4((p + 0.5) * srcSize.zw, 0, 0)).rgb;
}

float luma(float3 c) {
    return dot(c, float3(0.2126, 0.7152, 0.0722));
}

// P[r*4+c]: "\" is P0 P5 P10 P15, "/" is P3 P6 P9 P12.  Interpolate along the diagonal the picture changes less
// along (a soft mix near a tie), never outside the four nearest known neighbours.
float3 interpolate_window(float3 P[16], float wa, float wb) {
    float L[16];
    [unroll] for (int i = 0; i < 16; ++i) {
        L[i] = luma(P[i]);
    }
    float along_main = 4.0 * abs(L[5] - L[10]) +
                       2.0 * (abs(L[1] - L[6]) + abs(L[6] - L[11]) + abs(L[4] - L[9]) + abs(L[9] - L[14])) +
                       abs(L[0] - L[5]) + abs(L[10] - L[15]) + abs(L[2] - L[7]) + abs(L[8] - L[13]);
    float along_anti = 4.0 * abs(L[6] - L[9]) +
                       2.0 * (abs(L[2] - L[5]) + abs(L[5] - L[8]) + abs(L[7] - L[10]) + abs(L[10] - L[13])) +
                       abs(L[3] - L[6]) + abs(L[9] - L[12]) + abs(L[1] - L[4]) + abs(L[11] - L[14]);
    float3 main_line = wa * (P[0] + P[15]) + wb * (P[5] + P[10]);
    float3 anti_line = wa * (P[3] + P[12]) + wb * (P[6] + P[9]);
    float k = saturate(0.5 + (along_anti - along_main) / (2.0 * (0.1 * (along_anti + along_main) + 0.0001 / 255.0)));
    float3 o = lerp(anti_line, main_line, k);
    float3 lo = min(min(P[5], P[6]), min(P[9], P[10]));
    float3 hi = max(max(P[5], P[6]), max(P[9], P[10]));
    return clamp(o, lo, hi);
}

float4 ed_step1(float2 vpos : VPOS) : COLOR {
    float2 o = floor(vpos + 0.25);
    float2 i = floor(o * 0.5);
    float2 odd = o - 2.0 * i;
    if (odd.x + odd.y < 0.5) {
        return float4(texel(i), 1.0);
    }
    if (odd.x + odd.y < 1.5) {
        return float4(0.0, 0.0, 0.0, 1.0);
    }
    float3 P[16];
    [unroll] for (int r = 0; r < 4; ++r) {
        [unroll] for (int c = 0; c < 4; ++c) {
            P[r * 4 + c] = texel(i + float2(c - 1, r - 1));
        }
    }
    return float4(interpolate_window(P, W1, W2), 1.0);
}

float reflect_even(float v, float n) {
    v = abs(v);
    return v >= n ? 2.0 * (n - 1.0) - v : v;
}

float4 ed_step2(float2 vpos : VPOS) : COLOR {
    float2 o = floor(vpos + 0.25);
    if (fmod(o.x + o.y, 2.0) < 0.5) {
        return float4(texel(o), 1.0);
    }
    float3 P[16];
    [unroll] for (int r = 0; r < 4; ++r) {
        [unroll] for (int c = 0; c < 4; ++c) {
            float s = 2 * r - 3, t = 2 * c - 3;
            float2 q = float2(reflect_even(o.x + (s + t) * 0.5, srcSize.x), reflect_even(o.y + (s - t) * 0.5, srcSize.y));
            P[r * 4 + c] = texel(q);
        }
    }
    return float4(interpolate_window(P, W3, W4), 1.0);
}

float catmull_rom(float x) {
    x = abs(x);
    if (x < 1.0) {
        return (1.5 * x - 2.5) * x * x + 1.0;
    }
    if (x < 2.0) {
        return ((-0.5 * x + 2.5) * x - 4.0) * x + 2.0;
    }
    return 0.0;
}

float4 fit_rows(float2 vpos : VPOS) : COLOR {
    float2 p = floor(vpos + 0.25);
    float local = p.x + 0.5 - fitRect.x;
    if (local < 0.0 || local >= fitRect.z) {
        return float4(0.0, 0.0, 0.0, 1.0);
    }
    float c = fitMap.z * (local * fitMap.x / fitRect.z) + fitMap.w - 0.5;
    float lo = floor(c - fitKernel.y) + 1.0;
    float3 sum = 0.0;
    float wsum = 0.0;
    [unroll] for (int k = 0; k < 8; ++k) {
        if (k < fitKernel.z) {
            float w = catmull_rom((lo + k - c) * fitKernel.x);
            sum += w * texel(float2(lo + k, p.y));
            wsum += w;
        }
    }
    return float4(sum / wsum, 1.0);
}

float4 fit_columns(float2 vpos : VPOS) : COLOR {
    float2 p = floor(vpos + 0.25);
    float local = p.y + 0.5 - fitRect.y;
    if (local < 0.0 || local >= fitRect.w || p.x + 0.5 < fitRect.x || p.x + 0.5 >= fitRect.x + fitRect.z) {
        return float4(0.0, 0.0, 0.0, 1.0);
    }
    float c = fitMap.z * (local * fitMap.y / fitRect.w) + fitMap.w - 0.5;
    float lo = floor(c - fitKernel.y) + 1.0;
    float3 sum = 0.0;
    float wsum = 0.0;
    [unroll] for (int k = 0; k < 8; ++k) {
        if (k < fitKernel.z) {
            float w = catmull_rom((lo + k - c) * fitKernel.x);
            sum += w * texel(float2(p.x, lo + k));
            wsum += w;
        }
    }
    return float4(saturate(sum / wsum), 1.0);
}

float4 vs_quad(float4 p : POSITION) : POSITION {
    return p;
}
