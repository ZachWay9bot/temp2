#ifndef SESC_VSO_TYPES_H
#define SESC_VSO_TYPES_H

#include <stdint.h>
#include <stdbool.h>

typedef enum {
    SESC_VSO_IDLE = 0,
    SESC_VSO_HFI_ACQUIRE,
    SESC_VSO_HFI_LOCK,
    SESC_VSO_OPENLOOP_ASSIST,
    SESC_VSO_OBSERVER_ACQUIRE,
    SESC_VSO_BLEND,
    SESC_VSO_RUN_OBSERVER,
    SESC_VSO_REACQUIRE,
    SESC_VSO_FAULT
} sesc_vso_mode_t;

typedef struct {
    float x1;
    float x2;
    float lambda_est;
    float i_alpha_last;
    float i_beta_last;
} sesc_vso_observer_state_t;

typedef struct {
    float angle;
    float double_integrator;
    float prev_sample;
    float prev_sample_d;
    float last_di;
    float last_di_d;
    float confidence;

    float amb_pos_sum;
    float amb_pos_count;
    float amb_zero_sum;
    float amb_zero_count;

    uint16_t est_done_cnt;
    uint16_t pair_count;
    uint8_t amb_bucket;

    bool is_samp_n;
    bool ready;
    bool ambiguity_done;
    bool using_hfi;
} sesc_vso_hfi_state_t;

/*
 * Kept deliberately smaller than VESC motor_all_state_t.
 * Add fields only when the extracted algorithm proves they are required.
 */
typedef struct {
    sesc_vso_mode_t mode;
    sesc_vso_observer_state_t observer;
    sesc_vso_hfi_state_t hfi;

    float pll_phase;
    float pll_speed;
    float observer_confidence;
    float blend;
    float resistance_est;

    uint16_t bad_count;
    uint16_t good_count;
} sesc_vso_state_t;

#endif
