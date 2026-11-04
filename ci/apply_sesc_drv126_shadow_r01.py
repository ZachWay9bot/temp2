from pathlib import Path

root=Path("SOURCE_KOXX3")

p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-SHADOW-R0"'
new='#define HW_NAME "SESC-DRV126-SHADOW-R0.1"'
assert old in s
p.write_text(s.replace(old,new))

p=root/"common_files/src/mc_tasks.c"
s=p.read_text()
start=s.index("/* DRV126 Shadow R0 ---------------------------------------------------------")
end=s.index("#endif\n#if MUSIC_ENABLE", start)
table="""0,201,402,603,804,1005,1206,1407,1608,1809,2009,2210,2410,2611,2811,3012,3212,3412,3612,3811,4011,4210,4410,4609,4808,5007,5205,5404,5602,5800,5998,6195,6393,6590,6786,6983,7179,7375,7571,7767,7962,8157,8351,8545,8739,8933,9126,9319,9512,9704,9896,10087,10278,10469,10659,10849,11039,11228,11417,11605,11793,11980,12167,12353,12539,12725,12910,13094,13279,13462,13645,13828,14010,14191,14372,14553,14732,14912,15090,15269,15446,15623,15800,15976,16151,16325,16499,16673,16846,17018,17189,17360,17530,17700,17869,18037,18204,18371,18537,18703,18868,19032,19195,19357,19519,19680,19841,20000,20159,20317,20475,20631,20787,20942,21096,21250,21403,21554,21705,21856,22005,22154,22301,22448,22594,22739,22884,23027,23170,23311,23452,23592,23731,23870,24007,24143,24279,24413,24547,24680,24811,24942,25072,25201,25329,25456,25582,25708,25832,25955,26077,26198,26319,26438,26556,26674,26790,26905,27019,27133,27245,27356,27466,27575,27683,27790,27896,28001,28105,28208,28310,28411,28510,28609,28706,28803,28898,28992,29085,29177,29268,29358,29447,29534,29621,29706,29791,29874,29956,30037,30117,30195,30273,30349,30424,30498,30571,30643,30714,30783,30852,30919,30985,31050,31113,31176,31237,31297,31356,31414,31470,31526,31580,31633,31685,31736,31785,31833,31880,31926,31971,32014,32057,32098,32137,32176,32213,32250,32285,32318,32351,32382,32412,32441,32469,32495,32521,32545,32567,32589,32609,32628,32646,32663,32678,32692,32705,32717,32728,32737,32745,32752,32757,32761,32765,32766"""

insert=f'''/* DRV126 Shadow R0.1 -------------------------------------------------------
 * Diagnostic only. No TIM1/ADC/GPIO/PWM ownership.
 *
 * R0.1 removes the invalid mixed-coordinate adapter from R0. DRV126 uses
 * Ibeta=+(Ia+2*Ib)/sqrt(3), while MCSDK uses the opposite beta sign. The
 * original DRV126 Park matrix compensates that sign and maps directly onto
 * the SESC q/d convention when the same physical Ia/Ib and angle are used.
 *
 * Stock binary anchors:
 *   Clarke 0x08002828: 2365/4096
 *   trig    0x0800340C: 256x quarter-wave LUT @ 0x08008292
 *   Park    0x080049F0
 *   PI-B    0x20002668: Kp=200/2048 Ki=10/8192 out=+-31128
 *   PI-C    0x20002694: Kp=200/2048 Ki=10/8192 out=+-10376
 * FOC call order proves Park axis0 -> PI-B and axis1 -> PI-C.
 */
volatile uint16_t g30_drv126_sh_samples=0u;
volatile uint16_t g30_drv126_sh_clarke_max=0u;
volatile uint16_t g30_drv126_sh_dq_max=0u;
volatile uint16_t g30_drv126_sh_sat_q=0u;
volatile uint16_t g30_drv126_sh_sat_d=0u;
volatile int16_t g30_drv126_sh_qref_ma=0;
volatile int16_t g30_drv126_sh_iq_ma=0;
volatile int16_t g30_drv126_sh_id_ma=0;
volatile int16_t g30_drv126_sh_vq=0;
volatile int16_t g30_drv126_sh_vd=0;
volatile int16_t g30_drv126_sh_cos=0;
volatile int16_t g30_drv126_sh_sin=0;

static int32_t g30_drv126_sh_q_acc=0;
static int32_t g30_drv126_sh_d_acc=0;

static const uint16_t g30_drv126_qtr[256]={{
{table}
}};

static int32_t g30_drv126_sh_abs32(int32_t v){{ return v<0 ? -v : v; }}
static int32_t g30_drv126_sh_clamp32(int32_t v,int32_t lo,int32_t hi){{
  return v<lo ? lo : (v>hi ? hi : v);
}}
static int16_t g30_drv126_sh_ma_from_mc(int16_t counts){{
  int32_t v=((int32_t)counts*2669)/1000;
  return (int16_t)g30_drv126_sh_clamp32(v,-32767,32767);
}}
static int16_t g30_drv126_sh_pi(int32_t ref,int32_t act,int32_t *acc,
                                int32_t acc_lim,int32_t out_lim,uint16_t *sat){{
  int32_t e=ref-act;
  int32_t pterm=(e*200)/2048;
  *acc=g30_drv126_sh_clamp32(*acc+e,-acc_lim,acc_lim);
  int32_t iterm=(*acc*10)/8192;
  int32_t out=pterm+iterm;
  if(out>out_lim){{out=out_lim;if(*sat<65535u)(*sat)++;}}
  else if(out<-out_lim){{out=-out_lim;if(*sat<65535u)(*sat)++;}}
  return (int16_t)out;
}}
static void g30_drv126_stock_trig(uint16_t angle,int16_t *co,int16_t *si){{
  uint16_t q=(uint16_t)((((uint16_t)(angle+0x8000u))>>6)&0x0300u);
  uint8_t i=(uint8_t)((angle>>6)&0xffu);
  uint8_t j=(uint8_t)(0xffu-i);
  int32_t lo=0,hi=0;
  switch(q){{
    case 0x000u: hi=-(int32_t)g30_drv126_qtr[i]; lo=-(int32_t)g30_drv126_qtr[j]; break;
    case 0x100u: hi=-(int32_t)g30_drv126_qtr[j]; lo= (int32_t)g30_drv126_qtr[i]; break;
    case 0x200u: hi= (int32_t)g30_drv126_qtr[i]; lo= (int32_t)g30_drv126_qtr[j]; break;
    default:     hi= (int32_t)g30_drv126_qtr[j]; lo=-(int32_t)g30_drv126_qtr[i]; break;
  }}
  *co=(int16_t)lo; *si=(int16_t)hi;
}}
static void g30_drv126_stock_park(int32_t alpha,int32_t beta,uint16_t angle,
                                  int32_t *axis0,int32_t *axis1){{
  int16_t co,si; g30_drv126_stock_trig(angle,&co,&si);
  g30_drv126_sh_cos=co; g30_drv126_sh_sin=si;
  int32_t c12=((int32_t)co)>>3;
  int32_t s12=((int32_t)si)>>3;
  *axis0=(c12*alpha+s12*beta)>>12;
  *axis1=(s12*alpha-c12*beta)>>12;
}}
void g30_drv126_shadow_reset(void){{
  g30_drv126_sh_samples=0u;g30_drv126_sh_clarke_max=0u;g30_drv126_sh_dq_max=0u;
  g30_drv126_sh_sat_q=0u;g30_drv126_sh_sat_d=0u;
  g30_drv126_sh_qref_ma=0;g30_drv126_sh_iq_ma=0;g30_drv126_sh_id_ma=0;
  g30_drv126_sh_vq=0;g30_drv126_sh_vd=0;g30_drv126_sh_cos=0;g30_drv126_sh_sin=0;
  g30_drv126_sh_q_acc=0;g30_drv126_sh_d_acc=0;
}}
static void g30_drv126_shadow_tick_1k(void){{
  if(!VescToSTM_g30_hall_selected() || PWM_Handle_M1._Super.PWM_off ||
     STM_GetState(&STM[M1])!=RUN){{
    g30_drv126_sh_q_acc=0;g30_drv126_sh_d_acc=0;
    g30_drv126_sh_qref_ma=0;g30_drv126_sh_iq_ma=0;g30_drv126_sh_id_ma=0;
    g30_drv126_sh_vq=0;g30_drv126_sh_vd=0;
    return;
  }}

  /* Convert the already hardware-validated SESC phase-current sample into the
   * nominal mA domain, then execute the original DRV126 Clarke sign convention. */
  int32_t ia=g30_drv126_sh_ma_from_mc(FOCVars[M1].Iab.a);
  int32_t ib=g30_drv126_sh_ma_from_mc(FOCVars[M1].Iab.b);
  int32_t sh_a=ia;
  int32_t sh_b=((ia+2*ib)*2365)>>12;

  int32_t sesc_a=g30_drv126_sh_ma_from_mc(FOCVars[M1].Ialphabeta.alpha);
  int32_t sesc_b=g30_drv126_sh_ma_from_mc(FOCVars[M1].Ialphabeta.beta);
  int32_t da=g30_drv126_sh_abs32(sh_a-sesc_a);
  int32_t db=g30_drv126_sh_abs32(sh_b+sesc_b); /* beta conventions are opposite */
  int32_t dm=da>db?da:db;
  if(dm>65535)dm=65535;
  if((uint16_t)dm>g30_drv126_sh_clarke_max)g30_drv126_sh_clarke_max=(uint16_t)dm;

  int32_t axis0,axis1;
  g30_drv126_stock_park(sh_a,sh_b,(uint16_t)FOCVars[M1].hElAngle,&axis0,&axis1);

  int32_t sesc_q=g30_drv126_sh_ma_from_mc(FOCVars[M1].Iqd.q);
  int32_t sesc_d=g30_drv126_sh_ma_from_mc(FOCVars[M1].Iqd.d);
  int32_t dq=g30_drv126_sh_abs32(axis0-sesc_q);
  int32_t dd=g30_drv126_sh_abs32(axis1-sesc_d);
  dm=dq>dd?dq:dd;if(dm>65535)dm=65535;
  if((uint16_t)dm>g30_drv126_sh_dq_max)g30_drv126_sh_dq_max=(uint16_t)dm;

  int16_t qref=g30_drv126_sh_ma_from_mc(FOCVars[M1].Iqdref.q);
  int16_t dref=g30_drv126_sh_ma_from_mc(FOCVars[M1].Iqdref.d);
  g30_drv126_sh_qref_ma=qref;
  g30_drv126_sh_iq_ma=(int16_t)g30_drv126_sh_clamp32(axis0,-32767,32767);
  g30_drv126_sh_id_ma=(int16_t)g30_drv126_sh_clamp32(axis1,-32767,32767);

  /* The stock FOC call order itself resolves the old Map A/B ambiguity:
   * axis0 -> PI-B (wide), axis1 -> PI-C (narrow). Four substeps reproduce
   * the verified 4-kHz stock divider from the 1-kHz diagnostic task. */
  for(unsigned n=0;n<4u;n++){{
    g30_drv126_sh_vq=g30_drv126_sh_pi(qref,g30_drv126_sh_iq_ma,&g30_drv126_sh_q_acc,
                                       25500057,31128,&g30_drv126_sh_sat_q);
    g30_drv126_sh_vd=g30_drv126_sh_pi(dref,g30_drv126_sh_id_ma,&g30_drv126_sh_d_acc,
                                       8500019,10376,&g30_drv126_sh_sat_d);
  }}
  if(g30_drv126_sh_samples<65535u)g30_drv126_sh_samples++;
}}
#endif
'''
s=s[:start]+insert+s[end+len("#endif\n"):]
p.write_text(s)

p=root/"common_files/src/terminal.c"
s=p.read_text()
start=s.index('    }else if (strcmp(argv[0], "g30_drv126_shadow_reset") == 0){')
end=s.index('    }else if (strcmp(argv[0], "g30_motorpath_reset") == 0){',start)
insert='''    }else if (strcmp(argv[0], "g30_drv126_shadow_reset") == 0){
#ifdef G30P
        extern void g30_drv126_shadow_reset(void);
        g30_drv126_shadow_reset();
        commands_printf(phandle,"DRV126SH01 RESET");
#else
        commands_printf(phandle,"DRV126SH01 unavailable");
#endif
    }else if (strcmp(argv[0], "g30_drv126_shadow") == 0){
#ifdef G30P
        extern volatile uint16_t g30_drv126_sh_samples,g30_drv126_sh_clarke_max,g30_drv126_sh_dq_max;
        extern volatile uint16_t g30_drv126_sh_sat_q,g30_drv126_sh_sat_d;
        extern volatile int16_t g30_drv126_sh_qref_ma,g30_drv126_sh_iq_ma,g30_drv126_sh_id_ma;
        extern volatile int16_t g30_drv126_sh_vq,g30_drv126_sh_vd,g30_drv126_sh_cos,g30_drv126_sh_sin;
        commands_printf(phandle,"DRV126SH01 mode=STOCK_CLARKE_TRIG_PARK owner=SESC_HALL writes=0 samples=%u",
            (unsigned)g30_drv126_sh_samples);
        commands_printf(phandle,"DRV126SH01 bridge clarkeMax=%u parkMax=%u qref=%dmA iq=%dmA id=%dmA trig=%d,%d",
            (unsigned)g30_drv126_sh_clarke_max,(unsigned)g30_drv126_sh_dq_max,
            (int)g30_drv126_sh_qref_ma,(int)g30_drv126_sh_iq_ma,(int)g30_drv126_sh_id_ma,
            (int)g30_drv126_sh_cos,(int)g30_drv126_sh_sin);
        commands_printf(phandle,"DRV126SH01 PI qB=%d satQ=%u dC=%d satD=%u SESC=%d,%d",
            (int)g30_drv126_sh_vq,(unsigned)g30_drv126_sh_sat_q,
            (int)g30_drv126_sh_vd,(unsigned)g30_drv126_sh_sat_d,
            (int)FOCVars[M1].Vqd.q,(int)FOCVars[M1].Vqd.d);
#else
        commands_printf(phandle,"DRV126SH01 unavailable");
#endif
'''
s=s[:start]+insert+s[end:]
p.write_text(s)

print("SESC DRV126 Shadow R0.1 applied: exact stock Clarke+trig+Park, fixed PI-B/C mapping, writes=0")
