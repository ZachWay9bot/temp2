from pathlib import Path

root=Path("SOURCE_KOXX3")

# Build ID: child of Motorpath Audit V0.2. No Hall/observer/PI changes.
p=root/"common_files/src/defines.h"
s=p.read_text()
assert '#define HW_NAME "SESC-MOTORPATH-AUDIT-V0.2"' in s
p.write_text(s.replace('#define HW_NAME "SESC-MOTORPATH-AUDIT-V0.2"',
                       '#define HW_NAME "SESC-MOTORPATH-SAFETY-V0.1"'))

# 1) G30 software OCP: use immediate trip regardless of stored VESC slow-OC flag.
p=root/"common_files/src/conf_general.c"
s=p.read_text()
old='''	if(mcconf->l_slow_abs_current){
		PWM_Handle_M1._Super.OverCurrentCycles = utils_map(mcconf->foc_current_filter_const,1,0,0,ABS_OVR_CURRENT_TRIP_MS) / (1000.0 / mcconf->foc_f_sw);
	}else{
		PWM_Handle_M1._Super.OverCurrentCycles = 0;  //instant trip
	}'''
new='''#ifdef G30P
	/* Safety V0.1: the G30 has no verified active TIM1-BKIN hardware trip.
	 * Do not add the legacy 2 ms software delay on top of the ADC current check. */
	PWM_Handle_M1._Super.OverCurrentCycles = 0;
#else
	if(mcconf->l_slow_abs_current){
		PWM_Handle_M1._Super.OverCurrentCycles = utils_map(mcconf->foc_current_filter_const,1,0,0,ABS_OVR_CURRENT_TRIP_MS) / (1000.0 / mcconf->foc_f_sw);
	}else{
		PWM_Handle_M1._Super.OverCurrentCycles = 0;
	}
#endif'''
assert old in s
p.write_text(s.replace(old,new,1))

# 2) G30 temporary modulation guard. It clamps existing/stored 0.99 configs at setup.
p=root/"common_files/inc/product.h"
s=p.read_text()
old='#define HW_LIM_DUTY_MAX\t\t\t0.0, 0.99'
assert old in s
p.write_text(s.replace(old,'#define HW_LIM_DUTY_MAX\t\t\t0.0, 0.95',1))

# 3) Fix thermal derating direction and hard-clamp the hot endpoint.
p=root/"common_files/src/VescToSTM.c"
s=p.read_text()
old='''	//Do temperature Iq limit
	uint16_t temp = NTC_GetAvTemp_d(pMCT[M1]->pTemperatureSensor);
	if(temp < fp.temp_cut_start){
		app_adc_set_mode(M365_MODE_TEMP);
		iq = utils_map_int(temp, fp.temp_cut_start, fp.temp_cut_end, 0, iq);
	}else{
		app_adc_clear_mode(M365_MODE_TEMP);
	}'''
new='''	//Do temperature Iq limit
	uint16_t temp = NTC_GetAvTemp_d(pMCT[M1]->pTemperatureSensor);
	if(fp.temp_cut_start > fp.temp_cut_end){
		if(temp <= fp.temp_cut_end){
			/* NTC ADC falls as temperature rises: at/above end temperature, no torque. */
			app_adc_set_mode(M365_MODE_TEMP);
			iq = 0;
		}else if(temp < fp.temp_cut_start){
			app_adc_set_mode(M365_MODE_TEMP);
			/* start temperature = 100% requested Iq, end temperature = 0%. */
			iq = utils_map_int(temp, fp.temp_cut_start, fp.temp_cut_end, iq, 0);
		}else{
			app_adc_clear_mode(M365_MODE_TEMP);
		}
	}else{
		/* Invalid/non-monotonic calibration: do not extrapolate into sign reversal. */
		app_adc_clear_mode(M365_MODE_TEMP);
	}'''
assert old in s
s=s.replace(old,new,1)
# diagnostic getter: no stored state, only exposes the already-existing cut endpoints
anchor='''void VescToSTM_set_temp_cut(float start, float end){'''
idx=s.index(anchor)
end=s.index('\n}\n',idx)+3
insert='''\nvoid VescToSTM_get_temp_cut_raw(uint16_t *start, uint16_t *end){\n\tif(start) *start = fp.temp_cut_start;\n\tif(end) *end = fp.temp_cut_end;\n}\n'''
s=s[:end]+insert+s[end:]
p.write_text(s)

p=root/"common_files/src/VescToSTM.h"
s=p.read_text()
anchor='void VescToSTM_set_temp_cut(float start, float end);'
assert anchor in s
p.write_text(s.replace(anchor,anchor+'\nvoid VescToSTM_get_temp_cut_raw(uint16_t *start, uint16_t *end);',1))

# 4) Runtime watchdog: no new task/stack. Enable from the existing 10 ms LED health task.
p=root/"common_files/src/task_LED.c"
s=p.read_text()
anchor='''extern stm_state VescToSTM_mode;'''
wd='''extern stm_state VescToSTM_mode;

#ifdef G30P
static void g30_safety_iwdg_start(void){
	/* Nominal ~2 s: LSI ~40 kHz / 64 / 1250. Actual LSI tolerance is wide,
	 * still vastly longer than the 10 ms health-task cadence. */
	IWDG->KR = 0x5555u;
	IWDG->PR = 4u;       /* /64 */
	IWDG->RLR = 1250u;
	while(IWDG->SR != 0u) { }
	IWDG->KR = 0xAAAAu;
	IWDG->KR = 0xCCCCu;
}
static inline void g30_safety_iwdg_feed(void){
	IWDG->KR = 0xAAAAu;
}
#endif'''
assert anchor in s
s=s.replace(anchor,wd,1)

anchor='''void task_LED(void * argument)
{
	uint32_t last_fault_time=0;
	uint16_t last_fault = 0;
	/* Infinite loop */
	for(;;)
	{'''
replacement='''void task_LED(void * argument)
{
	uint32_t last_fault_time=0;
	uint16_t last_fault = 0;
#ifdef G30P
	/* Start only after task creation/runtime init. A pre-runtime boot problem remains
	 * recoverable without entering a watchdog reset loop. */
	g30_safety_iwdg_start();
#endif
	/* Infinite loop */
	for(;;)
	{'''
assert anchor in s
s=s.replace(anchor,replacement,1)
anchor='''		vTaskDelay(MS_TO_TICKS(10));'''
replacement='''#ifdef G30P
		g30_safety_iwdg_feed();
#endif
		vTaskDelay(MS_TO_TICKS(10));'''
assert anchor in s
s=s.replace(anchor,replacement,1)
p.write_text(s)

# 5) Motorpath diagnostics: temperature, stack/heap low-water, watchdog/reset flags.
p=root/"common_files/src/terminal.c"
s=p.read_text()
old='''        commands_printf(phandle,"MP cpu last=%lu max=%lu budget=%lu load=%lu%% heap=%u",
            (unsigned long)pMCI[M1]->pFOCVars->cycles_last,(unsigned long)maxcy,
            (unsigned long)budget,(unsigned long)load,(unsigned)xPortGetFreeHeapSize());
        commands_printf(phandle,"MP vbus=%ldmV offsets=%lu,%lu,%lu",'''
new='''        commands_printf(phandle,"MP cpu last=%lu max=%lu budget=%lu load=%lu%% heap=%u heap_min=%u cli_stack_hw=%u",
            (unsigned long)pMCI[M1]->pFOCVars->cycles_last,(unsigned long)maxcy,
            (unsigned long)budget,(unsigned long)load,(unsigned)xPortGetFreeHeapSize(),
            (unsigned)xPortGetMinimumEverFreeHeapSize(),
            (unsigned)uxTaskGetStackHighWaterMark(NULL));
        uint16_t temp_start_raw=0u,temp_end_raw=0u;
        VescToSTM_get_temp_cut_raw(&temp_start_raw,&temp_end_raw);
        commands_printf(phandle,"MP thermal raw=%u C=%d start_raw=%u end_raw=%u fault=%u",
            (unsigned)NTC_GetAvTemp_d(pMCT[M1]->pTemperatureSensor),
            (int)NTC_GetAvTemp_C(pMCT[M1]->pTemperatureSensor),
            (unsigned)temp_start_raw,(unsigned)temp_end_raw,
            (unsigned)NTC_CheckTemp(pMCT[M1]->pTemperatureSensor));
        commands_printf(phandle,"MP safety iwdg_pr=%lu iwdg_rlr=%lu reset_csr=%08lx break_en=%u",
            (unsigned long)IWDG->PR,(unsigned long)IWDG->RLR,(unsigned long)RCC->CSR,
            (unsigned)((TIM1->BDTR & TIM_BDTR_BKE)!=0u));
        commands_printf(phandle,"MP vbus=%ldmV offsets=%lu,%lu,%lu",'''
assert old in s
p.write_text(s.replace(old,new,1))

print("SESC Motorpath Safety V0.1 applied: instant OCP + thermal fix + 0.95 duty guard + IWDG + diagnostics")
