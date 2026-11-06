from pathlib import Path

root=Path('SOURCE_KOXX3')

# Identity layer on the proven pre-clonk SHUD4+BMS V1 baseline.
p=root/'common_files/src/defines.h'
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-P6500-HALL14S-SHUD4BMS-V1"\n#define G30_HALL14S_V1 1\n#define G30_SHUD4_BMS_V1 1'
new='#define HW_NAME "SESC-DRV126-P6500-H14-SBMS-HSYNC-V1"\n#define G30_HALL14S_V1 1\n#define G30_SHUD4_BMS_V1 1\n#define G30_HALL_ROLLING_SYNC_V1 1'
assert old in s
p.write_text(s.replace(old,new,1))

p=root/'common_files/src/VescToSTM.c'
s=p.read_text()

# Add one narrow helper: seed the Hall electrical angle at the actual rolling
# position immediately before PWM is enabled. Do not touch coast behavior or
# the 16-kHz fast FOC/PWM path.
marker='''void VescToSTM_pwm_start(void){\n'''
helper=r'''#ifdef G30P
#define G30_HALL_ROLLING_SYNC_MIN_ERPM 1000
#define G30_HALL_SECTOR_S16 ((int32_t)(65536 / 6))

static void g30_hall_prepare_pwm_reentry_angle(void){
    int32_t erpm=VescToSTM_get_erpm_fast()*2;
    int16_t dpp=HALL_M1._Super.hElSpeedDpp;
    if(erpm<0) erpm=-erpm;

    if(VescToSTM_g30_hall_selected() &&
       HALL_M1.SensorIsReliable &&
       erpm>=G30_HALL_ROLLING_SYNC_MIN_ERPM &&
       dpp!=0){
        /*
         * TIM3 Hall mode resets CNT on every Hall edge. CNT therefore measures
         * elapsed time since the latest real rotor edge. Convert that elapsed
         * time to current-control periods and extrapolate from the exact
         * MeasuredElAngle using the already measured signed Hall speed.
         *
         * Cap extrapolation to one Hall sector. If anything is stale, the
         * seed can never run farther than the next physical Hall edge.
         */
        uint32_t cnt=(uint32_t)HALL_M1.TIMx->CNT;
        uint32_t psc=(uint32_t)HALL_M1.TIMx->PSC+1u;
        uint64_t num=(uint64_t)cnt*(uint64_t)psc*
                     (uint64_t)HALL_M1._Super.hMeasurementFrequency;
        uint32_t cycles=(uint32_t)((num+(HALL_M1.TIMClockFreq/2u))/
                                   (uint64_t)HALL_M1.TIMClockFreq);
        int32_t adpp=dpp<0 ? -(int32_t)dpp : (int32_t)dpp;
        uint32_t max_cycles=(uint32_t)((G30_HALL_SECTOR_S16+adpp-1)/adpp);
        if(cycles>max_cycles) cycles=max_cycles;

        int32_t delta=(int32_t)cycles*(int32_t)dpp;
        if(delta>G30_HALL_SECTOR_S16) delta=G30_HALL_SECTOR_S16;
        else if(delta< -G30_HALL_SECTOR_S16) delta=-G30_HALL_SECTOR_S16;

        int16_t seed=(int16_t)((int32_t)HALL_M1.MeasuredElAngle+delta);
        HALL_M1._Super.hElAngle=seed;
        HALL_M1.CompAngle=seed;
        HALL_M1.CompSpeed=0;
        /*
         * Deliberately preserve hElSpeedDpp, AvrElSpeedDpp and
         * hAvrMecSpeedUnit. HALL_CalcElAngle() can therefore continue
         * interpolation on the very first PWM/FOC cycle.
         */
        return;
    }

    /* Original HALL14S standstill/low-speed start behavior. */
    HALL_M1._Super.hElAngle=HALL_M1.MeasuredElAngle;
    HALL_M1.CompAngle=HALL_M1.MeasuredElAngle;
    HALL_M1.CompSpeed=0;
    HALL_M1._Super.hAvrMecSpeedUnit=0;
}
#endif

'''
assert marker in s
s=s.replace(marker,helper+marker,1)

old='''        HALL_M1._Super.hElAngle = HALL_M1.MeasuredElAngle;
        HALL_M1.CompSpeed = 0;
        HALL_M1._Super.hAvrMecSpeedUnit = 0;
        PWMC_SwitchOnPWM(&PWM_Handle_M1._Super);
'''
new='''#ifdef G30P
        if(VescToSTM_g30_hall_selected()){
            g30_hall_prepare_pwm_reentry_angle();
        }else
#endif
        {
            HALL_M1._Super.hElAngle = HALL_M1.MeasuredElAngle;
            HALL_M1.CompSpeed = 0;
            HALL_M1._Super.hAvrMecSpeedUnit = 0;
        }
        PWMC_SwitchOnPWM(&PWM_Handle_M1._Super);
'''
assert old in s
p.write_text(s.replace(old,new,1))

print('HSYNC V1 applied: pre-clonk coast unchanged; rolling Hall PWM reentry seeds live angle and preserves Hall speed')
