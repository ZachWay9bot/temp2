from pathlib import Path

root=Path("SOURCE_KOXX3")

p=root/"common_files/src/defines.h"
s=p.read_text()
assert '#define HW_NAME "SESC-DRV126-SHADOW-R0.3"' in s
p.write_text(s.replace('#define HW_NAME "SESC-DRV126-SHADOW-R0.3"',
                       '#define HW_NAME "SESC-DRV126-MOTORCORE-R1-GATED"',1))

p=root/"common_files/src/mc_tasks.c"
s=p.read_text()
s=s.replace("/* DRV126 Shadow R0.3 -------------------------------------------------------",
            "/* DRV126 MotorCore R1 gated takeover -------------------------------------",1)
s=s.replace(" * Diagnostic only. No TIM1/ADC/GPIO/PWM ownership.\n",
""" * R1 is the first deliberately armed PWM ownership test.
 * Default boot remains the validated SESC Hall path. DRV126 ownership exists
 * only after a RAM-only terminal ARM and only in Hall mode.
""",1)
s=s.replace(""" * R0.3 keeps the proven R0.2 input path and extends the shadow through the
 * original DRV126 inverse Park and six-sector SVPWM. It computes virtual
 * CCR1/2/3 only; it never writes TIM1 or PWMC state.
""",
""" * R0.3 proved inverse Park/SVPWM against live TIM1 with zero phase-order
 * mismatches and <=13/2000 compare error. R1 reuses that exact integer path,
 * updates it at 4 kHz (every fourth 16-kHz current ISR), scales stock
 * 4000-count CCRs to the existing validated 2000-count carrier, and commits
 * through the existing MCSDK ADC-sampling writer.
""",1)

old_globals="""volatile uint16_t g30_drv126_sh_drv_c1=0,g30_drv126_sh_drv_c2=0,g30_drv126_sh_drv_c3=0;
volatile uint16_t g30_drv126_sh_bridge_c1=0,g30_drv126_sh_bridge_c2=0,g30_drv126_sh_bridge_c3=0;
volatile uint16_t g30_drv126_sh_hw_c1=0,g30_drv126_sh_hw_c2=0,g30_drv126_sh_hw_c3=0;
volatile uint16_t g30_drv126_sh_order_mismatch=0,g30_drv126_sh_ccr_err_max=0;
volatile uint8_t g30_drv126_sh_drv_sec=0,g30_drv126_sh_bridge_sec=0,g30_drv126_sh_hw_sec=0;
"""
new_globals="""volatile uint16_t g30_drv126_r1_c1=1000u,g30_drv126_r1_c2=1000u,g30_drv126_r1_c3=1000u;
volatile uint16_t g30_drv126_r1_updates=0u,g30_drv126_r1_trips=0u;
volatile uint8_t g30_drv126_r1_arm=0u,g30_drv126_r1_active=0u,g30_drv126_r1_trip=0u;
volatile uint8_t g30_drv126_r1_div=0u,g30_drv126_r1_sec=0u,g30_drv126_r1_reason=0u;
"""
assert old_globals in s
s=s.replace(old_globals,new_globals,1)

# Replace R0.3 reset + medium shadow with R1 control core.
start=s.index("void g30_drv126_shadow_reset(void){")
end=s.index("\n#endif\n#if MUSIC_ENABLE",start)
r1_core=r'''#define G30_DRV126_R1_MAX_QREF_U 1500
#define G30_DRV126_R1_RAIL_MIN_RAW 80u
#define G30_DRV126_R1_RAIL_MAX_RAW 3920u

static void g30_drv126_r1_reset_core(void){
  g30_drv126_sh_q_acc=0;g30_drv126_sh_d_acc=0;
  g30_drv126_sh_qref_u=0;g30_drv126_sh_iq_u=0;g30_drv126_sh_id_u=0;
  g30_drv126_sh_vq=0;g30_drv126_sh_vd=0;
  g30_drv126_r1_div=0u;g30_drv126_r1_sec=0u;
  g30_drv126_r1_c1=1000u;g30_drv126_r1_c2=1000u;g30_drv126_r1_c3=1000u;
}
void g30_drv126_shadow_reset(void){
  if(g30_drv126_r1_active) return;
  g30_drv126_sh_samples=0u;g30_drv126_sh_clarke_max=0u;g30_drv126_sh_dq_max=0u;
  g30_drv126_sh_sat_q=0u;g30_drv126_sh_sat_d=0u;
  g30_drv126_sh_sesc_vq=0;g30_drv126_sh_sesc_vd=0;
  g30_drv126_r1_updates=0u;g30_drv126_r1_trips=0u;
  g30_drv126_r1_reset_core();
}
uint8_t g30_drv126_r1_trip_active(void){ return g30_drv126_r1_trip; }
int g30_drv126_r1_command(uint8_t cmd){
  if(cmd==1u){
    if(g30_drv126_r1_trip || !VescToSTM_g30_hall_selected() || !PWM_Handle_M1._Super.PWM_off) return 0;
    g30_drv126_r1_arm=1u;g30_drv126_r1_active=0u;g30_drv126_r1_reason=0u;
    g30_drv126_r1_reset_core();
    return 1;
  }
  if(cmd==0u){
    if(!PWM_Handle_M1._Super.PWM_off) return 0;
    g30_drv126_r1_active=0u;g30_drv126_r1_arm=0u;g30_drv126_r1_reset_core();
    return 1;
  }
  if(cmd==2u){
    if(!PWM_Handle_M1._Super.PWM_off) return 0;
    g30_drv126_r1_active=0u;g30_drv126_r1_arm=0u;g30_drv126_r1_trip=0u;g30_drv126_r1_reason=0u;
    g30_drv126_r1_reset_core();
    return 1;
  }
  return 0;
}
static uint16_t g30_drv126_r1_trip_now(uint8_t reason){
  g30_drv126_r1_reason=reason;
  g30_drv126_r1_trip=1u;g30_drv126_r1_arm=0u;g30_drv126_r1_active=0u;
  if(g30_drv126_r1_trips<65535u)g30_drv126_r1_trips++;
  PWMC_SwitchOffPWM(pwmcHandle[M1]);
  return MC_NO_ERROR;
}
static uint16_t g30_drv126_r1_step(PWMC_Handle_t *pHdl,ab_t Iab,int16_t angle,
                                   int16_t qref_mc,int16_t dref_mc){
  if(!g30_drv126_r1_arm || g30_drv126_r1_trip) return MC_NO_ERROR;
  if(!VescToSTM_g30_hall_selected()) return g30_drv126_r1_trip_now(2u);

  int32_t qref=g30_drv126_sh_stock_u_from_mc(qref_mc);
  int32_t dref=g30_drv126_sh_stock_u_from_mc(dref_mc);
  if(g30_drv126_sh_abs32(qref)>G30_DRV126_R1_MAX_QREF_U ||
     g30_drv126_sh_abs32(dref)>G30_DRV126_R1_MAX_QREF_U)
    return g30_drv126_r1_trip_now(1u);

  if(!g30_drv126_r1_active){
    g30_drv126_r1_active=1u;
    g30_drv126_r1_reset_core();
  }

  /* 16-kHz current acquisition, 4-kHz stock control update. Held CCRs between
   * updates keep the already validated ADC-sector/sample schedule coherent. */
  if(g30_drv126_r1_div!=0u){
    g30_drv126_r1_div=(uint8_t)((g30_drv126_r1_div+1u)&3u);
    return MC_NO_ERROR;
  }
  g30_drv126_r1_div=1u;

  int32_t ia=g30_drv126_sh_stock_u_from_mc(Iab.a);
  int32_t ib=g30_drv126_sh_stock_u_from_mc(Iab.b);
  int32_t alpha=ia;
  int32_t beta=((ia+2*ib)*2365)>>12;
  int32_t iq,id;
  g30_drv126_stock_park(alpha,beta,(uint16_t)angle,&iq,&id);

  g30_drv126_sh_qref_u=(int16_t)g30_drv126_sh_clamp32(qref,-32767,32767);
  g30_drv126_sh_iq_u=(int16_t)g30_drv126_sh_clamp32(iq,-32767,32767);
  g30_drv126_sh_id_u=(int16_t)g30_drv126_sh_clamp32(id,-32767,32767);
  g30_drv126_sh_vq=g30_drv126_sh_pi(qref,iq,&g30_drv126_sh_q_acc,
                                     25500057,31128,&g30_drv126_sh_sat_q);
  g30_drv126_sh_vd=g30_drv126_sh_pi(dref,id,&g30_drv126_sh_d_acc,
                                     8500019,10376,&g30_drv126_sh_sat_d);

  int16_t va,vb;
  uint16_t r1,r2,r3;
  g30_drv126_stock_invpark(g30_drv126_sh_vq,g30_drv126_sh_vd,
                           g30_drv126_sh_cos,g30_drv126_sh_sin,&va,&vb);
  uint8_t stock_sec=g30_drv126_stock_svpwm(va,vb,&r1,&r2,&r3);
  (void)stock_sec;

  if(r1<G30_DRV126_R1_RAIL_MIN_RAW || r1>G30_DRV126_R1_RAIL_MAX_RAW ||
     r2<G30_DRV126_R1_RAIL_MIN_RAW || r2>G30_DRV126_R1_RAIL_MAX_RAW ||
     r3<G30_DRV126_R1_RAIL_MIN_RAW || r3>G30_DRV126_R1_RAIL_MAX_RAW)
    return g30_drv126_r1_trip_now(3u);

  uint16_t c1=(uint16_t)((r1+1u)>>1);
  uint16_t c2=(uint16_t)((r2+1u)>>1);
  uint16_t c3=(uint16_t)((r3+1u)>>1);
  uint8_t sec=g30_drv126_order3(c1,c2,c3);
  if(sec==0u){ c1=1000u;c2=1000u;c3=1000u;sec=4u; }

  pHdl->CntPhA=c1;pHdl->CntPhB=c2;pHdl->CntPhC=c3;
  pHdl->Sector=(uint8_t)(sec-1u);
  uint16_t lo=c1,hi=c1;
  if(c2>lo)lo=c2;if(c3>lo)lo=c3;
  if(c2<hi)hi=c2;if(c3<hi)hi=c3;
  pHdl->lowDuty=lo;pHdl->highDuty=hi;
  pHdl->midDuty=(uint16_t)((uint32_t)c1+(uint32_t)c2+(uint32_t)c3-lo-hi);

  g30_drv126_r1_c1=c1;g30_drv126_r1_c2=c2;g30_drv126_r1_c3=c3;
  g30_drv126_r1_sec=sec;
  if(g30_drv126_r1_updates<65535u)g30_drv126_r1_updates++;
  if(g30_drv126_sh_samples<65535u)g30_drv126_sh_samples++;
  return pHdl->pFctSetADCSampPointSectX(pHdl);
}
'''
s=s[:start]+r1_core+s[end:]

# Remove old 1-kHz shadow hook from medium task.
assert "    g30_drv126_shadow_tick_1k();\n" in s
s=s.replace("    g30_drv126_shadow_tick_1k();\n","",1)

# Replace the FOC core tail with a gated R1 branch.
old=r'''  PWMC_GetPhaseCurrents(pwmcHandle[M1], &Iab);
  Ialphabeta = MCM_Clarke(Iab);
  Iqd = MCM_Park(Ialphabeta, hElAngle);
  Vqd.q = PI_Controller(pPIDIq[M1], (int32_t)(FOCVars[M1].Iqdref.q) - Iqd.q);
#if MUSIC_ENABLE
  Vqd.q += bldc_music.music_signal;
#endif

  Vqd.d = PI_Controller(pPIDId[M1], (int32_t)(FOCVars[M1].Iqdref.d) - Iqd.d);
  //min duty limit
  if(abs(Vqd.q) < FOCVars[M1].min_duty) Vqd.q = 0;
  if(abs(Vqd.d) < FOCVars[M1].min_duty) Vqd.d = 0;

  Vqd = Circle_Limitation(pCLM[M1], Vqd);
  hElAngle += hElSpeedDpp*REV_PARK_ANGLE_COMPENSATION_FACTOR;
  Valphabeta = MCM_Rev_Park(Vqd, hElAngle);
  /* Capture the PWM that produced the current sample, then complete the
   * time-critical PWM update BEFORE running the heavier shadow observer.
   * This preserves sample/PWM alignment without risking MC_FOC_DURATION. */
  uint16_t g30_old_ca = pwmcHandle[M1]->CntPhA;
  uint16_t g30_old_cb = pwmcHandle[M1]->CntPhB;
  uint16_t g30_old_cc = pwmcHandle[M1]->CntPhC;
  hCodeError = PWMC_SetPhaseVoltage(pwmcHandle[M1], Valphabeta);
  g30_fo76_shadow_step(Iab.a, Iab.b, HALL_M1._Super.hElAngle,
                       pBusSensorM1->_Super.AvBusVoltage_d,
                       g30_old_ca, g30_old_cb, g30_old_cc,
                       PWM_Handle_M1.Half_PWMPeriod,
                       (uint16_t)DEAD_TIME_COUNTS,
                       HALL_M1._Super.hElSpeedDpp,
                       (uint8_t)!PWM_Handle_M1._Super.PWM_off);
  FOCVars[M1].Vqd = Vqd;
  FOCVars[M1].Iab = Iab;
  FOCVars[M1].Ialphabeta = Ialphabeta;
  FOCVars[M1].Iqd = Iqd;
  FOCVars[M1].Valphabeta = Valphabeta;
  FOCVars[M1].hElAngle = hElAngle;
  /* FO76 R3B: PWM update is committed first; shadow uses captured old PWM. */
  FW_DataProcess(pFW[M1], Vqd, Iqd);
  return(hCodeError);
'''
new=r'''  PWMC_GetPhaseCurrents(pwmcHandle[M1], &Iab);
  Ialphabeta = MCM_Clarke(Iab);
  Iqd = MCM_Park(Ialphabeta, hElAngle);

#ifdef G30P
  if(g30_drv126_r1_arm || g30_drv126_r1_active){
    hCodeError=g30_drv126_r1_step(pwmcHandle[M1],Iab,hElAngle,
                                  FOCVars[M1].Iqdref.q,FOCVars[M1].Iqdref.d);
    FOCVars[M1].Iab=Iab;
    FOCVars[M1].Ialphabeta=Ialphabeta;
    FOCVars[M1].Iqd=Iqd;
    FOCVars[M1].Vqd.q=0;FOCVars[M1].Vqd.d=0;
    FOCVars[M1].Valphabeta.alpha=0;FOCVars[M1].Valphabeta.beta=0;
    FOCVars[M1].hElAngle=hElAngle;
    return hCodeError;
  }
#endif

  Vqd.q = PI_Controller(pPIDIq[M1], (int32_t)(FOCVars[M1].Iqdref.q) - Iqd.q);
#if MUSIC_ENABLE
  Vqd.q += bldc_music.music_signal;
#endif
  Vqd.d = PI_Controller(pPIDId[M1], (int32_t)(FOCVars[M1].Iqdref.d) - Iqd.d);
  if(abs(Vqd.q) < FOCVars[M1].min_duty) Vqd.q = 0;
  if(abs(Vqd.d) < FOCVars[M1].min_duty) Vqd.d = 0;
  Vqd = Circle_Limitation(pCLM[M1], Vqd);
  hElAngle += hElSpeedDpp*REV_PARK_ANGLE_COMPENSATION_FACTOR;
  Valphabeta = MCM_Rev_Park(Vqd, hElAngle);
  uint16_t g30_old_ca = pwmcHandle[M1]->CntPhA;
  uint16_t g30_old_cb = pwmcHandle[M1]->CntPhB;
  uint16_t g30_old_cc = pwmcHandle[M1]->CntPhC;
  hCodeError = PWMC_SetPhaseVoltage(pwmcHandle[M1], Valphabeta);
  g30_fo76_shadow_step(Iab.a, Iab.b, HALL_M1._Super.hElAngle,
                       pBusSensorM1->_Super.AvBusVoltage_d,
                       g30_old_ca, g30_old_cb, g30_old_cc,
                       PWM_Handle_M1.Half_PWMPeriod,
                       (uint16_t)DEAD_TIME_COUNTS,
                       HALL_M1._Super.hElSpeedDpp,
                       (uint8_t)!PWM_Handle_M1._Super.PWM_off);
  FOCVars[M1].Vqd = Vqd;
  FOCVars[M1].Iab = Iab;
  FOCVars[M1].Ialphabeta = Ialphabeta;
  FOCVars[M1].Iqd = Iqd;
  FOCVars[M1].Valphabeta = Valphabeta;
  FOCVars[M1].hElAngle = hElAngle;
  FW_DataProcess(pFW[M1], Vqd, Iqd);
  return(hCodeError);
'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s)

# Block automatic PWM restart after an R1 safety trip.
p=root/"common_files/src/VescToSTM.c"
s=p.read_text()
needle="""void VescToSTM_pwm_start(void){
#ifdef G30P
"""
repl="""void VescToSTM_pwm_start(void){
#ifdef G30P
    extern uint8_t g30_drv126_r1_trip_active(void);
    if(g30_drv126_r1_trip_active()) return;
"""
assert needle in s
s=s.replace(needle,repl,1)
p.write_text(s)

# Terminal: replace R0.3 shadow report with R1 state and add ARM/OFF/CLEAR command.
p=root/"common_files/src/terminal.c"
s=p.read_text()
start=s.index('    }else if (strcmp(argv[0], "g30_drv126_shadow_reset") == 0){')
end=s.index('    }else if (strcmp(argv[0], "g30_motorpath_reset") == 0){',start)
block=r'''    }else if (strcmp(argv[0], "g30_drv126_shadow_reset") == 0){
#ifdef G30P
        extern void g30_drv126_shadow_reset(void);
        g30_drv126_shadow_reset();
        commands_printf(phandle,"DRV126R1 DIAG_RESET");
#else
        commands_printf(phandle,"DRV126R1 unavailable");
#endif
    }else if (strcmp(argv[0], "g30_drv126_r1") == 0){
#ifdef G30P
        extern int g30_drv126_r1_command(uint8_t cmd);
        int ok=1;
        if(argc==2 && strcmp(argv[1],"arm")==0) ok=g30_drv126_r1_command(1u);
        else if(argc==2 && strcmp(argv[1],"off")==0) ok=g30_drv126_r1_command(0u);
        else if(argc==2 && strcmp(argv[1],"clear")==0) ok=g30_drv126_r1_command(2u);
        else if(argc!=1 && !(argc==2 && strcmp(argv[1],"status")==0)){
            commands_printf(phandle,"Usage: g30_drv126_r1 [arm | off | clear | status]");
            return;
        }
        commands_printf(phandle,"DRV126R1 command_ok=%u",(unsigned)(ok?1u:0u));
#else
        commands_printf(phandle,"DRV126R1 unavailable");
#endif
    }else if (strcmp(argv[0], "g30_drv126_shadow") == 0){
#ifdef G30P
        extern volatile uint16_t g30_drv126_sh_samples,g30_drv126_sh_sat_q,g30_drv126_sh_sat_d;
        extern volatile int16_t g30_drv126_sh_qref_u,g30_drv126_sh_iq_u,g30_drv126_sh_id_u;
        extern volatile int16_t g30_drv126_sh_vq,g30_drv126_sh_vd,g30_drv126_sh_cos,g30_drv126_sh_sin;
        extern volatile uint16_t g30_drv126_r1_c1,g30_drv126_r1_c2,g30_drv126_r1_c3;
        extern volatile uint16_t g30_drv126_r1_updates,g30_drv126_r1_trips;
        extern volatile uint8_t g30_drv126_r1_arm,g30_drv126_r1_active,g30_drv126_r1_trip;
        extern volatile uint8_t g30_drv126_r1_div,g30_drv126_r1_sec,g30_drv126_r1_reason;
        commands_printf(phandle,"DRV126R1 mode=GATED_4K owner=%s arm=%u active=%u trip=%u reason=%u writes=%u samples=%u",
            g30_drv126_r1_active?"DRV126":"SESC",
            (unsigned)g30_drv126_r1_arm,(unsigned)g30_drv126_r1_active,
            (unsigned)g30_drv126_r1_trip,(unsigned)g30_drv126_r1_reason,
            (unsigned)g30_drv126_r1_updates,(unsigned)g30_drv126_sh_samples);
        commands_printf(phandle,"DRV126R1 guard maxQrefU=1500 railRaw=80..3920 div=%u trips=%u hall=%u pwmOff=%u",
            (unsigned)g30_drv126_r1_div,(unsigned)g30_drv126_r1_trips,
            (unsigned)VescToSTM_g30_hall_selected(),(unsigned)PWM_Handle_M1._Super.PWM_off);
        commands_printf(phandle,"DRV126R1 core qrefU=%d iqU=%d idU=%d qB=%d satQ=%u dC=%d satD=%u trig=%d,%d",
            (int)g30_drv126_sh_qref_u,(int)g30_drv126_sh_iq_u,(int)g30_drv126_sh_id_u,
            (int)g30_drv126_sh_vq,(unsigned)g30_drv126_sh_sat_q,
            (int)g30_drv126_sh_vd,(unsigned)g30_drv126_sh_sat_d,
            (int)g30_drv126_sh_cos,(int)g30_drv126_sh_sin);
        commands_printf(phandle,"DRV126R1 PWM sec=%u ccr=%u,%u,%u",
            (unsigned)g30_drv126_r1_sec,(unsigned)g30_drv126_r1_c1,
            (unsigned)g30_drv126_r1_c2,(unsigned)g30_drv126_r1_c3);
#else
        commands_printf(phandle,"DRV126R1 unavailable");
#endif
'''
s=s[:start]+block+s[end:]
p.write_text(s)

print("SESC DRV126 MotorCore R1 gated takeover applied: Hall-only, 4k control, hard current/rail trip")
