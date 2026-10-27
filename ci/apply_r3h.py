from pathlib import Path

ROOT = Path("SOURCE_KOXX3/common_files/src")

def replace1(path, old, new):
    p = ROOT / path
    s = p.read_text()
    if s.count(old) != 1:
        raise SystemExit(f"{path}: expected exactly one match, got {s.count(old)} for {old[:60]!r}")
    p.write_text(s.replace(old, new, 1))

replace1("defines.h",
         '#define HW_NAME "G30D-FO76-TAKEOVER-R3G2"',
         '#define HW_NAME "G30D-FO76-OBSERVER-ONLY-R3H"')

replace1("g30_fo76_shadow.h",
         '    uint32_t takeover_entries, takeover_fallbacks;\n',
         '    uint32_t takeover_entries, takeover_fallbacks;\n    uint8_t takeover_coast_latched;\n')
replace1("g30_fo76_shadow.h",
         'uint16_t g30_fo76_control_angle(int16_t hall_angle, int16_t hall_speed_dpp);\n',
         'uint16_t g30_fo76_control_angle(int16_t hall_angle, int16_t hall_speed_dpp);\n'
         '/* R3H: latched coast request after observer-only operation loses its run envelope. */\n'
         'uint8_t g30_fo76_coast_requested(void);\n')

p = ROOT / "g30_fo76_shadow.c"
s = p.read_text()
s = s.replace('#define G30_R3G_FALLBACK_MIN_DPP 48\n',
              '#define G30_R3G_FALLBACK_MIN_DPP 48\n#define G30_R3H_OBSERVER_COAST_MIN_DPP 64\n', 1)
s = s.replace('static volatile uint8_t takeover_enable_request;\n',
              'static volatile uint8_t takeover_enable_request;\nstatic volatile uint8_t takeover_coast_request;\n', 1)
old = '''void g30_fo76_request_takeover(uint8_t enable) {
    takeover_enable_request=enable?1u:0u;
}
'''
new = '''void g30_fo76_request_takeover(uint8_t enable) {
    if(enable){
        takeover_coast_request=0u;
    }
    takeover_enable_request=enable?1u:0u;
}

uint8_t g30_fo76_coast_requested(void) {
    return takeover_coast_request;
}
'''
if old not in s: raise SystemExit("request_takeover block missing")
s = s.replace(old, new, 1)
old = '''static void takeover_latch_fallback(uint8_t reason) {
    takeover_state=G30_TK_FALLBACK;
    takeover_fallback_reason=reason;
    takeover_enable_request=0u; /* explicit re-arm required after any fallback */
    takeover_blend_offset=0;
    takeover_fallbacks++;
}
'''
new = old + '''
/* R3H: after the observer owns FOC, loss of its run envelope never returns
 * control to Hall. Latch a coast request; the medium-frequency task moves the
 * motor state machine to ANY_STOP while the fast loop keeps its last observer
 * trajectory until PWM is switched off. */
static void takeover_latch_coast(uint8_t reason) {
    takeover_state=G30_TK_FALLBACK;
    takeover_fallback_reason=reason;
    takeover_enable_request=0u;
    takeover_blend_offset=0;
    takeover_coast_request=1u;
    takeover_fallbacks++;
}
'''
if old not in s: raise SystemExit("fallback block missing")
s = s.replace(old, new, 1)

start = s.index('uint16_t g30_fo76_control_angle(')
end = s.index('\n/* ST/Koxx3:', start)
newfun = r'''uint16_t g30_fo76_control_angle(int16_t hall_angle, int16_t hall_speed_dpp) {
    uint16_t hall=(uint16_t)hall_angle;
    takeover_last_hall_phase=hall;

    /* While an R3H coast is pending, never hand angle control back to Hall.
     * Medium-frequency code will request ANY_STOP and switch PWM off. */
    if(takeover_state==G30_TK_FALLBACK && takeover_coast_request){
        uint16_t predicted=takeover_phase_history?takeover_predicted_phase():takeover_control_phase;
        takeover_control_phase=predicted;
        return predicted;
    }

    if(!takeover_enable_request){
        if(takeover_state!=G30_TK_FALLBACK){
            takeover_state=G30_TK_HALL_OFF;
            takeover_fallback_reason=G30_TK_FB_NONE;
        }
        takeover_control_phase=hall;
        return hall;
    }
    if(takeover_state==G30_TK_HALL_OFF || takeover_state==G30_TK_FALLBACK){
        takeover_state=G30_TK_ARMED_WAIT;
        takeover_fallback_reason=G30_TK_FB_NONE;
    }

    uint16_t predicted=takeover_phase_history?takeover_predicted_phase():d.phase;
    int16_t pred_err=(int16_t)(predicted-hall);
    uint16_t hall_speed=abs_i16_u(hall_speed_dpp);

    if(takeover_state==G30_TK_ARMED_WAIT){
        /* Hardware convention from the validated FWD run: physical forward
         * rotation is negative Hall electrical DPP. R3H intentionally does not
         * arm observer takeover for reverse operation. */
        if(d.valid && d.tracking && takeover_phase_history &&
           hall_speed_dpp<=-(int16_t)G30_R3G_TAKEOVER_MIN_DPP &&
           abs_phase16(pred_err)<G30_R3G_ENTRY_ERR_COUNTS){
            takeover_blend_offset=(int16_t)(hall-predicted);
            takeover_state=G30_TK_BLEND;
            takeover_entries++;
        }else{
            takeover_control_phase=hall;
            return hall;
        }
    }

    if(takeover_state==G30_TK_BLEND){
        /* During the short transition Hall is still allowed as guard/reference. */
        if(!d.valid){takeover_latch_fallback(G30_TK_FB_INVALID);takeover_control_phase=hall;return hall;}
        if(!d.tracking){takeover_latch_fallback(G30_TK_FB_NOT_TRACKING);takeover_control_phase=hall;return hall;}
        if(hall_speed<G30_R3G_FALLBACK_MIN_DPP){takeover_latch_fallback(G30_TK_FB_SPEED);takeover_control_phase=hall;return hall;}
        if(abs_phase16(pred_err)>=G30_R3G_FALLBACK_ERR_COUNTS ||
           abs_phase16(d.error)>=G30_R3G_FALLBACK_ERR_COUNTS){
            takeover_latch_fallback(G30_TK_FB_PHASE);takeover_control_phase=hall;return hall;
        }

        int16_t off=takeover_blend_offset;
        uint16_t out=(uint16_t)(predicted+off);
        if(off>G30_R3G_BLEND_STEP_COUNTS) off-=G30_R3G_BLEND_STEP_COUNTS;
        else if(off< -G30_R3G_BLEND_STEP_COUNTS) off+=G30_R3G_BLEND_STEP_COUNTS;
        else {off=0;takeover_state=G30_TK_OBSERVER;}
        takeover_blend_offset=off;
        takeover_control_phase=out;
        return out;
    }

    /* R3H observer-only run state. Hall is diagnostic only from here onward.
     * Speed comes from the observer predictor: step_q4 is Q4 electrical DPP. */
    uint16_t observer_speed_dpp=(uint16_t)(abs_i16_u(takeover_step_foc_q4)>>4);
    if(!d.valid){takeover_latch_coast(G30_TK_FB_INVALID);takeover_control_phase=predicted;return predicted;}
    if(!d.tracking){takeover_latch_coast(G30_TK_FB_NOT_TRACKING);takeover_control_phase=predicted;return predicted;}
    if(observer_speed_dpp<G30_R3H_OBSERVER_COAST_MIN_DPP){takeover_latch_coast(G30_TK_FB_SPEED);takeover_control_phase=predicted;return predicted;}

    takeover_state=G30_TK_OBSERVER;
    takeover_control_phase=predicted;
    return predicted;
}
'''
s = s[:start] + newfun + s[end:]
s = s.replace('            snap.takeover_fallbacks=takeover_fallbacks;\n            return snap;',
              '            snap.takeover_fallbacks=takeover_fallbacks;\n            snap.takeover_coast_latched=takeover_coast_request;\n            return snap;', 1)
s = s.replace('    snap.takeover_fallbacks=takeover_fallbacks;\n    return snap;',
              '    snap.takeover_fallbacks=takeover_fallbacks;\n    snap.takeover_coast_latched=takeover_coast_request;\n    return snap;', 1)
p.write_text(s)

replace1("mc_tasks.c",
'''  case RUN:
    /* USER CODE BEGIN MediumFrequencyTask M1 2 */

    /* USER CODE END MediumFrequencyTask M1 2 */

    MCI_ExecBufferedCommands( oMCInterface[M1] );
''',
'''  case RUN:
    /* USER CODE BEGIN MediumFrequencyTask M1 2 */

    /* USER CODE END MediumFrequencyTask M1 2 */
#ifdef G30P
    /* R3H: observer-only exit is Coast. Use the normal motor state machine
     * stop path instead of switching the FOC angle back to Hall. */
    if(g30_fo76_coast_requested())
    {
      (void)MCI_StopMotor( pMCI[M1] );
      break;
    }
#endif

    MCI_ExecBufferedCommands( oMCInterface[M1] );
''')

p = ROOT / "terminal.c"
s = p.read_text()
s = s.replace('FO76_R3G takeover_capable=1', 'FO76_R3H observer_only_fwd=1')
s = s.replace('takeover req=%u state=%u reason=%u control=%u observer=%u hall=%u pred_err=%d blend=%d step_q4=%d entries=%lu fallbacks=%lu',
              'takeover req=%u state=%u reason=%u coast=%u control=%u observer=%u hall=%u pred_err=%d blend=%d step_q4=%d entries=%lu fallbacks=%lu')
s = s.replace('(unsigned)obs.takeover_requested,(unsigned)obs.takeover_state,(unsigned)obs.takeover_fallback_reason,\n            (unsigned)obs.takeover_control_phase',
              '(unsigned)obs.takeover_requested,(unsigned)obs.takeover_state,(unsigned)obs.takeover_fallback_reason,\n            (unsigned)obs.takeover_coast_latched,(unsigned)obs.takeover_control_phase')
s = s.replace('R3G takeover ARM requested; Hall remains active until observer qualifies',
              'R3H FWD observer-only ARM requested; Hall used only for entry/blend')
s = s.replace('R3G takeover OFF requested; Hall angle selected on next FOC tick',
              'R3H takeover OFF requested')
s = s.replace('R3G req=%u state=%u reason=%u entries=%lu fallbacks=%lu',
              'R3H req=%u state=%u reason=%u coast=%u entries=%lu fallbacks=%lu')
s = s.replace('(unsigned)tk.takeover_requested,(unsigned)tk.takeover_state,(unsigned)tk.takeover_fallback_reason,\n            (unsigned long)tk.takeover_entries',
              '(unsigned)tk.takeover_requested,(unsigned)tk.takeover_state,(unsigned)tk.takeover_fallback_reason,\n            (unsigned)tk.takeover_coast_latched,(unsigned long)tk.takeover_entries')
p.write_text(s)

print("R3H transform applied")
