#ifndef VESC_OBSERVER_PORT_H
#define VESC_OBSERVER_PORT_H

#include <stdbool.h>
#include "sesc_vso_types.h"

typedef struct {
    float resistance_ohm;
    float inductance_h;
    float ld_lq_diff_h;
    float flux_linkage_wb;
    float observer_gamma;
    float pll_kp;
    float pll_ki;
} sesc_vso_observer_cfg_t;

void sesc_vso_observer_reset(sesc_vso_state_t *state,
                             const sesc_vso_observer_cfg_t *cfg,
                             float electrical_angle_rad);

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
        float *phase_out);

void sesc_vso_pll_run(float phase,
                      float dt,
                      float kp,
                      float ki,
                      float *phase_var,
                      float *speed_var);

#endif
