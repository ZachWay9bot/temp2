from pathlib import Path
import re

root=Path("SOURCE_KOXX3")

# Build identity.
p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-MOTORCORE-R1.2-LOADSYM"'
new='#define HW_NAME "SESC-DRV126-MOTORCORE-FINAL-V1"'
assert old in s
p.write_text(s.replace(old,new,1))

# Replace the complete experimental DRV126 block with the production Hall core.
p=root/"common_files/src/mc_tasks.c"
s=p.read_text()
m=re.search(r'static const uint16_t g30_drv126_qtr\[256\]=\{.*?\n\};',s,re.S)
assert m, "DRV126 LUT missing"
qtr=m.group(0)

start=s.index("/* DRV126 MotorCore R1.2 load/symmetry takeover")
end=s.index("\n#endif\n#if MUSIC_ENABLE",start)

block=r'''/* DRV126 MotorCore FINAL V1 -------------------------------------------------
 * Production architecture:
 * - HALL mode: DRV126 current-domain Clarke/Park/PI/invPark/SVPWM owns PWM.
 * - SENSORLESS mode: the frozen SESC/FO76 path below remains untouched.
 * - DRV126 current control cadence = 4 kHz; proven MCSDK carrier/sample
 *   infrastructure remains 16 kHz and is committed on every current ISR.
 *
 * Hardware proof inherited from R0.2/R0.3/R1.1/R1.2:
 * - stock current bridge + Clarke/Park + PI shadow validated,
 * - inverse Park/SVPWM compared against live PWM <=13/2000 counts,
 * - timing takeover clean,
 * - physical FWD and REV rotation clean at 2 A and 3 A.
 *
 * This final block removes all RAM-only arm/test state. The normal configured
 * current, battery-current, field-weakening, Hall, OCP and direction guards
 * remain authoritative.
 */

static int32_t g30_drv126_final_q_acc=0;
static int32_t g30_drv126_final_d_acc=0;
static int16_t g30_drv126_final_vq=0;
static int16_t g30_drv126_final_vd=0;
static uint8_t g30_drv126_final_div=0u;

''' + qtr + r'''

static inline int32_t g30_drv126_final_clamp32(int32_t v,int32_t lo,int32_t hi){
  return v<lo ? lo : (v>hi ? hi : v);
}
static inline int32_t g30_drv126_final_stock_u_from_mc(int16_t counts){
  int32_t p=(int32_t)counts*51575;
  if(p>=0) return p>>14;
  return -(((-p)+16383)>>14);
}
static int16_t g30_drv126_final_pi(int32_t ref,int32_t act,int32_t *acc,
                                   int32_t acc_lim,int32_t out_lim){
  int32_t e=ref-act;
  int32_t pterm=(e*200)/2048;
  *acc=g30_drv126_final_clamp32(*acc+e,-acc_lim,acc_lim);
  int32_t iterm=(*acc*10)/8192;
  int32_t out=pterm+iterm;
  out=g30_drv126_final_clamp32(out,-out_lim,out_lim);
  return (int16_t)out;
}
static void g30_drv126_final_trig(uint16_t angle,int16_t *co,int16_t *si){
  uint16_t q=(uint16_t)((((uint16_t)(angle+0x8000u))>>6)&0x0300u);
  uint8_t i=(uint8_t)((angle>>6)&0xffu);
  uint8_t j=(uint8_t)(0xffu-i);
  int32_t lo=0,hi=0;
  switch(q){
    case 0x000u: hi=-(int32_t)g30_drv126_qtr[i]; lo=-(int32_t)g30_drv126_qtr[j]; break;
    case 0x100u: hi=-(int32_t)g30_drv126_qtr[j]; lo= (int32_t)g30_drv126_qtr[i]; break;
    case 0x200u: hi= (int32_t)g30_drv126_qtr[i]; lo= (int32_t)g30_drv126_qtr[j]; break;
    default:     hi= (int32_t)g30_drv126_qtr[j]; lo=-(int32_t)g30_drv126_qtr[i]; break;
  }
  *co=(int16_t)lo;
  *si=(int16_t)hi;
}
static void g30_drv126_final_park(int32_t alpha,int32_t beta,uint16_t angle,
                                  int32_t *axis0,int32_t *axis1,
                                  int16_t *co_out,int16_t *si_out){
  int16_t co,si;
  g30_drv126_final_trig(angle,&co,&si);
  int32_t c12=((int32_t)co)>>3;
  int32_t s12=((int32_t)si)>>3;
  *axis0=(c12*alpha+s12*beta)>>12;
  *axis1=(s12*alpha-c12*beta)>>12;
  *co_out=co;
  *si_out=si;
}
static inline int32_t g30_drv126_final_asr_floor(int32_t v,uint8_t sh){
  if(v>=0) return v>>sh;
  return -(((-v)+(((int32_t)1<<sh)-1))>>sh);
}
static void g30_drv126_final_invpark(int16_t q,int16_t d,int16_t co,int16_t si,
                                     int16_t *alpha,int16_t *beta){
  int32_t a=(int32_t)co*(int32_t)q+(int32_t)si*(int32_t)d;
  int32_t b=(int32_t)si*(int32_t)q-(int32_t)co*(int32_t)d;
  *alpha=(int16_t)g30_drv126_final_asr_floor(a,15);
  *beta =(int16_t)g30_drv126_final_asr_floor(b,15);
}
static uint8_t g30_drv126_final_svpwm(int16_t alpha,int16_t beta,
                                      uint16_t *c1,uint16_t *c2,uint16_t *c3){
  const int32_t per=4000,lim=3920;
  int32_t t=g30_drv126_final_asr_floor((int32_t)alpha*1774,10);
  int32_t x=g30_drv126_final_asr_floor((int32_t)beta+t,1);
  int32_t y=g30_drv126_final_asr_floor((int32_t)beta-t,1);
  uint8_t sec;
  if(x<0){
    if(y<0) sec=5u;
    else if(beta<=0) sec=4u;
    else sec=3u;
  }else{
    if(y>=0) sec=2u;
    else if(beta<=0) sec=6u;
    else sec=1u;
  }

  int32_t X=g30_drv126_final_asr_floor(x*per,15);
  int32_t Y=g30_drv126_final_asr_floor(y*per,15);
  int32_t B=g30_drv126_final_asr_floor((int32_t)beta*per,15);
  int32_t a=2000,b=2000,c=2000,u,v,den,base;

  switch(sec){
    case 1u:
      u=B;v=-Y;den=B-Y;
      if(den>lim){u=(B*lim)/den;v=((-Y)*lim)/den;}
      base=g30_drv126_final_asr_floor(per-v-u,1);
      c=base;b=base+u;a=b+v;
      break;
    case 2u:
      u=X;v=Y;den=Y+X;
      if(den>lim){v=(Y*lim)/den;u=(X*lim)/den;}
      base=g30_drv126_final_asr_floor(per-u-v,1);
      c=base;a=base+u;b=a+v;
      break;
    case 3u:
      u=B;v=-X;den=B-X;
      if(den>lim){v=((-X)*lim)/den;u=(B*lim)/den;}
      base=g30_drv126_final_asr_floor(per-u-v,1);
      a=base;c=base+v;b=c+u;
      break;
    case 4u:
      u=Y;v=-B;den=Y-B;
      if(den>lim){u=(Y*lim)/den;v=((-B)*lim)/den;}
      base=g30_drv126_final_asr_floor(per-u-v,1);
      a=base;b=base+u;c=b+v;
      break;
    case 5u:
      u=-Y;v=-X;den=(-Y)+(-X);
      if(den>lim){u=((-Y)*lim)/den;v=((-X)*lim)/den;}
      base=g30_drv126_final_asr_floor(per-v-u,1);
      b=base;a=base+u;c=a+v;
      break;
    default:
      u=X;v=-B;den=X-B;
      if(den>lim){v=((-B)*lim)/den;u=(X*lim)/den;}
      base=g30_drv126_final_asr_floor(per-v-u,1);
      b=base;c=base+v;a=c+u;
      break;
  }

  if(a<0)a=0;else if(a>4000)a=4000;
  if(b<0)b=0;else if(b>4000)b=4000;
  if(c<0)c=0;else if(c>4000)c=4000;
  *c1=(uint16_t)a;
  *c2=(uint16_t)b;
  *c3=(uint16_t)c;
  return sec;
}

void g30_drv126_final_reset(void){
  g30_drv126_final_q_acc=0;
  g30_drv126_final_d_acc=0;
  g30_drv126_final_vq=0;
  g30_drv126_final_vd=0;
  g30_drv126_final_div=0u;
}
static int32_t g30_drv126_final_acc_from_voltage(int16_t v,int32_t lim){
  int32_t a=((int32_t)v*8192)/10;
  return g30_drv126_final_clamp32(a,-lim,lim);
}
void g30_drv126_final_preload(int16_t vq,int16_t vd){
  vq=(int16_t)g30_drv126_final_clamp32(vq,-31128,31128);
  vd=(int16_t)g30_drv126_final_clamp32(vd,-10376,10376);
  g30_drv126_final_q_acc=g30_drv126_final_acc_from_voltage(vq,25500057);
  g30_drv126_final_d_acc=g30_drv126_final_acc_from_voltage(vd,8500019);
  g30_drv126_final_vq=vq;
  g30_drv126_final_vd=vd;
  g30_drv126_final_div=0u;
}

static uint16_t g30_drv126_final_hall_step(PWMC_Handle_t *pHdl,ab_t Iab,
                                           int16_t angle,int16_t qref_mc,
                                           int16_t dref_mc){
  /* Cheap live Hall guard on every current ISR. The medium-frequency Hall
   * fault path still owns fault latching/recovery policy. */
  uint8_t raw=HALL_read(&HALL_M1);
  if(pHdl->PWM_off || raw==0u || raw==7u || HALL_M1.lut[raw]==255u ||
     !HALL_M1.SensorIsReliable){
    PWMC_SwitchOffPWM(pHdl);
    return MC_NO_ERROR;
  }

  /* The configured SESC phase-current limits remain authoritative. */
  int32_t pos=(int32_t)SpeednTorqCtrlM1.MaxPositiveTorque;
  int32_t neg=(int32_t)SpeednTorqCtrlM1.MinNegativeTorque;
  if(pos<0)pos=0;
  if(neg>0)neg=0;
  int32_t qmc=g30_drv126_final_clamp32((int32_t)qref_mc,neg,pos);
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

  int32_t ia=g30_drv126_final_stock_u_from_mc(Iab.a);
  int32_t ib=g30_drv126_final_stock_u_from_mc(Iab.b);
  int32_t alpha=ia;
  int32_t beta=((ia+2*ib)*2365)>>12;
  int32_t iq,id;
  int16_t co,si;
  g30_drv126_final_park(alpha,beta,(uint16_t)angle,&iq,&id,&co,&si);

  int32_t qref=g30_drv126_final_stock_u_from_mc((int16_t)qmc);
  int32_t dref=g30_drv126_final_stock_u_from_mc((int16_t)dmc);
  g30_drv126_final_vq=g30_drv126_final_pi(qref,iq,&g30_drv126_final_q_acc,
                                          25500057,31128);
  g30_drv126_final_vd=g30_drv126_final_pi(dref,id,&g30_drv126_final_d_acc,
                                          8500019,10376);

  int16_t va,vb;
  uint16_t r1,r2,r3;
  g30_drv126_final_invpark(g30_drv126_final_vq,g30_drv126_final_vd,
                           co,si,&va,&vb);
  uint8_t sec=g30_drv126_final_svpwm(va,vb,&r1,&r2,&r3);

  /* Exact stock SVPWM range over the complete PI output space is 40..3960
   * of 4000 with <=3920 active span. Scale it onto the proven 2000-count
   * carrier. Keep stock's sector even at tie boundaries instead of injecting
   * the old R1 test neutral vector. */
  uint16_t c1=(uint16_t)((r1+1u)>>1);
  uint16_t c2=(uint16_t)((r2+1u)>>1);
  uint16_t c3=(uint16_t)((r3+1u)>>1);

  pHdl->CntPhA=c1;
  pHdl->CntPhB=c2;
  pHdl->CntPhC=c3;
  pHdl->Sector=(uint8_t)(sec-1u);

  uint16_t lo=c1,hi=c1;
  if(c2>lo)lo=c2;if(c3>lo)lo=c3;
  if(c2<hi)hi=c2;if(c3<hi)hi=c3;
  pHdl->lowDuty=lo;
  pHdl->highDuty=hi;
  pHdl->midDuty=(uint16_t)((uint32_t)c1+(uint32_t)c2+(uint32_t)c3-lo-hi);

  return pHdl->pFctSetADCSampPointSectX(pHdl);
}
'''

s=s[:start]+block+s[end:]
# end slice keeps the #endif that closes G30P.
p.write_text(s)

# Replace experimental armed branch with automatic Hall ownership + full
# FOCVars/FW telemetry so battery current limiting and FW stay functional.
p=root/"common_files/src/mc_tasks.c"
s=p.read_text()
old=r'''#ifdef G30P
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

  Ialphabeta = MCM_Clarke(Iab);'''
new=r'''#ifdef G30P
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

  Ialphabeta = MCM_Clarke(Iab);'''
assert old in s, "R1.2 FOC branch not found"
s=s.replace(old,new,1)

# Reset production DRV state whenever the generic FOC state is cleared.
needle='''  PWMC_SwitchOffPWM(pwmcHandle[bMotor]);
#ifdef G30P
  /* R3I2 preserves an externally seeded sensorless trajectory through the'''
repl='''  PWMC_SwitchOffPWM(pwmcHandle[bMotor]);
#ifdef G30P
  if(bMotor==M1) g30_drv126_final_reset();
  /* R3I2 preserves an externally seeded sensorless trajectory through the'''
assert needle in s
s=s.replace(needle,repl,1)
p.write_text(s)

# Integrate reset/preload into the normal PWM lifecycle. Sensorless behavior is
# deliberately untouched.
p=root/"common_files/src/VescToSTM.c"
s=p.read_text()
s=s.replace('''void VescToSTM_pwm_stop(void){
#ifdef G30P
    g30_hall_trace_freeze(G30_HT_PWM_STOP);
#endif''',
'''void VescToSTM_pwm_stop(void){
#ifdef G30P
    extern void g30_drv126_final_reset(void);
    g30_hall_trace_freeze(G30_HT_PWM_STOP);
#endif''',1)
needle='''#ifdef G30P
	/* Only after MOE/gate outputs are off is it safe to disarm takeover. */
	g30_fo76_request_takeover(0u);
#endif
}'''
repl='''#ifdef G30P
	/* Only after MOE/gate outputs are off is it safe to disarm takeover. */
	g30_fo76_request_takeover(0u);
    g30_drv126_final_reset();
#endif
}'''
assert needle in s
s=s.replace(needle,repl,1)

old='''void VescToSTM_pwm_start(void){
#ifdef G30P
    extern uint8_t g30_drv126_r1_trip_active(void);
    if(g30_drv126_r1_trip_active()) return;
    /* HallDevV0.1: never energize the bridge with an invalid Hall state.'''
new='''void VescToSTM_pwm_start(void){
#ifdef G30P
    extern void g30_drv126_final_reset(void);
    extern void g30_drv126_final_preload(int16_t vq,int16_t vd);
    /* HallDevV0.1: never energize the bridge with an invalid Hall state.'''
assert old in s
s=s.replace(old,new,1)

needle='''    if(PWM_Handle_M1._Super.PWM_off){
#ifdef G30P
        if(VescToSTM_g30_sensorless_selected() && g30_r3i_sensorless_active()){'''
repl='''    if(PWM_Handle_M1._Super.PWM_off){
#ifdef G30P
        g30_drv126_final_reset();
        if(VescToSTM_g30_sensorless_selected() && g30_r3i_sensorless_active()){'''
assert needle in s
s=s.replace(needle,repl,1)

needle='''            PIDIqHandle_M1.wIntegralTerm = fVd * TF_KIDIV;
            PIDIdHandle_M1.wIntegralTerm = -PIDIqHandle_M1.wIntegralTerm/4;
        }
        HALL_M1._Super.hElAngle = HALL_M1.MeasuredElAngle;'''
repl='''            PIDIqHandle_M1.wIntegralTerm = fVd * TF_KIDIV;
            PIDIdHandle_M1.wIntegralTerm = -PIDIqHandle_M1.wIntegralTerm/4;
#ifdef G30P
            if(VescToSTM_g30_hall_selected()){
                int16_t drv_vq=(int16_t)fVd;
                int16_t drv_vd=(int16_t)(-drv_vq/4);
                g30_drv126_final_preload(drv_vq,drv_vd);
            }
#endif
        }
        HALL_M1._Super.hElAngle = HALL_M1.MeasuredElAngle;'''
assert needle in s
s=s.replace(needle,repl,1)
p.write_text(s)

# Remove the experimental arm/shadow terminal surface. g30_status,
# g30_motorpath and Hall diagnostics remain.
p=root/"common_files/src/terminal.c"
s=p.read_text()
start=s.index('    }else if (strcmp(argv[0], "g30_drv126_shadow_reset") == 0){')
end=s.index('    }else if (strcmp(argv[0], "g30_motorpath_reset") == 0){',start)
s=s[:start]+s[end:]
p.write_text(s)

print("SESC DRV126 FINAL V1 applied: automatic Hall owner, 4k/16k timing, full FW/battery telemetry, sensorless untouched")
