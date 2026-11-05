from pathlib import Path
import re

root=Path('SOURCE_KOXX3')

# Build identity
p=root/'common_files/src/defines.h'
s=p.read_text()
assert '#define HW_NAME "SESC-DRV126-MOTORCORE-FINAL-V1"' in s
s=s.replace('#define HW_NAME "SESC-DRV126-MOTORCORE-FINAL-V1"',
            '#define HW_NAME "SESC-DRV126-HYBRID-FINAL-V1"',1)
p.write_text(s)

# Observer takeover: add safe observer->Hall return blend and mark direct hybrid takeover active.
p=root/'common_files/src/g30_fo76_shadow.h'
s=p.read_text()
old='uint16_t g30_fo76_control_angle(int16_t hall_angle, int16_t hall_speed_dpp);'
new='uint16_t g30_fo76_control_angle(int16_t hall_angle, int16_t hall_speed_dpp, uint8_t hybrid_mode, uint8_t hall_valid);'
assert old in s
s=s.replace(old,new,1)
anchor='#define G30_FO76_SHADOW_H\n'
assert anchor in s
s=s.replace(anchor,anchor+'\n#define G30_HYBRID_TAKEOVER_DPP 64u\n#define G30_HYBRID_RETURN_DPP 48u\n',1)
p.write_text(s)

p=root/'common_files/src/g30_fo76_shadow.c'
s=p.read_text()
assert '#define G30_R3G_TAKEOVER_MIN_DPP 64' in s
s=s.replace('#define G30_R3G_TAKEOVER_MIN_DPP 64', '#define G30_R3G_TAKEOVER_MIN_DPP G30_HYBRID_TAKEOVER_DPP',1)
assert '#define G30_R3H_OBSERVER_COAST_MIN_DPP 64' in s
s=s.replace('#define G30_R3H_OBSERVER_COAST_MIN_DPP 64',
'''#define G30_R3H_OBSERVER_COAST_MIN_DPP 64
#define G30_HYBRID_NOHALL_COAST_DPP 40''',1)
assert 'G30_TK_OBSERVER=3, G30_TK_FALLBACK=4' in s
s=s.replace('G30_TK_OBSERVER=3, G30_TK_FALLBACK=4',
            'G30_TK_OBSERVER=3, G30_TK_FALLBACK=4, G30_TK_RETURN_BLEND=5',1)

old='uint16_t g30_fo76_control_angle(int16_t hall_angle, int16_t hall_speed_dpp) {'
new='uint16_t g30_fo76_control_angle(int16_t hall_angle, int16_t hall_speed_dpp, uint8_t hybrid_mode, uint8_t hall_valid) {'
assert old in s
s=s.replace(old,new,1)

old='else {off=0;takeover_state=G30_TK_OBSERVER;}'
new='''else {
            off=0;
            takeover_state=G30_TK_OBSERVER;
            if(hybrid_mode){
                /* Hall->observer handover is now committed. Mark it exactly like
                 * the validated Hall-free path so run-dropout grace and observer
                 * speed reporting become authoritative, while the DRV126 current
                 * controller itself remains unchanged. */
                sensorless_external=1u;
                observer_run_bad_1k=0u;
            }
        }'''
assert old in s
s=s.replace(old,new,1)

old=r'''    /* R3H observer-only run state. Hall is diagnostic only from here onward.
     * Speed comes from the observer predictor: step_q4 is Q4 electrical DPP. */
    uint16_t observer_speed_dpp=(uint16_t)(abs_i16_u(takeover_step_foc_q4)>>4);
    if(!d.valid){takeover_latch_coast(G30_TK_FB_INVALID);takeover_control_phase=predicted;return predicted;}
    if(!d.tracking){takeover_latch_coast(G30_TK_FB_NOT_TRACKING);takeover_control_phase=predicted;return predicted;}
    if(observer_speed_dpp<G30_R3H_OBSERVER_COAST_MIN_DPP){takeover_latch_coast(G30_TK_FB_SPEED);takeover_control_phase=predicted;return predicted;}

    takeover_state=G30_TK_OBSERVER;
    takeover_control_phase=predicted;
    return predicted;'''
new=r'''    /* Observer run. In HYBRID mode Hall keeps running as a non-authoritative
     * reference so low-speed operation and a degraded observer can be handed
     * back smoothly instead of producing the old coast/release requirement.
     * Pure SENSORLESS mode retains the frozen R3H coast semantics. */
    uint16_t observer_speed_dpp=(uint16_t)(abs_i16_u(takeover_step_foc_q4)>>4);
    int16_t hall_err=(int16_t)(predicted-hall);
    uint8_t hall_return_ok=(uint8_t)(hybrid_mode && hall_valid &&
        hall_speed_dpp<0 && abs_phase16(hall_err)<G30_R3G_FALLBACK_ERR_COUNTS);

    if(takeover_state==G30_TK_RETURN_BLEND){
        if(!hall_return_ok){
            /* Hall disappeared or no longer agrees during the return. Abort the
             * hand-back and keep the observer authoritative; never snap angle. */
            takeover_blend_offset=0;
            takeover_state=G30_TK_OBSERVER;
        }else{
            int16_t off=takeover_blend_offset;
            uint16_t out=(uint16_t)(hall+off);
            if(off>G30_R3G_BLEND_STEP_COUNTS) off-=G30_R3G_BLEND_STEP_COUNTS;
            else if(off< -G30_R3G_BLEND_STEP_COUNTS) off+=G30_R3G_BLEND_STEP_COUNTS;
            else {
                off=0;
                out=hall;
                sensorless_external=0u;
                takeover_enable_request=0u;
                takeover_state=G30_TK_HALL_OFF;
                observer_run_bad_1k=0u;
            }
            takeover_blend_offset=off;
            takeover_control_phase=out;
            return out;
        }
    }

    if(hybrid_mode && sensorless_external){
        /* 64 DPP entry / 48 DPP return hysteresis. Observer degradation also
         * returns to Hall when Hall still agrees within 30 electrical degrees.
         * If Hall is unavailable we stay sensorless down to 40 DPP, then coast. */
        if(hall_return_ok &&
           (observer_speed_dpp<=G30_HYBRID_RETURN_DPP || !d.valid || !d.tracking)){
            takeover_blend_offset=(int16_t)(predicted-hall);
            takeover_state=G30_TK_RETURN_BLEND;
            uint16_t out=(uint16_t)(hall+takeover_blend_offset);
            takeover_control_phase=out;
            return out;
        }
        if(!d.valid){takeover_latch_coast(G30_TK_FB_INVALID);takeover_control_phase=predicted;return predicted;}
        if(!d.tracking){takeover_latch_coast(G30_TK_FB_NOT_TRACKING);takeover_control_phase=predicted;return predicted;}
        if(observer_speed_dpp<G30_HYBRID_NOHALL_COAST_DPP){takeover_latch_coast(G30_TK_FB_SPEED);takeover_control_phase=predicted;return predicted;}
    }else{
        if(!d.valid){takeover_latch_coast(G30_TK_FB_INVALID);takeover_control_phase=predicted;return predicted;}
        if(!d.tracking){takeover_latch_coast(G30_TK_FB_NOT_TRACKING);takeover_control_phase=predicted;return predicted;}
        if(observer_speed_dpp<G30_R3H_OBSERVER_COAST_MIN_DPP){takeover_latch_coast(G30_TK_FB_SPEED);takeover_control_phase=predicted;return predicted;}
    }

    takeover_state=G30_TK_OBSERVER;
    takeover_control_phase=predicted;
    return predicted;'''
assert old in s, 'observer tail missing'
s=s.replace(old,new,1)
p.write_text(s)

p=root/'common_files/src/mc_tasks.c'
s=p.read_text()

old='''  if(VescToSTM_g30_sensorless_selected() && g30_fo76_sensorless_active()){
    int16_t odpp=g30_fo76_control_speed_dpp();'''
new='''  if((VescToSTM_g30_sensorless_selected() || VescToSTM_g30_hall_selected()) &&
     g30_fo76_sensorless_active()){
    int16_t odpp=g30_fo76_control_speed_dpp();'''
assert old in s
s=s.replace(old,new,1)

old='if(VescToSTM_g30_hall_selected() && !VescToSTM_g30_hall_feedback_valid())\n    {'
new='if(VescToSTM_g30_hall_selected() && !g30_fo76_sensorless_active() && !VescToSTM_g30_hall_feedback_valid())\n    {'
assert s.count(old)>=2
s=s.replace(old,new,2)

old='''    if(g30_fo76_coast_requested())
    {
      (void)MCI_StopMotor( pMCI[M1] );
      break;
    }'''
new='''    if(g30_fo76_coast_requested())
    {
      if(VescToSTM_g30_hall_selected() && g30_fo76_sensorless_active()){
        /* A failed hybrid observer must never leave stale observer ownership
         * across the STOP/START cycle. Gates off first, then return to Hall. */
        VescToSTM_pwm_stop();
        g30_fo76_sensorless_clear();
      }
      (void)MCI_StopMotor( pMCI[M1] );
      break;
    }'''
assert old in s
s=s.replace(old,new,1)

old='''  hElSpeedDpp = (VescToSTM_g30_sensorless_selected() && g30_fo76_sensorless_active())?g30_fo76_control_speed_dpp():SPD_GetElSpeedDpp(speedHandle);'''
new='''  hElSpeedDpp = ((VescToSTM_g30_sensorless_selected() || VescToSTM_g30_hall_selected()) &&
                  g30_fo76_sensorless_active()) ?
                  g30_fo76_control_speed_dpp() : SPD_GetElSpeedDpp(speedHandle);'''
assert old in s
s=s.replace(old,new,1)

old='''#ifdef G30P
  /* R3G: Hall is still the default. This fast selector can return the
   * predicted observer angle only after an explicit, validated takeover. */
  hElAngle = (int16_t)g30_fo76_control_angle(hElAngle, hElSpeedDpp);
#endif
  PWMC_GetPhaseCurrents(pwmcHandle[M1], &Iab);'''
new='''#ifdef G30P
  /* FINAL HYBRID: Hall mode starts with the proven DRV126 Hall path. Once
   * physical FWD reaches the validated 64-DPP (~3 km/h) region, request the
   * already-running FO76 observer. control_angle() performs the guarded blend.
   * Reverse intentionally stays Hall-only. */
  uint8_t hybrid_mode=(uint8_t)VescToSTM_g30_hall_selected();
  uint8_t hall_raw_fast=HALL_read(&HALL_M1);
  uint8_t hall_valid_fast=(uint8_t)(HALL_M1.SensorIsReliable &&
      hall_raw_fast!=0u && hall_raw_fast!=7u && HALL_M1.lut[hall_raw_fast]!=255u);
  if(hybrid_mode && !g30_fo76_sensorless_active()){
      if(!PWM_Handle_M1._Super.PWM_off && FOCVars[M1].Iqdref.q!=0 &&
         hElSpeedDpp<=-(int16_t)G30_HYBRID_TAKEOVER_DPP){
          g30_fo76_request_takeover(1u);
      }else if(hElSpeedDpp>-(int16_t)G30_HYBRID_RETURN_DPP || PWM_Handle_M1._Super.PWM_off ||
               FOCVars[M1].Iqdref.q==0){
          g30_fo76_request_takeover(0u);
      }
  }
  hElAngle = (int16_t)g30_fo76_control_angle(hElAngle,hElSpeedDpp,
                                              hybrid_mode,hall_valid_fast);
#endif
  PWMC_GetPhaseCurrents(pwmcHandle[M1], &Iab);'''
assert old in s
s=s.replace(old,new,1)

old='''  uint8_t raw=HALL_read(&HALL_M1);
  if(pHdl->PWM_off || raw==0u || raw==7u || HALL_M1.lut[raw]==255u ||
     !HALL_M1.SensorIsReliable){
    PWMC_SwitchOffPWM(pHdl);
    return MC_NO_ERROR;
  }'''
new='''  uint8_t raw=HALL_read(&HALL_M1);
  if(pHdl->PWM_off ||
     (!g30_fo76_sensorless_active() &&
      (raw==0u || raw==7u || HALL_M1.lut[raw]==255u || !HALL_M1.SensorIsReliable))){
    PWMC_SwitchOffPWM(pHdl);
    return MC_NO_ERROR;
  }'''
assert old in s
s=s.replace(old,new,1)

old='''  if(VescToSTM_g30_hall_selected()){
    hCodeError=g30_drv126_final_hall_step(pwmcHandle[M1],Iab,hElAngle,
                                          FOCVars[M1].Iqdref.q,
                                          FOCVars[M1].Iqdref.d);

    /* Keep the SESC supervisory layer truthful. R0.2/R0.3 established that
     * these q/d voltage units are compatible with the DRV126 controller. */'''
new='''  if(VescToSTM_g30_hall_selected()){
    uint16_t g30_old_ca=pwmcHandle[M1]->CntPhA;
    uint16_t g30_old_cb=pwmcHandle[M1]->CntPhB;
    uint16_t g30_old_cc=pwmcHandle[M1]->CntPhC;
    hCodeError=g30_drv126_final_hall_step(pwmcHandle[M1],Iab,hElAngle,
                                          FOCVars[M1].Iqdref.q,
                                          FOCVars[M1].Iqdref.d);

    /* Keep the SESC supervisory layer truthful. R0.2/R0.3 established that
     * these q/d voltage units are compatible with the DRV126 controller. */'''
assert old in s
s=s.replace(old,new,1)

old='''    FOCVars[M1].Valphabeta=Valphabeta;
    FOCVars[M1].hElAngle=hElAngle;
    FW_DataProcess(pFW[M1],Vqd,Iqd);
    return hCodeError;'''
new='''    FOCVars[M1].Valphabeta=Valphabeta;
    FOCVars[M1].hElAngle=hElAngle;
    FW_DataProcess(pFW[M1],Vqd,Iqd);

    /* FO76 observes the actual previous PWM vector, exactly like the validated
     * shadow path. This makes the observer independent of the DRV126 q/d
     * voltage representation and keeps the physical R/L/lambda model intact. */
    g30_fo76_shadow_step(Iab.a,Iab.b,HALL_M1._Super.hElAngle,
                         pBusSensorM1->_Super.AvBusVoltage_d,
                         g30_old_ca,g30_old_cb,g30_old_cc,
                         PWM_Handle_M1.Half_PWMPeriod,
                         (uint16_t)DEAD_TIME_COUNTS,
                         HALL_M1._Super.hElSpeedDpp,
                         (uint8_t)!PWM_Handle_M1._Super.PWM_off);
    return hCodeError;'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s)

p=root/'common_files/src/VescToSTM.c'
s=p.read_text()
old='''#ifdef G30P
\t/* Only after MOE/gate outputs are off is it safe to disarm takeover. */
\tg30_fo76_request_takeover(0u);
    g30_drv126_final_reset();
#endif'''
new='''#ifdef G30P
\t/* Only after MOE/gate outputs are off is it safe to disarm takeover. */
    if(VescToSTM_g30_hall_selected() && g30_fo76_sensorless_active())
        g30_fo76_sensorless_clear();
    else
\t    g30_fo76_request_takeover(0u);
    g30_drv126_final_reset();
#endif'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s)

p=root/'common_files/src/stm32f10x_mc_it.c'
s=p.read_text()
old='''    if(VescToSTM_g30_hall_selected() && !HALL_M1.SensorIsReliable){'''
new='''    if(VescToSTM_g30_hall_selected() && !g30_fo76_sensorless_active() &&
       !HALL_M1.SensorIsReliable){'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s)

p=root/'common_files/src/task_LED.c'
s=p.read_text()
if '#include "g30_fo76_shadow.h"' not in s:
    s=s.replace('#include "VescToSTM.h"\n', '#include "VescToSTM.h"\n#ifdef G30P\n#include "g30_fo76_shadow.h"\n#endif\n',1)
old='''                bool hall_speed_fault=VescToSTM_g30_hall_selected() &&
                    ((pMCI[M1]->pSTM->hFaultOccurred & MC_SPEED_FDBK)!=0u);'''
new='''                bool hall_speed_fault=VescToSTM_g30_hall_selected() &&
                    !g30_fo76_sensorless_active() &&
                    ((pMCI[M1]->pSTM->hFaultOccurred & MC_SPEED_FDBK)!=0u);'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s)

p=root/'common_files/src/terminal.c'
s=p.read_text()
s=s.replace('''            HW_NAME,VescToSTM_g30_hall_selected()?"HALL":"SENSORLESS",
            (unsigned)g30_r3i_sensorless_active());''',
'''            HW_NAME,VescToSTM_g30_hall_selected()?
                (g30_fo76_sensorless_active()?"HYBRID-SENSORLESS":"HYBRID-HALL"):
                "SENSORLESS",
            (unsigned)(g30_r3i_sensorless_active() || g30_fo76_sensorless_active()));''',1)
s=s.replace('''            VescToSTM_g30_hall_selected()?"HALL":"SENSORLESS",
            (unsigned)g30_r3i_sensorless_active());''',
'''            VescToSTM_g30_hall_selected()?
                (g30_fo76_sensorless_active()?"HYBRID-SENSORLESS":"HYBRID-HALL"):
                "SENSORLESS",
            (unsigned)(g30_r3i_sensorless_active() || g30_fo76_sensorless_active()));''',1)
s=s.replace('''            HW_NAME,VescToSTM_g30_hall_selected()?"HALL":"SENSORLESS",
            (unsigned)PWM_Handle_M1._Super.PWM_off,(unsigned)STM_GetState(&STM[M1]),''',
'''            HW_NAME,VescToSTM_g30_hall_selected()?
                (g30_fo76_sensorless_active()?"HYBRID-SENSORLESS":"HYBRID-HALL"):
                "SENSORLESS",
            (unsigned)PWM_Handle_M1._Super.PWM_off,(unsigned)STM_GetState(&STM[M1]),''',1)
p.write_text(s)

print('SESC DRV126 HYBRID FINAL V1 applied')
