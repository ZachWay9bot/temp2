from pathlib import Path

root=Path('SOURCE_KOXX3')

# Identity
p=root/'common_files/src/defines.h'
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-P6500-HALL14S-SHUD4BMS-V1"\n#define G30_HALL14S_V1 1\n#define G30_SHUD4_BMS_V1 1'
new='#define HW_NAME "SESC-DRV126-P6500-H14-SHUD4BMS-CLONKFREE-V1"\n#define G30_HALL14S_V1 1\n#define G30_SHUD4_BMS_V1 1\n#define G30_SHUD4_CLONKFREE_V1 1'
assert old in s
p.write_text(s.replace(old,new,1))

p=root/'common_files/src/VescToSTM.c'
s=p.read_text()
proto_old='''volatile bool pwm_force; //State of PWM force on
'''
proto_new='''volatile bool pwm_force; //State of PWM force on
#ifdef G30_SHUD4_CLONKFREE_V1
static bool g30_shud4_coast_hold_allowed(void);
#endif
'''
assert proto_old in s
s=s.replace(proto_old,proto_new,1)

# Add exact SHUD no-KERS coast-hold threshold. The SHUD/stock hall-rate scale
# is ~313 units/kmh and the reconstructed CFW changes the passive release gate
# 1890 -> 500. On this G30 integration VescToSTM_get_erpm_fast()*2 is the
# matching electrical-rate quantity used by the Hall path.
needle='''bool VescToSTM_g30_hall_direction_allowed(int32_t requested){
'''
insert='''#ifdef G30_SHUD4_CLONKFREE_V1
#define G30_SHUD4_COAST_HOLD_ERPM 500

static bool g30_shud4_coast_hold_allowed(void){
    if(!VescToSTM_g30_hall_selected()) return false;
    if(PWM_Handle_M1._Super.PWM_off) return false; /* never energize from a zero command */
    if(!VescToSTM_g30_hall_feedback_valid()) return false;
    int32_t erpm=VescToSTM_get_erpm_fast()*2;
    if(erpm<0) erpm=-erpm;
    return erpm>G30_SHUD4_COAST_HOLD_ERPM;
}
#endif

'''
assert needle in s
s=s.replace(needle,insert+needle,1)

# Change automatic PWM-off feature: when already energized and rolling above the
# SHUD release threshold with valid Hall, zero-current coast keeps the FOC
# synchronized instead of dropping the bridge. No torque/regen is requested.
old='''\t//Do PWM off feature
\tif(fp.minimum_current>0 && pMCI[M1]->pSTM->hFaultOccurred == 0){
\t\tif(pwm_force == false && abs(iq) <= fp.minimum_current && abs(FW_M1.AvVolt_qd.q) < MIN_DUTY_PWM){
\t\t\tint32_t erpm = VescToSTM_get_erpm_fast()*2;
\t\t\tfloat rad_s = erpm * ((2.0 * M_PI) / 60.0);
\t\t\tmotor_voltage = rad_s * mc_conf.foc_motor_flux_linkage;
\t\t\tif(VescToSTM_overspeed()==false){
\t\t\t\tVescToSTM_pwm_stop();
\t\t\t}
\t\t}else{
\t\t\tVescToSTM_pwm_start();  //Function checks if PWM off otherwise it does nothing
\t\t}
\t}
'''
new='''\t//Do PWM off feature
\tif(fp.minimum_current>0 && pMCI[M1]->pSTM->hFaultOccurred == 0){
#ifdef G30_SHUD4_CLONKFREE_V1
        bool shud_coast_hold=(abs(iq)<=fp.minimum_current) && g30_shud4_coast_hold_allowed();
        if(shud_coast_hold){
            /* SHUD no-KERS behavior: keep an already-running Hall FOC alive at
             * zero current while the wheel is still moving. This preserves
             * electrical synchronization and avoids a PWM re-enable clonk. */
        }else
#endif
\t\tif(pwm_force == false && abs(iq) <= fp.minimum_current && abs(FW_M1.AvVolt_qd.q) < MIN_DUTY_PWM){
\t\t\tint32_t erpm = VescToSTM_get_erpm_fast()*2;
\t\t\tfloat rad_s = erpm * ((2.0 * M_PI) / 60.0);
\t\t\tmotor_voltage = rad_s * mc_conf.foc_motor_flux_linkage;
\t\t\tif(VescToSTM_overspeed()==false){
\t\t\t\tVescToSTM_pwm_stop();
\t\t\t}
\t\t}else{
\t\t\tVescToSTM_pwm_start();  //Function checks if PWM off otherwise it does nothing
\t\t}
\t}
'''
assert old in s
s=s.replace(old,new,1)

# Change explicit coast/zero handling. SHUD keeps motor_enabled while rolling
# above 500 and drives the signed request to zero. We do the same only if PWM is
# already on and live Hall is valid. Below threshold or on invalid Hall, retain
# the proven hard-coast path.
old='''static void VescToSTM_g30_coast_rearm(void){
    g30_r3i_set_drive_request(0u);
    /* HF2: electrical coast must happen BEFORE observer/takeover state is
     * changed. Otherwise a 16 kHz FOC interrupt can run on disconnected Hall
     * angle data for one or more cycles, which produces the observed hard
     * braking / DC-bus spike. */
    VescToSTM_pwm_stop();

    /* HallDevV0.1: an MC_SPEED_FDBK Hall fault is deliberately release-latched.
'''
new='''static void VescToSTM_g30_coast_rearm(void){
    g30_r3i_set_drive_request(0u);
#ifdef G30_SHUD4_CLONKFREE_V1
    if(g30_shud4_coast_hold_allowed()){
        /* Reconstructed SHUD no-KERS release behavior:
         *   hall-rate > 500 -> request toward zero, motor remains enabled.
         * Do NOT call pwm_start here; zero commands may only preserve an
         * already-running bridge. The live current controller naturally holds
         * the back-EMF voltage required for Iq=Id=0, so the next throttle
         * command re-engages without a zero-state PWM restart. */
        VescToSTM_set_open_loop(false,0,0);
        VescToSTM_set_current(0.0f,0.0f);
        SpeednTorqCtrlM1.PISpeed->wIntegralTerm=0;
        g30_fo76_sensorless_clear();
        g30_fo76_request_takeover(0u);
        g30_r3i_request_arm(0u);
        return;
    }
#endif
    /* True bridge-off coast is retained below the SHUD release threshold,
     * after a Hall validity loss, or if PWM was already off. */
    VescToSTM_pwm_stop();

    /* HallDevV0.1: an MC_SPEED_FDBK Hall fault is deliberately release-latched.
'''
assert old in s
s=s.replace(old,new,1)

p.write_text(s)
print('SHUD4 clonk-free coast hold applied: zero-current Hall FOC remains enabled only while already PWM-on and |ERPM|>500')
