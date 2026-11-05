from pathlib import Path

root=Path("SOURCE_KOXX3")

p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-MOTORCORE-R1.2-LOADSYM"'
new='#define HW_NAME "SESC-DRV126-MOTORCORE-R1.3-PITRACE"'
assert old in s
p.write_text(s.replace(old,new,1))

p=root/"common_files/src/mc_tasks.c"
s=p.read_text()

# Diagnostic-only accessor: no control law or timing changes, no new state.
needle="""static int32_t g30_drv126_sh_q_acc=0;
static int32_t g30_drv126_sh_d_acc=0;
"""
assert needle in s
repl=needle+"""
void g30_drv126_r13_get_pi_state(int32_t *qacc,int32_t *dacc){
  if(qacc)*qacc=g30_drv126_sh_q_acc;
  if(dacc)*dacc=g30_drv126_sh_d_acc;
}
"""
s=s.replace(needle,repl,1)
s=s.replace("DRV126 MotorCore R1.2 load/symmetry takeover",
            "DRV126 MotorCore R1.3 PI-fidelity trace",1)
p.write_text(s)

p=root/"common_files/src/terminal.c"
s=p.read_text()
s=s.replace("DRV126R12 mode=LOADSYM_4K","DRV126R13 mode=PITRACE_4K",1)
s=s.replace("DRV126R12 command_ok=","DRV126R13 command_ok=",1)
s=s.replace("DRV126R12 guard maxQrefU=3800 maxPhaseU=5000 railRaw=80..3920 div=%u trips=%u hall=%u pwmOff=%u",
            "DRV126R13 guard maxQrefU=3800 maxPhaseU=5000 railRaw=80..3920 div=%u trips=%u hall=%u pwmOff=%u",1)
s=s.replace("DRV126R12 core qrefU=","DRV126R13 core qrefU=",1)
s=s.replace("DRV126R12 PWM sec=","DRV126R13 PWM sec=",1)
s=s.replace("DRV126R12 sync hallRaw=","DRV126R13 sync hallRaw=",1)
s=s.replace("DRV126R12 timing cycles=","DRV126R13 timing cycles=",1)

needle='''        commands_printf(phandle,"DRV126R13 timing cycles=%u max=%u budget=4000",
            (unsigned)g30_drv126_r11_cycles_last,(unsigned)g30_drv126_r11_cycles_max);'''
assert needle in s
repl=needle+'''
        extern void g30_drv126_r13_get_pi_state(int32_t *qacc,int32_t *dacc);
        int32_t r13_qacc=0,r13_dacc=0;
        g30_drv126_r13_get_pi_state(&r13_qacc,&r13_dacc);
        commands_printf(phandle,"DRV126R13 pi qAcc=%ld dAcc=%ld qErr=%d dErr=%d",
            (long)r13_qacc,(long)r13_dacc,
            (int)g30_drv126_sh_qref_u-(int)g30_drv126_sh_iq_u,
            -(int)g30_drv126_sh_id_u);'''
s=s.replace(needle,repl,1)
p.write_text(s)

print("DRV126 R1.3 PI trace applied: diagnostics only, control path byte-equivalent to R1.2 apart from reporting code")
