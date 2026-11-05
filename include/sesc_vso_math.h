#ifndef SESC_VSO_MATH_H
#define SESC_VSO_MATH_H

/*
 * Replaceable math hooks.
 *
 * Host/reference builds use src/sesc_vso_math_ref.c.
 * The G30 target provides strong replacements using the MCSDK integer
 * trig/CORDIC routines where that preserves the VESC math semantics.
 */
void sesc_vso_math_sincos(float angle_rad, float *s, float *c);
float sesc_vso_math_atan2(float y, float x);
float sesc_vso_math_hypot(float x, float y);

#endif
