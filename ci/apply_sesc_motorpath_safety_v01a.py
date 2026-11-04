from pathlib import Path

root=Path("SOURCE_KOXX3")

# Safety V0.1A: remove experimental IWDG runtime start/feed after hardware report
# showed dashboard/throttle communication regression. Keep all other safety fixes.
p=root/"common_files/src/defines.h"
s=p.read_text()
assert '#define HW_NAME "SESC-MOTORPATH-SAFETY-V0.1"' in s
p.write_text(s.replace('#define HW_NAME "SESC-MOTORPATH-SAFETY-V0.1"',
                       '#define HW_NAME "SESC-MOTORPATH-SAFETY-V0.1A"'))

p=root/"common_files/src/task_LED.c"
s=p.read_text()
block='''#ifdef G30P
static void g30_safety_iwdg_start(void){
\t/* Nominal ~2 s: LSI ~40 kHz / 64 / 1250. Actual LSI tolerance is wide,
\t * still vastly longer than the 10 ms health-task cadence. */
\tIWDG->KR = 0x5555u;
\tIWDG->PR = 4u;       /* /64 */
\tIWDG->RLR = 1250u;
\twhile(IWDG->SR != 0u) { }
\tIWDG->KR = 0xAAAAu;
\tIWDG->KR = 0xCCCCu;
}
static inline void g30_safety_iwdg_feed(void){
\tIWDG->KR = 0xAAAAu;
}
#endif'''
assert block in s
s=s.replace(block,'',1)

block='''#ifdef G30P
\t/* Start only after task creation/runtime init. A pre-runtime boot problem remains
\t * recoverable without entering a watchdog reset loop. */
\tg30_safety_iwdg_start();
#endif
'''
assert block in s
s=s.replace(block,'',1)

block='''#ifdef G30P
\t\tg30_safety_iwdg_feed();
#endif
'''
assert block in s
s=s.replace(block,'',1)
p.write_text(s)

# Keep the diagnostic line but make status explicit: watchdog is intentionally OFF.
p=root/"common_files/src/terminal.c"
s=p.read_text()
old='''        commands_printf(phandle,"MP safety iwdg_pr=%lu iwdg_rlr=%lu reset_csr=%08lx break_en=%u",
            (unsigned long)IWDG->PR,(unsigned long)IWDG->RLR,(unsigned long)RCC->CSR,
            (unsigned)((TIM1->BDTR & TIM_BDTR_BKE)!=0u));'''
new='''        commands_printf(phandle,"MP safety iwdg=OFF reset_csr=%08lx break_en=%u",
            (unsigned long)RCC->CSR,
            (unsigned)((TIM1->BDTR & TIM_BDTR_BKE)!=0u));'''
assert old in s
p.write_text(s.replace(old,new,1))

print("SESC Motorpath Safety V0.1A applied: IWDG runtime experiment removed")
