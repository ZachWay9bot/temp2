from pathlib import Path

root=Path("SOURCE_KOXX3")

# Build ID only. R0 is SHADOW-ONLY: the proven SESC Hall motor path remains the
# only owner of TIM1/PWM. DRV126 math is evaluated in the 1 kHz medium task.
p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-MOTORPATH-AUDIT-V0.3"'
new='#define HW_NAME "SESC-DRV126-SHADOW-R0"'
assert old in s
p.write_text(s.replace(old,new))

p=root/"common_files/src/mc_tasks.c"
s=p.read_text()

anchor='''/* USER CODE BEGIN Private Variables */
#if MUSIC_ENABLE'''
insert='''/* USER CODE BEGIN Private Variables */
#ifdef G30P
/* DRV126 Shadow R0 ---------------------------------------------------------
 * Diagnostic only. No TIM1/ADC/GPIO ownership, no PWMC_SetPhaseVoltage call.
 * The real motor stays on the validated SESC Hall path.
 *
 * DRV126 fixed current PI evidence:
 *   PI-B Kp=200/2048 Ki=10/8192 out=+-31128 acc=+-25500057
 *   PI-C Kp=200/2048 Ki=10/8192 out=+-10376 acc=+-8500019
 * d/q assignment is not proven, so both mappings are evaluated.
 *
 * The medium task is ~1 kHz. Four identical-error PI substeps model the
 * stock ~4 kHz current-loop integrator without adding work to the 16 kHz ISR.
 */
volatile uint16_t g30_drv126_sh_samples=0u;
volatile uint16_t g30_drv126_sh_clarke_max=0u;
volatile uint16_t g30_drv126_sh_dq_max=0u;
volatile uint16_t g30_drv126_sh_sat_a=0u;
volatile uint16_t g30_drv126_sh_sat_b=0u;
volatile int16_t g30_drv126_sh_qref_ma=0;
volatile int16_t g30_drv126_sh_iq_ma=0;
volatile int16_t g30_drv126_sh_id_ma=0;
volatile int16_t g30_drv126_sh_a_vq=0;
volatile int16_t g30_drv126_sh_a_vd=0;
volatile int16_t g30_drv126_sh_b_vq=0;
volatile int16_t g30_drv126_sh_b_vd=0;

static int32_t g30_drv126_sh_a_q_acc=0;
static int32_t g30_drv126_sh_a_d_acc=0;
static int32_t g30_drv126_sh_b_q_acc=0;
static int32_t g30_drv126_sh_b_d_acc=0;

static int32_t g30_drv126_sh_abs32(int32_t v){ return v<0 ? -v : v; }
static int32_t g30_drv126_sh_clamp32(int32_t v,int32_t lo,int32_t hi){
  return v<lo ? lo : (v>hi ? hi : v);
}
static int16_t g30_drv126_sh_pi(int32_t ref,int32_t act,int32_t *acc,
                                int32_t acc_lim,int32_t out_lim,uint16_t *sat){
  int32_t e=ref-act;
  int32_t pterm=(e*200)/2048;
  *acc=g30_drv126_sh_clamp32(*acc+e,-acc_lim,acc_lim);
  int32_t iterm=(*acc*10)/8192;
  int32_t out=pterm+iterm;
  if(out>out_lim){out=out_lim;if(*sat<65535u)(*sat)++;}
  else if(out<-out_lim){out=-out_lim;if(*sat<65535u)(*sat)++;}
  return (int16_t)out;
}
static int16_t g30_drv126_sh_ma_from_mc(int16_t counts){
  /* V0.3 hardware log: CURRENT_FACTOR_A=374.679 counts/A =>
   * 2.66895 mA/count. Integer diagnostic adapter only; it does not change
   * the real SESC current scale or claim an original DRV126 SI calibration. */
  int32_t v=((int32_t)counts*2669)/1000;
  return (int16_t)g30_drv126_sh_clamp32(v,-32767,32767);
}
void g30_drv126_shadow_reset(void){
  g30_drv126_sh_samples=0u;g30_drv126_sh_clarke_max=0u;g30_drv126_sh_dq_max=0u;
  g30_drv126_sh_sat_a=0u;g30_drv126_sh_sat_b=0u;
  g30_drv126_sh_qref_ma=0;g30_drv126_sh_iq_ma=0;g30_drv126_sh_id_ma=0;
  g30_drv126_sh_a_vq=0;g30_drv126_sh_a_vd=0;g30_drv126_sh_b_vq=0;g30_drv126_sh_b_vd=0;
  g30_drv126_sh_a_q_acc=0;g30_drv126_sh_a_d_acc=0;
  g30_drv126_sh_b_q_acc=0;g30_drv126_sh_b_d_acc=0;
}
static void g30_drv126_shadow_tick_1k(void){
  /* Hall-only R0. Sensorless/observer freeze is deliberately excluded. */
  if(!VescToSTM_g30_hall_selected() || PWM_Handle_M1._Super.PWM_off ||
     STM_GetState(&STM[M1])!=RUN){
    g30_drv126_sh_a_q_acc=0;g30_drv126_sh_a_d_acc=0;
    g30_drv126_sh_b_q_acc=0;g30_drv126_sh_b_d_acc=0;
    return;
  }

  /* Exact DRV126 Clarke constant, applied to the latest already-valid SESC
   * phase-current sample. This checks transform convention without touching
   * the ADC sequencer used by the real motor loop. */
  int32_t ia=(int32_t)FOCVars[M1].Iab.a;
  int32_t ib=(int32_t)FOCVars[M1].Iab.b;
  int32_t sh_a=ia;
  int32_t sh_b=((ia + 2*ib)*2365)>>12;
  int32_t da=g30_drv126_sh_abs32(sh_a-(int32_t)FOCVars[M1].Ialphabeta.alpha);
  int32_t db=g30_drv126_sh_abs32(sh_b-(int32_t)FOCVars[M1].Ialphabeta.beta);
  int32_t dm=da>db?da:db;
  if(dm>65535)dm=65535;
  if((uint16_t)dm>g30_drv126_sh_clarke_max)g30_drv126_sh_clarke_max=(uint16_t)dm;

  /* Use the existing MCSDK Park only as an adapter after the exact stock
   * Clarke step. R0 therefore proves Clarke/PI compatibility and both PI
   * assignment hypotheses, not byte-identical stock Park/SVM semantics. */
  alphabeta_t sh_ab={(int16_t)g30_drv126_sh_clamp32(sh_a,-32767,32767),
                     (int16_t)g30_drv126_sh_clamp32(sh_b,-32767,32767)};
  qd_t sh_qd=MCM_Park(sh_ab,FOCVars[M1].hElAngle);
  int32_t dd=g30_drv126_sh_abs32((int32_t)sh_qd.d-(int32_t)FOCVars[M1].Iqd.d);
  int32_t dq=g30_drv126_sh_abs32((int32_t)sh_qd.q-(int32_t)FOCVars[M1].Iqd.q);
  dm=dd>dq?dd:dq;if(dm>65535)dm=65535;
  if((uint16_t)dm>g30_drv126_sh_dq_max)g30_drv126_sh_dq_max=(uint16_t)dm;

  int16_t qref=g30_drv126_sh_ma_from_mc(FOCVars[M1].Iqdref.q);
  int16_t dref=g30_drv126_sh_ma_from_mc(FOCVars[M1].Iqdref.d);
  int16_t iq=g30_drv126_sh_ma_from_mc(sh_qd.q);
  int16_t id=g30_drv126_sh_ma_from_mc(sh_qd.d);
  g30_drv126_sh_qref_ma=qref;g30_drv126_sh_iq_ma=iq;g30_drv126_sh_id_ma=id;

  /* Mapping A: q=PI-B(full), d=PI-C(1/3). Mapping B: q=PI-C, d=PI-B.
   * Four substeps approximate stock 4 kHz integration over this 1 ms tick. */
  for(unsigned n=0;n<4u;n++){
    g30_drv126_sh_a_vq=g30_drv126_sh_pi(qref,iq,&g30_drv126_sh_a_q_acc,
                                         25500057,31128,&g30_drv126_sh_sat_a);
    g30_drv126_sh_a_vd=g30_drv126_sh_pi(dref,id,&g30_drv126_sh_a_d_acc,
                                         8500019,10376,&g30_drv126_sh_sat_a);
    g30_drv126_sh_b_vq=g30_drv126_sh_pi(qref,iq,&g30_drv126_sh_b_q_acc,
                                         8500019,10376,&g30_drv126_sh_sat_b);
    g30_drv126_sh_b_vd=g30_drv126_sh_pi(dref,id,&g30_drv126_sh_b_d_acc,
                                         25500057,31128,&g30_drv126_sh_sat_b);
  }
  if(g30_drv126_sh_samples<65535u)g30_drv126_sh_samples++;
}
#endif
#if MUSIC_ENABLE'''
assert anchor in s
s=s.replace(anchor,insert,1)

# Run shadow only from medium-frequency control updates. No high-frequency hook.
needle='''    MCI_ExecBufferedCommands( oMCInterface[M1] );
    FOC_CalcCurrRef( M1 );

    if( !IsSpeedReliable )'''
repl='''    MCI_ExecBufferedCommands( oMCInterface[M1] );
    FOC_CalcCurrRef( M1 );
#ifdef G30P
    g30_drv126_shadow_tick_1k();
#endif

    if( !IsSpeedReliable )'''
assert needle in s
s=s.replace(needle,repl,1)
p.write_text(s)

# Read-only terminal diagnostics.
p=root/"common_files/src/terminal.c"
s=p.read_text()
anchor='''    }else if (strcmp(argv[0], "g30_motorpath_reset") == 0){'''
insert='''    }else if (strcmp(argv[0], "g30_drv126_shadow_reset") == 0){
#ifdef G30P
        extern void g30_drv126_shadow_reset(void);
        g30_drv126_shadow_reset();
        commands_printf(phandle,"DRV126SH RESET");
#else
        commands_printf(phandle,"DRV126SH unavailable");
#endif
    }else if (strcmp(argv[0], "g30_drv126_shadow") == 0){
#ifdef G30P
        extern volatile uint16_t g30_drv126_sh_samples,g30_drv126_sh_clarke_max,g30_drv126_sh_dq_max;
        extern volatile uint16_t g30_drv126_sh_sat_a,g30_drv126_sh_sat_b;
        extern volatile int16_t g30_drv126_sh_qref_ma,g30_drv126_sh_iq_ma,g30_drv126_sh_id_ma;
        extern volatile int16_t g30_drv126_sh_a_vq,g30_drv126_sh_a_vd,g30_drv126_sh_b_vq,g30_drv126_sh_b_vd;
        commands_printf(phandle,"DRV126SH mode=SHADOW_ONLY owner=SESC_HALL rate_model=4k_from_1k writes=0 samples=%u",
            (unsigned)g30_drv126_sh_samples);
        commands_printf(phandle,"DRV126SH transform clarkeMax=%u dqAdapterMax=%u qref=%dmA iq=%dmA id=%dmA",
            (unsigned)g30_drv126_sh_clarke_max,(unsigned)g30_drv126_sh_dq_max,
            (int)g30_drv126_sh_qref_ma,(int)g30_drv126_sh_iq_ma,(int)g30_drv126_sh_id_ma);
        commands_printf(phandle,"DRV126SH mapA qB_dC Vqd=%d,%d sat=%u mapB qC_dB Vqd=%d,%d sat=%u SESC=%d,%d",
            (int)g30_drv126_sh_a_vq,(int)g30_drv126_sh_a_vd,(unsigned)g30_drv126_sh_sat_a,
            (int)g30_drv126_sh_b_vq,(int)g30_drv126_sh_b_vd,(unsigned)g30_drv126_sh_sat_b,
            (int)FOCVars[M1].Vqd.q,(int)FOCVars[M1].Vqd.d);
#else
        commands_printf(phandle,"DRV126SH unavailable");
#endif
    }else if (strcmp(argv[0], "g30_motorpath_reset") == 0){'''
assert anchor in s
s=s.replace(anchor,insert,1)
p.write_text(s)

print("SESC DRV126 Shadow R0 applied: read-only 1k shadow / 4k PI model, no PWM ownership")
