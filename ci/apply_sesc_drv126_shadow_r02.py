from pathlib import Path

root=Path("SOURCE_KOXX3")

p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-SHADOW-R0.1"'
new='#define HW_NAME "SESC-DRV126-SHADOW-R0.2"'
assert old in s
p.write_text(s.replace(old,new,1))

p=root/"common_files/src/mc_tasks.c"
s=p.read_text()
s=s.replace("/* DRV126 Shadow R0.1 -------------------------------------------------------","/* DRV126 Shadow R0.2 -------------------------------------------------------",1)
s=s.replace(" * R0.1 removes the invalid mixed-coordinate adapter from R0. DRV126 uses\n",
""" * R0.2 keeps the stock Clarke/trig/Park from R0.1 and fixes the remaining
 * bridge errors: one atomic FOC snapshot per 1-kHz tick and the original
 * DRV126 current integer domain. DRV126 uses
""",1)
s=s.replace(" * FOC call order proves Park axis0 -> PI-B and axis1 -> PI-C.\n",
""" * FOC call order proves Park axis0 -> PI-B and axis1 -> PI-C.
 * Current-domain bridge proof:
 *   MCSDK injected ADC is left aligned; R3_2 current counts correspond to
 *   16 counts per original 12-bit ADC delta on this G30 path. Stock DRV126
 *   applies signed (adc_delta * 51575) ASR 10. Therefore the equivalent
 *   bridge from an MCSDK current count is signed floor(count*51575/16384).
""",1)

s=s.replace("""volatile int16_t g30_drv126_sh_qref_ma=0;
volatile int16_t g30_drv126_sh_iq_ma=0;
volatile int16_t g30_drv126_sh_id_ma=0;
""","""volatile int16_t g30_drv126_sh_qref_u=0;
volatile int16_t g30_drv126_sh_iq_u=0;
volatile int16_t g30_drv126_sh_id_u=0;
""",1)
s=s.replace("""volatile int16_t g30_drv126_sh_cos=0;
volatile int16_t g30_drv126_sh_sin=0;
""","""volatile int16_t g30_drv126_sh_cos=0;
volatile int16_t g30_drv126_sh_sin=0;
volatile int16_t g30_drv126_sh_sesc_vq=0;
volatile int16_t g30_drv126_sh_sesc_vd=0;
""",1)

old="""static int16_t g30_drv126_sh_ma_from_mc(int16_t counts){
  int32_t v=((int32_t)counts*2669)/1000;
  return (int16_t)g30_drv126_sh_clamp32(v,-32767,32767);
}
"""
new="""static int32_t g30_drv126_sh_stock_u_from_mc(int16_t counts){
  /* Exact bridge into the DRV126 internal current integer domain.
   * MCSDK count = 16 * original 12-bit ADC delta on this configured G30 path.
   * DRV126: signed MUL 51575 then ASRS #10. Combined denominator = 16384.
   * Spell out floor-for-negative so the host test and ARM ASR agree. */
  int64_t p=(int64_t)counts*51575LL;
  if(p>=0) return (int32_t)(p/16384LL);
  return (int32_t)(-((-p+16383LL)/16384LL));
}
typedef struct {
  int16_t ia,ib,alpha,beta,iq,id,iqref,idref,angle,vq,vd;
  uint8_t pwm_off;
} g30_drv126_snapshot_t;
static void g30_drv126_snapshot(g30_drv126_snapshot_t *o){
  /* Medium task can be pre-empted by the 16-kHz FOC ISR. Copy the small
   * comparison set under PRIMASK and restore the previous IRQ mask exactly. */
  uint32_t pm=__get_PRIMASK();
  __disable_irq();
  o->ia=FOCVars[M1].Iab.a; o->ib=FOCVars[M1].Iab.b;
  o->alpha=FOCVars[M1].Ialphabeta.alpha; o->beta=FOCVars[M1].Ialphabeta.beta;
  o->iq=FOCVars[M1].Iqd.q; o->id=FOCVars[M1].Iqd.d;
  o->iqref=FOCVars[M1].Iqdref.q; o->idref=FOCVars[M1].Iqdref.d;
  o->angle=FOCVars[M1].hElAngle; o->vq=FOCVars[M1].Vqd.q; o->vd=FOCVars[M1].Vqd.d;
  o->pwm_off=PWM_Handle_M1._Super.PWM_off;
  __set_PRIMASK(pm);
}
"""
assert old in s
s=s.replace(old,new,1)

s=s.replace("""  g30_drv126_sh_qref_ma=0;g30_drv126_sh_iq_ma=0;g30_drv126_sh_id_ma=0;
  g30_drv126_sh_vq=0;g30_drv126_sh_vd=0;g30_drv126_sh_cos=0;g30_drv126_sh_sin=0;
""","""  g30_drv126_sh_qref_u=0;g30_drv126_sh_iq_u=0;g30_drv126_sh_id_u=0;
  g30_drv126_sh_vq=0;g30_drv126_sh_vd=0;g30_drv126_sh_cos=0;g30_drv126_sh_sin=0;
  g30_drv126_sh_sesc_vq=0;g30_drv126_sh_sesc_vd=0;
""",1)

start=s.index("static void g30_drv126_shadow_tick_1k(void){")
end=s.index("\n}\n#endif\n#if MUSIC_ENABLE",start)+2
new_tick="""static void g30_drv126_shadow_tick_1k(void){
  g30_drv126_snapshot_t x;
  g30_drv126_snapshot(&x);
  if(!VescToSTM_g30_hall_selected() || x.pwm_off || STM_GetState(&STM[M1])!=RUN){
    g30_drv126_sh_q_acc=0;g30_drv126_sh_d_acc=0;
    g30_drv126_sh_qref_u=0;g30_drv126_sh_iq_u=0;g30_drv126_sh_id_u=0;
    g30_drv126_sh_vq=0;g30_drv126_sh_vd=0;
    g30_drv126_sh_sesc_vq=x.vq;g30_drv126_sh_sesc_vd=x.vd;
    return;
  }

  /* Translate the coherent MCSDK phase-current sample into the original
   * DRV126 integer current domain, then run the stock transforms. */
  int32_t ia=g30_drv126_sh_stock_u_from_mc(x.ia);
  int32_t ib=g30_drv126_sh_stock_u_from_mc(x.ib);
  int32_t sh_a=ia;
  int32_t sh_b=((ia+2*ib)*2365)>>12;

  int32_t sesc_a=g30_drv126_sh_stock_u_from_mc(x.alpha);
  int32_t sesc_b=g30_drv126_sh_stock_u_from_mc(x.beta);
  int32_t da=g30_drv126_sh_abs32(sh_a-sesc_a);
  int32_t db=g30_drv126_sh_abs32(sh_b+sesc_b);
  int32_t dm=da>db?da:db;
  if(dm>65535)dm=65535;
  if((uint16_t)dm>g30_drv126_sh_clarke_max)g30_drv126_sh_clarke_max=(uint16_t)dm;

  int32_t axis0,axis1;
  g30_drv126_stock_park(sh_a,sh_b,(uint16_t)x.angle,&axis0,&axis1);

  int32_t sesc_q=g30_drv126_sh_stock_u_from_mc(x.iq);
  int32_t sesc_d=g30_drv126_sh_stock_u_from_mc(x.id);
  int32_t dq=g30_drv126_sh_abs32(axis0-sesc_q);
  int32_t dd=g30_drv126_sh_abs32(axis1-sesc_d);
  dm=dq>dd?dq:dd;if(dm>65535)dm=65535;
  if((uint16_t)dm>g30_drv126_sh_dq_max)g30_drv126_sh_dq_max=(uint16_t)dm;

  int32_t qref=g30_drv126_sh_stock_u_from_mc(x.iqref);
  int32_t dref=g30_drv126_sh_stock_u_from_mc(x.idref);
  g30_drv126_sh_qref_u=(int16_t)g30_drv126_sh_clamp32(qref,-32767,32767);
  g30_drv126_sh_iq_u=(int16_t)g30_drv126_sh_clamp32(axis0,-32767,32767);
  g30_drv126_sh_id_u=(int16_t)g30_drv126_sh_clamp32(axis1,-32767,32767);
  g30_drv126_sh_sesc_vq=x.vq;g30_drv126_sh_sesc_vd=x.vd;

  for(unsigned n=0;n<4u;n++){
    g30_drv126_sh_vq=g30_drv126_sh_pi(qref,axis0,&g30_drv126_sh_q_acc,
                                       25500057,31128,&g30_drv126_sh_sat_q);
    g30_drv126_sh_vd=g30_drv126_sh_pi(dref,axis1,&g30_drv126_sh_d_acc,
                                       8500019,10376,&g30_drv126_sh_sat_d);
  }
  if(g30_drv126_sh_samples<65535u)g30_drv126_sh_samples++;
}"""
s=s[:start]+new_tick+s[end:]
p.write_text(s)

p=root/"common_files/src/terminal.c"
s=p.read_text()
s=s.replace("DRV126SH01 RESET","DRV126SH02 RESET")
s=s.replace("DRV126SH01 unavailable","DRV126SH02 unavailable")
s=s.replace("extern volatile int16_t g30_drv126_sh_qref_ma,g30_drv126_sh_iq_ma,g30_drv126_sh_id_ma;","extern volatile int16_t g30_drv126_sh_qref_u,g30_drv126_sh_iq_u,g30_drv126_sh_id_u;",1)
s=s.replace("extern volatile int16_t g30_drv126_sh_vq,g30_drv126_sh_vd,g30_drv126_sh_cos,g30_drv126_sh_sin;","extern volatile int16_t g30_drv126_sh_vq,g30_drv126_sh_vd,g30_drv126_sh_cos,g30_drv126_sh_sin;\n        extern volatile int16_t g30_drv126_sh_sesc_vq,g30_drv126_sh_sesc_vd;",1)
s=s.replace("""commands_printf(phandle,"DRV126SH01 mode=STOCK_CLARKE_TRIG_PARK owner=SESC_HALL writes=0 samples=%u",
            (unsigned)g30_drv126_sh_samples);
        commands_printf(phandle,"DRV126SH01 bridge clarkeMax=%u parkMax=%u qref=%dmA iq=%dmA id=%dmA trig=%d,%d",
            (unsigned)g30_drv126_sh_clarke_max,(unsigned)g30_drv126_sh_dq_max,
            (int)g30_drv126_sh_qref_ma,(int)g30_drv126_sh_iq_ma,(int)g30_drv126_sh_id_ma,
            (int)g30_drv126_sh_cos,(int)g30_drv126_sh_sin);
        commands_printf(phandle,"DRV126SH01 PI qB=%d satQ=%u dC=%d satD=%u SESC=%d,%d",
            (int)g30_drv126_sh_vq,(unsigned)g30_drv126_sh_sat_q,
            (int)g30_drv126_sh_vd,(unsigned)g30_drv126_sh_sat_d,
            (int)FOCVars[M1].Vqd.q,(int)FOCVars[M1].Vqd.d);""",
"""commands_printf(phandle,"DRV126SH02 mode=STOCK_DOMAIN_ATOMIC owner=SESC_HALL writes=0 samples=%u",
            (unsigned)g30_drv126_sh_samples);
        commands_printf(phandle,"DRV126SH02 bridge scale=51575/16384 snapshot=atomic clarkeMax=%u parkMax=%u qrefU=%d iqU=%d idU=%d trig=%d,%d",
            (unsigned)g30_drv126_sh_clarke_max,(unsigned)g30_drv126_sh_dq_max,
            (int)g30_drv126_sh_qref_u,(int)g30_drv126_sh_iq_u,(int)g30_drv126_sh_id_u,
            (int)g30_drv126_sh_cos,(int)g30_drv126_sh_sin);
        commands_printf(phandle,"DRV126SH02 PI qB=%d satQ=%u dC=%d satD=%u SESCsnap=%d,%d",
            (int)g30_drv126_sh_vq,(unsigned)g30_drv126_sh_sat_q,
            (int)g30_drv126_sh_vd,(unsigned)g30_drv126_sh_sat_d,
            (int)g30_drv126_sh_sesc_vq,(int)g30_drv126_sh_sesc_vd);""",1)
p.write_text(s)

print("SESC DRV126 Shadow R0.2 applied: atomic FOC snapshot + stock current domain, writes=0")
