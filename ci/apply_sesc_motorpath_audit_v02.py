from pathlib import Path

root=Path("SOURCE_KOXX3")

# Build ID only. This branch is a diagnostic/safety child of Motorpath Audit V0.1.
p=root/"common_files/src/defines.h"
s=p.read_text()
assert '#define HW_NAME "SESC-MOTORPATH-AUDIT-V0.1"' in s
p.write_text(s.replace('#define HW_NAME "SESC-MOTORPATH-AUDIT-V0.1"',
                       '#define HW_NAME "SESC-MOTORPATH-AUDIT-V0.2"'))

# Fix the remaining software-OCP hole: reconstructed Ic must be tested in wide
# arithmetic before it is narrowed to int16_t for the legacy handle field.
p=root/"common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c"
s=p.read_text()
old='''  pHandle->_Super.Ia = pStator_Currents->a;
  pHandle->_Super.Ib = pStator_Currents->b;
  pHandle->_Super.Ic = -pStator_Currents->a - pStator_Currents->b;

  if(pHandle->_Super.OverCurrent && ((abs(pHandle->_Super.Ia) > pHandle->_Super.OverCurrent) || (abs(pHandle->_Super.Ib) > pHandle->_Super.OverCurrent) || (abs(pHandle->_Super.Ic) > pHandle->_Super.OverCurrent))){
\t  pHandle->_Super.OverCurrentCyclesCounter++;
\t  if(pHandle->_Super.OverCurrentCyclesCounter > pHandle->_Super.OverCurrentCycles){
\t\t  pHandle->OverCurrentFlag = true;
\t  \t  R3_2_SwitchOffPWM(pHdl);
\t  }
  }else{
\t  pHandle->_Super.OverCurrentCyclesCounter = 0;
  }'''
new='''  pHandle->_Super.Ia = pStator_Currents->a;
  pHandle->_Super.Ib = pStator_Currents->b;

  /* Motorpath V0.2: reconstruct phase C in wide arithmetic. Narrowing first
   * can wrap a real >87 A reconstructed phase current back below the 60 A
   * software OCP threshold. Keep the legacy Ic field saturated for consumers,
   * but perform the protection comparison on the full int32 value. */
  int32_t ia_oc = (int32_t)pStator_Currents->a;
  int32_t ib_oc = (int32_t)pStator_Currents->b;
  int32_t ic_oc = -ia_oc - ib_oc;
  if (ic_oc > INT16_MAX) {
      pHandle->_Super.Ic = INT16_MAX;
  } else if (ic_oc < -INT16_MAX) {
      pHandle->_Super.Ic = -INT16_MAX;
  } else {
      pHandle->_Super.Ic = (int16_t)ic_oc;
  }

  int32_t oc = (int32_t)pHandle->_Super.OverCurrent;
  if((oc > 0) &&
     ((ia_oc > oc) || (ia_oc < -oc) ||
      (ib_oc > oc) || (ib_oc < -oc) ||
      (ic_oc > oc) || (ic_oc < -oc))){
      pHandle->_Super.OverCurrentCyclesCounter++;
      if(pHandle->_Super.OverCurrentCyclesCounter > pHandle->_Super.OverCurrentCycles){
          pHandle->OverCurrentFlag = true;
          R3_2_SwitchOffPWM(pHdl);
      }
  }else{
      pHandle->_Super.OverCurrentCyclesCounter = 0;
  }'''
assert old in s
p.write_text(s.replace(old,new))

# Improve motorpath diagnostics. V0.1's "edge_ns" is only phase compare
# distance to a rail; it is NOT the ADC sampling margin. Log the actual CCR4
# trigger, PWM4 mode and sorted duty values so the adaptive MCSDK sampling path
# can be verified from hardware logs. Add a cycles_max reset command so each
# guided stage gets an independent FOC worst-case value.
p=root/"common_files/src/terminal.c"
s=p.read_text()
anchor='''    }else if (strcmp(argv[0], "g30_motorpath") == 0){'''
replacement='''    }else if (strcmp(argv[0], "g30_motorpath_reset") == 0){
        pMCI[M1]->pFOCVars->cycles_max=0u;
        commands_printf(phandle,"MP_RESET cycles_max=0");
    }else if (strcmp(argv[0], "g30_motorpath") == 0){'''
assert anchor in s
s=s.replace(anchor,replacement,1)

old='''        commands_printf(phandle,"MP pwm sect=%u cnt=%u,%u,%u half=%u edge=%u edge_ns=%lu mod=%lu/1000",
            (unsigned)PWM_Handle_M1._Super.Sector,(unsigned)ca,(unsigned)cb,(unsigned)cc,
            (unsigned)half,(unsigned)edge,(unsigned long)edge_ns,(unsigned long)mod_pm);'''
new='''        commands_printf(phandle,"MP pwm sect=%u cnt=%u,%u,%u half=%u rail=%u rail_ns=%lu mod=%lu/1000",
            (unsigned)PWM_Handle_M1._Super.Sector,(unsigned)ca,(unsigned)cb,(unsigned)cc,
            (unsigned)half,(unsigned)edge,(unsigned long)edge_ns,(unsigned long)mod_pm);
        commands_printf(phandle,"MP sample ccr4=%lu pwm4mode=%08lx lowmidhigh=%u,%u,%u",
            (unsigned long)TIM1->CCR4,(unsigned long)PWM_Handle_M1.PWM_Mode,
            (unsigned)PWM_Handle_M1._Super.lowDuty,
            (unsigned)PWM_Handle_M1._Super.midDuty,
            (unsigned)PWM_Handle_M1._Super.highDuty);'''
assert old in s
s=s.replace(old,new,1)

old='''        commands_printf(phandle,"MP Vqd=%d,%d PIq kp=%d/%u ki=%d/%u int=%ld PId int=%ld",
            (int)FOCVars[M1].Vqd.q,(int)FOCVars[M1].Vqd.d,
            (int)PIDIqHandle_M1.hKpGain,(unsigned)PIDIqHandle_M1.hKpDivisor,
            (int)PIDIqHandle_M1.hKiGain,(unsigned)PIDIqHandle_M1.hKiDivisor,
            (long)(PIDIqHandle_M1.wIntegralTerm/(int32_t)PIDIqHandle_M1.hKiDivisor),
            (long)(PIDIdHandle_M1.wIntegralTerm/(int32_t)PIDIdHandle_M1.hKiDivisor));'''
new='''        commands_printf(phandle,"MP Vqd=%d,%d PIq kp=%d/%u ki=%d/%u int=%ld PId int=%ld",
            (int)FOCVars[M1].Vqd.q,(int)FOCVars[M1].Vqd.d,
            (int)PIDIqHandle_M1.hKpGain,(unsigned)PIDIqHandle_M1.hKpDivisor,
            (int)PIDIqHandle_M1.hKiGain,(unsigned)PIDIqHandle_M1.hKiDivisor,
            (long)(PIDIqHandle_M1.wIntegralTerm/(int32_t)PIDIqHandle_M1.hKiDivisor),
            (long)(PIDIdHandle_M1.wIntegralTerm/(int32_t)PIDIdHandle_M1.hKiDivisor));
        commands_printf(phandle,"MP ctrl erpm=%ld qerr_mA=%ld qlim=%d/%d",
            (long)(VescToSTM_get_erpm_fast()*2),
            (long)(iqr_ma-iq_ma),
            (int)PIDIqHandle_M1.hLowerOutputLimit,(int)PIDIqHandle_M1.hUpperOutputLimit);'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s)

print("SESC Motorpath Audit V0.2 applied: wide-Ic OCP + real ADC-trigger diagnostics")
