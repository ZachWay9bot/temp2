from pathlib import Path

root=Path("SOURCE_KOXX3")

# Build ID
p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-MOTORPATH-AUDIT-V0.2"'
new='#define HW_NAME "SESC-MOTORPATH-AUDIT-V0.3"'
assert old in s
p.write_text(s.replace(old,new))

# 1) Software OCP threshold is stored as int16_t. G30 CURRENT_FACTOR makes
#    values above ~87.45 A overflow that field. Saturate instead of narrowing.
p=root/"common_files/src/conf_general.c"
s=p.read_text()
old='''	PWM_Handle_M1._Super.OverCurrent = mcconf->l_abs_current_max * CURRENT_FACTOR_A;'''
new='''	/* Motorpath V0.3: OverCurrent is int16_t. Never let an otherwise legal
	 * VESC absolute-current setting (>~87.45 A on G30) wrap negative and
	 * silently disable software OCP. Saturation keeps protection active. */
	float oc_counts_f = mcconf->l_abs_current_max * CURRENT_FACTOR_A;
	utils_truncate_number(&oc_counts_f, 0.0f, (float)INT16_MAX);
	PWM_Handle_M1._Super.OverCurrent = (int16_t)oc_counts_f;'''
assert old in s
p.write_text(s.replace(old,new))

# 2) Torque-mode speed PI: integral limits are Ki-divisor scaled; output limits
#    are int16 torque units and must NOT be multiplied by SP_KIDIV.
#    G30 policy is explicitly no active braking/regen, independent of an old
#    or imported mc_conf flag.
p=root/"common_files/src/VescToSTM.c"
s=p.read_text()
old='''void VescToSTM_update_torque(int32_t q, int32_t min_erpm, int32_t max_erpm){
#ifdef G30P
    if(!VescToSTM_g30_hall_direction_allowed(q)){
        VescToSTM_set_brake(0);
        return;
    }
#endif
	q *= DIR_MUL;
	if(q >= 0){
		SpeednTorqCtrlM1.PISpeed->wUpperIntegralLimit = q * SP_KIDIV;
		SpeednTorqCtrlM1.PISpeed->wLowerIntegralLimit = mc_conf.s_pid_allow_braking ? -q * SP_KIDIV : 0;
		SpeednTorqCtrlM1.PISpeed->hUpperOutputLimit = q;
		SpeednTorqCtrlM1.PISpeed->hLowerOutputLimit = mc_conf.s_pid_allow_braking ? -q * SP_KIDIV : 0;
		if(MCI_RampCompleted(pMCI[M1])){
			MCI_ExecSpeedRamp(pMCI[M1], VescToSTM_erpm_to_speed(max_erpm), 0);
		}

	}else{
		SpeednTorqCtrlM1.PISpeed->wUpperIntegralLimit = mc_conf.s_pid_allow_braking ? -q * SP_KIDIV : 0;
		SpeednTorqCtrlM1.PISpeed->wLowerIntegralLimit = q * SP_KIDIV;
		SpeednTorqCtrlM1.PISpeed->hUpperOutputLimit = mc_conf.s_pid_allow_braking ? -q * SP_KIDIV : 0;
		SpeednTorqCtrlM1.PISpeed->hLowerOutputLimit = q;
		if(MCI_RampCompleted(pMCI[M1])){
			MCI_ExecSpeedRamp(pMCI[M1], VescToSTM_erpm_to_speed(min_erpm) , 0);
		}
	}
}'''
new='''void VescToSTM_update_torque(int32_t q, int32_t min_erpm, int32_t max_erpm){
#ifdef G30P
    if(!VescToSTM_g30_hall_direction_allowed(q)){
        VescToSTM_set_brake(0);
        return;
    }
    /* Motorpath V0.3: G30 brake policy is Coast. Do not allow an imported
     * mc_conf.s_pid_allow_braking bit to re-enable active counter-torque. */
    const bool allow_braking = false;
#else
    const bool allow_braking = mc_conf.s_pid_allow_braking;
#endif
	q *= DIR_MUL;
	if(q >= 0){
		SpeednTorqCtrlM1.PISpeed->wUpperIntegralLimit = q * SP_KIDIV;
		SpeednTorqCtrlM1.PISpeed->wLowerIntegralLimit = allow_braking ? -q * SP_KIDIV : 0;
		SpeednTorqCtrlM1.PISpeed->hUpperOutputLimit = q;
		SpeednTorqCtrlM1.PISpeed->hLowerOutputLimit = allow_braking ? -q : 0;
		if(MCI_RampCompleted(pMCI[M1])){
			MCI_ExecSpeedRamp(pMCI[M1], VescToSTM_erpm_to_speed(max_erpm), 0);
		}

	}else{
		SpeednTorqCtrlM1.PISpeed->wUpperIntegralLimit = allow_braking ? -q * SP_KIDIV : 0;
		SpeednTorqCtrlM1.PISpeed->wLowerIntegralLimit = q * SP_KIDIV;
		SpeednTorqCtrlM1.PISpeed->hUpperOutputLimit = allow_braking ? -q : 0;
		SpeednTorqCtrlM1.PISpeed->hLowerOutputLimit = q;
		if(MCI_RampCompleted(pMCI[M1])){
			MCI_ExecSpeedRamp(pMCI[M1], VescToSTM_erpm_to_speed(min_erpm) , 0);
		}
	}
}'''
assert old in s
p.write_text(s.replace(old,new))

# 3) Expose configured vs effective OCP so the test can prove saturation.
p=root/"common_files/src/terminal.c"
s=p.read_text()
old='''        commands_printf(phandle,"MP oc threshold=%dct=%ldmA delay=%lu cycNow=%lu current_factor_x1000=%lu",
            (int)PWM_Handle_M1._Super.OverCurrent,(long)oc_ma,
            (unsigned long)PWM_Handle_M1._Super.OverCurrentCycles,
            (unsigned long)PWM_Handle_M1._Super.OverCurrentCyclesCounter,
            (unsigned long)(CURRENT_FACTOR_A*1000.0f));'''
new='''        commands_printf(phandle,"MP oc cfg=%ldmA threshold=%dct=%ldmA delay=%lu cycNow=%lu current_factor_x1000=%lu",
            (long)(mc_conf.l_abs_current_max*1000.0f),
            (int)PWM_Handle_M1._Super.OverCurrent,(long)oc_ma,
            (unsigned long)PWM_Handle_M1._Super.OverCurrentCycles,
            (unsigned long)PWM_Handle_M1._Super.OverCurrentCyclesCounter,
            (unsigned long)(CURRENT_FACTOR_A*1000.0f));'''
assert old in s
p.write_text(s.replace(old,new))

print("SESC Motorpath Audit V0.3 applied: OCP threshold saturation + torque-limit scaling/no-regen hardening")
