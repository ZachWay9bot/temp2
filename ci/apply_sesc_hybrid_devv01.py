from pathlib import Path

root=Path("SOURCE_KOXX3")

# Build name
p=root/"common_files/src/defines.h"
s=p.read_text()
s=s.replace('#define HW_NAME "G30D-R3I23-HS3-HF4SL1"',
            '#define HW_NAME "SESC-HYBRID-DEVV0.1"')
p.write_text(s)

# Iq ramp + fallback latch
p=root/"common_files/src/VescToSTM.c"
s=p.read_text()
old='''int16_t VescToSTM_Iq_lim_hook(int16_t iq){
#ifdef G30P
    if(g30_r3i_sensorless_active() && g30_r3i_active_age_ms()<800u){
        int16_t lim=(int16_t)current_to_torque(1000);
        if(iq>lim)iq=lim;else if(iq< -lim)iq=-lim;
    }
#endif
'''
new='''int16_t VescToSTM_Iq_lim_hook(int16_t iq){
#ifdef G30P
    if(g30_r3i_sensorless_active()){
        /* DevV0.1: keep the proven 1 A catch window, but never jump directly
         * from 1 A to the full requested torque at 800 ms. Ramp to the actual
         * requested Iq over the following 1000 ms. Hall mode is untouched. */
        const uint32_t hold_ms=800u;
        const uint32_t ramp_ms=1000u;
        uint32_t age=g30_r3i_active_age_ms();
        int32_t one_a=current_to_torque(1000);
        int32_t req=(int32_t)iq;
        int32_t sign=req<0?-1:1;
        int32_t mag=req<0?-req:req;
        if(mag>one_a){
            int32_t lim;
            if(age<hold_ms){
                lim=one_a;
            }else if(age<hold_ms+ramp_ms){
                uint32_t t=age-hold_ms;
                lim=one_a + (int32_t)(((int64_t)(mag-one_a)*(int64_t)t)/(int64_t)ramp_ms);
            }else{
                lim=mag;
            }
            if(mag>lim)mag=lim;
            iq=(int16_t)(sign*mag);
        }
    }
#endif
'''
assert old in s
s=s.replace(old,new)
old='''    if(ps.mode==2u){
        /* HF4: FO76 can request Coast after a catch/observer fallback while
         * g30_r3i still says mode 2. Do not leave Auto-Arm in this zombie
         * state. Clear the failed takeover once and return to armed BEMF
         * capture. Repeated VESC drive packets will then restart MCSDK as
         * soon as its stop state reaches IDLE. */
        if(!g30_fo76_coast_requested()) return;
        VescToSTM_pwm_stop();
        g30_fo76_sensorless_clear();
        g30_fo76_request_takeover(0u);
        g30_r3i_request_arm(1u);
        ps=g30_r3i_get_diag();
    }
'''
new='''    if(ps.mode==2u){
        /* DevV0.1: a true observer fallback stays latched while the non-zero
         * drive command remains present. Repeated drive packets may not clear
         * or re-arm it. Release/zero uses the normal coast path to re-arm. */
        if(!g30_fo76_coast_requested()) return;
        VescToSTM_pwm_stop();
        return;
    }
'''
assert old in s
s=s.replace(old,new)
p.write_text(s)

# Observer run-valid grace
p=root/"common_files/src/g30_fo76_shadow.c"
s=p.read_text()
s=s.replace('#define G30_R3H_OBSERVER_COAST_MIN_DPP 64\n',
            '#define G30_R3H_OBSERVER_COAST_MIN_DPP 64\n#define G30_DEVV01_RUN_BAD_GRACE_1K 4u\n')
s=s.replace('static uint32_t takeover_entries, takeover_fallbacks;\n',
            'static uint32_t takeover_entries, takeover_fallbacks;\nstatic uint8_t observer_run_bad_1k;\n')
s=s.replace('    d.good_eval_1k=0u;d.valid=0u;\n',
            '    d.good_eval_1k=0u;d.valid=0u;observer_run_bad_1k=0u;\n',1)
s=s.replace('    d.valid=0u;d.tracking=0u;d.seeded=0u;d.good_eval_1k=0u;\n',
            '    d.valid=0u;d.tracking=0u;d.seeded=0u;d.good_eval_1k=0u;observer_run_bad_1k=0u;\n',1)
s=s.replace('    d.max_abs_error=0; d.clamp_count=0; d.over90_count=0; d.within30_count=0;\n',
            '    d.max_abs_error=0; d.clamp_count=0; d.over90_count=0; d.within30_count=0;\n    observer_run_bad_1k=0u;\n',1)
s=s.replace('        d.valid=0; d.good_eval_1k=0; d.tracking=0; d.seeded=0;\n',
            '        d.valid=0; d.good_eval_1k=0; d.tracking=0; d.seeded=0; observer_run_bad_1k=0u;\n')
s=s.replace('        d.seeded=1; d.valid=0; d.good_eval_1k=0; d.tracking=0; decim4=0;\n',
            '        d.seeded=1; d.valid=0; d.good_eval_1k=0; d.tracking=0; observer_run_bad_1k=0u; decim4=0;\n')
s=s.replace('        uint8_t clamped_now=0;\n',
            '        uint8_t clamped_now=0;\n        uint8_t hard_clamped_now=0;\n',1)
s=s.replace('                d.clamp_hard++;\n                clamped_now=1;\n',
            '                d.clamp_hard++;\n                clamped_now=1;\n                hard_clamped_now=1;\n',1)
old='''            if(model_good){if(d.good_eval_1k<200u)d.good_eval_1k++;}
            else d.good_eval_1k=0;
            d.valid=d.good_eval_1k>=required_good;
            if(d.valid)d.valid_eval_1k++;
        }else{d.valid=0;d.good_eval_1k=0;}
'''
new='''            /* DevV0.1: strict entry, short dropout tolerance only after the
             * observer already owns FOC. One soft radial-clamp sample no
             * longer forces Coast. Four consecutive soft-bad 1 kHz samples
             * do. Severe flux collapse or hard clamp still drops immediately. */
            uint8_t stable_run=(uint8_t)(sensorless_external &&
                sensorless_catch_state==0u &&
                takeover_state==G30_TK_OBSERVER && d.valid);
            uint8_t severe_bad=(uint8_t)(hard_clamped_now ||
                d.magnitude_uwb<(uint16_t)(lambda/4) ||
                d.magnitude_uwb>(uint16_t)(lambda*2));
            if(stable_run){
                if(model_good){
                    observer_run_bad_1k=0u;
                    d.good_eval_1k=200u;
                    d.valid=1u;
                }else if(severe_bad){
                    observer_run_bad_1k=G30_DEVV01_RUN_BAD_GRACE_1K;
                    d.good_eval_1k=0u;
                    d.valid=0u;
                }else{
                    if(observer_run_bad_1k<255u)observer_run_bad_1k++;
                    if(observer_run_bad_1k>=G30_DEVV01_RUN_BAD_GRACE_1K){
                        d.good_eval_1k=0u;
                        d.valid=0u;
                    }else{
                        d.good_eval_1k=200u;
                        d.valid=1u;
                    }
                }
            }else{
                observer_run_bad_1k=0u;
                if(model_good){if(d.good_eval_1k<200u)d.good_eval_1k++;}
                else d.good_eval_1k=0u;
                d.valid=d.good_eval_1k>=required_good;
            }
            if(d.valid)d.valid_eval_1k++;
        }else{d.valid=0;d.good_eval_1k=0;observer_run_bad_1k=0u;}
'''
assert old in s
s=s.replace(old,new)
p.write_text(s)

print("SESC Hybrid DevV0.1 source patch applied")
