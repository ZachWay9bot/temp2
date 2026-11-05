/*
 * VESC adaptive resistance observer extracted for SESC-VSO.
 *
 * Derived from vedderb/bldc motor/mcpwm_foc.c at
 * 21e66bb9efb41322c84f34c1db03a71ffeb7d8a1.
 *
 * Reference noted by upstream:
 * "An adaptive flux observer for the permanent magnet synchronous motor"
 * https://doi.org/10.1002/acs.2587
 */

#include "vesc_resistance_observer.h"

#include <math.h>
#include <stddef.h>

static float clampf(float x, float lo, float hi) {
    if (x < lo) return lo;
    if (x > hi) return hi;
    return x;
}

void sesc_vso_resistance_reset(sesc_vso_resistance_state_t *st,
                               float nominal_r_ohm) {
    if (st == NULL) return;
    st->r_est_state = nominal_r_ohm;
    st->r_est = nominal_r_ohm;
}

float sesc_vso_resistance_step(
        sesc_vso_resistance_state_t *st,
        float nominal_r_ohm,
        float inductance_h,
        float i_alpha,
        float i_beta,
        float v_alpha,
        float v_beta,
        float observer_x1,
        float observer_x2,
        float electrical_speed_rad_s,
        float dt) {
    if (st == NULL || dt <= 0.0f || nominal_r_ohm <= 0.0f) {
        return nominal_r_ohm;
    }

    const float gain = 0.00002f;
    const float i_abs_sq = i_alpha * i_alpha + i_beta * i_beta;

    st->r_est = st->r_est_state -
            0.5f * gain * inductance_h * i_abs_sq;

    const float cross =
            electrical_speed_rad_s *
            (i_beta * observer_x1 - i_alpha * observer_x2);

    const float electric_power =
            i_alpha * v_alpha + i_beta * v_beta;

    const float res_dot = -gain *
            (st->r_est * i_abs_sq + cross - electric_power);

    st->r_est_state += res_dot * dt;
    st->r_est_state = clampf(st->r_est_state,
                             nominal_r_ohm * 0.25f,
                             nominal_r_ohm * 3.0f);

    if (!isfinite(st->r_est_state)) {
        st->r_est_state = nominal_r_ohm;
    }
    if (!isfinite(st->r_est)) {
        st->r_est = nominal_r_ohm;
    }

    return st->r_est;
}
