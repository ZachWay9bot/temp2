from pathlib import Path

root=Path("SOURCE_KOXX3")

# Build identity
p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-MOTORCORE-FINAL-V1"'
new='#define HW_NAME "SESC-DRV126-POWERCORE6500-FINAL-V1"'
assert old in s
p.write_text(s.replace(old,new,1))

# Shared DRV126 power core for Hall-only and Sensorless-only.
p=root/"common_files/src/mc_tasks.c"
s=p.read_text()

needle='''static int32_t g30_drv126_final_q_acc=0;
static int32_t g30_drv126_final_d_acc=0;
static int16_t g30_drv126_final_vq=0;
static int16_t g30_drv126_final_vd=0;
static uint8_t g30_drv126_final_div=0u;
'''
repl='''static int32_t g30_drv126_final_q_acc=0;
static int32_t g30_drv126_final_d_acc=0;
static int16_t g30_drv126_final_vq=0;
static int16_t g30_drv126_final_vd=0;
static uint8_t g30_drv126_final_div=0u;

/* Modified DRV126 / SHUD1 current-raising coefficient.
 * Stock DRV126 = 300 mA/update, modified DRV126 = 6500 mA/update.
 * The DRV126 control law executes at 4 kHz. G30 SESC phase-current scaling is
 * 374.6797 counts/A, therefore 6500 mA = 2435.418 counts -> 2435 counts.
 * This slew is deliberately before the stock-domain current PI. */
#define G30_DRV126_CURRENT_RAISING_COEFF_MA 6500
#define G30_DRV126_CURRENT_RAISING_STEP_MC 2435
static int32_t g30_drv126_final_q_slew_mc=0;
'''
assert needle in s
s=s.replace(needle,repl,1)

needle='''  g30_drv126_final_vq=0;
  g30_drv126_final_vd=0;
  g30_drv126_final_div=0u;
}'''
repl='''  g30_drv126_final_vq=0;
  g30_drv126_final_vd=0;
  g30_drv126_final_div=0u;
  g30_drv126_final_q_slew_mc=0;
}'''
assert needle in s
s=s.replace(needle,repl,1)

old='''static uint16_t g30_drv126_final_hall_step(PWMC_Handle_t *pHdl,ab_t Iab,
                                           int16_t angle,int16_t qref_mc,
                                           int16_t dref_mc){'''
new='''static uint16_t g30_drv126_final_power_step(PWMC_Handle_t *pHdl,ab_t Iab,
                                            int16_t angle,int16_t qref_mc,
                                            int16_t dref_mc,uint8_t hall_guard){'''
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
     (hall_guard &&
      (raw==0u || raw==7u || HALL_M1.lut[raw]==255u || !HALL_M1.SensorIsReliable))){
    PWMC_SwitchOffPWM(pHdl);
    return MC_NO_ERROR;
  }'''
assert old in s
s=s.replace(old,new,1)

old='''  int32_t qmc=g30_drv126_final_clamp32((int32_t)qref_mc,neg,pos);
  int32_t phase_lim=pos;
  if(-neg>phase_lim)phase_lim=-neg;
  int32_t dmc=g30_drv126_final_clamp32((int32_t)dref_mc,-phase_lim,phase_lim);

  /* Hold DRV126 voltage for four 16-kHz current samples. The MCSDK
   * ADC/sample-point writer still runs on every ISR. */
  if(g30_drv126_final_div!=0u){
    g30_drv126_final_div=(uint8_t)((g30_drv126_final_div+1u)&3u);
    return pHdl->pFctSetADCSampPointSectX(pHdl);
  }
  g30_drv126_final_div=1u;

  int32_t ia='''
new='''  int32_t qtarget=g30_drv126_final_clamp32((int32_t)qref_mc,neg,pos);
  int32_t phase_lim=pos;
  if(-neg>phase_lim)phase_lim=-neg;
  int32_t dmc=g30_drv126_final_clamp32((int32_t)dref_mc,-phase_lim,phase_lim);

  /* Hold DRV126 voltage for four 16-kHz current samples. The MCSDK
   * ADC/sample-point writer still runs on every ISR. */
  if(g30_drv126_final_div!=0u){
    g30_drv126_final_div=(uint8_t)((g30_drv126_final_div+1u)&3u);
    return pHdl->pFctSetADCSampPointSectX(pHdl);
  }
  g30_drv126_final_div=1u;

  /* Exact modified-DRV126 setpoint behavior: before the current PI, move the
   * requested q current toward target by at most coeff=6500 mA per 4-kHz
   * controller update. This is the only intentional Stock->CFW behavior delta. */
  int32_t qdelta=qtarget-g30_drv126_final_q_slew_mc;
  if(qdelta>G30_DRV126_CURRENT_RAISING_STEP_MC)
      g30_drv126_final_q_slew_mc+=G30_DRV126_CURRENT_RAISING_STEP_MC;
  else if(qdelta< -G30_DRV126_CURRENT_RAISING_STEP_MC)
      g30_drv126_final_q_slew_mc-=G30_DRV126_CURRENT_RAISING_STEP_MC;
  else
      g30_drv126_final_q_slew_mc=qtarget;
  int32_t qmc=g30_drv126_final_q_slew_mc;

  int32_t ia='''
assert old in s
s=s.replace(old,new,1)

old='''#ifdef G30P
  if(VescToSTM_g30_hall_selected()){
    hCodeError=g30_drv126_final_hall_step(pwmcHandle[M1],Iab,hElAngle,
                                          FOCVars[M1].Iqdref.q,
                                          FOCVars[M1].Iqdref.d);

    /* Keep the SESC supervisory layer truthful. R0.2/R0.3 established that
     * these q/d voltage units are compatible with the DRV126 controller. */
    Ialphabeta=MCM_Clarke(Iab);
    Iqd=MCM_Park(Ialphabeta,hElAngle);
    Vqd.q=g30_drv126_final_vq;
    Vqd.d=g30_drv126_final_vd;
    Valphabeta=MCM_Rev_Park(Vqd,hElAngle);

    FOCVars[M1].Iab=Iab;
    FOCVars[M1].Ialphabeta=Ialphabeta;
    FOCVars[M1].Iqd=Iqd;
    FOCVars[M1].Vqd=Vqd;
    FOCVars[M1].Valphabeta=Valphabeta;
    FOCVars[M1].hElAngle=hElAngle;
    FW_DataProcess(pFW[M1],Vqd,Iqd);
    return hCodeError;
  }
#endif
'''
new='''#ifdef G30P
  if(VescToSTM_g30_hall_selected() ||
     (VescToSTM_g30_sensorless_selected() && g30_fo76_sensorless_active())){
    /* VESC Tool still selects HALL ONLY or SENSORLESS ONLY exactly as before.
     * Only the angle/speed source changes. The motor/current/power-stage path
     * below is the same DRV126 core in both modes. */
    uint16_t g30_old_ca=pwmcHandle[M1]->CntPhA;
    uint16_t g30_old_cb=pwmcHandle[M1]->CntPhB;
    uint16_t g30_old_cc=pwmcHandle[M1]->CntPhC;
    uint8_t hall_guard=(uint8_t)VescToSTM_g30_hall_selected();

    hCodeError=g30_drv126_final_power_step(pwmcHandle[M1],Iab,hElAngle,
                                           FOCVars[M1].Iqdref.q,
                                           FOCVars[M1].Iqdref.d,
                                           hall_guard);

    /* Keep SESC's supervisory layer truthful for battery limiting, FW,
     * power calculation and VESC telemetry. */
    Ialphabeta=MCM_Clarke(Iab);
    Iqd=MCM_Park(Ialphabeta,hElAngle);
    Vqd.q=g30_drv126_final_vq;
    Vqd.d=g30_drv126_final_vd;
    Valphabeta=MCM_Rev_Park(Vqd,hElAngle);

    FOCVars[M1].Iab=Iab;
    FOCVars[M1].Ialphabeta=Ialphabeta;
    FOCVars[M1].Iqd=Iqd;
    FOCVars[M1].Vqd=Vqd;
    FOCVars[M1].Valphabeta=Valphabeta;
    FOCVars[M1].hElAngle=hElAngle;
    FW_DataProcess(pFW[M1],Vqd,Iqd);

    if(VescToSTM_g30_sensorless_selected()){
      /* FO76 observes the voltage actually present during this current sample:
       * the previous DRV126 PWM vector. This preserves the frozen 16-kHz
       * observer model while the DRV126 current controller runs at 4 kHz. */
      g30_fo76_shadow_step(Iab.a,Iab.b,HALL_M1._Super.hElAngle,
                           pBusSensorM1->_Super.AvBusVoltage_d,
                           g30_old_ca,g30_old_cb,g30_old_cc,
                           PWM_Handle_M1.Half_PWMPeriod,
                           (uint16_t)DEAD_TIME_COUNTS,
                           HALL_M1._Super.hElSpeedDpp,
                           (uint8_t)!PWM_Handle_M1._Super.PWM_off);
    }
    return hCodeError;
  }
#endif
'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s)

# Sensorless start preload must seed the DRV126 controller now owning PWM.
p=root/"common_files/src/VescToSTM.c"
s=p.read_text()
old='''void VescToSTM_prepare_sensorless_start(void){
#ifdef G30P
    /* May also be called from MCSDK CLEAR immediately before its direct'''
new='''void VescToSTM_prepare_sensorless_start(void){
#ifdef G30P
    extern void g30_drv126_final_preload(int16_t vq,int16_t vd);
    /* May also be called from MCSDK CLEAR immediately before its direct'''
assert old in s
s=s.replace(old,new,1)

old='''    PIDIdHandle_M1.wIntegralTerm=g30_r3i_preload_integral(initial.vd_counts,
        PIDIdHandle_M1.hKiDivisor,PIDIdHandle_M1.wLowerIntegralLimit,PIDIdHandle_M1.wUpperIntegralLimit);
    motor_voltage=(float)initial.bemf_mv/1000.0f;'''
new='''    PIDIdHandle_M1.wIntegralTerm=g30_r3i_preload_integral(initial.vd_counts,
        PIDIdHandle_M1.hKiDivisor,PIDIdHandle_M1.wLowerIntegralLimit,PIDIdHandle_M1.wUpperIntegralLimit);
    /* Sensorless uses the same DRV126 power core as Hall. Seed the controller
     * that actually owns PWM; keep the legacy MCSDK preload for diagnostics. */
    g30_drv126_final_preload(initial.vq_counts,initial.vd_counts);
    motor_voltage=(float)initial.bemf_mv/1000.0f;'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s)

print("SESC DRV126 POWERCORE6500 FINAL V1 applied")
