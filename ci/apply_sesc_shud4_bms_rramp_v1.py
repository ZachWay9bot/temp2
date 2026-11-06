from pathlib import Path

root = Path('SOURCE_KOXX3')

# -----------------------------------------------------------------------------
# Identity: this is a minimal layer on the proven SHUD4+BMS V1 baseline.
# -----------------------------------------------------------------------------
p = root / 'common_files/src/defines.h'
s = p.read_text()
old = '#define HW_NAME "SESC-DRV126-P6500-HALL14S-SHUD4BMS-V1"\n#define G30_HALL14S_V1 1\n#define G30_SHUD4_BMS_V1 1'
new = '#define HW_NAME "SESC-DRV126-P6500-H14-SBMS-RRAMP-V1"\n#define G30_HALL14S_V1 1\n#define G30_SHUD4_BMS_V1 1\n#define G30_HALL_ROLLING_RAMP_V1 1'
assert old in s
p.write_text(s.replace(old, new, 1))

# -----------------------------------------------------------------------------
# Rolling re-engage mini-ramp.
#
# Goal:
#   Preserve the exact pre-clonk coast behavior and the exact fast FOC/PWM path.
#   Only soften the 0 -> throttle transition when the Hall motor is ALREADY
#   rolling. Standstill starts are intentionally untouched.
#
# Trigger:
#   Hall selected, first nonzero drive command after release, |ERPM| >= 1000.
#
# Shape:
#   1 A initial torque ceiling -> requested torque ceiling over 200 ms.
#   The dash/VESC control packets repeat, so update_torque() naturally advances
#   the ceiling without adding a timer task or touching the 16-kHz ISR.
# -----------------------------------------------------------------------------
p = root / 'common_files/src/VescToSTM.c'
s = p.read_text()

marker = '''void VescToSTM_g30_sensor_mode_sync(void){
'''
insert = r'''#ifdef G30P
#define G30_HALL_RRAMP_MIN_ERPM 1000
#define G30_HALL_RRAMP_MS 200u
#define G30_HALL_RRAMP_START_MA 1000

static uint8_t g30_hall_rramp_drive_active;
static uint8_t g30_hall_rramp_active;
static uint32_t g30_hall_rramp_start_ms;

static void g30_hall_rramp_release(void){
    g30_hall_rramp_drive_active=0u;
    g30_hall_rramp_active=0u;
}

static void g30_hall_rramp_arm_on_drive_edge(void){
    int32_t erpm;
    if(g30_hall_rramp_drive_active) return;
    g30_hall_rramp_drive_active=1u;
    g30_hall_rramp_active=0u;
    if(!VescToSTM_g30_hall_selected()) return;
    erpm=VescToSTM_get_erpm_fast()*2;
    if(erpm<0) erpm=-erpm;
    if(erpm>=G30_HALL_RRAMP_MIN_ERPM){
        g30_hall_rramp_start_ms=HAL_GetTick();
        g30_hall_rramp_active=1u;
    }
}

static int32_t g30_hall_rramp_limit_q(int32_t q){
    uint32_t age;
    int32_t sign,mag,start_q,cap;
    if(!g30_hall_rramp_active || !VescToSTM_g30_hall_selected()) return q;
    age=HAL_GetTick()-g30_hall_rramp_start_ms;
    if(age>=G30_HALL_RRAMP_MS){
        g30_hall_rramp_active=0u;
        return q;
    }
    sign=(q<0)?-1:1;
    mag=(q<0)?-q:q;
    start_q=current_to_torque(G30_HALL_RRAMP_START_MA);
    if(start_q<0) start_q=-start_q;
    if(mag<=start_q) return q;
    cap=start_q+(int32_t)(((int64_t)(mag-start_q)*(int64_t)age)/(int64_t)G30_HALL_RRAMP_MS);
    if(mag>cap) mag=cap;
    return sign*mag;
}
#endif

'''
assert marker in s
s = s.replace(marker, insert + marker, 1)

old = '''void VescToSTM_g30_pushstart_command(bool active){
    if(!active){
        VescToSTM_g30_coast_rearm();
        return;
    }

    if(VescToSTM_g30_hall_selected()){
'''
new = '''void VescToSTM_g30_pushstart_command(bool active){
    if(!active){
#ifdef G30P
        g30_hall_rramp_release();
#endif
        VescToSTM_g30_coast_rearm();
        return;
    }

    if(VescToSTM_g30_hall_selected()){
#ifdef G30P
        g30_hall_rramp_arm_on_drive_edge();
#endif
'''
assert old in s
s = s.replace(old, new, 1)

old = '''void VescToSTM_update_torque(int32_t q, int32_t min_erpm, int32_t max_erpm){
#ifdef G30P
    if(!VescToSTM_g30_hall_direction_allowed(q)){
        VescToSTM_set_brake(0);
        return;
    }
'''
new = '''void VescToSTM_update_torque(int32_t q, int32_t min_erpm, int32_t max_erpm){
#ifdef G30P
    if(!VescToSTM_g30_hall_direction_allowed(q)){
        VescToSTM_set_brake(0);
        return;
    }
#ifdef G30_HALL_ROLLING_RAMP_V1
    q=g30_hall_rramp_limit_q(q);
#endif
'''
assert old in s
s = s.replace(old, new, 1)

p.write_text(s)
print('RRAMP V1 applied: Hall rolling re-engage only, >1000 ERPM, 1A -> request in 200ms; coast and fast FOC untouched')
