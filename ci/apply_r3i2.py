from pathlib import Path

ROOT=Path("SOURCE_KOXX3")
SRC=ROOT/"common_files/src"

def one(path, old, new, label):
    p=path
    s=p.read_text()
    n=s.count(old)
    if n!=1:
        raise SystemExit(f"{label}: expected one anchor, got {n}")
    p.write_text(s.replace(old,new,1))

# Identity: preserve failed hardware R3I and create an explicit fixed candidate.
one(SRC/"defines.h",
    '#define HW_NAME "G30D-FO76-PUSHSTART-R3I"',
    '#define HW_NAME "G30D-FO76-PUSHSTART-R3I2"',
    "build id")

# R3I2 start request API.
p=SRC/"g30_r3i_pushstart.h"; s=p.read_text()
old='''uint8_t g30_r3i_sensorless_active(void);
uint32_t g30_r3i_active_age_ms(void);
'''
new='''uint8_t g30_r3i_sensorless_active(void);
uint8_t g30_r3i_start_pending(void);
void g30_r3i_start_consumed(void);
uint32_t g30_r3i_active_age_ms(void);
'''
if old not in s: raise SystemExit("pushstart header anchor")
p.write_text(s.replace(old,new,1))

# R3I2: seed does not directly imply that the MCSDK state machine is running.
# It raises a pending restart, consumed only from IDLE in mc_tasks.c.
p=SRC/"g30_r3i_pushstart.c"; s=p.read_text()
s=s.replace('static volatile uint8_t request_arm;\n',
            'static volatile uint8_t request_arm;\nstatic volatile uint8_t start_request;\n',1)
old='''void g30_r3i_request_arm(uint8_t enable){
    request_arm=enable?1u:0u;
    if(!enable){d.mode=0u;d.sensorless_started=0u;return;}
    arm_had_cal=cal_persist_valid;
    reset_roll();d.mode=1u;
}
uint8_t g30_r3i_block_pwm_start(void){return (uint8_t)(d.mode==1u && !d.sensorless_started);}
uint8_t g30_r3i_sensorless_active(void){return (uint8_t)(d.mode==2u && d.sensorless_started);}
'''
new='''void g30_r3i_request_arm(uint8_t enable){
    request_arm=enable?1u:0u;
    start_request=0u;
    if(!enable){d.mode=0u;d.sensorless_started=0u;return;}
    arm_had_cal=cal_persist_valid;
    reset_roll();d.mode=1u;
}
uint8_t g30_r3i_block_pwm_start(void){return (uint8_t)(d.mode==1u && !d.sensorless_started);}
uint8_t g30_r3i_sensorless_active(void){return (uint8_t)(d.mode==2u && d.sensorless_started);}
uint8_t g30_r3i_start_pending(void){return start_request;}
void g30_r3i_start_consumed(void){start_request=0u;}
'''
if old not in s: raise SystemExit("pushstart arm/api anchor")
s=s.replace(old,new,1)
old='''                g30_fo76_sensorless_seed(d.phase_cal,d.speed_dpp);
                d.sensorless_started=1u;d.mode=2u;d.starts++;start_tick=HAL_GetTick();
'''
new='''                g30_fo76_sensorless_seed(d.phase_cal,d.speed_dpp);
                d.sensorless_started=1u;d.mode=2u;d.starts++;start_tick=HAL_GetTick();
                start_request=1u;
'''
if old not in s: raise SystemExit("pushstart seed/start request anchor")
p.write_text(s.replace(old,new,1))

# Keep the external observer seed through MCSDK's normal FOC_Clear restart, and
# restart MCSDK only after the passive BEMF seed exists and the state machine is IDLE.
p=SRC/"mc_tasks.c"; s=p.read_text()
old='''  StateM1 = STM_GetState( &STM[M1] );

  switch ( StateM1 )
'''
new='''  StateM1 = STM_GetState( &STM[M1] );

#ifdef G30P
  if(g30_r3i_start_pending() && StateM1==IDLE)
  {
    if(MCI_StartMotor( pMCI[M1] ))
    {
      g30_r3i_start_consumed();
    }
  }
#endif

  switch ( StateM1 )
'''
if old not in s: raise SystemExit("mc state/restart anchor")
s=s.replace(old,new,1)

old='''      FOC_Clear( M1 );

      R3_2_SwitchOnPWM( pwmcHandle[M1] );
'''
new='''      FOC_Clear( M1 );

#ifdef G30P
      if(g30_fo76_sensorless_active()) VescToSTM_prepare_sensorless_start();
#endif
      R3_2_SwitchOnPWM( pwmcHandle[M1] );
'''
if old not in s: raise SystemExit("clear pwm start anchor")
s=s.replace(old,new,1)

old='''#ifdef G30P
  /* R3G never carries an armed observer takeover through a motor restart. */
  g30_fo76_request_takeover(0u);
#endif
'''
new='''#ifdef G30P
  /* R3I2 preserves an externally seeded sensorless trajectory through the
   * intentional STOP->IDLE->START transition. All ordinary restarts still
   * disarm observer takeover exactly as before. */
  if(!g30_fo76_sensorless_active()) g30_fo76_request_takeover(0u);
#endif
'''
if old not in s: raise SystemExit("FOC_Clear observer disarm anchor")
p.write_text(s.replace(old,new,1))

# Split voltage-integrator preparation from direct PWM switching so the normal
# MCSDK state-machine restart can use the same rolling-start preload.
p=SRC/"VescToSTM.h"; s=p.read_text()
old='''void VescToSTM_pwm_start(void);
void VescToSTM_pwm_stop(void);
'''
new='''void VescToSTM_pwm_start(void);
void VescToSTM_prepare_sensorless_start(void);
void VescToSTM_pwm_stop(void);
'''
if old not in s: raise SystemExit("VescToSTM header anchor")
p.write_text(s.replace(old,new,1))

p=SRC/"VescToSTM.c"; s=p.read_text()
anchor='''void VescToSTM_pwm_start(void){
#ifdef G30P
    if(g30_r3i_block_pwm_start()) return;
    if(g30_r3i_sensorless_active()){
        int32_t erpm=g30_r3i_erpm();
        float rad_s=(float)erpm*((2.0f*(float)M_PI)/60.0f);
        motor_voltage=rad_s*mc_conf.foc_motor_flux_linkage;
    }
#endif
	if(PWM_Handle_M1._Super.PWM_off){
		float fVd = 32768.0 / VescToSTM_get_bus_voltage() * motor_voltage;
		utils_truncate_number(&fVd, -32767, 32767);
		PIDIqHandle_M1.wIntegralTerm = fVd * TF_KIDIV;
		PIDIdHandle_M1.wIntegralTerm = -PIDIqHandle_M1.wIntegralTerm/4;
		HALL_M1._Super.hElAngle = HALL_M1.MeasuredElAngle;
		HALL_M1.CompSpeed = 0;
		HALL_M1._Super.hAvrMecSpeedUnit = 0;
		PWMC_SwitchOnPWM(&PWM_Handle_M1._Super);
	}
}
'''
replacement='''void VescToSTM_prepare_sensorless_start(void){
#ifdef G30P
    if(!g30_r3i_sensorless_active()) return;
    int32_t erpm=g30_r3i_erpm();
    float rad_s=(float)erpm*((2.0f*(float)M_PI)/60.0f);
    motor_voltage=rad_s*mc_conf.foc_motor_flux_linkage;
    float fVd = 32768.0 / VescToSTM_get_bus_voltage() * motor_voltage;
    utils_truncate_number(&fVd, -32767, 32767);
    PIDIqHandle_M1.wIntegralTerm = fVd * TF_KIDIV;
    PIDIdHandle_M1.wIntegralTerm = -PIDIqHandle_M1.wIntegralTerm/4;
#endif
}

void VescToSTM_pwm_start(void){
#ifdef G30P
    if(g30_r3i_block_pwm_start()) return;
    if(g30_r3i_sensorless_active()) VescToSTM_prepare_sensorless_start();
#endif
	if(PWM_Handle_M1._Super.PWM_off){
		float fVd = 32768.0 / VescToSTM_get_bus_voltage() * motor_voltage;
		utils_truncate_number(&fVd, -32767, 32767);
		PIDIqHandle_M1.wIntegralTerm = fVd * TF_KIDIV;
		PIDIdHandle_M1.wIntegralTerm = -PIDIqHandle_M1.wIntegralTerm/4;
		HALL_M1._Super.hElAngle = HALL_M1.MeasuredElAngle;
		HALL_M1.CompSpeed = 0;
		HALL_M1._Super.hAvrMecSpeedUnit = 0;
		PWMC_SwitchOnPWM(&PWM_Handle_M1._Super);
	}
}
'''
if anchor not in s: raise SystemExit("VescToSTM PWM block anchor")
p.write_text(s.replace(anchor,replacement,1))

# Terminal ARM now really means coast/stop first. No passive measurement can
# begin while the old RUN/PWM state is still active.
p=SRC/"terminal.c"; s=p.read_text()
old='''        if(argc==2 && strcmp(argv[1],"arm")==0){
            g30_r3i_request_arm(1u);
            g30_fo76_request_takeover(0u);
            commands_printf(phandle,"R3I pushstart ARM: first arm calibrates fixed BEMF frame from Hall; later arms in same boot start from passive BEMF without Hall gate");
'''
new='''        if(argc==2 && strcmp(argv[1],"arm")==0){
            VescToSTM_set_speed(0);
            (void)MCI_StopMotor( pMCI[M1] );
            VescToSTM_pwm_stop();
            g30_fo76_request_takeover(0u);
            g30_r3i_request_arm(1u);
            commands_printf(phandle,"R3I2 ARM: forced MCSDK STOP + PWM OFF; passive BEMF sampling only after coast");
'''
if old not in s: raise SystemExit("terminal ARM anchor")
s=s.replace(old,new,1)

old='''        commands_printf(phandle,"phase_base=%u phase_cal=%u hall=%u err=%d cal_n=%u offset=%d",
            (unsigned)ps.phase_base,(unsigned)ps.phase_cal,(unsigned)ps.hall,(int)ps.phase_error,
            (unsigned)ps.cal_samples,(int)ps.cal_offset);
'''
new='''        commands_printf(phandle,"phase_base=%u phase_cal=%u hall=%u err=%d cal_n=%u offset=%d",
            (unsigned)ps.phase_base,(unsigned)ps.phase_cal,(unsigned)ps.hall,(int)ps.phase_error,
            (unsigned)ps.cal_samples,(int)ps.cal_offset);
        commands_printf(phandle,"mcstate=%u pwm_off=%u start_pending=%u",
            (unsigned)STM_GetState(&STM[M1]),(unsigned)PWM_Handle_M1._Super.PWM_off,
            (unsigned)g30_r3i_start_pending());
'''
if old not in s: raise SystemExit("terminal status telemetry anchor")
s=s.replace(old,new,1)
s=s.replace('FO76_R3I pushstart_sensorless=1','FO76_R3I2 pushstart_sensorless=1',1)
p.write_text(s)

print("R3I2 transform applied")
