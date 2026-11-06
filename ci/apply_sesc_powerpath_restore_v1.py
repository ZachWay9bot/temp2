from pathlib import Path
root=Path('SOURCE_KOXX3')

# Build identity + test-only Hall selection without touching power-stage code.
p=root/'common_files/src/defines.h'
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-POWERCORE6500-FINAL-V1"'
new='#define HW_NAME "SESC-DRV126-POWERCORE6500-POWERPATH-RESTORE-V1"\n#define G30_POWERPATH_RESTORE_V1 1'
assert old in s
p.write_text(s.replace(old,new,1))

# Keep faults latched for diagnosis. Baseline had auto reset=1.
p=root/'common_files/inc/product.h'
s=p.read_text()
import re
s,n=re.subn(r'(#define AUTO_RESET_FAULT\s+)1',r'\g<1>0',s,count=1)
assert n==1
p.write_text(s)

# Force Hall selection only for this restoration test. No current/voltage/PWM/ADC logic is changed.
p=root/'common_files/src/VescToSTM.c'
s=p.read_text()
old='''bool VescToSTM_g30_sensorless_selected(void){
    return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_SENSORLESS;
}

bool VescToSTM_g30_hall_selected(void){
    return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_HALL;
}'''
new='''bool VescToSTM_g30_sensorless_selected(void){
#ifdef G30_POWERPATH_RESTORE_V1
    return false;
#else
    return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_SENSORLESS;
#endif
}

bool VescToSTM_g30_hall_selected(void){
#ifdef G30_POWERPATH_RESTORE_V1
    return true;
#else
    return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_HALL;
#endif
}'''
assert old in s
p.write_text(s.replace(old,new,1))

# Fault logging: one-shot only, no UART flood. Do NOT alter motor/PWM path.
p=root/'common_files/src/task_LED.c'
s=p.read_text()
old='''#if ERROR_PRINTING && VESC_TOOL_ENABLE
				commands_printf(((port_str*)argument)->phandle, "FAULTS: %x", last_fault);
#endif'''
new='''#if ERROR_PRINTING && VESC_TOOL_ENABLE
				commands_printf(((port_str*)argument)->phandle, "FAULTS: %x", last_fault);
#ifdef G30_POWERPATH_RESTORE_V1
                last_fault_time = 0xFFFFFFFFu; /* one-shot diagnostic, no UART flood */
#endif
#endif'''
assert old in s
p.write_text(s.replace(old,new,1))

# Safe explicit ACK. Return to baseline Hall coast-ready RUN, leave PWM/MOE off.
p=root/'common_files/src/terminal.c'
s=p.read_text()
marker='''	}else if (strcmp(argv[0], "top") == 0){'''
assert marker in s
block=r'''    }else if (strcmp(argv[0], "g30_faultguard") == 0){
        uint16_t fn=pMCI[M1]->pSTM->hFaultNow;
        uint16_t fo=pMCI[M1]->pSTM->hFaultOccurred;
        uint32_t budget=(CPU_CLOCK/PWM_FREQUENCY);
        uint32_t maxcy=pMCI[M1]->pFOCVars->cycles_max;
        commands_printf(phandle,
          "POWERPATH_RESTORE now=0x%04x occurred=0x%04x state=%u pwm_off=%u moe=%u auto_reset=0",
          (unsigned)fn,(unsigned)fo,(unsigned)STM_GetState(pMCI[M1]->pSTM),
          (unsigned)PWM_Handle_M1._Super.PWM_off,
          (unsigned)((TIM1->BDTR&TIM_BDTR_MOE)?1u:0u));
        commands_printf(phandle,
          "POWERPATH_RESTORE foc_cycles last=%lu max=%lu budget=%lu load_max_pct=%lu offsets=%lu,%lu,%lu",
          (unsigned long)pMCI[M1]->pFOCVars->cycles_last,
          (unsigned long)maxcy,(unsigned long)budget,
          (unsigned long)(budget?(maxcy*100u/budget):0u),
          (unsigned long)PWM_Handle_M1.PhaseAOffset,
          (unsigned long)PWM_Handle_M1.PhaseBOffset,
          (unsigned long)PWM_Handle_M1.PhaseCOffset);
        return;
    }else if (strcmp(argv[0], "g30_faultguard_ack") == 0){
        uint16_t fn=pMCI[M1]->pSTM->hFaultNow;
        State_t st=STM_GetState(pMCI[M1]->pSTM);
        uint8_t pwm_off=(uint8_t)PWM_Handle_M1._Super.PWM_off;
        uint8_t moe=(uint8_t)((TIM1->BDTR&TIM_BDTR_MOE)?1u:0u);
        if(fn!=0u || st!=FAULT_OVER || !pwm_off || moe){
            commands_printf(phandle,
              "POWERPATH_ACK DENIED now=0x%04x state=%u pwm_off=%u moe=%u",
              (unsigned)fn,(unsigned)st,(unsigned)pwm_off,(unsigned)moe);
            return;
        }
        VescToSTM_set_current(0.0f,0.0f);
        MCI_ExecSpeedRamp(pMCI[M1],0,0);
        VescToSTM_pwm_stop();
        if(!MCI_FaultAcknowledged(pMCI[M1])){
            commands_printf(phandle,"POWERPATH_ACK FAILED");
            return;
        }
        STM[M1].bState = RUN;
        pMCI[M1]->pFOCVars->cycles_max = 0u;
        VescToSTM_set_current(0.0f,0.0f);
        MCI_ExecSpeedRamp(pMCI[M1],0,0);
        VescToSTM_pwm_stop();
        commands_printf(phandle,"POWERPATH_ACK OK state=%u pwm_off=%u moe=%u ready=RUN",
          (unsigned)STM_GetState(pMCI[M1]->pSTM),
          (unsigned)PWM_Handle_M1._Super.PWM_off,
          (unsigned)((TIM1->BDTR&TIM_BDTR_MOE)?1u:0u));
        return;
'''
s=s.replace(marker,block+marker,1)
p.write_text(s)

print('POWERPATH_RESTORE_V1 applied: exact FINAL-V1 motor path + Hall test selection + latched faults + safe ACK')
