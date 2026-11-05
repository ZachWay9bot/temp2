/*
 * SESC-VSO minimal VESC observer transplant.
 *
 * Derived from VESC firmware motor/foc_math.c at:
 *   vedderb/bldc
 *   commit 21e66bb9efb41322c84f34c1db03a71ffeb7d8a1
 *
 * VESC firmware copyright (c) Benjamin Vedder and contributors.
 * This derivative is intended to remain under the GNU GPL v3 terms
 * applicable to the upstream VESC firmware.
 *
 * This file intentionally contains only the selected
 * FOC_OBSERVER_MXV_LAMBDA_COMP_LIN behavior and PLL mathematics.
 * Hardware access, PWM, ADC, Hall, encoder, RTOS and VESC application
 * infrastructure are not part of this module.
 */

#include "vesc_observer_port.h"
#include "sesc_vso_math.h"

#include <math.h>
#include <stddef.h>

#ifndef SESC_VSO_PI
#define SESC_VSO_PI 3.14159265358979323846f
#endif

static float vso_clampf(float x, float lo, float hi) {
    if (x < lo) {
        return lo;
    }
    if (x > hi) {
        return hi;
    }
    return x;
}

static float vso_norm_angle(float a) {
    while (a > SESC_VSO_PI) {
        a -= 2.0f * SESC_VSO_PI;
    }
    while (a < -SESC_VSO_PI) {
        a += 2.0f * SESC_VSO_PI;
    }
    return a;
}

static float vso_finite_or_zero(float x) {
    return isfinite(x) ? x : 0.0f;
}

void sesc_vso_observer_reset(sesc_vso_state_t *state,
                             const sesc_vso_observer_cfg_t *cfg,
                             float electrical_angle_rad) {
    if (state == NULL || cfg == NULL) {
        return;
    }

    float s = 0.0f, c = 1.0f;
    sesc_vso_math_sincos(electrical_angle_rad, &s, &c);

    state->observer.x1 = c * cfg->flux_linkage_wb;
    state->observer.x2 = s * cfg->flux_linkage_wb;
    state->observer.lambda_est = cfg->flux_linkage_wb;
    state->observer.i_alpha_last = 0.0f;
    state->observer.i_beta_last = 0.0f;
    state->pll_phase = vso_norm_angle(electrical_angle_rad);
    state->pll_speed = 0.0f;
}

void sesc_vso_observer_update_mxv_lambda_lin(
        sesc_vso_state_t *state,
        const sesc_vso_observer_cfg_t *cfg,
        float v_alpha,
        float v_beta,
        float i_alpha,
        float i_beta,
        float id,
        float iq,
        float dt,
        float *phase_out) {
    if (state == NULL || cfg == NULL || dt <= 0.0f) {
        return;
    }

    float r = cfg->resistance_ohm;
    float l = cfg->inductance_h;
    const float lambda_nom = cfg->flux_linkage_wb;
    const float ld_lq_diff = cfg->ld_lq_diff_h;

    /*
     * VESC saliency adjustment retained from foc_observer_update().
     * For SPMSM ld_lq_diff can simply be configured as zero.
     */
    if (fabsf(id) > 0.1f || fabsf(iq) > 0.1f) {
        const float denom = id * id + iq * iq;
        if (denom > 1.0e-12f) {
            l = l - ld_lq_diff * 0.5f +
                ld_lq_diff * (iq * iq) / denom;
        }
    }

    const float l_ia = l * i_alpha;
    const float l_ib = l * i_beta;
    const float r_ia = r * i_alpha;
    const float r_ib = r * i_beta;
    const float gamma_half = cfg->observer_gamma * 0.5f;

    /* Selected VESC MXV observer integration. */
    state->observer.x1 += (v_alpha - r_ia) * dt;
    state->observer.x2 += (v_beta - r_ib) * dt;

    /*
     * Selected VESC FOC_OBSERVER_MXV_LAMBDA_COMP_LIN behavior.
     * Track flux magnitude with a linear low-pass update.
     */
    float mag = sesc_vso_math_hypot(state->observer.x1 - l_ia,
                          state->observer.x2 - l_ib);

    const float lp = 0.1f * gamma_half * dt *
                     state->observer.lambda_est *
                     state->observer.lambda_est;
    state->observer.lambda_est += lp * (mag - state->observer.lambda_est);
    state->observer.lambda_est = vso_clampf(state->observer.lambda_est,
                                            lambda_nom * 0.3f,
                                            lambda_nom * 2.5f);

    if (mag > state->observer.lambda_est && mag > 1.0e-12f) {
        const float scale = state->observer.lambda_est / mag;
        state->observer.x1 *= scale;
        state->observer.x2 *= scale;
    }

    state->observer.i_alpha_last = i_alpha;
    state->observer.i_beta_last = i_beta;

    state->observer.x1 = vso_finite_or_zero(state->observer.x1);
    state->observer.x2 = vso_finite_or_zero(state->observer.x2);

    /* Preserve the upstream low-magnitude stabilization behavior. */
    mag = sesc_vso_math_hypot(state->observer.x1, state->observer.x2);
    if (mag < lambda_nom * 0.5f) {
        state->observer.x1 *= 1.1f;
        state->observer.x2 *= 1.1f;
    }

    if (phase_out != NULL) {
        *phase_out = sesc_vso_math_atan2(state->observer.x2 - l_ib,
                                          state->observer.x1 - l_ia);
    }
}

void sesc_vso_pll_run(float phase,
                      float dt,
                      float kp,
                      float ki,
                      float *phase_var,
                      float *speed_var) {
    if (phase_var == NULL || speed_var == NULL || dt <= 0.0f) {
        return;
    }

    *phase_var = vso_finite_or_zero(*phase_var);
    *speed_var = vso_finite_or_zero(*speed_var);

    float delta_theta = vso_norm_angle(phase - *phase_var);
    *phase_var += (*speed_var + kp * delta_theta) * dt;
    *phase_var = vso_norm_angle(*phase_var);
    *speed_var += ki * delta_theta * dt;
}
