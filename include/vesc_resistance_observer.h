#ifndef VESC_RESISTANCE_OBSERVER_H
#define VESC_RESISTANCE_OBSERVER_H

typedef struct {
    float r_est_state;
    float r_est;
} sesc_vso_resistance_state_t;

void sesc_vso_resistance_reset(sesc_vso_resistance_state_t *st,
                               float nominal_r_ohm);

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
        float dt);

#endif
