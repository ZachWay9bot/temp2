#ifndef SESC_VSO_SHADOW_G30_H
#define SESC_VSO_SHADOW_G30_H

#include <stdint.h>
#include <stdbool.h>

typedef struct {
    uint32_t fast_calls;
    uint32_t observer_updates;
    uint32_t resistance_updates;
    uint32_t nonfinite_events;

    uint32_t cycles_last;
    uint32_t cycles_max;

    int16_t control_angle_s16;
    int16_t observer_angle_s16;
    int16_t phase_error_s16;
    uint16_t phase_error_abs_max_s16;

    int32_t pll_erpm;
    uint32_t lambda_uwb;
    uint32_t resistance_mohm;

    uint8_t initialized;
    uint8_t heap_alloc_ok;
} g30_vso_shadow_diag_t;

/* Call once from normal task/init context. Never allocates from ISR. */
bool g30_vso_shadow_init(void);

/*
 * Read-only shadow step. No PWM, current reference or angle output exists in
 * this API by design.
 */
void g30_vso_shadow_step(int16_t i_alpha_counts,
                         int16_t i_beta_counts,
                         int16_t v_alpha_counts,
                         int16_t v_beta_counts,
                         int16_t id_counts,
                         int16_t iq_counts,
                         uint32_t vbus_mv,
                         int16_t control_angle_s16);

g30_vso_shadow_diag_t g30_vso_shadow_get_diag(void);
void g30_vso_shadow_reset_diag(void);

#endif
