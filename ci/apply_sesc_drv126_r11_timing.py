from pathlib import Path

root=Path("SOURCE_KOXX3")

p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-MOTORCORE-R1-GATED"'
new='#define HW_NAME "SESC-DRV126-MOTORCORE-R1.1-TIMING"'
assert old in s
p.write_text(s.replace(old,new,1))

p=root/"common_files/src/mc_tasks.c"
s=p.read_text()

# 32-bit exact floor bridges; all reachable products are proven within int32.
old="""static int32_t g30_drv126_sh_stock_u_from_mc(int16_t counts){
  /* Exact bridge into the DRV126 internal current integer domain.
   * MCSDK count = 16 * original 12-bit ADC delta on this configured G30 path.
   * DRV126: signed MUL 51575 then ASRS #10. Combined denominator = 16384.
   * Spell out floor-for-negative so the host test and ARM ASR agree. */
  int64_t p=(int64_t)counts*51575LL;
  if(p>=0) return (int32_t)(p/16384LL);
  return (int32_t)(-((-p+16383LL)/16384LL));
}
"""
new="""static inline __attribute__((always_inline)) int32_t g30_drv126_sh_stock_u_from_mc(int16_t counts){
  /* int16 * 51575 fits signed int32: max magnitude 1,690,009,600.
   * Preserve arithmetic-right-shift floor semantics without 64-bit helpers. */
  int32_t p=(int32_t)counts*51575;
  if(p>=0) return p>>14;
  return -(((-p)+16383)>>14);
}
"""
assert old in s
s=s.replace(old,new,1)

old="""static int32_t g30_drv126_asr_floor(int32_t v,uint8_t s){
  if(v>=0) return v>>s;
  return -(int32_t)(((int64_t)(-v)+(((int64_t)1<<s)-1))>>s);
}
"""
new="""static inline __attribute__((always_inline)) int32_t g30_drv126_asr_floor(int32_t v,uint8_t s){
  /* Every DRV126 transform intermediate here is far from INT32_MIN.
   * 32-bit floor-preserving ASR avoids the generic 64-bit sequence in R1. */
  if(v>=0) return v>>s;
  return -(((-v)+(((int32_t)1<<s)-1))>>s);
}
"""
assert old in s
s=s.replace(old,new,1)

# Add cycle diagnostics without bloating RAM.
needle="volatile uint16_t g30_drv126_r1_updates=0u,g30_drv126_r1_trips=0u;"
assert needle in s
s=s.replace(needle,needle+"\nvolatile uint16_t g30_drv126_r11_cycles_last=0u,g30_drv126_r11_cycles_max=0u;",1)

# Reset timing counters only when explicit diagnostic reset occurs.
needle="  g30_drv126_r1_updates=0u;g30_drv126_r1_trips=0u;"
assert needle in s
s=s.replace(needle,needle+"\n  g30_drv126_r11_cycles_last=0u;g30_drv126_r11_cycles_max=0u;",1)

# Fast Hall reliability check and commit held CCR/sample point every 16-kHz ISR.
old="""  if(!g30_drv126_r1_arm || g30_drv126_r1_trip) return MC_NO_ERROR;
  if(!VescToSTM_g30_hall_selected() || !VescToSTM_g30_hall_feedback_valid())
    return g30_drv126_r1_trip_now(2u);
"""
new="""  if(!g30_drv126_r1_arm || g30_drv126_r1_trip) return MC_NO_ERROR;
  if(!VescToSTM_g30_hall_selected() || !HALL_M1.SensorIsReliable)
    return g30_drv126_r1_trip_now(2u);
"""
assert old in s
s=s.replace(old,new,1)

old="""  if(g30_drv126_r1_div!=0u){
    g30_drv126_r1_div=(uint8_t)((g30_drv126_r1_div+1u)&3u);
    return MC_NO_ERROR;
  }
"""
new="""  if(g30_drv126_r1_div!=0u){
    g30_drv126_r1_div=(uint8_t)((g30_drv126_r1_div+1u)&3u);
    /* MCSDK requires a timing/sample-point commit on every current ISR even
     * while DRV126 voltage is held for the 4-kHz control cadence. */
    return pHdl->pFctSetADCSampPointSectX(pHdl);
  }
"""
assert old in s
s=s.replace(old,new,1)

# Reorder the R1 branch before duplicate MCSDK Clarke/Park and measure exact R1 cycles.
old="""  PWMC_GetPhaseCurrents(pwmcHandle[M1], &Iab);
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

  Vqd.q = PI_Controller"""
new="""  PWMC_GetPhaseCurrents(pwmcHandle[M1], &Iab);

#ifdef G30P
  if(g30_drv126_r1_arm || g30_drv126_r1_active){
    uint32_t r1_c0=*DWT_CYCCNT;
    hCodeError=g30_drv126_r1_step(pwmcHandle[M1],Iab,hElAngle,
                                  FOCVars[M1].Iqdref.q,FOCVars[M1].Iqdref.d);
    uint32_t r1_c=*DWT_CYCCNT-r1_c0;
    g30_drv126_r11_cycles_last=(uint16_t)(r1_c>65535u?65535u:r1_c);
    if(g30_drv126_r11_cycles_last>g30_drv126_r11_cycles_max)
      g30_drv126_r11_cycles_max=g30_drv126_r11_cycles_last;
    FOCVars[M1].Iab=Iab;
    FOCVars[M1].Ialphabeta.alpha=0;FOCVars[M1].Ialphabeta.beta=0;
    FOCVars[M1].Iqd.q=0;FOCVars[M1].Iqd.d=0;
    FOCVars[M1].Vqd.q=0;FOCVars[M1].Vqd.d=0;
    FOCVars[M1].Valphabeta.alpha=0;FOCVars[M1].Valphabeta.beta=0;
    FOCVars[M1].hElAngle=hElAngle;
    return hCodeError;
  }
#endif

  Ialphabeta = MCM_Clarke(Iab);
  Iqd = MCM_Park(Ialphabeta, hElAngle);
  Vqd.q = PI_Controller"""
assert old in s
s=s.replace(old,new,1)

# Update header comment.
s=s.replace("DRV126 MotorCore R1 gated takeover","DRV126 MotorCore R1.1 timing-fixed takeover",1)
p.write_text(s)

p=root/"common_files/src/terminal.c"
s=p.read_text()
s=s.replace("DRV126R1 mode=GATED_4K","DRV126R11 mode=GATED_4K_TIMING",1)
s=s.replace("DRV126R1 command_ok=","DRV126R11 command_ok=",1)
s=s.replace("DRV126R1 guard maxQrefU=1500 maxPhaseU=2500 railRaw=80..3920 div=%u trips=%u hall=%u pwmOff=%u",
            "DRV126R11 guard maxQrefU=1500 maxPhaseU=2500 railRaw=80..3920 div=%u trips=%u hall=%u pwmOff=%u",1)
s=s.replace("DRV126R1 core qrefU=","DRV126R11 core qrefU=",1)
s=s.replace("DRV126R1 PWM sec=","DRV126R11 PWM sec=",1)

# Add timing line with no new formatting state.
needle='        commands_printf(phandle,"DRV126R11 PWM sec=%u ccr=%u,%u,%u",\n            (unsigned)g30_drv126_r1_sec,(unsigned)g30_drv126_r1_c1,\n            (unsigned)g30_drv126_r1_c2,(unsigned)g30_drv126_r1_c3);'
assert needle in s
repl=needle+'''\n        extern volatile uint16_t g30_drv126_r11_cycles_last,g30_drv126_r11_cycles_max;
        commands_printf(phandle,"DRV126R11 timing cycles=%u max=%u budget=4000",
            (unsigned)g30_drv126_r11_cycles_last,(unsigned)g30_drv126_r11_cycles_max);'''
s=s.replace(needle,repl,1)
p.write_text(s)

print("DRV126 R1.1 timing fix applied: 32-bit exact shifts, no duplicate MCSDK transforms, 16k sample commits, cycle telemetry")
