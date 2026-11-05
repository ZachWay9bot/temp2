/*
 * G30D / STM32F103 math overrides for SESC-VSO.
 * Reuses MCSDK integer trig and phase extraction.
 */

#include "sesc_vso_math.h"
#include "mc_math.h"

#include <math.h>
#include <stdint.h>

#define VSO_PI_F 3.14159265358979323846f

static int16_t rad_to_s16(float angle_rad) {
    while (angle_rad > VSO_PI_F) angle_rad -= 2.0f * VSO_PI_F;
    while (angle_rad < -VSO_PI_F) angle_rad += 2.0f * VSO_PI_F;

    float q = angle_rad * (32768.0f / VSO_PI_F);
    if (q > 32767.0f) q = 32767.0f;
    if (q < -32768.0f) q = -32768.0f;
    return (int16_t)q;
}

void sesc_vso_math_sincos(float angle_rad, float *s, float *c) {
    const Trig_Components t = MCM_Trig_Functions(rad_to_s16(angle_rad));
    if (s != 0) *s = (float)t.hSin * (1.0f / 32768.0f);
    if (c != 0) *c = (float)t.hCos * (1.0f / 32768.0f);
}

float sesc_vso_math_atan2(float y, float x) {
    const float ax = fabsf(x);
    const float ay = fabsf(y);
    const float m = ax > ay ? ax : ay;

    if (m < 1.0e-20f) return 0.0f;

    const float scale = 536870912.0f / m; /* 2^29 */
    const int32_t xi = (int32_t)(x * scale);
    const int32_t yi = (int32_t)(y * scale);
    const int16_t a = MCM_PhaseComputation(xi, yi);
    return (float)a * (VSO_PI_F / 32768.0f);
}

float sesc_vso_math_hypot(float x, float y) {
    /* Exact in the first shadow build; observer is decimated. */
    return sqrtf(x * x + y * y);
}
