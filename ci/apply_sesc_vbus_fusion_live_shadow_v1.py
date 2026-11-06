#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")

# Identity + unlock only for the deliberately hard-clamped live-shadow gate.
p=root/"common_files/src/defines.h"
s=p.read_text()
old='''#define HW_NAME "SESC-DRV126-POWERCORE6500-VBUS-FUSION-WIRED-LOCKED-V2"
#define G30_BMS_BATTERY_SAFE_POWERLOCK 1'''
new='''#define HW_NAME "SESC-DRV126-POWERCORE6500-FAULTGUARD-V1B"
#define G30_VBUS_LIVE_SHADOW_GATE 1
#define G30_FAULTGUARD_V1 1
#define G30_FAULTGUARD_V1B 1'''
assert old in s
p.write_text(s.replace(old,new,1))

# Force Hall control in this gate. Sensorless takeover is impossible by build.
p=root/"common_files/src/VescToSTM.c"
s=p.read_text()
old='''bool VescToSTM_g30_sensorless_selected(void){
    return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_SENSORLESS;
}

bool VescToSTM_g30_hall_selected(void){
    return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_HALL;
}'''
new='''bool VescToSTM_g30_sensorless_selected(void){
#ifdef G30_VBUS_LIVE_SHADOW_GATE
    return false;
#else
    return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_SENSORLESS;
#endif
}

bool VescToSTM_g30_hall_selected(void){
#ifdef G30_VBUS_LIVE_SHADOW_GATE
    return true;
#else
    return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_HALL;
#endif
}'''
assert old in s
s=s.replace(old,new,1)

# Hard speed clamp regardless of dashboard/VESC/terminal command source.
needle='''void VescToSTM_set_speed(int32_t erpm){
#ifdef G30P
'''
assert needle in s
s=s.replace(needle,'''void VescToSTM_set_speed(int32_t erpm){
#ifdef G30P
#ifdef G30_VBUS_LIVE_SHADOW_GATE
    if(erpm>3000) erpm=3000;
    if(erpm< -3000) erpm=-3000;
#endif
''',1)
p.write_text(s)

# Hard phase-current and voltage-vector clamps inside the actual DRV126 loop.
p=root/"common_files/src/mc_tasks.c"
s=p.read_text()
old='''  int32_t pos=(int32_t)SpeednTorqCtrlM1.MaxPositiveTorque;
  int32_t neg=(int32_t)SpeednTorqCtrlM1.MinNegativeTorque;
  if(pos<0)pos=0;
  if(neg>0)neg=0;
  int32_t qtarget=g30_drv126_final_clamp32((int32_t)qref_mc,neg,pos);
  int32_t phase_lim=pos;
  if(-neg>phase_lim)phase_lim=-neg;
  int32_t dmc=g30_drv126_final_clamp32((int32_t)dref_mc,-phase_lim,phase_lim);
'''
new='''  int32_t pos=(int32_t)SpeednTorqCtrlM1.MaxPositiveTorque;
  int32_t neg=(int32_t)SpeednTorqCtrlM1.MinNegativeTorque;
  if(pos<0)pos=0;
  if(neg>0)neg=0;
#ifdef G30_VBUS_LIVE_SHADOW_GATE
  /* Absolute gate clamp: 5 A phase, regardless of loaded mc_conf. */
  const int32_t gate_phase_lim=(int32_t)(5.0f*CURRENT_FACTOR_A+0.5f);
  if(pos>gate_phase_lim) pos=gate_phase_lim;
  if(neg< -gate_phase_lim) neg=-gate_phase_lim;
#endif
  int32_t qtarget=g30_drv126_final_clamp32((int32_t)qref_mc,neg,pos);
  int32_t phase_lim=pos;
  if(-neg>phase_lim)phase_lim=-neg;
  int32_t dmc=g30_drv126_final_clamp32((int32_t)dref_mc,-phase_lim,phase_lim);
#ifdef G30_VBUS_LIVE_SHADOW_GATE
  dmc=0; /* no field weakening / d-axis excitation in the gate */
#endif
'''
assert old in s
s=s.replace(old,new,1)

old2='''  g30_drv126_final_vd=g30_drv126_final_pi(dref,id,&g30_drv126_final_d_acc,
                                          8500019,10376);

  int16_t va,vb;'''
new2='''  g30_drv126_final_vd=g30_drv126_final_pi(dref,id,&g30_drv126_final_d_acc,
                                          8500019,10376);
#ifdef G30_VBUS_LIVE_SHADOW_GATE
  /* Roughly 25% of full q-axis voltage. The current clamp remains primary. */
  g30_drv126_final_vq=(int16_t)g30_drv126_final_clamp32(g30_drv126_final_vq,-8192,8192);
  g30_drv126_final_vd=0;
#endif

  int16_t va,vb;'''
assert old2 in s
s=s.replace(old2,new2,1)

# At >45 V, a lost/stale BMS fusion immediately coasts the gate.
needle='''    uint8_t hall_guard=(uint8_t)VescToSTM_g30_hall_selected();

    hCodeError=g30_drv126_final_power_step'''
assert needle in s
s=s.replace(needle,'''    uint8_t hall_guard=(uint8_t)VescToSTM_g30_hall_selected();
#ifdef G30_VBUS_LIVE_SHADOW_GATE
    if(!g30_vbus_fusion_runtime_sensorless_ok()){
      PWMC_SwitchOffPWM(pwmcHandle[M1]);
      return MC_NO_ERROR;
    }
#endif

    hCodeError=g30_drv126_final_power_step''',1)

# Observer runs as shadow even though Hall remains the only control source.
old3='''    if(VescToSTM_g30_sensorless_selected()){
      /* FO76 observes the voltage actually present during this current sample:
       * the previous DRV126 PWM vector. This preserves the frozen 16-kHz
       * observer model while the DRV126 current controller runs at 4 kHz. */
      g30_fo76_shadow_step(Iab.a,Iab.b,HALL_M1._Super.hElAngle,
                           g30_vbus_fusion_runtime_mv(),
                           g30_old_ca,g30_old_cb,g30_old_cc,
                           PWM_Handle_M1.Half_PWMPeriod,
                           (uint16_t)DEAD_TIME_COUNTS,
                           HALL_M1._Super.hElSpeedDpp,
                           (uint8_t)!PWM_Handle_M1._Super.PWM_off);
    }'''
new3='''#ifdef G30_VBUS_LIVE_SHADOW_GATE
    g30_fo76_request_takeover(0u);
    g30_fo76_shadow_step(Iab.a,Iab.b,HALL_M1._Super.hElAngle,
                         g30_vbus_fusion_runtime_mv(),
                         g30_old_ca,g30_old_cb,g30_old_cc,
                         PWM_Handle_M1.Half_PWMPeriod,
                         (uint16_t)DEAD_TIME_COUNTS,
                         HALL_M1._Super.hElSpeedDpp,
                         (uint8_t)!PWM_Handle_M1._Super.PWM_off);
#else
    if(VescToSTM_g30_sensorless_selected()){
      g30_fo76_shadow_step(Iab.a,Iab.b,HALL_M1._Super.hElAngle,
                           g30_vbus_fusion_runtime_mv(),
                           g30_old_ca,g30_old_cb,g30_old_cc,
                           PWM_Handle_M1.Half_PWMPeriod,
                           (uint16_t)DEAD_TIME_COUNTS,
                           HALL_M1._Super.hElSpeedDpp,
                           (uint8_t)!PWM_Handle_M1._Super.PWM_off);
    }
#endif'''
assert old3 in s
s=s.replace(old3,new3,1)
p.write_text(s)

# Terminal identity/status for the host gate.
p=root/"common_files/src/terminal.c"
s=p.read_text()
marker='''    }else if (strcmp(argv[0], "g30_vbus_fusion_wired") == 0){'''
assert marker in s
block=r'''    }else if (strcmp(argv[0], "g30_live_shadow_gate") == 0){
        g30_vbus_fusion_result_t r=g30_vbus_fusion_runtime_result();
        uint32_t fused=(r.source==G30_VBUS_SRC_PA1)?r.pa1_mv:
                       (r.source==G30_VBUS_SRC_BMS_EST)?r.est_mv:0u;
        commands_printf(phandle,"LIVE_SHADOW gate=1 hall_forced=1 takeover=0 phase_limit_mA=5000 speed_limit_erpm=3000");
        commands_printf(phandle,"LIVE_SHADOW fusion_src=%s fused=%lu sl_ok=%u pwm_off=%u moe=%u",
          g30_vbus_fusion_source_name(r.source),(unsigned long)fused,
          (unsigned)r.sensorless_ok,(unsigned)PWM_Handle_M1._Super.PWM_off,
          (unsigned)((TIM1->BDTR&TIM_BDTR_MOE)?1u:0u));
        return;
'''
s=s.replace(marker,block+marker,1)
p.write_text(s)

print("VBUS FUSION LIVE SHADOW V1 applied: Hall-only control, FO76 shadow, 5A/3000erpm/25pct-voltage hard gate")

# Hotfix: long FW_VERSION name exceeded PACKET_SIZE(60) (reply needs ~75B).
# Enlarged local stack buffer; this does not change motor control.
p=root/"common_files/src/VescCommand.c"
s=p.read_text()
old='uint8_t send_buffer[PACKET_SIZE(60)];'
assert s.count(old)==1, s.count(old)
s=s.replace(old,'uint8_t send_buffer[PACKET_SIZE(96)];',1)
p.write_text(s)
print("FW_VERSION response stack buffer fixed: 96B payload capacity")


# FAULTGUARD V1: latch every MCSDK fault. Never auto-ack/restart the bridge.
p=root/"common_files/inc/product.h"
x=p.read_text()
old='#define AUTO_RESET_FAULT													 1'
assert old in x, "AUTO_RESET_FAULT define not found"
x=x.replace(old,'#define AUTO_RESET_FAULT													 0',1)
p.write_text(x)

# With auto-reset disabled, task_LED's legacy logger would print the same fault forever.
# Print once per newly latched fault instead.
p=root/"common_files/src/task_LED.c"
x=p.read_text()
old='''#if ERROR_PRINTING && VESC_TOOL_ENABLE
				commands_printf(((port_str*)argument)->phandle, "FAULTS: %x", last_fault);
#endif

#if AUTO_RESET_FAULT'''
new='''#if ERROR_PRINTING && VESC_TOOL_ENABLE
				commands_printf(((port_str*)argument)->phandle, "FAULTS: %x", last_fault);
#ifdef G30_FAULTGUARD_V1
				last_fault_time = 0xFFFFFFFFu; /* one-shot diagnostic, no UART flood */
#endif
#endif

#if AUTO_RESET_FAULT'''
assert old in x
x=x.replace(old,new,1)
p.write_text(x)

# Parent POWERCORE source already maps any unknown nonzero MCSDK fault (including MC_FOC_DURATION)
# to FAULT_CODE_DRV while preserving raw hFaultNow/hFaultOccurred for g30_status.

# Minimal raw MCSDK fault snapshot. Host queries this only while motor is coasted.
p=root/"common_files/src/terminal.c"
x=p.read_text()
marker='''    }else if (strcmp(argv[0], "g30_live_shadow_gate") == 0){'''
assert marker in x
block=r'''    }else if (strcmp(argv[0], "g30_faultguard") == 0){
        uint16_t fn=pMCI[M1]->pSTM->hFaultNow;
        uint16_t fo=pMCI[M1]->pSTM->hFaultOccurred;
        commands_printf(phandle,
          "FAULTGUARD v1 now=0x%04x occurred=0x%04x state=%u pwm_off=%u moe=%u auto_reset=0",
          (unsigned)fn,(unsigned)fo,(unsigned)STM_GetState(pMCI[M1]->pSTM),
          (unsigned)PWM_Handle_M1._Super.PWM_off,
          (unsigned)((TIM1->BDTR&TIM_BDTR_MOE)?1u:0u));
        commands_printf(phandle,
          "FAULTGUARD foc_cycles last=%lu max=%lu budget=%lu load_max_pct=%lu",
          (unsigned long)pMCI[M1]->pFOCVars->cycles_last,
          (unsigned long)pMCI[M1]->pFOCVars->cycles_max,
          (unsigned long)(CPU_CLOCK/PWM_FREQUENCY),
          (unsigned long)(pMCI[M1]->pFOCVars->cycles_max*PWM_FREQUENCY*100u/CPU_CLOCK));
        return;
    }else if (strcmp(argv[0], "g30_faultguard_ack") == 0){
        uint16_t fn=pMCI[M1]->pSTM->hFaultNow;
        State_t st=STM_GetState(pMCI[M1]->pSTM);
        uint8_t pwm_off=(uint8_t)PWM_Handle_M1._Super.PWM_off;
        uint8_t moe=(uint8_t)((TIM1->BDTR&TIM_BDTR_MOE)?1u:0u);
        if(fn!=0u || st!=FAULT_OVER || !pwm_off || moe){
            commands_printf(phandle,
              "FAULTGUARD_ACK DENIED now=0x%04x state=%u pwm_off=%u moe=%u",
              (unsigned)fn,(unsigned)st,(unsigned)pwm_off,(unsigned)moe);
            return;
        }
        VescToSTM_set_current(0.0f,0.0f);
        MCI_ExecSpeedRamp(pMCI[M1],0,0);
        VescToSTM_pwm_stop();
        if(!MCI_FaultAcknowledged(pMCI[M1])){
            commands_printf(phandle,"FAULTGUARD_ACK FAILED");
            return;
        }
        /*
         * POWERCORE/G30 coast-ready state is RUN with the bridge disabled.
         * The legacy auto-recovery path already used direct RUN assignment,
         * but then immediately re-enabled PWM. FAULTGUARD V1B deliberately
         * omits that re-enable so the next torque request can use the proven
         * G30 start path without re-entering MCSDK current-offset calibration.
         */
        STM[M1].bState = RUN;
        pMCI[M1]->pFOCVars->cycles_max = 0u;
        VescToSTM_set_current(0.0f,0.0f);
        MCI_ExecSpeedRamp(pMCI[M1],0,0);
        VescToSTM_pwm_stop();
        commands_printf(phandle,"FAULTGUARD_ACK OK state=%u pwm_off=%u moe=%u ready=RUN",
          (unsigned)STM_GetState(pMCI[M1]->pSTM),
          (unsigned)PWM_Handle_M1._Super.PWM_off,
          (unsigned)((TIM1->BDTR&TIM_BDTR_MOE)?1u:0u));
        return;
'''
x=x.replace(marker,block+marker,1)
p.write_text(x)

print("FAULTGUARD V1B applied: latched faults, safe ACK to RUN+PWM_OFF, no re-calibration, no auto restart")
