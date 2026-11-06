from pathlib import Path

root = Path("SOURCE_KOXX3")

# Identity only.
p = root / "common_files/src/defines.h"
s = p.read_text()
old = '#define HW_NAME "SESC-DRV126-POWERCORE6500-POWERPATH-RESTORE-V1"'
new = '#define HW_NAME "SESC-DRV126-POWERCORE6500-HALL14S-V1"\n#define G30_HALL14S_V1 1'
assert old in s
p.write_text(s.replace(old, new, 1))

# Hall restart policy:
# - keep the hardware-validated POWERPATH RESTORE fast FOC byte-identical
# - do not estimate/preload voltage from speed/flux/VBUS
# - restart with zero PI state and zero voltage command
# - let Hall angle + measured current + existing DRV126/SHUD current slew bring torque in
p = root / "common_files/src/VescToSTM.c"
s = p.read_text()
old = '''        {
            /* HallDevV0.1: preserve the established preload formula, but feed
             * it from the live Hall speed every time PWM is re-enabled. */
#ifdef G30P
            if(VescToSTM_g30_hall_selected()){
                int32_t hall_erpm=VescToSTM_get_erpm_fast()*2;
                float hall_rad_s=(float)hall_erpm*((2.0f*(float)M_PI)/60.0f);
                motor_voltage=hall_rad_s*mc_conf.foc_motor_flux_linkage;
            }
#endif
            float fVd = 32768.0 / VescToSTM_get_bus_voltage() * motor_voltage;
            utils_truncate_number(&fVd, -32767, 32767);
            PIDIqHandle_M1.wIntegralTerm = fVd * TF_KIDIV;
            PIDIdHandle_M1.wIntegralTerm = -PIDIqHandle_M1.wIntegralTerm/4;
#ifdef G30P
            if(VescToSTM_g30_hall_selected()){
                int16_t drv_vq=(int16_t)fVd;
                int16_t drv_vd=(int16_t)(-drv_vq/4);
                g30_drv126_final_preload(drv_vq,drv_vd);
            }
#endif
        }'''
new = '''        {
#ifdef G30P
            if(VescToSTM_g30_hall_selected()){
                /*
                 * HALL14S-V1: stock-style Hall current-controller entry.
                 * Hall angle is already valid before gate enable. Start the
                 * current controller from zero state and let measured current
                 * error build the required voltage through the PI + SVPWM path.
                 *
                 * Deliberately NO speed*flux estimate, NO VBUS division and
                 * NO voltage/integrator preload. This makes Hall restart
                 * independent of the PA1 bus-voltage full-scale limitation.
                 */
                PIDIqHandle_M1.wIntegralTerm = 0;
                PIDIdHandle_M1.wIntegralTerm = 0;
                FOCVars[M1].Vqd.q = 0;
                FOCVars[M1].Vqd.d = 0;
                motor_voltage = 0.0f;
            }else
#endif
            {
                /* Legacy non-Hall fallback retained but unreachable in the
                 * Hall-only HALL14S build. */
                float fVd = 32768.0 / VescToSTM_get_bus_voltage() * motor_voltage;
                utils_truncate_number(&fVd, -32767, 32767);
                PIDIqHandle_M1.wIntegralTerm = fVd * TF_KIDIV;
                PIDIdHandle_M1.wIntegralTerm = -PIDIqHandle_M1.wIntegralTerm/4;
            }
        }'''
assert old in s
p.write_text(s.replace(old, new, 1))

print("HALL14S-V1 applied: Hall restart has zero PI/Vqd preload and no VBUS dependency; fast FOC untouched")
