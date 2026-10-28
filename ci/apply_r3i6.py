from pathlib import Path

ROOT=Path("SOURCE_KOXX3/common_files/src")

def one(name, old, new, label):
    p=ROOT/name
    s=p.read_text()
    n=s.count(old)
    if n!=1:
        raise SystemExit(f"{label}: expected one anchor, got {n}")
    p.write_text(s.replace(old,new,1))

one("defines.h",
    '#define HW_NAME "G30D-FO76-PUSHSTART-R3I5"',
    '#define HW_NAME "G30D-FO76-PUSHSTART-R3I6"',
    "build id")

# Public read-only catch diagnostics.
one("g30_fo76_shadow.h",
'''uint8_t g30_fo76_sensorless_active(void);
void g30_fo76_sensorless_clear(void);
int16_t g30_fo76_control_speed_dpp(void);
''',
'''uint8_t g30_fo76_sensorless_active(void);
void g30_fo76_sensorless_clear(void);
int16_t g30_fo76_control_speed_dpp(void);
uint8_t g30_fo76_catch_state(void);
uint16_t g30_fo76_catch_phase(void);
int16_t g30_fo76_catch_error(void);
uint16_t g30_fo76_catch_ticks(void);
''',
"catch diag API")

p=ROOT/"g30_fo76_shadow.c"
s=p.read_text()

s=s.replace('#define G30_R3H_OBSERVER_COAST_MIN_DPP 64\n',
'''#define G30_R3H_OBSERVER_COAST_MIN_DPP 64
#define G30_R3I6_CATCH_GOOD_1K 20u
#define G30_R3I6_CATCH_TIMEOUT_FOC 4000u
''',1)

s=s.replace('static volatile uint8_t sensorless_external;\n',
'''static volatile uint8_t sensorless_external;
static uint8_t sensorless_catch_state; /* 0 observer, 1 BEMF predictor, 2 blend */
static int32_t sensorless_catch_phase_q4;
static int16_t sensorless_catch_step_q4;
static int16_t sensorless_catch_error;
static int16_t sensorless_catch_blend_offset;
static uint16_t sensorless_catch_ticks;
''',1)

old='''    d.phase=control_phase;d.magnitude_uwb=(uint16_t)(psi0/Q8);d.seeded=1;d.tracking=1;
    d.good_eval_1k=200u;d.valid=1u;
    takeover_phase_history=1u;takeover_last_observer_phase=control_phase;
    takeover_predictor_phase=control_phase;takeover_control_phase=control_phase;
    takeover_step_foc_q4=(int16_t)((int32_t)speed_dpp*16);
    takeover_blend_offset=0;takeover_state=G30_TK_OBSERVER;
'''
new='''    d.phase=control_phase;d.magnitude_uwb=(uint16_t)(psi0/Q8);d.seeded=1;d.tracking=1;
    /* R3I6 does not pretend the FO76 observer is valid at the instant of a
     * passive BEMF seed. The independent BEMF predictor owns angle first. */
    d.good_eval_1k=0u;d.valid=0u;
    takeover_phase_history=1u;takeover_last_observer_phase=control_phase;
    takeover_predictor_phase=control_phase;takeover_control_phase=control_phase;
    takeover_step_foc_q4=(int16_t)((int32_t)speed_dpp*16);
    sensorless_catch_phase_q4=((int32_t)(uint16_t)control_phase)<<4;
    sensorless_catch_step_q4=(int16_t)((int32_t)speed_dpp*16);
    sensorless_catch_error=0;sensorless_catch_blend_offset=0;
    sensorless_catch_ticks=0u;sensorless_catch_state=1u;
    takeover_blend_offset=0;takeover_state=G30_TK_OBSERVER;
'''
if old not in s: raise SystemExit("seed validity anchor missing")
s=s.replace(old,new,1)

old='''    takeover_phase_history=0u;
    takeover_blend_offset=0;
    d.valid=0u;d.tracking=0u;d.seeded=0u;d.good_eval_1k=0u;
}
int16_t g30_fo76_control_speed_dpp(void){
    if(sensorless_external || takeover_state==G30_TK_OBSERVER)
        return (int16_t)(takeover_step_foc_q4/16);
    return 0;
}
'''
new='''    takeover_phase_history=0u;
    takeover_blend_offset=0;
    sensorless_catch_state=0u;sensorless_catch_ticks=0u;
    sensorless_catch_error=0;sensorless_catch_blend_offset=0;
    d.valid=0u;d.tracking=0u;d.seeded=0u;d.good_eval_1k=0u;
}
int16_t g30_fo76_control_speed_dpp(void){
    if(sensorless_external && sensorless_catch_state)
        return (int16_t)(sensorless_catch_step_q4/16);
    if(sensorless_external || takeover_state==G30_TK_OBSERVER)
        return (int16_t)(takeover_step_foc_q4/16);
    return 0;
}
uint8_t g30_fo76_catch_state(void){return sensorless_catch_state;}
uint16_t g30_fo76_catch_phase(void){return (uint16_t)((uint32_t)sensorless_catch_phase_q4>>4);}
int16_t g30_fo76_catch_error(void){return sensorless_catch_error;}
uint16_t g30_fo76_catch_ticks(void){return sensorless_catch_ticks;}
'''
if old not in s: raise SystemExit("clear/speed anchor missing")
s=s.replace(old,new,1)

# Catch-on-the-fly angle owner: BEMF predictor first, observer only after
# independent phase agreement. Hall is not consulted here.
anchor='''    uint16_t hall=(uint16_t)hall_angle;
    takeover_last_hall_phase=hall;

    /* While an R3H coast is pending, never hand angle control back to Hall.
'''
insert='''    uint16_t hall=(uint16_t)hall_angle;
    takeover_last_hall_phase=hall;

    if(sensorless_external && sensorless_catch_state){
        sensorless_catch_phase_q4+=sensorless_catch_step_q4;
        uint16_t catch_phase=(uint16_t)((uint32_t)sensorless_catch_phase_q4>>4);
        if(sensorless_catch_ticks<65535u)sensorless_catch_ticks++;

        uint16_t obs_pred=takeover_phase_history?takeover_predicted_phase():d.phase;
        sensorless_catch_error=(int16_t)(obs_pred-catch_phase);

        if(sensorless_catch_state==1u){
            if(sensorless_catch_ticks>G30_R3I6_CATCH_TIMEOUT_FOC){
                takeover_latch_coast(G30_TK_FB_INVALID);
                takeover_control_phase=catch_phase;
                return catch_phase;
            }
            if(d.valid && d.tracking &&
               abs_phase16(sensorless_catch_error)<G30_R3G_ENTRY_ERR_COUNTS){
                sensorless_catch_blend_offset=(int16_t)(catch_phase-obs_pred);
                sensorless_catch_state=2u;
            }
            takeover_control_phase=catch_phase;
            return catch_phase;
        }

        /* Short BEMF-predictor -> observer blend. If observer agreement is
         * lost during the blend, return to predictor catch instead of Hall. */
        if(!d.tracking ||
           abs_phase16(sensorless_catch_error)>=G30_R3G_FALLBACK_ERR_COUNTS){
            sensorless_catch_state=1u;
            d.valid=0u;d.good_eval_1k=0u;
            takeover_control_phase=catch_phase;
            return catch_phase;
        }

        int16_t off=sensorless_catch_blend_offset;
        uint16_t out=(uint16_t)(obs_pred+off);
        if(off>G30_R3G_BLEND_STEP_COUNTS)off-=G30_R3G_BLEND_STEP_COUNTS;
        else if(off< -G30_R3G_BLEND_STEP_COUNTS)off+=G30_R3G_BLEND_STEP_COUNTS;
        else{
            off=0;
            sensorless_catch_state=0u;
            d.good_eval_1k=200u;
            d.valid=1u;
            takeover_state=G30_TK_OBSERVER;
        }
        sensorless_catch_blend_offset=off;
        takeover_control_phase=out;
        return out;
    }

    /* While an R3H coast is pending, never hand angle control back to Hall.
'''
if anchor not in s: raise SystemExit("control catch insertion anchor missing")
s=s.replace(anchor,insert,1)

# During catch, observer validity is based on agreement with the independent
# BEMF predictor, not Hall. Twenty clean 1 kHz samples are enough for handoff.
old='''            uint8_t model_good;
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
            d.valid=d.good_eval_1k>=200u;
'''
new='''            uint8_t model_good;
            uint16_t required_good=200u;
            if(sensorless_external){
                int16_t sdpp=g30_fo76_control_speed_dpp();
                uint8_t phase_good=1u;
                if(sensorless_catch_state){
                    uint16_t catch_phase=(uint16_t)((uint32_t)sensorless_catch_phase_q4>>4);
                    phase_good=(uint8_t)(abs_phase16((int16_t)(d.phase-catch_phase))<
                                         G30_R3G_ENTRY_ERR_COUNTS);
                    required_good=G30_R3I6_CATCH_GOOD_1K;
                }
                model_good=(uint8_t)(!clamped_now && phase_good &&
                    d.magnitude_uwb>lambda/2 && d.magnitude_uwb<lambda*3/2 &&
                    sdpp<=-G30_FO76_MIN_TRACK_DPP);
            }else{
                model_good=(uint8_t)(!clamped_now && ape<5461 && d.magnitude_uwb>lambda/2 &&
                    d.magnitude_uwb<lambda*3/2);
            }
            if(model_good){if(d.good_eval_1k<200u)d.good_eval_1k++;}
            else d.good_eval_1k=0;
            d.valid=d.good_eval_1k>=required_good;
'''
if old not in s: raise SystemExit("observer validity anchor missing")
s=s.replace(old,new,1)

p.write_text(s)

# Diagnostic output makes the hardware decision visible without extra RAM in
# the large observer snapshot structure.
p=ROOT/"terminal.c"
s=p.read_text()
s=s.replace('FO76_R3I5 pushstart_sensorless=1','FO76_R3I6 pushstart_sensorless=1',1)
anchor='''        commands_printf(phandle, "last_pwm=%u,%u,%u half_period=%u",
            (unsigned)obs.last_ca,(unsigned)obs.last_cb,(unsigned)obs.last_cc,(unsigned)obs.last_period);
'''
rep=anchor+'''        commands_printf(phandle, "catch state=%u phase=%u err=%d ticks=%u",
            (unsigned)g30_fo76_catch_state(),(unsigned)g30_fo76_catch_phase(),
            (int)g30_fo76_catch_error(),(unsigned)g30_fo76_catch_ticks());
'''
if anchor not in s: raise SystemExit("terminal catch diag anchor missing")
s=s.replace(anchor,rep,1)
s=s.replace('R3I5 ARM: keep MCSDK RUN, force PWM OFF for coast; BEMF seed re-enables PWM directly',
            'R3I6 ARM: RUN-coast; BEMF predictor catches rotor before observer blend',1)
p.write_text(s)

print("R3I6 transform applied")
