from pathlib import Path

root=Path("SOURCE_KOXX3")

p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-MOTORCORE-R1.1-TIMING"'
new='#define HW_NAME "SESC-DRV126-MOTORCORE-R1.2-LOADSYM"'
assert old in s
p.write_text(s.replace(old,new,1))

p=root/"common_files/src/mc_tasks.c"
s=p.read_text()

# Keep the proven R1.1 timing/control path. Only widen the bench-load guards.
assert "#define G30_DRV126_R1_MAX_QREF_U 1500" in s
assert "#define G30_DRV126_R1_MAX_PHASE_U 2500" in s
s=s.replace("#define G30_DRV126_R1_MAX_QREF_U 1500",
            "#define G30_DRV126_R1_MAX_QREF_U 3800",1)
s=s.replace("#define G30_DRV126_R1_MAX_PHASE_U 2500",
            "#define G30_DRV126_R1_MAX_PHASE_U 5000",1)

# Add a tiny coherent Hall/angle snapshot from the actual DRV126 control sample.
needle="volatile uint8_t g30_drv126_r1_div=0u,g30_drv126_r1_sec=0u,g30_drv126_r1_reason=0u;"
assert needle in s
s=s.replace(needle,needle+"\nvolatile int16_t g30_drv126_r12_angle=0;\nvolatile uint8_t g30_drv126_r12_hall=0u;",1)

needle="""  int32_t alpha=ia;
  int32_t beta=((ia+2*ib)*2365)>>12;
  int32_t iq,id;
  g30_drv126_stock_park(alpha,beta,(uint16_t)angle,&iq,&id);
"""
repl="""  int32_t alpha=ia;
  int32_t beta=((ia+2*ib)*2365)>>12;
  int32_t iq,id;
  g30_drv126_r12_angle=angle;
  g30_drv126_r12_hall=HALL_read(&HALL_M1);
  g30_drv126_stock_park(alpha,beta,(uint16_t)angle,&iq,&id);
"""
assert needle in s
s=s.replace(needle,repl,1)

s=s.replace("DRV126 MotorCore R1.1 timing-fixed takeover",
            "DRV126 MotorCore R1.2 load/symmetry takeover",1)
p.write_text(s)

p=root/"common_files/src/terminal.c"
s=p.read_text()

s=s.replace("DRV126R11 mode=GATED_4K_TIMING","DRV126R12 mode=LOADSYM_4K",1)
s=s.replace("DRV126R11 command_ok=","DRV126R12 command_ok=",1)
s=s.replace("DRV126R11 guard maxQrefU=1500 maxPhaseU=2500 railRaw=80..3920 div=%u trips=%u hall=%u pwmOff=%u",
            "DRV126R12 guard maxQrefU=3800 maxPhaseU=5000 railRaw=80..3920 div=%u trips=%u hall=%u pwmOff=%u",1)
s=s.replace("DRV126R11 core qrefU=","DRV126R12 core qrefU=",1)
s=s.replace("DRV126R11 PWM sec=","DRV126R12 PWM sec=",1)
s=s.replace("DRV126R11 timing cycles=","DRV126R12 timing cycles=",1)

needle='''        commands_printf(phandle,"DRV126R12 PWM sec=%u ccr=%u,%u,%u",
            (unsigned)g30_drv126_r1_sec,(unsigned)g30_drv126_r1_c1,
            (unsigned)g30_drv126_r1_c2,(unsigned)g30_drv126_r1_c3);'''
assert needle in s
repl=needle+'''
        extern volatile int16_t g30_drv126_r12_angle;
        extern volatile uint8_t g30_drv126_r12_hall;
        commands_printf(phandle,"DRV126R12 sync hallRaw=%u elAngle=%d",
            (unsigned)g30_drv126_r12_hall,(int)g30_drv126_r12_angle);'''
s=s.replace(needle,repl,1)
p.write_text(s)

print("DRV126 R1.2 load/symmetry applied: unchanged R1.1 timing, 3A bench headroom, coherent Hall/angle snapshot")
