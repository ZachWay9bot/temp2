from pathlib import Path

root=Path("SOURCE_KOXX3")

p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-HALL-DEVV0.1"'
new='#define HW_NAME "SESC-MOTORPATH-AUDIT-V0.1"'
assert old in s
p.write_text(s.replace(old,new))

p=root/"common_files/src/terminal.c"
s=p.read_text()
old='#include "g30_dash_link.h"'
new='#include "g30_dash_link.h"\n#include "parameters_conversion.h"\n#include "mc_parameters.h"'
assert old in s
s=s.replace(old,new)

anchor='''    }else if (strcmp(argv[0], "g30_observer") == 0){'''
block=r'''    }else if (strcmp(argv[0], "g30_motorpath") == 0){
        uint16_t half=PWM_Handle_M1.Half_PWMPeriod;
        uint16_t ca=PWM_Handle_M1._Super.CntPhA;
        uint16_t cb=PWM_Handle_M1._Super.CntPhB;
        uint16_t cc=PWM_Handle_M1._Super.CntPhC;
        uint16_t edge=ca;
        if(cb<edge) edge=cb;
        if(cc<edge) edge=cc;
        if(ca<=half && (uint16_t)(half-ca)<edge) edge=(uint16_t)(half-ca);
        if(cb<=half && (uint16_t)(half-cb)<edge) edge=(uint16_t)(half-cb);
        if(cc<=half && (uint16_t)(half-cc)<edge) edge=(uint16_t)(half-cc);
        uint32_t edge_ns=((uint32_t)edge*1000u)/(uint32_t)MOT_TMR_MHZ;

        int32_t ia_ma=(int32_t)((float)FOCVars[M1].Iab.a*1000.0f/CURRENT_FACTOR_A);
        int32_t ib_ma=(int32_t)((float)FOCVars[M1].Iab.b*1000.0f/CURRENT_FACTOR_A);
        int32_t ic_counts=-(int32_t)FOCVars[M1].Iab.a-(int32_t)FOCVars[M1].Iab.b;
        int32_t ic_ma=(int32_t)((float)ic_counts*1000.0f/CURRENT_FACTOR_A);
        int32_t iq_ma=(int32_t)((float)FOCVars[M1].Iqd.q*1000.0f/CURRENT_FACTOR_A);
        int32_t id_ma=(int32_t)((float)FOCVars[M1].Iqd.d*1000.0f/CURRENT_FACTOR_A);
        int32_t iqr_ma=(int32_t)((float)FOCVars[M1].Iqdref.q*1000.0f/CURRENT_FACTOR_A);
        int32_t idr_ma=(int32_t)((float)FOCVars[M1].Iqdref.d*1000.0f/CURRENT_FACTOR_A);

        uint32_t vsq=(uint32_t)((int32_t)FOCVars[M1].Vqd.q*FOCVars[M1].Vqd.q)+
                      (uint32_t)((int32_t)FOCVars[M1].Vqd.d*FOCVars[M1].Vqd.d);
        uint32_t vmag=MCM_Sqrt(vsq);
        uint32_t mod_pm=(vmag*1000u)/32767u;

        uint32_t hz=HALL_M1._Super.hMeasurementFrequency;
        uint32_t budget=hz?CPU_CLOCK/hz:0u;
        uint32_t maxcy=pMCI[M1]->pFOCVars->cycles_max;
        uint32_t load=budget?(maxcy*100u)/budget:0u;

        int32_t oc_ma=(int32_t)((float)PWM_Handle_M1._Super.OverCurrent*1000.0f/CURRENT_FACTOR_A);
        int32_t batt_max_ma=(int32_t)((float)FOCVars[M1].max_i_batt*1000.0f/CURRENT_FACTOR_A);
        int32_t batt_min_ma=(int32_t)((float)FOCVars[M1].min_i_batt*1000.0f/CURRENT_FACTOR_A);

        commands_printf(phandle,"MP build=%s sensor=%s pwmOff=%u state=%u fault=0x%04x",
            HW_NAME,VescToSTM_g30_hall_selected()?"HALL":"SENSORLESS",
            (unsigned)PWM_Handle_M1._Super.PWM_off,(unsigned)STM_GetState(&STM[M1]),
            (unsigned)(STM[M1].hFaultNow|STM[M1].hFaultOccurred));
        commands_printf(phandle,"MP timer f=%luHz PSC=%lu ARR=%lu RCR=%lu CR1=%04lx BDTR=%04lx DTG=%lu phys_dt=%uns",
            (unsigned long)hz,(unsigned long)TIM1->PSC,(unsigned long)TIM1->ARR,
            (unsigned long)TIM1->RCR,(unsigned long)TIM1->CR1,(unsigned long)TIM1->BDTR,
            (unsigned long)(TIM1->BDTR&0xffu),(unsigned)SW_DEADTIME_NS);
        commands_printf(phandle,"MP dtcomp enabled=%u cnt=%u vesc_dt_us_x1000=%ld tafter=%u tbefore=%u",
            (unsigned)PWM_Handle_M1._Super.DTTest,(unsigned)PWM_Handle_M1._Super.DTCompCnt,
            (long)(mc_conf.foc_dt_us*1000.0f),(unsigned)R3_2_ParamsM1.Tafter,(unsigned)R3_2_ParamsM1.Tbefore);
        commands_printf(phandle,"MP pwm sect=%u cnt=%u,%u,%u half=%u edge=%u edge_ns=%lu mod=%lu/1000",
            (unsigned)PWM_Handle_M1._Super.Sector,(unsigned)ca,(unsigned)cb,(unsigned)cc,
            (unsigned)half,(unsigned)edge,(unsigned long)edge_ns,(unsigned long)mod_pm);
        commands_printf(phandle,"MP Iabc_mA=%ld,%ld,%ld Iqd_mA=%ld,%ld ref_mA=%ld,%ld",
            (long)ia_ma,(long)ib_ma,(long)ic_ma,(long)iq_ma,(long)id_ma,(long)iqr_ma,(long)idr_ma);
        commands_printf(phandle,"MP Vqd=%d,%d PIq kp=%d/%u ki=%d/%u int=%ld PId int=%ld",
            (int)FOCVars[M1].Vqd.q,(int)FOCVars[M1].Vqd.d,
            (int)PIDIqHandle_M1.hKpGain,(unsigned)PIDIqHandle_M1.hKpDivisor,
            (int)PIDIqHandle_M1.hKiGain,(unsigned)PIDIqHandle_M1.hKiDivisor,
            (long)(PIDIqHandle_M1.wIntegralTerm/(int32_t)PIDIqHandle_M1.hKiDivisor),
            (long)(PIDIdHandle_M1.wIntegralTerm/(int32_t)PIDIdHandle_M1.hKiDivisor));
        commands_printf(phandle,"MP cfg phase=%ld/%ldmA batt=%ld/%ldmA abs=%ldmA duty=%ld/1000 fw=%ldmA",
            (long)(mc_conf.l_current_max*1000.0f),(long)(mc_conf.l_current_min*1000.0f),
            (long)batt_max_ma,(long)batt_min_ma,(long)(mc_conf.l_abs_current_max*1000.0f),
            (long)(mc_conf.l_max_duty*1000.0f),(long)(mc_conf.foc_fw_current_max*1000.0f));
        commands_printf(phandle,"MP oc threshold=%dct=%ldmA delay=%lu cycNow=%lu current_factor_x1000=%lu",
            (int)PWM_Handle_M1._Super.OverCurrent,(long)oc_ma,
            (unsigned long)PWM_Handle_M1._Super.OverCurrentCycles,
            (unsigned long)PWM_Handle_M1._Super.OverCurrentCyclesCounter,
            (unsigned long)(CURRENT_FACTOR_A*1000.0f));
        commands_printf(phandle,"MP cpu last=%lu max=%lu budget=%lu load=%lu%% heap=%u",
            (unsigned long)pMCI[M1]->pFOCVars->cycles_last,(unsigned long)maxcy,
            (unsigned long)budget,(unsigned long)load,(unsigned)xPortGetFreeHeapSize());
        commands_printf(phandle,"MP vbus=%ldmV offsets=%lu,%lu,%lu",
            (long)(VescToSTM_get_bus_voltage()*1000.0f),
            (unsigned long)PWM_Handle_M1.PhaseAOffset,(unsigned long)PWM_Handle_M1.PhaseBOffset,
            (unsigned long)PWM_Handle_M1.PhaseCOffset);
'''
assert anchor in s
s=s.replace(anchor,block+anchor)
p.write_text(s)

print("SESC motorpath audit V0.1 diagnostics applied; control path unchanged")


# Motorpath safety audit: exact built Hall source had Ia checked twice, Ib omitted.
p=root/"common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c"
x=p.read_text()
old='''((abs(pHandle->_Super.Ia) > pHandle->_Super.OverCurrent) || (abs(pHandle->_Super.Ia) > pHandle->_Super.OverCurrent) || (abs(pHandle->_Super.Ic) > pHandle->_Super.OverCurrent))'''
new='''((abs(pHandle->_Super.Ia) > pHandle->_Super.OverCurrent) || (abs(pHandle->_Super.Ib) > pHandle->_Super.OverCurrent) || (abs(pHandle->_Super.Ic) > pHandle->_Super.OverCurrent))'''
assert old in x
p.write_text(x.replace(old,new))

# Dormant today (G30 temp is virtual), but correct the derating endpoint before
# any future real temperature channel is enabled.
p=root/"common_files/src/VescToSTM.c"
x=p.read_text()
old='''iq = utils_map_int(temp, fp.temp_cut_start, fp.battery_cut_end, 0, iq);'''
new='''iq = utils_map_int(temp, fp.temp_cut_start, fp.temp_cut_end, 0, iq);'''
assert old in x
p.write_text(x.replace(old,new))

print("Motorpath safety audit: Ia/Ib/Ic overcurrent + temp endpoint fixed")
