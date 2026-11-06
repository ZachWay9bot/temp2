from pathlib import Path

root=Path('SOURCE_KOXX3')

# -----------------------------------------------------------------------------
# Identity: comparison layer on proven pre-clonk SHUD4+BMS V1.
# -----------------------------------------------------------------------------
p=root/'common_files/src/defines.h'
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-P6500-HALL14S-SHUD4BMS-V1"\n#define G30_HALL14S_V1 1\n#define G30_SHUD4_BMS_V1 1'
new='#define HW_NAME "SESC-DRV126-P6500-H14-SHUD4PATH-CMP-V1"\n#define G30_HALL14S_V1 1\n#define G30_SHUD4_BMS_V1 1\n#define G30_SHUD4_FULLPATH_CMP_V1 1'
assert old in s
p.write_text(s.replace(old,new,1))

# -----------------------------------------------------------------------------
# Public helpers: direct SHUD4-style current-reference path.
# -----------------------------------------------------------------------------
p=root/'common_files/src/VescToSTM.h'
s=p.read_text()
needle='''void VescToSTM_g30_sensor_mode_sync(void);\n'''
insert='''void VescToSTM_g30_sensor_mode_sync(void);
#ifdef G30_SHUD4_FULLPATH_CMP_V1
void VescToSTM_g30_shud4_cmp_hold_pwm(bool hold);
void VescToSTM_g30_shud4_cmp_direct_ma(int32_t forward_ma);
#endif
'''
assert needle in s
p.write_text(s.replace(needle,insert,1))

# -----------------------------------------------------------------------------
# Direct current handoff, bypassing the SESC speed-PI torque-limiter.
# The 5 A clamp is intentionally a first-bench comparison guard, not a SHUD4
# performance claim. 55 A phase/current configuration remains unchanged.
# -----------------------------------------------------------------------------
p=root/'common_files/src/VescToSTM.c'
s=p.read_text()
marker='''volatile bool pwm_force; //State of PWM force on\n'''
insert=r'''volatile bool pwm_force; //State of PWM force on

#ifdef G30_SHUD4_FULLPATH_CMP_V1
#define G30_SHUD4_CMP_BENCH_MAX_MA 5000

void VescToSTM_g30_shud4_cmp_hold_pwm(bool hold){
    /* SHUD/no-KERS comparison: zero current while rolling is an energized
     * current-controlled state, NOT freewheel/coast. */
    pwm_force=hold;
}

void VescToSTM_g30_shud4_cmp_direct_ma(int32_t forward_ma){
    if(forward_ma<0) forward_ma=0; /* no KERS / no negative torque */
    if(forward_ma>G30_SHUD4_CMP_BENCH_MAX_MA)
        forward_ma=G30_SHUD4_CMP_BENCH_MAX_MA;

    if(forward_ma && !VescToSTM_g30_hall_direction_allowed(1))
        forward_ma=0;

    VescToSTM_mode=STM_STATE_TORQUE;
    VescToSTM_set_open_loop(false,0,0);

    /* Physical FWD follows the already proven G30 direction inversion. */
    float iq=((float)(forward_ma * DIR_MUL))/1000.0f;
    VescToSTM_set_current(iq,0.0f);

    /* MCI_SetCurrentReferences is a buffered EXTERNAL-current command.
     * Starting from IDLE with it is an MCSDK-supported path and makes the
     * drive request feed the FOC directly, matching SHUD's slow-request ->
     * fast-current-loop architecture much more closely than SESC speed PI. */
    if(STM_GetState(&STM[M1])==IDLE){
        (void)MCI_StartMotor(pMCI[M1]);
    }else if(STM_GetState(&STM[M1])==RUN){
        VescToSTM_pwm_start();
    }
}
#endif
'''
assert marker in s
s=s.replace(marker,insert,1)
p.write_text(s)

# -----------------------------------------------------------------------------
# Dashboard slow path:
# - keep proven G30 transport/input validation and neutral arm as a safety shell
# - once "drive" is validated, use reconstructed SHUD4 DPC + request state
# - direct current reference, no SESC speed PI
# - throttle release above rate 500: current -> 0, PWM remains enabled
# - never negative request: no KERS
# - low speed shuts output off
# -----------------------------------------------------------------------------
p=root/'common_files/src/g30_dash_link.c'
s=p.read_text()

old='''    uint32_t last_input_ms, drive_commands, coast_commands, remote_claims;
    g30_dash_r2_control control;
} dash_link_state;'''
new='''    uint32_t last_input_ms, drive_commands, coast_commands, remote_claims;
#ifdef G30_SHUD4_FULLPATH_CMP_V1
    int32_t shud_request_ma, shud_target_ma;
    uint32_t shud_next_step_ms, shud_steps, shud_release_steps, shud_hard_offs;
    uint8_t shud_motor_enabled;
#endif
    g30_dash_r2_control control;
} dash_link_state;'''
assert old in s
s=s.replace(old,new,1)

claim_anchor='''/* Called on legitimate IoT VESC motor-control packets, before their setter.
 * The existing VESC command contents and motor setters are NOT changed. */
void g30_dash_link_vesc_claim(void) {'''
helper=r'''
#ifdef G30_SHUD4_FULLPATH_CMP_V1
#define G30_SHUD4_CMP_PHASE_LIMIT_MA 55000
#define G30_SHUD4_CMP_OUTPUT_CAP_MA   5000
#define G30_SHUD4_CMP_STEP_MS            5u
#define G30_SHUD4_CMP_DRIVE_SLEW_MA   6500
#define G30_SHUD4_CMP_RELEASE_FAST_MA  1500
#define G30_SHUD4_CMP_RELEASE_LOW_MA    500
#define G30_SHUD4_CMP_HOLD_RATE         500
#define G30_SHUD4_CMP_LOW_RATE          400

static int32_t g30_shud4_cmp_slew(int32_t cur,int32_t target,int32_t step){
    int32_t d=target-cur;
    if(d>step) return cur+step;
    if(d< -step) return cur-step;
    return target;
}

static int32_t g30_shud4_cmp_target_ma(uint8_t raw){
    /* Exact reconstructed SHUD DPC shape: n=clamp(raw-55,0,120),
     * target=current_limit*n^2/110^2. First comparison build then clamps
     * the physical phase-current request to 5 A for the lamp bench. */
    int32_t n=(int32_t)raw-55;
    if(n<0) n=0;
    if(n>120) n=120;
    int32_t target=(int32_t)(((int64_t)G30_SHUD4_CMP_PHASE_LIMIT_MA*
                              (int64_t)n*(int64_t)n)/(110ll*110ll));
    if(target>G30_SHUD4_CMP_OUTPUT_CAP_MA)
        target=G30_SHUD4_CMP_OUTPUT_CAP_MA;
    return target;
}

static int32_t g30_shud4_cmp_hall_rate(void){
    int32_t r=VescToSTM_get_erpm_fast()*2;
    return r<0 ? -r : r;
}

static void g30_shud4_cmp_hard_off(dash_link_state *d){
    if(!d) return;
    d->shud_target_ma=0;
    d->shud_request_ma=0;
    d->shud_motor_enabled=0u;
    d->shud_hard_offs++;
    VescToSTM_g30_shud4_cmp_direct_ma(0);
    VescToSTM_g30_shud4_cmp_hold_pwm(false);
    VescToSTM_pwm_stop();
}

static void g30_shud4_cmp_service(dash_link_state *d,uint32_t now,
        bool fresh,bool remote_busy,bool ready){
    if(!d) return;
    if((int32_t)(now-d->shud_next_step_ms)<0) return;
    d->shud_next_step_ms=now+G30_SHUD4_CMP_STEP_MS;
    d->shud_steps++;

    if(remote_busy || !fresh || !ready ||
       !VescToSTM_g30_hall_selected() ||
       !VescToSTM_g30_hall_feedback_valid()){
        g30_shud4_cmp_hard_off(d);
        return;
    }

    bool braking=d->brake>=G30_DASH_R2_BRAKE_BEGIN &&
                 d->brake<=G30_DASH_R2_INPUT_MAX;
    bool drive=d->control.driving && !braking &&
               d->gas>G30_DASH_R2_GAS_BEGIN;

    d->shud_target_ma=drive ? g30_shud4_cmp_target_ma(d->gas) : 0;

    if(d->shud_target_ma>0){
        d->shud_request_ma=g30_shud4_cmp_slew(
            d->shud_request_ma,d->shud_target_ma,G30_SHUD4_CMP_DRIVE_SLEW_MA);
        d->shud_motor_enabled=1u;
        VescToSTM_g30_shud4_cmp_hold_pwm(true);
        VescToSTM_g30_shud4_cmp_direct_ma(d->shud_request_ma);
        return;
    }

    if(!d->shud_motor_enabled){
        d->shud_request_ma=0;
        VescToSTM_g30_shud4_cmp_hold_pwm(false);
        return;
    }

    /* SHUD no-KERS/passive-release semantics used deliberately as a
     * comparison: no negative current and no bridge-off/coast while rolling.
     * This is active zero-current FOC, not freewheel. */
    int32_t rate=g30_shud4_cmp_hall_rate();
    d->shud_release_steps++;
    if(rate>G30_SHUD4_CMP_HOLD_RATE){
        d->shud_request_ma=g30_shud4_cmp_slew(
            d->shud_request_ma,0,G30_SHUD4_CMP_RELEASE_FAST_MA);
        VescToSTM_g30_shud4_cmp_hold_pwm(true);
        VescToSTM_g30_shud4_cmp_direct_ma(d->shud_request_ma);
        return;
    }
    if(rate>G30_SHUD4_CMP_LOW_RATE){
        d->shud_request_ma=g30_shud4_cmp_slew(
            d->shud_request_ma,0,G30_SHUD4_CMP_RELEASE_LOW_MA);
        VescToSTM_g30_shud4_cmp_hold_pwm(true);
        VescToSTM_g30_shud4_cmp_direct_ma(d->shud_request_ma);
        if(d->shud_request_ma!=0) return;
    }

    d->shud_request_ma=0;
    d->shud_motor_enabled=0u;
    VescToSTM_g30_shud4_cmp_direct_ma(0);
    VescToSTM_g30_shud4_cmp_hold_pwm(false);
    VescToSTM_pwm_stop();
}
#endif

'''
assert claim_anchor in s
s=s.replace(claim_anchor,helper+claim_anchor,1)

old='''    d->remote_claimed=1u;
    g30_dash_r2_remote_claim(&d->control);
    d->remote_claims++;
}'''
new='''    d->remote_claimed=1u;
    g30_dash_r2_remote_claim(&d->control);
#ifdef G30_SHUD4_FULLPATH_CMP_V1
    /* VESC/IoT remains available; hand ownership back cleanly before its
     * normal setter executes. */
    g30_shud4_cmp_hard_off(d);
#endif
    d->remote_claims++;
}'''
assert old in s
s=s.replace(old,new,1)

old='''    g30_dash_r2_action action=g30_dash_r2_step(&d->control,now,
        d->gas,d->brake,fresh,remote_busy,ready);
    if(action==G30_DASH_R2_COAST) {
        /* Existing HF4 brake implementation is true coast, never regen. */
        VescToSTM_set_brake(0);
        VescToSTM_g30_pushstart_command(false);
        d->coast_commands++;
    } else if(action==G30_DASH_R2_DRIVE) {
        /* A valid neutral-to-throttle transition arms the ORIGINAL
         * >=3 km/h sensorless push-start. Not a stationary start path. */
        uint16_t torque=g30_dash_r2_scale(d->gas);
        if(!torque) return;
        if(!VescToSTM_g30_hall_direction_allowed(1)){
            VescToSTM_g30_pushstart_command(false);
            d->coast_commands++;
            return;
        }
        VescToSTM_g30_pushstart_command(true);
        /* HF4SL1: no post-HF4 sensorless startup torque shaping here. The
         * dashboard is only an input adapter; motor start/catch stays HF4. */
        VescToSTM_set_current_rel_int((int32_t)torque);
        VescToSTM_timeout_reset();
        d->drive_commands++;
    }
}'''
new='''    g30_dash_r2_action action=g30_dash_r2_step(&d->control,now,
        d->gas,d->brake,fresh,remote_busy,ready);
#ifdef G30_SHUD4_FULLPATH_CMP_V1
    if(action==G30_DASH_R2_COAST) d->coast_commands++;
    else if(action==G30_DASH_R2_DRIVE) d->drive_commands++;
    g30_shud4_cmp_service(d,now,fresh,remote_busy,ready);
    if(d->shud_motor_enabled || d->shud_request_ma)
        VescToSTM_timeout_reset();
    return;
#else
    if(action==G30_DASH_R2_COAST) {
        /* Existing HF4 brake implementation is true coast, never regen. */
        VescToSTM_set_brake(0);
        VescToSTM_g30_pushstart_command(false);
        d->coast_commands++;
    } else if(action==G30_DASH_R2_DRIVE) {
        /* A valid neutral-to-throttle transition arms the ORIGINAL
         * >=3 km/h sensorless push-start. Not a stationary start path. */
        uint16_t torque=g30_dash_r2_scale(d->gas);
        if(!torque) return;
        if(!VescToSTM_g30_hall_direction_allowed(1)){
            VescToSTM_g30_pushstart_command(false);
            d->coast_commands++;
            return;
        }
        VescToSTM_g30_pushstart_command(true);
        VescToSTM_set_current_rel_int((int32_t)torque);
        VescToSTM_timeout_reset();
        d->drive_commands++;
    }
#endif
}'''
assert old in s
s=s.replace(old,new,1)

# Add diagnostics to existing g30_dash output.
needle='''    commands_printf(phandle,"R2 driveCmd=%lu coastCmd=%lu vescClaim=%lu vescHold=%u",
        (unsigned long)d->drive_commands,(unsigned long)d->coast_commands,
        (unsigned long)d->remote_claims,
        d->remote_claimed && (uint32_t)(HAL_GetTick()-d->last_remote_ms)<G30_DASH_R2_VESC_HOLD_MS);
'''
extra='''    commands_printf(phandle,"R2 driveCmd=%lu coastCmd=%lu vescClaim=%lu vescHold=%u",
        (unsigned long)d->drive_commands,(unsigned long)d->coast_commands,
        (unsigned long)d->remote_claims,
        d->remote_claimed && (uint32_t)(HAL_GetTick()-d->last_remote_ms)<G30_DASH_R2_VESC_HOLD_MS);
#ifdef G30_SHUD4_FULLPATH_CMP_V1
    commands_printf(phandle,
        "SHUD4CMP motor=%u request_mA=%ld target_mA=%ld rate=%ld step=%lu release=%lu hardOff=%lu cap=5000 noKERS=1 noCoast=1",
        d->shud_motor_enabled,(long)d->shud_request_ma,(long)d->shud_target_ma,
        (long)g30_shud4_cmp_hall_rate(),(unsigned long)d->shud_steps,
        (unsigned long)d->shud_release_steps,(unsigned long)d->shud_hard_offs);
#endif
'''
assert needle in s
s=s.replace(needle,extra,1)

p.write_text(s)

print('SHUD4 FULLPATH CMP V1 applied: validated dash gas -> SHUD DPC -> direct MCSDK EXTERNAL current; rolling zero-current PWM hold; no KERS; 5A bench cap')
