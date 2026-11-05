/*
 * G30D read-only VSO shadow adapter.
 *
 * Safety property of SHADOW-V1:
 * - no PWM writes
 * - no Id/Iq writes
 * - no speed/angle feedback writes
 * - no HFI injection
 * - no motor state-machine calls
 *
 * It only consumes already-computed FOC values and benchmarks the VESC-derived
 * observer in parallel with the accepted SESC control path.
 */

#include "sesc_vso_shadow_g30.h"

#include "sesc_vso_types.h"
#include "vesc_observer_port.h"
#include "vesc_resistance_observer.h"

#include "FreeRTOS.h"
#include "conf_general.h"
#include "main.h"
#include "product.h"

#include <math.h>
#include <string.h>

#define VSO_PI_F 3.14159265358979323846f
#define VSO_FOC_HZ 16000u
#define VSO_OBSERVER_DIV 4u
#define VSO_RESISTANCE_DIV 16u

typedef struct {
    sesc_vso_state_t state;
    sesc_vso_resistance_state_t r_state;
    g30_vso_shadow_diag_t diag;

    uint8_t observer_div;
    uint8_t resistance_div;
    uint8_t seeded;
} g30_vso_shadow_ctx_t;

_Static_assert(sizeof(g30_vso_shadow_ctx_t) <= 192u,
               "VSO shadow heap context grew unexpectedly");

/*
 * Only this pointer consumes .bss. The context itself lives in the already
 * reserved FreeRTOS heap because FINAL-V1 has only tens of bytes linker RAM
 * headroom.
 */
static g30_vso_shadow_ctx_t *s_ctx;

static float s16_to_rad(int16_t a) {
    return (float)a * (VSO_PI_F / 32768.0f);
}

static int16_t rad_to_s16(float a) {
    while (a > VSO_PI_F) a -= 2.0f * VSO_PI_F;
    while (a < -VSO_PI_F) a += 2.0f * VSO_PI_F;

    float q = a * (32768.0f / VSO_PI_F);
    if (q > 32767.0f) q = 32767.0f;
    if (q < -32768.0f) q = -32768.0f;
    return (int16_t)q;
}

static uint16_t abs_s16_delta(int16_t a, int16_t b) {
    int16_t d = (int16_t)((uint16_t)a - (uint16_t)b);
    int32_t x = d;
    if (x < 0) x = -x;
    if (x > 32767) x = 32767;
    return (uint16_t)x;
}

static sesc_vso_observer_cfg_t current_cfg(void) {
    sesc_vso_observer_cfg_t c;

    c.resistance_ohm = mc_conf.foc_motor_r;
    c.inductance_h = mc_conf.foc_motor_l;
    c.ld_lq_diff_h = mc_conf.foc_motor_ld_lq_diff;
    c.flux_linkage_wb = mc_conf.foc_motor_flux_linkage;
    c.observer_gamma = mc_conf.foc_observer_gain;
    c.pll_kp = mc_conf.foc_pll_kp;
    c.pll_ki = mc_conf.foc_pll_ki;

    if (!(c.resistance_ohm > 0.0f)) c.resistance_ohm = 0.583f;
    if (!(c.inductance_h > 0.0f)) c.inductance_h = 0.000640f;
    if (!(c.flux_linkage_wb > 0.0f)) c.flux_linkage_wb = 0.0242f;
    if (!(c.observer_gamma > 0.0f)) c.observer_gamma = 9.0e7f;
    if (!(c.pll_kp > 0.0f)) c.pll_kp = 2000.0f;
    if (!(c.pll_ki > 0.0f)) c.pll_ki = 30000.0f;

    return c;
}

bool g30_vso_shadow_init(void) {
    if (s_ctx != 0) {
        return true;
    }

    g30_vso_shadow_ctx_t *ctx =
            (g30_vso_shadow_ctx_t *)pvPortMalloc(sizeof(g30_vso_shadow_ctx_t));

    if (ctx == 0) {
        return false;
    }

    memset(ctx, 0, sizeof(*ctx));
    ctx->diag.heap_alloc_ok = 1u;

    const sesc_vso_observer_cfg_t cfg = current_cfg();
    sesc_vso_observer_reset(&ctx->state, &cfg, 0.0f);
    sesc_vso_resistance_reset(&ctx->r_state, cfg.resistance_ohm);
    ctx->state.resistance_est = cfg.resistance_ohm;

    ctx->diag.initialized = 1u;
    s_ctx = ctx;
    return true;
}

void g30_vso_shadow_step(int16_t i_alpha_counts,
                         int16_t i_beta_counts,
                         int16_t v_alpha_counts,
                         int16_t v_beta_counts,
                         int16_t id_counts,
                         int16_t iq_counts,
                         uint32_t vbus_mv,
                         int16_t control_angle_s16) {
    g30_vso_shadow_ctx_t *ctx = s_ctx;
    if (ctx == 0) {
        return;
    }

    const uint32_t cyc0 = CPU_CYCLES;
    ctx->diag.fast_calls++;
    ctx->diag.control_angle_s16 = control_angle_s16;

    if (!ctx->seeded) {
        const sesc_vso_observer_cfg_t seed_cfg = current_cfg();
        sesc_vso_observer_reset(&ctx->state, &seed_cfg,
                                s16_to_rad(control_angle_s16));
        sesc_vso_resistance_reset(&ctx->r_state, seed_cfg.resistance_ohm);
        ctx->state.resistance_est = seed_cfg.resistance_ohm;
        ctx->seeded = 1u;
    }

    /*
     * Preserve the exact unit conventions already used by the existing G30
     * sensorless path.
     */
    const float inv_current_factor = 1.0f / (float)CURRENT_FACTOR_A;
    const float i_alpha = (float)i_alpha_counts * inv_current_factor;
    const float i_beta  = (float)i_beta_counts  * inv_current_factor;
    const float id      = (float)id_counts      * inv_current_factor;
    const float iq      = (float)iq_counts      * inv_current_factor;

    const float vbus = (float)vbus_mv * 0.001f;
    const float v_scale = vbus * (1.0f / 32768.0f);
    const float v_alpha = (float)v_alpha_counts * v_scale;
    const float v_beta  = (float)v_beta_counts  * v_scale;

    ctx->observer_div++;
    if (ctx->observer_div >= VSO_OBSERVER_DIV) {
        ctx->observer_div = 0u;
        sesc_vso_observer_cfg_t cfg = current_cfg();

        /*
         * Adaptive R is observed in SHADOW-V1 but is deliberately not fed back
         * into the MXV observer yet. That keeps the first comparison isolated.
         */
        float phase = 0.0f;
        sesc_vso_observer_update_mxv_lambda_lin(
                &ctx->state,
                &cfg,
                v_alpha,
                v_beta,
                i_alpha,
                i_beta,
                id,
                iq,
                (float)VSO_OBSERVER_DIV / (float)VSO_FOC_HZ,
                &phase);

        sesc_vso_pll_run(
                phase,
                (float)VSO_OBSERVER_DIV / (float)VSO_FOC_HZ,
                cfg.pll_kp,
                cfg.pll_ki,
                &ctx->state.pll_phase,
                &ctx->state.pll_speed);

        ctx->diag.observer_updates++;
        ctx->diag.observer_angle_s16 = rad_to_s16(phase);
        ctx->diag.phase_error_s16 =
                (int16_t)((uint16_t)ctx->diag.observer_angle_s16 -
                          (uint16_t)control_angle_s16);

        const uint16_t ae = abs_s16_delta(
                ctx->diag.observer_angle_s16, control_angle_s16);
        if (ae > ctx->diag.phase_error_abs_max_s16) {
            ctx->diag.phase_error_abs_max_s16 = ae;
        }

        ctx->diag.pll_erpm = (int32_t)(
                ctx->state.pll_speed * (60.0f / (2.0f * VSO_PI_F)));
        ctx->diag.lambda_uwb =
                (uint32_t)fmaxf(0.0f, ctx->state.observer.lambda_est * 1000000.0f);

        if (!isfinite(phase) ||
                !isfinite(ctx->state.pll_speed) ||
                !isfinite(ctx->state.observer.lambda_est)) {
            ctx->diag.nonfinite_events++;
        }
    }

    ctx->resistance_div++;
    if (ctx->resistance_div >= VSO_RESISTANCE_DIV) {
        ctx->resistance_div = 0u;
        const sesc_vso_observer_cfg_t cfg = current_cfg();

        const float r = sesc_vso_resistance_step(
                &ctx->r_state,
                cfg.resistance_ohm,
                cfg.inductance_h,
                i_alpha,
                i_beta,
                v_alpha,
                v_beta,
                ctx->state.observer.x1,
                ctx->state.observer.x2,
                ctx->state.pll_speed,
                (float)VSO_RESISTANCE_DIV / (float)VSO_FOC_HZ);

        ctx->state.resistance_est = r;
        ctx->diag.resistance_mohm =
                (uint32_t)fmaxf(0.0f, r * 1000.0f);
        ctx->diag.resistance_updates++;
    }

    const uint32_t cycles = (uint32_t)(CPU_CYCLES - cyc0);
    ctx->diag.cycles_last = cycles;
    if (cycles > ctx->diag.cycles_max) {
        ctx->diag.cycles_max = cycles;
    }
}

g30_vso_shadow_diag_t g30_vso_shadow_get_diag(void) {
    g30_vso_shadow_diag_t d;
    memset(&d, 0, sizeof(d));

    if (s_ctx != 0) {
        d = s_ctx->diag;
    }

    return d;
}

void g30_vso_shadow_reset_diag(void) {
    if (s_ctx == 0) return;

    s_ctx->diag.fast_calls = 0u;
    s_ctx->diag.observer_updates = 0u;
    s_ctx->diag.resistance_updates = 0u;
    s_ctx->diag.nonfinite_events = 0u;
    s_ctx->diag.cycles_last = 0u;
    s_ctx->diag.cycles_max = 0u;
    s_ctx->diag.phase_error_abs_max_s16 = 0u;
}
