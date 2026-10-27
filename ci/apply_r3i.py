from pathlib import Path

ROOT=Path("SOURCE_KOXX3")
SRC=ROOT/"common_files/src"
INC=ROOT/"common_files/inc"
G30=ROOT/"g30p/Src"

def one(path, old, new, label):
    p=path
    s=p.read_text()
    n=s.count(old)
    if n!=1: raise SystemExit(f"{label}: expected one anchor, got {n}")
    p.write_text(s.replace(old,new,1))

# Build identity.
one(SRC/"defines.h",
    '#define HW_NAME "G30D-FO76-OBSERVER-ONLY-R3H"',
    '#define HW_NAME "G30D-FO76-PUSHSTART-R3I"',
    "build id")

# Passive BEMF inputs are confirmed G30 hardware pins. Configure as analog.
p=G30/"stm32f1xx_hal_msp.c"; s=p.read_text()
old='''    GPIO_InitStruct.Pin = MAIN_CURR_AMPL_Pin|M1_BUS_VOLTAGE_Pin|M1_CURR_AMPL_U_Pin|M1_CURR_AMPL_V_Pin
                          |M1_CURR_AMPL_W_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_ANALOG;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
'''
new='''    GPIO_InitStruct.Pin = MAIN_CURR_AMPL_Pin|M1_BUS_VOLTAGE_Pin|M1_CURR_AMPL_U_Pin|M1_CURR_AMPL_V_Pin
                          |M1_CURR_AMPL_W_Pin|GPIO_PIN_6|GPIO_PIN_7;
    GPIO_InitStruct.Mode = GPIO_MODE_ANALOG;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
#ifdef G30P
    __HAL_RCC_GPIOB_CLK_ENABLE();
    GPIO_InitStruct.Pin = GPIO_PIN_1; /* PB1 = BEMF_C / ADC9 */
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
#endif
'''
if old not in s: raise SystemExit("ADC GPIO anchor missing")
p.write_text(s.replace(old,new,1))

# R3I passive rolling detector / one-session calibration + start arming.
(SRC/"g30_r3i_pushstart.h").write_text(r'''#pragma once
#include <stdint.h>

typedef struct {
    uint8_t mode;             /* 0 off, 1 armed/wait roll, 2 sensorless running */
    uint8_t cal_valid;
    uint8_t sensorless_started;
    uint8_t sector;
    uint16_t a,b,c,span;
    uint16_t frames;
    uint16_t forward_edges,reverse_edges,bad_jumps;
    uint16_t cal_samples;
    uint16_t phase_base,phase_cal,hall;
    int16_t phase_error;
    int16_t cal_offset;
    int16_t speed_dpp;
    int32_t erpm;
    uint32_t starts;
} g30_r3i_diag_t;

void g30_r3i_request_arm(uint8_t enable);
void g30_r3i_tick(uint8_t pwm_off, uint16_t hall_angle, int16_t hall_speed_dpp);
uint8_t g30_r3i_block_pwm_start(void);
uint8_t g30_r3i_sensorless_active(void);
uint32_t g30_r3i_active_age_ms(void);
int16_t g30_r3i_speed_dpp(void);
int32_t g30_r3i_erpm(void);
g30_r3i_diag_t g30_r3i_get_diag(void);
''')

(SRC/"g30_r3i_pushstart.c").write_text(r'''#include "g30_r3i_pushstart.h"
#include "g30_fo76_shadow.h"
#include "regular_conversion_manager.h"
#include "drive_parameters.h"
#include "mc_stm_types.h"
#include "main.h"

#define R3I_NO_SECTOR 0xffu
#define R3I_MIN_SPAN 40u
#define R3I_MIN_DPP 64
#define R3I_MIN_EDGES 4u
#define R3I_CAL_SAMPLES 12u
#define R3I_SAMPLE_DIV 3u
#define R3I_PHASE60 10923u

static volatile uint8_t request_arm;
static g30_r3i_diag_t d;
static RegConv_t ca={ADC1,6u,M1_VBUS_SAMPLING_TIME};
static RegConv_t cb={ADC1,7u,M1_VBUS_SAMPLING_TIME};
static RegConv_t cc={ADC1,9u,M1_VBUS_SAMPLING_TIME};
static uint8_t ha=255u,hb=255u,hc=255u,init_done,divn,last_sector=R3I_NO_SECTOR;
static uint32_t last_edge_cycles,avg_edge_cycles,start_tick;
static int32_t cal_sum;

static uint16_t abs16(int16_t x){return (uint16_t)(x<0?-(int32_t)x:(int32_t)x);}
static uint16_t atan2_u16(int32_t y,int32_t x){
    static const uint16_t at[15]={8192u,4836u,2555u,1297u,651u,326u,163u,81u,41u,20u,10u,5u,3u,1u,1u};
    if(!x&&!y)return 0u;
    int32_t xi=x,yi=y,a=0;
    if(xi<0){xi=-xi;yi=-yi;a=32768;}
    for(unsigned i=0;i<15u;i++){
        if(!yi)break;
        int32_t xo=xi;
        if(yi>0){xi+=yi>>i;yi-=xo>>i;a+=at[i];}
        else{xi-=yi>>i;yi+=xo>>i;a-=at[i];}
    }
    return (uint16_t)a;
}
static uint8_t sector_from_abc(uint16_t a,uint16_t b,uint16_t c){
    if(a>=b){if(b>=c)return 0u;if(a>=c)return 5u;return 4u;}
    if(a>=c)return 1u;
    if(b>=c)return 2u;
    return 3u;
}
static uint16_t base_control_phase(uint16_t a,uint16_t b,uint16_t c){
    int32_t common=((int32_t)a+b+c)/3;
    int32_t ea=(int32_t)a-common;
    int32_t eb=(int32_t)(((int64_t)((int32_t)b-(int32_t)c)*18919)>>15);
    /* Forward is negative electrical rotation. psi = e + 90deg in physical
     * alpha/beta, while the validated R3H control frame is psi + 90deg. */
    return (uint16_t)(atan2_u16(eb,ea)+32768u);
}
static void reset_roll(void){
    d.a=d.b=d.c=d.span=0;d.frames=0;d.forward_edges=d.reverse_edges=d.bad_jumps=0;
    d.cal_samples=0;d.phase_base=d.phase_cal=d.hall=0;d.phase_error=0;d.speed_dpp=0;d.erpm=0;
    d.cal_valid=0;d.sensorless_started=0;d.sector=R3I_NO_SECTOR;d.cal_offset=0;
    last_sector=R3I_NO_SECTOR;last_edge_cycles=avg_edge_cycles=0;cal_sum=0;divn=0;
}
static void init_once(void){
    if(init_done)return;
    ha=RCM_RegisterRegConv(&ca); hb=RCM_RegisterRegConv(&cb); hc=RCM_RegisterRegConv(&cc);
    init_done=(uint8_t)(ha!=255u && hb!=255u && hc!=255u);
}
void g30_r3i_request_arm(uint8_t enable){
    request_arm=enable?1u:0u;
    if(!enable){d.mode=0u;d.sensorless_started=0u;return;}
    reset_roll();d.mode=1u;
}
uint8_t g30_r3i_block_pwm_start(void){return (uint8_t)(d.mode==1u && !d.sensorless_started);}
uint8_t g30_r3i_sensorless_active(void){return (uint8_t)(d.mode==2u && d.sensorless_started);}
uint32_t g30_r3i_active_age_ms(void){return g30_r3i_sensorless_active()?(uint32_t)(HAL_GetTick()-start_tick):0u;}
int16_t g30_r3i_speed_dpp(void){return g30_r3i_sensorless_active()?g30_fo76_control_speed_dpp():d.speed_dpp;}
int32_t g30_r3i_erpm(void){return (int32_t)g30_r3i_speed_dpp()*16000*60/65536;}
g30_r3i_diag_t g30_r3i_get_diag(void){return d;}

void g30_r3i_tick(uint8_t pwm_off,uint16_t hall_angle,int16_t hall_speed_dpp){
    init_once();
    if(!request_arm || !init_done)return;
    if(g30_r3i_sensorless_active())return;
    if(!pwm_off)return;
    if(++divn<R3I_SAMPLE_DIV)return;
    divn=0;

    uint32_t sa=0,sb=0,sc=0;
    for(unsigned i=0;i<3u;i++){sa+=RCM_ExecRegularConv(ha);sb+=RCM_ExecRegularConv(hb);sc+=RCM_ExecRegularConv(hc);}
    uint16_t a=(uint16_t)((sa+1u)/3u),b=(uint16_t)((sb+1u)/3u),c=(uint16_t)((sc+1u)/3u);
    uint16_t hi=a,lo=a;if(b>hi)hi=b;if(c>hi)hi=c;if(b<lo)lo=b;if(c<lo)lo=c;
    d.a=a;d.b=b;d.c=c;d.span=(uint16_t)(hi-lo);d.hall=hall_angle;if(d.frames<65535u)d.frames++;
    if(d.span<R3I_MIN_SPAN){last_sector=R3I_NO_SECTOR;d.sector=R3I_NO_SECTOR;d.forward_edges=0;d.speed_dpp=0;return;}
    uint8_t sec=sector_from_abc(a,b,c);d.sector=sec;
    d.phase_base=base_control_phase(a,b,c);
    d.phase_error=(int16_t)(d.phase_base-hall_angle);

    uint32_t now=DWT->CYCCNT;
    if(last_sector==R3I_NO_SECTOR){last_sector=sec;last_edge_cycles=now;return;}
    if(sec!=last_sector){
        uint8_t step=(uint8_t)((sec+6u-last_sector)%6u);
        uint32_t dt=now-last_edge_cycles;last_sector=sec;last_edge_cycles=now;
        if(step==5u && dt>50000u && dt<8000000u){
            if(d.forward_edges<65535u)d.forward_edges++;
            avg_edge_cycles=avg_edge_cycles?((avg_edge_cycles*7u+dt)>>3):dt;
            uint32_t mag=(R3I_PHASE60*(64000000u/16000u)+avg_edge_cycles/2u)/avg_edge_cycles;
            if(mag>32767u)mag=32767u;
            d.speed_dpp=-(int16_t)mag;
            d.erpm=(int32_t)d.speed_dpp*16000*60/65536;
        }else if(step==1u){
            if(d.reverse_edges<65535u)d.reverse_edges++;d.forward_edges=0;d.speed_dpp=0;
        }else{
            if(d.bad_jumps<65535u)d.bad_jumps++;d.forward_edges=0;d.speed_dpp=0;
        }
    }

    if(d.forward_edges>=R3I_MIN_EDGES && d.speed_dpp<=-R3I_MIN_DPP){
        /* Development calibration only: establish the fixed board/wiring frame
         * offset from the connected Hall reference. It is not used after seed. */
        if(!d.cal_valid && hall_speed_dpp<=-40){
            cal_sum+=(int16_t)(hall_angle-d.phase_base);
            if(d.cal_samples<65535u)d.cal_samples++;
            if(d.cal_samples>=R3I_CAL_SAMPLES){
                d.cal_offset=(int16_t)(cal_sum/(int32_t)d.cal_samples);
                d.cal_valid=1u;
            }
        }
        if(d.cal_valid){
            d.phase_cal=(uint16_t)(d.phase_base+(uint16_t)d.cal_offset);
            if(abs16((int16_t)(d.phase_cal-hall_angle))<3641u){
                g30_fo76_sensorless_seed(d.phase_cal,d.speed_dpp);
                d.sensorless_started=1u;d.mode=2u;d.starts++;start_tick=HAL_GetTick();
            }
        }
    }
}
''')

# Extend observer API for genuine sensorless angle/speed/validity after R3I seed.
p=SRC/"g30_fo76_shadow.h"; s=p.read_text()
anchor='''uint8_t g30_fo76_coast_requested(void);
void g30_fo76_shadow_step'''
rep='''uint8_t g30_fo76_coast_requested(void);
void g30_fo76_sensorless_seed(uint16_t control_phase, int16_t speed_dpp);
uint8_t g30_fo76_sensorless_active(void);
int16_t g30_fo76_control_speed_dpp(void);
void g30_fo76_shadow_step'''
if anchor not in s: raise SystemExit("shadow h anchor")
p.write_text(s.replace(anchor,rep,1))

p=SRC/"g30_fo76_shadow.c"; s=p.read_text()
s=s.replace('static volatile uint8_t takeover_coast_request;\n',
            'static volatile uint8_t takeover_coast_request;\nstatic volatile uint8_t sensorless_external;\n',1)
anchor='''uint8_t g30_fo76_coast_requested(void) {
    return takeover_coast_request;
}
'''
rep=anchor+r'''
static uint16_t hall_to_flux(int16_t hall);
static int32_t cos_q15(uint16_t phase);
static int32_t sin_phase_q15(uint16_t phase);

void g30_fo76_sensorless_seed(uint16_t control_phase, int16_t speed_dpp) {
    int32_t psi0=(int32_t)(d.lambda_uwb?d.lambda_uwb:G30_FO76_LAMBDA_PROVEN_UWB)*Q8;
    uint16_t flux_phase=hall_to_flux((int16_t)control_phase);
    ++seq;
    x_a_q8=(int32_t)(((int64_t)psi0*cos_q15(flux_phase))>>15);
    x_b_q8=(int32_t)(((int64_t)psi0*sin_phase_q15(flux_phase))>>15);
    d.phase=control_phase;d.magnitude_uwb=(uint16_t)(psi0/Q8);d.seeded=1;d.tracking=1;
    d.good_eval_1k=200u;d.valid=1u;
    takeover_phase_history=1u;takeover_last_observer_phase=control_phase;
    takeover_predictor_phase=control_phase;takeover_control_phase=control_phase;
    takeover_step_foc_q4=(int16_t)((int32_t)speed_dpp*16);
    takeover_blend_offset=0;takeover_state=G30_TK_OBSERVER;
    takeover_fallback_reason=G30_TK_FB_NONE;takeover_coast_request=0u;
    takeover_enable_request=1u;sensorless_external=1u;takeover_entries++;
    decim16=decim4=0;
    ++seq;
}
uint8_t g30_fo76_sensorless_active(void){return sensorless_external;}
int16_t g30_fo76_control_speed_dpp(void){
    if(sensorless_external || takeover_state==G30_TK_OBSERVER)
        return (int16_t)(takeover_step_foc_q4/16);
    return 0;
}
'''
if anchor not in s: raise SystemExit("shadow seed anchor")
s=s.replace(anchor,rep,1)

# Preserve external seed while PWM is still off; don't erase it before the first powered FOC tick.
old='''    if(!pwm_on || d.foc_hz!=16000u){
        ++seq;
        d.valid=0; d.good_eval_1k=0; d.tracking=0; d.seeded=0;
        takeover_phase_history=0;
        decim16=decim4=0;
        ++seq;
        return;
    }
'''
new='''    if(!pwm_on || d.foc_hz!=16000u){
        if(sensorless_external && d.foc_hz==16000u){
            decim16=decim4=0;
            return;
        }
        ++seq;
        d.valid=0; d.good_eval_1k=0; d.tracking=0; d.seeded=0;
        takeover_phase_history=0;
        decim16=decim4=0;
        ++seq;
        return;
    }
'''
if old not in s: raise SystemExit("pwmoff anchor")
s=s.replace(old,new,1)

old='''    int32_t sp=hall_speed_dpp; if(sp<0) sp=-sp;
    ++seq;
    if(sp<G30_FO76_MIN_TRACK_DPP){
'''
new='''    int32_t model_speed_dpp=sensorless_external?g30_fo76_control_speed_dpp():hall_speed_dpp;
    int32_t sp=model_speed_dpp; if(sp<0) sp=-sp;
    ++seq;
    if(!sensorless_external && sp<G30_FO76_MIN_TRACK_DPP){
'''
if old not in s: raise SystemExit("speed anchor")
s=s.replace(old,new,1)

# Sensorless validity no longer depends on Hall agreement. Hall error remains diagnostics only.
old='''            if(!clamped_now && ape<5461 && d.magnitude_uwb>lambda/2 &&
                d.magnitude_uwb<lambda*3/2){
                if(d.good_eval_1k<200u)d.good_eval_1k++;
            }else d.good_eval_1k=0;
'''
new='''            uint8_t model_good;
            if(sensorless_external){
                int16_t sdpp=g30_fo76_control_speed_dpp();
                model_good=(uint8_t)(!clamped_now && d.magnitude_uwb>lambda/2 &&
                    d.magnitude_uwb<lambda*3/2 && sdpp<=-G30_FO76_MIN_TRACK_DPP);
            }else{
                model_good=(uint8_t)(!clamped_now && ape<5461 && d.magnitude_uwb>lambda/2 &&
                    d.magnitude_uwb<lambda*3/2);
            }
            if(model_good){if(d.good_eval_1k<200u)d.good_eval_1k++;}
            else d.good_eval_1k=0;
'''
if old not in s: raise SystemExit("valid anchor")
s=s.replace(old,new,1)
p.write_text(s)

# Integrate push-start sampler and virtual observer speed feedback.
p=SRC/"mc_tasks.c"; s=p.read_text()
s=s.replace('#include "g30_fo76_shadow.h"\n','#include "g30_fo76_shadow.h"\n#include "g30_r3i_pushstart.h"\n',1)
old='''  bool IsSpeedReliable = HALL_CalcAvrgMecSpeedUnit( &HALL_M1, &wAux );
  PQD_CalcElMotorPower( pMPM[M1] );
'''
new='''#ifdef G30P
  g30_r3i_tick((uint8_t)PWM_Handle_M1._Super.PWM_off,(uint16_t)HALL_M1._Super.hElAngle,HALL_M1._Super.hElSpeedDpp);
#endif
  bool IsSpeedReliable;
#ifdef G30P
  if(g30_fo76_sensorless_active()){
    int16_t odpp=g30_fo76_control_speed_dpp();
    wAux=(int16_t)(((int32_t)odpp*(int32_t)HALL_M1._Super.hMeasurementFrequency*(int32_t)SPEED_UNIT)/
                   (int32_t)HALL_M1._Super.DPPConvFactor);
    HALL_M1._Super.hElSpeedDpp=odpp;
    HALL_M1.AvrElSpeedDpp=odpp;
    HALL_M1._Super.hAvrMecSpeedUnit=wAux;
    IsSpeedReliable=true;
  }else
#endif
  {
    IsSpeedReliable = HALL_CalcAvrgMecSpeedUnit( &HALL_M1, &wAux );
  }
  PQD_CalcElMotorPower( pMPM[M1] );
'''
if old not in s: raise SystemExit("medium speed anchor")
s=s.replace(old,new,1)
old='''	HALL_CalcElAngle (&HALL_M1);
'''
new='''#ifdef G30P
    if(!g30_fo76_sensorless_active()) HALL_CalcElAngle (&HALL_M1);
#else
    HALL_CalcElAngle (&HALL_M1);
#endif
'''
if old not in s: raise SystemExit("HF hall anchor")
s=s.replace(old,new,1)
old='''  hElSpeedDpp = SPD_GetElSpeedDpp(speedHandle);
'''
new='''  hElSpeedDpp = g30_fo76_sensorless_active()?g30_fo76_control_speed_dpp():SPD_GetElSpeedDpp(speedHandle);
'''
if old not in s: raise SystemExit("foc speed anchor")
s=s.replace(old,new,1)
p.write_text(s)

# Gate PWM until passive roll is qualified, preload BEMF voltage, clamp the first 800ms.
p=SRC/"VescToSTM.c"; s=p.read_text()
s=s.replace('#include "g30_fo76_shadow.h"\n','#include "g30_fo76_shadow.h"\n#include "g30_r3i_pushstart.h"\n',1)
old='''int16_t VescToSTM_Iq_lim_hook(int16_t iq){

	//Do temperature Iq limit
'''
new='''int16_t VescToSTM_Iq_lim_hook(int16_t iq){
#ifdef G30P
    if(g30_r3i_sensorless_active() && g30_r3i_active_age_ms()<800u){
        int16_t lim=(int16_t)current_to_torque(1000);
        if(iq>lim)iq=lim;else if(iq< -lim)iq=-lim;
    }
#endif

	//Do temperature Iq limit
'''
if old not in s: raise SystemExit("iq hook anchor")
s=s.replace(old,new,1)
old='''void VescToSTM_pwm_start(void){
	if(PWM_Handle_M1._Super.PWM_off){
		float fVd = 32768.0 / VescToSTM_get_bus_voltage() * motor_voltage;
'''
new='''void VescToSTM_pwm_start(void){
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
'''
if old not in s: raise SystemExit("pwm start anchor")
s=s.replace(old,new,1)
p.write_text(s)

# Terminal control and telemetry.
p=SRC/"terminal.c"; s=p.read_text()
s=s.replace('#include "g30_fo76_shadow.h"\n','#include "g30_fo76_shadow.h"\n#include "g30_r3i_pushstart.h"\n',1)
anchor='''	}else if (strcmp(argv[0], "top") == 0){
'''
block=r'''	}else if (strcmp(argv[0], "g30_pushstart") == 0){
        if(argc==2 && strcmp(argv[1],"arm")==0){
            g30_r3i_request_arm(1u);
            g30_fo76_request_takeover(0u);
            commands_printf(phandle,"R3I pushstart ARM: PWM held off until passive FWD BEMF >=64 DPP; first run calibrates fixed BEMF frame from Hall reference");
        }else if(argc==2 && strcmp(argv[1],"off")==0){
            g30_r3i_request_arm(0u);
            g30_fo76_request_takeover(0u);
            commands_printf(phandle,"R3I pushstart OFF");
        }else if(argc!=1 && !(argc==2 && strcmp(argv[1],"status")==0)){
            commands_printf(phandle,"Usage: g30_pushstart [arm | off | status]");
            return;
        }
        g30_r3i_diag_t ps=g30_r3i_get_diag();
        commands_printf(phandle,"R3I mode=%u cal=%u started=%u starts=%lu frames=%u edges=%u rev=%u bad=%u",
            (unsigned)ps.mode,(unsigned)ps.cal_valid,(unsigned)ps.sensorless_started,(unsigned long)ps.starts,
            (unsigned)ps.frames,(unsigned)ps.forward_edges,(unsigned)ps.reverse_edges,(unsigned)ps.bad_jumps);
        commands_printf(phandle,"bemf=%u,%u,%u span=%u sector=%u dpp=%d erpm=%ld",
            (unsigned)ps.a,(unsigned)ps.b,(unsigned)ps.c,(unsigned)ps.span,(unsigned)ps.sector,
            (int)ps.speed_dpp,(long)ps.erpm);
        commands_printf(phandle,"phase_base=%u phase_cal=%u hall=%u err=%d cal_n=%u offset=%d",
            (unsigned)ps.phase_base,(unsigned)ps.phase_cal,(unsigned)ps.hall,(int)ps.phase_error,
            (unsigned)ps.cal_samples,(int)ps.cal_offset);
'''+anchor
if anchor not in s: raise SystemExit("terminal anchor")
s=s.replace(anchor,block,1)
s=s.replace('FO76_R3H observer_only_fwd=1','FO76_R3I pushstart_sensorless=1',1)
p.write_text(s)

# The reproducible native builder follows the Eclipse linked-resource list.
# Add the new R3I C unit beside the already linked FO76 observer.
proj=ROOT/"g30p/STM32CubeIDE/.project"
ps=proj.read_text()
plink='''			<link>
			<name>Common/g30_fo76_shadow.c</name>
			<type>1</type>
			<locationURI>PARENT-2-PROJECT_LOC/common_files/src/g30_fo76_shadow.c</locationURI>
		</link>
'''
pnew=plink+'''		<link>
			<name>Common/g30_r3i_pushstart.c</name>
			<type>1</type>
			<locationURI>PARENT-2-PROJECT_LOC/common_files/src/g30_r3i_pushstart.c</locationURI>
		</link>
'''
if ps.count(plink)!=1:
    raise SystemExit(f".project FO76 link anchor count={ps.count(plink)}")
proj.write_text(ps.replace(plink,pnew,1))

print("R3I transform applied")
