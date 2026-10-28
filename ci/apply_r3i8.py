from pathlib import Path
R=Path("SOURCE_KOXX3/common_files/src")
p=R/"defines.h"; s=p.read_text(); s=s.replace('#define HW_NAME "G30D-FO76-PUSHSTART-R3I7"','#define HW_NAME "G30D-FO76-PUSHSTART-R3I8"',1); p.write_text(s)

p=R/"mc_tasks.c"; s=p.read_text()
old='''#ifdef G30P
  g30_r3i_tick((uint8_t)PWM_Handle_M1._Super.PWM_off,(uint16_t)HALL_M1._Super.hElAngle,HALL_M1._Super.hElSpeedDpp);
#endif
  bool IsSpeedReliable;
'''
new='''  bool IsSpeedReliable;
'''
if old not in s: raise SystemExit("medium anchor")
s=s.replace(old,new,1)
old='''	  uint16_t voltage_fault = RVBS_CalcAvVbus(pBusSensorM1);
	  if(voltage_fault==MC_UNDER_VOLT){
'''
new='''	  uint16_t voltage_fault = RVBS_CalcAvVbus(pBusSensorM1);
#ifdef G30P
      g30_r3i_tick((uint8_t)PWM_Handle_M1._Super.PWM_off,
                   (uint16_t)HALL_M1._Super.hElAngle,
                   HALL_M1._Super.hElSpeedDpp);
#endif
	  if(voltage_fault==MC_UNDER_VOLT){
'''
if old not in s: raise SystemExit("safety anchor")
p.write_text(s.replace(old,new,1))

p=R/"terminal.c"; s=p.read_text()
s=s.replace('FO76_R3I7 pushstart_sensorless=1','FO76_R3I8 pushstart_sensorless=1',1)
s=s.replace('R3I7 ARM: PWM blocked; IDLE auto-restarts at zero; BEMF angle + observer frequency catch','R3I8 ARM: serialized regular ADC; BEMF angle + observer frequency catch',1)
old='''        commands_printf(phandle,"mcstate=%u pwm_off=%u start_pending=%u adc_ready=%u handles=%u,%u,%u",
            (unsigned)STM_GetState(&STM[M1]),(unsigned)PWM_Handle_M1._Super.PWM_off,
            (unsigned)g30_r3i_start_pending(),(unsigned)g30_r3i_adc_ready(),
            (unsigned)g30_r3i_adc_handle_a(),(unsigned)g30_r3i_adc_handle_b(),
            (unsigned)g30_r3i_adc_handle_c());
'''
new='''        commands_printf(phandle,"mcstate=%u pwm_off=%u start_pending=%u adc_ready=%u handles=%u,%u,%u vbus_now=%ld adc_vbus=%u",
            (unsigned)STM_GetState(&STM[M1]),(unsigned)PWM_Handle_M1._Super.PWM_off,
            (unsigned)g30_r3i_start_pending(),(unsigned)g30_r3i_adc_ready(),
            (unsigned)g30_r3i_adc_handle_a(),(unsigned)g30_r3i_adc_handle_b(),
            (unsigned)g30_r3i_adc_handle_c(),
            (long)(VescToSTM_get_bus_voltage()*1000.0f),
            (unsigned)RealBusVoltageSensorParamsM1._Super.AvBusVoltage_d);
'''
if old not in s: raise SystemExit("status anchor")
p.write_text(s.replace(old,new,1))
print("R3I8 transform applied")
