from pathlib import Path

root=Path("SOURCE_KOXX3")

p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-SHADOW-R0.2"'
new='#define HW_NAME "SESC-DRV126-SHADOW-R0.3"'
assert old in s
p.write_text(s.replace(old,new,1))

p=root/"common_files/src/mc_tasks.c"
s=p.read_text()
s=s.replace("/* DRV126 Shadow R0.2 -------------------------------------------------------","/* DRV126 Shadow R0.3 -------------------------------------------------------",1)
s=s.replace(
""" * R0.2 keeps the stock Clarke/trig/Park from R0.1 and fixes the remaining
 * bridge errors: one atomic FOC snapshot per 1-kHz tick and the original
 * DRV126 current integer domain. DRV126 uses
""",
""" * R0.3 keeps the proven R0.2 input path and extends the shadow through the
 * original DRV126 inverse Park and six-sector SVPWM. It computes virtual
 * CCR1/2/3 only; it never writes TIM1 or PWMC state.
 *
 * R0.2 already proved an atomic FOC snapshot and the original DRV126 current
 * integer domain. DRV126 uses
""",1)
s=s.replace(
""" *   PI-C    0x20002694: Kp=200/2048 Ki=10/8192 out=+-10376
 * FOC call order proves Park axis0 -> PI-B and axis1 -> PI-C.
""",
""" *   PI-C    0x20002694: Kp=200/2048 Ki=10/8192 out=+-10376
 *   InvPark 0x080054E4: alpha=(q*cos+d*sin)>>15,
 *                       beta=(q*sin-d*cos)>>15
 *   SVPWM   0x08005510: 6 sectors, period=4000, active-span limit=3920,
 *                       CCR1/2/3 output, CCR4=3996 in stock.
 * FOC call order proves Park axis0 -> PI-B and axis1 -> PI-C.
""",1)

anchor="""volatile int16_t g30_drv126_sh_sesc_vq=0;
volatile int16_t g30_drv126_sh_sesc_vd=0;
"""
insert=anchor+"""volatile uint16_t g30_drv126_sh_drv_c1=0,g30_drv126_sh_drv_c2=0,g30_drv126_sh_drv_c3=0;
volatile uint16_t g30_drv126_sh_bridge_c1=0,g30_drv126_sh_bridge_c2=0,g30_drv126_sh_bridge_c3=0;
volatile uint16_t g30_drv126_sh_hw_c1=0,g30_drv126_sh_hw_c2=0,g30_drv126_sh_hw_c3=0;
volatile uint16_t g30_drv126_sh_order_mismatch=0,g30_drv126_sh_ccr_err_max=0;
volatile uint8_t g30_drv126_sh_drv_sec=0,g30_drv126_sh_bridge_sec=0,g30_drv126_sh_hw_sec=0;
"""
assert anchor in s
s=s.replace(anchor,insert,1)

# Extend atomic snapshot with actual SESC PWM outputs.
old="""typedef struct {
  int16_t ia,ib,alpha,beta,iq,id,iqref,idref,angle,vq,vd;
  uint8_t pwm_off;
} g30_drv126_snapshot_t;
"""
new="""typedef struct {
  int16_t ia,ib,alpha,beta,iq,id,iqref,idref,angle,vq,vd;
  uint16_t c1,c2,c3;
  uint8_t pwm_off,sector;
} g30_drv126_snapshot_t;
"""
assert old in s
s=s.replace(old,new,1)

old="""  o->angle=FOCVars[M1].hElAngle; o->vq=FOCVars[M1].Vqd.q; o->vd=FOCVars[M1].Vqd.d;
  o->pwm_off=PWM_Handle_M1._Super.PWM_off;
"""
new="""  o->angle=FOCVars[M1].hElAngle; o->vq=FOCVars[M1].Vqd.q; o->vd=FOCVars[M1].Vqd.d;
  o->c1=PWM_Handle_M1._Super.CntPhA; o->c2=PWM_Handle_M1._Super.CntPhB;
  o->c3=PWM_Handle_M1._Super.CntPhC;
  o->pwm_off=PWM_Handle_M1._Super.PWM_off;
  o->sector=(uint8_t)(PWM_Handle_M1._Super.Sector+1u);
"""
assert old in s
s=s.replace(old,new,1)

# Add exact output transform/SVPWM helpers immediately after stock Park.
park_end="""  *axis0=(c12*alpha+s12*beta)>>12;
  *axis1=(s12*alpha-c12*beta)>>12;
}
"""
helpers=park_end+r'''
static int32_t g30_drv126_asr_floor(int32_t v,uint8_t s){
  if(v>=0) return v>>s;
  return -(int32_t)(((int64_t)(-v)+(((int64_t)1<<s)-1))>>s);
}
static void g30_drv126_stock_invpark(int16_t q,int16_t d,int16_t co,int16_t si,
                                     int16_t *alpha,int16_t *beta){
  int32_t a=(int32_t)co*(int32_t)q+(int32_t)si*(int32_t)d;
  int32_t b=(int32_t)si*(int32_t)q-(int32_t)co*(int32_t)d;
  *alpha=(int16_t)g30_drv126_asr_floor(a,15);
  *beta =(int16_t)g30_drv126_asr_floor(b,15);
}
static uint8_t g30_drv126_stock_svpwm(int16_t alpha,int16_t beta,
                                      uint16_t *c1,uint16_t *c2,uint16_t *c3){
  /* Opcode-equivalent reconstruction of DRV126 @0x08005510.
   * Carrier period 4000. Overmodulation normalizes active span to 3920. */
  const int32_t per=4000,lim=3920;
  int32_t t=g30_drv126_asr_floor((int32_t)alpha*1774,10);
  int32_t x=g30_drv126_asr_floor((int32_t)beta+t,1);
  int32_t y=g30_drv126_asr_floor((int32_t)beta-t,1);
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

  int32_t X=g30_drv126_asr_floor(x*per,15);
  int32_t Y=g30_drv126_asr_floor(y*per,15);
  int32_t B=g30_drv126_asr_floor((int32_t)beta*per,15);
  int32_t a=2000,b=2000,c=2000,u,v,den,base;

  switch(sec){
    case 1u:
      u=B; v=-Y; den=B-Y;
      if(den>lim){u=(B*lim)/den;v=((-Y)*lim)/den;}
      base=g30_drv126_asr_floor(per-v-u,1);
      c=base;b=base+u;a=b+v;
      break;
    case 2u:
      u=X; v=Y; den=Y+X;
      if(den>lim){v=(Y*lim)/den;u=(X*lim)/den;}
      base=g30_drv126_asr_floor(per-u-v,1);
      c=base;a=base+u;b=a+v;
      break;
    case 3u:
      u=B; v=-X; den=B-X;
      if(den>lim){v=((-X)*lim)/den;u=(B*lim)/den;}
      base=g30_drv126_asr_floor(per-u-v,1);
      a=base;c=base+v;b=c+u;
      break;
    case 4u:
      u=Y; v=-B; den=Y-B;
      if(den>lim){u=(Y*lim)/den;v=((-B)*lim)/den;}
      base=g30_drv126_asr_floor(per-u-v,1);
      a=base;b=base+u;c=b+v;
      break;
    case 5u:
      u=-Y; v=-X; den=(-Y)+(-X);
      if(den>lim){u=((-Y)*lim)/den;v=((-X)*lim)/den;}
      base=g30_drv126_asr_floor(per-v-u,1);
      b=base;a=base+u;c=a+v;
      break;
    default: /* sector 6 */
      u=X; v=-B; den=X-B;
      if(den>lim){v=((-B)*lim)/den;u=(X*lim)/den;}
      base=g30_drv126_asr_floor(per-v-u,1);
      b=base;c=base+v;a=c+u;
      break;
  }

  if(a<0)a=0;else if(a>4000)a=4000;
  if(b<0)b=0;else if(b>4000)b=4000;
  if(c<0)c=0;else if(c>4000)c=4000;
  *c1=(uint16_t)a;*c2=(uint16_t)b;*c3=(uint16_t)c;
  return sec;
}
static uint8_t g30_drv126_order3(uint16_t a,uint16_t b,uint16_t c){
  /* Sector boundaries intentionally produce equal compare values. Those
   * samples have no unique phase ordering and must not count as mismatch. */
  if(a==b || b==c || a==c) return 0u;
  if(a>b && b>c) return 1u;
  if(b>a && a>c) return 2u;
  if(b>c && c>a) return 3u;
  if(c>b && b>a) return 4u;
  if(c>a && a>b) return 5u;
  return 6u;
}
'''
assert park_end in s
s=s.replace(park_end,helpers,1)

# Reset new diagnostics.
old="""  g30_drv126_sh_sesc_vq=0;g30_drv126_sh_sesc_vd=0;
  g30_drv126_sh_q_acc=0;g30_drv126_sh_d_acc=0;
"""
new="""  g30_drv126_sh_sesc_vq=0;g30_drv126_sh_sesc_vd=0;
  g30_drv126_sh_drv_c1=0;g30_drv126_sh_drv_c2=0;g30_drv126_sh_drv_c3=0;
  g30_drv126_sh_bridge_c1=0;g30_drv126_sh_bridge_c2=0;g30_drv126_sh_bridge_c3=0;
  g30_drv126_sh_hw_c1=0;g30_drv126_sh_hw_c2=0;g30_drv126_sh_hw_c3=0;
  g30_drv126_sh_order_mismatch=0;g30_drv126_sh_ccr_err_max=0;
  g30_drv126_sh_drv_sec=0;g30_drv126_sh_bridge_sec=0;g30_drv126_sh_hw_sec=0;
  g30_drv126_sh_q_acc=0;g30_drv126_sh_d_acc=0;
"""
assert old in s
s=s.replace(old,new,1)

# Add virtual output computation after the four PI substeps.
needle="""  for(unsigned n=0;n<4u;n++){
    g30_drv126_sh_vq=g30_drv126_sh_pi(qref,axis0,&g30_drv126_sh_q_acc,
                                       25500057,31128,&g30_drv126_sh_sat_q);
    g30_drv126_sh_vd=g30_drv126_sh_pi(dref,axis1,&g30_drv126_sh_d_acc,
                                       8500019,10376,&g30_drv126_sh_sat_d);
  }
  if(g30_drv126_sh_samples<65535u)g30_drv126_sh_samples++;
"""
repl=needle.replace("  if(g30_drv126_sh_samples<65535u)g30_drv126_sh_samples++;",r'''  int16_t da,db,ba,bb;
  g30_drv126_stock_invpark(g30_drv126_sh_vq,g30_drv126_sh_vd,
                           g30_drv126_sh_cos,g30_drv126_sh_sin,&da,&db);
  g30_drv126_sh_drv_sec=g30_drv126_stock_svpwm(da,db,
      (uint16_t*)&g30_drv126_sh_drv_c1,(uint16_t*)&g30_drv126_sh_drv_c2,
      (uint16_t*)&g30_drv126_sh_drv_c3);

  /* Bridge-only comparator: feed the exact same SESC Vq/Vd snapshot through
   * the stock inverse Park/SVPWM. This removes PI dynamics from the PWM math
   * comparison. No result from either path is written to hardware. */
  g30_drv126_stock_invpark(x.vq,x.vd,g30_drv126_sh_cos,g30_drv126_sh_sin,&ba,&bb);
  g30_drv126_sh_bridge_sec=g30_drv126_stock_svpwm(ba,bb,
      (uint16_t*)&g30_drv126_sh_bridge_c1,(uint16_t*)&g30_drv126_sh_bridge_c2,
      (uint16_t*)&g30_drv126_sh_bridge_c3);
  g30_drv126_sh_hw_c1=x.c1;g30_drv126_sh_hw_c2=x.c2;g30_drv126_sh_hw_c3=x.c3;
  g30_drv126_sh_hw_sec=x.sector;

  uint8_t bo=g30_drv126_order3(g30_drv126_sh_bridge_c1,g30_drv126_sh_bridge_c2,
                               g30_drv126_sh_bridge_c3);
  uint8_t ho=g30_drv126_order3(x.c1,x.c2,x.c3);
  if(bo!=0u && ho!=0u && bo!=ho && g30_drv126_sh_order_mismatch<65535u)g30_drv126_sh_order_mismatch++;

  uint16_t b1=(uint16_t)((g30_drv126_sh_bridge_c1+1u)>>1);
  uint16_t b2=(uint16_t)((g30_drv126_sh_bridge_c2+1u)>>1);
  uint16_t b3=(uint16_t)((g30_drv126_sh_bridge_c3+1u)>>1);
  uint16_t e1=(b1>x.c1)?(uint16_t)(b1-x.c1):(uint16_t)(x.c1-b1);
  uint16_t e2=(b2>x.c2)?(uint16_t)(b2-x.c2):(uint16_t)(x.c2-b2);
  uint16_t e3=(b3>x.c3)?(uint16_t)(b3-x.c3):(uint16_t)(x.c3-b3);
  uint16_t em=e1;if(e2>em)em=e2;if(e3>em)em=e3;
  if(em>g30_drv126_sh_ccr_err_max)g30_drv126_sh_ccr_err_max=em;

  if(g30_drv126_sh_samples<65535u)g30_drv126_sh_samples++;''')
assert needle in s
s=s.replace(needle,repl,1)
p.write_text(s)

p=root/"common_files/src/terminal.c"
s=p.read_text()
s=s.replace("DRV126SH02 RESET","DRV126SH03 RESET")
s=s.replace("DRV126SH02 unavailable","DRV126SH03 unavailable")
# Add externs before output.
anchor="""        extern volatile int16_t g30_drv126_sh_sesc_vq,g30_drv126_sh_sesc_vd;
"""
insert=anchor+"""        extern volatile uint16_t g30_drv126_sh_drv_c1,g30_drv126_sh_drv_c2,g30_drv126_sh_drv_c3;
        extern volatile uint16_t g30_drv126_sh_bridge_c1,g30_drv126_sh_bridge_c2,g30_drv126_sh_bridge_c3;
        extern volatile uint16_t g30_drv126_sh_hw_c1,g30_drv126_sh_hw_c2,g30_drv126_sh_hw_c3;
        extern volatile uint16_t g30_drv126_sh_order_mismatch,g30_drv126_sh_ccr_err_max;
        extern volatile uint8_t g30_drv126_sh_drv_sec,g30_drv126_sh_bridge_sec,g30_drv126_sh_hw_sec;
"""
assert anchor in s
s=s.replace(anchor,insert,1)

s=s.replace(
"""commands_printf(phandle,"DRV126SH02 mode=STOCK_DOMAIN_ATOMIC owner=SESC_HALL writes=0 samples=%u",
            (unsigned)g30_drv126_sh_samples);""",
"""commands_printf(phandle,"DRV126SH03 mode=FULL_STOCK_SHADOW owner=SESC_HALL writes=0 samples=%u",
            (unsigned)g30_drv126_sh_samples);""",1)
s=s.replace("DRV126SH02 bridge scale=51575/16384 snapshot=atomic","DRV126SH03 bridge scale=51575/16384 snapshot=atomic",1)
s=s.replace("DRV126SH02 PI qB=%d satQ=%u dC=%d satD=%u SESCsnap=%d,%d","DRV126SH03 PI qB=%d satQ=%u dC=%d satD=%u SESCsnap=%d,%d",1)

needle="""        commands_printf(phandle,"DRV126SH03 PI qB=%d satQ=%u dC=%d satD=%u SESCsnap=%d,%d",
            (int)g30_drv126_sh_vq,(unsigned)g30_drv126_sh_sat_q,
            (int)g30_drv126_sh_vd,(unsigned)g30_drv126_sh_sat_d,
            (int)g30_drv126_sh_sesc_vq,(int)g30_drv126_sh_sesc_vd);
"""
extra=needle+"""        commands_printf(phandle,"DRV126SH03 PWM drv sec=%u ccr=%u,%u,%u bridge sec=%u ccr=%u,%u,%u hw sec=%u ccr=%u,%u,%u orderMis=%u ccrErrMax=%u",
            (unsigned)g30_drv126_sh_drv_sec,
            (unsigned)g30_drv126_sh_drv_c1,(unsigned)g30_drv126_sh_drv_c2,(unsigned)g30_drv126_sh_drv_c3,
            (unsigned)g30_drv126_sh_bridge_sec,
            (unsigned)g30_drv126_sh_bridge_c1,(unsigned)g30_drv126_sh_bridge_c2,(unsigned)g30_drv126_sh_bridge_c3,
            (unsigned)g30_drv126_sh_hw_sec,
            (unsigned)g30_drv126_sh_hw_c1,(unsigned)g30_drv126_sh_hw_c2,(unsigned)g30_drv126_sh_hw_c3,
            (unsigned)g30_drv126_sh_order_mismatch,(unsigned)g30_drv126_sh_ccr_err_max);
"""
assert needle in s
s=s.replace(needle,extra,1)
p.write_text(s)

print("SESC DRV126 Shadow R0.3 applied: stock inverse Park + stock SVPWM virtual CCRs, writes=0")
